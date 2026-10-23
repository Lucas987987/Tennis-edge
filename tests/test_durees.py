"""Durée des matchs (23/10/2026) : complément des feuilles déjà collectées, variables de fatigue."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import durees_matchs as DM  # noqa: E402
import facteurs as FA  # noqa: E402


class Faux:
    def __init__(self):
        self.n = 0

    def get(self, chemin):
        self.n += 1
        if '/categories' in chemin:
            return 200, {'categories': [{'category': {'id': 3, 'name': 'ATP'}, 'totalEvents': 1}]}
        return 200, {'events': [{'id': 1, 'time': {'period1': 3000, 'period2': 3600}}, {'id': 2, 'time': {}}]}


class Durees(unittest.TestCase):
    def test_completer(self):
        with tempfile.TemporaryDirectory() as d:
            old = DM.FM.DOSSIER
            DM.FM.DOSSIER = d
            try:
                with gzip.open(os.path.join(d, '2026-07-01.jsonl.gz'), 'wt', encoding='utf-8') as f:
                    for i in (1, 2):
                        f.write(json.dumps({'id': i, 'jour': '2026-07-01', 'rang': None}) + '\n')
                c = Faux()
                self.assertEqual(DM.completer_jour(c, '2026-07-01'), 1)
                recs = DM.FM.lire_jour('2026-07-01', d)
                self.assertEqual((recs[1]['duree_min'], recs[2]['duree_min']), (110, None))
                self.assertIsNone(DM.completer_jour(c, '2026-07-01'))          # jour déjà traité : aucune requête
                self.assertEqual(c.n, 2)
            finally:
                DM.FM.DOSSIER = old

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
