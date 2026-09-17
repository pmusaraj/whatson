#!/usr/bin/env python3
"""Collect source links and evaluate reviewed facts for a local series preview."""
import argparse
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from build_series_report import COUNTRIES, ROOT, source_url

BASE = ROOT / 'data/series/discovery'
TOPIC = re.compile(r'seri[eèé]|fiction|drama|review|criti|recens|television|télévision|estren|premier', re.I)
STREAMERS = re.compile(r'\bnetflix\b|prime video|\bamazon\b|apple tv|disney\+|\bhbo\b|\bmax\b|paramount\+', re.I)


def publisher(url, sources, country=None, role=None):
    source_url(url)
    host = urlsplit(url).hostname.lower()
    for source in sources:
        if country and source['country'] != country:
            continue
        if role and source['role'] != role:
            continue
        if any(host == d or host.endswith('.' + d) for d in source['domains']):
            return source
    raise ValueError('Source outside approved country/source list: ' + url)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.href, self.parts = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href, self.parts = dict(attrs).get('href'), []

    def handle_data(self, data):
        if self.href:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.links.append((self.href, ' '.join(' '.join(self.parts).split())))
            self.href, self.parts = None, []


def collect(source):
    result = {'sourceId': source['id'], 'url': source['url'], 'leads': []}
    try:
        request = urllib.request.Request(source['url'], headers={'User-Agent': 'WhatsonDiscovery/0.1'})
        with urllib.request.urlopen(request, timeout=15) as response:
            publisher(response.url, [source])
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError('Source page exceeds 2 MB')
            parser = Links()
            parser.feed(body.decode('utf-8', errors='replace'))
        seen = set()
        for href, title in parser.links:
            url = urljoin(source['url'], href).split('#')[0]
            if len(title) < 18 or not TOPIC.search(title + ' ' + url) or STREAMERS.search(title):
                continue
            try:
                publisher(url, [source])
            except ValueError:
                continue
            if url in seen:
                continue
            seen.add(url)
            result['leads'].append({'title': title[:200], 'url': url})
            if len(result['leads']) == 40:
                break
        result['status'] = 'ok' if result['leads'] else 'no-links'
    except (OSError, ValueError) as error:
        result.update(status='unavailable', error=str(error))
    return result


def evaluate(candidate, as_of, sources):
    c = dict(candidate)
    country = c['country']
    if country not in COUNTRIES:
        raise ValueError('Unsupported country')
    for url in c.get('evidence', {}).values():
        publisher(url, sources, country)
    review = c.get('review')
    if review:
        publisher(review['url'], sources, country, 'review')
    reasons = []
    if c.get('releaseYear') is not None and c['releaseYear'] != as_of.year:
        reasons.append('Series first released before the current year' if c['releaseYear'] < as_of.year else 'Future release year')
    if type(c.get('season')) is int and c['season'] >= 6:
        reasons.append('Season 6 or later')
    if c.get('distribution') == 'streaming-only' or STREAMERS.search(c.get('channel', '')):
        reasons.append('Internet streaming service')
    if c.get('productionCountries') and (country not in c['productionCountries'] or 'US' in c['productionCountries']):
        reasons.append('Not an eligible domestic production')
    day = date.fromisoformat(c['broadcastDate']) if c.get('broadcastDate') else None
    if day and day > as_of:
        reasons.append('Broadcast has not happened yet')
    if reasons:
        return {**c, 'status': 'excluded', 'reasons': reasons}
    required = ('releaseYear', 'season', 'productionCountries', 'channel', 'producer', 'broadcastDate', 'schedule')
    missing = [key for key in required if not c.get(key) or not c.get('evidence', {}).get(key)]
    if c.get('distribution') != 'linear':
        missing.append('verified linear broadcast')
    if type(c.get('season')) is not int or c['season'] < 1:
        missing.append('verified numeric season')
    if not c.get('factsReviewed'):
        missing.append('fact review')
    # A broadcaster-owned page must support the actual broadcast date.
    if day and c.get('evidence', {}).get('broadcastDate'):
        try:
            publisher(c['evidence']['broadcastDate'], sources, country, 'official')
        except ValueError:
            missing.append('official broadcast confirmation')
    if not review or review.get('verdict') not in {'positive', 'mixed', 'negative'}:
        missing.append('independent review')
    if missing:
        return {**c, 'status': 'pending', 'reasons': ['Missing: ' + ', '.join(missing)]}
    if review['verdict'] == 'negative':
        return {**c, 'status': 'not-recommended', 'reasons': ['Available review is unfavorable']}
    age = (as_of - day).days
    tier = 0 if age < 14 else 1 if age < 21 else 2
    return {**c, 'status': 'recent' if tier < 2 else 'fallback', 'recencyTier': tier,
            'reasons': [review['note']]}


