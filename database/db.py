import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import re
import atexit
from datetime import datetime, timedelta
from mongoengine import Document, StringField, DateTimeField, ListField, DictField, Q, connect
from pymongo import UpdateOne
from config import config
from logutil import get_logger, log_info, log_error, log_success
from notifier import notify, get_enabled_services
from logutil import log_warn
# Module logger
logger = get_logger("database")

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_domain_name(url):
    import tldextract  # lazy: only the API needs it
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"


# ---------------------------------------------------------------------------
# Notifications: queued and sent as batched digests (never one POST per item)
#   WATCH_NO_NOTIFY=1      disable DB-level notifications
#   NOTIFY_MAX_PER_RUN=200 cap per process; the rest is summarised in one line
# ---------------------------------------------------------------------------
_NOTIFY_MAX = int(os.environ.get('NOTIFY_MAX_PER_RUN', '200'))
_NOTIFY_DISABLED = os.environ.get('WATCH_NO_NOTIFY', '').lower() in ('1', 'true', 'yes')
_pending = []
_pending_len = 0
_sent = 0
_suppressed = 0


def flush_notifications():
    global _pending, _pending_len, _suppressed
    if _pending:
        notify("\n".join(_pending))
        _pending = []
        _pending_len = 0
    if _suppressed:
        notify(f"... and {_suppressed} more notifications suppressed (NOTIFY_MAX_PER_RUN={_NOTIFY_MAX})")
        _suppressed = 0


def notify_all(message):
    """Queue a notification; messages are flushed in batches (and at exit)."""
    global _pending_len, _sent, _suppressed
    if _NOTIFY_DISABLED or not get_enabled_services():
        return
    if _sent >= _NOTIFY_MAX:
        _suppressed += 1
        return
    _sent += 1
    _pending.append(message)
    _pending_len += len(message) + 1
    if _pending_len >= 1800:
        flush_notifications()


atexit.register(flush_notifications)


_MONGO_HOST = os.environ.get('MONGO_HOST', '127.0.0.1')
_MONGO_PORT = os.environ.get('MONGO_PORT', '27017')
_MONGO_URI = os.environ.get('MONGO_URI') or f'mongodb://{_MONGO_HOST}:{_MONGO_PORT}/watchtower'
log_info(logger, f"Connecting to MongoDB at {_MONGO_HOST}:{_MONGO_PORT}")
connect('watchtower', host=_MONGO_URI)
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
            {'fields': ['program_name'], 'unique': True},
            'scopes',
        ]
    }

class Subdomains(Document):
    program_name = StringField(required=True)
    subdomain = StringField(required=True)
    scope = StringField(required=True)
    providers = ListField(StringField())
    created_date = DateTimeField(default=datetime.now)
    last_update = DateTimeField(default=datetime.now)
    last_resolved = DateTimeField()

    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain'], 'unique': True},
            'subdomain',
            ['scope', 'last_resolved'],
            'providers',
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
    last_probed = DateTimeField()

    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain'], 'unique': True},
            'subdomain',
            ['scope', 'last_probed'],
            'last_update',
            'created_date',
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
    last_nuclei = DateTimeField()

    # One record per URL (host + port + scheme): different ports of the same
    # host no longer overwrite each other / trigger fake "changed" alerts.
    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain', 'url'], 'unique': True},
            'subdomain',
            'scope',
            'last_update',
            'created_date',
            'last_nuclei',
        ]
    }


def _migrate_indexes():
    """
    Older versions had a UNIQUE index on HTTP(program_name, subdomain), which
    forbids several URLs per host. Drop it if it still exists.
    """
    try:
        col = HTTP._get_collection()  # also makes sure the new indexes exist
        for name, spec in col.index_information().items():
            keys = [k for k, _ in spec.get('key', [])]
            if name != '_id_' and spec.get('unique') and keys == ['program_name', 'subdomain']:
                col.drop_index(name)
                log_info(logger, f"Dropped legacy unique index {name} on HTTP")
    except Exception as e:
        log_warn(logger, f"Index migration skipped: {e}")


_migrate_indexes()


# ---------------------------------------------------------------------------
# Lookup caches / helpers (avoid one Mongo round-trip per record)
# ---------------------------------------------------------------------------
_program_cache = {}   # program_name -> Programs
_scope_cache = {}     # scope -> Programs
_HOST_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')


