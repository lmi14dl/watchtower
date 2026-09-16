import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from mongoengine import Document, StringField, DateTimeField, ListField, DictField, connect
from datetime import datetime
from config import config
import tldextract, requests

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_domain_name(url):
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"

def send_discord_message(message):
    data = {
        "content": message
    }
    response = requests.post(config().get('WEBHOOK_URL'), json=data)
    if response.status_code == 204:
        pass
    else:
        print(response.status_code)


_MONGO_HOST = os.environ.get('MONGO_HOST', '127.0.0.1')
_MONGO_PORT = os.environ.get('MONGO_PORT', '27017')
connect('watchtower', host=f'mongodb://{_MONGO_HOST}:{_MONGO_PORT}/watchtower')

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
    # print(program.program_name)
    existing = LiveSubdomains.objects(subdomain=obj['subdomain']).first()

    if existing:
        obj['ips'].sort()
        existing.ips.sort()
        if obj['ips'] != existing.ips:
            existing.ips = obj['ips']
            print(f"[{current_time()}] Updated live subdomain: {obj['subdomain']}")
        existing.last_update = datetime.now()
        existing.save()

    else:
        new_live = LiveSubdomains(
            program_name=program.program_name,
            subdomain=obj['subdomain'],
            scope=obj['domain'],
            ips=obj['ips'],
            created_date=datetime.now(),
            last_update=datetime.now(),
            cdn=None
        )
        
        new_live.save()
        send_discord_message(f"""
        ```'{obj['subdomain']}' (fresh live) has been added to '{program.program_name}' program```
        """)
        print(f"[{current_time()}] Inserted new live subdomain: {obj['subdomain']} for program: {program.program_name}")
        

def upsert_http(obj):
    # {'subdomain': 'api.voorivex.academy', 'scope': 'voorivex.academy', 'ips': ['188.114.97.2', '188.114.96.2'], 'tech': ['Cloudflare', 'Express', 'HTTP/3', 'Node.js'], 'title': '', 'status_code': 404, 'headers': {'access_control_allow_credentials': 'true', 'access_control_allow_origin': '*', 'alt_svc': 'h3=":443"; ma=86400', 'cf_cache_status': 'DYNAMIC', 'cf_ray': 'a23d82e9cc580f1e-CDG', 'content_type': 'application/json; charset=utf-8', 'date': 'Fri, 31 Jul 2026 15:07:12 GMT', 'etag': 'W/"3f-BunLb98SCK6azHy0RO08GDnFBek"', 'nel': '{"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}', 'report_to': '{"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=WpIAMSX1PvCJwV3xNgHW6xFLLtVq2hzI5plX0wIZlLfipsGu6SMrsyeCvmLbMaHJvfCB2zA%2BovRrI3K10CQtYw1Nymf50WnG9RnN%2BG4bhTvsx3tYSotFyDKVGovAFJVZSbgmZffrIA%3D%3D"}]}', 'server': 'cloudflare', 'x_powered_by': 'Express'}, 'url': 'https://api.voorivex.academy:443', 'final_url': '', 'favicon_md5': ''}
    program = Programs.objects(scopes=obj['scope']).first()
    existing = HTTP.objects(subdomain=obj['subdomain']).first()

    if existing:

        if existing.title != obj.get('title'):
            send_discord_message(f"""
            ```'{obj['subdomain']}' Title has been changed from '{obj.get('title')}' to '{existing.title}' ```
            """)
            print(f"[{current_time()}] Changes Title for subdomain: {obj['subdomain']}")
            existing.title = obj.get('title')
           
        if existing.status_code != str(obj.get('status_code')):
            send_discord_message(f"""
            ```'{obj['subdomain']}' Status Code has been changed from '{obj.get('status_code')}' to '{existing.status_code}'```
            """)
            print(f"[{current_time()}] Changes Status Code for subdomain: {obj['subdomain']}")
            existing.status_code = str(obj.get('status_code'))

        if existing.favicon != obj.get('favicon'):
            send_discord_message(f"""
            ```'{obj['subdomain']}' favhash has been changed from '{obj.get('favicon')}' to '{existing.favicon}'```
            """)
            print(f"[{current_time()}] Changes favhash for subdomain: {obj['subdomain']}")
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
        send_discord_message(f"""
        ```'{obj['subdomain']}' (fresh http) has been added to '{program.program_name}' program```
        """)
        print(f"[{current_time()}] Inserted new http service: {obj['subdomain']} for program: {program.program_name}")
        


# Upsert (Update and Insert) Programs
def upsert_program(program_name, scopes, ooscopes, config):
    program = Programs.objects(program_name=program_name).first()
    if program:
        # Update existing program fields
        program.config = config
        program.scopes = scopes
        program.ooscopes = ooscopes
        program.save()
        print(f"[{current_time()}] Updated program: {program.program_name}")
    else:
        # Create new program
        new_program = Programs(
            program_name=program_name,
            created_date=datetime.now,
            config=config,
            scopes=scopes,
            ooscopes=ooscopes
        )
        new_program.save()
        print(f"[{current_time()}] Inserted new program {new_program.program_name}")

# Upsert subdomains (check if subdomain exists, if not insert, if yes update providers)
def upsert_subdomains(program_name, subdomain_name, provider):
    program = Programs.objects(program_name=program_name).first()

    if get_domain_name(subdomain_name) not in program.scopes or subdomain_name in program.ooscopes:
        print(f"[{current_time()}] subdomain is not in scope: {subdomain_name}")
        return True

    # TODO: check if subdomain exist or not, filter: domain.tld

    existing = Subdomains.objects(program_name=program_name, subdomain=subdomain_name).first()
    if existing:
        if provider not in existing.providers:
            existing.providers.append(provider)
            existing.last_update = datetime.now()
            existing.save()
            print(f"[{current_time()}] Updated subdomain: {subdomain_name}")
        else:
            pass
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
        print(f"[{current_time()}] Insterted new subdomains: {subdomain_name}")