import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from scripts import refresh_epg, refresh_uhf_epg
from scripts.build_uhf_channel_mapping import load_targets, map_row

ROOT = Path(__file__).resolve().parents[1]


class CountryFeedFixesTest(unittest.TestCase):
    def test_curated_channels_have_ids_and_keep_distinct_stations(self):
        directory = ROOT / 'data/sources/iptv-org'
        for country in ['IT', 'DE']:
            for path in directory.glob('custom-*' + country + '-*.channels.xml'):
                for channel in ET.parse(path).getroot():
                    self.assertTrue(channel.get('xmltv_id'), (path, channel.text))
        channels = {c.get('site_id'): c.get('xmltv_id') for c in ET.parse(directory / 'custom-IT-guidatv.sky.it.channels.xml').getroot()}
        self.assertEqual(channels['DTH#319'], 'LA7.it')
        self.assertEqual(channels['DTH#9097'], 'SkySportUno.it')
        channels = {c.get('site_id'): c.get('xmltv_id') for c in ET.parse(directory / 'custom-premium-DE-web.magentatv.de.channels.xml').getroot()}
        self.assertEqual(channels['31'], 'SkySportTopEvent.de')
        self.assertEqual(channels['192'], 'SkySport1.de')
        self.assertEqual(channels['5555'], 'SkySportPremierLeague.de')

    def test_canal_sport_and_sport_360_are_not_aliases(self):
        targets, raw, _ = load_targets()
        for name, target in [('FR-SP:Canal+Sport', 'FR:CanalPlusSport.fr'), ('FR-SP:Canal+ Sport 360', 'FR:CanalPlusSport360.fr')]:
            row = map_row(dict(uhf_pk='1', category='French Sports', name=name, original_name=name), targets, raw)
            self.assertEqual(row['target_xmltv_id'], target)

    def test_country_refresh_routes_shared_and_current_html_fetchers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ['FR-tv.sfr.fr', 'IT-superguidatv.it', 'IT-guidatv.sky.it', 'US-test']:
                (root / f'custom-{name}.channels.xml').write_text('<channels>' + '<channel xmltv_id="test"/>' * 12 + '</channels>')
            with (patch.object(refresh_epg, 'SOURCES_DIR', root), patch.object(refresh_epg, 'EPG_DIR', root),
                  patch.object(refresh_epg, 'NORMALIZED_DIR', root / 'normalized'),
                  patch.object(refresh_epg, 'WEB_DATA_DIR', root / 'web'), patch.object(refresh_epg, 'run') as run,
                  patch('sys.argv', ['refresh_epg.py', '--countries', 'FR', 'IT', '--skip-editor-picks'])):
                self.assertEqual(refresh_epg.main(), 0)
            grabs = [call for call in run.call_args_list if 'timeout' in call.kwargs]
            self.assertEqual(len(grabs), 3)
            self.assertEqual(grabs[0].args[0][:2], ['python3', 'scripts/grab_sfr_epg.py'])
            self.assertEqual(grabs[1].kwargs['timeout'], 480)
            for grab in grabs:
                command = grab.args[0]
                self.assertEqual(command[command.index('--days') + 1], '4')
            self.assertEqual(grabs[2].args[0][:2], ['python3', 'scripts/grab_superguida_epg.py'])
            self.assertFalse(any('scripts/build_editor_picks.py' in call.args[0] for call in run.call_args_list))
