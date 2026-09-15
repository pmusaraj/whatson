import unittest
from scripts.build_uhf_grab_lists import choose_mapping
from scripts.build_uhf_channel_mapping import load_targets, map_row


class FeedSelectionTest(unittest.TestCase):
    def test_us_prefers_working_domestic_source_and_eastern_feed(self):
        candidates = [dict(channel='HBO.us', site=site, feed=feed)
                      for site, feed in [('tvtv.us', 'East'), ('tvpassport.com', 'East'),
                                         ('tvpassport.com', 'West')]]
        self.assertEqual(choose_mapping('US', candidates), candidates[1])
        self.assertIsNone(choose_mapping('US', [dict(site='mi.tv', feed='LatinAmerica')]))

    def test_bbc_region_does_not_depend_on_mapping_order(self):
        candidates = [dict(channel='BBCOne.uk', site='virgintvgo.virginmedia.com', feed=feed)
                      for feed in ['LondonHD', 'WalesHD']]
        self.assertEqual(choose_mapping('UK', candidates), candidates[0])

    def test_distinct_channels_do_not_receive_parent_or_foreign_schedules(self):
        targets, raw, _ = load_targets()
        cases = [('USA', 'Disney JNR', 'US:DisneyJunior.us'),
                 ('USA', 'USA- CINEMAX MOVIEMAX', 'US:MovieMax.us'),
                 ('USA', 'USA-SYFY', 'US:SYFY.us'),
                 ('UK', 'UK-Discovery Investigation', 'UK:InvestigationDiscovery.uk'),
                 ('UK', 'UK-Discovery Science', 'UK:DiscoveryScienceEurope.uk'),
                 ('UK', 'UK-Disney Junior', ''),
                 ('USA', 'US-Russia Today USA', '')]
        for category, name, expected in cases:
            with self.subTest(name=name):
                result = map_row(dict(uhf_pk='1', category=category, name=name, original_name=name), targets, raw)
                self.assertEqual(result['target_xmltv_id'], expected)

    def test_export_ignores_obsolete_us_snapshot_without_deleting_it(self):
        import tempfile
        import json
        from pathlib import Path
        from unittest.mock import patch
        from scripts import build_uhf_custom_xmltv as exporter
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data/uhf').mkdir(parents=True)
            (root / 'data/uhf/grab-plan.json').write_text(json.dumps({'writtenFiles': [
                {'path': 'data/sources/iptv-org/custom-uhf-US-tvpassport.com.channels.xml'}]}))
            active = root / 'guide-uhf-US-tvpassport.com.xml'
            obsolete = root / 'guide-uhf-US-tvtv.us.xml'
            active.touch()
            obsolete.touch()
            with patch.object(exporter, 'ROOT', root), patch.object(exporter, 'NORMALIZED_DIR', root):
                self.assertEqual(exporter.source_xml_files(), [active])
            self.assertTrue(obsolete.exists())
