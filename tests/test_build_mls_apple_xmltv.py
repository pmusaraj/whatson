import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_mls_apple_xmltv.py"
spec = importlib.util.spec_from_file_location("build_mls_apple_xmltv", MODULE_PATH)
assert spec and spec.loader
build_mls_apple_xmltv = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = build_mls_apple_xmltv
spec.loader.exec_module(build_mls_apple_xmltv)


class BuildMlsAppleXmltvTest(unittest.TestCase):
    def test_normalize_matches_keeps_only_apple_tv_matches(self):
        rows = [
            {
                "competition_id": "MLS-COM-000001",
                "match_id": "MLS-MAT-1",
                "planned_kickoff_time": "2026-05-23T23:30:00Z",
                "home_team_name": "FC Cincinnati",
                "away_team_name": "Orlando City",
                "competition_label": "MLS Regular Season 2026",
                "stadium_name": "TQL Stadium",
                "stadium_city": "Cincinnati, OH",
            },
            {
                "competition_id": "MLS-COM-000001",
                "match_id": "MLS-MAT-2",
                "planned_kickoff_time": "2026-05-24T00:30:00Z",
                "home_team_name": "Not",
                "away_team_name": "Apple",
            },
        ]
        details = {
            "MLS-MAT-1": {
                "appleStreamURL": "https://tv.apple.com/us/sporting-event/example",
                "broadcasters": [{"broadcasterName": "Apple TV"}],
                "home": {"logoColorUrl": "https://images.example/{formatInstructions}/home.png"},
            },
            "MLS-MAT-2": {"broadcasters": [{"broadcasterName": "Cable TV"}]},
        }

        matches = build_mls_apple_xmltv.normalize_matches(rows, details)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_id, "MLS-MAT-1")
        self.assertEqual(matches[0].title, "FC Cincinnati vs Orlando City")
        self.assertEqual(matches[0].start.isoformat(), "2026-05-23T23:30:00+00:00")
        self.assertEqual(matches[0].stop.isoformat(), "2026-05-24T02:00:00+00:00")
        self.assertIn("Watch on Apple TV", matches[0].description)
        self.assertEqual(matches[0].image_url, "https://images.example/w_400,h_400,c_fit,q_auto,f_png/home.png")

    def test_build_xml_keeps_overlapping_matches_on_one_virtual_channel(self):
        match = build_mls_apple_xmltv.Match
        matches = [
            match(
                "A",
                "Team A vs Team B",
                "MLS",
                datetime(2026, 5, 23, 23, 30, tzinfo=timezone.utc),
                datetime(2026, 5, 24, 2, 0, tzinfo=timezone.utc),
                "Watch on Apple TV",
            ),
            match(
                "B",
                "Team C vs Team D",
                "MLS",
                datetime(2026, 5, 24, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 24, 2, 30, tzinfo=timezone.utc),
                "Watch on Apple TV",
            ),
            match(
                "C",
                "Team E vs Team F",
                "MLS",
                datetime(2026, 5, 24, 2, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 24, 4, 30, tzinfo=timezone.utc),
                "Watch on Apple TV",
            ),
        ]

        tree = build_mls_apple_xmltv.build_xml(matches, datetime(2026, 5, 23, tzinfo=timezone.utc))

        root = tree.getroot()
        self.assertEqual([channel.attrib["id"] for channel in root.findall("channel")], ["MLSSeasonPass.us"])
        programmes = root.findall("programme")
        self.assertEqual(len(programmes), 3)
        self.assertEqual([programme.attrib["channel"] for programme in programmes], ["MLSSeasonPass.us", "MLSSeasonPass.us", "MLSSeasonPass.us"])
        self.assertEqual(programmes[0].findtext("category"), "Sports")

    def test_write_xml_outputs_parseable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mls.xml"
            tree = build_mls_apple_xmltv.build_xml([], datetime(2026, 5, 23, tzinfo=timezone.utc))
            build_mls_apple_xmltv.write_xml(path, tree)
            self.assertEqual(ET.parse(path).getroot().tag, "tv")


if __name__ == "__main__":
    unittest.main()
