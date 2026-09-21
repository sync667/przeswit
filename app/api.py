"""Endpointy JSON. Ścieżki i odpowiedzi są zgodne z poprzednią wersją (stdlib http.server)."""

import base64
import datetime
import os
import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from . import __version__, importers, local_vision, photo_cache, profiles, providers, sync
from . import storage as store
from .core import analyze_ai, inside, normalize, rank, valid_url
from .schemas import (
    CloudAnalysis,
    Empty,
    ImportRequest,
    KeyRequest,
    LibraryRequest,
    LocalAnalysis,
    NoteRequest,
    OwnPhoto,
    OwnPhotoDelete,
    OwnPlace,
    ParallelMode,
    PhotosPause,
    ProfileSearch,
    ProfilesPause,
    RankRequest,
    SyncRequest,
)
from .security import TOKEN, access_email, is_public, read_only, require_token

# Odczyty są otwarte dla przeglądarki; każdy zapis wymaga tokenu sesji i poprawnego Origin.
read = APIRouter()
write = APIRouter(dependencies=[Depends(require_token)])


def ok(data) -> JSONResponse:
    """Bezpośrednia serializacja słownika — bez jsonable_encoder, który spowalnia duże listy miejsc."""
    return JSONResponse(data)


def ranked(p):
    """Zapisana analiza chmurowa ma pierwszeństwo; w przeciwnym razie oceny z lokalnego profilu AI uzupełniają reguły."""
    if p.get('saved_ai'):
        return rank(p, p['saved_ai'])
    derived = profiles.as_ai(p.get('profile_info'))
    return rank(p, derived, merge=True) if derived else rank(p)


# ---------- GET ----------


@read.get('/api/config')
def config(request: Request):
    return ok(
        dict(
            token=TOKEN,
            ai_ready=bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')),
            sources=providers.SOURCES,
            last_area=store.get_setting('last_area'),
            inbox=str(importers.INBOX),
            version=__version__,
            read_only=read_only(request),
            user=access_email(request) if is_public(request) else None,
        )
    )


@read.get('/photos/{digest}')
def photo(digest: str):
    item = photo_cache.read(digest)
    if not item:
        return JSONResponse({'error': 'Zdjęcie niedostępne'}, 404)
    return Response(item[0], media_type=item[1])


@read.get('/api/photos')
def photos_status():
    return ok(photo_cache.status())


@read.get('/api/database')
def database():
    return ok(store.database_info())


@read.get('/api/profiles')
def profiles_snapshot():
    return ok(profiles.snapshot())


@read.get('/api/local-ai')
def local_ai_status():
    return ok(local_vision.status())


@read.get('/api/status')
def status():
    return ok(dict(jobs=store.jobs(), inbox=store.inbox_rows()))


# ---------- POST ----------


@write.post('/api/photos/pause')
def photos_pause(body: PhotosPause):
    store.set_setting('photos_paused', body.paused)
    return ok(photo_cache.status())


@write.post('/api/database/backup')
def database_backup(body: Empty):
    return ok(dict(path=store.daily_backup(force=True)))


@write.post('/api/profiles/parallel')
def profiles_parallel(body: ParallelMode):
    store.set_setting('profile_parallel', body.mode)
    return ok(dict(ok=True))


@write.post('/api/profile-search')
def profile_search(body: ProfileSearch):
    return ok(profiles.search(body.criteria))


@write.post('/api/profiles/pause')
def profiles_pause(body: ProfilesPause):
    store.set_setting('profiles_paused', body.paused)
    return ok(profiles.snapshot())


@write.post('/api/profiles/retry')
def profiles_retry(body: Empty):
    with store.connect() as db:
        db.execute("update profiles set status='pending',attempts=0,retry_at=0 where status='error'")
    return ok(dict(ok=True))


@write.post('/api/local-ai')
def local_ai_analyze(body: LocalAnalysis):
    return ok(dict(result=local_vision.analyze(body.key, body.criteria)))


