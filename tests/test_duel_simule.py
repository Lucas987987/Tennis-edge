"""Paquet 455 : le duel service / retour tiré de la simulation du match (choix de Lucas), au lieu de la différence de
deux classements sur 100 qui pouvait contredire la simulation (Kicker – Moller du 25/11)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import cartes_joueurs as CJ  # noqa: E402
import match_simule as MS  # noqa: E402
import vitrine as V  # noqa: E402


class DuelSimule(unittest.TestCase):
    def test_feuille_de_la_simulation(self):
        self.assertIn('points_service_pct', MS.CLES_FEUILLE)
        self.assertIn('points_service_pct', V.CLES_PLUS)
        st = [0] * 12
        st[MS.SVPT], st[MS.IN1], st[MS.W1], st[MS.W2] = 100, 60, 45, 15
        self.assertEqual(MS.feuille_derivee(st, [0] * 12)['points_service_pct'], 60.0)

    def test_duel_tire_de_la_simulation(self):
        ligne = {'circuit': 'CH', 'surface': 'Clay',
                 'feuille_prevue': [{'jeux_service_gagnes_pct': 52.7}, {'jeux_service_gagnes_pct': 67.4}],
                 'feuille_plus': [{'points_service_pct': [51.2, 45.0, 57.0]}, {'points_service_pct': [57.8, 51.0, 64.0]}]}
        d = CJ.duel_simule(ligne, 60.5)
        self.assertEqual(d['source'], 'simulation')
        self.assertTrue(d['descriptif_seulement'])
        self.assertEqual([j['points_service_pct'] for j in d['joueurs']], [51.2, 57.8])
        self.assertEqual(d['ecarts'], [-9.3, -2.7])
        self.assertEqual(d['joueurs'][1]['jeux_service_gagnes_pct'], 67.4)

    def test_sans_simulation_pas_de_duel(self):
        self.assertIsNone(CJ.duel_simule({'feuille_plus': [{}, {}]}, 60.5))
        self.assertIsNone(CJ.duel_simule({}, None))

    def test_site_et_textes(self):
        h = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('function duelSimTexte(ds, N)', h)
        self.assertIn('${m.duel_simule ? rendDuelSim(m.duel_simule,m) : rendDuel(m.duel,m)}', h)
        self.assertIn("const du = dsT ? null : m.duel;", h)                  # analyse complète : plus de « Avantage : N points »


if __name__ == '__main__':
    unittest.main()
