"""Zabezpieczenia lokalnego serwera: token sesji, dozwolone hosty/origin, nagłówki odpowiedzi."""

import os
import secrets

from fastapi import HTTPException, Request

HOST = '127.0.0.1'
PORT = 8765
# Dostęp z internetu przez Cloudflare Tunnel + Access: PRZESWIT_PUBLIC_HOST=przeswit.example.com,
# PRZESWIT_ACCESS_EMAILS=ja@example.com,gosc@example.com (lista po przecinku; starsze PRZESWIT_ACCESS_EMAIL nadal działa).
# Żądania z publicznego hosta muszą nieść nagłówek Cloudflare Access z jednym z tych adresów — bez Access
# (albo z innym kontem) serwer odpowiada 403 nawet za tunelem.
PUBLIC_HOST = os.getenv('PRZESWIT_PUBLIC_HOST', '').strip().lower()
ACCESS_EMAILS = frozenset(
    e.strip().lower()
    for e in (os.getenv('PRZESWIT_ACCESS_EMAILS') or os.getenv('PRZESWIT_ACCESS_EMAIL') or '').split(',')
    if e.strip()
)
ACCESS_HEADER = 'Cf-Access-Authenticated-User-Email'
JWT_HEADER = 'Cf-Access-Jwt-Assertion'
# Weryfikacja podpisu JWT Access (obrona w głąb): PRZESWIT_ACCESS_TEAM=<nazwa zespołu Zero Trust>, PRZESWIT_ACCESS_AUD=<aud aplikacji>.
ACCESS_TEAM = os.getenv('PRZESWIT_ACCESS_TEAM', '').strip().lower()
ACCESS_AUD = os.getenv('PRZESWIT_ACCESS_AUD', '').strip()
# Właściciele mogą zapisywać; pozostałe dozwolone adresy przeglądają w trybie tylko do odczytu.
OWNER_EMAILS = (
    frozenset(e.strip().lower() for e in os.getenv('PRZESWIT_OWNER_EMAILS', '').split(',') if e.strip())
    or ACCESS_EMAILS
)
ALLOWED_HOSTS = frozenset({f'{HOST}:{PORT}', f'localhost:{PORT}'} | ({PUBLIC_HOST} if PUBLIC_HOST else set()))
ALLOWED_ORIGINS = frozenset(
    {f'http://{HOST}:{PORT}', f'http://localhost:{PORT}'} | ({f'https://{PUBLIC_HOST}'} if PUBLIC_HOST else set())
)
MAX_BODY_BYTES = 28_000_000
TOKEN_HEADER = 'X-ADV-Token'
CSP = (
    "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
)
SECURITY_HEADERS = {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy': CSP,
}

# Token generowany przy każdym starcie; front pobiera go z /api/config i dołącza do każdego POST.
TOKEN = secrets.token_urlsafe(24)


_JWKS = {'at': 0.0, 'keys': None}


def _jwks():
    """Klucze publiczne zespołu Access (cache 1 h)."""
    import json
    import time
    import urllib.request

    if _JWKS['keys'] is None or time.time() - _JWKS['at'] > 3600:
        with urllib.request.urlopen(
            f'https://{ACCESS_TEAM}.cloudflareaccess.com/cdn-cgi/access/certs', timeout=10
        ) as r:
            _JWKS['keys'] = json.load(r).get('keys', [])
            _JWKS['at'] = time.time()
    return _JWKS['keys']


def access_email(request: Request):
    """E-mail zalogowanego użytkownika Access; None, gdy brak/niepoprawny. Przy skonfigurowanym zespole i aud
    wymaga poprawnego podpisu JWT z nagłówka Cf-Access-Jwt-Assertion (klucze z certs zespołu)."""
    email = (request.headers.get(ACCESS_HEADER) or '').strip().lower()
    if not email:
        return None
    if ACCESS_TEAM and ACCESS_AUD:
        try:
            import jwt

            token = request.headers.get(JWT_HEADER) or ''
            kid = jwt.get_unverified_header(token).get('kid')
            key = next((k for k in _jwks() if k.get('kid') == kid), None)
            if not key:
                return None
            claims = jwt.decode(token, jwt.PyJWK(key).key, algorithms=['RS256'], audience=ACCESS_AUD)
            if (claims.get('email') or '').strip().lower() != email:
                return None
        except Exception:
            return None
    return email


def is_public(request: Request) -> bool:
    return bool(PUBLIC_HOST) and (request.headers.get('host') or '').lower() == PUBLIC_HOST


def host_ok(request: Request) -> bool:
    host = (request.headers.get('host') or '').lower()
    if host not in ALLOWED_HOSTS:
        return False
    if is_public(request):
        email = access_email(request)
        return bool(ACCESS_EMAILS) and email in ACCESS_EMAILS
    return True


def read_only(request: Request) -> bool:
    """Gość (dozwolony e-mail spoza właścicieli) przegląda bez prawa zapisu."""
    return is_public(request) and access_email(request) not in OWNER_EMAILS


def require_token(request: Request) -> None:
    """Zależność dla endpointów POST: token sesji plus Origin z tej samej aplikacji (lub brak Origin)."""
    if request.headers.get(TOKEN_HEADER) != TOKEN:
        raise HTTPException(403, 'Unauthorized')
    if request.headers.get('origin') not in (None, *ALLOWED_ORIGINS):
        raise HTTPException(403, 'Origin rejected')
    if read_only(request):
        raise HTTPException(403, 'Tryb tylko do odczytu: to konto może przeglądać, ale nie zapisywać.')
