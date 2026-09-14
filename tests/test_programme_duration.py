import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from scripts import build_uhf_custom_xmltv as uhf, build_web_data as web


class ProgrammeDurationTest(unittest.TestCase):
    def test_both_exports_skip_below_five_minutes(self):
        root = ET.Element("tv")
        ET.SubElement(ET.SubElement(root, "channel", id="Test.fr"), "display-name").text = "Test"
        start = datetime(2026, 9, 14, tzinfo=timezone.utc)
        for index, seconds in enumerate((-1, 0, 299, 300, 301)):
            begin = start + timedelta(hours=index)
            programme = ET.SubElement(root, "programme", channel="Test.fr",
                start=begin.strftime("%Y%m%d%H%M%S %z"),
                stop=(begin + timedelta(seconds=seconds)).strftime("%Y%m%d%H%M%S %z"))
            ET.SubElement(programme, "title").text = str(seconds)
        programs = {}
        web.ingest_xmltv_root(root, "test", "test", "test", {}, programs, set(), False)
        self.assertEqual([p["title"] for p in programs["test:Test.fr"]], ["300", "301"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "guide-uhf-FR-test.xml"
            ET.ElementTree(root).write(path)
            with patch.object(uhf, "ROOT", Path(tmp)), patch.object(uhf, "source_xml_files", return_value=[path]):
                _, programmes, _ = uhf.source_epg_indexes()
            self.assertEqual([p.findtext("title") for p in programmes["FR:Test.fr"]], ["300", "301"])


if __name__ == "__main__":
    unittest.main()
