import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from mongoengine import Document, StringField, DateTimeField, ListField, DictField, connect
from datetime import datetime
from config import config
import tldextract, requests
from logutil import get_logger, log_info, log_error, log_success
from notifier import notify, get_enabled_services

# Module logger
logger = get_logger("database")

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_domain_name(url):
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"

def notify_all(message):
    """Send notification to all configured services."""
    services = get_enabled_services()
    if not services:
        log_warn(logger, "No notification services configured, skipping notification")
        return
    notify(message)


_MONGO_HOST = os.environ.get('MONGO_HOST', '127.0.0.1')
_MONGO_PORT = os.environ.get('MONGO_PORT', '27017')
log_info(logger, f"Connecting to MongoDB at {_MONGO_HOST}:{_MONGO_PORT}")
connect('watchtower', host=f'mongodb://{_MONGO_HOST}:{_MONGO_PORT}/watchtower')
log_success(logger, "MongoDB connection established")

# Log which notification services are active
services = get_enabled_services()
if services:
    log_info(logger, f"Notifications enabled for: {', '.join(services)}")
else:
    log_warn(logger, "No notification services configured (set DISCORD_WEBHOOK_URL and/or TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)")

class Programs(Document):
    program_name = StringField(required=True)
    created_date = DateTimeField(default=datetime.now)
    config = DictField()
    scopes = ListField(StringField(), default=[])
    ooscopes = ListField(StringField(), default=[])

    meta = {
        'indexes': [
            {'fields': ['program_name'], 'unique': True}
        ]
    }

class Subdomains(Document):
    program_name = StringField(required=True)
    subdomain = StringField(required=True)
    scope = StringField(required=True)
    providers = ListField(StringField())
    created_date = DateTimeField(default=datetime.now)
    last_update = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain'], 'unique': True}
        ]
    }

class LiveSubdomains(Document):
    program_name = StringField(required=True)
    subdomain = StringField(required=True)
    scope = StringField(required=True)
    cdn = StringField()
    ips = ListField(StringField())
    created_date = DateTimeField(default=datetime.now)
    last_update = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain'], 'unique': True}
        ]
    }

class HTTP(Document):
    program_name = StringField(required=True)
    subdomain = StringField(required=True)
    scope = StringField(required=True)
    ips = ListField(StringField())
    tech = StringField()
    title = StringField()
    status_code = StringField()
    headers = DictField()
    url = StringField()
    final_url = StringField()
    favicon = StringField()
    created_date = DateTimeField(default=datetime.now)
    last_update = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain'], 'unique': True}
        ]
    }


def upsert_lives(obj):
    program = Programs.objects(scopes=obj['domain']).first()
    if not program:
        log_error(logger, f"No program found for scope {obj['domain']}")
        return

    existing = LiveSubdomains.objects(subdomain=obj['subdomain']).first()

    if existing:
        obj_ips = list(obj.get('ips', []))
        obj_ips.sort()
        existing_ips = list(existing.ips)
        existing_ips.sort()
        if obj_ips != existing_ips:
            log_info(logger, f"Updated live subdomain: {obj['subdomain']} IPs changed")
            existing.ips = obj_ips
        existing.last_update = datetime.now()
        existing.save()

    else:
        new_live = LiveSubdomains(
            program_name=program.program_name,
            subdomain=obj['subdomain'],
            scope=obj['domain'],
            ips=obj.get('ips', []),
            created_date=datetime.now(),
            last_update=datetime.now(),
            cdn=None
        )
        
        new_live.save()
        notify_all(f"```{obj['subdomain']} (fresh live) has been added to '{program.program_name}' program```")
        log_success(logger, f"Inserted new live subdomain: {obj['subdomain']} for program: {program.program_name}")
        
