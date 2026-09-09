import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "refresh_uhf_epg.py"
spec = importlib.util.spec_from_file_location("refresh_uhf_epg", SCRIPT)
assert spec is not None and spec.loader is not None
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class RefreshUhfEpgTest(unittest.TestCase):
    def test_grab_failure_stops_before_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(refresh, "EPG_DIR", root / "epg"),
                patch.object(refresh, "SOURCES_DIR", root / "sources"),
                patch.object(refresh, "NORMALIZED_DIR", root / "normalized"),
            ):
                refresh.EPG_DIR.mkdir()
                refresh.SOURCES_DIR.mkdir()
                (refresh.SOURCES_DIR / "custom-uhf-test.channels.xml").touch()

                with patch.object(
                    refresh,
                    "run",
                    side_effect=[None, subprocess.CalledProcessError(1, "grab")],
                ) as run:
                    with self.assertRaisesRegex(SystemExit, "refusing to build"):
                        refresh.main()

                self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
