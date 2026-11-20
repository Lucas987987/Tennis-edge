"""Changement de surface (04/11/2026) : définition point-in-time, fantôme par circuit, juge par circuit."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import etude_changement_surface as EC  # noqa: E402
import facteurs as FA  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402

J = 86400.0


class Definition(unittest.TestCase):
    def test_premier_et_deuxieme_match_seulement(self):
        Sf = {'a': [(0.0, 'Clay'), (1 * J, 'Clay'), (10 * J, 'Hard'), (11 * J, 'Hard')]}
        self.assertEqual(FA.nouveau_surface(Sf, 'a', 'Hard', 10 * J), 1.0)    # 1er match sur dur
        self.assertEqual(FA.nouveau_surface(Sf, 'a', 'Hard', 11 * J), 1.0)    # 2e
        self.assertEqual(FA.nouveau_surface(Sf, 'a', 'Hard', 12 * J), 0.0)    # 3e : adapté
        self.assertEqual(FA.nouveau_surface(Sf, 'a', 'Clay', 1 * J), 0.0)     # pas de changement
        self.assertEqual(FA.nouveau_surface(Sf, 'a', 'Grass', 80 * J), 0.0)   # retour de pause (> 45 j)
        self.assertEqual(FA.nouveau_surface({}, 'b', 'Hard', 5 * J), 0.0)

    def test_meme_definition_que_l_etude(self):
        s, d0 = EC.Suivi(), dt.date(2026, 1, 1)
        hist, faits = [], []
        for n, su in ((0, 'Clay'), (1, 'Clay'), (10, 'Hard'), (11, 'Hard'), (12, 'Hard'), (80, 'Grass')):
            d = d0 + dt.timedelta(n)
            faits.append((s.nouveau('a', d, su), FA.nouveau_surface({'a': hist}, 'a', su, n * J)))
            s.jouer('a', d, su)
            hist = hist + [(n * J, su)]
        self.assertEqual([a for a, _ in faits], [int(b) for _, b in faits])


class Fantome(unittest.TestCase):
    def setUp(self):
        self.ancien = PD.CONTEXTE

        class Ctx:
            surfaces = {'h': [(0.0, 'Clay')], 'a': [(0.0, 'Hard')]}

            def nouveau_surface(self, j, s, t):
                return FA.nouveau_surface(self.surfaces, j, s, t)
        PD.CONTEXTE = Ctx()

    def tearDown(self):
        PD.CONTEXTE = self.ancien

    def test_le_nouveau_est_moins_fort(self):
        debut = dt.datetime(1970, 1, 6, tzinfo=dt.timezone.utc)
        r = PD.controle_changement_surface(0.6, 'ATP', 'h', 'a', 'Hard', debut)
        self.assertEqual(r['x'], 1.0)
        self.assertLess(r['p_home'], 0.6)
        self.assertIsNone(PD.controle_changement_surface(0.6, 'ITF', 'h', 'a', 'Hard', debut))

    def test_juge_par_circuit(self):
        self.assertIn('changement_surface', FC.SIGNAUX)
        b = {'circuit': 'WTA', 'debut': '2026-11-03', 'ecarts': {'fantome_changement_surface': {'ll_elo': .7, 'll_reference': .6}}}
        self.assertEqual(FC.paires(b, 'changement_surface'), (.7, .6))


if __name__ == '__main__':
    unittest.main()
