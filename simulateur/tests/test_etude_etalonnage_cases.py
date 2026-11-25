# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_etalonnage_cases.py (paquet 448 : analyse case par case, sans rien modifier), sur données
factices : aucune archive nécessaire."""
import datetime as dt
import gzip
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
import etude_etalonnage_cases as EC  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


def tirage(a_vrai, n, graine=1):
    """Logits vus du vainqueur, la réalité suivant σ(a_vrai · z0)."""
    rnd = random.Random(graine)
    Z = []
    for _ in range(n):
        z0 = rnd.gauss(0, 1.2)
        Z.append(z0 if rnd.random() < _sg(a_vrai * z0) else -z0)
    return Z


def rejeu_factice(pentes, n=1500):
    """Lignes du rejeu (circuit, date, n_min, z) : la réalité suit la pente de la classe d'expérience."""
    rows = []
    for c in EC.CIRCUITS:
        for nom, lo, hi in EC.FENETRES:
            for i, n_min in enumerate((15, 50, 150, 500)):
                for z in tirage(pentes[i], n, graine=sum(map(ord, f'{c}{nom}{i}'))):
                    rows.append((c, lo + dt.timedelta(days=30), n_min, z))
    return rows


class TestMesures(unittest.TestCase):
    def test_pente_et_erreur_type(self):
        a, et = EC.pente(tirage(0.8, 20000))
        self.assertAlmostEqual(a, 0.8, delta=0.04)
        self.assertGreater(et, 0)
        self.assertLess(et, 0.03)

    def test_lecture(self):
        self.assertEqual(EC.lecture(0.8, 0.03, 5000), '% trop sûrs')
        self.assertEqual(EC.lecture(1.2, 0.03, 5000), '% trop timides')
        self.assertEqual(EC.lecture(1.02, 0.03, 5000), "conforme à l'erreur près")
        self.assertTrue(EC.lecture(0.5, 0.1, 300).startswith('tendance seulement'))
        self.assertTrue(EC.lecture(None, None, 10).startswith('moins de'))

    def test_decrire(self):
        d = EC.decrire(tirage(1.0, 4000))
        self.assertEqual(d['matchs'], 4000)
        self.assertLess(abs(d['ecart_a_l_attendu']), 0.02)          # % exacts : log loss proche de l'attendu
        self.assertLess(abs(d['favori_annonce_pct'] - d['favori_reel_pct']), 3)
        self.assertEqual(sum(t['matchs'] for t in d['par_tranche'].values()), 4000)
        trop_surs = EC.decrire(tirage(0.6, 4000))
        self.assertGreater(trop_surs['ecart_a_l_attendu'], 0.01)
        self.assertGreater(trop_surs['favori_annonce_pct'], trop_surs['favori_reel_pct'])
        self.assertIsNone(EC.decrire([0.5] * 5)['pente'])          # trop peu de matchs : pas de pente
        self.assertEqual(EC.decrire([]), {'matchs': 0})

    def test_classes(self):
        self.assertEqual([EC.classe_experience(n) for n in (0, 29, 30, 99, 100, 299, 300, 5000)], [0, 0, 1, 1, 2, 2, 3, 3])
        self.assertEqual([EC.classe_ampleur(a) for a in (0, 0.1, -0.1, 0.2, -0.5)], [0, 1, 1, 2, 2])


class TestRejeuEtAccord(unittest.TestCase):
    def setUp(self):
        self.rj = EC.decrire_rejeu(rejeu_factice((0.7, 1.0, 1.0, 1.3)))

    def test_fenetres(self):
        ch = self.rj['CH']
        self.assertEqual(ch['reference'], '2025 → mai 2026')
        self.assertNotIn(EC.DEUXIEME_PERIODE, ch['par_classe']['0'])   # Challenger : pas de 2023 → mai 2026 agrégé
        self.assertIn(EC.DEUXIEME_PERIODE, self.rj['ATP']['par_classe']['0'])
        self.assertEqual(ch['par_classe']['0']['2025 → mai 2026']['lecture'], '% trop sûrs')
        self.assertEqual(ch['par_classe']['3']['2025 → mai 2026']['lecture'], '% trop timides')

    def test_reference_et_verdict(self):
        ref, d = EC.reference(self.rj, 'CH', 0)
        self.assertEqual(ref, -1)
        self.assertEqual(EC.reference(self.rj, 'ATP', 3)[0], 1)              # même sens sur les deux périodes
        self.assertEqual(EC.verdict(-1, EC.decrire(tirage(0.6, 3000))), "d'accord")
        self.assertEqual(EC.verdict(-1, EC.decrire(tirage(1.5, 3000))), 'en désaccord')
        self.assertEqual(EC.verdict(-1, EC.decrire(tirage(0.6, 50))), 'trop peu de matchs en direct')
        self.assertTrue(EC.verdict(None, EC.decrire(tirage(0.6, 3000))).startswith('référence illisible'))

    def test_periodes_en_desaccord_illisibles(self):
        rows = [r for r in rejeu_factice((1.0, 1.0, 1.0, 1.0)) if r[0] != 'ATP']
        rows += [('ATP', dt.date(2019, 5, 1), 500, z) for z in tirage(0.7, 3000, 5)]
        rows += [('ATP', dt.date(2024, 5, 1), 500, z) for z in tirage(1.3, 3000, 6)]
        self.assertIsNone(EC.reference(EC.decrire_rejeu(rows), 'ATP', 3)[0])


