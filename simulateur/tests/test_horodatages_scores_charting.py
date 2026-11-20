import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import charting_atp_wta as CAW
import distribution_exacte as DE
import facteurs as FA
import match_simule as MS
import pronostics_du_jour as PDJ
import validation_vitrine as VV
import variables_pre_match as VP
import vitrine as V


def match(jour, gagnant='a', perdant='b', debut=None, minutes=120):
    return {'date': jour, 'gagnant': gagnant, 'perdant': perdant, 'surface': 'Hard', 'circuit': 'ATP',
            'bo': 3, 'sets': [(6, 4), (6, 4)], 'complet': False, 'minutes': minutes,
            'tournoi': 'Test', 'tournoi_base': 'test', 'debut_utc': debut}


class HorodatagesReelsTest(unittest.TestCase):
    def test_repos_exact_et_absence_sans_interpolation(self):
        h = VP.HistoriquePreMatch()
        h.ajouter(match(dt.date(2026, 1, 1), debut='2026-01-01T12:00:00Z'))
        courant = match(dt.date(2026, 1, 2), debut='2026-01-02T06:00:00Z')
        x = h.calendrier(courant, 'a', 'b')
        self.assertTrue(x['fatigue_horodatage_deux_joueurs'])
        self.assertEqual(x['fatigue_repos_heures_reel'], 0)
        h.ajouter(match(dt.date(2026, 1, 1), gagnant='a', perdant='c', debut='2026-01-01T18:00:00Z'))
        x = h.calendrier(courant, 'a', 'b')
        self.assertEqual(x['fatigue_repos_heures_reel'], -6)
        self.assertEqual(x['fatigue_matchs_168h_reel'], 1)
        sans_heure = h.calendrier(match(dt.date(2026, 1, 2)), 'a', 'b')
        self.assertIsNone(sans_heure['fatigue_repos_heures_reel'])
        self.assertFalse(sans_heure['fatigue_horodatage_deux_joueurs'])

    def test_couverture_des_entrees_a_venir(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [{'id': 'ok', 'commence_time': '2026-10-28T12:00:00Z', 'home_team': 'A', 'away_team': 'B'},
                    {'id': 'sans_fuseau', 'commence_time': '2026-10-28 12:00:00', 'home_team': 'C', 'away_team': 'D'}]
            with open(os.path.join(d, 'matches_oddspapi.json'), 'w', encoding='utf-8') as f:
                json.dump(rows, f)
            matchs, rapport = PDJ.matchs_a_venir(d, dt.datetime(2026, 10, 28), avec_couverture=True)
            self.assertEqual(len(matchs), 1)
            self.assertEqual(rapport['couverture_pct'], 50)
            self.assertFalse(rapport['interpolation'])
            self.assertEqual(matchs[0]['horodatage']['nature'], 'debut_planifie')


class DistributionPubliqueTest(unittest.TestCase):
    def test_vitrine_exacte_et_medoid_rejoue(self):
        a = {'f': .6, 'a': .08, 'w1': .72, 'd': .03, 'w2j': .53}
        b = {'f': .62, 'a': .06, 'w1': .69, 'd': .04, 'w2j': .51}
        p = MS.victoire_pure(a, b, 2, .15)
        sim = MS.simuler(a, b, p, 2, 100, .15, cle='test-public')
        distribution = DE.distribution_forme(a, b, 2, .15, p_victoire=p)
        rows = DE.scores_ordonnes(distribution)
        scores = [[' '.join(f'{x}-{y}' for x, y in r['score']), r['probabilite']] for r in rows]
        exact = {'scores': scores[:3],
                 'distribution': [{'score': r['score'], 'vainqueur': r['vainqueur'], 'probabilite': r['probabilite']}
                                  for r in rows]}
        m = {'uid': 'u', 'debut': '2026-10-29T12:00', 'home': 'A', 'away': 'B', 'circuit': 'ATP',
             'surface': 'Hard', 'meilleur_des': 3,
             'combinaison': {'p_home': p, 'scores_probables': scores[:3], 'scores_exact': exact, 'match_simule': sim},
             'direct': {'a': .63, 'b': .61, 'sets_gagnants': 2, 'tb_final': 7}}
        ligne = V.ligne_match(m, True)
        self.assertEqual(ligne['scores_source'], 'exact')
        self.assertEqual(ligne['scores_probables'], scores[:3])
        self.assertEqual(ligne['scores_simules'], sim['scores'][:3])
        self.assertTrue(VV.valider({'simulations': 100, 'matchs': [ligne]}, 100))


class ChartingProspectifTest(unittest.TestCase):
    def setUp(self):
        self.racine_source = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.modele = CAW.charger_modele(self.racine_source)

    def contexte(self):
        return FA.Contexte({'charting': {'a': [.01, .02, -.01], 'b': [-.01, .01, .02]},
                            'charting_documentation': {
                                'a': {'matchs': 3, 'points_service': 200, 'points_retour': 200},
                                'b': {'matchs': 2, 'points_service': 150, 'points_retour': 150}}})

    def match(self, circuit='ATP', debut='2026-10-29T12:00:00Z'):
        return {'uid': 'u1', 'debut_utc': debut, 'home': 'A', 'away': 'B', 'circuit': circuit,
                'surface': 'Hard', 'cles': ['a', 'b'], 'matchs_joues': [20, 30],
                'stats': {'p_home': .61},
                'combinaison': {'p_simulation': .58, 'match_simule': {
                    'profil_contexte': {'n_balles_effectives': [800, 900]}}}}

    def test_eligibilite_et_prediction_appariee(self):
        obs = CAW.observation(self.match(), self.contexte())
        self.assertIsNotNone(obs)
        p0, p1 = CAW.predire(self.modele, obs[0])
        self.assertTrue(0 < p0 < 1 and 0 < p1 < 1)
        self.assertIsNone(CAW.observation(self.match('CH'), self.contexte()))
        self.assertIsNone(CAW.observation(self.match(debut='2026-10-27T12:00:00Z'), self.contexte()))

    def test_journal_premier_pronostic_immuable(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            shutil.copy(os.path.join(self.racine_source, CAW.FICHIER_MODELE),
                        os.path.join(d, CAW.FICHIER_MODELE))
            doc = {'genere_le': '2026-10-28T01:00:00Z', 'matchs': [self.match()]}
            r1 = CAW.journaliser(d, doc, self.contexte())
            r2 = CAW.journaliser(d, doc, self.contexte())
            self.assertEqual(r1['nouveaux_figes'], 1)
            self.assertEqual(r2['nouveaux_figes'], 0)
            with open(os.path.join(d, CAW.JOURNAL), encoding='utf-8') as f:
                self.assertEqual(len(f.readlines()), 1)

    def test_confirmation_refuse_historique_et_n_active_pas(self):
        ancien = {'debut_utc': '2026-10-27T12:00:00Z', 'resultat_resolu': False}
        with self.assertRaises(ValueError):
            CAW.evaluer_confirmation([ancien])
        futur = {'debut_utc': '2026-10-29T12:00:00Z', 'resultat_resolu': True,
                 'pronostic_fige': True, 'apparie_champion': True, 'y': 1,
                 'controle': .6, 'challenger': .61}
        rapport = CAW.evaluer_confirmation([futur])
        self.assertFalse(rapport['activation'])
        self.assertFalse(rapport['criteres_numeriques_atteints'])


if __name__ == '__main__':
    unittest.main()
