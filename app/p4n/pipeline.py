"""Kroki pobierania: siatka (around) → szczegóły (stare API) → komentarze (HTML) → konwersja → import do bazy / plik seed."""

import datetime as dt
import gzip
import json
import random
import time
from collections import defaultdict
from pathlib import Path

from .. import storage as store
from ..core import normalize
from . import client
from .convert import convert, parse_comments
from .dataset import Dataset

POLAND_BBOX = (49.0, 14.1, 54.9, 24.2)  # lat_min, lon_min, lat_max, lon_max
STEP = 0.35
RADIUS_KM = 50
CLUSTER = 0.15
SAVE_EVERY = 20
BATCH = 1000  # limit normalize() to 5000 miejsc na wywołanie


def grid(bbox, step=STEP):
    lat_min, lon_min, lat_max, lon_max = bbox
    lats, lat = [], lat_min
    while lat <= lat_max + 1e-9:
        lats.append(round(lat, 4))
        lat += step
    lons, lon = [], lon_min
    while lon <= lon_max + 1e-9:
        lons.append(round(lon, 4))
        lon += step
    return [(la, lo) for la in lats for lo in lons]


def scan(ds: Dataset, bbox=POLAND_BBOX, step=STEP, radius=RADIUS_KM, types=('PN',)):
    """Siatka punktów; każda komórka odpytana raz (state.cells). Zapisuje wszystkie miejsca wybranych typów."""
    done = set(tuple(c) for c in ds.state.get('cells', []))
    cells = [c for c in grid(bbox, step) if c not in done]
    random.shuffle(cells)
    ds.log(f'scan: komórek do sprawdzenia {len(cells)} (zrobionych {len(done)}), bbox={bbox}')
    for i, (lat, lon) in enumerate(cells, 1):
        try:
            places = client.fetch_around(lat, lon, radius)
        except client.Blocked as e:
            ds.log(f'BLOKADA: {e} — przerywam')
            ds.save()
            raise
        except Exception as e:
            ds.log(f'[{i}/{len(cells)}] {lat},{lon}: błąd {type(e).__name__}: {e}')
            client.sleep(client.DELAY_GRID)
            continue
        new = 0
        for p in places:
            if (p.get('type') or {}).get('code') in types and str(p.get('id')) not in ds.places:
                ds.places[str(p['id'])] = p
                new += 1
        ds.state.setdefault('cells', []).append([lat, lon])
        ds.state['fetched_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        ds.log(f'[{i}/{len(cells)}] {lat:.2f},{lon:.2f} +{new} (łącznie {len(ds.places)})')
        if i % SAVE_EVERY == 0:
            ds.save('places', 'state')
        if i < len(cells):
            client.sleep(client.DELAY_GRID)
    ds.save('places', 'state')


def details(ds: Dataset):
    """Stare API zwraca szeroki promień, więc odpytujemy klastry 0,15°, a resztę punkt po punkcie."""
    missing = ds.missing_details()
    clusters = defaultdict(list)
    for pid in missing:
        p = ds.places[pid]
        clusters[(round(p['lat'] / CLUSTER) * CLUSTER, round(p['lng'] / CLUSTER) * CLUSTER)].append(pid)
    items = list(clusters.items())
    random.shuffle(items)
    ds.log(f'details: brakuje {len(missing)} rekordów w {len(items)} klastrach')

    def absorb(records):
        found = 0
        for op in records:
            oid = str(op.get('id'))
            if oid in ds.places and oid not in ds.details:
                ds.details[oid] = op
                found += 1
        return found

    for i, ((clat, clon), pids) in enumerate(items, 1):
        if all(pid in ds.details for pid in pids):
            continue
        try:
            found = absorb(client.fetch_old_details(round(clat, 4), round(clon, 4)))
            ds.log(
                f'[{i}/{len(items)}] klaster {clat:.2f},{clon:.2f}: +{found}/{len(pids)} (pełnych {len(ds.details)})'
            )
        except client.Blocked as e:
            ds.log(f'BLOKADA: {e} — przerywam')
            ds.save('details')
            raise
        except Exception as e:
            ds.log(f'[{i}/{len(items)}] błąd {type(e).__name__}: {e}')
        if i % SAVE_EVERY == 0:
            ds.save('details')
        client.sleep(client.DELAY_DETAIL)
    rest = ds.missing_details()
    random.shuffle(rest)
    for i, pid in enumerate(rest, 1):
        p = ds.places[pid]
        try:
            absorb(client.fetch_old_details(p['lat'], p['lng']))
            ds.log(f'  [{i}/{len(rest)}] {pid}: {"ok" if pid in ds.details else "brak"}')
        except client.Blocked as e:
            ds.log(f'BLOKADA: {e} — przerywam')
            ds.save('details')
            raise
        except Exception as e:
            ds.log(f'  [{i}/{len(rest)}] {pid}: błąd {type(e).__name__}: {e}')
        if i % SAVE_EVERY == 0:
            ds.save('details')
        client.sleep(client.DELAY_DETAIL)
    ds.save('details')


def comments(ds: Dataset, country=None):
    """Komentarze ze stron HTML dla miejsc z nb_commentaires > 0; wskazany kraj najpierw."""
    first = ds.missing_comments(country) if country else []
    rest = [pid for pid in ds.missing_comments() if pid not in set(first)]
    random.shuffle(first)
    random.shuffle(rest)
    todo = first + rest
    ds.log(f'comments: do pobrania {len(todo)} miejsc (w tym {len(first)} z {country or "-"})')
    t0 = time.time()
    for i, pid in enumerate(todo, 1):
        try:
            items, declared = parse_comments(client.fetch_page(pid))
            ds.comments[pid] = items
            exp = ds.expected_comments(pid)
            ds.log(
                f'[{i}/{len(todo)}] {pid}: {len(items)} kom.'
                + ('' if len(items) == exp else f' (oczekiwano {exp}, strona {declared})')
            )
        except client.Blocked as e:
            ds.log(f'BLOKADA: {e} — przerywam')
            ds.save('comments')
            raise
        except Exception as e:
            ds.log(f'[{i}/{len(todo)}] {pid}: błąd {type(e).__name__}: {e}')
        if i % SAVE_EVERY == 0:
            ds.save('comments')
        if i < len(todo):
            client.sleep(client.DELAY_PAGE)
    ds.save('comments')
    ds.log(f'comments: koniec, {time.time() - t0:.0f}s')


def spots(ds: Dataset, country=None, with_authors=True):
    fetched = ds.state.get('fetched_at') or dt.datetime.now(dt.timezone.utc).isoformat()
    return [
        convert(ds.places[pid], ds.details.get(pid), ds.comments.get(pid), fetched, with_authors)
        for pid in ds.ids(country)
    ]


def ingest(ds: Dataset, country=None):
    """Upsert do bazy aplikacji (klucz p4n:<id>); zmienione rekordy trafią ponownie do kolejki profili."""
    items = spots(ds, country)
    changed = 0
    for i in range(0, len(items), BATCH):
        places, _ = normalize({'spots': items[i : i + BATCH]})
        changed += store.upsert(places)
    ds.log(f'ingest: {len(items)} rekordów ({country or "wszystkie kraje"}), zapisanych/odświeżonych {changed}')
    return len(items), changed


PACK_MAGIC = b'PSWT1'


def _mask(data: bytes) -> bytes:
    """Odwracalne maskowanie strumienia (klucz z SHA-256 stałej) — zbiór nie jest czytelny ani indeksowalny jako tekst."""
    import hashlib

    key = hashlib.sha256(b'przeswit-seed-pack').digest()
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def pack_seed(payload: dict) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return PACK_MAGIC + _mask(gzip.compress(raw, compresslevel=9))


def unpack_seed(blob: bytes) -> dict:
    if not blob.startswith(PACK_MAGIC):
        raise ValueError('Nieznany format zbioru startowego.')
    return json.loads(gzip.decompress(_mask(blob[len(PACK_MAGIC) :])).decode('utf-8'))


def export_seed(ds: Dataset, path, country='Poland'):
    """Plik startowy dystrybuowany z aplikacją (.pack): bez autorów komentarzy i bez danych kontaktowych (convert je pomija)."""
    items = spots(ds, country, with_authors=False)
    payload = dict(label=f'Zbiór startowy · {country} · {str(ds.state.get("fetched_at") or "")[:10]}', spots=items)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pack_seed(payload))
    ds.log(f'seed: {len(items)} miejsc → {path} ({path.stat().st_size // 1024} KiB)')
    return len(items)


def load_seed(path):
    return unpack_seed(Path(path).read_bytes())
