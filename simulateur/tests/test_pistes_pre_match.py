"""Garde-fous temporels et statistiques des cinq familles de challengers."""
import copy
import csv
import datetime as dt
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import conditions_tournoi as CT
import donnees
import elo_recherche as ER
import pistes_observations as PO
import variables_pre_match as VP


def match(i=0, jour=None, gagnant='a', perdant='b', edition=None):
    jour = jour or dt.date(2024, 1, 1) + dt.timedelta(days=10 * i)
    detail_w = (100, 60, 42, 18, 10, 2, 4, 2, 10)
    detail_l = (100, 60, 42, 18, 10, 2, 6, 3, 10)
    return {'date': jour, 'fin': jour + dt.timedelta(days=2), 'circuit': 'ATP', 'surface': 'Hard',
            'bo': 3, 'gagnant': gagnant, 'perdant': perdant, 'nom_g': 'Joueur A', 'nom_p': 'Joueur B',
            'sets': [(7, 6), (6, 4)], 'complet': True, 'abandon': False, 'tournoi': 'Test',
            'tournoi_id': f'{jour.year}-0001', 'tournoi_base': '0001', 'edition': edition or jour.year,
            'main_g': 'R', 'main_p': 'L', 'minutes': 100,
            'detail': {'w': detail_w, 'l': detail_l}, 'tour': 1, 'num': i, 'niveau': 'M'}


class VariablesTests(unittest.TestCase):
    def test_petits_echantillons_contractes_et_antisymetrie(self):
        h = VP.HistoriquePreMatch()
        m = match()
        self.assertEqual(h.gauchers_h2h(m, 'a', 'b', 'R', 'L')['h2h_global'], 0)
        self.assertEqual(h.features_pression('a', 'b')['pression_tiebreak'], 0)
        h.ajouter(m, .5)
        suivant = match(jour=m['date'] + dt.timedelta(days=1))
        x = h.gauchers_h2h(suivant, 'a', 'b', 'R', 'L')
        poids = 2.0 ** (-1 / VP.DEMI_VIE_H2H)
        taux = (poids + VP.PRIOR_H2H / 2) / (poids + VP.PRIOR_H2H)
        attendu = math.log(taux / (1 - taux))
        self.assertAlmostEqual(x['h2h_global'], attendu)
        self.assertLess(abs(x['h2h_global']), 1)
        y = h.gauchers_h2h(suivant, 'b', 'a', 'L', 'R')
        self.assertAlmostEqual(x['h2h_global'], -y['h2h_global'])
        self.assertAlmostEqual(x['main_bilan_contre_main'], -y['main_bilan_contre_main'])
        p = h.features_pression('a', 'b')
        q = h.features_pression('b', 'a')
        for nom in p:
            if not nom.endswith('documentation_tiebreak') and 'documentation' not in nom:
                self.assertAlmostEqual(p[nom], -q[nom])

    def test_balles_de_break_service_et_retour_distinctes(self):
        h = VP.HistoriquePreMatch()
        h.ajouter(match(), .5)
        n, v = h.pression[('a', 'bp_service')]
        self.assertEqual((n, v), (1, .5))
        n, v = h.pression[('a', 'bp_retour')]
        self.assertEqual((n, v), (1, .5))
        n, v = h.pression[('b', 'bp_service')]
        self.assertEqual((n, v), (1, .5))
        n, v = h.pression[('b', 'bp_retour')]
        self.assertEqual((n, v), (1, .5))

    def test_calendrier_utilise_seulement_les_jours_precedents(self):
        h = VP.HistoriquePreMatch()
        m = match(jour=dt.date(2024, 1, 10))
        h.ajouter(match(jour=dt.date(2024, 1, 1)), .5)
        x = h.calendrier(m, 'a', 'b')
        # Les deux joueurs ont le même historique : tous les écarts sont nuls.
        descriptifs = {'fatigue_documentation_duree_7j', 'fatigue_duree_derniers_matchs_connue',
                       'fatigue_historique_deux_joueurs', 'fatigue_horodatage_deux_joueurs',
                       'fatigue_duree_168h_reel_documentee', 'fatigue_repos_heures_reel',
                       'fatigue_matchs_168h_reel', 'fatigue_minutes_168h_reel'}
        for nom, valeur in x.items():
            if nom not in descriptifs:
                self.assertEqual(valeur, 0, nom)
        h.ajouter(match(jour=dt.date(2024, 1, 9)), .5)
        self.assertEqual(h.calendrier(m, 'a', 'b')['fatigue_matchs_7j'], 0)

    def test_absences_et_enchainement_sont_orientes(self):
        h = VP.HistoriquePreMatch()
        ancien = match(jour=dt.date(2024, 1, 1), gagnant='a', perdant='c')
        ancien['tournoi_base'] = '0002'
        h.ajouter(ancien, .5)
        courant = match(jour=dt.date(2024, 1, 7), gagnant='a', perdant='b')
        x = h.calendrier(courant, 'a', 'b')
        self.assertEqual(x['fatigue_enchainement_7j'], 1)
        self.assertEqual(x['fatigue_retour_absence_30j'], -1)
        self.assertEqual(x['fatigue_retour_absence_60j'], -1)
        self.assertEqual(x['fatigue_retour_absence_90j'], -1)
        y = h.calendrier(courant, 'b', 'a')
        for nom in ('fatigue_enchainement_7j', 'fatigue_retour_absence_30j',
                    'fatigue_retour_absence_60j', 'fatigue_retour_absence_90j'):
            self.assertEqual(x[nom], -y[nom])

    def test_h2h_decroit_avec_le_temps(self):
        h = VP.HistoriquePreMatch()
        ancien = match(jour=dt.date(2020, 1, 1))
        h.ajouter(ancien, .5)
        jour = dt.date(2024, 1, 1)
        x = h.gauchers_h2h(match(jour=jour), 'a', 'b', 'R', 'L')
        self.assertLess(x['h2h_poids_effectif'], .3)
        self.assertLess(x['h2h_global'], .1)


