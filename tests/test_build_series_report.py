import copy
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_series_report as series


class SeriesReportTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
        # Stable fixtures keep ranking/network tests independent of the live catalogue.
        seeds = json.loads(series.CATALOGUE.read_text())["series"]
        items = []
        for code in series.COUNTRIES:
            seed = next(p for p in seeds if p["country"] == code)
            for index in range(6):
                item = copy.deepcopy(seed)
                item.update(id=f"{code.lower()}-fixture-{index}", checkedAt="2026-09-15")
                if code == "CA":
                    item["originalLanguages"] = ["en" if index % 2 else "fr"]
                items.append(item)
        self.catalogue = {"schemaVersion": 1, "series": items}
        self.by_id = series.validate_catalogue(self.catalogue, self.now.date())
        self.selection = {code: [p["id"] for p in self.by_id.values() if p["country"] == code][:5]
                          for code in series.COUNTRIES}
        self.report = series.make_report(self.catalogue, self.selection, date(2026, 9, 14),
                                         {"method": "test"}, self.now)

    def test_catalogue_has_verified_origins_and_both_canadian_languages(self):
        languages = {lang for p in self.by_id.values() if p["country"] == "CA" for lang in p["originalLanguages"]}
        self.assertTrue({"en", "fr"} <= languages)
        self.assertEqual(sum(len(c["picks"]) for c in self.report["countries"]), 25)
        series.validate_report(self.report)

    def test_rejects_us_unknown_and_unreviewed_origins(self):
        for change in ({"productionCountries": ["FR", "US"]}, {"productionCountries": []},
                       {"productionCountries": None}, {"originVerified": False},
                       {"productionCountries": ["CA"]}):
            with self.subTest(change=change):
                catalogue = copy.deepcopy(self.catalogue)
                catalogue["series"][0].update(change)
                with self.assertRaises(ValueError):
                    series.validate_catalogue(catalogue, self.now.date())

    def test_canadian_dub_does_not_establish_original_language(self):
        catalogue = copy.deepcopy(self.catalogue)
        next(p for p in catalogue["series"] if p["country"] == "CA")["originalLanguages"] = ["es"]
        with self.assertRaisesRegex(ValueError, "original language"):
            series.validate_catalogue(catalogue, self.now.date())

    def test_rejects_us_editorial_sources_and_missing_origin_evidence(self):
        catalogue = copy.deepcopy(self.catalogue)
        catalogue["series"][0]["sources"][0]["country"] = "US"
        with self.assertRaisesRegex(ValueError, "non-US"):
            series.validate_catalogue(catalogue, self.now.date())
        catalogue = copy.deepcopy(self.catalogue)
        catalogue["series"][0]["sources"] = catalogue["series"][0]["sources"][:1]
        with self.assertRaisesRegex(ValueError, "origin evidence"):
            series.validate_catalogue(catalogue, self.now.date())

    def test_rejects_missing_countries_invented_duplicate_and_misclassified_ids(self):
        variants = []
        value = copy.deepcopy(self.selection)
        del value["CA"]
        variants.append(value)
        for replacement in ("made-up-show", self.selection["FR"][1], self.selection["CA"][0]):
            value = copy.deepcopy(self.selection)
            value["FR"][0] = replacement
            variants.append(value)
        value = copy.deepcopy(self.selection)
        value["FR"].pop()
        variants.append(value)
        for selection in variants:
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                series.validate_selection(selection, self.by_id)

    def test_html_escapes_copy_and_rejects_script_links(self):
        report = copy.deepcopy(self.report)
        report["countries"][0]["picks"][0]["title"] = '<script>alert("x")</script>'
        html = series.render_html(report, self.now.date())
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert', html)
        for url in ('javascript:alert(1)', 'https://user:pass@example.com/', '//example.com', 'https://localhost/'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                series.source_url(url)

    def test_html_is_complete_unindexed_and_not_linked_from_main_site(self):
        html = series.render_html(self.report, self.now.date())
        self.assertEqual(html.count('<li class="pick">'), 25)
        self.assertEqual(html.count('<ul class="sources"'), 25)
        self.assertIn('content="noindex, nofollow"', html)
        self.assertIn('Recommended series for this week by country', html)
        self.assertNotIn('Good stories.', html)
        self.assertNotIn('About these picks', html)
        self.assertIn('2026-09-14', html)
        for file in ('index.html', 'app.js', 'uhf.html'):
            self.assertNotIn('href="/series', (series.ROOT / 'web' / file).read_text())

    def test_week_boundaries_and_invalid_dates(self):
        self.assertEqual(series.week_start(date(2027, 1, 3)), date(2026, 12, 28))
        self.assertEqual(series.week_start(date(2027, 1, 4)), date(2027, 1, 4))
        report = copy.deepcopy(self.report)
        report['weekEnd'] = '2026-09-21'
        with self.assertRaises(ValueError):
            series.validate_report(report)

    def test_current_year_and_season_limits(self):
        for change in ({"year": 2025}, {"year": 2015}, {"season": 6}, {"season": 7}, {"season": 8}, {"season": 67}):
            with self.subTest(change=change):
                catalogue = copy.deepcopy(self.catalogue)
                item = catalogue["series"][0]
                item.update(change)
                candidates = series.validate_catalogue(catalogue, self.now.date())
                self.assertNotIn(item["id"], candidates)
                with self.assertRaises(ValueError):
                    series.validate_selection(self.selection, candidates)
        self.assertEqual(series.validate_catalogue(self.catalogue, date(2027, 1, 1)), {})

    def test_early_seasons_take_priority_over_later_seasons(self):
        catalogue = copy.deepcopy(self.catalogue)
        catalogue["series"][0]["season"] = 3
        candidates = series.validate_catalogue(catalogue, self.now.date())
        with self.assertRaisesRegex(ValueError, "Prefer first"):
            series.validate_selection(self.selection, candidates)
        catalogue["series"][5]["season"] = 5
        candidates = series.validate_catalogue(catalogue, self.now.date())
        with self.assertRaisesRegex(ValueError, "rank before"):
            series.validate_selection(self.selection, candidates)
        selection = copy.deepcopy(self.selection)
        selection["FR"] = selection["FR"][1:] + selection["FR"][:1]
        series.validate_selection(selection, candidates)

    def test_sparse_countries_and_year_rollover_do_not_backfill(self):
        catalogue = {"schemaVersion": 1, "series": [self.catalogue["series"][0]]}
        selection = {code: [] for code in series.COUNTRIES}
        selection["FR"] = [catalogue["series"][0]["id"]]
        report = series.make_report(catalogue, selection, date(2026, 9, 14), {}, self.now)
        html = series.render_html(report, self.now.date())
        self.assertEqual(html.count('<li class="pick">'), 1)
        self.assertIn('No verified current-year recommendations yet.', html)
        html = series.render_html(report, date(2027, 1, 1))
        self.assertNotIn('<li class="pick">', html)

    def test_watch_details_are_required_escaped_and_sourced(self):
        report = copy.deepcopy(self.report)
        pick = report["countries"][0]["picks"][0]
        pick["productionCompany"] = '<Producer & Co>'
        html = series.render_html(report, self.now.date())
        self.assertIn('Production: &lt;Producer &amp; Co&gt;', html)
        self.assertIn('Channel / platform:', html)
        self.assertIn('21:10', html)
        pick["airingSource"] = 'javascript:alert(1)'
        with self.assertRaises(ValueError):
            series.render_html(report, self.now.date())
        catalogue = copy.deepcopy(self.catalogue)
        catalogue["series"][0].pop("broadcaster")
        catalogue["series"][0].pop("productionCompany")
        with self.assertRaisesRegex(ValueError, "production company required"):
            series.validate_catalogue(catalogue, self.now.date())

    def test_committed_report_contains_only_eligible_sourced_picks(self):
        report = json.loads(series.REPORT.read_text())
        series.validate_report(report)
        for country in report["countries"]:
            self.assertTrue(country["picks"])
            for pick in country["picks"]:
                self.assertEqual(pick["year"], 2026)
                self.assertLess(pick["season"], 6)
                self.assertIn(country["code"], pick["productionCountries"])
                self.assertTrue(pick.get("broadcaster") or pick.get("productionCompany"))

    def temporary_paths(self, root):
        catalogue_path = root / 'catalogue.json'
        catalogue_path.write_text(json.dumps(self.catalogue))
        return dict(catalogue_path=catalogue_path, report_path=root / 'series.json',
                    page_path=root / 'series/index.html', archive_dir=root / 'archives')

    def test_bootstrap_weekly_idempotence_and_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.temporary_paths(root)
            result = series.build(**paths, now=self.now, bootstrap=True)
            self.assertEqual(result['selection']['method'], 'researched-bootstrap')
            self.assertTrue((root / 'archives/2026-09-14.json').exists())
            selector = Mock(side_effect=AssertionError('must not call model'))
            series.build(**paths, now=self.now, selector=selector)
            selector.assert_not_called()
            self.assertEqual(json.loads(paths['report_path'].read_text()), result)

    def test_next_week_uses_model_preserves_previous_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.temporary_paths(root)
            series.build(**paths, now=self.now, bootstrap=True)
            original_archive = (root / 'archives/2026-09-14.json').read_bytes()
            selector = Mock(return_value=(self.selection, {'method': 'llm', 'model': 'test'}))
            result = series.build(**paths, now=datetime(2026, 9, 21, tzinfo=timezone.utc), api_key='test', selector=selector)
            self.assertEqual(result['weekStart'], '2026-09-21')
            self.assertEqual((root / 'archives/2026-09-14.json').read_bytes(), original_archive)
            self.assertEqual(selector.call_args.kwargs['previous'], self.selection)

    def test_failed_model_and_missing_key_preserve_all_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.temporary_paths(root)
            series.build(**paths, now=self.now, bootstrap=True)
            original = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            for key, selector in [('', Mock()), ('test', Mock(side_effect=ValueError('invalid JSON')))]:
                with self.assertRaises(ValueError):
                    series.build(**paths, now=self.now, force=True, api_key=key, selector=selector)
                self.assertEqual({p: p.read_bytes() for p in root.rglob('*') if p.is_file()}, original)

    def test_bad_model_selection_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.temporary_paths(root)
            selector = Mock(return_value=({'FR': ['invented']}, {'method': 'llm'}))
            with self.assertRaises(ValueError):
                series.build(**paths, now=self.now, api_key='test', selector=selector)
            self.assertFalse(paths['report_path'].exists())
            self.assertFalse(paths['page_path'].exists())

    def test_render_only_never_needs_model_or_relabels_old_week(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.temporary_paths(Path(directory))
            series.build(**paths, now=self.now, bootstrap=True)
            selector = Mock(side_effect=AssertionError('no model'))
            series.build(**paths, now=datetime(2026, 10, 1, tzinfo=timezone.utc), render_only=True, selector=selector)
            self.assertIn('2026-09-14', paths['page_path'].read_text())
            selector.assert_not_called()

    def test_write_failure_rolls_back_report_and_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.temporary_paths(root)
            series.build(**paths, now=self.now, bootstrap=True)
            original = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            writer = series.atomic_write
            def fail_on_page(path, content):
                if path == paths['page_path']:
                    raise OSError('disk full')
                writer(path, content)
            with patch.object(series, 'atomic_write', side_effect=fail_on_page), self.assertRaises(OSError):
                series.build(**paths, now=datetime(2026, 9, 21, tzinfo=timezone.utc), api_key='test',
                             selector=Mock(return_value=(self.selection, {'method': 'llm'})))
            self.assertEqual({p: p.read_bytes() for p in root.rglob('*') if p.is_file()}, original)

    def response(self, content=None):
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': json.dumps(content or self.selection)}}],
                                     'usage': {'total_tokens': 100}}).encode())

    def test_model_fallback_for_unavailable_model(self):
        error = urllib.error.HTTPError(series.OPENCODE_GO_URL, 429, 'limited', {}, None)
        opener = Mock(side_effect=[error, self.response()])
        result, provenance = series.select_with_llm(self.by_id, date(2026, 9, 14), 'test', opener=opener)
        self.assertEqual(result, self.selection)
        self.assertEqual(provenance['model'], series.OPENCODE_GO_MODELS[1])
        self.assertEqual(provenance['usage'], {'total_tokens': 100})

    def test_authentication_and_bad_output_do_not_change_model(self):
        for error in (urllib.error.HTTPError(series.OPENCODE_GO_URL, 401, 'unauthorized', {}, None),):
            opener = Mock(side_effect=error)
            with self.assertRaises(urllib.error.HTTPError):
                series.select_with_llm(self.by_id, date(2026, 9, 14), 'test', opener=opener)
            self.assertEqual(opener.call_count, 1)
        opener = Mock(return_value=self.response({'FR': ['invented']}))
        with self.assertRaises(ValueError):
            series.select_with_llm(self.by_id, date(2026, 9, 14), 'test', opener=opener)
        self.assertEqual(opener.call_count, 1)


if __name__ == '__main__':
    unittest.main()
