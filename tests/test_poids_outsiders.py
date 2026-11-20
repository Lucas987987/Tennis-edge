"""Paquet 273 : poids du mélange propres à l'ATP (255 B) avec retrait ; étude des outsiders qui gagnent."""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import pronostics_du_jour as P  # noqa: E402
import poids_circuit as PC  # noqa: E402
import etude_outsiders_gagnants as OG  # noqa: E402


class Poids(unittest.TestCase):
    def test_atp_seulement(self):
        self.assertEqual(P.charger_poids_circuit(str(RACINE)), {'ATP': {'elo': 0.7339, 'simulation': 0.3036}})

    def test_poids_de(self):
        ancien = P.COMBINAISON, P.POIDS_CIRCUIT
        try:
            P.COMBINAISON = {'elo': 0.7815, 'simulation': 0.2378}
            P.POIDS_CIRCUIT = {'ATP': {'elo': 0.7339, 'simulation': 0.3036}}
            self.assertEqual(P.poids_de('WTA'), {'elo': 0.7815, 'simulation': 0.2378})
            a = P.poids_de('ATP')
            self.assertEqual((a['elo'], a['simulation']), (0.7339, 0.3036))
        finally:
            P.COMBINAISON, P.POIDS_CIRCUIT = ancien

    def test_retire_n_est_plus_lu(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            json.dump({'circuits': {'ATP': {'elo': .7, 'simulation': .3, 'retire': True}}},
                      open(os.path.join(d, 'simulateur', 'poids_circuit.json'), 'w'))
            self.assertEqual(P.charger_poids_circuit(d), {})

    def _racine(self, d, n, avec, communs, gagne):
        os.makedirs(os.path.join(d, 'simulateur')); os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        json.dump({'circuits': {'ATP': {'elo': .7339, 'simulation': .3036, 'retire': False}}},
                  open(os.path.join(d, 'simulateur', 'poids_circuit.json'), 'w'))
        R = [{'circuit': 'ATP', 'reel': {'gagnant': 'home' if gagne(k) else 'away', 'interrompu': None},
              'fiabilite': {'poids_circuit': {'circuit': 'ATP', 'p_home_avec': avec, 'p_home_poids_communs': communs}}}
             for k in range(n)]
        json.dump({'matchs': R}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))

    def test_regle_de_retrait(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, .75, .70, lambda k: k % 10 < 6)            # réel 60 % : les poids ATP font pire
            r, nouveau = PC.suivi(d)
            self.assertEqual(r['ATP']['verdict'], 'retirés')
            self.assertTrue(nouveau['circuits']['ATP']['retire'])
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, .75, .70, lambda k: k % 20 < 15)           # réel 75 % : ils font mieux
            self.assertEqual(PC.suivi(d)[0]['ATP']['verdict'], 'gardés')
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 150, .75, .70, lambda k: k % 10 < 6)
            self.assertEqual(PC.suivi(d)[0]['ATP']['verdict'], 'trop tôt')

    def test_les_deux_pourcentages_sont_gardes(self):
        src = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertIn("combinaison['poids_circuit'] = {'circuit': c, 'poids': POIDS_CIRCUIT[c], 'p_home_avec': combinaison['p_home'],", src)
        self.assertIn("m['fiabilite'] = dict(m['fiabilite'], poids_circuit=pc_)", src)


class Outsiders(unittest.TestCase):
    def test_regle_ecrite_et_situations(self):
        self.assertIn('RÈGLE ÉCRITE LE 18/11/2026, AVANT DE REGARDER LES RÉSULTATS', OG.__doc__)
        self.assertEqual((OG.MIN_JUGES, OG.MARGE, OG.MIN_ERREURS_TYPES), (1000, 0.001, 2.0))
        o = {'long': False, 'court': True, 'serie': 5, 'titre_premier': False, 'domicile': True, 'gaucher': True,
             'droitier': False, 'rang': 80}
        f = {'long': True, 'court': False, 'serie': 0, 'titre_premier': True, 'domicile': False, 'gaucher': False,
             'droitier': True, 'rang': 120}
        for nom in OG.SITUATIONS:
            self.assertTrue(OG.situation(nom, o, f), nom)
            self.assertFalse(OG.situation(nom, f, o), nom)

    def test_cas_outsider_entre_15_et_45(self):
        v = {'long': True, 'court': True, 'serie': 0, 'titre_premier': False, 'domicile': False, 'gaucher': False,
             'droitier': True, 'rang': None}
        r = {'zb': math.log(0.3 / 0.7), 'vg': dict(v, rang=50), 'vp': dict(v, rang=100)}   # le vainqueur est l'outsider (30 %)
        sg, p_out, y = OG.cas(r, 'outsider_mieux_classe')
        self.assertEqual((sg, y), (1.0, 1))
        self.assertAlmostEqual(p_out, 0.3)
        r['zb'] = math.log(0.9 / 0.1)
        self.assertIsNone(OG.cas(r, 'outsider_mieux_classe'))                # outsider à 10 % : hors champ

    def test_rapport_public(self):
        doc = json.load(open(RACINE / 'simulateur' / 'rapport_outsiders_gagnants.json', encoding='utf-8'))
        self.assertEqual(sorted(doc['retenus']), ['favori_fatigue · CH', 'outsider_mieux_classe · CH'])
        t = json.dumps(doc, ensure_ascii=False)
        for interdit in ('cote', 'Pinnacle', 'march'):
            self.assertNotIn(interdit, t)


if __name__ == '__main__':
    unittest.main()
