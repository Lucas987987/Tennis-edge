# 06/11/2026 (paquet 208) — infos des tournois : lieu hôte, dotation ; lieu hôte prioritaire ; groupe « dotation ».
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import tournois_infos as TI  # noqa: E402
import lieux_tournois as LT  # noqa: E402

# format réel relevé par la sonde du 06/11/2026 (Masters de Paris)
SAISON = {"info": {"season": {"name": "ATP Paris, France Men Singles 2026", "year": "2026", "id": 82442},
                   "hostCities": ["Paris"], "numberOfCompetitors": 57, "totalPrizeMoney": 6309095,
                   "totalPrizeMoneyCurrency": "€", "hostCountries": ["France"], "hostCity": "Paris",
                   "totalPrizeMoneyRaw": {"value": 6309095, "currency": "€"}}}


class TestInfos(unittest.TestCase):
    def test_fiche_saison(self):
        f = TI.fiche_saison(SAISON)
        self.assertEqual((f['ville'], f['pays'], f['joueurs']), ('Paris', 'France', 57))
        self.assertEqual(f['dotation_usd'], round(6309095 * 1.08))
        self.assertIsNone(TI.fiche_saison({}))
        self.assertIsNone(TI.dotation_usd(1000, 'XYZ'))

    def test_saison_de_l_annee(self):
        doc = {'seasons': [{'year': '2026', 'id': 9}, {'year': '2025', 'id': 8}]}
        self.assertEqual(TI.saison_de_l_annee(doc, '2025'), 8)
        self.assertIsNone(TI.saison_de_l_annee(doc, '2024'))

    def test_lieu_hote_prioritaire(self):
        infos = {'2404': {'nom': 'Paris', '2025': {'ville': 'Paris', 'pays': 'France'}, '2026': {'essais': 1}}}
        self.assertEqual(LT.lieu_hote(infos, 2404), ('Paris', 'France'))
        self.assertEqual(LT.lieu_hote(infos, 1), (None, None))

    def test_facteurs_lit_les_dotations(self):
        import facteurs as FA
        self.assertIn('dotation', FA.GROUPES)
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'feuilles'))
            with open(os.path.join(d, 'feuilles', 'tournois_infos.json'), 'w', encoding='utf-8') as f:
                json.dump({'2404': {'nom': 'Paris', '2026': {'dotation_usd': 6800000}}}, f)
            T, M = FA.charger_lieux(d)
            self.assertEqual(T['2404']['dotations'], {'2026': 6800000})
            self.assertEqual(M, {})

    def test_variables_dotation(self):
        import facteurs as FA
        H, t = FA.Historique(), 1793000000
        H.lieux = {'1': {'dotations': {'2026': 1e6}}, '2': {'dotations': {'2026': 1e5}}}
        H.parcours['a'].append((t - 5 * 86400, '2'))          # vient d'un tournoi 10 fois moins doté
        v = H.variables('a', 'b', '1', t, {})
        self.assertAlmostEqual(v['dotation_niveau'], 0.5)
        self.assertAlmostEqual(v['dot_ecart_srv'], 1.0)
        self.assertEqual(v['dot_ecart_adv'], 0.0)
        v = H.variables('a', 'b', 'inconnu', t, {})
        self.assertEqual((v['dotation_niveau'], v['dot_ecart_srv']), (0.0, 0.0))


if __name__ == '__main__':
    unittest.main()
