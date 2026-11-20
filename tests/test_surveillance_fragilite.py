"""Fragilité revérifiée chaque semaine (04/11/2026) : hystérésis deux semaines, semaine pauvre neutre."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import surveillance_fragilite as SF  # noqa: E402


class Decision(unittest.TestCase):
    def test_leve_apres_deux_semaines_non_justifiees(self):
        e = SF.decider(None, {'assez': True, 'justifie': False}, True)
        self.assertTrue(e['actif'])
        e = SF.decider(e, {'assez': True, 'justifie': False}, True)
        self.assertFalse(e['actif'])

    def test_semaine_pauvre_neutre_et_serie_remise_a_zero(self):
        e = SF.decider(None, {'assez': True, 'justifie': False}, True)
        e = SF.decider(e, {'assez': False}, True)
        self.assertTrue(e['actif'])
        e = SF.decider(e, {'assez': True, 'justifie': True}, True)
        self.assertEqual(e['serie'], 0)

    def test_entre_apres_deux_semaines_justifiees(self):
        e = SF.decider(None, {'assez': True, 'justifie': True}, False)
        self.assertFalse(e['actif'])
        e = SF.decider(e, {'assez': True, 'justifie': True}, False)
        self.assertTrue(e['actif'])

    def test_criteres(self):
        r = {'p': .55, 'pe': .6, 'ps': .4, 'xp': 20}
        self.assertTrue(SF.CRITERES['favoris_opposes'][1](r))
        self.assertTrue(SF.CRITERES['experience_30'][1](r))
        self.assertTrue(SF.CRITERES['match_serre'][1](r))
        self.assertFalse(SF.CRITERES['gros_favori'][1](r))

    def test_pronostic_bouge(self):
        f = SF.CRITERES['pronostic_bouge'][1]
        self.assertTrue(f({'p': .6, 'p0': .60, 'p1': .66}))
        self.assertFalse(f({'p': .6, 'p0': .60, 'p1': .63}))
        self.assertFalse(f({'p': .6, 'p0': None, 'p1': .70}))

    def test_huitiemes(self):
        self.assertTrue(SF.CRITERES['huitiemes'][1]({'p': .6, 'tour': 'Round of 16'}))
        self.assertFalse(SF.CRITERES['huitiemes'][1]({'p': .6, 'tour': 'Round of 32'}))
        self.assertFalse(SF.CRITERES['huitiemes'][1]({'p': .6}))

    def test_actifs_par_defaut(self):
        self.assertEqual(SF.actifs('/nulle/part'), {'favoris_opposes'})


if __name__ == '__main__':
    unittest.main()
