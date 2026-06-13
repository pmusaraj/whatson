import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

UTILS_PATH = Path(__file__).resolve().parents[1] / "scripts" / "xmltv_utils.py"
utils_spec = importlib.util.spec_from_file_location("xmltv_utils", UTILS_PATH)
assert utils_spec is not None and utils_spec.loader is not None
xmltv_utils = importlib.util.module_from_spec(utils_spec)
sys.modules["xmltv_utils"] = xmltv_utils
utils_spec.loader.exec_module(xmltv_utils)

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_uhf_xmltv.py"
validator_spec = importlib.util.spec_from_file_location("validate_uhf_xmltv", VALIDATOR_PATH)
assert validator_spec is not None and validator_spec.loader is not None
validate_uhf_xmltv = importlib.util.module_from_spec(validator_spec)
sys.modules["validate_uhf_xmltv"] = validate_uhf_xmltv
validator_spec.loader.exec_module(validate_uhf_xmltv)


class XmltvUtilsTest(unittest.TestCase):
    def test_parse_xmltv_time_returns_utc(self):
        value = "20260613123000 -0400"
        parsed = xmltv_utils.parse_xmltv_time(value)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(xmltv_utils.iso_z(parsed), "2026-06-13T16:30:00Z")

    def test_parse_xmltv_time_rejects_empty_value(self):
        with self.assertRaises(ValueError):
            xmltv_utils.parse_xmltv_time("")


class UhfXmltvValidatorTest(unittest.TestCase):
    def write_fixture(self, root: Path, xml_text: str, channels=None, summary=None):
        xml_path = root / "epg.xml"
        xml_path.write_text(xml_text, encoding="utf-8")
        gzip_path = root / "epg.xml.gz"
        with gzip_path.open("wb") as raw_file:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as outfile:
                outfile.write(xml_text.encode("utf-8"))
        channels_path = root / "channels.json"
        channels_path.write_text(
            json.dumps(
                channels
                if channels is not None
                else [
                    {
                        "custom_xmltv_id": "uhf:1",
                        "name": "One",
                        "category": "News",
                        "target_xmltv_id": "One.us",
                        "target_country": "US",
                    }
                ]
            ),
            encoding="utf-8",
        )
        summary_path = root / "summary.json"
        summary_path.write_text(json.dumps(summary or {"generatedAt": "2026-06-13T12:00:00Z"}), encoding="utf-8")
        return xml_path, gzip_path, channels_path, summary_path

    def validate_fixture(self, xml_text: str, *, channels=None, summary=None, now="2026-06-13T12:30:00Z"):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self.write_fixture(Path(tmpdir), xml_text, channels=channels, summary=summary)
            report, preview = validate_uhf_xmltv.validate(
                xml_path=paths[0],
                gzip_path=paths[1],
                channels_path=paths[2],
                summary_path=paths[3],
                now=validate_uhf_xmltv.parse_iso_datetime(now),
            )
        return report, preview

    def test_validate_minimal_xmltv_reports_counts(self):
        report, preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>News</title></programme>
</tv>
"""
        )

        self.assertEqual(report["counts"]["channels"], 1)
        self.assertEqual(report["counts"]["programmes"], 1)
        self.assertEqual(report["counts"]["errors"], 0)
        self.assertEqual(report["counts"]["channelsWithCurrent"], 1)
        self.assertEqual(preview["channels"][0]["programs"][0]["title"], "News")

    def test_bad_programme_ref_is_error(self):
        report, _preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:999"><title>News</title></programme>
</tv>
"""
        )
        self.assertTrue(any(f["code"] == "programme.unknown_channel" for f in report["findings"]))
        self.assertEqual(report["counts"]["errors"], 1)

    def test_invalid_time_range_is_error(self):
        report, _preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613130000 +0000" stop="20260613120000 +0000" channel="uhf:1"><title>Backwards</title></programme>
</tv>
"""
        )
        self.assertTrue(any(f["code"] == "programme.invalid_time_range" for f in report["findings"]))
        self.assertEqual(report["counts"]["errors"], 1)

    def test_channel_without_current_programme_warns(self):
        report, _preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260612120000 +0000" stop="20260612130000 +0000" channel="uhf:1"><title>Old</title></programme>
</tv>
"""
        )
        self.assertTrue(any(f["code"] == "channel.no_current_programme" for f in report["findings"]))
        self.assertTrue(any(f["code"] == "channel.no_next_24h" for f in report["findings"]))

    def test_duplicate_and_placeholder_titles_warn(self):
        report, _preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>No events</title></programme>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>No events</title></programme>
</tv>
"""
        )
        self.assertTrue(any(f["code"] == "programme.duplicate_exact_slot" for f in report["findings"]))
        self.assertTrue(any(f["code"] == "programme.placeholder_title" for f in report["findings"]))

    def test_same_slot_different_title_warns(self):
        report, _preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>News</title></programme>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>Sports</title></programme>
</tv>
"""
        )
        self.assertTrue(any(f["code"] == "programme.same_slot_different_title" for f in report["findings"]))

    def test_empty_xmltv_is_error(self):
        report, _preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z"></tv>
""",
            channels=[],
        )
        self.assertTrue(any(f["code"] == "xmltv.no_channels" for f in report["findings"]))
        self.assertTrue(any(f["code"] == "xmltv.no_programmes" for f in report["findings"]))
        self.assertEqual(report["counts"]["errors"], 2)

    def test_gzip_content_mismatch_is_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>News</title></programme>
</tv>
"""
            xml_path, gzip_path, channels_path, summary_path = self.write_fixture(root, xml_text)
            gzip_text = xml_text.replace("<title>News</title>", "<title>Different</title>")
            with gzip_path.open("wb") as raw_file:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as outfile:
                    outfile.write(gzip_text.encode("utf-8"))

            report, _preview = validate_uhf_xmltv.validate(
                xml_path=xml_path,
                gzip_path=gzip_path,
                channels_path=channels_path,
                summary_path=summary_path,
                now=validate_uhf_xmltv.parse_iso_datetime("2026-06-13T12:30:00Z"),
            )

        self.assertTrue(any(f["code"] == "gzip.content_mismatch" for f in report["findings"]))
        self.assertEqual(report["counts"]["errors"], 1)

    def test_channels_json_mismatch_warns(self):
        report, _preview = self.validate_fixture(
            """<?xml version="1.0" encoding="UTF-8"?>
<tv date="2026-06-13T12:00:00Z">
  <channel id="uhf:1"><display-name>One</display-name></channel>
  <programme start="20260613120000 +0000" stop="20260613130000 +0000" channel="uhf:1"><title>News</title></programme>
</tv>
""",
            channels=[{"custom_xmltv_id": "uhf:2", "name": "Two"}],
        )
        self.assertTrue(any(f["code"] == "mapping.channel_missing_from_xml" for f in report["findings"]))
        self.assertTrue(any(f["code"] == "mapping.xml_channel_missing_from_channels_json" for f in report["findings"]))


if __name__ == "__main__":
    unittest.main()