class ConditionsTests(unittest.TestCase):
    def test_edition_courante_exclue_et_edition_suivante_utilisee(self):
        c = CT.ConditionsTournoi()
        m = match(jour=dt.date(2024, 1, 1))
        attendu = c.attendu(m)
        c.ajouter(m, attendu)
        self.assertEqual(c._environnement(m, 'aces'), (0.0, 0.0))
        suivant = match(jour=dt.date(2025, 1, 1))
        env, n = c._environnement(suivant, 'aces')
        self.assertEqual(n, 1)
        self.assertAlmostEqual(env, .04)
        self.assertAlmostEqual(c._environnement(suivant, 'service_gagne')[0], -.03)
        self.assertAlmostEqual(-env, -.04)

    def test_effet_principal_commun_transforme_en_interaction(self):
        c = CT.ConditionsTournoi()
        m = match(jour=dt.date(2024, 1, 1))
        c.ajouter(m, c.attendu(m))
        suivant = match(jour=dt.date(2025, 1, 1))
        h = VP.HistoriquePreMatch()
        profil = {'f': .6, 'a': .1, 'w1': .7, 'w2j': .55, 'r1': .7, 'r2j': .55}
        x = c.features(suivant, 'a', 'b', profil, profil, h)
        for nom in ('conditions_aces_x_profil', 'conditions_service_retour',
                    'conditions_tiebreak_x_service', 'conditions_longueur_x_endurance',
                    'conditions_minutes_x_endurance'):
            self.assertEqual(x[nom], 0)
        self.assertGreater(x['conditions_matchs_editions'], 0)


