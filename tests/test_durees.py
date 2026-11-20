"""Durées des matchs (23/10/2026 ; collecte corrigée le 28/10/2026) : détail TennisApi, rattrapage borné, variables
de fatigue."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import durees_matchs as D  # noqa: E402
import facteurs as FA  # noqa: E402
import feuilles_match as FM  # noqa: E402


class Client:
    def __init__(self, reponses):
        self.reponses, self.n = reponses, 0

    def get(self, chemin):
        self.n += 1
        return self.reponses(chemin)


def rec(i, cat='ATP', stats=True, **kw):
    return dict({'id': i, 'categorie': cat, 'stats': {'ALL': {}} if stats else None}, **kw)


class Durees(unittest.TestCase):
    def test_detail_et_liste(self):
        self.assertEqual(FM.duree_minutes({'event': {'time': {'period1': 3000, 'period2': 2400}}}), 90)
        self.assertEqual(FM.duree_minutes({'time': {'period1': 1800}}), 30)
        self.assertIsNone(FM.duree_minutes({'event': {}}))
        self.assertIsNone(FM.duree_minutes(None))

    def test_rattrapage_borne_et_itf_exclu(self):
        recs = {1: rec(1), 2: rec(2, cat='ITF Men'), 3: rec(3, stats=False), 4: rec(4, duree_min=80)}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(FM, 'DOSSIER', d):
            FM.ecrire_jour('2026-10-01', recs, d)
            c = Client(lambda ch: (200, {'event': {'time': {'period1': 3600}}}))
            cpt = {'essais': 0, 'trouves': 0}
            self.assertEqual(D.completer_jour(c, '2026-10-01', cpt), 1)
            self.assertEqual(c.n, 1)                                  # seul le match ATP avec feuille, sans durée
            relu = FM.lire_jour('2026-10-01', d)
            self.assertEqual(relu[1]['duree_min'], 60)
            self.assertEqual(relu[4]['duree_min'], 80)
            self.assertIsNone(D.completer_jour(c, '2026-10-01', cpt))   # plus rien à faire

    def test_format_inconnu_ne_consomme_rien(self):
        recs = {i: rec(i) for i in range(25)}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(FM, 'DOSSIER', d):
            FM.ecrire_jour('2026-10-02', recs, d)
            c = Client(lambda ch: (200, {'event': {'autre': 1}}))
            with self.assertRaises(D.FormatInconnu):
                D.completer_jour(c, '2026-10-02', {'essais': 0, 'trouves': 0})
            relu = FM.lire_jour('2026-10-02', d)
            self.assertTrue(all((r.get('duree_essai') or 0) == 0 for r in relu.values()))


class VariablesFatigue(unittest.TestCase):
    def test_variables(self):
        H = FA.Historique()
        J = 86400
        t = 1_790_000_000.0
        H.minutes['a'] = [(t - 1 * J, 180, '1'), (t - 2 * J, 60, '1'), (t - 5 * J, 200, '9'), (t - 9 * J, 90, '1')]
        v = H.variables('a', 'b', '1', t, {})
        self.assertAlmostEqual(v['minutes_tournoi_srv'], 3.3)                # tout le tournoi « 1 », 9 jours compris
        self.assertAlmostEqual(v['minutes7_srv'], 4.4)                       # 7 derniers jours, tous tournois
        self.assertAlmostEqual(v['minutes_dernier_srv'], 1.8)
        self.assertEqual(v['minutes7_adv'], 0.0)
        doc = json.loads(json.dumps(FA.contexte(H, {}, {}, t)))
        self.assertAlmostEqual(FA.Contexte(doc).variables('a', 'b', '1', t)['minutes_tournoi_srv'], 0.0)   # nom inconnu
        C = FA.Contexte(dict(doc, noms_tournois={'1': 'Ortisei, Italy'}))
        self.assertAlmostEqual(C.variables('a', 'b', 'Ortisei', t)['minutes_tournoi_srv'], 3.3)
        self.assertIn('duree', FA.GROUPES)


if __name__ == '__main__':
    unittest.main()
