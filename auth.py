#!/usr/bin/env python3
"""
Simple HTTP Basic Auth for Watchtower API.

Usage in app.py:
    from auth import authenticate, require_auth

    @app.get("/api/programs/all")
    async def all_programs(user: dict = Depends(authenticate)):
        ...

Or use require_auth as a route decorator:
    @app.get("/api/programs/all")
    @require_auth
    async def all_programs():
        ...

Configuration via environment variables:
    - WATCHTOWER_API_USER: username (default: "admin")
    - WATCHTOWER_API_PASS: password (default: "changeme")
"""
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import logging

from logutil import get_logger, log_error

logger = get_logger("auth")

security = HTTPBasic()


def get_credentials():
    """Get configured credentials from environment."""
    user = os.environ.get("WATCHTOWER_API_USER", "admin")
    password = os.environ.get("WATCHTOWER_API_PASS", "changeme")
    return user, password


def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    """
    FastAPI dependency that authenticates via HTTP Basic Auth.
    Use as: async def my_endpoint(user: dict = Depends(authenticate))
    """
    expected_user, expected_pass = get_credentials()

    correct_user = secrets.compare_digest(credentials.username, expected_user)
    correct_pass = secrets.compare_digest(credentials.password, expected_pass)

    if not (correct_user and correct_pass):
        log_error(logger, f"Failed auth attempt from {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return {"username": credentials.username}


def require_auth(func):
    """
    Decorator that adds authentication dependency to a route.
    Use when you don't need access to the user object inside the route:
        @app.get("/api/programs/all")
        @require_auth
        async def all_programs():
            ...
    """
    from functools import wraps
    from inspect import signature
    from fastapi import Depends

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # The dependency will be resolved by FastAPI's Depends mechanism
        return await func(*args, **kwargs)

    # Add the auth dependency to the function's signature
    sig = signature(func)
    new_params = list(sig.parameters.values())
    new_params.insert(0, Depends(authenticate))
    wrapper.__signature__ = sig.replace(parameters=new_params)

    return wrapper
