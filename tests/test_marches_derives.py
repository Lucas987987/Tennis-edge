"""Marchés dérivés (21/10/2026) : gardés depuis la MÊME réponse historique
(0 requête de plus), format compact, jamais de cote d'après le début."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import marches_derives as md  # noqa: E402
import oddspapi_v5 as ov  # noqa: E402

DEBUT = dt.datetime(2026, 10, 19, 9, 15)
ms = lambda d: str(int(d.replace(tzinfo=dt.timezone.utc).timestamp() * 1000))


def serie(oid, mid, pts):
    return {ms(DEBUT - dt.timedelta(minutes=m)): {'outcomeId': oid, 'marketId': mid, 'price': p, 'mainLine': ml}
            for m, p, ml in pts}


TABLE = {
    '121': {'marketName': 'Winner', 'handicap': 0.0, 'outcomes': {'121': '1', '122': '2'}},
    '12231': {'marketName': 'Total Sets Over Under', 'handicap': 2.5, 'outcomes': {'12231': 'Over', '12232': 'Under'}},
    '12239': {'marketName': 'Set Handicap', 'handicap': -1.5, 'outcomes': {'12239': '1', '12240': '2'}},
    '1241': {'marketName': 'Total Games Over Under', 'handicap': 23.5, 'outcomes': {'1241': 'Over', '1242': 'Under'}},
}
DATA = {'odds': {'pinnacle': {
    'a': serie(121, 121, [(600, 1.70, True), (10, 1.72, True)]),
    'a2': serie(122, 121, [(600, 2.20, True), (10, 2.18, True)]),
    'b': serie(12231, 12231, [(600, 2.10, True), (45, 2.18, True), (5, 2.20, True), (-20, 3.50, True)]),   # -20 = après le début
    'c': serie(12232, 12231, [(600, 1.70, True), (45, 1.66, True), (5, 1.65, True)]),
    'd': serie(12239, 12239, [(300, 2.86, True)]),
    'e': serie(1241, 1241, [(200, 1.917, False), (40, 1.95, True)]),
    'f': serie(99999, 99999, [(100, 1.5, True)]),                       # marché inconnu : ignoré
}}}


class MarchesDerives(unittest.TestCase):
    def test_resume_compact_sans_cote_d_apres_le_debut(self):
        r = md.resumer(DATA, 'pinnacle', TABLE, DEBUT)
        self.assertEqual(set(r), {'total_sets 2.5', 'handicap_sets -1.5', 'total_jeux 23.5'})
        o = r['total_sets 2.5']['Over']
        self.assertEqual((o['ouverture'], o['a_30min'], o['cloture'], o['points']), (2.10, 2.18, 2.20, 4))
        self.assertEqual(r['total_sets 2.5']['Under']['cloture'], 1.65)
        self.assertTrue(r['total_jeux 23.5']['Over']['principale'])
        self.assertIsNone(r['handicap_sets -1.5'].get('2'))
        json.dumps(md.ligne('u', 'f', 'pinnacle', {'home': 'Rune'}, DEBUT, r))     # sérialisable

    def test_table_demandee_une_seule_fois(self):
        appels = []
        brut = [{'marketId': 12231, 'marketName': 'Total Sets Over Under', 'handicap': 2.5,
                 'outcomes': [{'outcomeId': 12231, 'outcomeName': 'Over'}, {'outcomeId': 12232, 'outcomeName': 'Under'}]}]
        with tempfile.TemporaryDirectory() as d:
            ch = os.path.join(d, 't.json')
            t1 = md.charger_table(ch, lambda: appels.append(1) or brut)
            t2 = md.charger_table(ch, lambda: appels.append(1) or brut)
        self.assertEqual(len(appels), 1)
        self.assertEqual(t1, t2)
        self.assertEqual(t1['12231']['outcomes']['12232'], 'Under')

    def test_une_seule_requete_pour_tout(self):
        appels = []
        orig = ov.historical
        ov.historical = lambda fid, book='pinnacle': appels.append((fid, book)) or DATA
        try:
            c, brut = ov.historical_curves_et_brut('f1', 'pinnacle', (ov.OUT_HOME, ov.OUT_AWAY), with_limit=True)
        finally:
            ov.historical = orig
        self.assertEqual(appels, [('f1', 'pinnacle')])
        self.assertEqual(sorted(c), [121, 122])
        self.assertIs(brut, DATA)
        self.assertEqual(c, ov.courbes_depuis(DATA, 'pinnacle', (ov.OUT_HOME, ov.OUT_AWAY), True))


if __name__ == '__main__':
    unittest.main()
