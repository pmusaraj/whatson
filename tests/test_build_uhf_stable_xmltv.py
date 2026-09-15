import unittest
from xml.etree import ElementTree as ET

from scripts.build_uhf_custom_xmltv import build_stable_xmltv


class StableXmltvTest(unittest.TestCase):
    def test_playlist_variants_share_stable_schedule_and_keep_name_aliases(self):
        root = ET.fromstring('''<tv>
          <channel id="uhf:1"><display-name>Canada- TSN 1</display-name><display-name>CA</display-name></channel>
          <channel id="uhf:99"><display-name>TSN1 HD</display-name><display-name>CA</display-name></channel>
          <programme channel="uhf:1" start="20260915170000 +0000" stop="20260915180000 +0000"><title>Sports</title></programme>
          <programme channel="uhf:99" start="20260915170000 +0000" stop="20260915180000 +0000"><title>Sports</title></programme>
        </tv>''')
        rows = [{"custom_xmltv_id": f"uhf:{pk}", "target_xmltv_id": "CA:TSN1.ca", "target_country": "CA"}
                for pk in (1, 99)]
        result = build_stable_xmltv(ET.ElementTree(root), rows).getroot()
        self.assertEqual([c.get("id") for c in result.findall("channel")], ["CA:TSN1.ca"])
        self.assertEqual([n.text for n in result.findall("channel/display-name")], ["Canada- TSN 1", "TSN1 HD"])
        self.assertEqual([p.get("channel") for p in result.findall("programme")], ["CA:TSN1.ca"])
        self.assertEqual(root.find("programme").get("channel"), "uhf:1")


if __name__ == "__main__":
    unittest.main()
