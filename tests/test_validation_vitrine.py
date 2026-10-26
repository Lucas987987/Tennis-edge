import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import match_simule as MS
import nos_resultats as NR
import validation_vitrine as VV


def document_valide():
    c = {'f': .62, 'a': .05, 'w1': .76, 'd': .04, 'w2j': .56, 'bp': 0.}
    gagnant, sets, stats, breaks, ntb, points = MS.un_match(c, c, 2, 7, random.Random(17), True, True)
    score = VV.score_texte(sets)
    scenario = {'score': score, 'sets': [list(x) for x in sets], 'points': ''.join(map(str, points)),
                'premier_serveur': True, 'simulation_index': 17}
    return {'simulations': 20000, 'matchs': [{
        'uid': 'test', 'simulation_disponible': True, 'scores_probables': [[score, .03]],
        'simulation': {'n': 20000, 'version': 'simulation', 'sets_gagnants': 2,
                       'tb_final': 7, 'scenario': scenario},
    }]}


class ValidationVitrine(unittest.TestCase):
    def test_trace_reelle_et_score_modal_acceptes(self):
        doc = document_valide()
        self.assertTrue(VV.valider(doc))
        sc = doc['matchs'][0]['simulation']['scenario']
        rejoue = VV.rejouer_trace(sc['points'], premier_serveur=True)
        self.assertEqual(rejoue['score'], sc['score'])

    def test_ancien_export_sans_scenario_est_refuse(self):
        doc = document_valide()
        del doc['matchs'][0]['simulation']['scenario']
        with self.assertRaisesRegex(ValueError, 'score le plus fréquent'):
            VV.valider(doc)

    def test_5000_est_refuse(self):
        doc = document_valide()
        doc['simulations'] = doc['matchs'][0]['simulation']['n'] = 5000
        with self.assertRaisesRegex(ValueError, '5000'):
            VV.valider(doc)

    def test_un_match_sans_simulation_bloque_tout_le_catalogue(self):
        doc = document_valide()
        del doc['matchs'][0]['simulation']
        with self.assertRaisesRegex(ValueError, 'simulation complète absente'):
            VV.valider(doc)

    def test_un_identifiant_duplique_est_refuse(self):
        doc = document_valide()
        doc['matchs'].append(copy.deepcopy(doc['matchs'][0]))
        with self.assertRaisesRegex(ValueError, 'publié en double'):
            VV.valider(doc)

    def test_score_annonce_different_de_la_trace_est_refuse(self):
        doc = document_valide()
        doc['matchs'][0]['simulation']['scenario']['score'] = '6-0 6-0'
        doc['matchs'][0]['scores_probables'][0][0] = '6-0 6-0'
        with self.assertRaisesRegex(ValueError, 'trace='):
            VV.valider(doc)

    def test_point_surnumeraire_est_refuse(self):
        doc = document_valide()
        doc['matchs'][0]['simulation']['scenario']['points'] += '0'
        with self.assertRaisesRegex(ValueError, 'surnuméraires'):
            VV.valider(doc)

    def test_vienne_reste_sur_dur_meme_si_ancienne_table_dit_terre(self):
        self.assertEqual(NR.surface_de('ATP Vienna', {'vienna': 'Clay'}), 'Hard')
        self.assertEqual(NR.surface_de('Vienna, Austria', {'vienna': 'Clay'}), 'Hard')

    def test_stabilite_doit_porter_sur_le_score_publie(self):
        doc = document_valide()
        sim = doc['matchs'][0]['simulation']
        sim['stabilite_score'] = {'statut': 'stable', 'score_reference': '6-0 6-0', 'n_par_bloc': 20000}
        with self.assertRaisesRegex(ValueError, 'stabilité'):
            VV.valider(doc)

    def test_chaque_rejeu_utilise_le_scenario_modal(self):
        chemin = os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html')
        with open(chemin, encoding='utf-8') as f:
            html = f.read()
        self.assertIn('if (seed == null && traceTop)', html)
        self.assertNotIn('mon === 1 && traceTop', html)
        self.assertNotIn('mon === 1 && !traceTop', html)
        self.assertNotIn('tire ensuite un autre match au hasard', html)
        self.assertNotIn('then draws another match at random', html)


    def test_catalogue_conserve_un_lien_direct_si_le_clic_dynamique_echoue(self):
        chemin = os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html')
        with open(chemin, encoding='utf-8') as f:
            html = f.read()
        self.assertIn('<a class="match-open" href="${m.uid===mdj?', html)
        self.assertIn("'#match='+encodeURIComponent(m.uid)", html)
        self.assertIn('let id = matchDemande() || selectionId || idJour', html)
        self.assertIn("window.addEventListener('hashchange'", html)
        self.assertIn("e.target.closest('a[data-uid]')", html)
        self.assertIn('if (ouvrirMatch(a.dataset.uid)) e.preventDefault();', html)
        self.assertNotIn("e.target.closest('button[data-uid]')", html)


if __name__ == '__main__':
    unittest.main()
