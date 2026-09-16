#!/usr/bin/env python3
import sys, os, subprocess, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *

def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error occured:", result.stderr)
            return False

        return result.stdout.splitlines()
        
    except subprocess.CalledProcessError as exc:
        print("Status: FAIL", exc.returncode, exc.output)

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def subfinder(domain):
    command = f"waybackurls {domain} | unfurl domains | sort -u"

    # running commands    
    print(f"{colors.GRAY}Executing commands: {command}{colors.RESET}")
    res = run_command_in_bash(command)

    res_num = len(res) if res else 0
    print(f"{colors.GRAY}done for {domain}, results: {res_num}{colors.RESET}")

    return res

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else 0

    if domain is False:
        print(f"Usage: watch_wayback domain")
        sys.exit()

    program = Programs.objects(scopes=domain).first()

    if program:
        print(f"[{current_time()}] Running waybackurls module for '{domain}'")
        subs = subfinder(domain)
        # TODO: save in file

        # save in watchtower database
        for sub in subs:
            if re.search(r'\.' + re.escape(domain) + r'$', sub, re.IGNORECASE):
                upsert_subdomains(program.program_name, sub, 'waybackurls')
    else:
        print(f"[{current_time()}] scope {domain} does not exist!")


