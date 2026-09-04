import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_editor_picks.py"
spec = importlib.util.spec_from_file_location("build_editor_picks", MODULE_PATH)
build_editor_picks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_editor_picks)


class BuildEditorPicksTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)

    def test_candidates_are_global_deduplicated_and_exclude_non_events(self):
        channels = [
            {
                "id": "sports-one",
                "name": "Sports One",
                "programs": [
                    self.program("Team A vs Team B", "2026-09-04T18:00:00Z"),
                    self.program("Team A vs Team B", "2026-09-04T18:00:00Z"),
                    self.program("Team A vs Team B", "2026-09-04T20:00:00Z"),
                    self.program("Match highlights", "2026-09-04T19:00:00Z"),
                    self.program("Live: LaLiga", "2026-09-04T19:30:00Z"),
                    self.program("Yesterday's game", "2026-09-04T08:00:00Z", end="2026-09-04T10:00:00Z"),
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.write_country(path, "US", channels)
            self.write_country(path, "FR", [{"id": "sports-fr", "name": "Sport FR", "programs": [self.program("Paris vs Lyon", "2026-09-04T20:00:00Z")]}])

            candidates = build_editor_picks.collect_candidates(path, self.now)

        self.assertEqual({candidate["country"] for candidate in candidates}, {"US", "FR"})
        self.assertEqual([candidate["title"] for candidate in candidates], ["Team A vs Team B", "Paris vs Lyon"])
        self.assertEqual([candidate["id"] for candidate in candidates], ["event-1", "event-2"])

    def test_candidate_cap_keeps_every_country_in_the_global_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            programs = [
                self.program(
                    f"Team {index} vs Team X",
                    (self.now + timedelta(minutes=index)).isoformat().replace("+00:00", "Z"),
                    end="2026-09-05T09:00:00Z",
                )
                for index in range(81)
            ]
            self.write_country(path, "ES", [{"id": "sports-es", "name": "Sport ES", "programs": programs}])
            self.write_country(path, "DE", [{"id": "sports-de", "name": "Sport DE", "programs": [
                self.program("Berlin vs Munich", "2026-09-05T07:00:00Z", end="2026-09-05T08:00:00Z")
            ]}])

            candidates = build_editor_picks.collect_candidates(path, self.now)

        self.assertEqual({candidate["country"] for candidate in candidates}, {"DE", "ES"})

    def test_selection_accepts_only_unique_supplied_ids_within_limit(self):
        candidates = [{"id": f"event-{index}"} for index in range(1, 8)]

        selected = build_editor_picks.validate_selection(json.dumps({"pick_ids": ["event-2", "event-1"]}), candidates)

        self.assertEqual([candidate["id"] for candidate in selected], ["event-2", "event-1"])
        for invalid in (
            '{"pick_ids":["invented"]}',
            '{"pick_ids":["event-1","event-1"]}',
            '{"pick_ids":["event-1","event-2","event-3","event-4","event-5","event-6"]}',
        ):
            with self.assertRaises(ValueError):
                build_editor_picks.validate_selection(invalid, candidates)

    def program(self, title, start, end="2026-09-04T21:00:00Z"):
        return {
            "title": title,
            "description": "Live coverage",
            "categories": ["Sports", "Football"],
            "sportType": "Football",
            "competition": "League",
            "startAt": start,
            "endAt": end,
        }

    def write_country(self, path, country, channels):
        (path / f"premium-{country}.json").write_text(
            json.dumps({"country": country, "countryName": country, "channels": channels}),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
