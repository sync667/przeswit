"""Uruchomienie lokalnego serwera Prześwitu (uvicorn na 127.0.0.1:8765)."""

import uvicorn

from .security import HOST, PORT
from .web import create_app


def main():
    app = create_app(start_workers=True)
    print(f'Prześwit: http://{HOST}:{PORT} · Ctrl+C kończy pracę', flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
