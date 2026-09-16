#!/usr/bin/env bash
# Watchtower quick runner
# Usage: ./watch.sh

# If running outside Docker, use the local scripts
# If running inside Docker, use the Docker command:
#   docker compose run --rm watchtower all
#   docker compose run --rm watchtower enum_single example.com
#   docker compose run --rm watchtower nuclei_all

if [ "$1" = "docker" ]; then
    shift
    case "$1" in
        up)
            docker compose up -d
            ;;
        down)
            docker compose down
            ;;
        run)
            shift
            docker compose run --rm watchtower "$@"
            ;;
        logs)
            docker compose logs -f
            ;;
        *)
            echo "Usage: $0 docker {up|down|run <args>|logs}"
            ;;
    esac
    exit 0
fi

# Local (non-Docker) execution path
shopt -s expand_aliases
source ~/.bashrc

echo "=== Running Watchtower locally ==="
watch_sync_programs
watch_enum_all
watch_ns_all
watch_http_all
watch_nuclei_all
