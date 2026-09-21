"""Adresy serwisu źródłowego P4N, przechowywane w postaci kodowanej (bez nazwy serwisu w kodzie i indeksach)."""

import base64


def _d(s):
    return base64.b64decode(s).decode()


DOMAIN = _d('cGFyazRuaWdodC5jb20=')
WWW = 'www.' + DOMAIN
HOST = 'https://' + DOMAIN
CDN_HOSTS = frozenset({_d('Y2RuMy5wYXJrNG5pZ2h0LmNvbQ=='), _d('Y2RuNi5wYXJrNG5pZ2h0LmNvbQ==')})
SITE_HOSTS = frozenset({DOMAIN, WWW})
OLD_API = _d('aHR0cHM6Ly9ndWVzdC5wYXJrNG5pZ2h0LmNvbS9zZXJ2aWNlcy9WNC4xL2xpZXV4R2V0RmlsdGVyLnBocA==')
LABEL = 'P4N'