def upsert_http(obj):
    program = Programs.objects(scopes=obj['scope']).first()
    if not program:
        log_error(logger, f"No program found for scope {obj['scope']}")
        return

    existing = HTTP.objects(subdomain=obj['subdomain']).first()

    if existing:
        title_changed = existing.title != obj.get('title')
        status_changed = existing.status_code != str(obj.get('status_code'))
        favicon_changed = existing.favicon != obj.get('favicon')

        if title_changed:
            notify_all(f"```{obj['subdomain']} Title has been changed from '{existing.title}' to '{obj.get('title')}'```")
            log_info(logger, f"Title changed for subdomain: {obj['subdomain']}")
            existing.title = obj.get('title')
           
        if status_changed:
            notify_all(f"```{obj['subdomain']} Status Code has been changed from '{existing.status_code}' to '{str(obj.get('status_code'))}'```")
            log_info(logger, f"Status Code changed for subdomain: {obj['subdomain']}")
            existing.status_code = str(obj.get('status_code'))

        if favicon_changed:
            notify_all(f"```{obj['subdomain']} favicon has been changed from '{existing.favicon}' to '{obj.get('favicon')}'```")
            log_info(logger, f"Favicon changed for subdomain: {obj['subdomain']}")
            existing.favicon = obj.get('favicon')
           

        existing.ips = obj.get('ips')
        existing.tech = str(obj.get('tech'))
        existing.headers = obj.get('headers')
        existing.url = obj.get('url')
        existing.final_url = obj.get('final_url')
        
        existing.last_update = datetime.now()
        existing.save()

    else:
        new_http_subdomain = HTTP(
            program_name = program.program_name,
            subdomain = obj.get('subdomain'),
            scope = obj.get('scope'),
            ips = obj.get('ips'),
            tech = str(obj.get('tech')),
            title = obj.get('title'),
            status_code = str(obj.get('status_code')),
            headers = obj.get('headers'),
            url = obj.get('url'),
            final_url = obj.get('final_url'),
            favicon = obj.get('favicon'),
            created_date = datetime.now(),
            last_update = datetime.now()
        )
        
        new_http_subdomain.save()
        notify_all(f"```{obj['subdomain']} (fresh http) has been added to '{program.program_name}' program```")
        log_success(logger, f"Inserted new http service: {obj['subdomain']} for program: {program.program_name}")
        

# Upsert (Update and Insert) Programs
def upsert_program(program_name, scopes, ooscopes, config):
    program = Programs.objects(program_name=program_name).first()
    if program:
        program.config = config
        program.scopes = scopes
        program.ooscopes = ooscopes
        program.save()
        log_info(logger, f"Updated program: {program.program_name}")
    else:
        new_program = Programs(
            program_name=program_name,
            created_date=datetime.now,
            config=config,
            scopes=scopes,
            ooscopes=ooscopes
        )
        new_program.save()
        log_success(logger, f"Inserted new program: {new_program.program_name}")

# Upsert subdomains (check if subdomain exists, if not insert, if yes update providers)
def upsert_subdomains(program_name, subdomain_name, provider):
    program = Programs.objects(program_name=program_name).first()
    if not program:
        log_error(logger, f"Program '{program_name}' not found for subdomain: {subdomain_name}")
        return False

    if get_domain_name(subdomain_name) not in program.scopes or subdomain_name in program.ooscopes:
        log_info(logger, f"Subdomain not in scope: {subdomain_name}")
        return True

    existing = Subdomains.objects(program_name=program_name, subdomain=subdomain_name).first()
    if existing:
        if provider not in existing.providers:
            existing.providers.append(provider)
            existing.last_update = datetime.now()
            existing.save()
            log_info(logger, f"Updated subdomain providers: {subdomain_name}")
        # else: provider already recorded, no change needed
    else:
        new_subdomains = Subdomains(
            program_name = program_name,
            subdomain = subdomain_name,
            scope = get_domain_name(subdomain_name),
            providers = [provider],
            created_date = datetime.now(),
            last_update = datetime.now()
        )
        new_subdomains.save()
        log_success(logger, f"Inserted new subdomain: {subdomain_name}")
    return True
