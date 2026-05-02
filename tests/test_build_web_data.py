import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_web_data.py"
spec = importlib.util.spec_from_file_location("build_web_data", MODULE_PATH)
build_web_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_web_data)


class BuildWebDataTest(unittest.TestCase):
    def test_program_window_includes_current_and_next_three_hours(self):
        now = datetime(2026, 5, 2, 12, 30, tzinfo=timezone.utc)
        programs = [
            {"title": "Before", "startAt": "2026-05-02T10:00:00Z", "endAt": "2026-05-02T11:00:00Z"},
            {"title": "Current", "startAt": "2026-05-02T12:00:00Z", "endAt": "2026-05-02T13:00:00Z"},
            {"title": "Next", "startAt": "2026-05-02T13:00:00Z", "endAt": "2026-05-02T14:00:00Z"},
            {"title": "Later", "startAt": "2026-05-02T15:45:00Z", "endAt": "2026-05-02T16:00:00Z"},
        ]

        window = build_web_data.program_window(programs, now, hours=3)

        self.assertEqual([program["title"] for program in window], ["Current", "Next"])

    def test_build_country_payload_contains_channel_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guide = root / "guide.xml"
            guide.write_text(
                """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<tv>
  <channel id=\"A.fr\"><display-name>Alpha</display-name><icon src=\"https://example.com/a.png\" /></channel>
  <programme start="20260502120000 +0000" stop="20260502130000 +0000" channel="A.fr"><title>News</title><desc>Midday news</desc><category>Sports</category><category>Hockey</category><icon src="https://example.com/news.jpg" /></programme>
  <programme start="20260502120000 +0000" stop="20260502130000 +0000" channel="A.fr"><title>News</title><desc>Duplicate from another source</desc></programme>
  <programme start="20260502130000 +0000" stop="20260502140000 +0000" channel="A.fr"><title>Movie</title></programme>
</tv>
""",
                encoding="utf-8",
            )

            payload = build_web_data.build_country_payload(
                "FR",
                [build_web_data.LocalGuide(guide, "Validated grabber", "validated")],
                root,
                datetime(2026, 5, 2, 12, 15, tzinfo=timezone.utc),
            )

        self.assertEqual(payload["country"], "FR")
        self.assertEqual(payload["channels"][0]["name"], "Alpha")
        self.assertEqual(payload["channels"][0]["provider"], "Validated grabber")
        self.assertEqual(payload["channels"][0]["programs"][0]["title"], "News")
        self.assertEqual(payload["channels"][0]["programs"][0]["categories"], ["Sports", "Hockey"])
        self.assertEqual(payload["channels"][0]["programs"][0]["sportType"], "Hockey")
        self.assertEqual(payload["channels"][0]["programs"][0]["imageUrl"], "https://example.com/news.jpg")
        self.assertEqual(payload["channels"][0]["programs"][1]["title"], "Movie")

    def test_is_premium_sports_channel_uses_keywords_and_ids(self):
        self.assertTrue(build_web_data.is_premium_sports_channel("TSN1.ca", "Movie Channel", set()))
        self.assertTrue(build_web_data.is_premium_sports_channel("CanalPlusSport.fr", "Canal+ Sport", {"CanalPlusSport.fr"}))
        self.assertTrue(build_web_data.is_premium_sports_channel("Any.id", "DAZN 1", set()))
        self.assertFalse(build_web_data.is_premium_sports_channel("Tennis.id", "Tennis Channel", set()))
        self.assertFalse(build_web_data.is_premium_sports_channel("News.id", "World News", set()))

    def test_build_country_payload_can_filter_premium_sports_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guide = root / "guide.xml"
            guide.write_text(
                """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<tv>
  <channel id="Sport.fr"><display-name>Canal+ Sport</display-name></channel>
  <channel id="News.fr"><display-name>World News</display-name></channel>
  <programme start="20260502120000 +0000" stop="20260502130000 +0000" channel="Sport.fr"><title>Live match</title></programme>

</tv>
""",
                encoding="utf-8",
            )

            payload = build_web_data.build_country_payload(
                "FR",
                [build_web_data.LocalGuide(guide, "Validated grabber", "validated")],
                root,
                datetime(2026, 5, 2, 12, 15, tzinfo=timezone.utc),
                premium_sports_only=True,
            )

        self.assertEqual([channel["name"] for channel in payload["channels"]], ["Canal+ Sport"])


if __name__ == "__main__":
    unittest.main()
