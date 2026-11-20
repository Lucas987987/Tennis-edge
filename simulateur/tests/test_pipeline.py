#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests d'intégration des sorties publiques, de la fiabilité et de l'ablation."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import ablation as AB
import ajustement as AJ
import apprentissage_continu as AC
import fiabilite as FI
import vitrine as V


def feuille(valeur):
    return [{'aces': {'moy': valeur}}, {'aces': {'moy': valeur + 1}}]


class SortiesUnifiees(unittest.TestCase):
    def test_vitrine_prend_toute_la_combinaison(self):
        m = {'uid': 'u', 'debut': '2026-10-27T12:00', 'home': 'A', 'away': 'B', 'circuit': 'ATP',
             'surface': 'Hard', 'meilleur_des': 3, 'fiabilite': {'note': 71, 'niveau': 'correct'},
             'stats': {'p_home': 0.55, 'scores_probables': [['stats', 1]], 'match_simule': {'feuille': feuille(1)}},
             'simulation': {'p_home': 0.60, 'match_simule': {'scores': [['simulation', 0.2]], 'feuille': feuille(2)}},
             'combinaison': {'p_home': 0.65, 'scores_probables': [['exact', 0.1]],
                             'match_simule': {'n': 20000, 'scores': [['combinaison', 0.2]], 'feuille': feuille(3),
                                              'match_type': {'score': 'combinaison', 'points': '01'}}},
             'direct': {'a': 0.65, 'b': 0.61, 'sets_gagnants': 2, 'tb_final': 7}}
        ligne = V.ligne_match(m, True)
        self.assertEqual(ligne['version'], 'combinaison')
        self.assertEqual(ligne['p_home'], 0.65)
        self.assertEqual(ligne['scores_probables'], [['exact', 0.1]])
        self.assertEqual(ligne['scores_simules'], [['combinaison', 0.2]])
        self.assertEqual(ligne['feuille_prevue'][0]['aces'], 3.0)
        self.assertEqual(ligne['simulation']['scenario']['points'], '01')
        self.assertEqual(ligne['simulation']['n'], 20000)
        self.assertEqual(ligne['fiabilite']['note'], 71)

    def test_repli_sans_simulation(self):
        m = {'uid': 'u', 'debut': '2026-10-27T12:00', 'home': 'A', 'away': 'B',
             'stats': {'p_home': 0.52, 'scores_probables': [['6-4 6-4', 0.1]]}}
        ligne = V.ligne_match(m, True)
        self.assertEqual(ligne['version'], 'stats')
        self.assertEqual(ligne['scores_probables'], [['6-4 6-4', 0.1]])
        self.assertIsNone(ligne['simulation'])


class Fiabilite(unittest.TestCase):
    def test_historique_exclut_interrompus_et_match_courant(self):
        doc = {'matchs': [
            {'uid': 'courant', 'surface': 'Hard', 'circuit': 'ATP', 'p_affiche': 0.6,
             'premier': {'combinaison': {'p_home': 0.6}}, 'reel': {'gagnant': 'home'}},
            {'uid': 'ancien', 'surface': 'Hard', 'circuit': 'ATP', 'p_affiche': 0.61,
             'premier': {'combinaison': {'p_home': 0.61}}, 'reel': {'gagnant': 'away'}},
            {'uid': 'stop', 'surface': 'Hard', 'circuit': 'ATP', 'p_affiche': 0.62,
             'premier': {'combinaison': {'p_home': 0.62}}, 'reel': {'gagnant': 'home', 'interrompu': 'abandon'}}]}
        hist = FI.enregistrements(doc)
        self.assertEqual([r['uid'] for r in hist], ['courant', 'ancien'])
        local = FI.calibration_locale(0.6, 'ATP', 'Hard', hist, uid='courant')
        self.assertEqual(local['n'], 2.8)  # poids de proximité × circuit ×2 × surface ×1,5
        self.assertEqual(local['reel'], 0.0)

    def test_note_bornee_et_definition(self):
        m = {'uid': 'u', 'circuit': 'ATP', 'surface': 'Hard', 'matchs_joues': [80, 70],
             'style_connu': [True, True],
             'stats': {'p_home': 0.62}, 'simulation': {'p_home': 0.64, 'match_simule': {'profil_connu': [True, True]}},
             'combinaison': {'p_home': 0.63, 'match_simule': {'profil_connu': [True, True]}}}
        note = FI.evaluer(m, [])
        self.assertTrue(0 <= note['note'] <= 100)
        self.assertEqual(note['version'], 'combinaison')
        self.assertIn('pas probabilité', note['definition'])
        self.assertEqual(note['historique_effectif'], 0)


