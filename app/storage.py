"""Local durable state. Provider records remain separate; no destructive fuzzy merge."""

import datetime
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

DATA = Path(
    os.getenv('PRZESWIT_DATA', os.getenv('ADV_SCOUT_DATA', str(Path(__file__).resolve().parent.parent / 'data')))
)
BACKUP_LOCK = threading.Lock()


@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'scout.sqlite3', timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('pragma journal_mode=WAL')
    db.execute('pragma synchronous=FULL')
    db.execute('pragma busy_timeout=20000')
    try:
        with db:
            yield db
    finally:
        db.close()


def init():
    with connect() as db:
        db.executescript("""
        create table if not exists places (key text primary key, source text, body text, updated real);
        create table if not exists notes (key text primary key, choice text, note text);
        create table if not exists cache (key text primary key, body text, fetched real);
        create table if not exists jobs (id text primary key, body text);
        create table if not exists settings (key text primary key, body text);
        create table if not exists inbox (name text primary key, digest text, status text, message text, updated real);
        create table if not exists usage (provider text, day text, requests integer, bytes integer, primary key(provider,day));
        """)
        # Kto i kiedy podjął decyzję / zapisał notatkę (goście przez Access, 'local' na komputerze).
        cols = {r[1] for r in db.execute('pragma table_info(notes)')}
        if 'author' not in cols:
            db.execute('alter table notes add column author text')
            db.execute('alter table notes add column updated real')
        # Migracja nazw źródła: dawny identyfikator (pełna nazwa serwisu) → 'p4n' (klucze i treść rekordów).
        legacy = 'park4' + 'night'
        db.execute(
            'create table if not exists profiles (key text primary key, fingerprint text, version integer, status text, body text, error text, attempts integer default 0, retry_at real default 0, updated real)'
        )
        for table in ('places', 'notes', 'profiles'):
            for (key,) in db.execute(f'select key from {table} where key like ?', (legacy + ':%',)).fetchall():
                new_key = 'p4n:' + key.split(':', 1)[1]
                if db.execute(f'select 1 from {table} where key=?', (new_key,)).fetchone():
                    db.execute(
                        f'delete from {table} where key=?', (key,)
                    )  # duplikat sprzed migracji — zostaje rekord z nowym kluczem
                else:
                    db.execute(f'update {table} set key=? where key=?', (new_key, key))
        for key, body in db.execute(
            "select key,body from places where key like 'p4n:%' and body like ?", ('%"' + legacy + '"%',)
        ).fetchall():
            db.execute(
                'update places set body=? where key=?',
                (body.replace('"' + legacy + '"', '"p4n"').replace(legacy + '_url', 'p4n_url'), key),
            )
        # A restart cannot complete an interrupted network import.
        for row in db.execute('select id,body from jobs').fetchall():
            job = json.loads(row['body'])
            if job.get('status') == 'running':
                job.update(
                    status='interrupted',
                    message='Import przerwany przez zamknięcie aplikacji. Uruchom ponownie; cache zostanie użyty.',
                )
                db.execute('update jobs set body=? where id=?', (json.dumps(job), row['id']))


def key_for(p):
    return p['source'] + ':' + p['id']


def upsert(places):
    changed = 0
    with connect() as db:
        for p in places:
            key = key_for(p)
            previous = db.execute('select body from places where key=?', (key,)).fetchone()
            # Context/AI is discarded on changed input; user notes live separately.
            body = json.dumps(p, ensure_ascii=False, sort_keys=True)
            if previous and previous['body'] == body:
                continue
            db.execute(
                'insert into places values(?,?,?,?) on conflict(key) do update set body=excluded.body, updated=excluded.updated',
                (key, p['source'], body, time.time()),
            )
            changed += 1
    return changed


def delete_place(key):
    with connect() as db:
        for table in ('places', 'notes', 'profiles'):
            db.execute(f'delete from {table} where key=?', (key,))


def all_places():
    with connect() as db:
        rows = db.execute(
            'select p.*,n.choice,n.note,n.author,n.updated note_updated from places p left join notes n on n.key=p.key order by p.key'
        ).fetchall()
    out = []
    for row in rows:
        p = json.loads(row['body'])
        p['key'] = row['key']
        p['choice'] = row['choice'] or ''
        p['user_note'] = row['note'] or ''
        p['note_author'] = row['author']
        p['note_updated'] = row['note_updated']
        out.append(p)
    return out


