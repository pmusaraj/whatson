import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

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
                    self.program("Live: Team A vs Team B", "2026-09-04T18:00:00Z"),
                    self.program("Live: Team A vs Team B", "2026-09-04T18:00:00Z"),
                    {**self.program("Live: Team A vs Team B", "2026-09-04T20:00:00Z"), "description": "Alternate coverage"},
                    self.program("Match highlights", "2026-09-04T19:00:00Z"),
                    self.program("Live: LaLiga", "2026-09-04T19:30:00Z"),
                    self.program("Yesterday's game", "2026-09-04T08:00:00Z", end="2026-09-04T10:00:00Z"),
                ],
            },
            {
                "id": "sports-two",
                "name": "Sports Two",
                "programs": [self.program("Live: Team A vs Team B", "2026-09-04T18:00:10Z")],
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.write_country(path, "US", channels)
            self.write_country(path, "FR", [{"id": "sports-fr", "name": "Sport FR", "programs": [self.program("Live: Paris vs Lyon", "2026-09-04T20:00:00Z")]}])

            candidates = build_editor_picks.collect_candidates(path, self.now)

        self.assertEqual({candidate["country"] for candidate in candidates}, {"US", "FR"})
        self.assertEqual([candidate["title"] for candidate in candidates], ["Live: Team A vs Team B", "Live: Team A vs Team B", "Live: Paris vs Lyon"])
        self.assertEqual(candidates[0]["startAt"], "2026-09-04T18:00:00Z")
        self.assertEqual([candidate["channelName"] for candidate in candidates[:2]], ["Sports One", "Sports Two"])
        self.assertEqual([candidate["id"] for candidate in candidates], ["event-1", "event-2", "event-3"])

    def test_candidate_cap_keeps_every_country_in_the_global_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            programs = [
                {
                    **self.program(
                        f"U.S. Open - Men’s Singles Round {index}",
                        (self.now + timedelta(minutes=index)).isoformat().replace("+00:00", "Z"),
                        end="2026-09-05T09:00:00Z",
                    ),
                    "isNew": True,
                    "subtitle": "Championship match",
                    "originalDate": "2026",
                    "sportType": "Tennis",
                }
                for index in range(10)
            ]
            programs.append({
                **self.program("New nature documentary", "2026-09-05T06:00:00Z", end="2026-09-05T07:00:00Z"),
                "categories": ["Documentary"],
                "originalDate": "2026",
            })
            programs.append({
                **self.program("Festival film premiere", "2026-09-05T07:00:00Z", end="2026-09-05T08:00:00Z"),
                "categories": ["Film"],
                "sportType": None,
                "competition": None,
                "isPremiere": True,
            })
            programs.append({
                **self.program("U.S. Open - Women’s Singles Final", "2026-09-04T20:00:00Z"),
                "categories": [], "sportType": "Tennis", "competition": None,
            })
            self.write_country(path, "ES", [{"id": "sports-es", "name": "Sport ES", "programs": programs}])
            self.write_country(path, "DE", [{"id": "sports-de", "name": "Sport DE", "programs": [
                self.program("Live: Champions Berlin vs Munich", "2026-09-05T07:00:00Z", end="2026-09-05T08:00:00Z"),
                {**self.program("U.S. Open Tennis", "2026-09-05T06:00:00Z", end="2026-09-05T07:00:00Z"), "competition": None, "sportType": "Tennis"},
            ]}])

            candidates = build_editor_picks.collect_candidates(path, self.now)

        self.assertEqual({candidate["country"] for candidate in candidates}, {"DE", "ES"})
        self.assertIn("New nature documentary", [candidate["title"] for candidate in candidates])
        self.assertIn("U.S. Open - Women’s Singles Final", [candidate["title"] for candidate in candidates])
        titles = [candidate["title"] for candidate in candidates]
        self.assertLess(titles.index("Live: Champions Berlin vs Munich"), titles.index("U.S. Open Tennis"))
        self.assertEqual(
            next(candidate for candidate in candidates if candidate["title"] == "Festival film premiere")["highlightType"],
            "freshProgramme",
        )

    def test_candidate_cap_keeps_all_channels_for_the_same_event(self):
        channels = [
            {
                "id": f"sports-{index}",
                "name": f"Sports {index}",
                "programs": [self.program("Live: Team A vs Team B", "2026-09-04T18:00:00Z")],
            }
            for index in range(12)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.write_country(path, "US", channels)

            candidates = build_editor_picks.collect_candidates(path, self.now)

        self.assertEqual(len(candidates), 12)

    def test_candidate_cap_keeps_same_live_event_with_translated_subtitles(self):
        strong_events = [
            self.program(f"Live: Champions Team {index} vs Team X", "2026-09-04T18:00:00Z")
            for index in range(9)
        ]
        channels = [
            {"id": "strong", "name": "Strong", "programs": strong_events},
            {
                "id": "english",
                "name": "English",
                "programs": [{**self.program("Live: Team A vs Team B", "2026-09-04T18:00:00Z"), "subtitle": "English coverage"}],
            },
            {
                "id": "spanish",
                "name": "Spanish",
                "programs": [{**self.program("Live: Team A vs Team B", "2026-09-04T18:00:00Z"), "subtitle": "Cobertura en español"}],
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.write_country(path, "US", channels)

            candidates = build_editor_picks.collect_candidates(path, self.now)

        self.assertEqual(len(candidates), 11)

    def test_selection_accepts_only_unique_supplied_ids_within_limit(self):
        candidates = [
            {
                "id": f"event-{index}",
                "country": "US",
                "countryName": "United States",
                "channelId": f"channel-{index}",
                "channelName": f"Channel {index}",
                "title": f"Local title {index}",
                "startAt": "2026-09-04T18:00:00Z",
                "endAt": "2026-09-04T20:00:00Z",
            }
            for index in range(1, 8)
        ]
        candidates[-1]["startAt"] = "2026-09-05T18:00:00Z"
        candidates[-2]["highlightType"] = "freshProgramme"
        for candidate in candidates[:-2]:
            candidate["highlightType"] = "liveSport"

        selected = build_editor_picks.validate_selection(json.dumps({
            "picks": [{"title": "Translated event", "pick_ids": ["event-2", "event-1"]}],
        }), candidates)

        self.assertEqual(selected[0]["title"], "Translated event")
        self.assertEqual([channel["channelId"] for channel in selected[0]["channels"]], ["channel-2", "channel-1"])
        self.assertEqual([channel["sourceTitle"] for channel in selected[0]["channels"]], ["Local title 2", "Local title 1"])
        for invalid in (
            '{"picks":[{"title":"Event","pick_ids":["invented"]}]}',
            '{"picks":[{"title":"Event","pick_ids":["event-1","event-1"]}]}',
            '{"picks":[{"title":"One","pick_ids":["event-1"]},{"title":"Two","pick_ids":["event-1"]}]}',
            '{"picks":[{"title":"Wrongly grouped","pick_ids":["event-1","event-7"]}]}',
            '{"picks":[{"title":"Mixed types","pick_ids":["event-1","event-6"]}]}',
            json.dumps({"picks": [{"title": str(index), "pick_ids": [f"event-{index}"]} for index in range(13)]}),
        ):
            with self.assertRaises(ValueError):
                build_editor_picks.validate_selection(invalid, candidates)

    def test_selection_accepts_twelve_picks_and_keeps_all_channels(self):
        candidates = [
            {"id": f"event-{index}", "title": f"Live event {index}",
             "channelId": f"channel-{index}", "highlightType": "liveSport",
             "startAt": "2026-09-04T18:00:00Z", "endAt": "2026-09-04T20:00:00Z"}
            for index in range(12)
        ]
        candidates.append({**candidates[0], "id": "simulcast", "channelId": "other-channel"})
        groups = [{"title": item["title"], "pick_ids": [item["id"]]} for item in candidates[:12]]
        selected = build_editor_picks.validate_selection(json.dumps({"picks": groups}), candidates)
        self.assertEqual(len(selected), 12)
        self.assertEqual([channel["channelId"] for channel in selected[0]["channels"]], ["channel-0", "other-channel"])

    def test_selection_adds_same_event_channels_the_model_omits(self):
        candidates = [
            {
                "id": f"event-{index}",
                "channelId": f"channel-{index}",
                "channelName": f"Channel {index}",
                "title": "Live: Team A vs Team B",
                "highlightType": "liveSport",
                "startAt": "2026-09-04T18:00:00Z",
                "endAt": "2026-09-04T20:00:00Z",
            }
            for index in (1, 2, 3)
        ]
        candidates[1]["startAt"] = "2026-09-04T18:50:00Z"
        candidates[2]["startAt"] = "2026-09-04T19:10:00Z"

        selected = build_editor_picks.validate_selection(
            '{"picks":[{"title":"Team A vs Team B","pick_ids":["event-1"]}]}',
            candidates,
        )

        self.assertEqual([channel["channelId"] for channel in selected[0]["channels"]], ["channel-1", "channel-2", "channel-3"])

        chinese = [
            {**candidates[0], "id": "football", "title": "足球赛事直播"},
            {**candidates[0], "id": "basketball", "channelId": "basketball", "title": "篮球赛事直播"},
        ]
        selected = build_editor_picks.validate_selection(
            '{"picks":[{"title":"Live football","pick_ids":["football"]}]}',
            chinese,
        )
        self.assertEqual([channel["channelId"] for channel in selected[0]["channels"]], ["channel-1"])

    def test_candidates_require_live_sports_or_fresh_quality_programming(self):
        base = {
            "title": "Programme",
            "startAt": "2026-09-04T18:00:00Z",
            "endAt": "2026-09-04T20:00:00Z",
        }
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "Live: Team A vs Team B", "categories": ["Sports"]}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "Team A vs Team B", "subtitle": "Live", "categories": ["Sports"]}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "Team A x Team B (Direto)", "categories": ["Sports"]}, self.now))
        self.assertFalse(build_editor_picks.is_candidate({**base, "title": "Team A vs Team B", "categories": ["Sports"]}, self.now))
        self.assertFalse(build_editor_picks.is_candidate({**base, "title": "Live: Team A vs Team B", "categories": ["Sports"]}, self.now, aired_earlier=True))
        self.assertFalse(build_editor_picks.is_candidate({**base, "title": "Live: Team A vs Team B", "categories": ["Sports"], "previouslyShown": True}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "New nature series", "categories": ["Documentary"], "originalDate": "2026"}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "New sports documentary", "categories": ["Documentary", "Sports"], "originalDate": "2026"}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "Drama pilot", "categories": ["Drama"], "episode": "S01E01"}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "Festival film premiere", "categories": ["Film"], "isPremiere": True}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "2026 US Open Tennis", "sportType": "Tennis", "categories": []}, self.now))
        self.assertTrue(build_editor_picks.is_candidate({**base, "title": "Amerika Açık", "description": "Tek Kadınlar Finali (Canlı)", "categories": ["Spor"]}, self.now))
        self.assertFalse(build_editor_picks.is_candidate({**base, "title": "Amerika Açık", "description": "Tek Kadınlar Finali (Tekrar)", "categories": ["Spor"]}, self.now))
        self.assertFalse(build_editor_picks.is_candidate({**base, "title": "Routine drama episode", "categories": ["Drama"], "originalDate": "2026"}, self.now))
        self.assertFalse(build_editor_picks.is_candidate({**base, "title": "Old documentary", "categories": ["Documentary"], "originalDate": "2021"}, self.now))

    def test_localized_us_open_finals_are_distinct_live_sport_airings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.write_country(path, "US", [{"id": "espn", "name": "ESPN", "programs": [{
                **self.program("2026 US Open Tennis", "2026-09-04T20:00:00Z", end="2026-09-04T23:00:00Z"),
                "categories": [], "sportType": "Tennis",
            }]}])
            self.write_country(path, "TR", [{"id": "eurosport", "name": "Eurosport", "programs": [
                {**self.program("Amerika Açık", "2026-09-04T16:00:00Z", end="2026-09-04T18:30:00Z"), "description": "Çift Erkekler Finali (Canlı)", "categories": ["Spor"], "sportType": None, "competition": None},
                {**self.program("Amerika Açık", "2026-09-04T18:50:00Z"), "description": "Tek Kadınlar Finali (Canlı)", "categories": ["Spor"], "sportType": None, "competition": None},
            ]}])

            candidates = build_editor_picks.collect_candidates(path, self.now)

        us = next(candidate for candidate in candidates if candidate["country"] == "US")
        women = next(candidate for candidate in candidates if "Kadınlar" in candidate.get("description", ""))
        self.assertEqual({us["highlightType"], women["highlightType"]}, {"liveSport"})
        selected = build_editor_picks.validate_selection(
            json.dumps({"picks": [{"title": "US Open Women’s Final", "pick_ids": [us["id"], women["id"]]}]}),
            candidates,
        )
        self.assertEqual([channel["channelName"] for channel in selected[0]["channels"]], ["ESPN", "Eurosport"])

    def test_opencode_go_request_uses_deepseek_and_retries_twice(self):
        candidate = {
            "id": "event-1",
            "country": "US",
            "channelName": "Sports One",
            "title": "Team A vs Team B",
            "startAt": "2026-09-04T18:00:00Z",
            "endAt": "2026-09-04T20:00:00Z",
        }
        response = io.BytesIO(b'{"choices":[{"message":{"content":"{\\"picks\\":[{\\"title\\":\\"Team A vs Team B\\",\\"pick_ids\\":[\\"event-1\\"]}]}"}}]}')
        opener = Mock(side_effect=[TimeoutError(), TimeoutError(), response])

        picks = build_editor_picks.select_with_opencode_go([candidate], "key", opener=opener)

        self.assertEqual(picks[0]["title"], "Team A vs Team B")
        self.assertEqual(picks[0]["channels"][0]["channelName"], "Sports One")
        self.assertEqual(opener.call_count, 3)
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://opencode.ai/zen/go/v1/chat/completions")
        body = json.loads(request.data)
        self.assertEqual(body["model"], "deepseek-v4.1-flash")
        self.assertEqual(request.get_header("Authorization"), "Bearer key")
        self.assertEqual(request.get_header("User-agent"), "whatson-editor-picks/1.0")
        self.assertEqual(request.get_header("X-opencode-session"), "whatson-editor-picks")
        self.assertTrue(all(call.kwargs["timeout"] == 180 for call in opener.call_args_list))

        exhausted = Mock(side_effect=[TimeoutError(), TimeoutError(), TimeoutError()])
        with self.assertRaises(TimeoutError):
            build_editor_picks.select_with_opencode_go([candidate], "key", opener=exhausted)
        self.assertEqual(exhausted.call_count, 3)

    def test_bad_group_does_not_erase_valid_picks_and_failure_preserves_output(self):
        candidates = [
            {**self.program(f"Live: Match {index}", "2026-09-04T18:00:00Z"),
             "id": f"event-{index}", "highlightType": "liveSport"}
            for index in range(3)
        ]
        candidates[2].update(startAt="2026-09-05T18:00:00Z", endAt="2026-09-05T21:00:00Z")
        good = {"title": "Match zero", "pick_ids": ["event-0"]}
        bad = {"title": "Different broadcasts", "pick_ids": ["event-1", "event-2"]}
        for groups in ([bad, good], [good, bad]):
            selected = build_editor_picks.validate_selection(json.dumps({"picks": groups}), candidates)
            self.assertEqual([pick["title"] for pick in selected], ["Match zero"])
        with self.assertRaises(ValueError):
            build_editor_picks.validate_selection(json.dumps({"picks": [bad]}), candidates)
        self.assertEqual(build_editor_picks.validate_selection('{"picks":[]}', candidates), [])

        from unittest.mock import patch
        with patch.object(build_editor_picks, "collect_candidates", side_effect=ValueError("invalid selection")), \
             patch.object(build_editor_picks, "write_output") as write:
            self.assertEqual(build_editor_picks.main(), 1)
            write.assert_not_called()

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