class Ablation(unittest.TestCase):
    def setUp(self):
        self.doc = {'matchs': []}
        for i in range(12):
            self.doc['matchs'].append({
                'uid': f'u{i}', 'debut': f'2026-10-{1 + i // 3:02d}T12:00',
                'premier': {'stats': {'p_home': 0.55 + (i % 3) * 0.05},
                            'simulation': {'p_home': 0.58 + (i % 3) * 0.04},
                            'combinaison': {'p_home': 0.60 + (i % 3) * 0.04}},
                'reel': {'gagnant': 'home' if i % 2 else 'away'}})

    def test_memes_matchs_et_bootstrap_deterministe(self):
        obs = AB.observations(self.doc)
        self.assertEqual(len(obs), 12)
        self.assertTrue(all(set(AB.MODELES) <= set(r) for r in obs))
        a, b = AB.analyser(self.doc, bootstrap=30), AB.analyser(self.doc, bootstrap=30)
        self.assertEqual(a, b)
        self.assertEqual({v['n'] for v in a['modeles'].values()}, {12})
        self.assertIn('pipeline_complet_contre_elo', a['comparaisons'])

    def test_entrees_incompletes_non_comparees(self):
        del self.doc['matchs'][0]['premier']['simulation']
        self.doc['matchs'][1]['reel']['interrompu'] = 'abandon'
        self.assertEqual(len(AB.observations(self.doc)), 10)

    def test_ablation_familles_et_documentation(self):
        lignes = []
        for i in range(120):
            ref = .55 + (i % 4) * .05
            lignes.append({'date': None, 'circuit': 'ATP' if i % 2 else 'WTA',
                           'surface': 'Hard', 'bo': 5 if i % 30 == 0 else 3,
                           'connus': i % 45, 'elo': ref + .03,
                           'elo_sans_surface': ref + .02, 'simulation_pure': ref - .02,
                           'simulation_pure_ajustee': ref,
                           'simulation_service_seul': ref - .01,
                           'simulation_retour_seul': ref - .015,
                           'simulation_sans_recence': ref - .005,
                           'simulation_sans_surface': ref - .008})
        r = AB.analyser_familles(lignes)
        self.assertEqual(r['n'], 120)
        self.assertEqual(r['comparaisons']['simulation_pure']['delta_log_loss_vs_reference'],
                         round(r['modeles']['simulation_pure']['log_loss'] - r['modeles']['simulation_pure_ajustee']['log_loss'], 6))
        self.assertIn('documentation:tres_peu_documente', r['sous_groupes'])
        self.assertIn('circuit:ATP', r['sous_groupes'])
        self.assertIn('styles', r['limites'])


class RegularisationSecondeBalle(unittest.TestCase):
    def test_prior_specifique_w2j(self):
        with mock.patch.object(AJ, 'ajuster', return_value='A') as a, \
             mock.patch.object(AJ, 'log_vraisemblance', return_value=.5) as lv:
            import datetime as dt
            n0, scores = AJ.choisir_n0([], lambda x: x, grille=(600.0,),
                                       dates=[dt.date(2023, 1, 1)], journal=lambda x: None,
                                       composante='w2j', n0_base=300.0)
            self.assertEqual(n0, 600.0)
            self.assertEqual(a.call_args.kwargs['n0'], 300.0)
            self.assertEqual(a.call_args.kwargs['n0_par_composante'], {'w2j': 600.0})
            self.assertEqual(lv.call_args.kwargs['composante'], 'w2j')


