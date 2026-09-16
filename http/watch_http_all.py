#!/usr/bin/env python3
import sys, os, subprocess, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *


class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error occured:", result.stderr)
            return False

        return result.stdout
        
    except subprocess.CalledProcessError as exc:
        print("Status: FAIL", exc.returncode, exc.output)

def create_tempfile(data):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        temp_file.write(data)
        return temp_file.name

def httpx(subdomains_array, domain):
    # Write all subdomains to a single temp file and run httpx once
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        for sub in subdomains_array:
            temp_file.write(sub + "\n")
    subdomains_file = temp_file.name

    command = (
        f"httpx -l {subdomains_file} -json -favicon -fhr -tech-detect -irh "
        f"-include-chain -timeout 5 -retries 3 -threads 50 -rate-limit 10 "
        f"-ports 443,80,8080,8443 -extract-fqdn -silent "
        f"-H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0' "
        f"-H 'Referrer: https://{domain}'"
    )

    print(f"{colors.GRAY}Executing: {command}{colors.RESET}")
    results = run_command_in_bash(command)

    if results and results != '':
        for line in results.splitlines():
            if line.strip():
                try:
                    json_obj = json.loads(line)
                    upsert_http({
                        "subdomain": json_obj.get('input', json_obj.get('host', '')),
                        "scope": domain,
                        "ips": json_obj.get('a', []),
                        "tech": json_obj.get('tech', []),
                        "title": json_obj.get('title', ''),
                        "status_code": json_obj.get('status_code'),
                        "headers": json_obj.get('header', {}),
                        "url": json_obj.get('url'),
                        "final_url": json_obj.get('final_url', ''),
                        "favicon": json_obj.get('favicon', '')
                    })
                except json.JSONDecodeError:
                    print(f"{colors.RED}Failed to parse line: {line[:100]}{colors.RESET}")

    # Cleanup
    os.unlink(subdomains_file)
    return True

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else 0

    if domain is False:
        # Run against all programs and scopes
        programs = Programs.objects().all()
        for program in programs:
            for scope in program.scopes:
                obj_lives = LiveSubdomains.objects(scope=scope)
                if obj_lives:
                    print(f"[{current_time()}] Running httpx module for {scope} subdomains")
                    httpx([obj_live.subdomain for obj_live in obj_lives], scope)
                else:
                    print(f"[{current_time()}] No live subdomains for scope {scope}")
    else:
        # Single domain mode
        obj_lives = LiveSubdomains.objects(scope=domain)
        if obj_lives:
            print(f"[{current_time()}] Running httpx module for '{domain}'")
            httpx([obj_live.subdomain for obj_live in obj_lives], domain)
        else:
            print(f"[{current_time()}] No live subdomains found for {domain}")
