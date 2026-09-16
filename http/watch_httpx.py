#!/usr/bin/env python3
import sys, os, subprocess, tempfile
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_httpx")

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
        f"echo {{}} | httpx -json -favicon -fhr -tech-detect -irh -include-chain "
        f"-timeout 5 -retries 3 -threads 5 -rate-limit 5 -ports 443 -extract-fqdn "
        f"-silent "
        f"-H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0' "
        f"-H 'Referrer: https://{domain}'"
    )

    log_info(logger, f"Running httpx for domain: {domain}")

    count = 0
    for sub in subdomains_array:
        full_command = command.format(sub)
        results = run_command_in_bash(full_command)
        if results and results.strip():
            try:
                json_obj = json.loads(results)
                upsert_http({
                    "subdomain": sub,
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
                log_error(logger, f"Failed to parse httpx JSON for {sub}")

    log_success(logger, f"httpx: {count} HTTP services probed for {domain}")
    os.unlink(subdomains_file)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_httpx <domain>")
        sys.exit(1)

    domain = sys.argv[1]
    obj_lives = LiveSubdomains.objects(scope=domain)

    if obj_lives:
        log_info(logger, f"Running httpx module for '{domain}'")
        httpx([obj_live.subdomain for obj_live in obj_lives], domain)
    else:
        log_warn(logger, f"No live subdomains found for {domain}")
