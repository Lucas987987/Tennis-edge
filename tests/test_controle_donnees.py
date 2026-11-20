"""Paquet 272 : contrôle quotidien de la qualité des données ; adversaires remplacés et doublons retirés du site."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import controle_donnees as CD  # noqa: E402
import vitrine as V  # noqa: E402

NOW = dt.datetime(2026, 11, 18, 10, 0, tzinfo=dt.timezone.utc)


def _ts(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())


def _fiche(h, a, debut, statut='Ended', vainqueur=1):
    return {'home': {'nom': h}, 'away': {'nom': a}, 'jour': debut[:10], 'debut': _ts(debut),
            'statut': {'texte': statut, 'type': 'finished'}, 'vainqueur': vainqueur,
            'score_home': {'sets': [6, 6]}, 'score_away': {'sets': [3, 4]}}


def _racine(d, journal, resultats, fiches, site=None):
    os.makedirs(os.path.join(d, 'simulateur')); os.makedirs(os.path.join(d, 'feuilles'))
    os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live')); os.makedirs(os.path.join(d, 'algo'))
    with open(os.path.join(d, 'simulateur', 'pronostics_log.jsonl'), 'w') as f:
        f.write('\n'.join(json.dumps(r) for r in journal))
    json.dump({'matchs': resultats}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))
    par_jour = {}
    for x in fiches:
        par_jour.setdefault(x['jour'], []).append(x)
    for j, L in par_jour.items():
        with gzip.open(os.path.join(d, 'feuilles', f'{j}.jsonl.gz'), 'wt') as f:
            f.write('\n'.join(json.dumps(x) for x in L))
    json.dump({'matchs': site or []}, open(os.path.join(d, 'algo', 'donnees.json'), 'w'))


def _j(uid, h, a, debut, c='CH'):
    return {'uid': uid, 'home': h, 'away': a, 'debut': debut, 'circuit': c}


class Causes(unittest.TestCase):
    def test_chaque_cause(self):
        J = [_j('ok', 'Ann Alpha', 'Bea Beta', '2026-11-17T10:00'),
             _j('fic', 'R16P3', 'Bea Beta', '2026-11-17T11:00'),
             _j('rep1', 'Cid Gamma', 'Dan Delta', '2026-11-17T20:40'), _j('rep2', 'Cid Gamma', 'Dan Delta', '2026-11-18T00:40'),
             _j('ab', 'Eli Eps', 'Fay Zeta', '2026-11-17T12:00'),
             _j('rem', 'Gus Eta', 'Hal Theta', '2026-11-17T16:30'),
             _j('rien', 'Ivo Iota', 'Jan Kappa', '2026-11-17T09:00'),
             _j('fin', 'Kim Lam', 'Leo Mu', '2026-11-17T08:00')]
        F = [_fiche('Eli Eps', 'Fay Zeta', '2026-11-17T12:05', 'Retired'),
             _fiche('Nil Nu', 'Hal Theta', '2026-11-17T16:30'),                 # Hal joue un autre adversaire
             _fiche('Kim Lam', 'Leo Mu', '2026-11-17T08:00')]
        with tempfile.TemporaryDirectory() as d:
            _racine(d, J, [{'uid': 'ok', 'home': 'Ann Alpha', 'away': 'Bea Beta', 'debut': '2026-11-17T10:00',
                            'reel': {'gagnant': 'home', 'score': '6-3 6-4'}}], F)
            L, _ = CD.classer(d, NOW)
        c = {x['uid']: x['cause'] for x in L}
        self.assertEqual(c['ok'], 'résolu')
        self.assertEqual(c['fic'], 'adversaire fictif')
        self.assertEqual(c['rep1'], 'doublon reprogrammé')
        self.assertEqual(c['ab'], 'abandon / forfait')
        self.assertEqual(c['rem'], 'adversaire remplacé')
        self.assertEqual(c['rien'], 'aucune feuille')
        self.assertEqual(c['fin'], 'feuille terminée non résolue')
        self.assertNotIn('rep2', c)                                            # commencé depuis moins de 12 h

    def test_deux_vrais_matchs_de_suite_ne_sont_pas_un_doublon(self):
        R = [{'uid': 'q', 'home': 'Juan Manuel Cerundolo', 'away': 'Daniel Altmaier', 'debut': '2026-10-25T12:00',
              'reel': {'gagnant': 'home', 'score': '7-6 6-3'}},
             {'uid': 't', 'home': 'Daniel Altmaier', 'away': 'Juan Manuel Cerundolo', 'debut': '2026-10-26T14:05',
              'reel': {'gagnant': 'away', 'score': '6-7 7-6 6-4'}}]
        self.assertEqual(CD.doubles_resolus(R), [])
        R[1]['reel']['score'] = '7-6 6-3'
        self.assertEqual(len(CD.doubles_resolus(R)), 1)

    def test_rapport_public_sans_nom(self):
        J = [_j('a', 'Ann Alpha', 'Bea Beta', '2026-11-17T10:00'), _j('b', 'Ivo Iota', 'Jan Kappa', '2026-11-17T09:00')]
        with tempfile.TemporaryDirectory() as d:
            _racine(d, J, [], [])
            r, L, dr, ds = CD.rapport(d, NOW)
        t = json.dumps(r, ensure_ascii=False)
        for interdit in ('Alpha', 'Iota', 'cote', 'Pinnacle'):
            self.assertNotIn(interdit, t)
        self.assertEqual(r['veille']['defauts_pct'], 100.0)
        self.assertTrue(r['alerte'])


class Site(unittest.TestCase):
    def test_doublon_reprogramme_garde_le_plus_recent(self):
        M = [{'uid': 'x17', 'home': 'Hynek Barton', 'away': 'Alexis Galarneau', 'debut': '2026-11-17T23:40', 'commence_garde': True,
              'circuit': 'CH', 'tournoi': 'ATP Challenger Drummondville'},
             {'uid': 'x18', 'home': 'Hynek Barton', 'away': 'Alexis Galarneau', 'debut': '2026-11-18T00:40',
              'circuit': 'CH', 'tournoi': 'ATP Challenger Drummondville'},
             {'uid': 'y', 'home': 'Ann Alpha', 'away': 'Bea Beta', 'debut': '2026-11-18T10:00'}]
        self.assertEqual([m['uid'] for m in V.dedoublonner_site(M)], ['x18', 'y'])

    def test_adversaire_remplace_retire(self):
        M = [{'uid': 'r', 'home': 'Camilo Ugo Carabelli', 'away': 'Felipe Meligeni Alves', 'debut': '2026-11-17T16:30'},
             {'uid': 's', 'home': 'Ann Alpha', 'away': 'Bea Beta', 'debut': '2026-11-17T16:30'}]
        F = [_fiche('Pedro Boscardin Dias', 'Felipe Meligeni Alves', '2026-11-17T16:30')]
        with tempfile.TemporaryDirectory() as d:
            _racine(d, [], [], F)
            out = V.retirer_annules(M, d, NOW)
        self.assertEqual([m['uid'] for m in out], ['s'])


if __name__ == '__main__':
    unittest.main()
