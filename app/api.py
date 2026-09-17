"""Endpointy JSON. Ścieżki i odpowiedzi są zgodne z poprzednią wersją (stdlib http.server)."""
import base64
import os
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from . import __version__
from . import importers
from . import local_vision
from . import photo_cache
from . import profiles
from . import providers
from . import storage as store
from . import sync
from .core import analyze_ai, inside, normalize, rank
from .schemas import (CloudAnalysis, Empty, ImportRequest, KeyRequest, LibraryRequest, LocalAnalysis, NoteRequest, ParallelMode,
                      PhotosPause, ProfileSearch, ProfilesPause, RankRequest, SyncRequest)
from .security import TOKEN, require_token

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
def config():
    return ok(dict(token=TOKEN, ai_ready=bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')), sources=providers.SOURCES,
                   last_area=store.get_setting('last_area'), inbox=str(importers.INBOX), version=__version__))


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
        p['profile_info'] = info if info and info['fingerprint'] == profiles.digest(p) else {'status': 'pending', 'profile': None}
    selected = [p for p in places if not areas or any(inside(p, a) for a in areas)]
    if body.save_area and areas:
        store.set_setting('last_area', dict(areas=body.areas, radius=body.radius))
    return ok(dict(photo_cache=photo_cache.url_map(), spots=[ranked(p) for p in selected], areas=areas, total=len(places), outside=len(places) - len(selected)))


@write.post('/api/import')
def import_file(body: ImportRequest):
    content = base64.b64decode(body.content, validate=True)
    places = importers.parse_file(body.name, content, body.source)
    return ok(dict(imported=len(places), saved=store.upsert(places)))


@write.post('/api/note')
def note(body: NoteRequest):
    store.save_note(body.key, body.choice, body.note)
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
    data, _ = providers.request_json('https://commons.wikimedia.org/w/api.php',
                                     dict(action='query', format='json', titles=file, prop='imageinfo', iiprop='url|extmetadata', iiurlwidth=600),
                                     provider='commons', ttl=604800)
    page = next(iter(data.get('query', {}).get('pages', {}).values()), {})
    info = (page.get('imageinfo') or [{}])[0]
    meta = info.get('extmetadata', {})
    url = info.get('thumburl') or info.get('url', '')
    if not url.startswith('https://upload.wikimedia.org/'):
        raise ValueError('Brak zdjęcia Commons do wyświetlenia.')
    photo = dict(url=url, caption=file, source_url=info.get('descriptionurl', ''), author=providers.clean(meta.get('Artist', {}).get('value')),
                 license=providers.clean(meta.get('LicenseShortName', {}).get('value')), license_url=meta.get('LicenseUrl', {}).get('value', ''))
    p['photos'] = [x for x in p['photos'] if x.get('caption') != file] + [photo]
    p.pop('saved_ai', None)
    store.upsert([p])
    return ok(dict(spot=ranked(p)))


@write.post('/api/rank')
def rank_dataset(body: RankRequest):
    places, dups = normalize(body.dataset)
    areas = sync.parse_areas(body.areas, body.radius)
    selected = [p for p in places if any(inside(p, a) for a in areas)]
    return ok(dict(spots=[rank(p) for p in selected], areas=areas, imported=len(places), duplicates=dups, outside=len(places) - len(selected)))
