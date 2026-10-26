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
    scenario.update({'selection': 'representatif', 'vainqueur': 0 if gagnant == 0 else 1})
    return {'simulations': 20000, 'matchs': [{
        'uid': 'test', 'p_home': .62 if gagnant == 0 else .38,
        'simulation_disponible': True, 'scores_probables': [[score, .03]],
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

    def test_scenario_representatif_peut_etre_different_du_score_modal(self):
        doc = document_valide()
        doc['matchs'][0]['scores_probables'].insert(0, ['0-6 0-6', .04])
        self.assertTrue(VV.valider(doc))

    def test_scenario_representatif_suit_le_favori_de_la_variante(self):
        doc = document_valide()
        m = doc['matchs'][0]
        m['p_home'] = .99 if m['p_home'] < .5 else .01
        with self.assertRaisesRegex(ValueError, 'vainqueur favori'):
            VV.valider(doc)

    def test_match_type_choisit_un_medoid_pas_un_score_impose(self):
        def ligne(sets, valeur):
            f = {k: float(valeur) for k in MS.CLES_FEUILLE}
            return (' '.join(f'{a}-{b}' for a, b in sets), f, dict(f), [], sets)
        brut = [ligne([(6, 0), (6, 0)], 0),
                ligne([(6, 4), (3, 6), (6, 4)], 10),
                ligne([(6, 4), (6, 4)], 20),
                ligne([(0, 6), (0, 6)], 10)]
        traces = [(1, b'0') for _ in brut]
        a = MS.match_type(brut, traces, vainqueur=0)
        b = MS.match_type(brut, traces, vainqueur=0)
        self.assertEqual(a['simulation_index'], 1)
        self.assertEqual(a['score'], '6-4 3-6 6-4')
        self.assertEqual(a['selection'], 'representatif')
        self.assertEqual(a, b)

    def test_ancien_export_sans_scenario_est_refuse(self):
        doc = document_valide()
        del doc['matchs'][0]['simulation']['scenario']
        with self.assertRaisesRegex(ValueError, 'scénario représentatif'):
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

    def test_chaque_rejeu_utilise_le_scenario_representatif(self):
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
        self.assertIn('const demande = matchDemande()', html)
        self.assertIn('let id = demande || selectionId || idJour', html)
        self.assertIn("window.addEventListener('hashchange'", html)
        self.assertIn("e.target.closest('a[data-uid]')", html)
        self.assertIn('if (ouvrirMatch(a.dataset.uid)) e.preventDefault();', html)
        self.assertNotIn("e.target.closest('button[data-uid]')", html)

    def test_catalogue_ne_compte_que_les_simulations_reellement_presentes(self):
        chemin = os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html')
        with open(chemin, encoding='utf-8') as f:
            html = f.read()
        self.assertIn("D.matchs.filter(m=>m.simulation && m.simulation_disponible !== false &&", html)
        self.assertIn("D.matchs.filter(m=>m.simulation && m.simulation_disponible !== false).length", html)
        self.assertNotIn("t('compte_matchs',tous.length,D.matchs.length)", html)

    def test_lien_incomplet_ne_retombe_pas_silencieusement_sur_match_du_jour(self):
        chemin = os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html')
        with open(chemin, encoding='utf-8') as f:
            html = f.read()
        self.assertIn("if (!m && !demande && idJour)", html)
        self.assertIn("t(demande ? 'sim_indisponible' : 'mdj_vide')", html)
        self.assertNotIn("if (!m && idJour)", html)

    def test_pages_se_redeploie_apres_chaque_generation_reussie(self):
        chemin = os.path.join(os.path.dirname(__file__), '..', '.github', 'workflows', 'pages.yml')
        with open(chemin, encoding='utf-8') as f:
            yml = f.read()
        self.assertIn("workflows: ['Pronostics du jour']", yml)
        self.assertIn('types: [completed]', yml)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", yml)


class WorkflowVideoTelegram(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chemin = os.path.join(os.path.dirname(__file__), '..', '.github', 'workflows', 'video_simulation.yml')
        with open(chemin, encoding='utf-8') as f:
            cls.yml = f.read()

    def test_uid_manuel_recharge_le_catalogue_public(self):
        self.assertIn("if uid_demande and not m:", self.yml)
        self.assertIn('https://algo.tennis-edge.workers.dev/donnees.json', self.yml)
        self.assertIn('https://lucas987987.github.io/Tennis-edge/algo/donnees.json', self.yml)
        self.assertIn("json.dump(d, f, ensure_ascii=False", self.yml)

    def test_uid_manuel_absent_fait_echouer_le_run(self):
        self.assertIn('raise SystemExit(f"UID demandé introuvable ou sans simulation', self.yml)
        self.assertNotIn("uid = os.environ.get('UID_DEMANDE') or", self.yml)

    def test_echec_telegram_ne_peut_plus_produire_un_run_vert(self):
        self.assertIn("Telegram non configuré : vidéos non envoyées.'; exit 1", self.yml)
        self.assertEqual(self.yml.count('curl --fail-with-body'), 2)
        self.assertNotIn('|| echo "::warning::envoi Telegram', self.yml)
        self.assertNotIn('|| echo "::warning::carte Telegram', self.yml)
        self.assertIn('test -s "videos/simulation_${lang}.mp4"', self.yml)


if __name__ == '__main__':
    unittest.main()
