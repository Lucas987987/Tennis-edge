"""Contrôles quotidiens de l'algo (06/11/2026, paquet 200)."""
import datetime as dt
import gzip
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import sante_algo as SA  # noqa: E402

MAINT = dt.datetime(2026, 11, 6, 8, 0, tzinfo=dt.timezone.utc)


def feuille(jour, h, a, cat='ATP', statut='Ended', tid=1):
    return {'jour': jour, 'categorie': cat, 'tournoi_id': tid, 'statut': {'texte': statut},
            'home': {'nom': h}, 'away': {'nom': a}}


class Sante(unittest.TestCase):
    def ecrire(self, d, donnees, feuilles, tournois, facteurs):
        os.makedirs(os.path.join(d, 'algo'))
        os.makedirs(os.path.join(d, 'feuilles'))
        os.makedirs(os.path.join(d, 'simulateur'))
        json.dump(donnees, open(os.path.join(d, 'algo', 'donnees.json'), 'w'))
        json.dump(tournois, open(os.path.join(d, 'feuilles', 'tournois.json'), 'w'))
        json.dump(facteurs, open(os.path.join(d, 'simulateur', 'facteurs.json'), 'w'))
        for j, L in feuilles.items():
            with gzip.open(os.path.join(d, 'feuilles', f'{j}.jsonl.gz'), 'wt') as f:
                f.write('\n'.join(json.dumps(x) for x in L) + '\n')

    def test_tout_va_bien(self):
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, {'genere_le': '2026-11-06T07:30:00+00:00',
                            'matchs': [{'circuit': 'ATP', 'home': 'A', 'away': 'B', 'simulation': {}}],
                            'apres_match': {'x': {'debut': '2026-11-05T10:00', 'ecarts': {'vainqueur_juste': True}}}},
                        {'2026-11-05': [feuille('2026-11-05', 'A', 'B')]}, {}, {'genere_le': '2026-11-04T08:00:00+00:00'})
            a, i = SA.controles(d, MAINT)
            self.assertEqual(a, [])
            self.assertTrue(any('Hier : 1 matchs' in x for x in i))

    def test_problemes(self):
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, {'genere_le': '2026-11-05T20:00:00+00:00',
                            'matchs': [{'circuit': 'ATP', 'home': 'Matteo Berrettini', 'away': 'Carlos Alcaraz'}] * 5,
                            'apres_match': {}},
                        {'2026-11-05': [feuille('2026-11-05', 'X', 'Y', cat='Exhibition', tid=9)],
                         '2026-11-04': [feuille('2026-11-05', 'Matteo Berrettini', 'Carlos Alcaraz', statut='Walkover', tid=9)]},
                        {'9': {'nom': 'Jinan, China, Qualifying', 'ville': 'Jinan', 'lat': None}},
                        {'genere_le': '2026-10-20T08:00:00+00:00'})
            a, _ = SA.controles(d, MAINT)
            txt = '\n'.join(a)
            for attendu in ('Catégorie TennisApi inconnue : Exhibition', 'vieilles de 12 h', 'sans simulation', "Aucun match d'hier", 'sans lieu', 'Forfait encore en ligne',
                            'Facteurs pas rejugés'):
                self.assertIn(attendu, txt)

    def test_workflows(self):
        runs = {'workflow_runs': [
            {'name': 'Vidéo', 'conclusion': 'cancelled', 'html_url': 'u1'},
            {'name': 'Vidéo', 'conclusion': 'cancelled', 'html_url': 'u0'},
            {'name': 'Ticks', 'conclusion': 'failure', 'html_url': 'u2'},
            {'name': 'Capture', 'conclusion': 'success', 'html_url': 'u3'}]}

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        with mock.patch('urllib.request.urlopen', lambda req, timeout=0: R(json.dumps(runs).encode())):
            n, E = SA.echecs_workflows('o', 'r', 'jeton', MAINT)
        self.assertEqual(n, 4)
        self.assertEqual(E[0], ('Vidéo', 'cancelled', 2, 'u1'))
        self.assertIn(('Ticks', 'failure', 1, 'u2'), E)


if __name__ == '__main__':
    unittest.main()