class SocleTests(unittest.TestCase):
    def test_resultat_du_meme_jour_exclu_partout(self):
        jour = dt.date(2024, 2, 1)
        M = [match(0, jour=jour), match(1, jour=jour), match(2, jour=jour + dt.timedelta(days=1))]
        rows = PO.observations(M, {id(m) for m in M})
        self.assertEqual(rows[0]['h2h_poids_effectif'], 0)
        self.assertEqual(rows[1]['h2h_poids_effectif'], 0)
        self.assertEqual(rows[0]['pression_documentation_tiebreak'], 0)
        self.assertEqual(rows[1]['pression_documentation_tiebreak'], 0)
        self.assertAlmostEqual(rows[2]['h2h_poids_effectif'], 2, places=2)
        self.assertEqual(rows[2]['pression_documentation_tiebreak'], 2)

    def test_inverser_l_issue_courante_ne_change_pas_ses_variables(self):
        jour = dt.date(2024, 2, 1)
        M = [match(0, jour=jour - dt.timedelta(days=10)), match(1, jour=jour)]
        inverse = copy.deepcopy(M)
        inverse[1]['gagnant'], inverse[1]['perdant'] = 'b', 'a'
        a = PO.observations(M, {id(M[1])})[0]
        b = PO.observations(inverse, {id(inverse[1])})[0]
        cles = ['elo', 'service_retour', 'h2h_global', 'fatigue_repos_log', 'pression_tiebreak']
        for cle in cles:
            self.assertAlmostEqual(a[cle], b[cle], msg=cle)
        self.assertNotEqual(a['y'], b['y'])

    def test_elo_meme_jour_non_mis_a_jour(self):
        jour = dt.date(2024, 2, 1)
        M = [match(0, jour=jour), match(1, jour=jour)]
        p = ER.predictions(M, {id(m) for m in M})
        uid0, uid1 = PO.cle_match(M[0]), PO.cle_match(M[1])
        for nom in ER.VARIANTES:
            self.assertAlmostEqual(p[uid0][nom], p[uid1][nom], msg=nom)


class EloTests(unittest.TestCase):
    def test_decroissance_vers_le_prior(self):
        e = ER.EloVariante(demi_vie_j=730)
        e.a_la_date(dt.date(2023, 12, 31))
        e.maj('a', 'b', 'Hard', circuit='ATP')
        avant = e._g('a')
        self.assertGreater(avant, 1500)
        e.a_la_date(dt.date(2025, 12, 31))
        apres = e.note('a')
        jours = (dt.date(2025, 12, 31) - dt.date(2023, 12, 31)).days
        attendu = 1500 + (avant - 1500) * 2.0 ** (-jours / 730)
        self.assertAlmostEqual(apres, attendu, places=6)

    def test_variantes_partent_du_controle_actif(self):
        for nom, options in ER.VARIANTES.items():
            e = ER.EloVariante(**PO.ELO_CONTROLE, **options)
            self.assertEqual(e.poids_surface, .3, nom)
            self.assertEqual(e.welo, 'norme', nom)
            self.assertEqual(e.incertitude, 5, nom)


class ChargeurTests(unittest.TestCase):
    def test_champs_main_duree_et_edition_valides(self):
        champs = ['tourney_id', 'tourney_name', 'surface', 'tourney_level', 'tourney_date', 'match_num',
                  'winner_id', 'winner_name', 'winner_hand', 'loser_id', 'loser_name', 'loser_hand',
                  'score', 'best_of', 'round', 'minutes']
        ligne = {'tourney_id': '2024-0001', 'tourney_name': 'Test', 'surface': 'Hard', 'tourney_level': 'M',
                 'tourney_date': '20240101', 'match_num': '1', 'winner_id': '1', 'winner_name': 'A',
                 'winner_hand': 'L', 'loser_id': '2', 'loser_name': 'B', 'loser_hand': 'X',
                 'score': '6-4 6-4', 'best_of': '3', 'round': 'F', 'minutes': '95'}
        with tempfile.TemporaryDirectory() as d:
            chemin = os.path.join(d, 'atp_matches_2024.csv')
            with open(chemin, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=champs)
                w.writeheader()
                w.writerow(ligne)
            m = donnees.charger(d, 2024)[0]
        self.assertEqual((m['main_g'], m['main_p']), ('L', 'U'))
        self.assertEqual((m['minutes'], m['tournoi_base'], m['edition']), (95, '0001', 2024))


if __name__ == '__main__':
    unittest.main()
