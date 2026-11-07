"""Cartes des joueurs (07/11/2026, paquet 216) : note Elo à échelle fixe, attributs en centiles, descriptif seulement."""
import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import cartes_joueurs as CJ  # noqa: E402
import elo as E  # noqa: E402


def _profil(i):
    return {'a': 0.05 + i / 1000, 'f': 0.55 + i / 500, 'd': 0.20 - i / 1000, 'serv': 0.6, 'ret': 0.4}


class Cartes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        noms = [f'Joueur {a}{b}' for a in 'BCDEFGHIJK' for b in 'aeio'][:40]
        J = {E.cle(n): {'nom': n, 'circuit': 'CH' if i % 2 else 'ATP', 'balles': 1000,
                        'surfaces': {'all': {'balles': 1000, 'joueur': _profil(i)}}} for i, n in enumerate(noms)}
        os.makedirs(os.path.join(self.d, 'Tennis_Edge_Lab', 'live'))
        with gzip.open(os.path.join(self.d, 'Tennis_Edge_Lab', 'live', 'joueurs_service.json.gz'), 'wt') as f:
            json.dump({'joueurs': J}, f)
        with open(os.path.join(self.d, 'Tennis_Edge_Lab', 'live', 'elo_service_retour.json'), 'w') as f:
            json.dump({'joueurs': {E.cle(n): [i / 100, -i / 100, 50] for i, n in enumerate(noms)}}, f)
        os.makedirs(os.path.join(self.d, 'feuilles', 'classements'))
        with open(os.path.join(self.d, 'feuilles', 'joueurs.json'), 'w') as f:
            json.dump({'1': {'nom': noms[39], 'naissance': '2000-11-08', 'taille_cm': 190, 'main': 'gauche',
                             'pays': 'FRA', 'maj': '2026-11-01'}}, f)
        with open(os.path.join(self.d, 'feuilles', 'classements', '2026-11-07.json'), 'w') as f:
            json.dump({'ATP': {E.cle(noms[39]): [12, 2000, noms[39]]}}, f)
        self.etat = {'options': {'poids_surface': 0.3},
                     'joueurs': {E.cle(n): {'nom': n, 'elo': 1500 + 20 * i, 'surfaces': {'Hard': 1500 + 20 * i}}
                                 for i, n in enumerate(noms)}}
        self.noms = noms

    def test_note_echelle_fixe(self):
        self.assertEqual(CJ.note_elo(2400), 99)
        self.assertEqual(CJ.note_elo(2400 - 22 * 20), 79)
        self.assertEqual(CJ.note_elo(500), 40)
        self.assertEqual(CJ.note_elo(3000), 99)

    def test_carte_complete_et_descriptive(self):
        av = {'home': {'reussite': {'matchs': 40, 'victoires': 30, 'attendu': 26.0, 'ecart': 4.0}},
              'away': {'reussite': {'matchs': 40, 'victoires': 20, 'attendu': 20.0, 'ecart': 0.0}}}
        L = [{'home': self.noms[39], 'away': self.noms[0], 'circuit': 'ATP', 'surface': 'Hard',
              'debut': '2026-11-07T10:00', 'avant_match': av}]
        CJ.ajouter_cartes(L, self.d, self.etat)
        C = L[0]['cartes']
        self.assertTrue(C['descriptif_seulement'])
        self.assertEqual(C['groupe'], 'hommes')
        h, a = C['joueurs']
        self.assertGreater(h['note'], a['note'])
        self.assertEqual(set(h['attributs']), set(CJ.ATTRIBUTS))
        self.assertTrue(all(1 <= v <= 99 for v in h['attributs'].values()))
        self.assertGreater(h['attributs']['ser'], a['attributs']['ser'])
        self.assertGreater(a['attributs']['ret'], h['attributs']['ret'])
        self.assertGreater(h['attributs']['df'], a['attributs']['df'])    # moins de doubles fautes = mieux
        self.assertEqual(h['attributs']['for'], 70)                       # 50 + 200 × 4 / 40
        self.assertEqual(a['attributs']['for'], 50)
        self.assertEqual((h['rang'], h['age'], h['taille_cm'], h['main'], h['pays']), (12, 25, 190, 'gauche', 'FRA'))

    def test_joueur_inconnu_pas_de_carte(self):
        L = [{'home': self.noms[1], 'away': 'Personne Inconnue', 'circuit': 'CH', 'surface': 'Hard', 'debut': '2026-11-07'}]
        CJ.ajouter_cartes(L, self.d, self.etat)
        self.assertNotIn('cartes', L[0])

    def test_sans_notes_service_retour_pas_d_attributs(self):
        os.remove(os.path.join(self.d, 'Tennis_Edge_Lab', 'live', 'elo_service_retour.json'))
        L = [{'home': self.noms[3], 'away': self.noms[5], 'circuit': 'CH', 'surface': 'Hard', 'debut': '2026-11-07'}]
        CJ.ajouter_cartes(L, self.d, self.etat)
        self.assertNotIn('attributs', L[0]['cartes']['joueurs'][0])
        self.assertIn('note', L[0]['cartes']['joueurs'][0])

    def test_aucune_cote(self):
        src = (RACINE / 'simulateur' / 'cartes_joueurs.py').read_text(encoding='utf-8').lower()
        for mot in ('pinnacle', 'oddspapi', 'cotes_justes', 'closing'):
            self.assertNotIn(mot, src)


if __name__ == '__main__':
    unittest.main()
