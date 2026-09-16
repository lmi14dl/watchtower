#!/usr/bin/env python3

#!/usr/bin/env python3

import json
from pathlib import Path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import upsert_program
from config import config

def scan_json_files():
    directory = Path(config().get("WATCH_DIR") + '/programs')

    if not directory.exists():
        print(f"Directory does not exist: {directory}")
        return

    for json_file in directory.rglob("*.json"):
        print(f"\n=== {json_file} ===")

        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            upsert_program(data.get('program_name'), data.get('scopes'), data.get('ooscopes'), {})

        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
        except Exception as e:
            print(f"Error reading file: {e}")


if __name__ == "__main__":
    scan_json_files()