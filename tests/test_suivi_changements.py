# -*- coding: utf-8 -*-
"""Suivi des changements du 29/10/2026 : modèle fantôme, journal, abandons récents, avant/après, taille du dépôt."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import apres_match as AM  # noqa: E402
import vitrine as V  # noqa: E402
import roi_algo as RA  # noqa: E402
import taille_depot as TD  # noqa: E402


class TestFantome(unittest.TestCase):
    def test_comparaison_apres_match(self):
        f = {'debut': '2026-10-29T10:00:00+00:00', 'circuit': 'CH', 'home': 'A Un', 'away': 'B Deux',
             'dernier': {'p_home': 0.7, 'controle': {'p_elo': 0.72, 'p_elo_reference': 0.60, 'reference': 'x'}}}
        b = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-3 6-3', 'sets': '2-0'})
        self.assertLess(b['ecarts']['fantome']['ll_elo'], b['ecarts']['fantome']['ll_reference'])
        A = AM.analyser({'u': b})['groupes']['TOUS']['fantome']
        self.assertGreater(A['gain'], 0)
        self.assertFalse(A['conclusion_possible'])

    def test_journal_sans_mot_interdit(self):
        racine = os.path.join(ICI, '..')
        J = V.journal_changements(racine, {'groupes': {'TOUS': {'fantome': {'matchs': 3}}}})
        self.assertTrue(J['changements'])
        self.assertEqual(J['fantome']['TOUS']['matchs'], 3)
        txt = json.dumps(J, ensure_ascii=False).lower()
        self.assertNotIn('marché', txt)
        self.assertNotIn('marche ', txt)


class TestAbandons(unittest.TestCase):
    def test_abandon_dans_les_90_jours(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'feuilles'))
            r = {'id': 1, 'jour': '2026-10-01', 'vainqueur': 1, 'statut': {'texte': 'Retired'},
                 'home': {'nom': 'X Gagne'}, 'away': {'nom': 'Y Abandonne'}}
            with gzip.open(os.path.join(d, 'feuilles', '2026-10-01.jsonl.gz'), 'wt') as f:
                f.write(json.dumps(r) + '\n')
            L = [{'debut_utc': '2026-10-29T10:00:00Z', 'home': 'Y Abandonne', 'away': 'Z Autre'},
                 {'debut_utc': '2027-03-01T10:00:00Z', 'home': 'Y Abandonne', 'away': 'Z Autre'}]
            V.ajouter_abandons(L, d)
            self.assertEqual(L[0]['abandon_recent'], [28, None])
            self.assertNotIn('abandon_recent', L[1])                 # plus de 90 jours


class TestAvantApres(unittest.TestCase):
    def test_decoupage_par_date(self):
        L = [('2026-10-27_a_b', 'CH', 0.6, 'home'), ('2026-10-30_c_d', 'CH', 0.7, 'away')]
        C = {'2026-10-27_a_b': (1.8, 2.1), '2026-10-30_c_d': (1.5, 2.6)}
        X = RA.avant_apres(L, C, os.path.join(ICI, '..'))
        x = next(v for v in X if v['date'] == '2026-10-28')
        self.assertEqual((x['avant']['n'], x['apres']['n']), (1, 1))
        self.assertIn('ecart', x['apres'])


class TestTaille(unittest.TestCase):
    def test_par_dossier(self):
        A = {'tree': [{'type': 'blob', 'path': 'feuilles/a.gz', 'size': 10}, {'type': 'blob', 'path': 'feuilles/b.gz', 'size': 5},
                      {'type': 'blob', 'path': 'README.md', 'size': 1}, {'type': 'tree', 'path': 'feuilles'}]}
        self.assertEqual(TD.par_dossier(A), {'feuilles': 15, '(racine)': 1})


if __name__ == '__main__':
    unittest.main()
