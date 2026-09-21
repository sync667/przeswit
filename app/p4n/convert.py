"""Konwersja surowych rekordów P4N (around + full + komentarze z HTML) na format importu Prześwitu."""

import datetime as dt
import html as html_mod
import re

from .endpoints import CDN_HOSTS, HOST

CDN_RE = re.compile(r'^https://(' + '|'.join(re.escape(h) for h in CDN_HOSTS) + ')/', re.I)
LICENSE = 'P4N / autorzy treści · prywatny przegląd; prawa do treści zastrzeżone'
FLAG = 'Karta P4N (typ PN, zebrana lokalnie); opinie, zgoda na namiot i dojazd nie są automatycznie potwierdzone.'
FULL_BOOL = (
    'animaux',
    'electricite',
    'wifi',
    'douche',
    'point_eau',
    'poubelle',
    'eau_noire',
    'eau_usee',
    'boulangerie',
    'piscine',
    'laverie',
    'caravaneige',
    'gaz',
    'wc_public',
    'donnees_mobile',
    'moto',
    'point_de_vue',
    'rando',
    'vtt',
    'baignade',
    'eaux_vives',
    'peche',
    'peche_pied',
    'escalade',
    'windsurf',
)
# Dane kontaktowe i identyfikatory użytkowników nigdy nie trafiają do rekordu.
CONTACT = ('tel', 'mail', 'site_internet', 'user_id', 'user', 'utilisateur_creation', 'p4n_user_id', 'contact_visible')
TAG_RE = re.compile(r'<[^>]+>')

# Komentarze ze strony HTML
ARTICLE_RE = re.compile(r'<article class="place-feedback-article"(?P<attrs>[^>]*)>(?P<body>.*?)</article>', re.S)
ID_RE = re.compile(r'data-review-id="(\d+)"')
RATING_RE = re.compile(r'data-review-rating="(\d+)"')
AUTHOR_RE = re.compile(r'<a href="/[a-z]{2}/user/([^"]*)"><strong>(.*?)</strong></a>', re.S)
DATE_RE = re.compile(r'<span class="caption text-gray">\s*(\d{2}/\d{2}/\d{4})\s*</span>')
CONTENT_RE = re.compile(r'<p class="place-feedback-article-content">(.*?)</p>', re.S)
AVERAGE_RE = re.compile(r'place-feedback-average[^<]*<strong>[^<]*\((\d+)\s+Feedback\)')


def clean(value):
    return html_mod.unescape(TAG_RE.sub(' ', str(value or ''))).replace('\xa0', ' ').strip()


