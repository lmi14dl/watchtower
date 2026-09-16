#!/usr/bin/env python3
import sys, os, subprocess, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *


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

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def httpx(subdomains_array, domain):
    # with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
    #     for sub in subdomains_array:
    #         temp_file.write(sub + "\n")

    # subdomains_file = temp_file.name
    for sub in subdomains_array:
        # print(sub)
        command = f"echo {sub} | httpx -json -favicon -fhr -tech-detect -irh -include-chain -timeout 5 -retries 3 -threads 5 -rate-limit 5 -ports 443 -extract-fqdn -silent -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0' -H 'Referrer: https://{sub}'"

        print(f"{colors.GRAY}Executing commands: {command}{colors.RESET}")
        results = run_command_in_bash(command)
        if results != '':
            json_obj = json.loads(results)
            upsert_http({
                "subdomain": sub,
                "scope": domain,
                "ips": json_obj.get('a', ''),
                "tech": json_obj.get('tech', []),
                "title": json_obj.get('title', ''),
                "status_code": json_obj.get('status_code'),
                "headers": json_obj.get('header', {}),
                "url": json_obj.get('url'),
                "final_url": json_obj.get('final_url', ''),
                "favicon": json_obj.get('favicon', '')
            })

    return True

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else 0

    if domain is False:
        print(f"Usage: watch_http domain")
        sys.exit()

    obj_lives = LiveSubdomains.objects(scope=domain)

    if obj_lives:
        print(f"[{current_time()}] Running httpx module for '{domain}'")
        httpx([obj_live.subdomain for obj_live in obj_lives], domain)

