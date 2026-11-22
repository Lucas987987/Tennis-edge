"""Paquet 337 — point par point ITF des joueurs de Challenger : filtre des joueurs, tournois sans déroulé abandonnés,
jours complets jamais redemandés, rangé à part, aucun script de l'algo ne le lit."""
import glob
import gzip
import json
import os
import sys
import tempfile
import unittest

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import itf_points as IP  # noqa: E402

TS = 1747224000          # 2025-05-14 12:00 UTC
JOUR = '2025-05-14'


def ev(i, h, a, tid=1):
    return {'id': i, 'startTimestamp': TS, 'status': {'type': 'finished'}, 'homeTeam': {'id': h, 'name': f'J{h}'},
            'awayTeam': {'id': a, 'name': f'J{a}'}, 'tournament': {'name': f'M25 T{tid}', 'uniqueTournament': {'id': tid}}}


PBP = {'pointByPoint': [{'set': 1, 'games': [
    {'game': g, 'score': {'serving': 1 if g % 2 else 2, 'scoring': 1 if g % 2 else 2},
     'points': [{'homePoint': '15', 'awayPoint': '0'}, {'homePoint': '30', 'awayPoint': '0'},
                {'homePoint': '40', 'awayPoint': '0'}, {'homePoint': 'A', 'awayPoint': '0'}] if g % 2 else
               [{'homePoint': '0', 'awayPoint': '15'}, {'homePoint': '0', 'awayPoint': '30'},
                {'homePoint': '0', 'awayPoint': '40'}, {'homePoint': '0', 'awayPoint': 'A'}]}
    for g in range(1, 9)]}]}


class Faux:
    def __init__(self, events, avec_pbp):
        self.events, self.avec, self.appels, self.n, self.restant = events, avec_pbp, [], 0, 9999

    def get(self, chemin):
        self.appels.append(chemin)
        self.n += 1
        if chemin.endswith('/categories'):
            return 200, {'categories': [{'category': {'id': 7, 'name': 'ITF Men'}, 'totalEvents': 5}]}
        if '/category/7/events/' in chemin:
            return 200, {'events': self.events}
        if chemin.endswith('/point-by-point'):
            i = int(chemin.split('/')[-2])
            return (200, PBP) if i in self.avec else (204, None)
        return 404, None


class Collecte(unittest.TestCase):
    def test_service_sans_jeux_decisifs(self):
        s = IP.service([[1, 1, 1, 'HHAH'], [1, 2, 2, 'AAAA'], [1, 13, 1, 'HAHAHAHA']])
        self.assertEqual(s, {'home': [3, 4], 'away': [4, 4]})

    def test_joueurs_challenger(self):
        with tempfile.TemporaryDirectory() as d:
            with gzip.open(os.path.join(d, '2026-11-01.jsonl.gz'), 'wt') as f:
                f.write(json.dumps({'categorie': 'Challenger', 'home': {'id': 1}, 'away': {'id': 2}}) + '\n')
                f.write(json.dumps({'categorie': 'ATP', 'home': {'id': 3}, 'away': {'id': 4}}) + '\n')
            self.assertEqual(IP.joueurs_challenger(d), {1, 2})

    def test_seuls_les_matchs_des_joueurs_suivis_et_tournoi_vide_abandonne(self):
        events = [ev(10, 1, 99), ev(11, 98, 97)] + [ev(20 + i, 2, 90 + i, tid=2) for i in range(6)]
        c = Faux(events, avec_pbp={10})
        with tempfile.TemporaryDirectory() as d:
            n, avec, complet = IP.collecter_jour(c, JOUR, {1, 2}, dossier=d, journal=lambda *_: None)
            pbp = [a for a in c.appels if a.endswith('point-by-point')]
            self.assertNotIn('/api/tennis/event/11/point-by-point', pbp)      # aucun joueur suivi
            self.assertEqual(len(pbp), 1 + IP.VIDES_TOURNOI)                  # tournoi 2 : 4 essais puis abandon
            self.assertEqual((n, avec), (7, 1))
            r = json.loads(gzip.open(os.path.join(d, JOUR + '.jsonl.gz'), 'rt').readline())
            self.assertEqual(r['id'], 10)
            self.assertEqual(r['service'], {'home': [20, 20], 'away': [20, 20]})
            # deuxième passage : les 4 essais vides sont redemandés une fois, le reste du tournoi est abandonné
            c2 = Faux(events, avec_pbp=set())
            n, avec, complet = IP.collecter_jour(c2, JOUR, {1, 2}, dossier=d, journal=lambda *_: None)
            self.assertEqual(len([a for a in c2.appels if a.endswith('point-by-point')]), IP.VIDES_TOURNOI)
            self.assertTrue(complet)

    def test_aucun_script_de_l_algo_ne_lit_ce_dossier(self):
        for p in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')):
            self.assertNotIn('itf_points', open(p, encoding='utf-8').read(), p)

    def test_workflow(self):
        w = open(os.path.join(RACINE, '.github/workflows/itf_points.yml'), encoding='utf-8').read()
        self.assertIn("FEUILLES_RESERVE: '7000'", w)
        self.assertIn('git add -A -- historique/itf_points', w)
        self.assertNotIn('--force', w)


if __name__ == '__main__':
    unittest.main()
