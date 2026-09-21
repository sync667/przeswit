"""Prześwit — lokalna biblioteka miejsc w naturze (stdlib HTTP + SQLite + lokalna Ollama)."""

__version__ = '2.0-local'

from . import settings  # noqa: E402,F401  (wczytuje data/przeswit.env przed pozostałymi modułami)
