import unittest
from pathlib import Path


class StaticAssetsTest(unittest.TestCase):
    def test_editor_picks_expire_without_reload(self):
        app = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("new Date(channel.programs[index].endAt).getTime() > state.now.getTime()", app)
        self.assertIn("renderEditorPicks();", app[app.index("window.setInterval"):])


if __name__ == "__main__":
    unittest.main()