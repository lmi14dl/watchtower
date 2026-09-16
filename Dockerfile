FROM python:3.11-slim

# Install system dependencies for bug bounty tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils \
    curl \
    git \
    jq \
    nmap \
    masscan \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Go (for subfinder, http-prober, etc.)
ENV GOLANG_VERSION=1.22.5
RUN curl -sSL https://go.dev/dl/go${GOLANG_VERSION}.linux-amd64.tar.gz -o /tmp/go.tgz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tgz

ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH=/root/go
ENV PATH="${GOPATH}/bin:${PATH}"

# Install core bug bounty tools via Go
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
RUN go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
RUN go install -v github.com/projectdiscovery/shuffledns/cmd/shuffledns@latest
RUN go install -v github.com/timb-machine-community/massdns/cmd/massdns@latest 2>/dev/null || \
    go install -v github.com/1hacker/massdns@latest 2>/dev/null || \
    echo "massdns install skipped, will use apt fallback"
RUN go install -v github.com/tomnomnom/anample/@latest 2>/dev/null || echo "gau install attempted"
RUN go install -v github.com/tomnomnom/waybackurls@latest 2>/dev/null || go install -v github.com/tomnomnom/waybackurls/v2@latest 2>/dev/null || echo "waybackurls install attempted"
RUN go install -v github.com/tomnomnom/unfurl@latest 2>/dev/null || echo "unfurl install attempted"
RUN go install -v github.com/projectdiscovery/chaos-client/cmd/chaos@latest 2>/dev/null || echo "chaos install skipped (needs API key)"

# Copy Python dependencies and install
COPY req.txt /app/req.txt
RUN pip install --no-cache-dir -r /app/req.txt

# Create app directory
WORKDIR /app

# Copy all watchtower files
COPY . /app/

# Create config directory for nuclei templates
RUN nuclei -config /app/nuclei/public-config.yaml -update-templates 2>/dev/null || true

# Copy nuclei templates list
RUN if [ -f /app/nuclei/templates.txt ]; then \
      nuclei -update-templates 2>/dev/null || true; \
    fi

# Copy the nuclei private xss config
RUN if [ -f /app/nuclei/private_templates/xss.yaml ]; then \
      cp /app/nuclei/private_templates/xss.yaml /root/.config/nuclei/ 2>/dev/null || true; \
    fi

# Create resolvers and wordlist directories (user will mount their own)
RUN mkdir -p /app/config

# Copy entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Default: run the full pipeline
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["all"]
