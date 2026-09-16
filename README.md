# watchtower
welcome to my watchtower : ]

## setup the watchtower

### Option A: Docker (recommended)
1. Copy `.env.example` to `.env` and fill in your Discord webhook:
```bash
cp .env.example .env
```
2. Mount your local tool data (resolvers, wordlists, nuclei templates) under `volumes/`:
```bash
mkdir -p volumes/{resolvers,wordlists,nuclei-templates,gau-config}
# Copy your files into these directories
```
3. Build and run the full pipeline:
```bash
docker compose up -d
```

### Option B: Local (manual)
1. Install all tools listed under "tools need to be installed"
2. Configure config.py paths
3. Set alias variables in your bashrc file
4. Install Python deps: `pip install -r req.txt`
5. Install MongoDB locally or use Docker for just mongo: `docker compose up mongo`
6. Run API: `uvicorn app:app --reload` or full pipeline: `./watch.sh`

## bashrc configurations (for local Option B)
add following lines to your `~/.bashrc` file:
```bash
alias watch_sync_programs="/mnt/c/Users/ARSEN/Desktop/codes/automation/programs/watch_sync_programs.py"
alias watch_subfinder="/mnt/c/Users/ARSEN/Desktop/codes/automation/enum/watch_subfinder.py"
alias watch_crtsh="/mnt/c/Users/ARSEN/Desktop/codes/automation/enum/watch_crtsh.py"
alias watch_abuse="/mnt/c/Users/ARSEN/Desktop/codes/automation/enum/watch_abuse.py"
alias watch_wayback="/mnt/c/Users/ARSEN/Desktop/codes/automation/enum/watch_wayback.py"
alias watch_gau="/mnt/c/Users/ARSEN/Desktop/codes/automation/enum/watch_gau.py"
alias watch_enum_all="/mnt/c/Users/ARSEN/Desktop/codes/automation/enum/watch_enum_all.py"
alias watch_ns="/mnt/c/Users/ARSEN/Desktop/codes/automation/ns/watch_ns.py"
alias watch_ns_all="/mnt/c/Users/ARSEN/Desktop/codes/automation/ns/watch_ns_all.py"
alias watch_brute="/mnt/c/Users/ARSEN/Desktop/codes/automation/ns/watch_brute.py"
alias watch_httpx="/mnt/c/Users/ARSEN/Desktop/codes/automation/http/watch_httpx.py"
alias watch_http_all="/mnt/c/Users/ARSEN/Desktop/codes/automation/http/watch_http_all.py"
alias watch_nuclei_all="/mnt/c/Users/ARSEN/Desktop/codes/automation/nuclei/watch_nuclei_all.py"
```

## Docker commands
```bash
# Full pipeline (all phases)
docker compose up -d

# Run a specific phase
docker compose run --rm watchtower sync_programs
docker compose run --rm watchtower enum_all
docker compose run --rm watchtower ns_all
docker compose run --rm watchtower httpx_all
docker compose run --rm watchtower nuclei_all

# Run enum for a single domain
docker compose run --rm watchtower enum_single example.com

# Run httpx for a single domain
docker compose run --rm watchtower httpx_single example.com

# Run nuclei for a single domain
docker compose run --rm watchtower nuclei_all

# Start the API server (FastAPI with auto docs at /docs)
docker compose --profile api-server up -d

# View logs
docker compose logs -f

# Shell access inside container
docker compose run --rm watchtower bash
```

## APIs
### All endpoints support OpenAPI docs at `/docs` and `/redoc`

### Programs
- get all programs: `/api/programs/all`
- get a specific program: `/api/programs/{program_name}`

### Subdomains
- get all subdomains (with optional provider filter + limit): `/api/subdomains/all?limit=1000&provider=subfinder`
- get all subdomains of a program: `/api/subdomains/program/{p_name}`
- get all subdomains of a domain: `/api/subdomains/domain/{domain}`

### Live Subdomains
- get all live subdomains (default 12h): `/api/lives/all?hours=12`
- get all live subdomains of a program: `/api/lives/program/{p_name}?hours=12`
- get all live subdomains of a domain: `/api/lives/domain/{domain}?hours=12`
- get all fresh live subdomains (plain text): `/api/lives/fresh?hours=24`
- get all live subdomains filter by provider: `/api/lives/provider/{provider}?hours=12`
- get full detail of a specific subdomain: `/api/lives/subdomain/{live}`

### HTTP Services
- get all http services (default 12h): `/api/http/all?hours=12&limit=1000`
- get all fresh http services (plain text): `/api/http/fresh/{hours}`
- get http services filtered by provider: `/api/http/provider/{provider}?hours=12`
- get http services for a specific subdomain: `/api/http/subdomain/{subdomain}`

### System
|- database health check: `/health`

## API (FastAPI auto-generated docs)
|- Swagger UI: `http://localhost:5000/docs`
|- ReDoc: `http://localhost:5000/redoc`


## tools included in Docker image
- subfinder
- httpx
- dnsx
- shuffledns
- massdns
- nuclei
- gau (if Go install succeeds)
- chaos (needs API key)
- waybackurls
- unfurl
