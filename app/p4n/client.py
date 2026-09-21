"""Klient HTTP P4N: trzy źródła (nowe API around, stare API szczegółów, strona HTML miejsca).

Użytek osobisty: publiczne dane na potrzeby własnej biblioteki. Odstępy między żądaniami, brak ponawiania
przy 403/429 (Blocked), brak obejść. Zanim uruchomisz pobieranie, sprawdź regulamin serwisu i robots.txt.
"""

import base64
import gzip
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

from .endpoints import HOST, OLD_API

DELAY_GRID = (1.1, 2.4)
DELAY_DETAIL = (0.9, 2.0)
DELAY_PAGE = (1.0, 2.0)
TIMEOUT = 30

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate',
    'Referer': HOST + '/en/search',
    'Origin': HOST,
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}
PAGE_HEADERS = dict(
    BROWSER_HEADERS,
    **{
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    },
)
PAGE_HEADERS.pop('Origin', None)


class Blocked(Exception):
    """HTTP 403/429 — serwis nie chce dalszych żądań; przerywamy natychmiast."""


def sleep(delay_range):
    time.sleep(random.uniform(*delay_range))


def _read(resp):
    raw = resp.read()
    enc = (resp.headers.get('Content-Encoding') or '').lower()
    if enc == 'gzip':
        raw = gzip.decompress(raw)
    elif enc == 'deflate':
        raw = zlib.decompress(raw)
    return raw


def _get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return _read(resp)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Blocked(f'HTTP {e.code}: {url}') from e
        raise


def fetch_around(lat, lng, radius=50):
    """Nowe API: miejsca w promieniu (km); odpowiedź bywa zakodowana base64."""
    params = dict(lat=lat, lng=lng, radius=radius, filter='{}', lang='en')
    headers = dict(BROWSER_HEADERS, Referer=f'{HOST}/en/search?lat={lat}&lng={lng}&z=9')
    raw = _get(f'{HOST}/api/places/around?' + urllib.parse.urlencode(params), headers)
    try:
        data = json.loads(base64.b64decode(raw))
    except Exception:
        data = json.loads(raw)
    return data if isinstance(data, list) else []


def fetch_old_details(lat, lng):
    """Stare API: pełne rekordy (udogodnienia, ceny, zdjęcia, sezonowość) w szerokim promieniu wokół punktu."""
    headers = {k: BROWSER_HEADERS[k] for k in ('User-Agent', 'Accept-Language', 'Origin', 'Connection')}
    headers.update({'Accept': 'application/json, text/javascript, */*; q=0.01', 'Referer': HOST + '/'})
    raw = _get(OLD_API + '?' + urllib.parse.urlencode(dict(latitude=lat, longitude=lng)), headers)
    return json.loads(raw.decode('utf-8')).get('lieux', []) or []


def fetch_page(pid):
    """Strona HTML miejsca — jedyne źródło treści komentarzy."""
    return _get(f'{HOST}/en/place/{pid}', PAGE_HEADERS).decode('utf-8', 'replace')
