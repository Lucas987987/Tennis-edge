"""26/11/2026 (paquet 468) : le tableau public « Réussite par niveau de fiabilité » ne montre plus que « normal » et
« fragile » : tous nos matchs terminés classés hors échantillon (note_par_match.reference_deux_niveaux) et, à côté, les
niveaux annoncés avant le match depuis le 26/11."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import note_par_match as NP  # noqa: E402
import vitrine as V  # noqa: E402


def m(niv, p, gagnant, d='2026-11-27T10:00'):
    return {'circuit': 'CH', 'debut': d, 'home': 'A', 'away': 'B', 'p_affiche': p, 'fiabilite': {'niveau': niv},
            'reel': {'gagnant': gagnant}, 'premier': {'combinaison': {'p_home': p}}}


class Tableau(unittest.TestCase):
    def test_anciens_niveaux_retires_du_bilan(self):
        pf = V._par_fiabilite({'solide': [(.7, 1)], 'correct': [(.6, 0)], 'normal': [(.7, 1)], 'fragile': [(.6, 0)]})
        self.assertEqual(list(pf), ['normal', 'fragile'])

    def test_reference_hors_echantillon(self):
        import random
        rnd = random.Random(3)
        dec = {'pentes_base': {'CH': {'0': 1.0, '_circuit': 1.0}}, 'effets': {}}
        L = []
        for i in range(400):
            h = i % 2
            z = rnd.uniform(.1, 1.5) * (1 if rnd.random() < (.6 if h else .75) else -1)
            L.append({'c': 'CH', 'n': 10, 'z': z, 'crit': {'huitiemes': h}})
        ref = NP.reference_deux_niveaux(L, dec)
        self.assertEqual(ref['matchs'], 400)
        n = sum((ref.get(k) or {}).get('n', 0) for k in ('normal', 'fragile'))
        self.assertEqual(n, 400)                      # chaque match classé une fois, hors échantillon
        self.assertIn('CH', ref['par_circuit'])
        self.assertIsNone(NP.reference_deux_niveaux(L[:10], dec))

    def test_vitrine_lit_la_reference(self):
        r = V.fiabilite_reference(RACINE)
        self.assertIsNotNone(r)
        self.assertEqual(set(k for k in ('normal', 'fragile') if r.get(k)), {'normal', 'fragile'})
        self.assertNotIn('pente_reelle', r['normal'])

    def test_page(self):
        page = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
        i = page.index('function rendBilanFiab(PF, circ)')
        bloc = page[i:page.index('function rendSuivi')]
        self.assertIn("['normal','fragile']", bloc)
        self.assertNotIn("'solide'", bloc)
        self.assertIn('fiabilite_reference', bloc)


if __name__ == '__main__':
    unittest.main()
