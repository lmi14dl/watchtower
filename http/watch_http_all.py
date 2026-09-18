#!/usr/bin/env python3
import sys, os, subprocess, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn, log_step

logger = get_logger("watch_http_all")

def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
        if result.returncode != 0:
            log_error(logger, f"Command failed: {command}")
            log_error(logger, f"stderr: {result.stderr}")
            return False
        return result.stdout
    except subprocess.CalledProcessError as exc:
        log_error(logger, f"Command exception: {exc}")

def create_tempfile(data):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        temp_file.write(data)
        return temp_file.name

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def httpx(subdomains_array, domain):
    if not subdomains_array:
        log_warn(logger, f"No subdomains to probe for {domain}")
        return True

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

    log_info(logger, f"Running httpx for {len(subdomains_array)} subdomains in {domain}")
    results = run_command_in_bash(command)

    if not results or results is False:
        log_warn(logger, f"No HTTP results for {domain}")
        os.unlink(subdomains_file)
        return True

    count = 0
    for line in results.splitlines() if isinstance(results, str) else results:
        if not line.strip():
            continue
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
            count += 1
        except json.JSONDecodeError:
            log_error(logger, f"Failed to parse httpx JSON line: {line[:200]}")

    log_success(logger, f"httpx: {count} HTTP services found for {domain}")
    os.unlink(subdomains_file)
    return True

if __name__ == "__main__":
    log_step(logger, "Starting HTTP probing for all programs")

    programs = Programs.objects().all()
    total_programs = len(programs)
    log_info(logger, f"Found {total_programs} programs to probe")

    for i, program in enumerate(programs, 1):
        for scope in program.scopes:
            obj_lives = LiveSubdomains.objects(scope=scope)
            if obj_lives:
                log_info(logger, f"[{i}/{total_programs}] [{program.program_name}] Probing {scope}")
                httpx([obj_live.subdomain for obj_live in obj_lives], scope)
            else:
                log_warn(logger, f"No live subdomains for scope {scope}")

    log_success(logger, "HTTP probing pipeline complete")

if __name__ == "__main__" and len(sys.argv) > 1:
    # Single domain mode
    domain = sys.argv[1]
    obj_lives = LiveSubdomains.objects(scope=domain)
    if obj_lives:
        log_info(logger, f"Running httpx module for '{domain}'")
        httpx([obj_live.subdomain for obj_live in obj_lives], domain)
    else:
        log_warn(logger, f"No live subdomains found for {domain}")
