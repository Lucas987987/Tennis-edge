"""Garde-fous du challenger pression V2 et des trajectoires descriptives."""
import copy
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import evolution_statistiques as EV
import pistes_observations as PO
import pression_v2 as PV2


def match(i=0, jour=None, gagnant='a', perdant='b'):
    jour = jour or dt.date(2024, 1, 1) + dt.timedelta(days=10 * i)
    return {
        'date': jour, 'fin': jour + dt.timedelta(days=2), 'circuit': 'ATP', 'surface': 'Hard',
        'bo': 3, 'gagnant': gagnant, 'perdant': perdant, 'nom_g': 'Joueur A', 'nom_p': 'Joueur B',
        'sets': [(7, 6), (6, 4)], 'complet': True, 'abandon': False, 'tournoi': 'Test',
        'tournoi_id': f'{jour.year}-0001', 'tournoi_base': '0001', 'edition': jour.year,
        'main_g': 'R', 'main_p': 'L', 'minutes': 100,
        'detail': {'w': (100, 60, 42, 18, 10, 2, 4, 2, 10),
                   'l': (100, 60, 42, 18, 10, 2, 6, 3, 10)},
        'tour': 1, 'num': i, 'niveau': 'M',
    }


class PressionV2Tests(unittest.TestCase):
    def test_force_adverse_et_antisymetrie(self):
        fort, faible = PV2.HistoriquePressionV2(), PV2.HistoriquePressionV2()
        m = match()
        fort.ajouter(m, .8)
        faible.ajouter(m, .2)
        jour = m['date'] + dt.timedelta(days=1)
        a = fort.mesure('a', 'tiebreak', 'Hard', 'ATP', jour)['residu_global']
        b = faible.mesure('a', 'tiebreak', 'Hard', 'ATP', jour)['residu_global']
        self.assertLess(a, b)
        x = fort.features('a', 'b', 'Hard', 'ATP', jour)
        y = fort.features('b', 'a', 'Hard', 'ATP', jour)
        for nom in PV2.VARIABLES:
            self.assertAlmostEqual(x[nom], -y[nom])

    def test_recence_surface_et_circuit(self):
        h = PV2.HistoriquePressionV2()
        ancien = match(jour=dt.date(2022, 1, 1))
        recent = match(jour=dt.date(2024, 1, 1))
        h.ajouter(ancien, .5)
        avant = h.mesure('a', 'tiebreak', 'Hard', 'ATP', dt.date(2024, 1, 2))['n_effectif']
        h.ajouter(recent, .5)
        apres = h.mesure('a', 'tiebreak', 'Hard', 'ATP', dt.date(2024, 1, 2))
        self.assertGreater(apres['n_effectif'], avant)
        self.assertLess(ancien['date'].year, recent['date'].year)
        self.assertGreater(apres['residu_surface'], 0)
        self.assertGreater(apres['residu_circuit'], 0)
        autre_surface = h.mesure('a', 'tiebreak', 'Clay', 'ATP', dt.date(2024, 1, 2))
        autre_circuit = h.mesure('a', 'tiebreak', 'Hard', 'CH', dt.date(2024, 1, 2))
        self.assertLess(abs(autre_surface['residu_surface']), abs(apres['residu_surface']))
        self.assertLess(abs(autre_circuit['residu_circuit']), abs(apres['residu_circuit']))

    def test_balle_de_break_nulle_si_identique_aux_points_ordinaires(self):
        h = PV2.HistoriquePressionV2()
        m = match()
        # 60 points gagnés sur 100 au service ; 2 sauvées sur 4 ne donnent pas ici
        # un résidu nul. On force 2,4 sauvées équivalentes sur 4 occasions.
        m['detail']['w'] = (100, 60, 42, 18, 10, 2, 4, 2.4, 10)
        h.ajouter(m, .5)
        mesure = h.mesure('a', 'bp_service', 'Hard', 'ATP', m['date'] + dt.timedelta(days=1))
        self.assertAlmostEqual(mesure['residu_global'], 0)

    def test_meme_jour_exclu_et_issue_courante_non_utilisee(self):
        jour = dt.date(2024, 2, 1)
        M = [match(0, jour=jour), match(1, jour=jour), match(2, jour=jour + dt.timedelta(days=1))]
        rows = PO.observations(M, {id(m) for m in M}, avec_pression_v2=True)
        self.assertEqual(rows[0]['pression_v2_documentation_tiebreak'], 0)
        self.assertEqual(rows[1]['pression_v2_documentation_tiebreak'], 0)
        self.assertAlmostEqual(rows[2]['pression_v2_documentation_tiebreak'], 2 * .5 ** (1 / 365))
        inverse = copy.deepcopy(M)
        inverse[2]['gagnant'], inverse[2]['perdant'] = 'b', 'a'
        a = rows[2]
        b = PO.observations(inverse, {id(inverse[2])}, avec_pression_v2=True)[0]
        for nom in PV2.VARIABLES:
            self.assertAlmostEqual(a[nom], b[nom])
        self.assertNotEqual(a['y'], b['y'])


class EvolutionTests(unittest.TestCase):
    def test_fenetres_excluent_le_futur_et_donnent_les_effectifs(self):
        reference = dt.date(2024, 7, 1)
        M = [match(0, jour=reference - dt.timedelta(days=10)),
             match(1, jour=reference - dt.timedelta(days=200)),
             match(2, jour=reference)]
        out = EV.construire(M, reference, joueurs=['a'], fenetre_jours=180,
                            points_trajectoire=2, pas_jours=90)
        bloc = out['joueurs']['a']['global']
        self.assertEqual(bloc['periode_recente']['matchs'], 1)
        self.assertEqual(bloc['periode_precedente']['matchs'], 1)
        premiere = bloc['periode_recente']['statistiques']['premiere_balle_pct']
        self.assertEqual(premiere['n'], 100)
        self.assertEqual(premiere['taux_pct'], 60)
        self.assertEqual(bloc['variations']['premiere_balle_pct']['variation_points'], 0)
        self.assertEqual(out['champion_actif_modifie'], False)

    def test_recherche_par_nom_resout_l_identifiant_archive(self):
        reference = dt.date(2024, 7, 1)
        m = match(0, jour=reference - dt.timedelta(days=10))
        m['gagnant'], m['perdant'] = 'wta:1', 'wta:2'
        m['nom_g'], m['nom_p'] = 'Harriet Dart', 'Janice Tjen'
        out = EV.construire([m], reference, joueurs=['Harriet Dart'], points_trajectoire=1)
        self.assertIn('wta:1', out['joueurs'])
        self.assertEqual(out['joueurs']['wta:1']['nom'], 'Harriet Dart')

    def test_petit_echantillon_ne_produit_pas_de_progression(self):
        reference = dt.date(2024, 7, 1)
        M = [match(0, jour=reference - dt.timedelta(days=10))]
        out = EV.construire(M, reference, joueurs=['a'], fenetre_jours=180,
                            points_trajectoire=1)
        variation = out['joueurs']['a']['global']['variations']['tiebreaks_gagnes_pct']
        self.assertEqual(variation['statut'], 'sous_documentee')
        self.assertIsNone(variation['variation_points'])


if __name__ == '__main__':
    unittest.main()
