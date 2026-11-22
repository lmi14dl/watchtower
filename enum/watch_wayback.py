#!/usr/bin/env python3
import sys, os, subprocess, re, shlex
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from runutil import run_bash
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_wayback")

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

def waybackurls(domain):
    max_urls = int(os.environ.get('ENUM_MAX_URLS', '500000'))  # cap huge result sets
    command = f"waybackurls {shlex.quote(domain)} | head -n {max_urls} | unfurl domains | sort -u"
    log_info(logger, f"Executing: {command}")
    res = run_command_in_bash(command)
    if not res:
        log_warn(logger, f"No results from waybackurls for {domain}")
        return []
    res_num = len(res)
    log_success(logger, f"waybackurls: {res_num} results for {domain}")
    return res

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_wayback <domain>")
        sys.exit(1)

    from runutil import missing_tools
    if missing_tools(['waybackurls', 'unfurl']):
        log_error(logger, "Required tool not found in PATH: waybackurls / unfurl")
        sys.exit(1)

    domain = sys.argv[1]
    program = Programs.objects(scopes=domain).first()

    if program:
        log_info(logger, f"Running waybackurls module for '{domain}' (program: {program.program_name})")
        subs = waybackurls(domain)

        if subs:
            upsert_subdomains_bulk(program.program_name, subs, 'waybackurls')
            log_success(logger, f"Upserted waybackurls results for {domain}")
        else:
            log_warn(logger, f"No subdomains found via waybackurls for {domain}")
    else:
        log_error(logger, f"Scope {domain} does not exist in any program!")