class ApprentissageControle(unittest.TestCase):
    def test_workflow_reapprend_avant_chaque_pronostic_et_publie_la_decision(self):
        racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        chemin = os.path.join(racine, '.github', 'workflows', 'pronostics_quotidien.yml')
        # 28/10/2026 : les runs de pronostics n'extraient pas .github/ (checkout partiel) ; ce contrôle tourne dans
        # le workflow « Tests » (dépôt complet). Sans ce saut, il bloquait TOUS les pronostics du jour.
        if not os.path.exists(chemin):
            self.skipTest('workflow absent du checkout partiel (vérifié par le workflow Tests)')
        with open(chemin, encoding='utf-8') as f:
            workflow = f.read()
        apprentissage = 'run: python simulateur/apprentissage_continu.py .'
        gouvernance = 'run: python simulateur/gouvernance.py --racine .'
        pronostic = 'run: python simulateur/pronostics_du_jour.py .'
        self.assertLess(workflow.index(apprentissage), workflow.index(gouvernance))
        self.assertLess(workflow.index(gouvernance), workflow.index(pronostic))
        publication = workflow[workflow.index('- name: Publier'):]
        for nom in ('simulateur/choix_simulation.json', 'simulateur/gouvernance_etat.json',
                    'simulateur/rapport_gouvernance.json', 'simulateur/recap_apprentissage.json'):
            self.assertIn(nom, publication)

    def test_adoption_automatique_seulement_si_le_jugement_est_meilleur(self):
        L = [(f'2026-10-{1 + i // 10:02d}T12:00', 0.55, 0.90) for i in range(40)]
        with mock.patch.object(AC, 'MIN_MATCHS', 40), \
             mock.patch.object(AC, 'ajuster', return_value=(0.0, 1.0)):
            decision = AC.decider(L, {'elo': 0.5, 'simulation': 0.5})
        self.assertTrue(decision['adopte'])
        self.assertEqual(decision['poids'], {'elo': 0.0, 'simulation': 1.0})
        self.assertGreaterEqual(decision['jugement']['gain_log_loss'], AC.MARGE_LOG_LOSS)
        self.assertLessEqual(decision['jugement']['brier_continu'],
                             decision['jugement']['brier_poids_archive'])

    def test_periode_de_jugement_non_reutilisee(self):
        L = [(f'2026-10-{1 + i // 10:02d}T12:00', 0.6, 0.65) for i in range(40)]
        with mock.patch.object(AC, 'MIN_MATCHS', 40), mock.patch.object(AC, 'MIN_NOUVEAUX', 5), \
             mock.patch.object(AC, 'ajuster', return_value=(0.5, 0.5)):
            premier = AC.decider(L, {'elo': 0.5, 'simulation': 0.5})
            self.assertIn('jugement', premier)
            self.assertFalse(premier['adopte'])  # gain nul : la marge de 0,001 n'est pas franchie
            self.assertEqual(premier['jugement']['gain_log_loss'], 0.0)
            borne = premier['jugement']['jusqua']
            attente = AC.decider(L, {'elo': 0.5, 'simulation': 0.5}, borne)
            self.assertFalse(attente['adopte'])
            self.assertNotIn('jugement', attente)
            nouveaux = L + [(f'2026-11-{1 + i:02d}T12:00', 0.6, 0.65) for i in range(5)]
            suivant = AC.decider(nouveaux, {'elo': 0.5, 'simulation': 0.5}, borne)
            self.assertEqual(suivant['jugement']['n'], 5)
            self.assertTrue(all(x[0] > borne for x in nouveaux if x in nouveaux[-5:]))


if __name__ == '__main__':
    unittest.main()
