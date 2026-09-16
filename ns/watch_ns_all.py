#!/usr/bin/env python3
import sys, os, subprocess, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_ns_all")

def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            log_error(logger, f"Command failed: {command}")
            log_error(logger, f"stderr: {result.stderr}")
            return False

        return result.stdout.splitlines()
        
    except subprocess.CalledProcessError as exc:
        log_error(logger, f"Command exception: {exc}")

def create_tempfile(data):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        temp_file.write(data)
        return temp_file.name

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def dnsx(subdomains_array, domain):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        for sub in subdomains_array:
            temp_file.write(sub + "\n")
    subdomains_file = temp_file.name
    command = f"shuffledns -l {subdomains_file} -silent -d {domain} -mode resolve -r {config()['RESOLVERS_PATH']} -t 10 | dnsx -silent -resp -json -r {config()['RESOLVERS_PATH']}"
    log_info(logger, f"Executing: {command}")
    results = run_command_in_bash(command)

    if not results:
        log_warn(logger, f"No DNS results for {domain}")
        os.unlink(subdomains_file)
        return True

    count = 0
    for res in results:
        try:
            res = json.loads(res)
            upsert_lives({
                'subdomain': res['host'],
                'domain': domain,
                'ips': res.get('a', []),
                'cdn': None
            })
            count += 1
        except (json.JSONDecodeError, KeyError) as e:
            log_error(logger, f"Failed to parse DNS result: {e}")

    log_success(logger, f"DNS resolution: {count} live hosts for {domain}")
    os.unlink(subdomains_file)
    return True

if __name__ == "__main__":
    log_step(logger, "Starting DNS resolution for all programs")

    programs = Programs.objects().all()
    total_programs = len(programs)
    log_info(logger, f"Found {total_programs} programs to resolve")

    for i, program in enumerate(programs, 1):
        for scope in program.scopes:
            obj_subs = Subdomains.objects(scope=scope)
            if obj_subs:
                log_info(logger, f"[{i}/{total_programs}] [{program.program_name}] DNS resolving {scope}")
                dnsx([obj_sub.subdomain for obj_sub in obj_subs], scope)
            else:
                log_warn(logger, f"No subdomains found for scope {scope}")

    log_success(logger, "DNS resolution pipeline complete")
