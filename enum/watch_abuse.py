#!/usr/bin/env python3
import sys, os, requests, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("watch_abuse")

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def abusewhois(domain):
    session = os.environ.get('ABUSE_IPDB_SESSION', 'YOUR-SESSION')
    url = f"https://www.abuseipdb.com/whois/{domain}"
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = {"abuseipdb_session": session}

    log_info(logger, f"Querying AbuseIPDB whois for {domain}")
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        log_error(logger, f"AbuseIPDB request failed for {domain}: {e}")
        return []

    items = re.findall(r"<li>([^<]+)</li>", response.text)
    subdomains = set()
    for item in items:
        item = item.strip()
        if re.fullmatch(r"[A-Za-z0-9_-]+", item):
            subdomains.add(f"{item}.{domain}")
        elif item.endswith(f".{domain}"):
            subdomains.add(item)

    result = sorted(subdomains)
    log_success(logger, f"AbuseIPDB: {len(result)} results for {domain}")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_abuse <domain>")
        sys.exit(1)

    domain = sys.argv[1]
    program = Programs.objects(scopes=domain).first()

    if program:
        log_info(logger, f"Running abuse module for '{domain}' (program: {program.program_name})")
        subs = abusewhois(domain)
        if subs:
            for sub in subs:
                upsert_subdomains(program.program_name, sub, 'abuse')
            log_success(logger, f"Upserted {len(subs)} abuse subdomains for {domain}")
        else:
            log_warn(logger, f"No subdomains found via AbuseIPDB for {domain}")
    else:
        log_error(logger, f"Scope {domain} does not exist in any program!")
