#!/usr/bin/env python3
import sys, os, subprocess, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_crtsh")

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

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def crtsh(domain, retries=3):
    import psycopg2
    from psycopg2 import OperationalError
    import time

    for attempt in range(retries):
        try:
            log_info(logger, f"crt.sh query attempt {attempt + 1}/{retries} for {domain}")
            conn = psycopg2.connect(
                host="crt.sh",
                port=5432,
                user="guest",
                dbname="certwatch",
                sslmode="require",
                connect_timeout=15
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                SELECT ci.NAME_VALUE
                FROM certificate_and_identities ci
                WHERE plainto_tsquery('certwatch', %s) @@ identities(ci.CERTIFICATE)
            """, (domain,))

            names = set()
            for (name,) in cur.fetchall():
                if name:
                    name = name.strip().replace(" ", "").lower()
                    if name.endswith("." + domain):
                        names.add(name.lstrip("."))
            cur.close()
            conn.close()
            res = sorted(names)
            res_num = len(res) if res else 0
            log_success(logger, f"crt.sh: {res_num} results for {domain}")
            return res

        except OperationalError as e:
            if attempt < retries - 1:
                log_warn(logger, f"crt.sh connection failed, retrying in 2s: {e}")
                time.sleep(2)
                continue
            log_error(logger, f"crt.sh failed after {retries} attempts: {e}")
            raise e

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_crtsh <domain>")
        sys.exit(1)

    domain = sys.argv[1]
    program = Programs.objects(scopes=domain).first()

    if program:
        log_info(logger, f"Running crt.sh module for '{domain}' (program: {program.program_name})")
        subs = crtsh(domain)

        if subs:
            for sub in subs:
                if re.search(r'\.' + re.escape(domain) + r'$', sub, re.IGNORECASE):
                    upsert_subdomains(program.program_name, sub, 'crtsh')
            log_success(logger, f"Upserted crt.sh results for {domain}")
        else:
            log_warn(logger, f"No subdomains found via crt.sh for {domain}")
    else:
        log_error(logger, f"Scope {domain} does not exist in any program!")
