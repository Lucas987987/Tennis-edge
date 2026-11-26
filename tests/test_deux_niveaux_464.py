"""26/11/2026 (paquet 464) : deux niveaux de fiabilité mesurés (fragile / normal) et études qui lisent vraiment les
résultats ITF hommes (scripts/feuilles_match.py dans chaque sparse-checkout qui prend scripts/resultats_itf.py)."""
import glob
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import note_par_match as NP  # noqa: E402


class DeuxNiveaux(unittest.TestCase):
    def test_seuil(self):
        self.assertEqual(NP.niveau_mesure(0.80), 'fragile')
        self.assertEqual(NP.niveau_mesure(0.949), 'fragile')
        self.assertEqual(NP.niveau_mesure(0.95), 'normal')
        self.assertEqual(NP.niveau_mesure(1.30), 'normal')       # « nos % trop prudents » ne se vérifie pas : normal

    def test_evaluer_match_donne_le_niveau(self):
        M = {'pentes_base': {'CH': {'0': 1.0, '_circuit': 1.0}}, 'effets': {'beta': {'huitiemes': -0.2}, 'gamma': {}}}
        a = NP.evaluer_match(M, 'CH', 10, {'huitiemes': 1})
        self.assertEqual(a['niveau_mesure'], 'fragile')
        self.assertEqual(NP.evaluer_match(M, 'CH', 10, {'huitiemes': 0})['niveau_mesure'], 'normal')

    def test_suivi_et_candidat_jamais_auto(self):
        L = [{'z': 1.0 if i % 3 else -1.0, 'a_nouvelle': 0.8 if i % 2 else 1.1} for i in range(120)]
        d = NP.suivi_deux_niveaux(L)
        self.assertEqual(d['fragile']['matchs'] + d['normal']['matchs'], 120)
        self.assertFalse(d['candidat_pente_fragiles']['a_proposer'])          # moins de 1 000 matchs
        self.assertIn('jamais appliqué automatiquement', d['candidat_pente_fragiles']['regle'])

    def test_pentes_ch_avec_itf(self):
        M = NP.charger(RACINE)
        self.assertEqual(M['pentes_base']['CH'], {'0': 1.092, '1': 1.075, '2': 1.103, '3': 0.892, '_circuit': 1.078})

    def test_page_deux_niveaux(self):
        page = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn('data-fniv="normal"', page)
        for k in ('solide', 'correct', 'prudent'):
            self.assertNotIn(f'data-fniv="{k}"', page)
        self.assertNotIn('marché', page[page.index('fiab_aide:'):page.index('fiab_aide:') + 900])


class EtudesAvecITF(unittest.TestCase):
    def test_sparse_checkout_complet(self):
        for f in glob.glob(os.path.join(RACINE, '.github', 'workflows', '*.yml')):
            s = open(f, encoding='utf-8').read()
            if 'scripts/resultats_itf.py' in s and 'sparse-checkout' in s:
                self.assertIn('scripts/feuilles_match.py', s, os.path.basename(f))


if __name__ == '__main__':
    unittest.main()
