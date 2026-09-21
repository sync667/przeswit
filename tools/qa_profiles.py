"""Kontrola jakości profili AI w bazie: metryki zbiorcze + reguły podejrzeń (do porównywania wersji promptu).

Użycie:  python tools/qa_profiles.py [--data data] [--out raport.md] [--sample 15]
Baza otwierana tylko do odczytu. Wynik: Markdown (na stdout albo do pliku).
"""

import argparse
import collections
import json
import random
import re
import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.profiles import METRIC_FEATURES, as_ai  # noqa: E402

PLACEHOLDER = re.compile(r'(description|comment|photo|evidence|metadata|geo|name):\w')
FREE_WORDS = re.compile(r'free|gratuit|kostenlos|bezp[łl]atn|za darmo|darmow', re.I)
PHOTO_ONLY = lambda o: all(str(e).startswith('photo:') for e in o.get('evidence', []))  # noqa: E731


def load(data_dir):
    db = sqlite3.connect(f'file:{Path(data_dir) / "scout.sqlite3"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    places = {r['key']: json.loads(r['body']) for r in db.execute('select key,body from places')}
    profiles = {
        r['key']: json.loads(r['body']) for r in db.execute("select key,body from profiles where status='ready'")
    }
    return places, profiles


def text_of(p):
    return ' '.join(
        [p.get('description', ''), p.get('name', '')] + [c.get('text', '') for c in p.get('comments', [])]
    ).lower()


def rules(key, p, prof):
    obs = {o['feature']: o for o in prof.get('observations', [])}
    hits = []
    for f in ('tent_space', 'moto_adjacent'):
        o = obs.get(f)
        if o and PHOTO_ONLY(o) and o['confidence'] >= 60 and o['score'] >= 70:
            hits.append('R1 namiot/moto tylko ze zdjęcia')
            break
    if obs.get('lake', {}).get('score', 0) >= 80 and obs.get('river', {}).get('score', 0) >= 80:
        hits.append('R2 jezioro i rzeka naraz')
    if (
        obs.get('free_cost', {}).get('score', 0) >= 80
        and not FREE_WORDS.search(text_of(p))
        and not (p.get('raw') or {}).get('full', {}).get('prix_stationnement') == 'gratuit'
    ):
        hits.append('R3 bezpłatność bez wzmianki')
    if any(f in obs and PHOTO_ONLY(obs[f]) for f in ('sunset', 'sunrise')):
        hits.append('R4 zachód/wschód tylko ze zdjęcia')
    if any(f in obs and PHOTO_ONLY(obs[f]) and obs[f]['score'] >= 80 for f in ('quiet', 'low_crowds')):
        hits.append('R5 cisza/tłumy tylko ze zdjęcia')
    geo = p.get('geo', {})
    if any(f in obs and obs[f]['score'] >= 60 for f in ('toilet', 'drinking_water')) and not any(
        k in geo for k in ('p4n_wc_public', 'p4n_point_eau')
    ):
        hits.append('R6 udogodnienie bez flagi źródła')
    closure = (p.get('raw') or {}).get('full', {}).get('date_fermeture')
    if (
        closure
        and closure not in ('all_year', '0', '')
        and not any('zamkn' in w.lower() or 'sezon' in w.lower() for w in prof.get('warnings', []))
    ):
        hits.append('R7 sezonowość bez ostrzeżenia')
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    ap.add_argument('--out')
    ap.add_argument('--sample', type=int, default=15)
    args = ap.parse_args()
    places, profiles = load(args.data)
    if not profiles:
        sys.exit('Brak gotowych profili.')
    n_obs, leaks, conf_low, cov, metrics, sources = (
        [],
        0,
        0,
        collections.Counter(),
        collections.Counter(),
        collections.Counter(),
    )
    flagged = collections.defaultdict(list)
    for key, prof in profiles.items():
        p = places.get(key)
        if not p:
            continue
        cov[prof.get('coverage', '?')] += 1
        n_obs.append(len(prof.get('observations', [])))
        leaks += sum(1 for f in ('warnings', 'unknown', 'scenes') for x in prof.get(f, []) if PLACEHOLDER.search(x))
        for o in prof.get('observations', []):
            if o.get('confidence', 0) < 40:
                conf_low += 1
            for e in o.get('evidence', []):
                sources[str(e).split(':')[0]] += 1
        ai = as_ai(dict(status='ready', profile=prof))
        for m, v in ai['scores'].items() if ai else []:
            if v is not None:
                metrics[m] += 1
        for hit in rules(key, p, prof):
            flagged[hit].append(key)
    total = len(n_obs)
    lines = [
        f'# QA profili — {total} gotowych',
        '',
        f'- pokrycie: {dict(cov)}',
        f'- obserwacje/profil: min {min(n_obs)}, mediana {statistics.median(n_obs):.0f}, max {max(n_obs)}; pewność < 40: {conf_low}',
        f'- źródła evidence: {dict(sources.most_common())}',
        f'- wycieki identyfikatorów w tekstach: {leaks}',
        '- metryki kart: ' + ', '.join(f'{m} {metrics[m]}/{total}' for m in METRIC_FEATURES),
        '',
        '## Reguły podejrzeń',
    ]
    for rule, keys in sorted(flagged.items()):
        lines.append(f'- **{rule}**: {len(keys)} — ' + ', '.join(keys[:12]) + (' …' if len(keys) > 12 else ''))
    random.seed(42)
    sample = random.sample(sorted(profiles), min(args.sample, len(profiles)))
    lines += ['', f'## Próbka do przeglądu ręcznego (seed 42, {len(sample)})'] + [f'- {k}' for k in sample]
    report = '\n'.join(lines) + '\n'
    if args.out:
        Path(args.out).write_text(report, encoding='utf-8')
        print(f'zapisano {args.out}')
    else:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        print(report)


if __name__ == '__main__':
    main()
