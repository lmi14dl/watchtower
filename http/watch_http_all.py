#!/usr/bin/env python3
import sys, os, shlex, tempfile, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn, log_step
from runutil import StreamProc, missing_tools

logger = get_logger("watch_http_all")

# Light defaults. Heavier probing is opt-in through env vars.
HTTPX_PORTS = os.environ.get('HTTPX_PORTS', '80,443')
HTTPX_THREADS = os.environ.get('HTTPX_THREADS', '10')
HTTPX_RATE_LIMIT = os.environ.get('HTTPX_RATE_LIMIT', '10')
HTTPX_RETRIES = os.environ.get('HTTPX_RETRIES', '1')
HTTPX_TIMEOUT = os.environ.get('HTTPX_TIMEOUT', '7')
HTTPX_TECH = os.environ.get('HTTPX_TECH', '0') == '1'        # -tech-detect (CPU heavy)
HTTPX_FAVICON = os.environ.get('HTTPX_FAVICON', '0') == '1'  # -favicon (extra request per host)
# Only probe live subdomains that are new or were not probed for this many hours
STALE_HOURS = float(os.environ.get('HTTP_STALE_HOURS', '24'))


def httpx(subdomains_array, domain):
    if not subdomains_array:
        log_warn(logger, f"No subdomains to probe for {domain}")
        return True

    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_file:
        for sub in subdomains_array:
            temp_file.write(sub + "\n")
    subdomains_file = temp_file.name

    extra = ""
    if HTTPX_TECH:
        extra += " -tech-detect"
    if HTTPX_FAVICON:
        extra += " -favicon"

    command = (
        f"httpx -l {shlex.quote(subdomains_file)} -json -fhr -irh "
        f"-timeout {HTTPX_TIMEOUT} -retries {HTTPX_RETRIES} -threads {HTTPX_THREADS} "
        f"-rate-limit {HTTPX_RATE_LIMIT} -ports {HTTPX_PORTS} -silent{extra} "
        f"-H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0' "
        f"-H {shlex.quote('Referrer: https://' + domain)}"
    )

    log_info(logger, f"Running httpx for {len(subdomains_array)} subdomains in {domain}")

    count = 0
    proc = StreamProc(command)
    try:
        for line in proc:
            try:
                json_obj = json.loads(line)
            except json.JSONDecodeError:
                log_error(logger, f"Failed to parse httpx JSON line: {line[:200]}")
                continue
            upsert_http({
                "subdomain": json_obj.get('input', json_obj.get('host', '')),
                "scope": domain,
                "ips": json_obj.get('a', []),
                "tech": json_obj.get('tech', []),
                "title": json_obj.get('title', ''),
                "status_code": json_obj.get('status_code'),
                "headers": json_obj.get('header', {}),
                "url": json_obj.get('url'),
                "final_url": json_obj.get('final_url', ''),
                "favicon": json_obj.get('favicon', '')
            })
            count += 1
    finally:
        os.unlink(subdomains_file)

    if proc.ok:
        mark_lives_probed(domain, subdomains_array)
    else:
        log_error(logger, f"httpx did not finish cleanly for {domain} "
                          f"(rc={proc.returncode}, timeout={proc.timed_out}); will retry next run")

    log_success(logger, f"httpx: {count} HTTP services found for {domain}")
    return True


def main():
    if missing_tools(['httpx']):
        log_error(logger, "Required tool not found in PATH: httpx")
        sys.exit(1)

    if len(sys.argv) > 1:
        # Single domain mode: probe every live subdomain of that scope
        domain = sys.argv[1]
        subs = get_lives_to_probe(domain, 0)
        if subs:
            log_info(logger, f"Running httpx module for '{domain}'")
            httpx(subs, domain)
        else:
            log_warn(logger, f"No live subdomains found for {domain}")
        return

    log_step(logger, "Starting HTTP probing for all programs")
    programs = Programs.objects().all()
    total_programs = len(programs)
    log_info(logger, f"Found {total_programs} programs to probe (stale after {STALE_HOURS}h)")

    for i, program in enumerate(programs, 1):
        for scope in program.scopes:
            subs = get_lives_to_probe(scope, STALE_HOURS)
            if subs:
                log_info(logger, f"[{i}/{total_programs}] [{program.program_name}] Probing {scope} ({len(subs)} hosts)")
                httpx(subs, scope)
            else:
                log_info(logger, f"[{program.program_name}] nothing to probe for {scope}")

    log_success(logger, "HTTP probing pipeline complete")


if __name__ == "__main__":
    main()
