import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("picks_html", ROOT / "scripts/build_editor_picks_html.py")
assert spec is not None and spec.loader is not None
picks_html = importlib.util.module_from_spec(spec)
spec.loader.exec_module(picks_html)


class EditorPicksHtmlTest(unittest.TestCase):
    def test_html_is_current_sorted_escaped_and_rebuilt_without_duplicates(self):
        now = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
        pick = {
            "title": "Late <event>", "highlightType": "liveSport",
            "startAt": "2026-09-14T16:00:00Z",
            "channels": [{"channelName": "Sports & TV", "endAt": "2026-09-14T18:00:00Z"}],
        }
        picks = [pick, {**pick, "title": "Early", "startAt": "2026-09-14T15:00:00+02:00"},
                 {**pick, "title": "Series", "highlightType": "freshProgramme"},
                 {**pick, "title": "Expired", "channels": [{"endAt": now.isoformat()}]}]
        template = (ROOT / "web/index.html").read_text()
        result = picks_html.build_html(template, picks, now)
        self.assertLess(result.index('>Early</strong>'), result.index('>Late &lt;event&gt;</strong>'))
        self.assertIn("Sports &amp; TV", result)
        self.assertIn("Sep 14, 13:00 UTC", result)
        self.assertNotIn(">Series</strong>", result)
        self.assertNotIn(">Expired</strong>", result)
        self.assertEqual(result.count('class="editor-pick-result"'), 2)
        self.assertIn("<section id=\"editor-picks\" class=\"editor-picks\" aria-label=\"Editor's Picks\">", result)
        self.assertNotIn('<summary>', result)
        self.assertEqual(picks_html.build_html(result, picks, now), result)
        channels = [{"country": country, "channelName": f"{country}{i}", "endAt": "2026-09-14T18:00:00Z"}
                    for country in ["US", "FR", "DE"] for i in range(4)]
        ranked = picks_html.render_picks([{**pick, "title": league, "channels": channels}
                                         for league in ["Bundesliga", "Ligue 1", "Serie A", "La Liga", "Premier League", "LaLiga Hypermotion"]], now)
        self.assertLess(ranked.index(">Premier League</strong>"), ranked.index(">La Liga</strong>"))
        self.assertLess(ranked.index(">Serie A</strong>"), ranked.index(">Ligue 1</strong>"))
        self.assertNotIn("Hypermotion", ranked)
        self.assertEqual(ranked.count('class="editor-pick-channel"'), 45)
        self.assertEqual(ranked.count('>more</summary>'), 5)
        self.assertNotIn("US3", ranked)
        empty = picks_html.build_html(result, [], now)
        self.assertNotIn('class="editor-pick-result"', empty)
        self.assertIn("aria-label=\"Editor's Picks\" hidden", empty)
