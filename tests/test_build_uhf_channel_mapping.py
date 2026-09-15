import unittest

from scripts.build_uhf_channel_mapping import load_targets, map_row


class UhfMappingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets, cls.raw, _ = load_targets()

    def row(self, name, category="Spain", **extra):
        source = {"uhf_pk": "1", "category": category, "name": name, "original_name": name,
                  "epg_channel_id": "", "logo_url": "", **extra}
        return map_row(source, self.targets, self.raw)

    def test_explicit_regional_selection_beats_old_original_name(self):
        row = self.row("CBC (CBAT) Fredericton, NB HD", "Canada", original_name="Canada- CBC Toronto HD",
                       epg_channel_id="!$!playlist!$!CA:CBATDT.ca")
        self.assertEqual(row["target_xmltv_id"], "CA:CBATDT.ca")

    def test_movistar_match_feeds_do_not_collapse_onto_studio_channel(self):
        expected = {"Movistar LaLiga": "LaLigaTVporMovistarPlusPlus.es",
                    "ESP-Movistar LaLiga 1": "LaLiga1porMovistarPlusPlus.es",
                    "ESP-Movistar LaLiga 2": "LaLigaTV2porMovistarPlusPlus.es",
                    "ESP-Movistar LaLiga 3": "LaLigaTV3porMovistarPlusPlus.es"}
        for name, target in expected.items():
            with self.subTest(name=name):
                self.assertEqual(self.row(name)["target_xmltv_id"], f"ES:{target}")

    def test_priority_sports_and_movies_have_distinct_approved_targets(self):
        for name, target in [("Golf", "GolfporMovistarPlusPlus.es"),
                             ("Deportes", "DeportesporMovistarPlusPlus.es"),
                             ("Liga de Campeones", "LigadeCampeonesporMovistarPlusPlus.es"),
                             ("Drama", "DramaporMovistarPlusPlus.es"),
                             ("Accion", "AccionporMovistarPlusPlus.es")]:
            with self.subTest(name=name):
                row = self.row(f"ESP-Movistar {name}")
                self.assertEqual(row["target_xmltv_id"], f"ES:{target}")
                self.assertEqual(row["review"], "ok")


if __name__ == "__main__":
    unittest.main()
