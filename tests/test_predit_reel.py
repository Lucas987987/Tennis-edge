"""Prédit / réel (22/10/2026) : chaque passage est enregistré, et chaque match joué est confronté à
sa prédiction (vainqueur, sets, score en jeux, total de jeux), depuis set_results et la feuille."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import pronostics_du_jour as P  # noqa: E402


def version(p, sets, scores, jeux):
    return {'p_home': p, 'sets': sets, 'scores_probables': scores, 'jeux_moyen': jeux}


class PreditReel(unittest.TestCase):
    def test_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            for sous in ('simulateur', 'feuilles', 'Tennis_Edge_Lab/live'):
                os.makedirs(os.path.join(d, sous))
            S = {'2-0': 0.45, '2-1': 0.25, '1-2': 0.15, '0-2': 0.15}
            det = {'combinaison': version(0.68, S, [['6-4 6-4', 0.04], ['6-3 6-4', 0.035], ['6-4 6-3', 0.03]], 22.0),
                   'simulation': version(0.45, {'2-0': 0.2, '2-1': 0.25, '1-2': 0.25, '0-2': 0.3}, [['4-6 4-6', 0.03]], 23.0),
                   'stats': version(0.7, S, [], 21.5), 'marche': version(0.66, S, [], 22.0)}
            r = {'uid': '2026-10-21_arthur_fils_hugo_gaston', 'pronostique_le': '2026-10-21T08:00:00Z', 'debut': '2026-10-21T14:00',
                 'home': 'Arthur Fils', 'away': 'Hugo Gaston', 'tournoi': 'ATP Vienna', 'circuit': 'ATP', 'meilleur_des': 3,
                 'stats': {'p_home': 0.7, 'sets': S}, 'marche': {'p_home': 0.66, 'sets': S}, 'detail': det}
            open(os.path.join(d, P.LOG), 'w').write(json.dumps(r) + '\n')
            json.dump({'2026-10-21_arthur_fils_hugo_gaston': {'match': 'home', 'set1': 'home', 'set2': 'home'}},
                      open(os.path.join(d, 'set_results.json'), 'w'))
            fi = {'id': 1, 'jour': '2026-10-21', 'debut': 1792591200, 'categorie': 'ATP', 'tournoi': 'Vienna, Austria',
                  'home': {'nom': 'Hugo Gaston', 'id': 2}, 'away': {'nom': 'Arthur Fils', 'id': 1}, 'vainqueur': 2,
                  'statut': {'texte': 'Ended'}, 'score_home': {'sets': [4, 4]}, 'score_away': {'sets': [6, 6]}, 'stats': None}
            with gzip.open(os.path.join(d, 'feuilles', '2026-10-21.jsonl.gz'), 'wt') as f:
                f.write(json.dumps(fi) + '\n')
            doc = {'genere_le': '2026-10-21T12:00:00Z', 'facteurs_adoptes': [], 'combinaison': None,
                   'matchs': [dict(r, surface='Hard', combinaison=det['combinaison'], simulation=det['simulation'],
                                   stats=det['stats'], marche=det['marche'], direct=None, pin_cotes=[1.45, 2.8])]}
            self.assertEqual(P.enregistrer_instantanes(d, doc), 1)
            doc2 = dict(doc, genere_le='2026-10-21T18:00:00Z')               # après le début : pas « dernier »
            P.enregistrer_instantanes(d, doc2)
            self.assertEqual(len(P.lire_instantanes(d)['2026-10-21_arthur_fils_hugo_gaston']), 2)
            R = P.resoudre(d, dt.datetime(2026, 10, 22, 12))
            self.assertEqual(len(R), 1)
            x = R[0]
            self.assertEqual(x['reel'], {'gagnant': 'home', 'sets': '2-0', 'score': '6-4 6-4', 'jeux': 20, 'feuille': None, 'interrompu': None})
            c = x['premier']['combinaison']
            self.assertTrue(c['vainqueur_juste'])
            self.assertTrue(c['sets_justes'])
            self.assertTrue(c['score_juste'])
            self.assertEqual(c['rang_du_score_reel'], 1)
            self.assertEqual(c['ecart_jeux'], -2.0)
            self.assertFalse(x['premier']['simulation']['vainqueur_juste'])
            self.assertEqual(x['dernier_passage'], '2026-10-21T12:00:00Z')
            self.assertEqual(x['n_passages'], 1)
            self.assertAlmostEqual(x['premier']['stats']['proba_du_vainqueur'], 0.7)

    def test_pas_encore_joue(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            open(os.path.join(d, P.LOG), 'w').write(json.dumps({'uid': 'u', 'debut': '2030-01-01T10:00', 'home': 'A', 'away': 'B',
                                                                 'tournoi': 'x', 'stats': {'p_home': 0.5, 'sets': {}}}) + '\n')
            self.assertEqual(P.resoudre(d, dt.datetime(2026, 10, 22)), [])


if __name__ == '__main__':
    unittest.main()
