"""Aplikacja FastAPI: pliki statyczne, nagłówki bezpieczeństwa, obsługa błędów, cykl życia procesów w tle."""

import logging
import mimetypes
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, ai_runtime, api, importers, photo_cache, profiles
from . import storage as store
from .security import MAX_BODY_BYTES, SECURITY_HEADERS, host_ok

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / 'static'
EXAMPLES = ROOT / 'examples'
SEED = ROOT / 'seed' / 'places_pl.pack'
PROFILE_WORKER_JOIN_S = 250

# Rejestr Windows potrafi mapować .js na text/plain; moduły ES wymagają typu JavaScript.
mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('image/svg+xml', '.svg')


def seed_if_empty():
    """Pierwsze uruchomienie: pusta baza dostaje dołączony zbiór miejsc (seed/), żeby było co przeglądać od razu."""
    if not SEED.exists() or store.get_setting('seed_imported') or store.database_info()['counts']['places']:
        return
    from .core import normalize
    from .p4n.pipeline import load_seed

    spots = load_seed(SEED).get('spots', [])
    saved = 0
    for i in range(0, len(spots), 1000):
        places, _ = normalize({'spots': spots[i : i + 1000]})
        saved += store.upsert(places)
    store.set_setting('seed_imported', dict(file=SEED.name, places=saved))
    print(f'Wczytano zbiór startowy: {saved} miejsc z {SEED.name}', flush=True)


def error(message: str, status: int) -> JSONResponse:
    return JSONResponse({'error': message}, status)


def create_app(start_workers: bool = False) -> FastAPI:
    """`start_workers=True` w produkcji: uruchamia lokalną Ollamę i wątki profilowania, zdjęć i inbox.
    Testy tworzą aplikację bez procesów w tle."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.init()
        profiles.init()
        photo_cache.init()
        seed_if_empty()
        stop = threading.Event()
        profile_worker = None
        if start_workers:
            store.daily_backup()
            ai_runtime.ensure()
            profile_worker = threading.Thread(target=profiles.worker, args=(stop,), daemon=True, name='profiles')
            profile_worker.start()
            threading.Thread(target=photo_cache.worker, args=(stop,), daemon=True, name='photos').start()
            threading.Thread(target=importers.watch, args=(stop,), daemon=True, name='inbox').start()
        yield
        stop.set()
        if profile_worker:
            # Bieżąca analiza modelu kończy się normalnie; nie przerywamy jej w połowie zapisu.
            profile_worker.join(timeout=PROFILE_WORKER_JOIN_S)

    app = FastAPI(title='Prześwit', version=__version__, lifespan=lifespan, docs_url='/docs', redoc_url=None)

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if not host_ok(request):
            response = error('Host rejected', 403)
        elif (
            request.method == 'POST' and not 0 < int(request.headers.get('content-length', '0') or 0) <= MAX_BODY_BYTES
        ):
            response = error('Limit żądania: 28 MB.', 400)
        else:
            try:
                response = await call_next(request)
            except Exception:
                logging.exception('Request failed')
                response = error('Błąd aplikacji; sprawdź log serwera. Dane lokalne zachowane.', 500)
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = '.'.join(str(x) for x in first.get('loc', ()) if x != 'body')
        return error(f'Nieprawidłowe żądanie: {where or "body"} — {first.get("msg", "błąd walidacji")}', 400)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException):
        return error(str(exc.detail) if exc.status_code != 404 else 'Not found', exc.status_code)

    @app.exception_handler(HTTPError)
    async def upstream_http_error(request: Request, exc: HTTPError):
        return error(f'Zewnętrzna usługa: HTTP {exc.code}; dane lokalne zachowane.', 502)

    @app.exception_handler(URLError)
    @app.exception_handler(TimeoutError)
    async def upstream_unreachable(request: Request, exc: Exception):
        return error('Brak odpowiedzi zewnętrznej usługi. Dane lokalne zachowane.', 502)

    @app.exception_handler(ValueError)
    @app.exception_handler(TypeError)
    @app.exception_handler(KeyError)
    async def bad_request(request: Request, exc: Exception):
        return error(str(exc), 400)

    app.include_router(api.read)
    app.include_router(api.write)

    @app.get('/sw.js', include_in_schema=False)
    def service_worker():
        return FileResponse(
            STATIC / 'sw.js', media_type='text/javascript; charset=utf-8', headers={'Service-Worker-Allowed': '/'}
        )

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(STATIC / 'index.html', media_type='text/html; charset=utf-8')

    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    app.mount('/examples', StaticFiles(directory=EXAMPLES), name='examples')
    return app
