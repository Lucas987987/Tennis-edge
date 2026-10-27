"""Contrôles des bilans descriptifs par style, sans entrée dans le modèle."""
import copy
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import styles_descriptifs as SD
import vitrine as V


def profil(w1=.70, w2j=.55, r1=.70, r2j=.55, ace=.08):
    return {'w1': w1, 'w2j': w2j, 'r1': r1, 'r2j': r2j, 'a': ace}


def match(i, complet=True, surface='Hard'):
    jour = dt.date(2024, 1, 1) + dt.timedelta(days=10*i)
    # Feuilles moyennes : six matchs documentent plus de 500 balles effectives.
    detail = (100, 60, 42, 18, 6, 2, 4, 2, 10)
    return {'date': jour, 'fin': jour + dt.timedelta(days=2), 'circuit': 'ATP', 'surface': surface,
            'bo': 3, '_g': 'a', '_p': 'b', 'gagnant': 'a', 'perdant': 'b',
            'nom_g': 'Joueur A', 'nom_p': 'Joueur B', 'sets': [(6, 4), (6, 3)],
            'complet': complet, 'abandon': not complet, 'tournoi': 'Test',
            'detail': {'w': detail, 'l': detail}, 'tour': 1, 'num': i}


class ClassificationTests(unittest.TestCase):
    def test_styles_observables_et_documentation(self):
        mu = profil()
        self.assertEqual(SD.classifier(profil(), 499, mu), 'indetermine')
        self.assertEqual(SD.classifier(profil(), 500, mu), 'equilibre')
        self.assertEqual(SD.classifier(profil(w1=.78, w2j=.60, ace=.12), 1000, mu), 'grand_serveur')
        self.assertEqual(SD.classifier(profil(w1=.78, w2j=.60, ace=.08), 1000, mu), 'serveur_attaquant')
        self.assertEqual(SD.classifier(profil(r1=.65, r2j=.50), 1000, mu), 'retourneur_pressant')
        self.assertEqual(SD.classifier(profil(w1=.65, w2j=.50, r1=.65, r2j=.50), 1000, mu), 'contreur')

    def test_wilson_et_niveaux_documentent_l_incertitude(self):
        r = SD.resume({'n': 7, 'v': 5, 'derniers': []})
        self.assertEqual(r['pct'], 71.4)
        self.assertEqual(r['documentation'], 'tres_faible')
        self.assertLess(r['ic95'][0], 50)
        self.assertGreater(r['ic95'][1], 90)
        self.assertEqual(SD.documentation(10), 'faible')
        self.assertEqual(SD.documentation(30), 'intermediaire')
        self.assertEqual(SD.documentation(100), 'large')


class HistoriqueTests(unittest.TestCase):
    def test_global_surface_derniers_et_sens_du_score(self):
        M = [match(i) for i in range(7)]
        acc, courants = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'},
                                        'b': {'circuit': 'ATP', 'surface': 'Hard'}},
                                    dt.date(2024, 4, 1))
        # Les six premiers matchs documentent les styles ; le septième entre au bilan.
        a = SD.resume(acc.get(('a', 'equilibre', 'global')))
        b = SD.resume(acc.get(('b', 'equilibre', 'global')))
        self.assertEqual((a['n'], a['victoires']), (1, 1))
        self.assertEqual((b['n'], b['victoires']), (1, 0))
        self.assertEqual(SD.resume(acc.get(('a', 'equilibre', 'Hard')))['n'], 1)
        self.assertIsNone(SD.resume(acc.get(('a', 'equilibre', 'Clay')))['pct'])
        self.assertEqual(a['derniers'][0]['score'], '6-4 6-3')
        self.assertEqual(b['derniers'][0]['score'], '4-6 3-6')
        self.assertNotEqual(courants['a']['style'], 'indetermine')

    def test_incomplet_et_futur_exclus(self):
        M = [match(i) for i in range(7)] + [match(7, complet=False), match(8)]
        jour = dt.date(2024, 3, 15)  # après l'incomplet du 11 mars, avant le match du 21
        acc, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'}}, jour)
        self.assertEqual(SD.resume(acc.get(('a', 'equilibre', 'global')))['n'], 1)

    def test_le_resultat_ne_change_pas_le_style_avant_le_match(self):
        M = [match(i) for i in range(7)]
        inverse = [dict(m) for m in M]
        inverse[-1] = dict(inverse[-1], nom_g='Joueur B', nom_p='Joueur A',
                           _g='b', _p='a', gagnant='b', perdant='a')
        cibles = {'a': {'circuit': 'ATP', 'surface': 'Hard'}, 'b': {'circuit': 'ATP', 'surface': 'Hard'}}
        a1, _ = SD.calculer(M, cibles, dt.date(2024, 4, 1))
        a2, _ = SD.calculer(inverse, cibles, dt.date(2024, 4, 1))
        # Le septième résultat change le bilan, pas la catégorie contre laquelle il est compté.
        self.assertIn(('a', 'equilibre', 'global'), a1)
        self.assertIn(('b', 'equilibre', 'global'), a2)

    def test_resultat_du_meme_jour_non_suppose_connu(self):
        M = [match(i) for i in range(8)]
        jour = M[-1]['date']
        acc, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'}}, jour)
        # Le septième résultat est disponible ; celui du huitième, joueur le jour de référence, ne l'est pas.
        self.assertEqual(SD.resume(acc.get(('a', 'equilibre', 'global')))['n'], 1)
        jour_suivant = jour + dt.timedelta(days=1)
        acc_apres, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'}}, jour_suivant)
        self.assertEqual(SD.resume(acc_apres.get(('a', 'equilibre', 'global')))['n'], 2)


if __name__ == '__main__':
    unittest.main()
