"""Zabezpieczenia lokalnego serwera: token sesji, dozwolone hosty/origin, nagłówki odpowiedzi."""
import secrets
from fastapi import HTTPException, Request

HOST = '127.0.0.1'
PORT = 8765
ALLOWED_HOSTS = frozenset({f'{HOST}:{PORT}', f'localhost:{PORT}'})
ALLOWED_ORIGINS = frozenset({f'http://{HOST}:{PORT}', f'http://localhost:{PORT}'})
MAX_BODY_BYTES = 28_000_000
TOKEN_HEADER = 'X-ADV-Token'
CSP = ("default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
SECURITY_HEADERS = {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy': CSP,
}

# Token generowany przy każdym starcie; front pobiera go z /api/config i dołącza do każdego POST.
TOKEN = secrets.token_urlsafe(24)


def host_ok(request: Request) -> bool:
    return request.headers.get('host') in ALLOWED_HOSTS


def require_token(request: Request) -> None:
    """Zależność dla endpointów POST: token sesji plus Origin z tej samej aplikacji (lub brak Origin)."""
    if request.headers.get(TOKEN_HEADER) != TOKEN:
        raise HTTPException(403, 'Unauthorized')
    if request.headers.get('origin') not in (None, *ALLOWED_ORIGINS):
        raise HTTPException(403, 'Origin rejected')
