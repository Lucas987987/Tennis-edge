"""H19 en direct : même règle que le Lab (gel lu et vérifié), décision à l'horizon,
un pari par joueur, commission, âge de cote, horizon manqué non alerté."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import h19_signal as h  # noqa: E402

# Pas de DRY_RUN dans l'environnement : il fuirait vers les autres tests
# (archive_ticks, restore_curves le lisent). On le pose sur le module seulement.
h.DRY_RUN = True

START = dt.datetime(2026, 10, 25, 15, 0)


def serie(*pts):
    return sorted((START - dt.timedelta(minutes=m), o) for m, o in pts)


def match(soft, book='bet365', tour='ATP Lyon'):
    fair = h.books.fair_close(2.0, 1.9)
    return {'_ct': START, '_home': 'Alpha Un', '_away': 'Beta Deux', '_tour': tour,
            'pinnacle': {'h': serie((400, 2.0), (65, 2.0), (12, 2.0)), 'a': serie((400, 1.9), (65, 1.9), (12, 1.9))},
            book: {'h': serie(*[(m, round(fair * (1 + e / 100), 3)) for m, e in soft]), 'a': serie((400, 1.8))}}


class Regle(unittest.TestCase):
    def setUp(self):
        self.R, self.sha = h.regle()

    def test_gel_lu_et_verifie(self):
        self.assertEqual(self.R['ecart_min_pct'], 2.0)
        self.assertIn('bet365', self.R['books'])

    def test_premier_horizon_un_seul_pari(self):
        g = {'m1': match([(370, 3.0), (70, 3.0)])}            # +3 % à 6 h et à 1 h
        etat, recs = {}, []
        t = START - dt.timedelta(minutes=400)
        while t < START:
            recs += h.traiter(g, etat, t, self.R, self.sha, ecrire=False)
            t += dt.timedelta(minutes=3)
        self.assertEqual(len(recs), 1)
        self.assertEqual((recs[0]['horizon'], recs[0]['book'], recs[0]['joueur']), ('6h', 'bet365', 'Alpha Un'))
        self.assertAlmostEqual(recs[0]['ecart_pct'], 3.0, delta=0.1)
        self.assertLess((dt.datetime.fromisoformat(recs[0]['signale_le'])
                         - dt.datetime.fromisoformat(recs[0]['detecte_le'])).total_seconds(), 3 * 60 + 1)

    def test_cote_trop_vieille_ou_hors_bande(self):
        for soft in ([(400, 3.0)], [(370, 9.0)], [(370, 1.0)]):   # 40 min avant la décision 6 h ; +9 % ; +1 %
            r = h.evaluer(match(soft), 'h', '6h', self.R)
            self.assertIsNone(r, soft)

    def test_commission_de_bourse(self):
        r = h.evaluer(match([(370, 3.0)], book='betfair-ex'), 'h', '6h', self.R)
        self.assertIsNone(r)                                    # +3 % brut, < +2 % net de 5 % de commission

    def test_horizon_manque_pas_alerte(self):
        g = {'m1': match([(370, 3.0)])}
        etat = {}
        recs = h.traiter(g, etat, START - dt.timedelta(minutes=300), self.R, self.sha, ecrire=False)
        self.assertEqual(recs, [])
        self.assertTrue(etat['m1|h']['manque'])

    def test_challenger_et_doubles(self):
        self.assertEqual(h.circuit('ATP Challenger Roanne'), 'Challenger')
        self.assertIsNone(h.circuit('ATP Lyon Doubles'))

    def test_gel_modifie_bloque(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'g.json')
            doc = json.load(open(h.GEL, encoding='utf-8'))
            doc['regle']['ecart_min_pct'] = 1.0
            json.dump(doc, open(p, 'w'))
            old = h.GEL
            h.GEL = p
            try:
                with self.assertRaises(SystemExit):
                    h.regle()
            finally:
                h.GEL = old


if __name__ == '__main__':
    unittest.main()
