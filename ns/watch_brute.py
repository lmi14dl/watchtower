#!/usr/bin/env python3
import sys, os, subprocess, tempfile
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_brute")

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

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

def create_wordlist(domain):
    wordlist_path = config().get('DNS_BRUTE_WORDLIST')
    with open(wordlist_path, "r", encoding="utf-8") as infile, \
        tempfile.NamedTemporaryFile(delete=False, mode='w') as output_file:
        for line in infile:
            word = line.strip()
            if word:
                output_file.write(f"{word}.{domain}\n")
        return output_file.name

def brute_force(subdomains_array, domain):
    word_list = create_wordlist(domain)
    command = f"shuffledns -list {word_list} -silent -d {domain} -mode resolve -r {config()['RESOLVERS_PATH']} -m $(which massdns) -t 30 -silent | dnsx -silent -a -resp -json -r {config()['RESOLVERS_PATH']}"
    log_info(logger, f"Executing brute force: {command}")
    results = run_command_in_bash(command)

    if not results or results is False:
        log_warn(logger, f"No results from brute force for {domain}")
        os.unlink(word_list)
        return True

    count = 0
    for line in results.splitlines() if isinstance(results, str) else results:
        if not line or not line.strip():
            continue
        try:
            import json
            res = json.loads(line)
            from database.db import upsert_lives
            upsert_lives({
                'subdomain': res['host'],
                'domain': domain,
                'ips': res.get('a', []),
                'cdn': None
            })
            count += 1
        except Exception as e:
            log_error(logger, f"Failed to parse brute force result: {e}")

    log_success(logger, f"Brute force: {count} live hosts for {domain}")
    os.unlink(word_list)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_brute <domain>")
        sys.exit(1)

    domain = sys.argv[1]
    from database.db import Subdomains
    obj_subs = Subdomains.objects(scope=domain)

    if obj_subs:
        log_info(logger, f"Running ShuffleDNS brute force module for '{domain}'")
        brute_force([obj_sub.subdomain for obj_sub in obj_subs], domain)
    else:
        log_warn(logger, f"No subdomains found for scope {domain}")
