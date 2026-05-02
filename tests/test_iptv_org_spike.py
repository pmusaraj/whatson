import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "iptv_org_spike.py"
spec = importlib.util.spec_from_file_location("iptv_org_spike", MODULE_PATH)
spike = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spike)


class IptvOrgSpikeTest(unittest.TestCase):
    def test_normalize_xmltv_id_removes_feed_suffix(self):
        self.assertEqual(spike.normalize_xmltv_id("France2.fr@SD"), "France2.fr")

    def test_normalize_xmltv_id_handles_empty_values(self):
        self.assertIsNone(spike.normalize_xmltv_id(""))
        self.assertIsNone(spike.normalize_xmltv_id(None))

    def test_display_channel_keeps_only_stable_fields(self):
        channel = {
            "id": "TF1.fr",
            "name": "TF1",
            "country": "FR",
            "categories": ["general"],
            "network": "TF1 Group",
            "website": "https://example.com",
            "raw": "ignored",
        }

        self.assertEqual(
            spike.display_channel(channel),
            {
                "id": "TF1.fr",
                "name": "TF1",
                "country": "FR",
                "categories": ["general"],
                "network": "TF1 Group",
                "website": "https://example.com",
            },
        )


if __name__ == "__main__":
    unittest.main()