def run(candidates, as_of, sources):
    seen = set()
    rows = []
    for c in candidates:
        if c['id'] in seen:
            raise ValueError('Duplicate series ID: ' + c['id'])
        seen.add(c['id'])
        rows.append(evaluate(c, as_of, sources))
    picks = {}
    for country in COUNTRIES:
        eligible = [c for c in rows if c['country'] == country and c['status'] in {'recent', 'fallback'}]
        eligible.sort(key=lambda c: (c['recencyTier'], c['season'] > 2, c['review']['verdict'] != 'positive', c['title']))
        picks[country] = eligible[:5]
    return {'asOf': str(as_of), 'picks': picks, 'candidates': rows}


def render(result):
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>Series discovery — local preview</title><style>body{font:16px/1.5 system-ui;max-width:980px;margin:32px auto;padding:0 20px;color:#25252c}h1{font-size:26px}h2{font-size:21px;margin-top:32px}article{border-top:1px solid #ddd;padding:14px 0}p{margin:4px 0}small{color:#555}a{color:#984127}table{width:100%;border-collapse:collapse}td,th{padding:8px;text-align:left;border-bottom:1px solid #ddd}td{vertical-align:top}</style>',
             f'<h1>Series discovery · {escape(result["asOf"])}</h1>']
    for country, name in COUNTRIES.items():
        parts.append(f'<h2>{name}</h2>')
        for c in result['picks'][country]:
            parts.append(f'<article><strong>{escape(c["title"])}</strong> · Season {c["season"]}<p>{escape(c["channel"])} · {escape(c["schedule"])}</p><p>Production: {escape(c["producer"])}</p><small>{escape(c["status"])} · verified broadcast {escape(c["broadcastDate"])}</small><p>{escape(c["review"]["note"])}</p><a href="{escape(c["evidence"]["broadcastDate"], quote=True)}">Broadcast source</a> · <a href="{escape(c["review"]["url"], quote=True)}">Review</a></article>')
        if not result['picks'][country]:
            parts.append('<p>No verified recommendation in this pass.</p>')
    parts.append('<details open><summary>Other discoveries</summary><table><tr><th>Country</th><th>Series</th><th>Result</th></tr>')
    for c in result['candidates']:
        if c['status'] in {'recent', 'fallback'}:
            continue
        links = ' · '.join(f'<a href="{escape(url, quote=True)}">Source {i}</a>' for i, url in enumerate(dict.fromkeys(c.get('evidence', {}).values()), 1))
        parts.append(f'<tr><td>{c["country"]}</td><td>{escape(c["title"])}<br>{links}</td><td>{escape(c["status"])}: {escape("; ".join(c["reasons"]))}</td></tr>')
    return ''.join(parts) + '</table></details></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true', help='Fetch source indexes; save unverified links, not article bodies')
    parser.add_argument('--input', type=Path, default=BASE / 'first-pass.json')
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.is_relative_to(ROOT.resolve()):
        parser.error('Preview output must be outside the repository')
    sources = json.loads((BASE / 'sources.json').read_text())['sources']
    out.mkdir(parents=True, exist_ok=True)
    if args.collect:
        with ThreadPoolExecutor(max_workers=6) as pool:
            collected = list(pool.map(collect, sources))
        (out / 'leads.json').write_text(json.dumps({'collectedAt': datetime.now(timezone.utc).isoformat(), 'sources': collected}, ensure_ascii=False, indent=2) + '\n')
        for item in collected:
            print(f'{item["sourceId"]}: {item["status"]}, {len(item["leads"])} links')
    data = json.loads(args.input.read_text())
    result = run(data['candidates'], date.fromisoformat(data['asOf']), sources)
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (out / 'index.html').write_text(render(result))
    for c in result['candidates']:
        print(f'{c["country"]}: {c["title"]} — {c["status"]}')


if __name__ == '__main__':
    main()
