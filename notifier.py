#!/usr/bin/env python3
"""
Notification system for Watchtower.
Supports Discord webhooks and Telegram bots.

Configuration via environment variables:
    # Discord
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

    # Telegram
    TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-xyz
    TELEGRAM_CHAT_ID=-1001234567890

Usage:
    from notifier import notify, send_discord, send_telegram

    # Auto-detect enabled services
    notify("New subdomain found: test.example.com")

    # Force specific service
    send_discord("message")
    send_telegram("message")
"""
import os
import requests
from logutil import get_logger, log_info, log_error, log_success, log_warn

logger = get_logger("notifier")


def is_discord_enabled():
    """Check if Discord webhook URL is configured."""
    return bool(os.environ.get("DISCORD_WEBHOOK_URL"))


def is_telegram_enabled():
    """Check if Telegram bot token and chat ID are configured."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    return bool(token and chat_id)


def get_enabled_services():
    """Return list of enabled notification services."""
    services = []
    if is_discord_enabled():
        services.append("discord")
    if is_telegram_enabled():
        services.append("telegram")
    return services


def send_discord(message):
    """Send a message to Discord via webhook."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log_warn(logger, "Discord webhook URL not configured, skipping")
        return False

    try:
        response = requests.post(
            webhook_url,
            json={"content": message},
            timeout=10,
        )
        if response.status_code in (204, 200):
            log_success(logger, "Discord notification sent")
            return True
        else:
            log_error(logger, f"Discord webhook failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        log_error(logger, f"Discord notification error: {e}")
        return False


def send_telegram(message):
    """Send a message to a Telegram chat via bot API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log_warn(logger, "Telegram credentials not configured, skipping")
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(
            url,
            data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        if response.status_code == 200:
            log_success(logger, "Telegram notification sent")
            return True
        else:
            log_error(logger, f"Telegram API failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        log_error(logger, f"Telegram notification error: {e}")
        return False


def notify(message, services=None):
    """
    Send a notification to all enabled services (or specific ones if specified).

    Args:
        message: The message text to send
        services: Optional list of specific services to notify
                   (e.g. ["discord"] or ["telegram"]). If None, sends to all enabled.
    Returns:
        dict mapping service name to success/failure boolean
    """
    if services is None:
        services = get_enabled_services()

    if not services:
        log_warn(logger, "No notification services configured")
        return {}

    results = {}
    for service in services:
        if service == "discord":
            results["discord"] = send_discord(message)
        elif service == "telegram":
            results["telegram"] = send_telegram(message)
        else:
            log_error(logger, f"Unknown notification service: {service}")
            results[service] = False

    return results


def notify_discord_only(message):
    """Send to Discord only (even if others are enabled)."""
    return {"discord": send_discord(message)}


def notify_telegram_only(message):
    """Send to Telegram only (even if others are enabled)."""
    return {"telegram": send_telegram(message)}


def test_notifications():
    """Test both notification services."""
    log_step_result = []

    if is_discord_enabled():
        result = send_discord("Watchtower notification test — Discord is working!")
        log_step_result.append(f"Discord: {'OK' if result else 'FAILED'}")
    else:
        log_step_result.append("Discord: NOT CONFIGURED")

    if is_telegram_enabled():
        result = send_telegram("Watchtower notification test — Telegram is working!")
        log_step_result.append(f"Telegram: {'OK' if result else 'FAILED'}")
    else:
        log_step_result.append("Telegram: NOT CONFIGURED")

    return "\n".join(log_step_result)
