"""Site public de l'algo : match du jour, catalogue complet de la préversion Plus et bilan sans tri.

Aucune donnée privée ni de bookmaker ne doit être publiée.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import vitrine as V  # noqa: E402

MAINTENANT = dt.datetime(2026, 10, 24, 5, 0, tzinfo=dt.timezone.utc)      # 07:00 à Paris


def match(uid, debut, circuit, p, cles, home='A B', away='C D', **k):
    m = {'uid': uid, 'debut': debut, 'tournoi': 'T', 'circuit': circuit, 'surface': 'Hard', 'meilleur_des': 3,
         'home': home, 'away': away, 'cles': cles, 'pin_cotes': {'pinnacle': [1.5, 2.6]},
         'combinaison': {'p_home': p, 'sets': {'2-0': .4, '2-1': .2, '1-2': .2, '0-2': .2},
                         'scores_probables': [['6-4 6-4', .03]], 'jeux_moyen': 22.0,
                         'match_simule': {'n': 20000, 'scores': [['6-4 6-4', .03]],
                                          'match_type': {'score': '6-4 6-4'}, 'feuille': []}},
         'marche': {'p_home': .5}, 'direct': {'a': .64, 'b': .6, 'sets_gagnants': 2, 'tb_final': 7}}
    m.update(k)
    return m


ETAT = {'joueurs': {'a': {'elo': 2000}, 'b': {'elo': 2000}, 'c': {'elo': 1500}, 'd': {'elo': 1500},
                    'e': {'elo': 2300}, 'f': {'elo': 2300}}}


class MatchDuJour(unittest.TestCase):
    def test_atp_wta_first_biggest_elo_never_confidence(self):
        L = [match('ch', '2026-10-24T12:00', 'CH', .99, ['e', 'f']),          # plus gros Elo mais Challenger
             match('petit', '2026-10-24T12:00', 'ATP', .95, ['c', 'd']),      # algo très sûr, petite affiche
             match('gros', '2026-10-24T13:00', 'WTA', .52, ['a', 'b'])]       # algo hésitant, grosse affiche
        self.assertEqual(V.choisir_match_du_jour(L, ETAT, MAINTENANT)['uid'], 'gros')

    def test_started_or_other_day_excluded_and_challenger_fallback(self):
        L = [match('commence', '2026-10-24T04:00', 'ATP', .6, ['a', 'b']),
             match('demain', '2026-10-25T12:00', 'ATP', .6, ['a', 'b']),
             match('ch', '2026-10-24T12:00', 'CH', .6, ['c', 'd'])]
        self.assertEqual(V.choisir_match_du_jour(L, ETAT, MAINTENANT)['uid'], 'ch')

    def test_choice_kept_all_day(self):
        L = [match('x', '2026-10-24T12:00', 'ATP', .6, ['c', 'd']), match('y', '2026-10-24T14:00', 'ATP', .6, ['a', 'b'])]
        prec = {'jour': '2026-10-24', 'uid': 'x'}
        self.assertEqual(V.choisir_match_du_jour(L, ETAT, MAINTENANT, prec)['uid'], 'x')
        prec = {'jour': '2026-10-23', 'uid': 'x'}
        self.assertEqual(V.choisir_match_du_jour(L, ETAT, MAINTENANT, prec)['uid'], 'y')


class Publication(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.tmp.name
        os.makedirs(os.path.join(r, 'Tennis_Edge_Lab', 'live'))
        os.makedirs(os.path.join(r, 'simulateur'))
        L = [match('gros', '2026-10-24T13:00', 'WTA', .7, ['a', 'b']), match('autre', '2026-10-24T14:00', 'ATP', .4, ['c', 'd']),
             match('prov', '2026-10-24T15:00', 'ATP', .5, ['a', 'b'], home='WQF1'),
             match('itf', '2026-10-24T15:00', 'ITF', .5, ['a', 'b'])]
        with open(os.path.join(r, 'Tennis_Edge_Lab', 'live', 'pronostics.json'), 'w', encoding='utf-8') as f:
            json.dump({'genere_le': 'x', 'simulations': 20000, 'matchs': L}, f)
        with open(os.path.join(r, 'simulateur', 'elo_etat.json'), 'w', encoding='utf-8') as f:
            json.dump(ETAT, f)

        def res(uid, c, p, gagnant, interrompu=None, home='A B'):
            v = {'p_home': p, 'vainqueur_juste': (p > .5) == (gagnant == 'home')}
            return {'uid': uid, 'debut': '2026-10-22T12:00', 'home': home, 'away': 'C D', 'tournoi': 'T', 'circuit': c,
                    'reel': {'gagnant': gagnant, 'score': '6-4 6-4', 'interrompu': interrompu},
                    'premier': {'stats': {'p_home': .9, 'vainqueur_juste': True}},
                    'dernier': {'combinaison': v}}
        with open(os.path.join(r, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w', encoding='utf-8') as f:
            json.dump({'matchs': [res('1', 'ATP', .7, 'home'), res('2', 'CH', .7, 'away'), res('3', 'WTA', .3, 'away'),
                                  res('4', 'ATP', .7, 'away', interrompu='abandon'), res('5', 'ITF', .7, 'away'),
                                  res('6', 'ATP', .7, 'away', home='WSF1')]}, f)
        self.doc = V.construire(r, MAINTENANT)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_detail_for_every_match(self):
        par = {m['uid']: m for m in self.doc['matchs']}
        self.assertEqual(set(par), {'gros', 'autre'})                   # ni joueur provisoire, ni ITF
        for uid in ('gros', 'autre'):
            self.assertIn('simulation', par[uid])
            self.assertIn('sets', par[uid])
            self.assertTrue(par[uid]['simulation_disponible'])
            self.assertEqual(par[uid]['simulation']['n'], 20000)
            self.assertEqual(par[uid]['simulation']['scenario']['score'], '6-4 6-4')
            self.assertNotIn('plus', par[uid])
        self.assertEqual(par['autre']['cotes_justes'], [2.5, 1.67])

    def test_nothing_private_or_from_bookmakers(self):
        txt = json.dumps(self.doc)
        for interdit in ('pin_cotes', 'pinnacle', 'marche', 'leovegas', '4casters', 'H18', 'H19', 'H20'):
            self.assertNotIn(interdit, txt)

    def test_record_last_prediction_no_filtering(self):
        g = self.doc['bilan']['global']
        self.assertEqual(g['n'], 3)                                     # abandon, ITF, joueur provisoire exclus
        self.assertEqual(g['vainqueurs'], 2)                            # jugé sur le DERNIER pronostic, pas le premier
        self.assertEqual(set(self.doc['bilan']['par_circuit']), {'ATP', 'CH', 'WTA'})

    def test_calibration_counts_both_sides(self):
        pts = [(.7, 1)] * 30
        c = V.calibration(pts)
        self.assertEqual([(b['de'], b['n']) for b in c], [(0.3, 30), (0.7, 30)])


if __name__ == '__main__':
    unittest.main()
