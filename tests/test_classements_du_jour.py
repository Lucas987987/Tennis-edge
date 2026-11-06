"""Classements du jour (06/11/2026, paquet 195) : noms courts, classements, vérification, forfaits retirés."""
import datetime as dt
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import classements_du_jour as CJ  # noqa: E402


def match(uid, h, a, p, aces, sets, tb, circuit='ATP', debut='2026-11-06T13:00'):
    return {'uid': uid, 'home': h, 'away': a, 'p_home': p, 'circuit': circuit, 'debut': debut,
            'feuille_prevue': [{'aces': aces / 2}, {'aces': aces / 2}], 'sets': sets, 'tiebreak': tb}


def apres(h, a, p, gagnant, sets_p, sets_r, aces_p, aces_r, tb, debut='2026-11-05T13:00'):
    return {'home': h, 'away': a, 'circuit': 'ATP', 'debut': debut,
            'prevu': {'p_home': p, 'sets': sets_p, 'feuille': [{'aces': aces_p}, {'aces': 0}]},
            'reel': {'gagnant': gagnant, 'sets': sets_r, 'score': '6-4 6-4', 'feuille': [{'aces': aces_r}, {'aces': 0}]},
            'ecarts': {'lignes': {'tie_break': tb}}}


class Classements(unittest.TestCase):
    def test_noms(self):
        self.assertEqual(CJ.nom('Zizou Bergs'), 'Bergs')
        self.assertEqual(CJ.nom('Raphael Van Assche'), 'Van Assche')
        self.assertEqual(CJ.nom('Botic van de Zandschulp'), 'van de Zandschulp')
        self.assertEqual(CJ.nom('Tomas Martin Etcheverry'), 'Etcheverry')

    def test_jour(self):
        s = {'2-0': .5, '2-1': .2, '1-2': .1, '0-2': .2}
        doc = {'matchs': [match('a', 'A a', 'B b', .9, 20, s, .6), match('b', 'C c', 'D d', .55, 10, s, .3),
                          match('c', 'E e', 'F f', .3, 15, {'2-0': .1, '2-1': .3, '1-2': .3, '0-2': .3}, .4),
                          match('d', 'G g', 'H h', .5, 99, s, .9, circuit='ITF')]}
        c = CJ.classements_jour(doc, dt.date(2026, 11, 6))
        self.assertEqual(c['n'], 3)                                         # ITF exclu
        self.assertEqual([r[0] for r in c['aces']], ['a – b', 'e – f', 'c – d'])
        self.assertEqual(c['trois'][0], ('e – f', 'ATP', '60 %'))
        self.assertEqual(c['fav'][0], ('a', 'a – b', '90 %'))
        self.assertEqual(c['fav'][1][0], 'f')                               # favori = l'adversaire si p < 0,5

    def test_verification(self):
        s2 = {'2-0': .6, '2-1': .2, '1-2': .1, '0-2': .1}
        doc = {'apres_match': {
            '1': apres('A a', 'B b', .8, 'home', s2, '2-0', 20, 30, [0.6, True]),
            '2': apres('C c', 'D d', .7, 'away', s2, '1-2', 10, 2, [0.3, False]),
            '3': apres('E e', 'F f', .6, 'home', s2, '2-1', 15, 10, [0.5, False])}}
        v = CJ.verification(doc, dt.date(2026, 11, 5))
        self.assertEqual(v['moy_aces'], '14,0')
        self.assertEqual([r[3] for r in v['aces']], [True, False, False])
        self.assertEqual(v['fav'][1][3], False)                             # 70 % annoncé, perdu : affiché perdu
        self.assertEqual(v['tb'][0][2], 'Oui')
        self.assertEqual(v['lignes'], len(v['aces']) + len(v['trois']) + len(v['tb']) + len(v['fav']))

    def test_forfait_retire(self):
        import vitrine as V
        import feuilles as FE

        class I:
            def __init__(self, *_):
                pass

            def trouver(self, jour, h, a):
                return ({'statut': {'texte': 'Walkover'}}, False) if h == 'Matteo Berrettini' else (None, False)
        vieux = FE.Index, FE.lire
        FE.Index, FE.lire = I, lambda *a, **k: []
        try:
            m = [{'debut': '2026-11-06T10:00', 'home': 'Matteo Berrettini', 'away': 'Carlos Alcaraz'},
                 {'debut': '2026-11-06T18:00', 'home': 'Taylor Fritz', 'away': 'Carlos Alcaraz'}]
            r = V.retirer_annules(m, '.', dt.datetime(2026, 11, 6, 9, tzinfo=dt.timezone.utc))
            self.assertEqual([x['home'] for x in r], ['Taylor Fritz'])
        finally:
            FE.Index, FE.lire = vieux


if __name__ == '__main__':
    unittest.main()
