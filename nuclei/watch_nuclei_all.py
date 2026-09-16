#!/usr/bin/env python3
import sys, os, subprocess, tempfile
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_nuclei_all")

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
    data = {"content": message}
    try:
        response = requests.post(config().get('WEBHOOK_URL'), json=data)
        if response.status_code == 204:
            pass
        else:
            log_error(logger, f"Discord webhook returned status {response.status_code}")
    except Exception as e:
        log_error(logger, f"Failed to send Discord message: {e}")

def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
        if result.returncode != 0:
            log_error(logger, f"Command failed: {command}")
            log_error(logger, f"stderr: {result.stderr}")
            return False
        return result.stdout
    except subprocess.CalledProcessError as exc:
        log_error(logger, f"Command exception: {exc}")

def create_tempfile(data):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
        temp_file.write(data)
        return temp_file.name

def nuclei(urls):
    urls_file = create_tempfile("\n".join(urls) + "\n")

    templates_file = config().get('WATCH_DIR') + '/nuclei/templates.txt'
    nuclei_config = config().get('WATCH_DIR') + '/nuclei/public-config.yaml'

    command = f"nuclei -l {urls_file} -config {nuclei_config} -silent"

    if os.path.exists(templates_file):
        command = f"nuclei -l {urls_file} -config {nuclei_config} -t {templates_file} -silent"

    log_info(logger, f"Executing: {command}")
    results = run_command_in_bash(command)

    if results and results != '':
        send_discord_message(results)
        log_success(logger, f"Nuclei scan complete. {len(results.splitlines())} findings sent to Discord.")
    elif results is False:
        log_error(logger, "Nuclei scan failed")
    else:
        log_info(logger, "No nuclei findings")

    os.unlink(urls_file)
    return True

if __name__ == "__main__":
    log_step(logger, "Starting Nuclei vulnerability scan")

    https_obj = HTTP.objects().all()
    if https_obj:
        urls = [http_obj.url for http_obj in https_obj if http_obj.url]
        log_info(logger, f"Running Nuclei against {len(urls)} HTTP services")
        nuclei(urls)
    else:
        log_warn(logger, "No HTTP services found in database")
