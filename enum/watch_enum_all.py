#!/usr/bin/env python3
import sys, os, subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *
from config import config


def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error occured:", result.stderr)
            return False

        return result.stdout.splitlines()
        
    except subprocess.CalledProcessError as exc:
        print("Status: FAIL", exc.returncode, exc.output)



if __name__ == "__main__":
    programs = Programs.objects.all()

    for program in programs:
        program_name = program.program_name
        print(f"[{current_time()}] let's go for {program_name} program...")
        scopes = program.scopes

        for scope in scopes:
            print(f"[{current_time()}] enumerating subdomains for {scope} domain...")
            enum_path = config().get("WATCH_DIR") + '/enum'
            run_command_in_bash(f"python3 {enum_path}/watch_crtsh.py {scope}")
            run_command_in_bash(f"python3 {enum_path}/watch_subfinder.py {scope}")
            run_command_in_bash(f"python3 {enum_path}/watch_abuse.py {scope}")
            run_command_in_bash(f"python3 {enum_path}/watch_wayback.py {scope}")
            # run_command_in_bash(f"python3 {enum_path}/watch_gau.py {scope}")
            # TODO: add waybackurl module
            # run_command_in_bash(f"python3 {enum_path}/another_module.py {scope}")

        print("---------------------------------------------")
