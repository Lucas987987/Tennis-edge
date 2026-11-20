"""Contrôles du suivi prospectif des six directions de profils."""
import datetime as dt  # noqa: F401
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import profils_orientes as PO


def match(uid='u1', debut='2026-11-02T12:00:00Z', circuit='WTA'):
    return {'uid': uid, 'debut_utc': debut, 'home': 'A', 'away': 'B', 'circuit': circuit,
            'surface': 'Hard', 'matchs_joues': [20, 30], 'cles': ['a', 'b'],
            'stats': {'p_home': .61}, 'combinaison': {'p_simulation': .58, 'match_simule': {
                'profil_contexte': {'n_balles_effectives': [800, 900]}}}}


def bloc(styles=('serveur_attaquant', 'contreur')):
    return {'challenger_seulement': True, 'schema': 'statistiques_styles_adverses_v1',
            'styles': list(styles), 'bilan_global': .1}


class DirectionTest(unittest.TestCase):
    def test_six_cellules_et_deux_orientations(self):
        self.assertEqual(len(PO.BRANCHES)*len(PO.DIRECTIONS), 6)
        self.assertEqual(PO.direction(['serveur_attaquant', 'contreur']),
                         ('serveur_attaquant_contre_contreur', 1))
        self.assertEqual(PO.direction(['contreur', 'serveur_attaquant']),
                         ('serveur_attaquant_contre_contreur', -1))
        self.assertEqual(PO.direction(['grand_serveur', 'contreur']),
                         ('contreur_contre_grand_serveur', -1))
        self.assertEqual(PO.direction(['equilibre', 'contreur']), (None, 0))

    def test_future_seulement_et_trois_branches(self):
        row = PO.observation(match(circuit='ITF'), bloc(('contreur', 'grand_serveur')))
        self.assertEqual(row['branche'], 'challenger')
        self.assertEqual(row['direction'], 'contreur_contre_grand_serveur')
        self.assertEqual(row['sens_profil_home'], 1)
        self.assertIsNone(PO.observation(match(debut='2026-10-31T12:00:00Z'), bloc()))
        self.assertIsNone(PO.observation(match(), bloc(('equilibre', 'contreur'))))

    def test_controle_symetrique_apres_orientation(self):
        modele = PO.charger_modele(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        row = PO.observation(match(), bloc())
        p = PO.predire_controle(modele, row)
        inverse = dict(row, cles=['b', 'a'], elo=1-row['elo'], service_retour=1-row['service_retour'],
                       bilan_global=-row['bilan_global'])
        q = PO.predire_controle(modele, inverse)
        self.assertAlmostEqual(p, 1-q)


class JournalProspectifTest(unittest.TestCase):
    def setUp(self):
        self.source = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_premier_fige_unique_et_historique_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            shutil.copy(os.path.join(self.source, PO.FICHIER_MODELE), os.path.join(d, PO.FICHIER_MODELE))
            with open(os.path.join(d, PO.FICHIER_FEATURES), 'w', encoding='utf-8') as f:
                json.dump({'matchs': {'u1': {'statistiques_styles': bloc()},
                                      'u2': {'statistiques_styles': bloc(('equilibre', 'contreur'))}}}, f)
            doc = {'genere_le': '2026-11-01T01:00:00Z',
                   'matchs': [match(), match(uid='u2')]}
            r1, r2 = PO.journaliser(d, doc), PO.journaliser(d, doc)
            self.assertEqual((r1['n_eligibles'], r1['nouveaux_figes']), (1, 1))
            self.assertEqual(r2['nouveaux_figes'], 0)
            self.assertEqual(r1['cellules_suivies'], 6)
            self.assertFalse(r1['correction_active'])
            lignes = list(PO.SG._lire_journal(os.path.join(d, PO.JOURNAL)).values())
            self.assertNotIn('challenger', lignes[0])
            self.assertTrue(lignes[0]['descriptif_prospectif_seulement'])

    def test_evaluation_future_insuffisante_et_toutes_cellules_presentes(self):
        futur = {'debut_utc': '2026-11-02T12:00:00Z', 'resultat_resolu': True,
                 'pronostic_fige': True, 'apparie_champion': True, 'y': 1,
                 'champion': .6, 'controle': .58, 'direction': 'serveur_attaquant_contre_contreur',
                 'branche': 'wta', 'sens_profil_home': 1}
        rapport = PO.evaluer_confirmation([futur], bootstrap=0)
        self.assertEqual(len(rapport['cellules']), 6)
        cellule = rapport['cellules']['wta|serveur_attaquant_contre_contreur']
        self.assertEqual(cellule['n_resolus'], 1)
        self.assertAlmostEqual(cellule['residuel_controle_points'], 42.0)
        self.assertFalse(cellule['signal_prospectif_confirme'])
        self.assertFalse(rapport['activation'])
        with self.assertRaises(ValueError):
            PO.evaluer_confirmation([dict(futur, debut_utc='2026-10-31T12:00:00Z')], bootstrap=0)


if __name__ == '__main__':
    unittest.main()