def _program_by_name(name):
    p = _program_cache.get(name)
    if p is None:
        p = Programs.objects(program_name=name).first()
        if p:
            _program_cache[name] = p
    return p


def _program_by_scope(scope):
    p = _scope_cache.get(scope)
    if p is None:
        p = Programs.objects(scopes=scope).first()
        if p:
            _scope_cache[scope] = p
    return p


def match_scope(host, scopes):
    """Return the scope that `host` belongs to (host == scope or *.scope), else None."""
    for s in scopes:
        if host == s or host.endswith('.' + s):
            return s
    return None


def _chunked(seq, n):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ---------------------------------------------------------------------------
# Incremental selection helpers
# ---------------------------------------------------------------------------
def get_subdomains_to_resolve(scope, stale_hours):
    """Subdomains of `scope` never resolved, or not resolved in the last `stale_hours`."""
    cutoff = datetime.now() - timedelta(hours=stale_hours)
    qs = Subdomains.objects(scope=scope).filter(Q(last_resolved=None) | Q(last_resolved__lt=cutoff))
    return list(qs.scalar('subdomain'))


def mark_subdomains_resolved(scope, subdomains):
    col = Subdomains._get_collection()
    now = datetime.now()
    for part in _chunked(subdomains, 5000):
        col.update_many({'scope': scope, 'subdomain': {'$in': part}}, {'$set': {'last_resolved': now}})


def get_lives_to_probe(scope, stale_hours):
    """Live subdomains of `scope` never probed, or not probed in the last `stale_hours`."""
    cutoff = datetime.now() - timedelta(hours=stale_hours)
    qs = LiveSubdomains.objects(scope=scope).filter(Q(last_probed=None) | Q(last_probed__lt=cutoff))
    return list(qs.scalar('subdomain'))


def mark_lives_probed(scope, subdomains):
    col = LiveSubdomains._get_collection()
    now = datetime.now()
    for part in _chunked(subdomains, 5000):
        col.update_many({'scope': scope, 'subdomain': {'$in': part}}, {'$set': {'last_probed': now}})


def get_urls_for_nuclei(rescan_days, limit):
    """HTTP URLs never scanned by nuclei, or scanned more than `rescan_days` ago."""
    cutoff = datetime.now() - timedelta(days=rescan_days)
    qs = HTTP.objects(url__ne=None).filter(Q(last_nuclei=None) | Q(last_nuclei__lt=cutoff))
    return list(qs.limit(limit).scalar('url'))


def mark_urls_nuclei(urls):
    col = HTTP._get_collection()
    now = datetime.now()
    for part in _chunked(urls, 5000):
        col.update_many({'url': {'$in': part}}, {'$set': {'last_nuclei': now}})


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------
def upsert_lives(obj):
    program = _program_by_scope(obj['domain'])
    if not program:
        log_error(logger, f"No program found for scope {obj['domain']}")
        return

    now = datetime.now()
    ips = sorted(set(obj.get('ips') or []))
    res = LiveSubdomains._get_collection().update_one(
        {'program_name': program.program_name, 'subdomain': obj['subdomain']},
        {
            '$set': {'ips': ips, 'scope': obj['domain'], 'last_update': now},
            '$setOnInsert': {'created_date': now, 'cdn': obj.get('cdn')},
        },
        upsert=True,
    )
    if res.upserted_id is not None:
        notify_all(f"```{obj['subdomain']} (fresh live) has been added to '{program.program_name}' program```")
        log_success(logger, f"Inserted new live subdomain: {obj['subdomain']} for program: {program.program_name}")


