from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import sys, os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from database.db import (
    Programs, Subdomains, LiveSubdomains, HTTP,
    current_time, get_domain_name
)

app = FastAPI(
    title="Watchtower API",
    description="Bug bounty watchtower API for tracking subdomains, live hosts, and HTTP services across bug bounty programs.",
    version="1.0.0"
)


@app.get("/")
async def root():
    return {"message": "Welcome to Watchtower API", "docs": "/docs", "redoc": "/redoc"}


# --- Programs ---

@app.get("/api/programs/all")
async def all_programs():
    programs = Programs.objects.all()
    response = {}
    for program in programs:
        response[program.program_name] = {
            "scopes": program.scopes,
            "ooscopes": program.ooscopes,
            "config": program.config,
            "created_date": program.created_date.isoformat() if program.created_date else None
        }
    return response


@app.get("/api/programs/{program_name}")
async def get_program(program_name: str = Path(..., description="Program name to look up")):
    program = Programs.objects(program_name=program_name).first()
    if not program:
        raise HTTPException(status_code=404, detail=f"Program '{program_name}' not found")
    return {
        "program_name": program.program_name,
        "scopes": program.scopes,
        "ooscopes": program.ooscopes,
        "config": program.config,
        "created_date": program.created_date.isoformat() if program.created_date else None
    }


# --- Subdomains ---

@app.get("/api/subdomains/all")
async def all_subdomains(
    limit: int = Query(default=1000, le=10000),
    provider: Optional[str] = Query(default=None, description="Filter by provider (e.g. subfinder, crtsh)")
):
    query = Subdomains.objects()
    if provider:
        query = Subdomains.objects(providers=provider)
    subs = query.limit(limit).all()
    response = []
    for sub in subs:
        response.append({
            "program_name": sub.program_name,
            "subdomain": sub.subdomain,
            "providers": sub.providers,
            "created_date": sub.created_date.isoformat() if sub.created_date else None,
            "last_update": sub.last_update.isoformat() if sub.last_update else None
        })
    return response


@app.get("/api/subdomains/domain/{domain}")
async def subdomains_of_domain(domain: str = Path(...)):
    subs = Subdomains.objects(scope=domain).all()
    if not subs:
        return {"message": f"No subdomains found for {domain}"}
    return [
        {
            "program_name": sub.program_name,
            "subdomain": sub.subdomain,
            "providers": sub.providers,
            "created_date": sub.created_date.isoformat() if sub.created_date else None,
            "last_update": sub.last_update.isoformat() if sub.last_update else None
        }
        for sub in subs
    ]


@app.get("/api/subdomains/program/{p_name}")
async def subdomains_of_program(p_name: str = Path(...)):
    subs = Subdomains.objects(program_name=p_name).all()
    if not subs:
        return {"message": f"No subdomains found for program '{p_name}'"}, 404
    return [
        {
            "program_name": sub.program_name,
            "subdomain": sub.subdomain,
            "providers": sub.providers,
            "created_date": sub.created_date.isoformat() if sub.created_date else None,
            "last_update": sub.last_update.isoformat() if sub.last_update else None
        }
        for sub in subs
    ]


# --- Live Subdomains ---

@app.get("/api/lives/all")
async def all_lives(
    hours: int = Query(default=12, description="Look back this many hours")
):
    ago = datetime.now() - timedelta(hours=hours)
    live_subs = LiveSubdomains.objects(last_update__gte=ago).all()
    response = []
    for live_sub in live_subs:
        response.append({
            "program_name": live_sub.program_name,
            "subdomain": live_sub.subdomain,
            "scope": live_sub.scope,
            "ips": live_sub.ips,
            "cdn": live_sub.cdn,
            "created_date": live_sub.created_date.isoformat() if live_sub.created_date else None,
            "last_update": live_sub.last_update.isoformat() if live_sub.last_update else None
        })
    return response


@app.get("/api/lives/program/{p_name}")
async def lives_of_program(
    p_name: str = Path(...),
    hours: int = Query(default=12)
):
    ago = datetime.now() - timedelta(hours=hours)
    live_subs = LiveSubdomains.objects(program_name=p_name, last_update__gte=ago).all()
    if not live_subs:
        return {"message": f"No live subdomains found for program '{p_name}'"}, 404
    return [
        {
            "subdomain": live_sub.subdomain,
            "scope": live_sub.scope,
            "ips": live_sub.ips,
            "cdn": live_sub.cdn,
            "created_date": live_sub.created_date.isoformat() if live_sub.created_date else None,
            "last_update": live_sub.last_update.isoformat() if live_sub.last_update else None
        }
        for live_sub in live_subs
    ]


