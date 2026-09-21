"""Konfiguracja z pliku data/przeswit.env (KEY=VALUE, wzór: przeswit.env.example) wczytana przed resztą modułów.

Zmienne już obecne w środowisku mają pierwszeństwo. Ścieżkę pliku można zmienić przez PRZESWIT_ENV.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path=None):
    path = Path(path or os.getenv('PRZESWIT_ENV') or ROOT / 'data' / 'przeswit.env')
    if not path.is_file():
        return {}
    loaded = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


load_env_file()
