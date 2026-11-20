import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import profils_robustes as PR
import stabilite_scores as SS
import surveillance_derive as SD


def sim(scores, n=20000):
    return {'n': n, 'scores': scores}


def metriques(n, ll, brier=.2):
    return {'n': n, 'log_loss': ll, 'brier': brier}


def rapport(ll_dec=.6, ll_conf=.6, sparse=.6, tres=.65, n_sparse=100, n_tres=40):
    return {'decouverte': {'global': metriques(200, ll_dec)},
            'confirmation': {'global': metriques(200, ll_conf),
                             'peu_documente': metriques(n_sparse, sparse),
                             'tres_peu_documente': metriques(n_tres, tres)}}


class StabiliteScores(unittest.TestCase):
    def test_meme_modal_et_ecarts_suffisants(self):
        ref = sim([['6-4 6-4', .031], ['6-3 6-4', .029], ['4-6 6-4 6-3', .02]])
        out = SS.synthetiser(ref, [ref, ref])
        self.assertEqual(out['statut'], 'stable')
        self.assertEqual(out['accord_modal'], 1)
        self.assertEqual(out['blocs_controle'], 2)

    def test_modal_different_est_instable(self):
        ref = sim([['6-4 6-4', .031], ['6-3 6-4', .029]])
        autre = sim([['6-3 6-4', .032], ['6-4 6-4', .03]])
        self.assertEqual(SS.synthetiser(ref, [autre])['statut'], 'instable')

    def test_quasi_egalite_est_fragile(self):
        ref = sim([['6-4 6-4', .0300], ['6-3 6-4', .0295]])
        self.assertEqual(SS.synthetiser(ref, [ref])['statut'], 'fragile')


class SurveillanceDerive(unittest.TestCase):
    def test_degradation_et_surconfiance_detectees(self):
        avant = [{'p': .6, 'y': i % 2, 'date': __import__('datetime').date(2026, 1, 1)} for i in range(40)]
        courant = [{'p': .99, 'y': 0, 'date': __import__('datetime').date(2026, 2, 1)} for _ in range(40)]
        out = SD.comparer(courant, avant)
        self.assertIn('degradation_log_loss_et_brier', out['alertes'])
        self.assertIn('surconfiance', out['alertes'])

    def test_petit_echantillon_ne_declenche_pas(self):
        rows = [{'p': .99, 'y': 0, 'date': __import__('datetime').date(2026, 1, 1)} for _ in range(10)]
        self.assertEqual(SD.comparer(rows, rows)['statut'], 'accumulation')

    def test_sans_periode_precedente_le_rapport_reste_en_accumulation(self):
        matchs = []
        for i in range(40):
            matchs.append({'uid': str(i), 'debut': f'2026-10-{1+i%7:02d}T10:00', 'circuit': 'ATP',
                           'surface': 'Hard', 'meilleur_des': 3, 'reel': {'gagnant': 'home'},
                           'premier': {'combinaison': {'p_home': .6}}})
        out = SD.evaluer({'matchs': matchs})
        self.assertEqual(out['statut'], 'accumulation')

    def test_metadonnees_peu_documentees_preservees(self):
        m = {'uid': 'u', 'debut': '2026-10-20T10:00', 'circuit': 'CH', 'surface': 'Hard', 'meilleur_des': 3,
             'reel': {'gagnant': 'home'}, 'premier': {'combinaison': {'p_home': .6}},
             'profil_contexte': {'n_balles_effectives': [80, 900]}}
        rows, rejetes = SD.preparer({'matchs': [m]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['documentation'], 'peu_documente')
        self.assertEqual(rows[0]['format'], 'BO3')
        self.assertFalse(rejetes)


class ProfilsPeuDocumentes(unittest.TestCase):
    def _rapports(self, sparse=.59, n_sparse=100):
        return {'champion': rapport(), 'recent': rapport(.62, .62),
                'prudent': rapport(.5, .59, sparse, .64, n_sparse),
                'recent_prudent': rapport(.61, .61)}

    def test_gain_global_et_sous_groupes_valides(self):
        nom, verdict = PR._verdict(self._rapports())
        self.assertEqual(nom, 'prudent')
        self.assertTrue(verdict['adopte'])
        self.assertIn('delta_brier', verdict['controles_sous_groupes']['peu_documente'])

    def test_echantillon_sparse_insuffisant_bloque(self):
        _, verdict = PR._verdict(self._rapports(n_sparse=10))
        self.assertFalse(verdict['adopte'])

    def test_degradation_sparse_bloque(self):
        _, verdict = PR._verdict(self._rapports(sparse=.65))
        self.assertFalse(verdict['adopte'])

    def test_brier_present(self):
        self.assertIn('brier', PR._resume([.2, .4]))


if __name__ == '__main__':
    unittest.main()