@write.post('/api/sync')
def sync_start(body: SyncRequest):
    return ok(sync.start(body.areas, body.radius, body.sources))


@write.post('/api/library')
def library(body: LibraryRequest):
    areas = sync.parse_areas(body.areas, body.radius) if body.areas else []
    places = store.all_places()
    pm = profiles.profiles_map()
    for p in places:
        info = pm.get(p['key'])
        p['profile_info'] = (
            info if info and info['fingerprint'] == profiles.digest(p) else {'status': 'pending', 'profile': None}
        )
    selected = [p for p in places if not areas or any(inside(p, a) for a in areas)]
    if body.save_area and areas:
        store.set_setting('last_area', dict(areas=body.areas, radius=body.radius))
    return ok(
        dict(
            photo_cache=photo_cache.url_map(),
            spots=[ranked(p) for p in selected],
            areas=areas,
            total=len(places),
            outside=len(places) - len(selected),
        )
    )


@write.post('/api/import')
def import_file(body: ImportRequest):
    content = base64.b64decode(body.content, validate=True)
    places = importers.parse_file(body.name, content, body.source)
    return ok(dict(imported=len(places), saved=store.upsert(places)))


@write.post('/api/note')
def note(body: NoteRequest, request: Request):
    store.save_note(body.key, body.choice, body.note, author=access_email(request) if is_public(request) else 'local')
    return ok(dict(ok=True))


@write.post('/api/enrich')
def enrich(body: KeyRequest):
    p = providers.enrich(store.get_place(body.key))
    store.upsert([p])
    return ok(dict(spot=ranked(p)))


@write.post('/api/ai')
def cloud_ai(body: CloudAnalysis):
    p = store.get_place(body.key)
    if p.get('local_only') or p.get('source') == 'ioverlander':
        raise ValueError('Ten rekord jest przeznaczony do użytku lokalnego; nie wysyłamy go do zewnętrznego AI.')
    a = analyze_ai(p, body.photos)
    p['saved_ai'] = a
    store.upsert([p])
    return ok(dict(spot=ranked(p)))


@write.post('/api/commons')
def commons(body: KeyRequest):
    p = store.get_place(body.key)
    file = p.get('commons_file', '')
    if not isinstance(file, str) or not file.startswith('File:') or len(file) > 400:
        raise ValueError('Brak odnośnika do pliku Wikimedia Commons.')
    data, _ = providers.request_json(
        'https://commons.wikimedia.org/w/api.php',
        dict(action='query', format='json', titles=file, prop='imageinfo', iiprop='url|extmetadata', iiurlwidth=600),
        provider='commons',
        ttl=604800,
    )
    page = next(iter(data.get('query', {}).get('pages', {}).values()), {})
    info = (page.get('imageinfo') or [{}])[0]
    meta = info.get('extmetadata', {})
    url = info.get('thumburl') or info.get('url', '')
    if not url.startswith('https://upload.wikimedia.org/'):
        raise ValueError('Brak zdjęcia Commons do wyświetlenia.')
    photo = dict(
        url=url,
        caption=file,
        source_url=info.get('descriptionurl', ''),
        author=providers.clean(meta.get('Artist', {}).get('value')),
        license=providers.clean(meta.get('LicenseShortName', {}).get('value')),
        license_url=meta.get('LicenseUrl', {}).get('value', ''),
    )
    p['photos'] = [x for x in p['photos'] if x.get('caption') != file] + [photo]
    p.pop('saved_ai', None)
    store.upsert([p])
    return ok(dict(spot=ranked(p)))


@write.post('/api/rank')
def rank_dataset(body: RankRequest):
    places, dups = normalize(body.dataset)
    areas = sync.parse_areas(body.areas, body.radius)
    selected = [p for p in places if any(inside(p, a) for a in areas)]
    return ok(
        dict(
            spots=[rank(p) for p in selected],
            areas=areas,
            imported=len(places),
            duplicates=dups,
            outside=len(places) - len(selected),
        )
    )


