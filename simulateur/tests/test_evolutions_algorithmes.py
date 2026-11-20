import copy
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import charting as CH
import contexte_optionnel as CO
import distribution_exacte as DE
import gouvernance_candidats as GC
import hierarchie as HI
import match_simule as MS


class DistributionExacteTest(unittest.TestCase):
    def test_distribution_normalisee_et_victoire_identique(self):
        for bo in (2, 3):
            d = DE.distribution_match(.63, .61, bo)
            self.assertTrue(DE.controle(d)['ok'])
            self.assertAlmostEqual(DE.victoire_depuis_distribution(d), MS.victoire(.63, .61, bo), places=11)

    def test_forme_et_symetrie(self):
        a = {'f': .6, 'a': .08, 'w1': .72, 'd': .03, 'w2j': .53}
        b = {'f': .62, 'a': .06, 'w1': .69, 'd': .04, 'w2j': .51}
        d = DE.distribution_forme(a, b, 2, .15)
        self.assertAlmostEqual(DE.victoire_depuis_distribution(d), MS.victoire_pure(a, b, 2, .15), places=11)
        inverse = DE.distribution_match(.61, .63, 2)
        for score, p in DE.distribution_match(.63, .61, 2).items():
            renverse = tuple((y, x) for x, y in score)
            self.assertAlmostEqual(p, inverse[renverse], places=12)

    def test_ancrage_sous_la_tolerance_du_controle_quotidien(self):
        # Cas reproductible qui laissait un résidu de 1,002e-8 avec 30 dichotomies.
        a = MS.ajuster({'f': .6, 'a': .08, 'w1': .72, 'd': .03, 'w2j': .53},
                       0.5609509048588737)
        b = MS.ajuster({'f': .62, 'a': .06, 'w1': .69, 'd': .04, 'w2j': .51,
                        'bp': -0.28834090169682697}, 0.6069058863227424)
        d = DE.distribution_forme(a, b, 2, .15, p_victoire=.5346)
        self.assertTrue(DE.controle(d)['ok'])
        self.assertLessEqual(abs(DE.victoire_depuis_distribution(d) - .5346), 1e-9)


class HierarchieTest(unittest.TestCase):
    def match(self, g='A', p='B'):
        return {'gagnant': g, 'perdant': p, 'circuit': 'ATP', 'surface': 'Hard',
                'date': dt.date(2024, 1, 1), 'fin': dt.date(2024, 1, 7),
                'stats': {'w': (60, 40), 'l': (60, 35)}}

    def test_partage_et_mise_a_jour_apres_ajout(self):
        h = HI.HierarchieServiceRetour()
        avant = h.point('A', 'B', 'ATP', 'Hard')
        self.assertAlmostEqual(avant, .62)
        for _ in range(10):
            h.ajouter(self.match())
        self.assertGreater(h.point('A', 'B', 'ATP', 'Hard'), avant)
        self.assertGreater(h.documentation('A'), 0)
        # Les effets locaux existent, mais la force globale reste partagée.
        self.assertIn('A', h.joueurs)
        self.assertIn(('A', 'Hard'), h.surfaces)

    def test_incertitude_diminue_avec_documentation(self):
        h = HI.HierarchieServiceRetour()
        inconnu, _ = h.sigma('A', 'B', dt.date(2024, 2, 1))
        for _ in range(20):
            h.ajouter(self.match())
        documente, _ = h.sigma('A', 'B', dt.date(2024, 1, 8))
        self.assertLess(documente, inconnu)
        self.assertLessEqual(documente, HI.SIGMA_MAX)


class ChartingTest(unittest.TestCase):
    def test_prior_et_profil_sans_fuite_future(self):
        passe = (dt.date(2024, 1, 1), 100, 30, 100, 70, 100, 20)
        futur = (dt.date(2025, 1, 1), 100, 90, 100, 10, 100, 90)
        date = dt.date(2024, 6, 1)
        a = CH.Charting({'A': [passe]})
        b = CH.Charting({'A': [passe], 'B': [futur]})
        self.assertEqual(a.profil('A', date), b.profil('A', date))
        self.assertEqual(b.documentation('A', dt.date(2024, 1, 1))['matchs'], 0)
        self.assertEqual(b.documentation('A', date)['matchs'], 1)

    def test_variables_match_antisymetriques(self):
        a = CH.variables_match((.1, .02, .03), (.04, -.01, -.02))
        c = CH.variables_match((.04, -.01, -.02), (.1, .02, .03))
        for k in a:
            self.assertAlmostEqual(a[k], -c[k])


class GouvernanceEtConnecteursTest(unittest.TestCase):
    def test_manifeste_et_future_uniquement(self):
        m = GC.charger(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.assertTrue(GC.auditer(m)['ok'])
        ancien = [{'date': '2024-01-01', 'pronostic_fige': True, 'resultat_resolu': True, 'apparie_champion': True}]
        self.assertFalse(GC.auditer(m, ancien)['ok'])

    def test_horodatage_strict_et_repli(self):
        idx = CO.horodatages([{'match_id': 'm1', 'debut': '2026-01-01T12:00:00Z', 'source': 'test'}])
        self.assertTrue(CO.appliquer_horodatage({'match_id': 'm1'}, idx)['horodatage_reel'])
        self.assertFalse(CO.appliquer_horodatage({'match_id': 'autre'}, idx)['horodatage_reel'])
        with self.assertRaises(ValueError):
            CO.instant('2026-01-01 12:00:00')

    def test_donnees_physiques_futures_exclues(self):
        rows = [{'joueur': 'A', 'observe_le': '2026-01-02T00:00:00Z', 'minutes_jouees_7j': 100}]
        self.assertEqual(CO.physiques(rows, '2026-01-01T00:00:00Z'), [])


if __name__ == '__main__':
    unittest.main()
