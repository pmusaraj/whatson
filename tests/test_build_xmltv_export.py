import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
MODULE_PATH = SCRIPTS_DIR / "build_xmltv_export.py"
spec = importlib.util.spec_from_file_location("build_xmltv_export", MODULE_PATH)
assert spec is not None and spec.loader is not None
build_xmltv_export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_xmltv_export)


class BuildXmltvExportTest(unittest.TestCase):
    def test_ingest_merges_normal_and_premium_same_raw_channel_into_global_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            normal = root / "normal.xml"
            premium = root / "premium.xml"
            normal.write_text(
                """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<tv>
  <channel id=\"Sport.fr\"><display-name>Canal+ Sport</display-name><icon src=\"https://example.com/logo.png\" /></channel>
  <programme start=\"20260502120000 +0000\" stop=\"20260502130000 +0000\" channel=\"Sport.fr\"><title>Live match</title><desc>First source</desc><category>Football</category></programme>
</tv>
""",
                encoding="utf-8",
            )
            premium.write_text(
                """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<tv>
  <channel id=\"Sport.fr\"><display-name>Canal+ Sport HD</display-name></channel>
  <programme start=\"20260502120000 +0000\" stop=\"20260502130000 +0000\" channel=\"Sport.fr\"><title>Duplicate match</title></programme>
  <programme start=\"20260502130000 +0000\" stop=\"20260502140000 +0000\" channel=\"Sport.fr\"><title>Postgame</title><sub-title>Highlights</sub-title></programme>
</tv>
""",
                encoding="utf-8",
            )

            channels = {}
            programmes_by_channel = {}
            build_xmltv_export.ingest_export_guide(
                "FR",
                build_xmltv_export.build_web_data.LocalGuide(normal, "Normal", "normal"),
                channels,
                programmes_by_channel,
                set(),
                False,
            )
            build_xmltv_export.ingest_export_guide(
                "FR",
                build_xmltv_export.build_web_data.LocalGuide(premium, "Premium", "premium"),
                channels,
                programmes_by_channel,
                set(),
                True,
            )

        self.assertEqual(list(channels), ["FR:Sport.fr"])
        self.assertEqual(channels["FR:Sport.fr"]["providers"], ["Normal", "Premium"])
        self.assertEqual(len(programmes_by_channel["FR:Sport.fr"]), 2)
        self.assertEqual(programmes_by_channel["FR:Sport.fr"][0]["title"], "Live match")
        self.assertEqual(programmes_by_channel["FR:Sport.fr"][1]["subtitle"], "Highlights")

    def test_build_xmltv_tree_emits_channels_programmes_and_metadata(self):
        channels = {
            "FR:Sport.fr": {
                "id": "FR:Sport.fr",
                "rawId": "Sport.fr",
                "country": "FR",
                "countryName": "France",
                "name": "Canal+ Sport",
                "logoUrl": "https://example.com/logo.png",
                "providers": ["Normal"],
                "sources": ["normal.xml"],
            }
        }
        programmes_by_channel = {
            "FR:Sport.fr": [
                {
                    "title": "Live match",
                    "subtitle": "Final",
                    "description": "A match",
                    "categories": ["Football"],
                    "imageUrl": "https://example.com/match.jpg",
                    "start": "20260502120000 +0000",
                    "stop": "20260502130000 +0000",
                    "startAt": "2026-05-02T12:00:00Z",
                    "endAt": "2026-05-02T13:00:00Z",
                }
            ]
        }

        tree = build_xmltv_export.build_xmltv_tree(channels, programmes_by_channel, ["normal.xml"])
        xml = ET.tostring(tree.getroot(), encoding="unicode")

        self.assertIn('generator-info-name="heywhatson.tv"', xml)
        self.assertIn('<channel id="FR:Sport.fr">', xml)
        self.assertIn('<display-name>Canal+ Sport</display-name>', xml)
        self.assertIn('<programme channel="FR:Sport.fr" start="20260502120000 +0000" stop="20260502130000 +0000">', xml)
        self.assertIn('<title>Live match</title>', xml)
        self.assertIn('<category>Football</category>', xml)
        self.assertIn('<icon src="https://example.com/match.jpg" />', xml)


if __name__ == "__main__":
    unittest.main()
