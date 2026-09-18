#!/usr/bin/env python3
"""
Watchtower Cron Scheduler

Runs the full watchtower pipeline at a configurable interval.
Supports both local (system cron) and Docker execution modes.

Usage:
    # Run whole pipeline 2 times a day (every 12 hours)
    python3 scheduler.py --runs 2

    # Run whole pipeline 4 times a day (every 6 hours)
    python3 scheduler.py --runs 4

    # Run every N hours
    python3 scheduler.py --interval 8

    # Run once immediately
    python3 scheduler.py --once

    # Run in Docker mode (uses docker compose)
    python3 scheduler.py --runs 2 --docker

    # Install as a system cron job
    python3 scheduler.py --install-cron --runs 2

    # Remove the cron job
    python3 scheduler.py --remove-cron
"""
import argparse
import subprocess
import sys
import os
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "scheduler_state.json")
CRON_MARKER = "# WATCHTOWER-CRON"

# Setup scheduler logger
sys.path.insert(0, SCRIPT_DIR)
from logutil import get_logger, log_info, log_error, log_success, log_warn, log_step, log_phase, Colors
from notifier import notify, get_enabled_services

logger = get_logger("scheduler")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_run": None, "run_count": 0, "total_runs": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_pipeline_docker():
    """Run pipeline via docker compose"""
    log_info(logger, "Running watchtower pipeline via Docker")
    result = subprocess.run(
        ["docker", "compose", "run", "--rm", "watchtower", "all"],
        cwd=SCRIPT_DIR,
        capture_output=False,
    )
    return result.returncode == 0


def run_pipeline_local():
    """Run pipeline locally using watch.sh"""
    log_info(logger, "Running watchtower pipeline locally")
    result = subprocess.run(
        ["bash", os.path.join(SCRIPT_DIR, "watch.sh")],
        capture_output=False,
    )
    return result.returncode == 0


def run_pipeline(phase="all"):
    """Run a specific pipeline phase or all phases"""
    env = os.environ.copy()
    env["PYTHONPATH"] = SCRIPT_DIR
    env["MONGO_HOST"] = os.environ.get("MONGO_HOST", "127.0.0.1")

    phases = {
        "sync_programs": ["python3", f"{SCRIPT_DIR}/programs/watch_sync_programs.py"],
        "enum_all": ["python3", f"{SCRIPT_DIR}/enum/watch_enum_all.py"],
        "ns_all": ["python3", f"{SCRIPT_DIR}/ns/watch_ns_all.py"],
        "httpx_all": ["python3", f"{SCRIPT_DIR}/http/watch_http_all.py"],
        # "nuclei_all": ["python3", f"{SCRIPT_DIR}/nuclei/watch_nuclei_all.py"],
    }

    if phase == "all":
        order = ["sync_programs", "enum_all", "ns_all", "httpx_all", "nuclei_all"]
    else:
        order = [phase]

    success = True
    for p in order:
        log_phase(logger, f"Phase: {p}", Colors.CYAN)
        cmd = phases[p]
        result = subprocess.run(cmd, env=env, capture_output=False)
        if result.returncode != 0:
            log_error(logger, f"Phase {p} failed with code {result.returncode}")
            success = False
            break  # Stop pipeline on failure
    return success


def schedule_run(run_count, interval_hours=None, docker_mode=False, phase="all"):
    """
    Schedule the pipeline to run `run_count` times per day, or every `interval_hours` hours.
    """
    if interval_hours:
        interval = interval_hours
    elif run_count:
        interval = 24 / run_count
    else:
        interval = 12  # default: twice a day

    state = load_state()
    state["total_runs"] = run_count if run_count else None
    state["interval_hours"] = interval
    state["docker_mode"] = docker_mode
    state["phase"] = phase
    save_state(state)

    log_step(logger, "Starting Watchtower Scheduler")
    log_info(logger, f"Interval: every {interval} hours")
    log_info(logger, f"Runs per day: {24 / interval:.1f}")
    log_info(logger, f"Mode: {'Docker' if docker_mode else 'Local'}")
    log_info(logger, f"Phase: {phase}")
    log_info(logger, f"State file: {STATE_FILE}")
    print()
    log_info(logger, "Press Ctrl+C to stop.")
    print()

    while True:
        ts = datetime.now().isoformat()
        if docker_mode:
            success = run_pipeline_docker()
        else:
            success = run_pipeline(phase)

        status = "OK" if success else "FAILED"
        log_info(logger, f"Run completed: {status}")

        state = load_state()
        state["last_run"] = datetime.now().isoformat()
        state["run_count"] += 1
        save_state(state)

        # Send notification about run completion
        services = get_enabled_services()
        if services:
            msg = f"Watchtower pipeline run #{state['run_count']} completed: {status}"
            notify(msg)

        log_info(logger, f"Next run in {interval} hours ({interval * 3600} seconds)")
        time.sleep(interval * 3600)