OWN_SOURCE = 'own-notes'
OWN_STATUS_LABELS = {'planned': 'Planowane', 'visited': 'Byłem', 'someday': 'Na kiedyś'}


@write.post('/api/places/own')
def own_place(body: OwnPlace, request: Request):
    """Dodaje lub edytuje własny punkt (source=own-notes). Notatka i wybór trafiają do tabeli notes jak przy innych miejscach."""
    name = body.name.strip()
    if not 1 <= len(name) <= 200:
        raise ValueError('Nazwa: 1–200 znaków.')
    if body.url and not valid_url(body.url):
        raise ValueError('Link musi być poprawnym adresem HTTPS.')
    existing = None
    if body.key:
        existing = store.get_place(body.key)
        if existing.get('source') != OWN_SOURCE:
            raise ValueError('Edytować można tylko własne punkty.')
    spot = dict(
        id=existing['id'] if existing else uuid.uuid4().hex[:12],
        source=OWN_SOURCE,
        name=name,
        lat=body.lat,
        lon=body.lon,
        type='nature',
        description=body.description.strip()[:6000],
        comments=existing.get('comments', []) if existing else [],
        photos=existing.get('photos', []) if existing else [],
        geo=existing.get('geo', {}) if existing else {},
        evidence=[],
        own_status=body.status,
        source_url=body.url or '',
        fetched_at=existing.get('fetched_at') if existing else datetime.datetime.now(datetime.timezone.utc).isoformat(),
        license='Własna notatka użytkownika',
        local_only=True,
    )
    places, _ = normalize({'spots': [spot]})
    store.upsert(places)
    key = f'{OWN_SOURCE}:{places[0]["id"]}'
    # Planowane i „na kiedyś” lądują na liście zachowanych; odwiedzone zostają w „Wszystkie” z notatką.
    store.save_note(
        key,
        'shortlist' if body.status in ('planned', 'someday') else '',
        body.note.strip()[:10000],
        author=access_email(request) if is_public(request) else 'local',
    )
    return ok(dict(key=key))


@write.post('/api/places/own/delete')
def own_place_delete(body: KeyRequest):
    p = store.get_place(body.key)
    if p.get('source') != OWN_SOURCE:
        raise ValueError('Usuwać można tylko własne punkty.')
    store.delete_place(body.key)
    for ph in p.get('photos', []):
        if str(ph.get('url', '')).startswith('own://'):
            photo_cache.delete_own(ph['url'])
    return ok(dict(ok=True))


MAX_OWN_PHOTOS = 20


@write.post('/api/places/own/photos')
def own_photo_add(body: OwnPhoto):
    """Dodaje własne zdjęcie (base64) do własnego punktu; plik ląduje w data/photos, adres own://<sha256>."""
    p = store.get_place(body.key)
    if p.get('source') != OWN_SOURCE:
        raise ValueError('Zdjęcia można dodawać tylko do własnych punktów.')
    if len(p.get('photos', [])) >= MAX_OWN_PHOTOS:
        raise ValueError(f'Maksymalnie {MAX_OWN_PHOTOS} zdjęć na punkt.')
    url = photo_cache.store_own(base64.b64decode(body.content, validate=True))
    if not any(ph.get('url') == url for ph in p['photos']):
        p['photos'].append(dict(url=url, caption=body.caption.strip()[:200] or 'Własne zdjęcie', source_url=''))
        store.upsert([p])
    return ok(dict(url=url, photos=len(p['photos'])))


@write.post('/api/places/own/photos/delete')
def own_photo_delete(body: OwnPhotoDelete):
    p = store.get_place(body.key)
    if p.get('source') != OWN_SOURCE:
        raise ValueError('Zdjęcia można usuwać tylko z własnych punktów.')
    p['photos'] = [ph for ph in p['photos'] if ph.get('url') != body.url]
    store.upsert([p])
    if body.url.startswith('own://'):
        photo_cache.delete_own(body.url)
    return ok(dict(photos=len(p['photos'])))