class TestDirect(unittest.TestCase):
    def _racine(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        os.makedirs(os.path.join(d, 'simulateur', 'journal_pronostics', 'fiches'))
        rnd = random.Random(4)
        matchs, fiches = [], {}
        for i in range(300):
            p = rnd.uniform(0.3, 0.9)
            uid = f'm{i}'
            matchs.append({'uid': uid, 'debut': '2026-11-10T10:00', 'circuit': 'CH', 'p_affiche': p,
                           'matchs_joues': [rnd.choice((10, 50, 150, 400)), 500],
                           'reel': {'gagnant': 'home' if rnd.random() < p else 'away', 'interrompu': None},
                           'premier': {'stats': {'p_home': p}, 'simulation': {'p_home': 0.5}},
                           'fiabilite': {'niveau': 'correct', 'version_fiabilite': 'pente_v3', 'fragile_criteres': []}})
            fiches[uid] = {'dernier': {'p_home': p, 'controle': {'signaux_circuit': {
                'decalages': {'age': 0.2}, 'p_home_sans': _sg(math.log(p / (1 - p)) - 0.2)}}}}
        matchs.append({'uid': 'x', 'circuit': 'CH', 'p_affiche': 0.6, 'matchs_joues': [10, 10],
                       'reel': {'gagnant': 'home', 'interrompu': 'abandon'}})            # abandon : écarté
        matchs.append({'uid': 'y', 'circuit': 'ITF', 'p_affiche': 0.6, 'matchs_joues': [10, 10],
                       'reel': {'gagnant': 'home'}})                                        # ITF : jamais
        with open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w', encoding='utf-8') as f:
            json.dump({'matchs': matchs}, f)
        with gzip.open(os.path.join(d, 'simulateur', 'journal_pronostics', 'fiches', '2026-11-10.json.gz'), 'wt',
                       encoding='utf-8') as f:
            json.dump(fiches, f)
        return d

    def test_lignes_et_description(self):
        L = EC.lignes_direct(self._racine())
        self.assertEqual(len(L), 300)
        self.assertTrue(all('z_fiche' in r and r['ampleur'] == 0.2 for r in L))
        rj = EC.decrire_rejeu(rejeu_factice((1.0, 1.0, 1.0, 1.0), n=300))
        D = EC.decrire_direct(L, rj, {}, {'CH|0': 0.75})
        self.assertEqual(D['matchs'], 300)
        self.assertEqual(sum(v['publie'].get('matchs', 0) for v in D['par_classe'].values()), 300)
        self.assertEqual(D['accord_avec_le_rejeu']['CH|0']['pente_de_la_note_v3'], 0.75)
        cas = [k for k in D['par_case'] if k.endswith('|2')]                 # ampleur 0,2 : classe « ≥ 0,15 »
        self.assertTrue(cas)
        sig = D['par_classe']['CH|2']['chaque_signal']['age']
        self.assertEqual(sig['matchs'], D['par_classe']['CH|2']['fiche_avec_signaux']['matchs'])
        self.assertGreater(sig['decalage_moyen_vers_le_favori'], -1)
        self.assertIn('correct', D['par_niveau_note_v3'])


class TestJournal(unittest.TestCase):
    def test_gabarit_et_entree(self):
        with open(EC.GABARIT_JOURNAL, encoding='utf-8') as f:
            g = json.load(f)
        self.assertEqual(g['paquet'], 448)
        rj = EC.decrire_rejeu(rejeu_factice((0.8, 1.0, 1.0, 1.2)))
        doc = {'direct': EC.decrire_direct([], rj, {}, {})}
        e = EC.entree_journal(doc, g)
        self.assertEqual(e['paquet'], 448)
        self.assertIn('Le % de victoire ne change pas', e['quoi'])
        for mot in ('marché', 'Pinnacle', 'cote'):
            self.assertNotIn(mot, e['quoi'] + e['garde_fou'])

    def test_ajouter_remplace(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'j.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'changements': [{'paquet': 448, 'quoi': 'ancien'}]}, f)
        EC.ajouter_au_journal(p, {'paquet': 448, 'quoi': 'nouveau'})
        EC.ajouter_au_journal(p, {'paquet': 449, 'quoi': 'autre'})
        L = json.load(open(p, encoding='utf-8'))['changements']
        self.assertEqual([x['quoi'] for x in L], ['nouveau', 'autre'])

    def test_rien_en_production(self):
        src = open(os.path.join(os.path.dirname(ICI), 'etude_etalonnage_cases.py'), encoding='utf-8').read()
        for fichier in ('pente_cases.json', 'correction_niveaux.json', 'corrections_chercheur.json'):
            self.assertNotIn(f"'{fichier}'), 'w'", src)                          # lus, jamais écrits
        self.assertIn('aucune correction proposée ni appliquée', src)


if __name__ == '__main__':
    unittest.main()
