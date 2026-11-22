#!/usr/bin/env python3
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn, log_step
from runutil import missing_tools
from watch_ns import dnsx, STALE_HOURS

logger = get_logger("watch_ns_all")

if __name__ == "__main__":
    log_step(logger, "Starting DNS resolution for all programs")

    if missing_tools(['dnsx']):
        log_error(logger, "Required tool not found in PATH: dnsx")
        sys.exit(1)

    programs = Programs.objects().all()
    total_programs = len(programs)
    log_info(logger, f"Found {total_programs} programs to resolve (stale after {STALE_HOURS}h)")

    for i, program in enumerate(programs, 1):
        for scope in program.scopes:
            subs = get_subdomains_to_resolve(scope, STALE_HOURS)
            if subs:
                log_info(logger, f"[{i}/{total_programs}] [{program.program_name}] DNS resolving {scope} ({len(subs)} subdomains)")
                dnsx(subs, scope)
            else:
                log_info(logger, f"[{program.program_name}] nothing to resolve for {scope}")

    log_success(logger, "DNS resolution pipeline complete")
