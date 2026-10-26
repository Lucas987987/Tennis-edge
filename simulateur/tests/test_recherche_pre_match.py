import copy
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import fiabilite as FI
import matchs_similaires as V
import profils_service as PS
import recalibrage as RC
import styles_joueurs as ST


def match(uid, jour, p=.6, pe=.62, ps=.58, gagnant='home', **extra):
    return dict({'uid': uid, 'debut': jour+'T12:00:00+00:00', 'circuit': 'ATP', 'surface': 'Hard',
                 'meilleur_des': 3, 'matchs_joues': [40, 35], 'style_connu': [True, True],
                 'premier': {'stats': {'p_home': pe}, 'simulation': {'p_home': ps},
                             'combinaison': {'p_home': p, 'match_simule': {'profil_connu': [True, True]}}},
                 'reel': {'gagnant': gagnant}}, **extra)


class FiabiliteConditionnelle(unittest.TestCase):
    def test_categories_et_desaccord_sont_explicites(self):
        self.assertEqual(FI.categorie(.9, False, 'stable', 100), 'A_solide')
        self.assertEqual(FI.categorie(.9, True, 'stable', 100), 'C_fragile')
        self.assertEqual(FI.categorie(.9, False, 'instable', 100), 'B_incertain')
        self.assertEqual(FI.categorie(.1, False, 'stable', 100), 'D_non_controle')
        m = match('u', '2026-10-01')
        courant = dict(m, **m['premier'])
        f = FI.evaluer(courant, [])
        self.assertIn('categorie', f)
        self.assertFalse(f['desaccord_vainqueur_elo_simulation'])
        courant['simulation']['p_home'] = .4
        self.assertTrue(FI.evaluer(courant, [])['desaccord_vainqueur_elo_simulation'])


class Voisinage(unittest.TestCase):
    def test_futur_et_match_courant_exclus(self):
        cible = match('cible', '2026-10-10')
        ancien = match('ancien', '2026-10-01')
        futur = match('futur', '2026-10-11')
        meme = match('cible', '2026-10-01')
        out = V.selectionner(cible, [ancien, futur, meme])
        self.assertEqual([v['match']['uid'] for v in out], ['ancien'])

    def test_resultat_et_marche_ne_changent_pas_la_distance(self):
        a, b = match('a', '2026-10-01'), match('b', '2026-10-02')
        d = V.distance(V.vecteur(a), V.vecteur(b))
        b['reel']['gagnant'] = 'away'
        b['pin_cotes'] = {'pinnacle': [1.1, 8.]}
        self.assertEqual(d, V.distance(V.vecteur(a), V.vecteur(b)))

    def test_resume_ne_selectionne_pas_selon_le_roi(self):
        cible = match('cible', '2026-10-10')
        historique = [match(f'u{i}', f'2026-09-{1+i:02d}', p=.6+(i%3)*.01,
                            gagnant='home' if i%2 else 'away') for i in range(20)]
        r = V.resumer(cible, historique, k=10)
        self.assertEqual(r['n'], 10)
        self.assertNotIn('roi', r)
        self.assertNotIn('uids', r)


class Styles(unittest.TestCase):
    def test_instantane_est_date_et_interaction_antisymetrique(self):
        P = PS.Profils()
        a = ST.instantane(P, 'a', 'ATP', 'Hard', dt.date(2026, 1, 1))
        self.assertEqual(a['disponible_avant'], '2026-01-01')
        mu = dict(PS.REPLI)
        ph = dict(mu, w1=mu['w1']+.04)
        pa = dict(mu, w1=mu['w1']-.04)
        self.assertAlmostEqual(ST.interaction(ph, pa, mu), -ST.interaction(pa, ph, mu))

    def test_challenger_ne_change_pas_le_champion_sans_preuve(self):
        vide = {str(x): {'decouverte': {'n': 0}, 'confirmation': {'n': 0}} for x in ST.LAMBDAS}
        self.assertFalse(ST.decider(vide)['adopte'])


class Recalibrage(unittest.TestCase):
    def doc(self):
        out = []
        for i in range(360):
            jour = dt.date(2026, 1, 1)+dt.timedelta(days=i//2)
            p = .52+(i%8)*.04
            out.append(match(f'u{i:03d}', jour.isoformat(), p=p, pe=p+.01, ps=p-.01,
                             gagnant='home' if (i*7)%11 < int(p*11) else 'away'))
        return {'matchs': out}

    def test_fenetres_futures_et_decision_reproductible(self):
        doc = self.doc()
        a = RC.evaluer(doc, min_train=80, min_test=20)
        b = RC.evaluer(copy.deepcopy(doc), min_train=80, min_test=20)
        self.assertEqual(a, b)
        self.assertGreaterEqual(len(a['fenetres_details']), 2)
        vues = set()
        for f in a['fenetres_details']:
            self.assertTrue(f['semaines_test'])
            self.assertGreater(f['test_n'], 0)
            self.assertFalse(vues.intersection(f['semaines_test']))
            vues.update(f['semaines_test'])
        self.assertFalse(a['champion_actif_modifie'])
        self.assertFalse(a['marche_utilise'])

    def test_isotone_est_apprise_sur_le_train_seulement(self):
        train = [{'pipeline_complet': .4, 'y': 0}, {'pipeline_complet': .6, 'y': 1}]
        modele = RC._pava(train)
        self.assertLess(RC._pred_pava(modele, .4), RC._pred_pava(modele, .6))


if __name__ == '__main__':
    unittest.main()
