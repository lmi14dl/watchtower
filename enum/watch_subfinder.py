#!/usr/bin/env python3
import sys, os, subprocess, shlex
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from runutil import run_bash
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_subfinder")

def run_command_in_bash(command):
    try:
        result = run_bash(command)

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
    # "-all" (every source) is much heavier: opt in with SUBFINDER_ALL=1
    all_flag = " -all" if os.environ.get('SUBFINDER_ALL', '0') == '1' else ""
    rate = os.environ.get('SUBFINDER_RATE_LIMIT', '30')
    command = f"subfinder -d {shlex.quote(domain)} -silent -rl {rate}{all_flag}"
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

    from runutil import missing_tools
    if missing_tools(['subfinder']):
        log_error(logger, "Required tool not found in PATH: subfinder")
        sys.exit(1)

    domain = sys.argv[1]
    program = Programs.objects(scopes=domain).first()

    if program:
        log_info(logger, f"Running subfinder module for '{domain}' (program: {program.program_name})")
        subs = subfinder(domain)

        if subs:
            upsert_subdomains_bulk(program.program_name, subs, 'subfinder')
            log_success(logger, f"Upserted {len(subs)} subdomains for {domain}")
        else:
            log_warn(logger, f"No subdomains found for {domain}")
    else:
        log_error(logger, f"Scope {domain} does not exist in any program!")
