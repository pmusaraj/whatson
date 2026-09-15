import unittest
from datetime import date, datetime, timezone
from scripts.grab_superguida_epg import parse_schedule


def page(*rows):
    return '<ul>' + ''.join('<li><span>' + ''.join(f'<p>{text}</p>' for text in row) + '</span></li>' for row in rows) + '</ul>'


class SuperGuidaTest(unittest.TestCase):
    def test_current_layout_preserves_title_duration_and_midnight(self):
        rows = parse_schedule(page(('23:50', 'Film &amp; friends', "Film (30&#39;)"),
                                   ('00:20', 'News', "Notizie (10')")), date(2026, 9, 15))
        self.assertEqual(rows[0]['title'], 'Film & friends')
        self.assertEqual(rows[0]['stop'], datetime(2026, 9, 15, 22, 20, tzinfo=timezone.utc))
        self.assertEqual(rows[1]['start'], rows[0]['stop'])

    def test_missing_final_duration_is_not_invented(self):
        rows = parse_schedule(page(('10:00', 'First', 'News'), ('10:15', 'Last', 'News')), date(2026, 9, 15))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['stop'] - rows[0]['start']).total_seconds(), 900)

    def test_autumn_clock_repetition_stays_on_same_date(self):
        rows = parse_schedule(page(('02:50', 'First', "Film (20')"), ('02:10', 'Second', "Film (20')")), date(2026, 10, 25))
        self.assertEqual((rows[1]['start'] - rows[0]['start']).total_seconds(), 1200)

    def test_error_page_fails_instead_of_producing_empty_guide(self):
        with self.assertRaises(ValueError):
            parse_schedule('<html>Unavailable</html>', date(2026, 9, 15))

    def test_failed_channel_is_excluded_and_total_failure_preserves_snapshot(self):
        import sys
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from xml.etree import ElementTree as ET
        from scripts import grab_superguida_epg as grabber
        entry = parse_schedule(page(('10:00', 'Good', "News (30')")), date(2026, 9, 15))[0]
        with tempfile.TemporaryDirectory() as tmp:
            channels = Path(tmp) / 'channels.xml'
            output = Path(tmp) / 'guide.xml'
            channels.write_text('<channels><channel xmltv_id="good" site_id="1">Good</channel><channel xmltv_id="bad" site_id="2">Bad</channel></channels>')
            argv = ['grab', '--channels', str(channels), '--output', str(output), '--days', '1']
            with patch.object(sys, 'argv', argv), patch.object(grabber, 'fetch_result', side_effect=[('good', [entry]), ('bad', None)]):
                grabber.main()
            root = ET.parse(output).getroot()
            self.assertEqual([c.get('id') for c in root.findall('channel')], ['good'])
            before = output.read_bytes()
            with patch.object(sys, 'argv', argv), patch.object(grabber, 'fetch_result', side_effect=[('good', None), ('bad', None)]):
                with self.assertRaises(ValueError):
                    grabber.main()
            self.assertEqual(output.read_bytes(), before)
