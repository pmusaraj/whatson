import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_editor_picks.py"
spec = importlib.util.spec_from_file_location("build_editor_picks", MODULE_PATH)
build_editor_picks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_editor_picks)


class BuildEditorPicksTest(unittest.TestCase):
    def setUp(self):
        calendar = patch.object(build_editor_picks, "fetch_f1_sessions", return_value=[])
        calendar.start()
        self.addCleanup(calendar.stop)
        self.now = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)

    def test_league_priority_and_second_tiers(self):
        leagues = ["Premier League", "La Liga", "Serie A", "Ligue 1", "Bundesliga"]
        programs = [{**self.program(f"{league}: A vs B (Direto)", "2026-09-04T18:00:00Z"),
                     "categories": [], "sportType": None, "competition": None} for league in leagues]
        for league in ["2. Bundesliga", "Bundesliga 2", "Ligue 2", "Serie B", "LaLiga 2", "LaLiga Hypermotion", "EFL Championship", "Liga Portugal 2", "Série B", "Segunda División"]:
            program = self.program(f"Live: {league}: C vs D", "2026-09-04T18:00:00Z")
            self.assertFalse(build_editor_picks.is_candidate(program, self.now), league)
        for program in [
            {"title": "Caribbean Premier League", "categories": ["Cricket"], "competition": "Premier League"},
            {"title": "Argentine Primera División", "competition": "Premier League", "description": "The premier league in Argentina"},
            {"title": "World Championship Final"},
        ]:
            self.assertEqual(build_editor_picks.league_rank(program), 5)
        with tempfile.TemporaryDirectory() as tmp:
            self.write_country(Path(tmp), "US", [{"id": "sports", "name": "Sports", "programs": programs[::-1]}])
            candidates = build_editor_picks.collect_candidates(Path(tmp), self.now)
        self.assertEqual([c["title"] for c in candidates], [p["title"] for p in programs])

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
        self.assertNotIn("New nature documentary", [candidate["title"] for candidate in candidates])
        self.assertIn("U.S. Open - Women’s Singles Final", [candidate["title"] for candidate in candidates])
        titles = [candidate["title"] for candidate in candidates]
        self.assertLess(titles.index("Live: Champions Berlin vs Munich"), titles.index("U.S. Open Tennis"))
        self.assertNotIn("Festival film premiere", titles)
        self.assertTrue(all(candidate["highlightType"] == "liveSport" for candidate in candidates))

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
        candidates.append({**candidates[0], "id": "distant", "channelId": "distant", "startAt": "2026-09-04T19:40:00Z"})

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

        exhausted = Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):
            build_editor_picks.select_with_opencode_go([candidate], "key", opener=exhausted)
        self.assertEqual(exhausted.call_count, 3 * len(build_editor_picks.OPENCODE_GO_MODELS))

    def test_model_fallback_is_ordered_and_only_for_unavailability(self):
        from email.message import Message
        from urllib.error import HTTPError

        response = b'{"choices":[{"message":{"content":"{\\"picks\\":[]}"}}]}'
        for code in (403, 404, 429, 503, 401, 400):
            with self.subTest(code=code):
                opener = Mock(side_effect=[HTTPError("https://example.com", code, "Unavailable", Message(), None), io.BytesIO(response)])
                if code in (401, 400):
                    with self.assertRaises(HTTPError):
                        build_editor_picks.select_with_opencode_go([], "key", opener=opener)
                    self.assertEqual(opener.call_count, 1)
                else:
                    self.assertEqual(build_editor_picks.select_with_opencode_go([], "key", opener=opener), [])
                    self.assertEqual([json.loads(c.args[0].data)["model"] for c in opener.call_args_list],
                                     list(build_editor_picks.OPENCODE_GO_MODELS[:2]))
        opener = Mock(side_effect=HTTPError("https://example.com", 403, "Unavailable", Message(), None))
        with self.assertRaises(HTTPError):
            build_editor_picks.select_with_opencode_go([], "key", opener=opener)
        self.assertEqual([json.loads(c.args[0].data)["model"] for c in opener.call_args_list],
                         list(build_editor_picks.OPENCODE_GO_MODELS))

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

    def test_semantic_expansion_reaches_sparse_cross_language_simulcasts(self):
        # Source-shaped September 14 listings; model responses below are test doubles.
        now = datetime(2026, 9, 14, 16, tzinfo=timezone.utc)
        rows = [
            ("PT", "DAZN2.uk", "La Liga EA Sports 2026-27 - Villarreal x Bétis (Direto)", "2627", "Assiste ao jogo da LALIGA entre Villarreal x Real Betis.", "18:50", ["Football"]),
            ("UK", "PremierSports1.ie", "Live: LaLiga", "Villarreal CF v Real Betis", "The Ceramica is the setting for this Monday night LALIGA fixture.", "18:55", ["Football"]),
            ("UK", "1638/premier-sports-1-hd", "Live LaLiga", "Villarreal v Real Betis", None, "18:55", []),
            ("TR", "SSport.tr", "Villareal - Real Betis", None, "La Liga 5. Hafta Maçı", "19:00", ["Spor"]),
            ("MX", "SkySports24.mx", "Villarreal vs. Real Betis", None, None, "19:00", []),
            ("PT", "DAZN1.uk", "Premier League 26/27 - Leeds x Newcastle (Direto)", "2627", "Assiste ao jogo da Premier League entre Leeds x Newcastle.", "18:50", ["Football"]),
            ("BR", "ESPN.br", "Leeds United x Newcastle United", None, "Todas as emoções da Premier League", "18:50", ["Campeonato Inglês"]),
            ("FR", "CanalPlusFoot.fr", "Football : Premier League", None, "Cette affiche du lundi soir présente des enjeux importants pour Leeds et Newcastle.", "18:55", ["Football"]),
            ("DE", "magenta-de:5555", "Live PL: Leeds United - Newcastle United, 4. Spieltag", None, "Aus dem Elland Road Stadium", "18:55", ["Fußball"]),
            ("UK", "SkySportsMainEvent.uk", "Live MNF", "Leeds United v Newcastle United 14.09", None, "17:30", []),
            ("UK", "SkySportsPremierLeague.uk", "Live MNF", "Leeds United v Newcastle United 14.09", None, "17:30", []),
            ("UK", "different", "Live LaLiga", "Barcelona v Real Madrid", None, "19:00", []),
            ("UK", "replay", "Live LaLiga", "Villarreal v Real Betis", "Replay", "19:00", []),
            ("UK", "previously-shown", "Live LaLiga", "Villarreal v Real Betis", None, "19:00", []),
            ("UK", "late", "Live LaLiga", "Villarreal v Real Betis", None, "23:00", []),
            ("UK", "expired", "Live LaLiga", "Earlier fixture", None, "12:00", []),
            ("FR", "earlier-generic", "Football : Premier League", None, "Arsenal contre Liverpool", "12:00", ["Football"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            countries = {}
            for country, channel, title, subtitle, description, start, categories in rows:
                program: dict = dict(title=title, subtitle=subtitle, description=description, categories=categories,
                               startAt=f"2026-09-14T{start}:00Z", endAt="2026-09-14T21:00:00Z")
                if channel == "SSport.tr":
                    program["endAt"] = "2026-09-15T20:59:00Z"  # Bad source duration must not widen matching.
                if channel == "late":
                    program["endAt"] = "2026-09-15T01:00:00Z"
                if channel == "expired":
                    program["endAt"] = "2026-09-14T14:00:00Z"
                if channel == "previously-shown":
                    program["previouslyShown"] = True
                countries.setdefault(country, []).append(dict(id=channel, name=channel, programs=[program]))
            for country, channels in countries.items():
                self.write_country(path, country, channels)
            candidates = build_editor_picks.collect_candidates(path, now)
            self.assertEqual({c["channelId"] for c in candidates}, {"DAZN1.uk", "DAZN2.uk"})
            seeds = build_editor_picks.validate_selection(json.dumps({"picks": [
                {"title": c["title"], "pick_ids": [c["id"]]} for c in candidates
            ]}), candidates)
            expected = [set(row[1] for row in rows[:5]), set(row[1] for row in rows[5:11])]

            def respond(request, **kwargs):
                prompt = json.loads(request.data)["messages"][1]["content"]
                public = json.loads(prompt.split("Candidates:\n")[1])
                supplied = {c["channel"]: c for c in public}
                self.assertTrue(set.union(*expected) <= supplied.keys())
                self.assertIn("different", supplied)
                self.assertTrue({"replay", "previously-shown", "late", "expired"}.isdisjoint(supplied))
                self.assertIn("Leeds et Newcastle", supplied["CanalPlusFoot.fr"]["description"])
                self.assertIn("Villarreal v Real Betis", supplied["1638/premier-sports-1-hd"]["subtitle"])
                selected = json.loads(prompt.split("Selected events:\n")[1].split("\n\nCandidates:\n")[0])
                self.assertEqual(len(selected), 1)
                self.assertTrue(all("highlightType" not in c for c in public))
                channels = next(channels for channels in expected
                                if any(supplied[channel]["id"] in selected[0]["pick_ids"] for channel in channels))
                groups = [{"title": "Same event", "pick_ids": [supplied[channel]["id"] for channel in sorted(channels)]}]
                return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps({"picks": groups})}}]}).encode())

            opener = Mock(side_effect=respond)
            expanded = build_editor_picks.expand_with_opencode_go(seeds, "key", path, now, opener=opener)
            self.assertEqual(opener.call_count, 2)
            self.assertEqual({frozenset(c["channelId"] for c in p["channels"]) for p in expanded}, {frozenset(s) for s in expected})
            self.assertTrue(all(p["highlightType"] == "liveSport" for p in expanded))

    def test_expansion_validation_and_failure_preserve_selected_events(self):
        candidates = [{**self.program("Live MNF", "2026-09-04T18:00:00Z"),
                       "subtitle": f"Fixture {index}", "id": f"event-{index}", "channelId": str(index),
                       "highlightType": "liveSport"} for index in range(4)]
        groups = [{"title": "Fixture zero", "pick_ids": ["event-0"], "eligible_ids": ["event-0", "event-2"]},
                  {"title": "Fixture one", "pick_ids": ["event-1"], "eligible_ids": ["event-1", "event-3"]}]
        good = [{"title": g["title"], "pick_ids": g["pick_ids"]} for g in groups]
        result = build_editor_picks.validate_selection(json.dumps({"picks": good}), candidates, groups)
        self.assertEqual([len(p["channels"]) for p in result], [1, 1])  # No exact-title expansion.
        for invalid in ([], good[:1],
                        [{"title": "Merged", "pick_ids": ["event-0", "event-1"]}],
                        [good[0], {"title": "Wrong window", "pick_ids": ["event-1", "event-2"]}],
                        [good[0], {"title": "Omitted seed", "pick_ids": ["event-3"]}],
                        [good[0], {"title": "Invented", "pick_ids": ["event-1", "invented"]}],
                        [good[0], {"title": "Duplicate", "pick_ids": ["event-1", "event-1"]}],
                        [{"title": "Malformed", "pick_ids": 42}]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_editor_picks.validate_selection(json.dumps({"picks": invalid}), candidates, groups)
        with self.assertRaises(ValueError):
            build_editor_picks.validate_selection(json.dumps({"picks": good}), [*candidates, candidates[0]], groups)
        candidates[2].update(startAt="2026-09-04T20:00:00Z", endAt="2026-09-05T23:00:00Z")
        with self.assertRaises(ValueError):
            build_editor_picks.validate_selection(json.dumps({"picks": [
                {"title": "Too late", "pick_ids": ["event-0", "event-2"]}, good[1]]}), candidates, groups)
        with patch.dict("os.environ", {"OPENCODE_GO_API_KEY": "test-key"}), \
             patch.object(build_editor_picks, "collect_candidates", return_value=candidates), \
             patch.object(build_editor_picks, "select_with_opencode_go", return_value=result), \
             patch.object(build_editor_picks, "expand_with_opencode_go", side_effect=ValueError("Expansion grouped non-overlapping broadcasts")), \
             patch.object(build_editor_picks, "write_output") as write, \
             patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(build_editor_picks.main(), 0)
            self.assertEqual(write.call_args.args, (result,))
            self.assertIn("keeping validated selections", stderr.getvalue())
            self.assertIn("non-overlapping broadcasts", stderr.getvalue())

    def test_exact_title_fallback_does_not_merge_different_fixtures(self):
        candidates = [{**self.program("Live football", "2026-09-04T18:00:00Z"),
                       "id": str(index), "subtitle": f"Fixture {index}"} for index in range(2)]
        result = build_editor_picks.validate_selection('{"picks":[{"title":"Fixture zero","pick_ids":["0"]}]}', candidates)
        self.assertEqual(len(result[0]["channels"]), 1)

    def test_expansion_preserves_simultaneous_event_feed_matches(self):
        now = datetime(2026, 9, 4, 16, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            programs = [self.program(title, "2026-09-04T18:00:00Z")
                        for title in ("Live: Team A vs Team B", "Live: Team C vs Team D")]
            for program in programs:
                program["categories"] = ["Sports", "MLS", "Apple TV"]
            self.write_country(path, "US", [{"id": "MLSSeasonPass.us", "name": "MLS", "programs": programs}])
            candidates = build_editor_picks.collect_candidates(path, now)
            seeds = build_editor_picks.validate_selection(json.dumps({"picks": [
                {"title": c["title"], "pick_ids": [c["id"]]} for c in candidates
            ]}), candidates)

            def respond(request, **kwargs):
                prompt = json.loads(request.data)["messages"][1]["content"]
                groups = json.loads(prompt.split("Selected events:\n")[1].split("\n\nCandidates:\n")[0])
                return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps({"picks": groups})}}]}).encode())

            expanded = build_editor_picks.expand_with_opencode_go(seeds, "key", path, now, opener=respond)
            self.assertEqual(len(expanded), 2)
            for pick in expanded:
                self.assertEqual([c["sourceTitle"] for c in pick["channels"]], [pick["title"]])

            # Independent requests must still reject one broadcast used by two events.
            def reuse_broadcast(request, **kwargs):
                prompt = json.loads(request.data)["messages"][1]["content"]
                public = json.loads(prompt.split("Candidates:\n")[1])
                group = {"title": "Merged fixtures", "pick_ids": [c["id"] for c in public]}
                return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps({"picks": [group]})}}]}).encode())

            with self.assertRaisesRegex(ValueError, "reused broadcasts"):
                build_editor_picks.expand_with_opencode_go(seeds, "key", path, now, opener=reuse_broadcast)

    def test_http_403_skips_picks_but_other_http_errors_still_fail(self):
        from email.message import Message
        from urllib.error import HTTPError

        for stage in ("select_with_opencode_go", "expand_with_opencode_go"):
            for code in (403, 401, 500):
                with self.subTest(stage=stage, code=code), \
                     patch.dict("os.environ", {"OPENCODE_GO_API_KEY": "test-key"}), \
                     patch.object(build_editor_picks, "collect_candidates", return_value=[{}]), \
                     patch.object(build_editor_picks, "select_with_opencode_go", return_value=[{}]), \
                     patch.object(build_editor_picks, stage, side_effect=HTTPError("https://example.com", code, "Denied", Message(), None)), \
                     patch.object(build_editor_picks, "write_output") as write, \
                     patch("sys.stderr", new_callable=io.StringIO) as stderr:
                    self.assertEqual(build_editor_picks.main(), 0 if code == 403 else 1)
                    write.assert_not_called()
                    self.assertIn("previous output preserved", stderr.getvalue())
                    self.assertIn("warning:" if code == 403 else "error:", stderr.getvalue())

    def test_output_replacement_is_atomic_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "editors-picks.json"
            output.write_text("previous output", encoding="utf-8")
            with patch.object(Path, "replace", side_effect=OSError("disk error")), self.assertRaises(OSError):
                build_editor_picks.write_output([], self.now, output)
            self.assertEqual(output.read_text(), "previous output")
            self.assertEqual(list(Path(tmp).iterdir()), [output])
            build_editor_picks.write_output([], self.now, output)
            self.assertEqual(json.loads(output.read_text())["picks"], [])

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
