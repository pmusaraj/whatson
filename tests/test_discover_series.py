import copy
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import discover_series as d


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.sources = json.loads((d.BASE / 'sources.json').read_text())['sources']
        self.data = json.loads((d.BASE / 'first-pass.json').read_text())
        self.today = date(2026, 9, 16)
        self.pick = copy.deepcopy(next(c for c in self.data['candidates'] if c['id'] == 'ca-kingston-falls'))

    def test_first_pass_results(self):
        result = d.run(self.data['candidates'], self.today, self.sources)
        statuses = {c['id']: c['status'] for c in result['candidates']}
        self.assertEqual(statuses['it-erica'], 'recent')
        self.assertEqual(statuses['ca-kingston-falls'], 'recent')
        self.assertEqual(statuses['ca-sur-le-fil'], 'recent')
        for identifier in ('ca-penelope-partout', 'uk-hit-point'):
            self.assertEqual(statuses[identifier], 'pending')
        self.assertEqual(statuses['fr-chambre-jaune'], 'not-recommended')
        self.assertEqual(statuses['fr-la-cible'], 'not-recommended')
        for identifier in ('es-hijas-criada', 'uk-split-up', 'it-due-spicci', 'es-genesi', 'it-metodo-paraldi'):
            self.assertEqual(statuses[identifier], 'excluded')
        self.assertFalse(result['picks']['ES'])
        self.assertFalse(result['picks']['UK'])

    def test_broadcast_boundaries_not_article_dates(self):
        for age, status, tier in [(0,'recent',0), (13,'recent',0), (14,'recent',1), (20,'recent',1), (21,'fallback',2)]:
            with self.subTest(age=age):
                c = copy.deepcopy(self.pick)
                c['broadcastDate'] = str(self.today - timedelta(days=age))
                r = d.evaluate(c, self.today, self.sources)
                self.assertEqual((r['status'],r['recencyTier']), (status,tier))
        self.pick['broadcastDate'] = '2026-09-17'
        self.assertEqual(d.evaluate(self.pick,self.today,self.sources)['status'], 'excluded')

    def test_eligibility(self):
        for change in ({'releaseYear':2025}, {'releaseYear':2027}, {'season':6}, {'season':8}, {'productionCountries':['US','CA']}, {'productionCountries':['FR']}, {'distribution':'streaming-only'}, {'channel':'Netflix'}):
            with self.subTest(change=change):
                c = {**self.pick, **change}
                self.assertEqual(d.evaluate(c,self.today,self.sources)['status'], 'excluded')

    def test_missing_evidence_or_review_cannot_be_recommended(self):
        for change in ({'factsReviewed':False}, {'review':None}, {'evidence':{}}, {'season':None}, {'distribution':None}):
            with self.subTest(change=change):
                self.assertEqual(d.evaluate({**self.pick,**change},self.today,self.sources)['status'], 'pending')

    def test_domain_spoofing_and_nonapproved_sources(self):
        for url in ('https://www.bbc.co.uk.evil.test/a','https://netflix.com/a','javascript:alert(1)'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                d.publisher(url,self.sources)
        self.pick['review']['url'] = self.pick['evidence']['broadcastDate']
        with self.assertRaises(ValueError):
            d.evaluate(self.pick,self.today,self.sources)

    def test_broadcast_needs_official_confirmation(self):
        self.pick['evidence']['broadcastDate'] = self.pick['review']['url']
        self.assertEqual(d.evaluate(self.pick,self.today,self.sources)['status'], 'pending')

    def test_duplicate_and_nonmutation(self):
        original = copy.deepcopy(self.data['candidates'])
        d.run(original,self.today,self.sources)
        self.assertEqual(original,self.data['candidates'])
        with self.assertRaises(ValueError):
            d.run([self.pick,self.pick],self.today,self.sources)

    def test_recent_then_early_seasons_then_review_support(self):
        old = {**copy.deepcopy(self.pick),'id':'old','broadcastDate':'2026-03-01'}
        later = {**copy.deepcopy(self.pick),'id':'later','season':3}
        result = d.run([old,later,self.pick],self.today,self.sources)
        self.assertEqual([c['id'] for c in result['picks']['CA']], [self.pick['id'],'later','old'])

    def test_html_escapes_review_and_title(self):
        self.pick['title'] = '<script>alert(1)</script>'
        html = d.render(d.run([self.pick],self.today,self.sources))
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>',html)

    def test_links_are_not_claimed_as_verified_titles(self):
        p = d.Links()
        p.feed('<a href="/news/test"><b>New drama</b> series</a>')
        self.assertEqual(p.links,[('/news/test','New drama series')])


if __name__ == '__main__':
    unittest.main()
