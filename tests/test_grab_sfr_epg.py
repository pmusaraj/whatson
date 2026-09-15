import unittest
from xml.etree import ElementTree as ET
from scripts.grab_sfr_epg import build_guide, xmltv_time


class SfrGuideTest(unittest.TestCase):
    def test_channels_stay_separate_and_repeated_events_are_deduplicated(self):
        channels = ET.fromstring('<channels><channel site_id="1" xmltv_id="TF1.fr">TF1</channel><channel site_id="2" xmltv_id="France2.fr">France 2</channel></channels>')
        def listing(title):
            return [dict(title=title, startDate=1789488000000, endDate=1789491600000,
                         longSynopsis='News & culture', genre='News')]
        day = {'1': listing('One'), '2': listing('Two'), '3': listing('Unselected')}
        root = build_guide(channels, [day, day]).getroot()
        programmes = root.findall('programme')
        self.assertEqual([(p.get('channel'), p.findtext('title')) for p in programmes], [('France2.fr', 'Two'), ('TF1.fr', 'One')])
        self.assertEqual(programmes[0].get('stop'), '20260915170000 +0000')
        self.assertEqual(programmes[0].findtext('desc'), 'News & culture')
        self.assertEqual(programmes[0].findtext('category'), 'News')

    def test_empty_results_cannot_replace_a_snapshot(self):
        with self.assertRaises(ValueError):
            build_guide(ET.fromstring('<channels/>'), [{}])

    def test_offsets_convert_to_utc(self):
        self.assertEqual(xmltv_time('2026-09-15T23:00:00+02:00'), xmltv_time(1789506000000))
