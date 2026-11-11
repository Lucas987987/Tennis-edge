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

# 11/11/2026 (paquet 227) — mots qui ne doivent jamais sortir dans le journal PUBLIÉ sur le site : la comparaison aux
# cotes reste privée. « cote » seul n'y est pas : « aucune cote », « indépendant des cotes » sont le message voulu.
INTERDITS_JOURNAL = ('marché', 'marche ', 'pinnacle', 'clôture', 'cloture', 'closing', 'oddspapi')


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
        for mot in INTERDITS_JOURNAL:                      # 11/11/2026 (paquet 227) : plus seulement « marché »
            self.assertNotIn(mot, txt, f"« {mot} » dans le journal publié : marquer l'entrée « prive »")

    def test_entrees_internes_jamais_publiees(self):
        """11/11/2026 (paquet 227) — une entrée « prive » reste dans le fichier mais ne sort pas sur le site."""
        racine = os.path.join(ICI, '..')
        with open(os.path.join(racine, 'simulateur', 'journal_changements.json'), encoding='utf-8') as fh:
            source = json.load(fh)['changements']
        prives = [c for c in source if c.get('prive')]
        self.assertTrue(prives, "le journal doit garder ses entrées internes, marquées « prive »")
        J = V.journal_changements(racine)
        self.assertTrue(J['entrees_internes_masquees'])
        self.assertEqual(len(J['changements']), len(source) - len(prives))
        self.assertFalse([c for c in J['changements'] if c.get('prive')])

    def test_filtre_sur_un_journal_fictif(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            with open(os.path.join(d, 'simulateur', 'journal_changements.json'), 'w', encoding='utf-8') as fh:
                json.dump({'regle': 'r', 'changements': [{'quoi': 'public', 'statut': 'production'},
                                                         {'quoi': 'interne', 'statut': 'etude', 'prive': True}]}, fh)
            J = V.journal_changements(d)
            self.assertEqual([c['quoi'] for c in J['changements']], ['public'])
            self.assertEqual(J['regle'], 'r')


class TestSitePublic(unittest.TestCase):
    def test_page_publique_sans_mot_interdit(self):
        racine = os.path.join(ICI, '..')
        vus = 0
        for f in ('algo/index.html', 'algo/donnees.json'):
            p = os.path.join(racine, f)
            if not os.path.exists(p):
                continue
            vus += 1
            with open(p, encoding='utf-8') as fh:
                txt = fh.read().lower()
            self.assertNotIn('marché', txt, f)
        self.assertGreaterEqual(vus, 1)

    def test_journal_des_donnees_publiques(self):
        """11/11/2026 (paquet 227) — le journal embarqué dans algo/donnees.json, dès qu'il a été produit par la vitrine
        filtrée (repère entrees_internes_masquees), ne contient aucun mot réservé aux outils privés. Un fichier produit
        avant le paquet n'a pas le repère : il n'est pas jugé, il sera remplacé au prochain passage."""
        p = os.path.join(ICI, '..', 'algo', 'donnees.json')
        if not os.path.exists(p):
            self.skipTest('algo/donnees.json absent')
        with open(p, encoding='utf-8') as fh:
            J = (json.load(fh) or {}).get('journal_changements') or {}
        if not J.get('entrees_internes_masquees'):
            self.skipTest("algo/donnees.json produit avant le filtre du journal : jugé au prochain passage")
        txt = json.dumps(J, ensure_ascii=False).lower()
        for mot in INTERDITS_JOURNAL:
            self.assertNotIn(mot, txt, mot)
        self.assertFalse([c for c in J.get('changements') or [] if c.get('prive')])


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