def get_place(key):
    with connect() as db:
        r = db.execute('select body from places where key=?', (key,)).fetchone()
    if not r:
        raise ValueError('Nie znaleziono miejsca.')
    return json.loads(r['body'])


def save_note(key, choice, note, author=None):
    get_place(key)
    if choice not in ('', 'shortlist', 'A', 'B', 'rejected'):
        raise ValueError('Nieprawidłowy wybór noclegu.')
    if not isinstance(note, str) or len(note) > 10000:
        raise ValueError('Notatka: maks. 10 000 znaków.')
    with connect() as db:
        db.execute(
            'insert into notes(key,choice,note,author,updated) values(?,?,?,?,?) on conflict(key) do update set choice=excluded.choice,note=excluded.note,author=excluded.author,updated=excluded.updated',
            (key, choice, note, author or 'local', time.time()),
        )


def get_setting(key, default=None):
    with connect() as db:
        r = db.execute('select body from settings where key=?', (key,)).fetchone()
    return json.loads(r['body']) if r else default


def set_setting(key, value):
    with connect() as db:
        db.execute('insert or replace into settings values(?,?)', (key, json.dumps(value)))


def cache_get(key, ttl=86400):
    with connect() as db:
        r = db.execute('select body,fetched from cache where key=?', (key,)).fetchone()
    return json.loads(r['body']) if r and time.time() - r['fetched'] < ttl else None


def cache_put(key, body):
    with connect() as db:
        db.execute('insert or replace into cache values(?,?,?)', (key, json.dumps(body), time.time()))


def save_job(job):
    with connect() as db:
        db.execute('insert or replace into jobs values(?,?)', (job['id'], json.dumps(job, ensure_ascii=False)))


def jobs():
    with connect() as db:
        rows = db.execute('select body from jobs order by rowid desc limit 15').fetchall()
    return [json.loads(r['body']) for r in rows]


def inbox_rows():
    with connect() as db:
        return [
            dict(r)
            for r in db.execute('select name,status,message,updated from inbox order by updated desc').fetchall()
        ]


def allowance(provider):
    day = time.strftime('%Y-%m-%d', time.gmtime())
    with connect() as db:
        row = db.execute('select requests,bytes from usage where provider=? and day=?', (provider, day)).fetchone()
        if provider == 'osm' and row and (row['requests'] >= 80 or row['bytes'] >= 8_000_000):
            raise ValueError(
                'Dzienny budżet publicznego Overpass wykorzystany (80 zapytań / 8 MB). Spróbuj jutro; dane lokalne są zachowane.'
            )
        if provider == 'p4n' and row and (row['requests'] >= 36 or row['bytes'] >= 10_000_000):
            raise ValueError(
                'Dzienny budżet publicznego P4N wykorzystany (36 żądań / 10 MB). Dane lokalne są zachowane.'
            )
        db.execute(
            'insert into usage values(?,?,1,0) on conflict(provider,day) do update set requests=requests+1',
            (provider, day),
        )


def account_bytes(provider, size):
    with connect() as db:
        db.execute(
            'update usage set bytes=bytes+? where provider=? and day=?',
            (size, provider, time.strftime('%Y-%m-%d', time.gmtime())),
        )


def daily_backup(force=False):
    with BACKUP_LOCK:
        folder = DATA / 'backups'
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f' if force else '%Y-%m-%d')
        target = folder / ('przeswit-' + stamp + '.sqlite3')
        if target.exists():
            return str(target)
        temp = target.with_suffix('.partial')
        with connect() as source:
            dest = sqlite3.connect(temp)
            try:
                source.backup(dest, pages=100, sleep=0.05)
                if dest.execute('pragma quick_check').fetchone()[0] != 'ok':
                    raise ValueError('Nieprawidłowa kopia bazy.')
            finally:
                dest.close()
        temp.replace(target)
        return str(target)


def database_info():
    with connect() as db:
        mode = db.execute('pragma journal_mode').fetchone()[0]
        counts = {t: db.execute('select count(*) from ' + t).fetchone()[0] for t in ('places', 'notes', 'profiles')}
    backups = sorted((DATA / 'backups').glob('*.sqlite3'), key=lambda p: p.stat().st_mtime, reverse=True)
    return dict(
        path=str((DATA / 'scout.sqlite3').resolve()),
        engine='SQLite',
        journal=mode,
        durable_writes=True,
        counts=counts,
        backups=len(backups),
        latest_backup=str(backups[0]) if backups else None,
    )
