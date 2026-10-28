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

    def test_statistiques_service_retour_et_ecart_a_tous_styles(self):
        M = [match(i) for i in range(7)]
        acc, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'}},
                             dt.date(2024, 4, 1))
        ligne = acc[('a', 'equilibre', 'global')]
        stats = SD.statistiques(ligne, acc[('a', SD.TOUS_STYLES, 'global')])
        self.assertEqual(stats['matchs'], 1)
        self.assertEqual((stats['points_service'], stats['points_retour']), (100, 100))
        self.assertEqual(stats['service_gagnes_pct'], 60.0)
        self.assertEqual(stats['retour_gagnes_pct'], 40.0)
        self.assertEqual(stats['points_gagnes_pct'], 50.0)
        self.assertEqual(stats['premiere_balle_pct'], 60.0)
        self.assertEqual(stats['gagnes_1re_pct'], 70.0)
        self.assertEqual(stats['gagnes_2e_pct'], 45.0)
        self.assertEqual(stats['aces_pct'], 6.0)
        self.assertEqual(stats['doubles_fautes_pct'], 5.0)
        self.assertEqual(stats['balles_break_sauvees_pct'], 50.0)
        self.assertEqual(stats['balles_break_converties_pct'], 50.0)
        self.assertTrue(all(v == 0 for v in stats['ecarts_tous_styles_points'].values()))
        self.assertEqual(acc[('a', SD.TOUS_STYLES, 'global')]['stats_n'], 7)

    def test_statistiques_absentes_ne_deviennent_pas_zero(self):
        M = [match(i) for i in range(7)]
        M[-1]['detail'] = None
        acc, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'}},
                             dt.date(2024, 4, 1))
        ligne = acc[('a', 'equilibre', 'global')]
        self.assertEqual(ligne['n'], 1)
        self.assertIsNone(SD.statistiques(ligne))

    def test_statistiques_du_jour_de_reference_non_supposees_connues(self):
        M = [match(i) for i in range(8)]
        jour = M[-1]['date']
        acc, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'}}, jour)
        self.assertEqual(SD.statistiques(acc[('a', 'equilibre', 'global')])['matchs'], 1)
        acc_apres, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'}},
                                   jour + dt.timedelta(days=1))
        self.assertEqual(SD.statistiques(acc_apres[('a', 'equilibre', 'global')])['matchs'], 2)

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


class AttenduTests(unittest.TestCase):
    """28/10/2026 : bilan réel comparé à l'attendu vu la force des adversaires (Elo d'avant-match)."""

    def test_attendu_et_ecart(self):
        r = SD.resume({'n': 4, 'v': 1, 'derniers': [], 'att': 0.8, 'n_att': 4})
        self.assertEqual(r['attendu_pct'], 20.0)
        self.assertEqual(r['ecart_pts'], 5.0)
        self.assertNotIn('attendu_pct', SD.resume({'n': 4, 'v': 1, 'derniers': []}))

    def test_attendu_pre_match_et_complementaire(self):
        M = [match(i) for i in range(7)]
        acc, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'},
                                 'b': {'circuit': 'ATP', 'surface': 'Hard'}}, dt.date(2024, 4, 1))
        a = SD.resume(acc.get(('a', 'equilibre', 'global')))
        b = SD.resume(acc.get(('b', 'equilibre', 'global')))
        # a a gagné les six matchs précédents : l'Elo d'AVANT le 7e le donne favori, pas à 100 %
        self.assertGreater(a['attendu_pct'], 50)
        self.assertLess(a['attendu_pct'], 100)
        self.assertAlmostEqual(a['attendu_pct'] + b['attendu_pct'], 100.0, places=0)
        self.assertEqual(a['derniers'][0]['attendu_pct'], a['attendu_pct'])


class DifficulteTests(unittest.TestCase):
    """28/10/2026 : difficulté des adversaires (Elo d'avant-match), note figée sur 10."""

    def test_note_bornee_et_outsider(self):
        r = SD.resume({'n': 2, 'v': 1, 'derniers': [], 'att': 0.9, 'n_att': 2, 'outsider': 1,
                       'elo_adv': 2 * 1750.0, 'n_elo': 2})
        self.assertEqual(r['difficulte'], {'note': 5.0, 'elo_moyen': 1750, 'matchs_outsider': 1})
        haut = SD.resume({'n': 1, 'v': 0, 'derniers': [], 'elo_adv': 2400.0, 'n_elo': 1})
        bas = SD.resume({'n': 1, 'v': 0, 'derniers': [], 'elo_adv': 1200.0, 'n_elo': 1})
        self.assertEqual((haut['difficulte']['note'], bas['difficulte']['note']), (10.0, 0.0))

    def test_elo_adverse_pre_match(self):
        M = [match(i) for i in range(7)]
        acc, _ = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'},
                                 'b': {'circuit': 'ATP', 'surface': 'Hard'}}, dt.date(2024, 4, 1))
        a = SD.resume(acc.get(('a', 'equilibre', 'global')))
        b = SD.resume(acc.get(('b', 'equilibre', 'global')))
        # avant le 7e match, b a perdu six fois : son Elo est sous celui de a ; a affronte donc le plus faible
        self.assertLess(a['difficulte']['elo_moyen'], b['difficulte']['elo_moyen'])
        self.assertEqual(b['difficulte']['matchs_outsider'], 1)
        self.assertEqual(a['difficulte']['matchs_outsider'], 0)
