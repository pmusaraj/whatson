import unittest
from xml.etree import ElementTree as ET

from scripts.grab_orange_epg import build_guide, xmltv_time


class OrangeGuideTest(unittest.TestCase):
    def test_shared_segments_keep_channels_separate_and_deduplicate_boundaries(self):
        channels = ET.fromstring('<channels><channel site_id="1" xmltv_id="La1.es">La 1</channel>'
                                 '<channel site_id="2" xmltv_id="La2.es">La 2</channel></channels>')
        def listing(channel_id, title):
            return {"channelExternalId": channel_id, "programs": [{
                "name": title, "startDate": 1789488000000, "endDate": 1789491600000,
                "description": "News & culture", "genres": [{"name": "News"}],
            }]}
        first = [listing("1", "First"), listing("2", "Second"), listing("3", "Unselected")]
        root = build_guide(channels, [first, first]).getroot()
        self.assertEqual([(p.get("channel"), p.findtext("title")) for p in root.findall("programme")],
                         [("La1.es", "First"), ("La2.es", "Second")])
        self.assertEqual(root.find("programme").get("stop"), "20260915170000 +0000")
        self.assertEqual(root.find("programme/desc").text, "News & culture")

    def test_empty_results_fail_instead_of_publishing_empty_guide(self):
        with self.assertRaises(ValueError):
            build_guide(ET.fromstring('<channels/>'), [[]])

    def test_offsets_and_milliseconds_convert_to_utc(self):
        self.assertEqual(xmltv_time("2026-09-15T23:00:00+02:00"), xmltv_time(1789506000000))


if __name__ == "__main__":
    unittest.main()