@app.get("/api/lives/domain/{domain}")
async def lives_of_domain(
    domain: str = Path(...),
    hours: int = Query(default=12)
):
    ago = datetime.now() - timedelta(hours=hours)
    live_subs = LiveSubdomains.objects(scope=domain, last_update__gte=ago).all()
    if not live_subs:
        return {"message": f"No live subdomains found for domain '{domain}'"}, 404
    return [
        {
            "program_name": live_sub.program_name,
            "subdomain": live_sub.subdomain,
            "ips": live_sub.ips,
            "cdn": live_sub.cdn,
            "created_date": live_sub.created_date.isoformat() if live_sub.created_date else None,
            "last_update": live_sub.last_update.isoformat() if live_sub.last_update else None
        }
        for live_sub in live_subs
    ]


@app.get("/api/lives/fresh")
async def fresh_lives(
    hours: int = Query(default=24, description="Hours to look back for fresh subdomains")
):
    ago = datetime.now() - timedelta(hours=hours)
    fresh = LiveSubdomains.objects(created_date__gte=ago).all()
    res_array = [f.subdomain for f in fresh]
    return PlainTextResponse("\n".join(res_array))


@app.get("/api/lives/provider/{provider}")
async def lives_of_provider(
    provider: str = Path(...),
    hours: int = Query(default=12)
):
    ago = datetime.now() - timedelta(hours=hours)
    subs_obj = Subdomains.objects(providers=provider).all()
    if not subs_obj:
        return {"message": f"The '{provider}' provider was not found"}
    response = ""
    for sub_obj in subs_obj:
        lives = LiveSubdomains.objects(subdomain=sub_obj.subdomain, last_update__gte=ago).first()
        if lives:
            response += f"{lives.subdomain}\n"
    return PlainTextResponse(response)


@app.get("/api/lives/subdomain/{live}")
async def live_sub_detail(live: str = Path(...)):
    live_obj = LiveSubdomains.objects(subdomain=live).first()
    sub_obj = Subdomains.objects(subdomain=live).first()
    if live_obj and sub_obj:
        return {
            "program_name": live_obj.program_name,
            "subdomain": live_obj.subdomain,
            "scope": live_obj.scope,
            "ips": live_obj.ips or [],
            "cdn": live_obj.cdn,
            "created_date": live_obj.created_date.isoformat() if live_obj.created_date else None,
            "last_update": live_obj.last_update.isoformat() if live_obj.last_update else None,
            "providers": sub_obj.providers or []
        }
    else:
        return {"message": f"Subdomain '{live}' not found"}


# --- HTTP Services ---

@app.get("/api/http/all")
async def all_http(
    hours: int = Query(default=12),
    limit: int = Query(default=1000, le=10000)
):
    ago = datetime.now() - timedelta(hours=hours)
    http_records = HTTP.objects(last_update__gte=ago).limit(limit).all()
    response = []
    for h in http_records:
        response.append({
            "program_name": h.program_name,
            "subdomain": h.subdomain,
            "scope": h.scope,
            "ips": h.ips,
            "tech": h.tech,
            "title": h.title,
            "status_code": h.status_code,
            "headers": h.headers,
            "url": h.url,
            "final_url": h.final_url,
            "favicon": h.favicon,
            "created_date": h.created_date.isoformat() if h.created_date else None,
            "last_update": h.last_update.isoformat() if h.last_update else None
        })
    return response


@app.get("/api/http/fresh/{hours}")
async def http_fresh(hours: int = Path(..., description="Hours to look back")):
    ago = datetime.now() - timedelta(hours=hours)
    fresh = HTTP.objects(created_date__gte=ago).all()
    res_array = [h.url for h in fresh if h.url]
    return PlainTextResponse("\n".join(res_array))


@app.get("/api/http/provider/{provider}")
async def http_of_provider(
    provider: str = Path(...),
    hours: int = Query(default=12)
):
    ago = datetime.now() - timedelta(hours=hours)
    subs_obj = Subdomains.objects(providers=provider).all()
    if not subs_obj:
        return {"message": f"The '{provider}' provider was not found"}
    response = ""
    for sub_obj in subs_obj:
        http_records = HTTP.objects(subdomain=sub_obj.subdomain, last_update__gte=ago).all()
        for h in http_records:
            response += f"{h.url}\n"
    return PlainTextResponse(response)


@app.get("/api/http/subdomain/{subdomain}")
async def http_of_subdomain(subdomain: str = Path(...)):
    http_records = HTTP.objects(subdomain=subdomain).all()
    if not http_records:
        return {"message": f"No HTTP services found for subdomain '{subdomain}'"}, 404
    return [
        {
            "program_name": h.program_name,
            "subdomain": h.subdomain,
            "scope": h.scope,
            "tech": h.tech,
            "title": h.title,
            "status_code": h.status_code,
            "url": h.url,
            "final_url": h.final_url,
            "favicon": h.favicon,
            "created_date": h.created_date.isoformat() if h.created_date else None,
            "last_update": h.last_update.isoformat() if h.last_update else None
        }
        for h in http_records
    ]


# --- Health check ---

@app.get("/health")
async def health_check():
    from mongoengine import connection
    try:
        conn = connection.get_connection()
        conn.admin.command("ping")
        return {"status": "ok", "database": "mongodb", "time": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "error", "database": "mongodb", "error": str(e)}, 503