def run_once(docker_mode=False, phase="all"):
    """Run the pipeline once immediately"""
    log_step(logger, "Running Watchtower Pipeline (single run)")
    ts = datetime.now().isoformat()
    if docker_mode:
        success = run_pipeline_docker()
    else:
        success = run_pipeline(phase)

    state = load_state()
    state["last_run"] = datetime.now().isoformat()
    state["run_count"] += 1
    save_state(state)

    status = "OK" if success else "FAILED"
    log_info(logger, f"Run #{state['run_count']} completed: {status}")

    # Send notification about run completion
    services = get_enabled_services()
    if services:
        msg = f"Watchtower pipeline run #{state['run_count']} completed: {status}"
        notify(msg)
    return success


def install_cron(run_count, docker_mode=False, phase="all"):
    """Install a cron job that runs the scheduler"""
    if docker_mode:
        cmd = f"cd {SCRIPT_DIR} && /usr/bin/python3 {SCRIPT_DIR}/scheduler.py --runs {run_count} --docker"
    else:
        cmd = f"cd {SCRIPT_DIR} && /usr/bin/python3 {SCRIPT_DIR}/scheduler.py --runs {run_count}"

    interval = 24 / run_count
    hours_interval = max(1, int(round(interval)))

    cron_entry = f"0 */{hours_interval} * * * {cmd} >> {SCRIPT_DIR}/logs/scheduler_cron.log 2>&1 {CRON_MARKER}"

    try:
        existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        crontab = existing.stdout if existing.returncode == 0 else ""
    except FileNotFoundError:
        log_error(logger, "cron is not installed. Please install cron first.")
        return

    lines = [l for l in crontab.splitlines() if CRON_MARKER not in l]
    lines.append(cron_entry)
    new_crontab = "\n".join(lines) + "\n"

    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    log_success(logger, f"Cron job installed: runs every {hours_interval} hours")
    log_info(logger, f"  Command: {cmd}")
    log_info(logger, f"  Log: {SCRIPT_DIR}/logs/scheduler_cron.log")


def remove_cron():
    """Remove watchtower cron job"""
    try:
        existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if existing.returncode != 0:
            log_info(logger, "No crontab found.")
            return
        lines = [l for l in existing.stdout.splitlines() if CRON_MARKER not in l]
        new_crontab = "\n".join(lines) + "\n"
        subprocess.run(["crontab", "-"], input=new_crontab, text=True)
        log_success(logger, "Watchtower cron job removed.")
    except FileNotFoundError:
        log_error(logger, "cron is not installed.")


def show_status():
    """Show scheduler status"""
    state = load_state()
    log_step(logger, "Watchtower Scheduler Status")
    log_info(logger, f"Last run: {state.get('last_run', 'Never')}")
    log_info(logger, f"Run count: {state.get('run_count', 0)}")
    log_info(logger, f"Interval: {state.get('interval_hours', 'Not set')} hours")
    mode = "Docker" if state.get("docker_mode") else "Local"
    log_info(logger, f"Mode: {mode}")
    log_info(logger, f"Phase: {state.get('phase', 'all')}")


def main():
    parser = argparse.ArgumentParser(
        description="Watchtower pipeline scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--runs", type=int, help="Number of runs per day (e.g. 2 = every 12 hours)")
    parser.add_argument("--interval", type=float, help="Interval in hours (overrides --runs)")
    parser.add_argument("--once", action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--docker", action="store_true", help="Use docker compose to run pipeline")
    parser.add_argument("--phase", type=str, default="all",
                        choices=["all", "sync_programs", "enum_all", "ns_all", "httpx_all", "nuclei_all"],
                        help="Phase to run (default: all)")
    parser.add_argument("--install-cron", action="store_true", help="Install as system cron job")
    parser.add_argument("--remove-cron", action="store_true", help="Remove cron job")
    parser.add_argument("--status", action="store_true", help="Show scheduler status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.remove_cron:
        remove_cron()
        return

    if args.once:
        success = run_once(docker_mode=args.docker, phase=args.phase)
        sys.exit(0 if success else 1)

    if args.install_cron:
        run_count = args.runs or 2
        install_cron(run_count, docker_mode=args.docker, phase=args.phase)
        return

    # Scheduled mode
    run_count = args.runs
    interval_hours = args.interval

    if not run_count and not interval_hours:
        run_count = 2  # default: twice a day

    try:
        schedule_run(
            run_count=run_count,
            interval_hours=interval_hours,
            docker_mode=args.docker,
            phase=args.phase,
        )
    except KeyboardInterrupt:
        log_info(logger, "Scheduler stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
