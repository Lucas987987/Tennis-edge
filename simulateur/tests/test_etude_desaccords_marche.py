import datetime as dt
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import etude_desaccords_marche as ET
import styles_joueurs as ST


def match(uid, jour='2026-10-23', p=.60, pin=(2.0, 1.9), gagnant='home'):
    return {
        'uid': uid, 'debut': jour+'T12:00:00', 'pronostique_le': jour+'T08:00:00Z',
        'home': 'Ann Alpha', 'away': 'Bea Beta', 'circuit': 'ATP', 'pin_cotes': pin,
        'premier': {'stats': {'p_home': p-.02}, 'simulation': {'p_home': p+.01},
                    'combinaison': {'p_home': p}},
        'reel': {'gagnant': gagnant, 'interrompu': None},
    }


class MarcheTests(unittest.TestCase):
    def test_demargination_est_symetrique(self):
        self.assertAlmostEqual(ET.proba_sans_marge(2, 2), .5)
        p = ET.proba_sans_marge(2.2, 1.75)
        self.assertAlmostEqual(p + ET.proba_sans_marge(1.75, 2.2), 1.0, places=10)

    def test_comparaison_appariée_sans_cloture_future(self):
        doc = {'matchs': [match('a'), match('b', p=.4, gagnant='away'), match('sans_cote', pin=None)]}
        rows, rejets = ET.observations_marche(doc)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rejets['cotes_au_pronostic_absentes'], 1)
        self.assertTrue(all(r['periode'] == 'decouverte' for r in rows))
        rapport = ET.analyser_marche(doc, bootstrap=0)
        self.assertEqual(rapport['n_avec_marche_au_pronostic'], 2)
        self.assertIn('log_loss', rapport['resultats']['global']['algorithme'])


class VetoEtDependanceTests(unittest.TestCase):
    def signal(self, uid='a', side='away', joueur='Bea Beta', detecte='2026-10-23T09:00:00'):
        return {'uid': uid, 'side': side, 'joueur': joueur, 'detecte_le': detecte,
                'pin_decision': 2.0, 'envoye': True, 'doublon': '', 'regle_hash': 'gèle', 'gele_le': '2026-10-02'}

    def test_veto_exige_pronostic_disponible_au_signal(self):
        doc = {'matchs': [match('a'), match('b'), match('c'), match('d')]}
        rows = [
            self.signal(),  # algo home, H14 away : veto
            self.signal('b', detecte='2026-10-23T07:00:00'),  # avant le pronostic
            self.signal('c', detecte='2026-10-23T13:00:00'),  # après le début
            self.signal('d', joueur='Mauvaise Identité'),
        ]
        testables, rejets = ET._signaux_h14(doc, rows)
        self.assertEqual(len(testables), 1)
        self.assertTrue(testables[0]['veto'])
        self.assertEqual(rejets['pronostic_non_disponible_ou_signal_hors_fenetre'], 2)
        self.assertEqual(rejets['identite_side_incoherente'], 1)
        rapport = ET.analyser_veto(doc, rows)
        self.assertFalse(rapport['activation'])
        self.assertEqual(rapport['resultats']['global']['ecartes_par_veto']['n'], 1)

    def test_chevauchement_par_match_et_par_joueur(self):
        h13 = [self.signal('a', joueur='Bea Beta', detecte='2026-10-20T11:00:00'),
               self.signal('b', joueur='Ann Alpha', detecte='2026-10-20T12:00:00')]
        h14 = [self.signal('a', joueur='Bea Beta', detecte='2026-10-20T11:00:00'),
               self.signal('c', joueur='Bea Beta', detecte='2026-10-20T12:00:00')]
        out = ET.analyser_chevauchement(h13, h14)['toutes_detections']
        self.assertEqual((out['h13'], out['h14'], out['intersection'], out['union']), (2, 2, 1, 3))
        self.assertEqual(out['meme_joueur_pct'], 100.0)


class RegressionLogistiqueTests(unittest.TestCase):
    def test_modele_apprend_seulement_sur_son_echantillon(self):
        X = [[1.0, x/10] for x in range(-30, 31)]
        y = [int(x > 0) for x in range(-30, 31)]
        modele = ST._ajuster(X, y, ridge=.1)
        p = ST._predire(modele, [[1.0, -2.0], [1.0, 2.0]])
        self.assertLess(p[0], .05)
        self.assertGreater(p[1], .95)

    def test_controle_ne_active_jamais_le_challenger(self):
        rows = []
        for i in range(240):
            jour = dt.date(2024, 6, 1) if i < 120 else dt.date(2025, 6, 1)
            rows.append({'date': jour+dt.timedelta(days=i % 100), 'semaine': f'{jour.year}-S{i%20:02d}',
                         'y': (i*7) % 11 > 4, 'elo': .45+.01*(i%10), 'service_retour': .46+.008*(i%8),
                         'style': (i%7-3)/3, 'surface': ('Hard', 'Clay')[i%2], 'circuit': 'ATP',
                         'documentation_balles': 50*(i%20), 'documentation_matchs': i%80})
        with mock.patch.object(ST, 'observations_controle', return_value=rows):
            out = ST.evaluer_controle([], set(), dt.date(2025, 1, 1), bootstrap=0)
        self.assertEqual((out['n_decouverte'], out['n_confirmation']), (120, 120))
        self.assertFalse(out['activation'])
        self.assertIn('Elo général et surface', out['controles'])


if __name__ == '__main__':
    unittest.main()
