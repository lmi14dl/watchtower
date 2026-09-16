#!/usr/bin/env python3
import sys, os, requests, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def abusewhois(domain, session="YOUR-SESSION"):
    url = f"https://www.abuseipdb.com/whois/{domain}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    cookies = {
        "abuseipdb_session": session
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
            timeout=30
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return []

    # Extract text inside <li>...</li>
    items = re.findall(r"<li>([^<]+)</li>", response.text)

    subdomains = set()

    for item in items:
        item = item.strip()

        # Single label -> append domain
        if re.fullmatch(r"[A-Za-z0-9_-]+", item):
            subdomains.add(f"{item}.{domain}")

        # Already a subdomain of the target domain
        elif item.endswith(f".{domain}"):
            subdomains.add(item)

    return sorted(subdomains)


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else 0

    if domain is False:
        print(f"Usage: watch_abuse domain")
        sys.exit()

    program = Programs.objects(scopes=domain).first()

    if program:
        print(f"[{current_time()}] Running abuse module for '{domain}'")
        subs = abusewhois(domain)
        # TODO: save in file

        # save in watchtower database
        for sub in subs:
            upsert_subdomains(program.program_name, sub, 'abuse')
    else:
        print(f"[{current_time()}] scope {domain} does not exist!")


