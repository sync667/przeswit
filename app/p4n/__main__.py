"""CLI: python -m app.p4n <krok> [opcje]

scan            siatka bbox (domyślnie cała Polska) → rekordy podstawowe
details         szczegóły ze starego API
comments        komentarze ze stron HTML (--country najpierw)
ingest          konwersja i zapis do bazy aplikacji (--country ogranicza)
seed            plik startowy seed/places_pl.pack (bez autorów komentarzy)
all             scan → details → comments → ingest
import-legacy   wczytaj pliki starszych skryptów (--legacy-dir)
status          liczby w zbiorze
"""

import argparse
import sys

from . import pipeline
from .dataset import Dataset


def bbox_arg(text):
    parts = [float(x) for x in text.split(',')]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError('bbox: lat_min,lon_min,lat_max,lon_max')
    return tuple(parts)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(
        prog='python -m app.p4n', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument('step', choices=['scan', 'details', 'comments', 'ingest', 'seed', 'all', 'import-legacy', 'status'])
    ap.add_argument('--dir', help='katalog stanu (domyślnie data/p4n)')
    ap.add_argument(
        '--bbox', type=bbox_arg, default=pipeline.POLAND_BBOX, help='lat_min,lon_min,lat_max,lon_max (domyślnie Polska)'
    )
    ap.add_argument(
        '--country',
        default='Poland',
        help='kraj z address.country (komentarze najpierw, ingest/seed tylko ten kraj); "" = wszystkie',
    )
    ap.add_argument('--legacy-dir', default='data/scrape')
    ap.add_argument('--seed-path', default='seed/places_pl.pack')
    args = ap.parse_args(argv)
    country = args.country or None
    ds = Dataset(args.dir)
    if args.step == 'import-legacy':
        print(ds.import_legacy(args.legacy_dir))
    if args.step in ('scan', 'all'):
        pipeline.scan(ds, args.bbox)
    if args.step in ('details', 'all'):
        pipeline.details(ds)
    if args.step in ('comments', 'all'):
        pipeline.comments(ds, country)
    if args.step in ('ingest', 'all'):
        print(pipeline.ingest(ds, country))
    if args.step == 'seed':
        print(pipeline.export_seed(ds, args.seed_path, country or 'Poland'))
    if args.step == 'status':
        print(
            dict(
                places=len(ds.places),
                details=len(ds.details),
                comments=len(ds.comments),
                cells=len(ds.state.get('cells', [])),
                country=len(ds.ids(country)),
                missing_details=len(ds.missing_details()),
                missing_comments=len(ds.missing_comments()),
                fetched_at=ds.state.get('fetched_at'),
            )
        )


if __name__ == '__main__':
    main()