def parse_date(value):
    if not value:
        return None
    m = re.match(r'(\d{4}-\d{2}-\d{2})', str(value))
    if m:
        return m[1]
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return dt.datetime.strptime(str(value)[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_comments(page):
    """Wszystkie komentarze z HTML strony miejsca (bez paginacji serwerowej) + liczba zadeklarowana w nagłówku sekcji."""
    start = page.find('class="place-feedback')
    end = page.find('inner-page-carousel', start if start >= 0 else 0)
    section = page[start:end] if start >= 0 and end > start else page
    out, seen = [], set()
    for m in ARTICLE_RE.finditer(section):
        attrs, body = m['attrs'], m['body']
        rid = ID_RE.search(attrs)
        rid = rid[1] if rid else None
        if rid in seen:
            continue
        seen.add(rid)
        rating, author, date, content = (
            RATING_RE.search(attrs),
            AUTHOR_RE.search(body),
            DATE_RE.search(body),
            CONTENT_RE.search(body),
        )
        out.append(
            dict(
                id=rid,
                rating=int(rating[1]) if rating else None,
                author=clean(author[2]) if author else None,
                date=parse_date(date[1]) if date else None,
                text=clean(content[1]) if content else '',
            )
        )
    declared = AVERAGE_RE.search(section)
    return out, (int(declared[1]) if declared else None)


def _flatten(value):
    if isinstance(value, dict):
        for k in ('link_large', 'lien', 'url', 'link', 'link_thumb', 'src', 'photo', 'commentaire', 'text'):
            if value.get(k):
                return value[k]
        return ''
    return value or ''


def photos_from(basic, full, url):
    seen, out = set(), []

    def add(link):
        link = _flatten(link)
        if isinstance(link, str) and link.startswith('https://') and link not in seen and CDN_RE.match(link):
            seen.add(link)
            out.append(dict(url=link, caption='Zdjęcie z karty P4N', source_url=url))

    for img in basic.get('images') or []:
        if isinstance(img, dict):
            add(img.get('url') or img.get('thumb'))
    for ph in full.get('photos') if isinstance(full.get('photos'), list) else []:
        add(ph)
    return out


def comments_from(scraped, with_authors=True):
    out = []
    for c in scraped or []:
        if not isinstance(c, dict):
            continue
        text = clean(c.get('text'))
        if not text:
            continue
        entry = dict(text=text, source='p4n')
        if parse_date(c.get('date')):
            entry['date'] = parse_date(c.get('date'))
        if with_authors and c.get('author'):
            entry['author'] = clean(c['author'])
        if c.get('rating') not in (None, ''):
            entry['rating'] = c['rating']
        if c.get('id'):
            entry['id'] = str(c['id'])
        out.append(entry)
    return out


def description_from(basic, full):
    parts = []
    for key in ('description_en', 'description_pl', 'description_de', 'description_fr', 'description'):
        text = clean(full.get(key))
        if text:
            parts.append(text)
            break
    base = clean(basic.get('description'))
    if base and base not in parts and not any(base in p for p in parts):
        parts.append(base)
    return '\n\n'.join(parts)


def convert(basic, full=None, comments=None, fetched_at=None, with_authors=True):
    """Jeden rekord importu (`examples/template.json`) z danych around (+ full ze starego API, + komentarze z HTML)."""
    full = full if isinstance(full, dict) else {}
    pid = str(basic['id'])
    url = f'{HOST}/en/place/{pid}'
    addr = basic.get('address') or {}
    code = (basic.get('type') or {}).get('code')
    name = (
        clean(basic.get('title_short') or basic.get('name') or basic.get('title') or full.get('titre')) or 'P4N ' + pid
    )
    name = re.sub(r'^\(\s*\)\s*[-–]?\s*', '', name).strip(' -–') or 'P4N ' + pid  # pusty kod pocztowy po zdjęciu flagi

    geo = {}
    for k in FULL_BOOL:
        v = full.get(k)
        if v in (None, ''):
            continue
        if str(v) in ('0', '1', 'True', 'False'):
            v = str(v) in ('1', 'True')
        if v is not False:
            geo['p4n_' + k] = v
    acts = basic.get('activities') or []
    if 'point_de_vue' in acts or geo.get('p4n_point_de_vue') is True:
        geo['viewpoint'] = True
    if acts:
        geo['p4n_activities'] = acts
    if basic.get('services'):
        geo['p4n_services'] = basic['services']
    if basic.get('nature_protect') or str(full.get('nature_protect') or '0') not in ('0', 'False'):
        geo['protected_area'] = True

    raw = dict(
        id=basic.get('id'),
        type=code,
        lat=basic.get('lat'),
        lng=basic.get('lng'),
        rating=basic.get('rating'),
        review_count=basic.get('review'),
        photo_count=basic.get('photo'),
        created_at=basic.get('created_at'),
        address=addr,
        nature_protect=basic.get('nature_protect'),
        waiting_validation=basic.get('waiting_validation'),
    )
    if full:
        raw['full'] = {
            k: v
            for k, v in full.items()
            if k not in CONTACT and k not in ('photos', 'commentaires') and not str(k).startswith('description')
        }
    return dict(
        id=pid,
        source='p4n',
        name=name,
        lat=basic.get('lat'),
        lon=basic.get('lng'),
        p4n_url=url,
        source_url=url,
        type='nature',
        source_type=code,
        description=description_from(basic, full),
        comments=comments_from(comments, with_authors),
        photos=photos_from(basic, full, url),
        geo=geo,
        evidence=[],
        source_date=parse_date(basic.get('created_at') or full.get('date_creation')),
        source_rating=basic.get('rating'),
        review_count=basic.get('review'),
        city=addr.get('city') or full.get('ville') or '',
        country=addr.get('country') or full.get('pays') or '',
        license=LICENSE,
        local_only=True,
        extra_flags=[FLAG],
        fetched_at=fetched_at,
        raw=raw,
    )
