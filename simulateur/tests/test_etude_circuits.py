"""Garde-fous des deux algorithmes par grand circuit."""
import copy
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import elo_recherche as ER
import etude_circuits as EC
import etude_pistes as EP
import styles_joueurs as ST


def ligne(circuit, i, confirmation=False):
    annee = 2025 + (i % 2) if confirmation else 2024
    jour = dt.date(annee, 1, 1) + dt.timedelta(days=3 * i)
    y = i % 2
    row = {
        'uid': f'{circuit}-{int(confirmation)}-{i}', 'date': jour, 'semaine': ST._semaine(jour),
        'y': y, 'elo': .56 if y else .44, 'service_retour': .5,
        'surface': ('Hard', 'Clay')[i % 2], 'circuit': circuit, 'bo': 3,
        'documentation_balles': 1000., 'documentation_matchs': 30,
        'transition_surface': False, 'retour_absence_30j': False,
    }
    for variables in EP.FAMILLES.values():
        for nom in variables:
            row[nom] = 0.0
    return row


def donnees():
    rows = [ligne(c, i, conf) for c in ('ATP', 'WTA', 'CH', 'ITF')
            for conf in (False, True) for i in range(60)]
    predictions = {r['uid']: {nom: r['elo'] for nom in ER.VARIANTES} for r in rows}
    return rows, predictions


class CircuitsTests(unittest.TestCase):
    def test_deux_groupes_couvrent_les_quatre_circuits(self):
        self.assertEqual(EC.groupe('ATP'), 'atp_wta')
        self.assertEqual(EC.groupe('WTA'), 'atp_wta')
        self.assertEqual(EC.groupe('CH'), 'challenger_itf')
        self.assertEqual(EC.groupe('ITF'), 'challenger_itf')
        with self.assertRaises(ValueError):
            EC.groupe('EXO')

    def test_la_confirmation_ne_peut_pas_influencer_le_choix(self):
        rows, predictions = donnees()
        dec = [r for r in rows if r['date'] < EP.COUPURE]
        a = EC.selectionner(dec, predictions)
        modifiees = copy.deepcopy(predictions)
        for r in rows:
            if r['date'] >= EP.COUPURE:
                for nom in modifiees[r['uid']]:
                    modifiees[r['uid']][nom] = 1 - modifiees[r['uid']][nom]
        b = EC.selectionner(dec, modifiees)
        self.assertEqual(a['selection'], b['selection'])

    def test_evaluation_conserve_deux_challengers_sans_activation(self):
        rows, predictions = donnees()
        out = EC.evaluer(rows, predictions, bootstrap=0)
        self.assertEqual(set(out['groupes']), {'atp_wta', 'challenger_itf'})
        self.assertFalse(out['algorithme_partage']['activation'])
        for bloc in out['groupes'].values():
            self.assertFalse(bloc['activation'])
            self.assertGreater(bloc['n_decouverte'], 0)
            self.assertGreater(bloc['n_confirmation'], 0)
        self.assertFalse(out['deux_algorithmes_vs_controle_partage']['activation'])
        self.assertFalse(out['deux_algorithmes_vs_algorithme_partage']['activation'])


if __name__ == '__main__':
    unittest.main()
