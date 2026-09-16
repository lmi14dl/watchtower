#!/usr/bin/env python3
import sys, os, subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_subfinder")

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

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def subfinder(domain):
    command = f"subfinder -d {domain} -all"
    log_info(logger, f"Executing: {command}")
    res = run_command_in_bash(command)
    if not res:
        log_warn(logger, f"No results from subfinder for {domain}")
        return []
    res_num = len(res)
    log_success(logger, f"subfinder: {res_num} results for {domain}")
    return res

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_subfinder <domain>")
        sys.exit(1)

    domain = sys.argv[1]
    program = Programs.objects(scopes=domain).first()

    if program:
        log_info(logger, f"Running subfinder module for '{domain}' (program: {program.program_name})")
        subs = subfinder(domain)

        if subs:
            for sub in subs:
                try:
                    upsert_subdomains(program.program_name, sub, 'subfinder')
                except Exception as e:
                    log_error(logger, f"Failed to upsert subdomain {sub}: {e}")
            log_success(logger, f"Upserted {len(subs)} subdomains for {domain}")
        else:
            log_warn(logger, f"No subdomains found for {domain}")
    else:
        log_error(logger, f"Scope {domain} does not exist in any program!")
