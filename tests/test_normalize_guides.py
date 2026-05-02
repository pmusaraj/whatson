import importlib.util
import unittest
from datetime import timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "normalize_guides.py"
spec = importlib.util.spec_from_file_location("normalize_guides", MODULE_PATH)
normalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(normalizer)


class NormalizeGuidesTest(unittest.TestCase):
    def test_parse_xmltv_time_returns_utc_datetime(self):
        value = normalizer.parse_xmltv_time("20260502003500 +0200")

        self.assertEqual(value.tzinfo, timezone.utc)
        self.assertEqual(value.isoformat(), "2026-05-01T22:35:00+00:00")


if __name__ == "__main__":
    unittest.main()
