"""Facteurs jugés par circuit et groupe « voyage » (06/11/2026, paquet 199)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import facteurs as FA  # noqa: E402


class Voyage(unittest.TestCase):
    def test_distance(self):
        self.assertAlmostEqual(FA.distance_km(48.86, 2.35, 51.51, -0.13), 344, delta=5)      # Paris – Londres
        self.assertAlmostEqual(FA.distance_km(0, 0, 0, 180), 20015, delta=10)

    def test_variables(self):
        H = FA.Historique()
        H.lieux = {'bogota': {'lat': 4.71, 'lon': -74.07}, 'lisbonne': {'lat': 38.72, 'lon': -9.14}}
        H.parcours['a'] = [(0, 'bogota')]
        v = H.variables('a', 'b', 'lisbonne', 4 * 86400, {})
        self.assertAlmostEqual(v['voyage_km_srv'], FA.distance_km(4.71, -74.07, 38.72, -9.14) / 5000, places=6)
        self.assertGreater(v['voyage_srv'], 0.6)
        self.assertEqual(v['voyage_km_adv'], 0.0)
        v2 = H.variables('a', 'b', 'lisbonne', 12 * 86400, {})                              # plus de 10 jours : rien
        self.assertEqual(v2['voyage_km_srv'], 0.0)
        self.assertIn('voyage', FA.GROUPES)


class ParCircuit(unittest.TestCase):
    def test_regle(self):
        vieux = FA.juger_groupe, FA.apprendre, FA.SORTIE
        import stabilite as ST
        vst = ST.lire, ST.ecrire, ST.decider
        try:
            FA.juger_groupe = lambda A, J, g: {'adopte': g == 'voyage' and A[0]['circuit'] == 'CH', 'raison': ''}
            FA.apprendre = lambda L, gs: {'service': {g: 1.0 for g in gs}}
            etat = {}
            ST.lire, ST.ecrire = (lambda: etat), (lambda e: None)
            ST.decider = lambda etat, cle, en_place, brut: (brut or en_place, 'test')
            with tempfile.TemporaryDirectory() as d:
                FA.SORTIE = os.path.join(d, 'facteurs.json')
                json.dump({'adoptes': ['forme_fatigue']}, open(FA.SORTIE, 'w'))
                appr = [{'circuit': 'CH'}] * 400 + [{'circuit': 'ATP'}] * 400 + [{'circuit': 'WTA'}] * 50
                juge = [{'circuit': 'CH'}] * 400 + [{'circuit': 'ATP'}] * 400 + [{'circuit': 'WTA'}] * 50
                out = FA.juger_par_circuit(appr, juge, {'adoptes': ['forme_fatigue']})
            # 06/11 (décision de Lucas) : premier verdict par circuit appliqué tout de suite, entrées comme sorties
            self.assertEqual(out['CH']['adoptes'], ['voyage'])
            self.assertEqual(out['ATP']['adoptes'], [])
            self.assertEqual(out['CH']['groupes']['voyage']['stabilite'], 'adoption directe (06/11)')
            self.assertIn('note', out['WTA'])                                               # trop petit : global
            self.assertEqual(etat['facteur:voyage:CH']['adopte'], True)
            self.assertEqual(etat['facteur:forme_fatigue:CH']['adopte'], False)
        finally:
            FA.juger_groupe, FA.apprendre, FA.SORTIE = vieux
            ST.lire, ST.ecrire, ST.decider = vst

    def test_application(self):
        import pronostics_du_jour as PJ
        vieux = PJ.FACTEURS
        try:
            PJ.FACTEURS = {'adoptes': ['a'], 'coefs': {'service': {'x': 1}},
                           'par_circuit': {'CH': {'adoptes': ['b'], 'coefs': {'service': {'y': 2}}, 'groupes': {}},
                                           'WTA': {'adoptes': ['a'], 'note': 'trop peu'}}}
            self.assertEqual(PJ.facteurs_en_place('CH'), (['b'], {'service': {'y': 2}}))
            self.assertEqual(PJ.facteurs_en_place('WTA'), (['a'], {'service': {'x': 1}}))
            self.assertEqual(PJ.facteurs_en_place('ATP'), (['a'], {'service': {'x': 1}}))
        finally:
            PJ.FACTEURS = vieux


if __name__ == '__main__':
    unittest.main()
