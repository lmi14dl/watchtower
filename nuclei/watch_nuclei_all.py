#!/usr/bin/env python3
import sys, os, shlex, tempfile
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from database.db import *
from logutil import get_logger, log_info, log_error, log_success, log_warn, log_step
from notifier import notify, get_enabled_services
from runutil import StreamProc, missing_tools

logger = get_logger("watch_nuclei_all")

# Only scan URLs never scanned, or scanned more than N days ago (never the whole history each run)
RESCAN_DAYS = float(os.environ.get('NUCLEI_RESCAN_DAYS', '7'))
# Safety caps per run
MAX_URLS_PER_RUN = int(os.environ.get('NUCLEI_MAX_URLS_PER_RUN', '2000'))
CHUNK_SIZE = int(os.environ.get('NUCLEI_CHUNK_SIZE', '200'))
NUCLEI_TIMEOUT = int(os.environ.get('NUCLEI_TIMEOUT', '14400'))
# Optional template path(s), comma separated. Default: nuclei's own templates.
NUCLEI_TEMPLATES = os.environ.get('NUCLEI_TEMPLATES', '')


def send_notification(message):
    """Send notification to all configured services (the notifier splits long messages)."""
    services = get_enabled_services()
    if not services:
        log_warn(logger, "No notification services configured")
        return
    notify(message)


def create_tempfile(data):
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_file:
        temp_file.write(data)
        return temp_file.name


def nuclei(urls):
    """Scan a batch of URLs. Returns the list of findings, or None if the scan failed."""
    urls_file = create_tempfile("\n".join(urls) + "\n")
    nuclei_config = config().get('WATCH_DIR') + '/nuclei/public-config.yaml'

    command = f"nuclei -l {shlex.quote(urls_file)} -silent"
    if os.path.isfile(nuclei_config) and os.path.getsize(nuclei_config) > 0:
        command += f" -config {shlex.quote(nuclei_config)}"
    if NUCLEI_TEMPLATES:
        command += f" -t {shlex.quote(NUCLEI_TEMPLATES)}"

    log_info(logger, f"Executing: {command}")
    findings = []
    proc = StreamProc(command, timeout=NUCLEI_TIMEOUT)
    try:
        for line in proc:
            findings.append(line)
    finally:
        os.unlink(urls_file)

    if not proc.ok:
        log_error(logger, f"Nuclei did not finish cleanly (rc={proc.returncode}, timeout={proc.timed_out})")
        return None
    return findings


if __name__ == "__main__":
    log_step(logger, "Starting Nuclei vulnerability scan")

    if missing_tools(['nuclei']):
        log_error(logger, "Required tool not found in PATH: nuclei")
        sys.exit(1)

    urls = get_urls_for_nuclei(RESCAN_DAYS, MAX_URLS_PER_RUN)
    if not urls:
        log_info(logger, "No new HTTP services to scan with nuclei")
        sys.exit(0)

    log_info(logger, f"Running Nuclei against {len(urls)} HTTP services (max {MAX_URLS_PER_RUN} per run)")
    total_findings = 0
    for i in range(0, len(urls), CHUNK_SIZE):
        chunk = urls[i:i + CHUNK_SIZE]
        findings = nuclei(chunk)
        if findings is None:
            break  # chunk not marked, it will be retried next run
        mark_urls_nuclei(chunk)
        if findings:
            total_findings += len(findings)
            send_notification("\n".join(findings))

    log_success(logger, f"Nuclei scan complete. {total_findings} findings sent to notifications.")
