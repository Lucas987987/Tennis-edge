# -*- coding: utf-8 -*-
"""Résultats ITF hommes pour l'Elo : collecte (sans réseau) et étude à règle fixée (28/10/2026)."""
import datetime as dt
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import resultats_itf as RI  # noqa: E402
import etude_itf_elo as EI  # noqa: E402

J = dt.date(2025, 3, 3)
TS = int(dt.datetime(2025, 3, 3, 12, tzinfo=dt.timezone.utc).timestamp())


def ev(i, statut='finished', ts=TS, h='Joueur Un', a='Joueur Deux'):
    return {'id': i, 'startTimestamp': ts, 'status': {'type': statut, 'description': 'Ended'}, 'winnerCode': 1,
            'homeTeam': {'id': 1, 'name': h}, 'awayTeam': {'id': 2, 'name': a},
            'homeScore': {'period1': 6, 'period2': 6}, 'awayScore': {'period1': 3, 'period2': 4},
            'tournament': {'name': 'M25 Test', 'uniqueTournament': {'id': 9, 'groundType': 'Clay'}}}


class Faux:
    def __init__(self):
        self.n, self.codes, self.restant = 0, {}, 9999

    def get(self, chemin):
        self.n += 1
        if chemin.endswith('/categories'):
            return 200, {'categories': [{'category': {'id': 785, 'name': 'ITF Men'}},
                                        {'category': {'id': 3, 'name': 'ATP'}}]}
        if '/category/785/' in chemin:
            return 200, {'events': [ev(1), ev(2, statut='inprogress'), ev(3, ts=TS - 86400),
                                    ev(4, h='A / B', a='C / D')]}
        return 404, None


class TestCollecte(unittest.TestCase):
    def test_jour(self):
        c = Faux()
        r = RI.collecter_jour(c, J.isoformat())
        self.assertEqual(list(r), [1])                     # en cours, veille et double écartés
        self.assertEqual(c.n, 2)                           # index + ITF hommes seulement
        f = r[1]
        self.assertEqual(f['home']['nom'], 'Joueur Un')
        self.assertNotIn('stats', f)
        m = EI.match_itf(f)
        self.assertEqual((m['nom_g'], m['circuit'], m['surface']), ('Joueur Un', 'ITFH', 'Clay'))
        self.assertEqual(m['sets'], [(6, 3), (6, 4)])


class TestReprise(unittest.TestCase):
    """28/10/2026 : un passage coupé ne perd plus que le mois en cours ; arrêt propre au bout du temps."""

    def test_mois_ecrits_au_fil_et_arret_au_temps(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            t = [0.0]

            def horloge():
                t[0] += 10
                return t[0]
            jours = ['2024-06-29', '2024-06-30', '2024-07-01', '2024-07-02', '2024-07-03']
            col = lambda c, j: {int(j.replace('-', '')): {'id': int(j.replace('-', '')), 'jour': j}}
            etat = {'jours': {}}
            faits, arret = RI.passer(Faux(), jours, etat, dt.date(2026, 10, 28), collecter=col, limite_s=35,
                                     horloge=horloge, journal=lambda *a: None, dossier=d)
            self.assertEqual(faits, 3)
            self.assertIn('temps', arret)
            self.assertEqual(len(RI.lire_mois('2024-06', d)), 2)
            self.assertEqual(len(RI.lire_mois('2024-07', d)), 1)
            self.assertTrue(os.path.exists(os.path.join(d, 'etat.json')))
            self.assertEqual(sorted(etat['jours']), jours[:3])


def mt(d, g, p, circuit='CH', src='archive', i=None):
    return {'date': d, 'fin': d, 'circuit': circuit, 'surface': 'Hard', 'nom_g': g, 'nom_p': p, 'sets': [(6, 3), (6, 3)],
            'complet': True, 'niveau': '', 'tour': 0, 'num': 0, 'source': src, 'id': i}


def itf(i, d, g, p):
    return {'id': i, 'jour': d.isoformat(), 'vainqueur': 1, 'statut': {'texte': 'Ended'}, 'surface': 'Hardcourt outdoor',
            'home': {'nom': g}, 'away': {'nom': p}, 'score_home': {'sets': [6, 6]}, 'score_away': {'sets': [2, 2]}}


class TestEtude(unittest.TestCase):
    def test_itf_aide_le_joueur_fort_et_doublon_ecarte(self):
        d0 = dt.date(2024, 12, 1)
        M = [mt(d0, 'Ancien Moyen', 'Autre Moyen')] * 3
        # « Nouveau Fort » gagne 60 matchs ITF, puis bat en Challenger des joueurs qui ne le connaissaient pas
        I = [itf(1000 + k, d0 + dt.timedelta(days=k % 20), 'Nouveau Fort', f'Victime N{k}') for k in range(60)]
        F = [mt(dt.date(2025, 2, k + 1), 'Nouveau Fort', f'Adversaire Ch{k}', src='tennisapi', i=k) for k in range(20)]
        F.append(mt(dt.date(2025, 2, 25), 'Nouveau Fort', 'Victime N0', circuit='ITFH', src='tennisapi', i=1000))
        r = EI.etude(M, F, I)
        self.assertEqual(r['matchs_itf'], 60)
        self.assertEqual(r['challenger']['n'], 20)
        self.assertGreater(r['challenger']['gain'], EI.MARGE)
        self.assertTrue(r['verdict_semaine'])
        T1 = EI.flux(M, F, [EI.match_itf(x) for x in I])
        self.assertEqual(sum(1 for m in T1 if m.get('id') == 1000), 1)    # déjà dans les feuilles : une seule fois

    def test_sans_itf_pas_de_verdict(self):
        M = [mt(dt.date(2024, 12, 1), 'A Un', 'B Deux')]
        F = [mt(dt.date(2025, 2, 1), 'A Un', 'B Deux', src='tennisapi', i=1)]
        r = EI.etude(M, F, [])
        self.assertEqual(r['challenger']['gain'], 0.0)
        self.assertFalse(r['verdict_semaine'])


if __name__ == '__main__':
    unittest.main()
