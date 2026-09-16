#!/usr/bin/env python3
import sys, os, subprocess, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *
import psycopg2
from psycopg2 import OperationalError
import time

def run_command_in_bash(command):
    try:
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error occured:", result.stderr)
            return False

        return result.stdout.splitlines()
        
    except subprocess.CalledProcessError as exc:
        print("Status: FAIL", exc.returncode, exc.output)

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def crtsh(domain, retries=3):
    for attempt in range(retries):
        try:
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
                        names.add(name.lstrip("*."))
            cur.close()
            conn.close()
            res = sorted(names)
            res_num = len(res) if res else 0
            print(f"{colors.GRAY}done for {domain}, results: {res_num}{colors.RESET}")
            return res

        except OperationalError as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise e


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else 0

    if domain is False:
        print(f"Usage: watch_subfinder domain")
        sys.exit()

    program = Programs.objects(scopes=domain).first()

    if program:
        print(f"[{current_time()}] Running crtsh module for '{domain}'")
        subs = crtsh(domain)
        # TODO: save in file

        # save in watchtower database
        for sub in subs:
            if re.search(r'\.' + re.escape(domain) + r'$', sub, re.IGNORECASE):
                upsert_subdomains(program.program_name, sub, 'crtsh')
    else:
        print(f"[{current_time()}] scope {domain} does not exist!")


