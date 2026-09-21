import threading
import uuid

from . import storage as store
from .core import area_parse
from .providers import check_area, fetch_bdl, fetch_osm, now
from .public_web import fetch_p4n

LOCK = threading.Lock()


def parse_areas(text, radius=40):
    if not isinstance(text, str):
        raise ValueError('Obszary muszą być tekstem.')
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if not 1 <= len(lines) <= 10:
        raise ValueError('Podaj 1–10 obszarów, po jednym w wierszu.')
    return [area_parse(x, radius) for x in lines]


def start(text, radius, sources):
    areas = parse_areas(text, radius)
    for a in areas:
        check_area(a)
    if not isinstance(sources, list) or not sources or any(s not in ('osm', 'bdl', 'p4n') for s in sources):
        raise ValueError('Wybierz dostępne źródło automatyczne.')
    if not LOCK.acquire(blocking=False):
        raise ValueError('Import już trwa. Poczekaj na zakończenie.')
    job = dict(
        id=uuid.uuid4().hex,
        status='running',
        started=now(),
        message='Przygotowuję import…',
        reports=[],
        progress=0,
        total=len(areas) * len(set(sources)),
    )
    store.save_job(job)
    store.set_setting('last_area', dict(areas=text, radius=radius))

    def run():
        try:
            for i, a in enumerate(areas):
                for source in dict.fromkeys(sources):

                    def progress(message):
                        job['message'] = f'Obszar {i + 1}/{len(areas)} · ' + message
                        store.save_job(job)

                    try:
                        places, report = ({'osm': fetch_osm, 'bdl': fetch_bdl, 'p4n': fetch_p4n}[source])(a, progress)
                        report['saved'] = store.upsert(places)
                        report['area'] = a
                    except Exception as e:
                        report = dict(provider=source, status='error', message=str(e), area=a)
                    job['reports'].append(report)
                    job['progress'] += 1
                    store.save_job(job)
            statuses = [x['status'] for x in job['reports']]
            job['status'] = (
                'complete'
                if all(s == 'ok' for s in statuses)
                else 'failed'
                if all(s == 'error' for s in statuses)
                else 'partial'
            )
            job['message'] = 'Import zakończony. Sprawdź raport źródeł.'
            job['finished'] = now()
        except Exception as e:
            job.update(status='failed', message=str(e))
        finally:
            store.save_job(job)
            LOCK.release()

    threading.Thread(target=run, daemon=True).start()
    return job
