#!/usr/bin/env python3
"""
Single-domain HTTP probing:  watch_httpx.py <domain>

Uses the same batched httpx run as watch_http_all.py (one httpx process for the
whole domain, instead of one process per subdomain).
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_httpx <domain>")
        sys.exit(1)
    from watch_http_all import main
    main()
