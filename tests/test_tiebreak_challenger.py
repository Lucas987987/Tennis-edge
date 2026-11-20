import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import lignes_algo as LA  # noqa: E402
import etude_tiebreaks as ET  # noqa: E402


class TestTiebreakChallenger(unittest.TestCase):
    def test_correction_seulement_challenger(self):
        q = LA.tiebreak_corrige(0.30, 'CH')
        self.assertGreater(q, 0.30)
        self.assertLess(q, 0.35)
        self.assertIsNone(LA.tiebreak_corrige(0.30, 'ATP'))

    def test_appliquee_si_adoptee(self):
        L = {'tie_break': 0.30}
        self.assertEqual(LA.appliquer_tiebreak(L, 'CH', []), L)
        r = LA.appliquer_tiebreak(L, 'CH', ['CH'])
        self.assertEqual(r['tie_break_brut'], 0.30)
        self.assertGreater(r['tie_break'], 0.30)

    def test_adopte_directement_sur_challenger(self):
        import tempfile, json
        import fantomes_circuits as FC
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            with open(os.path.join(d, 'simulateur', 'rapport_tiebreaks.json'), 'w') as f:
                json.dump({'circuits': {'CH': {'retenu_pour_fantome': True}, 'ATP': {'retenu_pour_fantome': False}}}, f)
            self.assertEqual(FC.lire(d).get('tiebreak'), ['CH'])
            with open(os.path.join(d, FC.SORTIE), 'w') as f:
                json.dump({'decisions': {'tiebreak|CH': {'adopte': False, 'retire': True, 'depuis': '2026-11-23'}}}, f)
            self.assertIsNone(FC.lire(d).get('tiebreak'))                    # retiré par la règle cumulée : il le reste
            with open(os.path.join(d, FC.SORTIE), 'w') as f:
                json.dump({'decisions': {'tiebreak|CH': {'adopte': False, 'retire': True}}}, f)
            self.assertEqual(FC.lire(d).get('tiebreak'), ['CH'])             # 12/11/2026 : retrait de l'ancienne règle annulé

    def test_calcul_rapide_egal_modele(self):
        import modele as M
        a, b = M.ancrer_forme(0.66, 0.62, 0.6, 2, 0.15, iterations=20)
        self.assertAlmostEqual(ET.p_tiebreak_match(a, b, 0.15), M.match_forme(a, b, 2, 0.15)['tiebreak'], places=3)


if __name__ == '__main__':
    unittest.main()


class TestRejeuSurLEloDeProduction(unittest.TestCase):
    """12/11/2026 (paquet 233) — l'étude est rejouée avec l'Elo du site ; le décalage en place est celui du rapport."""

    def test_le_decalage_en_place_est_celui_du_rapport(self):
        import json
        racine = os.path.join(os.path.dirname(__file__), '..')
        with open(os.path.join(racine, 'simulateur', 'rapport_tiebreaks.json'), encoding='utf-8') as f:
            R = json.load(f)
        self.assertIn('elo.de_production', R['elo'])
        retenus = {c: v['delta_appris'] for c, v in R['circuits'].items() if v['retenu_pour_fantome']}
        self.assertEqual(LA.DECALAGE_TIEBREAK, retenus)

    def test_l_etude_ne_cree_plus_d_elo_sans_reglage(self):
        with open(ET.__file__, encoding='utf-8') as f:
            src = f.read()
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
