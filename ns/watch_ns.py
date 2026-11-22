#!/usr/bin/env python3
import sys, os, shlex, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn
from runutil import StreamProc, missing_tools

logger = get_logger("watch_ns")

# Only (re)resolve subdomains that are new or older than this many hours
STALE_HOURS = float(os.environ.get('RESOLVE_STALE_HOURS', '24'))
DNSX_THREADS = os.environ.get('DNSX_THREADS', '20')
DNSX_RATE_LIMIT = os.environ.get('DNSX_RATE_LIMIT', '50')


def dnsx(subdomains_array, domain):
    """Resolve subdomains with dnsx only (no shuffledns/massdns double resolving)."""
    if not subdomains_array:
        return True

    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_file:
        for sub in subdomains_array:
            temp_file.write(sub + "\n")
    subdomains_file = temp_file.name

    resolvers = config()['RESOLVERS_PATH']
    resolvers_arg = f"-r {shlex.quote(resolvers)}" if resolvers and os.path.isfile(resolvers) else ""
    command = (
        f"dnsx -l {shlex.quote(subdomains_file)} -silent -a -resp -json "
        f"-t {DNSX_THREADS} -rl {DNSX_RATE_LIMIT} {resolvers_arg}"
    )
    log_info(logger, f"Resolving {len(subdomains_array)} subdomains of {domain}")
    log_info(logger, f"Executing: {command}")

    count = 0
    proc = StreamProc(command)
    try:
        for line in proc:
            try:
                res = json.loads(line)
                upsert_lives({
                    'subdomain': res['host'],
                    'domain': domain,
                    'ips': res.get('a', []),
                    'cdn': None
                })
                count += 1
            except (json.JSONDecodeError, KeyError) as e:
                log_error(logger, f"Failed to parse DNS result: {e}")
    finally:
        os.unlink(subdomains_file)

    if proc.ok:
        mark_subdomains_resolved(domain, subdomains_array)
    else:
        log_error(logger, f"dnsx did not finish cleanly for {domain} "
                          f"(rc={proc.returncode}, timeout={proc.timed_out}); will retry next run")

    log_success(logger, f"DNS resolution: {count} live hosts for {domain}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_ns <domain>")
        sys.exit(1)

    if missing_tools(['dnsx']):
        log_error(logger, "Required tool not found in PATH: dnsx")
        sys.exit(1)

    domain = sys.argv[1]
    subs = get_subdomains_to_resolve(domain, 0)  # single mode: resolve everything

    if subs:
        log_info(logger, f"Running DnsX module for '{domain}'")
        dnsx(subs, domain)
    else:
        log_warn(logger, f"No subdomains found for scope {domain}")
