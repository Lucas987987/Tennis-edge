"""Périmètre et invariants du test des bilans de styles seuls."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import etude_styles_seuls as SS
import gouvernance_candidats as GC


def ligne(i, bilan_global=0.0, bilan_surface=0.0):
    jour = (dt.date(2024, 1, 1) + dt.timedelta(days=i) if i < 240
            else dt.date(2025, 1, 1) + dt.timedelta(days=i-240))
    return {
        'date': jour, 'semaine': f'{jour.isocalendar().year}-S{jour.isocalendar().week:02d}',
        'y': i % 2, 'surface': ('Hard', 'Clay', 'Grass')[i % 3],
        'bilan_global': bilan_global, 'bilan_surface': bilan_surface,
        'documentation_bilans': 10, 'documentation_surface': 5,
        # Ces champs ne doivent jamais devenir des variables du modèle.
        'elo': .99, 'service_retour': .01, 'circuit': 'ATP', 'cote': 1.01,
    }


class VariablesSeules(unittest.TestCase):
    def test_seuls_les_bilans_demandes_entrent_dans_le_modele(self):
        r = ligne(0, .4, -.2)
        self.assertEqual(SS._variables(r, 'global'), [1.0, .4])
        self.assertEqual(SS._variables(r, 'surface'), [1.0, -.2])
        self.assertEqual(SS._variables(r, 'global_surface'), [1.0, .4, -.2])

    def test_les_autres_facteurs_ne_changent_aucune_variable(self):
        a = ligne(0, .4, -.2)
        b = dict(a, elo=.01, service_retour=.99, circuit='ITF', cote=50.0)
        for candidat in SS.CANDIDATS:
            self.assertEqual(SS._variables(a, candidat), SS._variables(b, candidat))

    def test_sans_bilan_le_signal_est_nul(self):
        r = ligne(0)
        for candidat in SS.CANDIDATS:
            self.assertEqual(SS._variables(r, candidat), [1.0] + [0.0] * len(SS.CANDIDATS[candidat]))


class Evaluation(unittest.TestCase):
    def test_reference_neutre_et_aucune_activation(self):
        rows = [ligne(i, (-1)**i * .1, (-1)**i * .05) for i in range(480)]
        out = SS.evaluer(rows, bootstrap=0)
        self.assertEqual(out['n_decouverte'], 240)
        self.assertEqual(out['n_confirmation'], 240)
        self.assertFalse(out['marche_utilise'])
        self.assertFalse(out['activation'])
        self.assertFalse(out['champion_actif_modifie'])
        self.assertEqual(out['comparaison_surface_incrementale_dans_profils']['reference'], 'global')
        self.assertEqual(out['comparaison_surface_incrementale_dans_profils']['challenger'], 'global_surface')
        for candidat, bloc in out['resultats'].items():
            neutre = bloc['confirmation']['neutre_50']
            self.assertEqual(neutre['log_loss'], .693147)
            self.assertEqual(neutre['brier'], .25)
            self.assertEqual(neutre['reussite_pct'], 50.0)
            self.assertEqual(bloc['variables'], list(SS.CANDIDATS[candidat]))
            self.assertTrue(bloc['convergence'])
            self.assertEqual(len(bloc['modele_complet_decouverte']['beta']), len(SS.CANDIDATS[candidat]) + 1)
            self.assertEqual(len(bloc['modele_complet_decouverte']['moyennes']), len(SS.CANDIDATS[candidat]) + 1)
            self.assertIn('gains_contre_neutre', bloc['confirmation'])

    def test_challenger_global_fige_sans_activation(self):
        racine = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        manifeste = GC.charger(racine)
        candidat = manifeste['candidats']['styles_adverses_global_v1']
        self.assertEqual(candidat['parametres']['variable'], 'bilan_global')
        self.assertFalse(candidat['parametres']['surface_ajoutee'])
        self.assertFalse(candidat['activation'])
        self.assertIn('modele_complet_decouverte', candidat['implementation'])
        self.assertTrue(GC.auditer(manifeste)['ok'])

    def test_couverture_exige_un_bilan_pour_chaque_joueur(self):
        rows = [ligne(i) for i in range(480)]
        rows[0]['documentation_bilans'] = 0
        rows[1]['documentation_surface'] = 0
        couverture = SS._couverture(rows[:2])
        self.assertEqual(couverture['deux_bilans_globaux_documentes']['n'], 1)
        self.assertEqual(couverture['deux_bilans_surface_documentes']['n'], 1)


if __name__ == '__main__':
    unittest.main()
