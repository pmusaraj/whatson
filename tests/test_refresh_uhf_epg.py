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
    def test_country_filter_uses_shared_orange_fetcher_and_scales_canada_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources = root / "sources"
            sources.mkdir()
            for name, count in [("CA-tvpassport.com", 50), ("ES-movistarplus.es", 12),
                                ("ES-orangetv.orange.es", 35), ("FR-test", 1)]:
                (sources / f"custom-uhf-{name}.channels.xml").write_text(
                    "<channels>" + '<channel xmltv_id="test"/>' * count + "</channels>")
            with (patch.object(refresh, "EPG_DIR", root), patch.object(refresh, "SOURCES_DIR", sources),
                  patch.object(refresh, "NORMALIZED_DIR", root / "normalized"), patch.object(refresh, "run") as run):
                self.assertEqual(refresh.main(["--countries", "CA", "ES"]), 0)
            grabs = [call for call in run.call_args_list if "timeout" in call.kwargs]
            self.assertEqual(len(grabs), 3)
            self.assertEqual(grabs[0].kwargs["timeout"], 900)
            self.assertEqual(grabs[1].kwargs["timeout"], 900)
            self.assertEqual(grabs[1].args[0][:2], ["python3", "scripts/grab_movistar_epg.py"])
            self.assertEqual(grabs[2].kwargs["timeout"], 300)
            self.assertEqual(grabs[2].args[0][:2], ["python3", "scripts/grab_orange_epg.py"])

    def test_timeout_kills_descendants_before_they_write(self):
        import sys
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            marker = Path(tmpdir) / "late-output"
            child = f"import time,pathlib; time.sleep(1); pathlib.Path({str(marker)!r}).touch()"
            parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(60)"
            with self.assertRaises(subprocess.TimeoutExpired):
                refresh.run([sys.executable, "-c", parent], timeout=0.3)
            time.sleep(1.2)
            self.assertFalse(marker.exists(), "Timed-out descendant wrote a skipped snapshot")

    def test_failed_grabs_are_skipped_and_export_continues(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(refresh, "EPG_DIR", root / "epg"),
                patch.object(refresh, "SOURCES_DIR", root / "sources"),
                patch.object(refresh, "NORMALIZED_DIR", root / "normalized"),
            ):
                refresh.EPG_DIR.mkdir()
                refresh.SOURCES_DIR.mkdir()
                refresh.NORMALIZED_DIR.mkdir()
                for name in ("a", "b", "c"):
                    (refresh.SOURCES_DIR / f"custom-uhf-{name}.channels.xml").touch()
                    (refresh.NORMALIZED_DIR / f"guide-uhf-{name}.xml").write_text("snapshot")
                with patch.object(refresh, "run", side_effect=[
                    None, subprocess.TimeoutExpired("grab", 120),
                    subprocess.CalledProcessError(1, "grab"), None, None, None,
                ]) as run:
                    self.assertEqual(refresh.main([]), 0)
                self.assertEqual(run.call_count, 6)
                self.assertEqual([call.kwargs["timeout"] for call in run.call_args_list[1:4]], [120] * 3)
                self.assertEqual([p.name for p in refresh.NORMALIZED_DIR.glob("*.xml")], ["guide-uhf-c.xml"])
                self.assertEqual(run.call_args_list[-2].args[0], ["python3", "scripts/build_uhf_custom_xmltv.py"])
                self.assertEqual(run.call_args_list[-1].args[0], ["python3", "scripts/validate_uhf_xmltv.py"])


if __name__ == "__main__":
    unittest.main()
