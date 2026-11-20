"""H20 en direct (21/10/2026) : gel lu et vérifié, WTA, cote Pinnacle 2–3,19, mouvement de
probabilité +3,15 à +20 pts depuis le premier point Pinnacle, prix jouable obligatoire,
un pari par joueur au premier horizon ; même calcul que l'Explorateur et que le Lab."""
import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import h20_signal as h  # noqa: E402

h.DRY_RUN = True          # sur le module seulement (ne pas fuir vers les autres tests)
_sp = importlib.util.spec_from_file_location('tennis_edge_t_h20lab', os.path.join(ICI, '..', 'Tennis_Edge_Lab', 'h20.py'))
lab = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(lab)

START = dt.datetime(2026, 10, 25, 15, 0)


def serie(*pts):
    return sorted((START - dt.timedelta(minutes=m), o) for m, o in pts)


def match(pin_h, pin_a, soft=((370, 2.6),), book='bet365', tour='WTA Linz'):
    """pin_h / pin_a : [(minutes avant le début, cote)] ; soft : prix du book pour home."""
    return {'_ct': START, '_home': 'Alpha Un', '_away': 'Beta Deux', '_tour': tour,
            'pinnacle': {'h': serie(*pin_h), 'a': serie(*pin_a)},
            book: {'h': serie(*soft), 'a': serie((400, 1.5))}}


# Ouverture 2,90 / 1,42 (≈ 32 %), 6 h avant : 2,50 / 1,55 (≈ 38 %) : +6 pts, cote dans 2–3,19.
SOUTENU = dict(pin_h=[(2000, 2.90), (400, 2.50), (65, 2.50), (12, 2.50)],
               pin_a=[(2000, 1.42), (400, 1.55), (65, 1.55), (12, 1.55)])


class Regle(unittest.TestCase):
    def setUp(self):
        self.R, self.sha = h.regle()

    def test_gel_lu_et_verifie(self):
        self.assertEqual(self.R['circuits'], ['WTA'])
        self.assertEqual((self.R['cote_pin_min'], self.R['cote_pin_max']), (2.0, 3.19))
        self.assertEqual((self.R['ampleur_pts_min'], self.R['ampleur_pts_max']), (3.15, 20.0))
        self.assertEqual(lab.lire_gel(os.path.join(ICI, '..'))[1], self.sha)

    def test_detection_et_un_seul_pari(self):
        g = {'m1': match(**SOUTENU, soft=[(370, 2.6), (70, 2.6), (15, 2.6)])}
        etat, recs = {}, []
        t = START - dt.timedelta(minutes=400)
        while t < START:
            recs += h.traiter(g, etat, t, self.R, self.sha, ecrire=False)
            t += dt.timedelta(minutes=3)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual((r['horizon'], r['joueur'], r['book']), ('6h', 'Alpha Un', 'bet365'))
        attendu = 100 * (1 / h.books.fair_close(2.5, 1.55) - 1 / h.books.fair_close(2.9, 1.42))
        self.assertAlmostEqual(r['ampleur_pts'], attendu, places=3)
        self.assertGreater(r['ampleur_pts'], 3.15)

    def test_hors_regle(self):
        cas = [
            match(pin_h=[(2000, 2.6), (400, 2.6)], pin_a=[(2000, 1.5), (400, 1.5)]),     # aucun mouvement
            match(pin_h=[(2000, 2.0), (400, 2.6)], pin_a=[(2000, 1.8), (400, 1.5)]),     # mouvement contre lui
            match(pin_h=[(2000, 1.9), (400, 1.6)], pin_a=[(2000, 1.9), (400, 2.3)]),     # cote < 2
        ]
        for g in cas:
            self.assertIsNone(h.evaluer(g, 'h', '6h', self.R), g['_tour'])
        g = {'m1': match(**SOUTENU, tour='ATP Vienna')}                                   # pas WTA
        t = START - dt.timedelta(minutes=355)
        self.assertEqual(h.traiter(g, {}, t, self.R, self.sha, ecrire=False), [])
        g = {'m1': match(**SOUTENU)}
        self.assertEqual(len(h.traiter(g, {}, t, self.R, self.sha, ecrire=False)), 1)     # même match en WTA

    def test_sans_prix_jouable_compte_quand_meme(self):
        # comme l'Explorateur : la décision existe, sans prix d'entrée (pas de CLV mesurable)
        for g in (match(**SOUTENU, soft=[(420, 2.6)]), match(**SOUTENU, book='sbobet')):           # cote trop vieille ; book non jouable
            d = h.evaluer(g, 'h', '6h', self.R)
            self.assertIsNotNone(d)
            self.assertIsNone(d['book'])
            self.assertIn('Aucun book jouable', h.message(g, 'h', d, self.R, START - dt.timedelta(minutes=355)))

    def test_roi_toujours_affiche(self):
        g = match(**SOUTENU)
        d = h.evaluer(g, 'h', '6h', self.R)
        txt = h.message(g, 'h', d, self.R, START - dt.timedelta(minutes=355))
        self.assertIn('ROI', txt)
        self.assertIn('Suivi', txt)

    def test_horizon_manque_pas_alerte(self):
        g = {'m1': match(**SOUTENU)}
        etat = {}
        self.assertEqual(h.traiter(g, etat, START - dt.timedelta(minutes=300), self.R, self.sha, ecrire=False), [])
        self.assertTrue(etat['m1|h']['manque'])

    def test_gel_modifie_bloque(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'g.json')
            doc = json.load(open(h.GEL, encoding='utf-8'))
            doc['regle']['cote_pin_max'] = 4.0
            json.dump(doc, open(p, 'w'))
            old = h.GEL
            h.GEL = p
            try:
                with self.assertRaises(SystemExit):
                    h.regle()
            finally:
                h.GEL = old


class SuiviLab(unittest.TestCase):
    def test_premier_horizon_avec_prix(self):
        R, _ = lab.lire_gel(os.path.join(ICI, '..'))
        base = {'circuit': 'WTA', 'date': '2026-10-23', 'joueur': 'X', 'cote_pin': 2.5, 'ampleur_pts': 5.0,
                'cote_jouable': 2.6, 'clv_jouable': 1.0, 'pnl_jouable': 1.6, 'gagne': 1}
        rows = [dict(base, horizon='24h', cote_jouable=None, decision_ts='2026-10-22T15:00+00:00'),   # pas de prix
                dict(base, horizon='6h', decision_ts='2026-10-23T09:00+00:00'),
                dict(base, horizon='1h', decision_ts='2026-10-23T14:00+00:00'),
                dict(base, horizon='10m', ampleur_pts=25.0, decision_ts='2026-10-23T14:50+00:00'),
                dict(base, joueur='Y', circuit='ATP', horizon='6h', decision_ts='2026-10-23T09:00+00:00')]
        d = lab.decisions(rows, R)
        self.assertEqual([(r['joueur'], r['horizon']) for r in d], [('X', '24h')])   # même sans prix (Explorateur)
        doc = lab.evaluer(os.path.join(ICI, '..'), rows=rows)
        self.assertEqual(doc['prospectif']['n'], 1)
        self.assertIn('EN COURS', doc['prospectif']['verdict'])


if __name__ == '__main__':
    unittest.main()
