#!/usr/bin/env python3
import sys, os, subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *
from config import config
from logutil import get_logger, log_info, log_error, log_success, log_warn, log_phase

logger = get_logger("watch_enum_all")

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

if __name__ == "__main__":
    log_step(logger, "Starting subdomain enumeration for all programs")

    programs = Programs.objects.all()
    total_programs = len(programs)
    log_info(logger, f"Found {total_programs} programs to enumerate")

    for i, program in enumerate(programs, 1):
        program_name = program.program_name
        log_info(logger, f"[{i}/{total_programs}] Processing program: {program_name}")
        scopes = program.scopes

        for scope in scopes:
            log_info(logger, f"  Enumerating subdomains for scope: {scope}")
            enum_path = config().get("WATCH_DIR") + '/enum'

            modules = [
                ('crtsh', f"python3 {enum_path}/watch_crtsh.py {scope}"),
                ('subfinder', f"python3 {enum_path}/watch_subfinder.py {scope}"),
                ('abuse', f"python3 {enum_path}/watch_abuse.py {scope}"),
                ('wayback', f"python3 {enum_path}/watch_wayback.py {scope}"),
                ('gau', f"python3 {enum_path}/watch_gau.py {scope}"),
            ]

            for module_name, cmd in modules:
                try:
                    log_info(logger, f"    Running {module_name} for {scope}")
                    run_command_in_bash(cmd)
                    log_success(logger, f"    {module_name} completed for {scope}")
                except Exception as e:
                    log_error(logger, f"    {module_name} failed for {scope}: {e}")

        log_info(logger, f"Completed program: {program_name}")
        log_info(logger, f"{'─' * 50}")

    log_success(logger, f"Enumeration pipeline complete for {total_programs} programs")
