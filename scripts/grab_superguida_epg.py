#!/usr/bin/env python3
"""Read Super Guida TV's current HTML schedule and its published durations."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

ROME = ZoneInfo('Europe/Rome')


class ScheduleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.fields = None
        self.text = None

    def handle_starttag(self, tag, attrs):
        if tag == 'li':
            self.fields = []
        elif tag == 'p' and self.fields is not None:
            self.text = ''

    def handle_data(self, data):
        if self.text is not None:
            self.text += data

    def handle_endtag(self, tag):
        if tag == 'p' and self.text is not None:
            self.fields.append(' '.join(self.text.split()))
            self.text = None
        elif tag == 'li' and self.fields is not None:
            if len(self.fields) >= 3 and re.fullmatch(r'\d{2}:\d{2}', self.fields[0]):
                self.entries.append(self.fields[:3])
            self.fields = None
            self.text = None


def parse_schedule(html, day):
    parser = ScheduleParser()
    parser.feed(html)
    result = []
    for clock, title, category in parser.entries:
        if not title:
            continue
        hour, minute = map(int, clock.split(':'))
        start = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute, tzinfo=ROME).astimezone(timezone.utc)
        if result and start < result[-1]['start']:
            folded = start.astimezone(ROME).replace(fold=1).astimezone(timezone.utc)
            if folded > result[-1]['start']:
                start = folded
            else:
                day += timedelta(days=1)
                start = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute, tzinfo=ROME).astimezone(timezone.utc)
        duration = re.search(r"\((\d+)[’']\)", category)
        stop = start + timedelta(minutes=int(duration[1])) if duration else None
        result.append(dict(title=title, start=start, stop=stop, category=category.split('(')[0].strip()))
    for entry, following in zip(result, result[1:]):
        if entry['stop'] is None:
            entry['stop'] = following['start']
    result = [entry for entry in result if entry['stop'] and entry['stop'] > entry['start']]
    if not result:
        raise ValueError(f'No programmes with known durations for {day}')
    return result


def fetch_schedule(channel, day, today):
    offset = (day - today).days
    if offset not in range(3):
        raise ValueError('Super Guida TV supports today and the next two days')
    slug = ['oggi', 'domani', 'dopodomani'][offset]
    url = f'https://www.superguidatv.it/programmazione-canale/{slug}/guida-programmi-tv-{channel.attrib["site_id"]}/'
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
                return channel.attrib['xmltv_id'], parse_schedule(response.read().decode('utf-8'), day)
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def fetch_result(job):
    channel, day, today = job
    try:
        return fetch_schedule(channel, day, today)
    except (OSError, ValueError) as error:
        print(f"Skipping {channel.attrib['xmltv_id']} on {day}: {error}", flush=True)
        return channel.attrib['xmltv_id'], None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--days', type=int, default=3)
    args = parser.parse_args()
    if args.days not in range(1, 4):
        parser.error('--days must be between 1 and 3')
    today = datetime.now(ROME).date()
    channels = ET.parse(args.channels).getroot()
    if any(not channel.get("xmltv_id") for channel in channels):
        raise ValueError("Every selected channel needs a nonempty XMLTV ID")
    jobs = [(channel, today + timedelta(days=offset), today) for channel in channels for offset in range(args.days)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        pages = list(pool.map(fetch_result, jobs))
    failed = {channel_id for channel_id, entries in pages if entries is None}
    root = ET.Element('tv', {'generator-info-name': 'heywhatson.tv Super Guida TV'})
    for channel in channels:
        if channel.attrib['xmltv_id'] in failed:
            continue
        ET.SubElement(ET.SubElement(root, 'channel', id=channel.attrib['xmltv_id']), 'display-name', lang='it').text = channel.text
    seen = set()
    for channel_id, entries in pages:
        if channel_id in failed:
            continue
        for entry in entries:
            key = (channel_id, entry['start'], entry['stop'])
            if key in seen:
                continue
            seen.add(key)
            programme = ET.SubElement(root, 'programme', channel=channel_id, start=entry['start'].strftime('%Y%m%d%H%M%S %z'), stop=entry['stop'].strftime('%Y%m%d%H%M%S %z'))
            ET.SubElement(programme, 'title', lang='it').text = entry['title']
            if entry['category']:
                ET.SubElement(programme, 'category', lang='it').text = entry['category']
    if not seen:
        raise ValueError('No programmes to publish')
    ET.indent(root, space='  ')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.xml.tmp')
    ET.ElementTree(root).write(temporary, encoding='utf-8', xml_declaration=True)
    temporary.replace(args.output)
    print(f'Super Guida TV: {len(jobs)} pages, {len(seen)} programmes')


if __name__ == '__main__':
    main()
