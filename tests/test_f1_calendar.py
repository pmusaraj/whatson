import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("picks", Path(__file__).resolve().parents[1] / "scripts/build_editor_picks.py")
assert spec is not None and spec.loader is not None
picks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(picks)


class F1CalendarTest(unittest.TestCase):
    def test_calendar_blocks_replays_in_selection_and_expansion(self):
        session = dict(year=2026, location="Madrid", circuit_short_name="Madring", session_name="Race",
                       date_start="2026-09-13T13:00:00Z", date_end="2026-09-13T15:00:00Z", is_cancelled=False)
        replay = dict(title="Fórmula 1 - Tag Heuer Gran Premio de España 2026 - Corrida",
                      description="Assiste, em direto de Madrid, ao Formula 1 Tag Heuer Gran Premio de Espanha 2026.",
                      sportType="Formula 1", startAt="2026-09-16T17:25:00Z", endAt="2026-09-16T19:25:00Z")
        live = dict(replay, startAt="2026-09-13T12:00:00Z", endAt="2026-09-13T15:30:00Z")
        self.assertFalse(picks.f1_session_matches(replay, [session]))
        self.assertTrue(picks.f1_session_matches(live, [session]))
        for invalid in (
            dict(live, title="Live: Formula 1 Madrid Race 2025"),
            dict(live, title="Live: Formula 1 Madrid Qualifying 2026"),
            dict(live, startAt="2026-09-13T15:10:00Z", endAt="2026-09-13T17:00:00Z"),
            dict(live, startAt="2026-09-13T06:00:00Z"),
            dict(live, title="Live: Formula 1 Monza Race 2026", description=""),
        ):
            self.assertFalse(picks.f1_session_matches(invalid, [session]), invalid)
        self.assertFalse(picks.f1_session_matches(live, [dict(session, is_cancelled=True)]))
        self.assertFalse(picks.f1_session_matches(live, []))
        # Recognize accents and abbreviations even when inferred sport metadata is missing.
        self.assertTrue(picks.is_f1(dict(live, sportType=None)))
        self.assertTrue(picks.is_f1(dict(title="Live F1 Madrid Race")))
        cycling = dict(title="Live: UCI ProSeries Cycling", description="Grand Prix de Wallonie", sportType="Formula 1", competition="Formula 1")
        self.assertFalse(picks.is_f1(cycling))
        football = dict(live, title="Live: Team A vs Team B", description="", sportType="Football")
        now = picks.parse_time("2026-09-13T11:00:00Z")
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            rows = [live, dict(live, title="Madrid Race 2026", sportType=None, description=""),
                    dict(live, title="Madrid Qualifying 2026", sportType=None, description=""), football]
            (data / "PT.json").write_text(json.dumps(dict(country="PT", channels=[
                dict(id=str(i), name=str(i), programs=[p]) for i, p in enumerate(rows)])))
            candidates = picks.collect_candidates(data, now, f1_sessions=[session])
            self.assertEqual({c["channelId"] for c in candidates}, {"0", "3"})
            self.assertEqual({c["channelId"] for c in picks.collect_candidates(data, now, f1_sessions=[])}, {"3"})
            seed = picks.validate_selection(json.dumps({"picks": [{"title": "Madrid Race", "pick_ids": [next(c["id"] for c in candidates if c["channelId"] == "0")]}]}), candidates)
            def respond(request, **kwargs):
                text = json.loads(request.data)["messages"][1]["content"]
                supplied = json.loads(text.split("Candidates:\n")[1])
                self.assertEqual({c["channel"] for c in supplied}, {"0", "1"})
                content = {"picks": [{"title": "Madrid Race", "pick_ids": [c["id"] for c in supplied]}]}
                return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode())
            result = picks.expand_with_opencode_go(seed, "key", data, now, opener=respond, f1_sessions=[session])
            self.assertEqual({c["channelId"] for c in result[0]["channels"]}, {"0", "1"})
            (data / "PT.json").write_text(json.dumps(dict(country="PT", channels=[dict(id="replay", programs=[replay])])))
            self.assertEqual(picks.collect_candidates(data, picks.parse_time("2026-09-16T13:00:00Z"), f1_sessions=[session]), [])
        with patch.object(picks.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertEqual(picks.fetch_f1_sessions(now), [])
        with patch.object(picks, "fetch_f1_sessions", return_value=[session]) as fetch, \
             patch.object(picks, "collect_candidates", return_value=[]) as collect, \
             patch.object(picks, "expand_with_opencode_go", return_value=[]) as expand, \
             patch.object(picks, "write_output"), patch.dict("os.environ", {"OPENCODE_GO_API_KEY": "test"}):
            self.assertEqual(picks.main(), 0)
            fetch.assert_not_called()
            collect.return_value = [live]
            with patch.object(picks, "select_with_opencode_go", return_value=[]):
                self.assertEqual(picks.main(), 0)
            fetch.assert_called_once()
            self.assertEqual(collect.call_args.kwargs["f1_sessions"], [session])
            self.assertEqual(expand.call_args.kwargs["f1_sessions"], [session])


if __name__ == "__main__":
    unittest.main()
