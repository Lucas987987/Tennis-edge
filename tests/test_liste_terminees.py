"""Paquet 271 : un match commencé depuis plus de 3 h et absent du direct va dans « Matchs terminés » (replié)."""
import re
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'algo' / 'index.html').read_text(encoding='utf-8')


class Terminees(unittest.TestCase):
    def test_trois_heures_sans_direct(self):
        self.assertIn("|| (!LIVE.par_uid[m.uid] && Date.now() - utc(m.debut).getTime() > 3 * 3600e3);", HTML)

    def test_replie_par_defaut(self):
        self.assertRegex(HTML, re.escape("<details ${etaitOuvert?'open':''}>"))
        self.assertIn("const etaitOuvert = !!document.querySelector('#list .finished-group details[open]');", HTML)


    def test_journal_replie_par_defaut(self):
        self.assertIn('<details class="jc-pli"${ouvert?\' open\':\'\'}>', HTML)
        self.assertIn("const ouvert = !!el.querySelector('details.jc-pli[open]');", HTML)


if __name__ == '__main__':
    unittest.main()
