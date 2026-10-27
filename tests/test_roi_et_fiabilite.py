import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import roi_algo as ROI
import fiabilite as FI
import validation_fiabilite as VF


def match_note(i, note, p, gagnant):
    return {'uid': str(i), 'debut': f'2026-{8+i//28:02d}-{1+i%28:02d}T10:00',
            'home': 'A', 'away': 'B', 'circuit': 'ATP', 'surface': 'Hard',
            'fiabilite': {'note': note}, 'reel': {'gagnant': gagnant},
            'premier': {'combinaison': {'p_home': p}}}


class ROIComptable(unittest.TestCase):
    def test_mise_unite_et_gain_net(self):
        # R1 choisit home à 2,0 et le match est gagné : +1 unité pour 1 unité misée.
        paris = ROI.paris([('2026-01-01_a_b', 'ATP', .6, 'home')], {'2026-01-01_a_b': (2., 1.8)})
        self.assertEqual(len(paris['R1']), 1)
        self.assertEqual(ROI.bilan(paris['R1'])['unites'], 1.)
        self.assertEqual(ROI.bilan(paris['R1'])['roi'], 1.)

    def test_regle_valeur_ne_change_pas_la_probabilite(self):
        lignes = [('2026-01-01_a_b', 'ATP', .6, 'home')]
        paris = ROI.paris(lignes, {'2026-01-01_a_b': (2., 3.)})
        self.assertEqual(lignes[0][2], .6)
        self.assertEqual(len(paris['R2']), 2)  # 0,6×2 et 0,4×3 franchissent tous deux 1,05
        self.assertEqual(ROI.bilan(paris['R2'])['unites'], 0.)

    def test_moins_de_30_paris_ne_conclut_pas(self):
        texte = ROI._ligne('R1', {'n': 12, 'gagnes': 8, 'unites': 2., 'roi': .1, 'cote_moy': 1.8, 'ic95': None})
        self.assertIn('rien à conclure', texte)


class PerformanceCircuit(unittest.TestCase):
    def test_challenger_survendu_ne_peut_plus_avoir_une_note_elevee(self):
        def match(circuit):
            return {'uid': 'courant-'+circuit, 'circuit': circuit, 'surface': 'Hard',
                    'matchs_joues': [80, 80], 'style_connu': [True, True],
                    'stats': {'p_home': .70}, 'simulation': {'p_home': .72},
                    'combinaison': {'p_home': .71, 'match_simule': {
                        'profil_connu': [True, True], 'stabilite_score': {'statut': 'stable'}}}}
        hist_atp = [{'uid': f'a{i}', 'circuit': 'ATP', 'surface': 'Hard', 'p': .85, 'y': 1} for i in range(60)]
        hist_ch = [{'uid': f'c{i}', 'circuit': 'CH', 'surface': 'Hard', 'p': .85, 'y': 0} for i in range(60)]
        atp = FI.evaluer(match('ATP'), hist_atp)
        ch = FI.evaluer(match('CH'), hist_ch)
        self.assertGreater(atp['note'], ch['note'])
        self.assertLessEqual(ch['note'], 64)
        self.assertEqual(ch['categorie'], 'B_incertain')
        self.assertGreater(ch['performance_circuit']['perte_residuelle'], .05)
        self.assertLess(ch['composantes']['performance_circuit'], 50)

    def test_circuit_sans_historique_reste_neutre(self):
        r = FI.performance_circuit('CH', [])
        self.assertEqual(r['score'], .5)
        self.assertEqual(r['n'], 0)


class ControleNotes(unittest.TestCase):
    def test_notes_confirmees_seulement_avec_contraste_fort(self):
        rows = []
        for i in range(80):
            haut = i % 2 == 0
            rows.append(match_note(i, 85 if haut else 30, .85, 'home' if haut else 'away'))
        out = VF.evaluer({'matchs': rows})
        self.assertEqual(out['effectifs_contraste']['notes_correct_ou_solide'], 40)
        self.assertEqual(out['effectifs_contraste']['notes_fragile_ou_prudent'], 40)
        self.assertEqual(out['verdict_notes'], 'confirmees')
        self.assertIn('ic95_exactitude_wilson', out['global'])
        self.assertEqual(out['global']['defaites_du_favori'], 40)
        self.assertIn('ATP', out['par_circuit'])
        self.assertIn('tres_peu_documente', out['par_documentation'])
        self.assertIn('spearman_note_vs_perte_residuelle', out)

    def test_effectif_insuffisant_ne_valide_pas(self):
        rows = [match_note(i, 85 if i % 2 else 30, .85, 'home' if i % 2 else 'away') for i in range(40)]
        out = VF.evaluer({'matchs': rows})
        self.assertEqual(out['statut'], 'accumulation')
        self.assertEqual(out['verdict_notes'], 'accumulation')


if __name__ == '__main__':
    unittest.main()