def upsert_http(obj):
    program = _program_by_scope(obj['scope'])
    if not program:
        log_error(logger, f"No program found for scope {obj['scope']}")
        return

    col = HTTP._get_collection()
    sub = obj.get('subdomain')
    url = obj.get('url') or sub
    key = {'program_name': program.program_name, 'subdomain': sub, 'url': url}
    now = datetime.now()
    new_vals = {
        'scope': obj.get('scope'),
        'ips': obj.get('ips') or [],
        'tech': str(obj.get('tech')),
        'title': obj.get('title'),
        'status_code': str(obj.get('status_code')),
        'headers': obj.get('headers') or {},
        'final_url': obj.get('final_url'),
        'favicon': obj.get('favicon'),
        'last_update': now,
    }

    existing = col.find_one(key, {'title': 1, 'status_code': 1, 'favicon': 1})
    if existing is None:
        first_for_host = col.count_documents(
            {'program_name': program.program_name, 'subdomain': sub}, limit=1) == 0
        col.update_one(key, {'$set': new_vals, '$setOnInsert': {'created_date': now}}, upsert=True)
        if first_for_host:
            notify_all(f"```{sub} (fresh http) has been added to '{program.program_name}' program```")
        log_success(logger, f"Inserted new http service: {url} for program: {program.program_name}")
        return

    label = url
    if existing.get('title') != obj.get('title'):
        notify_all(f"```{label} Title has been changed from '{existing.get('title')}' to '{obj.get('title')}'```")
        log_info(logger, f"Title changed for: {label}")
    if existing.get('status_code') != str(obj.get('status_code')):
        notify_all(f"```{label} Status Code has been changed from '{existing.get('status_code')}' to '{str(obj.get('status_code'))}'```")
        log_info(logger, f"Status Code changed for: {label}")
    if existing.get('favicon') != obj.get('favicon'):
        notify_all(f"```{label} favicon has been changed from '{existing.get('favicon')}' to '{obj.get('favicon')}'```")
        log_info(logger, f"Favicon changed for: {label}")

    col.update_one({'_id': existing['_id']}, {'$set': new_vals})


# Upsert (Update and Insert) Programs
def upsert_program(program_name, scopes, ooscopes, config):
    program = Programs.objects(program_name=program_name).first()
    scopes = scopes or []
    ooscopes = ooscopes or []
    if program:
        program.config = config
        program.scopes = scopes
        program.ooscopes = ooscopes
        program.save()
        log_info(logger, f"Updated program: {program.program_name}")
    else:
        new_program = Programs(
            program_name=program_name,
            created_date=datetime.now(),
            config=config,
            scopes=scopes,
            ooscopes=ooscopes
        )
        new_program.save()
        log_success(logger, f"Inserted new program: {new_program.program_name}")
    _program_cache.pop(program_name, None)
    _scope_cache.clear()


def upsert_subdomains_bulk(program_name, subdomains, provider, chunk=1000):
    """
    Insert/update many subdomains with a few bulk writes instead of one
    query per subdomain. Out-of-scope / junk hosts are skipped.
    Returns the number of newly inserted subdomains.
    """
    program = _program_by_name(program_name)
    if not program:
        log_error(logger, f"Program '{program_name}' not found")
        return 0

    scopes = [s.strip().lower() for s in (program.scopes or []) if s and s.strip()]
    oos = {x.strip().lower() for x in (program.ooscopes or []) if x and x.strip()}
    col = Subdomains._get_collection()
    now = datetime.now()

    seen = set()
    ops = []
    stats = {'new': 0, 'skipped': 0, 'total': 0}

    def flush():
        if ops:
            res = col.bulk_write(ops, ordered=False)
            stats['new'] += res.upserted_count
            ops.clear()

    for raw in subdomains:
        host = (raw or '').strip().lower().rstrip('.')
        if not host or host in seen:
            continue
        seen.add(host)
        if not _HOST_RE.match(host) or host in oos:
            stats['skipped'] += 1
            continue
        scope = match_scope(host, scopes)
        if not scope:
            stats['skipped'] += 1
            continue
        stats['total'] += 1
        ops.append(UpdateOne(
            {'program_name': program_name, 'subdomain': host},
            {
                '$addToSet': {'providers': provider},
                '$setOnInsert': {'scope': scope, 'created_date': now, 'last_update': now},
            },
            upsert=True,
        ))
        if len(ops) >= chunk:
            flush()
    flush()

    log_info(logger, f"[{provider}] {program_name}: {stats['total']} in-scope, "
                     f"{stats['new']} new, {stats['skipped']} skipped")
    return stats['new']


# Upsert a single subdomain (kept for backward compatibility)
def upsert_subdomains(program_name, subdomain_name, provider):
    if not _program_by_name(program_name):
        log_error(logger, f"Program '{program_name}' not found for subdomain: {subdomain_name}")
        return False
    upsert_subdomains_bulk(program_name, [subdomain_name], provider)
    return True
