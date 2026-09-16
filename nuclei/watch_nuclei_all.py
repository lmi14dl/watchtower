#!/usr/bin/env python3
import sys, os, subprocess, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *

class colors:
    # Reset
    RESET = "\033[0m"

    # Regular colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"


def send_discord_message(message):
    data = {
        "content": message
    }
    response = requests.post(config().get('WEBHOOK_URL'), json=data)
    if response.status_code == 204:
        pass
    else:
        print(response.status_code)

def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error occured:", result.stderr)
            return False

        return result.stdout
        
    except subprocess.CalledProcessError as exc:
        print("Status: FAIL", exc.returncode, exc.output)

def create_tempfile(data):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        temp_file.write(data)
        return temp_file.name

def nuclei(urls):
    urls_file = create_tempfile("\n".join(urls) + "\n")

    # Use templates.txt for the list of templates, pass config for headers/exclusions
    templates_file = config().get('WATCH_DIR') + '/nuclei/templates.txt'
    nuclei_config = config().get('WATCH_DIR') + '/nuclei/public-config.yaml'

    command = f"nuclei -l {urls_file} -config {nuclei_config}"

    # If templates.txt exists, use it as the template list
    if os.path.exists(templates_file):
        # Convert line-delimited template list to comma-separated -t arguments
        # or use -t with the file via -list-templates flag
        command = f"nuclei -l {urls_file} -config {nuclei_config} -t {templates_file}"

    print(f"{colors.GRAY}Executing: {command}{colors.RESET}")
    results = run_command_in_bash(command)

    if results and results != '':
        send_discord_message(results)
        print(f"{colors.GREEN}Nuclei scan complete. Results sent to Discord.{colors.RESET}")
    elif results is False:
        print(f"{colors.RED}Nuclei scan failed{colors.RESET}")
    else:
        print(f"{colors.GRAY}No nuclei findings{colors.RESET}")

    # Cleanup temp file
    os.unlink(urls_file)
    return True

if __name__ == "__main__":
    https_obj = HTTP.objects().all()
    if https_obj:
        print(f"[{current_time()}] Running Nuclei module for all http services")
        nuclei([http_obj.url for http_obj in https_obj])
    else:
        print(f"[{current_time()}] No HTTP services found in database")
