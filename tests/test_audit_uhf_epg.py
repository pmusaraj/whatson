import unittest
from datetime import timedelta

from scripts.audit_uhf_epg import APPLE_EPOCH, audit


class UhfAuditTest(unittest.TestCase):
    def test_manual_selection_overrides_name_match_and_stale_cache_is_not_current(self):
        cache = {"resolvedNameIds": {"La 1": "ES:La1.es", "TSN": "CA:TSN1.ca"},
                 "programmes": {"ES:La1.es": [{"start": 0, "end": 100, "title": "News"}],
                                "CA:TSN1.ca": [{"start": 0, "end": 10, "title": "Sports"}]}}
        rows = [("Spain", "La 1", "!$!playlist!$!missing"), ("Spain", "La 1", None),
                ("Canada", "TSN", None)]
        report = audit(rows, cache, APPLE_EPOCH + timedelta(seconds=50))
        self.assertEqual(report["countries"]["Spain"], {"playlistRows": 2, "matched": 1, "current": 1, "next24h": 1})
        self.assertEqual(report["countries"]["Canada"], {"playlistRows": 1, "matched": 1, "current": 0, "next24h": 0})


if __name__ == "__main__":
    unittest.main()
