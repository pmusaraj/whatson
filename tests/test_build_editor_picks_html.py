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
            "title": "Late United vs Late City <event>", "highlightType": "liveSport",
            "startAt": "2026-09-14T16:00:00Z",
            "channels": [{"channelName": "Sports & TV", "endAt": "2026-09-14T18:00:00Z"}],
        }
        picks = [pick, {**pick, "title": "Early Town vs Rovers", "startAt": "2026-09-14T15:00:00+02:00"},
                 {**pick, "title": "Series", "highlightType": "freshProgramme"},
                 {**pick, "title": "Expired", "channels": [{"endAt": now.isoformat()}]}]
        template = (ROOT / "web/index.html").read_text()
        result = picks_html.build_html(template, picks, now)
        self.assertLess(result.index('Early Town'), result.index('Late United'))
        self.assertIn("Late City &lt;event&gt;", result)
        self.assertIn(">LU<", result)
        self.assertIn('>13:00</div>', result)
        self.assertNotIn("Sep 14", result)
        self.assertNotIn(">Series<", result)
        self.assertNotIn("Expired", result)
        self.assertEqual(result.count('class="editor-pick-result"'), 2)
        self.assertIn("Tonight", result)
        self.assertIn("2 matches", result)
        self.assertIn("<section id=\"editor-picks\" class=\"editor-picks\" aria-label=\"Editor's Picks\">", result)
        self.assertNotIn('<summary>', result)
        self.assertEqual(picks_html.build_html(result, picks, now), result)
        channels = [{"country": country, "channelName": f"{country}{i}", "endAt": "2026-09-14T18:00:00Z"}
                    for country in ["US", "FR", "DE"] for i in range(4)]
        ranked = picks_html.render_picks([{**pick, "title": f"{league} United vs {league} City",
                                           "competition": league, "channels": channels}
                                          for league in ["Bundesliga", "Ligue 1", "Serie A", "La Liga", "Premier League", "LaLiga Hypermotion"]], now)
        self.assertLess(ranked.index(">Premier League<"), ranked.index(">La Liga<"))
        self.assertLess(ranked.index(">Serie A<"), ranked.index(">Ligue 1<"))
        self.assertNotIn("Hypermotion", ranked)
        self.assertEqual(ranked.count('class="editor-pick-watch"'), 5)
        self.assertEqual(ranked.count('+8 more'), 5)
        self.assertNotIn("US3", ranked)
        empty = picks_html.build_html(result, [], now)
        self.assertNotIn('class="editor-pick-result"', empty)
        self.assertIn("aria-label=\"Editor's Picks\" hidden", empty)
