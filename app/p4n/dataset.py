"""Stan pobierania P4N na dysku (data/p4n/): surowe rekordy, szczegóły, komentarze, zrobione komórki siatki.

Wszystkie kroki są wznawialne: to, co już jest na dysku, nie jest pobierane ponownie.
"""

import datetime as dt
import json
from pathlib import Path

from .. import storage as store

FILES = ('places', 'details', 'comments', 'state')


def default_dir():
    return store.DATA / 'p4n'


class Dataset:
    def __init__(self, directory=None):
        self.dir = Path(directory) if directory else default_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.places = self._load('places', {})  # id → rekord z /api/places/around
        self.details = self._load('details', {})  # id → rekord ze starego API (full)
        self.comments = self._load('comments', {})  # id → lista komentarzy z HTML
        self.state = self._load('state', {'cells': [], 'fetched_at': None})

    def _path(self, name):
        return self.dir / f'{name}.json'

    def _load(self, name, default):
        p = self._path(name)
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

    def save(self, *names):
        for name in names or FILES:
            tmp = self._path(name).with_suffix('.json.tmp')
            tmp.write_text(json.dumps(getattr(self, name), ensure_ascii=False), encoding='utf-8')
            tmp.replace(self._path(name))

    def log(self, message):
        line = f'{dt.datetime.now().isoformat(timespec="seconds")} {message}'
        try:
            print(line, flush=True)
        except UnicodeEncodeError:  # konsola Windows bez UTF-8
            print(line.encode('ascii', 'replace').decode(), flush=True)
        with (self.dir / 'p4n.log').open('a', encoding='utf-8') as f:
            f.write(line + '\n')

    # ---- wybór rekordów ----
    def ids(self, country=None):
        return [
            pid for pid, p in self.places.items() if not country or (p.get('address') or {}).get('country') == country
        ]

    def expected_comments(self, pid):
        return int((self.details.get(pid) or {}).get('nb_commentaires') or 0)

    def missing_details(self):
        return [pid for pid in self.places if pid not in self.details]

    def missing_comments(self, country=None):
        return [pid for pid in self.ids(country) if pid not in self.comments and self.expected_comments(pid) > 0]

    def import_legacy(self, directory):
        """Wczytuje pliki starszych skryptów (pn_poludnie_polska*.json, pn_comments.json) bez ponownego pobierania."""
        directory = Path(directory)
        added = dict(places=0, details=0, comments=0)
        for name in ('pn_poludnie_polska_full.json', 'pn_poludnie_polska.json'):
            p = directory / name
            if not p.exists():
                continue
            for r in json.loads(p.read_text(encoding='utf-8')):
                pid = str(r.get('id'))
                full = r.pop('full', None)
                if pid not in self.places:
                    self.places[pid] = r
                    added['places'] += 1
                if full and pid not in self.details:
                    self.details[pid] = full
                    added['details'] += 1
        p = directory / 'pn_comments.json'
        if p.exists():
            for pid, items in json.loads(p.read_text(encoding='utf-8')).items():
                if pid not in self.comments:
                    self.comments[pid] = items
                    added['comments'] += 1
        stamp = directory / 'pn_poludnie_polska_full.json'
        if stamp.exists() and not self.state.get('fetched_at'):
            self.state['fetched_at'] = dt.datetime.fromtimestamp(stamp.stat().st_mtime, dt.timezone.utc).isoformat()
        self.save()
        return added
