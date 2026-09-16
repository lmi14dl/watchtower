#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import upsert_program
from config import config
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_sync_programs")

def scan_json_files():
    directory = Path(config().get("WATCH_DIR") + '/programs')

    if not directory.exists():
        log_error(logger, f"Directory does not exist: {directory}")
        return

    json_files = list(directory.rglob("*.json"))
    log_info(logger, f"Found {len(json_files)} program JSON files to sync")

    for json_file in json_files:
        log_info(logger, f"Processing {json_file.name}")
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            upsert_program(
                data.get('program_name'),
                data.get('scopes'),
                data.get('ooscopes'),
                {}
            )
            log_success(logger, f"Synced program: {data.get('program_name')}")

        except json.JSONDecodeError as e:
            log_error(logger, f"Invalid JSON in {json_file}: {e}")
        except Exception as e:
            log_error(logger, f"Error reading {json_file}: {e}")

if __name__ == "__main__":
    log_step(logger, "Starting program sync")
    scan_json_files()
    log_success(logger, "Program sync complete")
