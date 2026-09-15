import unittest
from datetime import date
from xml.etree import ElementTree as ET

from scripts.grab_movistar_epg import build_guide, parse_schedule


def page(*entries):
    return '<html><li class="title">Navigation, not a programme</li>' + ''.join(
        f'<div class="container_box"><div><li class="title">{title}</li>'
        f'<li class="genre">Deportes</li><li class="time">{clock}</li></div></div>'
        for clock, title in entries) + '</html>'


class MovistarGuideTest(unittest.TestCase):
    def test_midnight_rollover_and_next_day_supply_real_stop_times(self):
        first = parse_schedule(page(('23:30', 'Golf &amp; highlights'), ('00:30', 'Late show')), date(2026, 9, 15))
        second = parse_schedule(page(('00:30', 'Late show'), ('02:00', 'Overnight')), date(2026, 9, 16))
        channels = ET.fromstring('<channels><channel xmltv_id="Golf.es">Golf</channel></channels>')
        root = build_guide(channels, [('Golf.es', first), ('Golf.es', second)], date(2026, 9, 17)).getroot()
        programmes = root.findall('programme')
        self.assertEqual([p.findtext('title') for p in programmes], ['Golf & highlights', 'Late show'])
        self.assertEqual(programmes[0].get('start'), '20260915213000 +0000')
        self.assertEqual(programmes[1].get('stop'), '20260916000000 +0000')

    def test_autumn_clock_change_does_not_roll_into_tomorrow(self):
        entries = parse_schedule(page(('02:30', 'First'), ('02:00', 'Second'), ('03:00', 'Third')), date(2026, 10, 25))
        self.assertEqual([x['start'].strftime('%Y%m%d%H%M') for x in entries],
                         ['202610250030', '202610250100', '202610250200'])

    def test_empty_or_changed_page_fails_instead_of_empty_export(self):
        with self.assertRaises(ValueError):
            parse_schedule('<html>Temporarily unavailable</html>', date(2026, 9, 15))


if __name__ == '__main__':
    unittest.main()
