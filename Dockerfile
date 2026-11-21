# ---- Stage 1: build the recon tools (Go) ----
FROM golang:bookworm AS tools
ENV CGO_ENABLED=0 GOBIN=/out
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest \
 && go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest \
 && go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest \
 && go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest \
 && go install -v github.com/lc/gau/v2/cmd/gau@latest \
 && go install -v github.com/tomnomnom/waybackurls@latest \
 && go install -v github.com/tomnomnom/unfurl@latest

# ---- Stage 2: runtime ----
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tools /out/ /usr/local/bin/

# Python dependencies
COPY req.txt /app/req.txt
RUN pip install --no-cache-dir -r /app/req.txt

WORKDIR /app
COPY . /app/

# Download nuclei templates once at build time (non-fatal)
RUN nuclei -update-templates 2>/dev/null || true

# Resolvers / wordlists are mounted by the user
RUN mkdir -p /app/config

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["all"]
