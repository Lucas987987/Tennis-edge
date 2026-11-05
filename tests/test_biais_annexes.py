"""Points de vigilance (05/11/2026) : biais des prévisions annexes signalés par circuit."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import biais_annexes as BA  # noqa: E402


def m(st, prevu, reel, dans):
    x = {'prevu': prevu, 'reel': reel, 'dans': dans, 'bas': 0, 'haut': 0}
    return {'diagnostic': {'stats': {st: {'home': x, 'away': x}}}}


class Biais(unittest.TestCase):
    def test_stat_sous_estimee_et_fourchette_etroite(self):
        M = [m('premiere_pct', 60.0, 64.0 + (i % 3), i % 10 < 6) for i in range(150)]
        s = BA.stats_circuit(M)['premiere_pct']
        self.assertTrue(s['signal'])
        self.assertEqual(s['sens'], 'sous-estimé')
        self.assertEqual(s['fourchette'], 'trop étroite')

    def test_stat_juste_non_signalee(self):
        M = [m('aces', 5.0, 5.0 + (1 if i % 2 else -1), i % 10 < 8) for i in range(150)]
        self.assertFalse(BA.stats_circuit(M)['aces']['signal'])

    def test_vigilance_fiche(self):
        doc = {'circuits': {'ATP': {'stats': {'premiere_pct': {'signal': True, 'sens': 'sous-estimé', 'biais': 3.9,
                                                               'fourchette': 'trop étroite', 'dans_fourchette_pct': 70.2},
                                              'breaks': {'signal': True, 'sens': None, 'biais': -0.2,
                                                         'fourchette': 'trop large', 'dans_fourchette_pct': 92.0}},
                                    'lignes': {'tie_break': {'signal': True, 'prevu_pct': 44.0, 'reel_pct': 52.0}}}}}
        v = BA.vigilance(doc, 'ATP', [40, 300])
        cles = [x.get('cle') or x['type'] for x in v]
        self.assertIn('premiere_pct', cles)
        self.assertNotIn('breaks', cles)                  # fourchette trop large : pas de surprise à craindre
        self.assertIn('tie_break', cles)
        self.assertIn('experience', cles)
        self.assertEqual(BA.vigilance(doc, 'WTA', [300, 300]), [])


if __name__ == '__main__':
    unittest.main()
