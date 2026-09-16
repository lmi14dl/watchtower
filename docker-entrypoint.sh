#!/usr/bin/env bash
set -e

# Docker entrypoint for Watchtower
# Usage:
#   docker compose up -d  (runs full pipeline via CMD: ["all"])
#   docker compose run --rm watchtower sync_programs
#   docker compose run --rm watchtower enum_all
#   docker compose run --rm watchtower ns_all
#   docker compose run --rm watchtower httpx_all
#   docker compose run --rm watchtower nuclei_all
#   docker compose run --rm watchtower enum_single example.com
#   docker compose run --rm watchtower httpx_single example.com
#   docker compose run --rm watchtower scheduler --runs 2 --docker
#   docker compose run --rm watchtower api
#   docker compose run --rm watchtower bash

export PYTHONPATH=/app:${PYTHONPATH}

case "$1" in
    scheduler)
        # Pass all remaining args to scheduler.py
        shift
        exec python3 /app/scheduler.py "$@"
        ;;
    all)
        echo "=== Running full Watchtower pipeline ==="
        echo "[$(date -Iseconds)] Phase 1: Sync programs"
        python3 /app/programs/watch_sync_programs.py

        echo "[$(date -Iseconds)] Phase 2: Enumerate subdomains (all programs)"
        python3 /app/enum/watch_enum_all.py

        echo "[$(date -Iseconds)] Phase 3: DNS resolution (dnsx + shuffledns)"
        python3 /app/ns/watch_ns_all.py

        echo "[$(date -Iseconds)] Phase 4: HTTP probing (httpx)"
        python3 /app/http/watch_http_all.py

        echo "[$(date -Iseconds)] Phase 5: Nuclei scan"
        python3 /app/nuclei/watch_nuclei_all.py

        echo "[$(date -Iseconds)] Pipeline complete."
        ;;
    sync_programs)
        python3 /app/programs/watch_sync_programs.py
        ;;
    enum_all)
        python3 /app/enum/watch_enum_all.py
        ;;
    enum_single)
        if [ -z "$2" ]; then
            echo "Usage: $0 enum_single <domain>"
            exit 1
        fi
        python3 /app/enum/watch_subfinder.py "$2"
        python3 /app/enum/watch_crtsh.py "$2"
        python3 /app/enum/watch_abuse.py "$2"
        python3 /app/enum/watch_wayback.py "$2"
        python3 /app/enum/watch_gau.py "$2"
        ;;
    ns_all)
        python3 /app/ns/watch_ns_all.py
        ;;
    ns_single)
        if [ -z "$2" ]; then
            echo "Usage: $0 ns_single <domain>"
            exit 1
        fi
        python3 /app/ns/watch_ns.py "$2"
        ;;
    brute_single)
        if [ -z "$2" ]; then
            echo "Usage: $0 brute_single <domain>"
            exit 1
        fi
        python3 /app/ns/watch_brute.py "$2"
        ;;
    httpx_all)
        python3 /app/http/watch_http_all.py
        ;;
    httpx_single)
        if [ -z "$2" ]; then
            echo "Usage: $0 httpx_single <domain>"
            exit 1
        fi
        python3 /app/http/watch_httpx.py "$2"
        ;;
    nuclei_all)
        python3 /app/nuclei/watch_nuclei_all.py
        ;;
    api)
        exec uvicorn app:app --host 0.0.0.0 --port 5000
        ;;
    bash)
        exec /bin/bash
        ;;
    *)
        echo "Usage: $0 {all|sync_programs|enum_all|enum_single <domain>|ns_all|ns_single <domain>|brute_single <domain>|httpx_all|httpx_single <domain>|nuclei_all|scheduler <args>|api|bash}"
        exit 1
        ;;
esac
