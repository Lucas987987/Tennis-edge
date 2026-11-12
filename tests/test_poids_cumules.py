# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 242) — les poids du mélange fournissent le détail par match et passent à la règle cumulée."""
import datetime as dt
import json
import math
import os
import random
import re
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
SIM = os.path.join(RACINE, 'simulateur')
sys.path.insert(0, SIM)
import backtest_match_simule as BMS  # noqa: E402
import entrainement_progressif as EP  # noqa: E402
import etude_poids_cumules as PC  # noqa: E402
import stabilite as ST  # noqa: E402


def hors(n, circuit='CH', graine=1, debut=dt.date(2026, 6, 1), par_jour=8):
    """Matchs vus du vrai vainqueur : p_elo informatif, p_sim bruité."""
    rnd = random.Random(graine)
    out = []
    for i in range(n):
        z = rnd.gauss(0, 1.0)
        pe = 1 / (1 + math.exp(-z))
        ps = 1 / (1 + math.exp(-(z + rnd.gauss(0, 0.8))))
        if rnd.random() > pe:                                   # le favori de l'Elo perd : vu du vainqueur
            pe, ps = 1 - pe, 1 - ps
        out.append(({'jour': debut + dt.timedelta(days=i // par_jour), 'circuit': circuit}, ps, pe))
    return out


P = {'elo': 0.78, 'simulation': 0.24}


class DetailParMatch(unittest.TestCase):
    def test_paires_match(self):
        p = EP.paires_match([dt.date(2026, 11, 2)], [0.5], [0.8])
        self.assertEqual(p, [('2026-11-02', round(math.log(2), 6), round(-math.log(0.8), 6))])

    def test_poids_circuit_donne_un_detail_par_match_juge(self):
        H = hors(3000)
        lim = H[-1][0]['jour'] - dt.timedelta(days=EP.FENETRE_JUGE_J)
        r = EP.poids_circuit(H, P, lim, BMS.ajuster_poids, 'CH')
        self.assertEqual(len(r['paires']), r['n_juge'])
        l0 = sum(a for _, a, _ in r['paires']) / len(r['paires'])
        l1 = sum(b for _, _, b in r['paires']) / len(r['paires'])
        self.assertAlmostEqual(l0, r['ll']['sans'], places=5)  # sans = poids communs, avec = poids propres
        self.assertAlmostEqual(l1, r['ll']['avec'], places=5)

    def test_trop_peu_de_matchs_rien_ne_bouge(self):
        H = hors(200)
        lim = H[-1][0]['jour'] - dt.timedelta(days=EP.FENETRE_JUGE_J)
        r = EP.poids_circuit(H, P, lim, BMS.ajuster_poids, 'CH')
        self.assertEqual(r['paires'], [])
        etat = {'poids_CH': {'adopte': True}}
        out = ST.appliquer(etat, 'poids_CH', {'adopte': True, 'poids': {'elo': 1, 'simulation': 0}},
                           EP.pour_stabilite(r, ('adopte', 'poids', 'raison', 'll')), ('poids',))
        self.assertTrue(out['adopte'])                              # règle cumulée : pas de sortie sans matchs
        self.assertEqual(out['poids'], {'elo': 1, 'simulation': 0})
        self.assertEqual(etat['poids_CH']['regle'], 'cumulee')

    def test_desaccords_sans_donnees(self):
        self.assertEqual(EP.desaccord_wta([], P, dt.date(2026, 1, 1), BMS.ajuster_poids, None, None)['paires'], [])

    def test_pour_stabilite(self):
        self.assertNotIn('paires', EP.pour_stabilite({'adopte': True}, ('adopte',)))
        self.assertEqual(EP.pour_stabilite({'adopte': True, 'paires': []}, ('adopte',))['paires'], [])
        self.assertEqual(EP.pour_stabilite(None, ('adopte',)), {'adopte': None})

    def test_appliquer_ne_garde_pas_le_detail(self):
        H = hors(3000, graine=4)
        lim = H[-1][0]['jour'] - dt.timedelta(days=EP.FENETRE_JUGE_J)
        r = EP.poids_circuit(H, P, lim, BMS.ajuster_poids, 'CH')
        etat = {}
        out = ST.appliquer(etat, 'poids_CH', None, EP.pour_stabilite(r, ('adopte', 'poids', 'raison', 'll')), ('poids',))
        self.assertNotIn('paires', json.dumps(out))
        self.assertNotIn('paires', json.dumps(etat))
        self.assertIn('cumul', out['stabilite'])


class Branchement(unittest.TestCase):
    def setUp(self):
        self.f = open(os.path.join(SIM, 'facteurs.py'), encoding='utf-8').read()

    def test_les_cinq_poids_passent_le_detail(self):
        for cle in ("'combinaison_feuilles'", "'poids_challenger'", "'poids_' + c_", "'desaccord_wta'"):
            i = self.f.index(f"ST.appliquer(etat_st, {cle}")
            self.assertIn('EP.pour_stabilite(', self.f[i:i + 300], cle)

    def test_rien_d_enregistre(self):
        i = self.f.index("json.dump(doc, f, ensure_ascii=False, indent=1)")
        self.assertIn('sans_paires(doc)', self.f[i - 300:i])

    def test_combinaison_feuilles_fournit_le_detail(self):
        src = open(os.path.join(SIM, 'entrainement_progressif.py'), encoding='utf-8').read()
        self.assertRegex(src, r"out\['paires'\] = paires_match\(\[h\[0\]\['jour'\] for h in juge\], p_arch, p_new\)")
        self.assertIn("raison='pas assez de matchs pour juger', paires=[]", src)


class Rapport(unittest.TestCase):
    def setUp(self):
        self.r = json.load(open(os.path.join(SIM, 'rapport_poids_cumules.json'), encoding='utf-8'))

    def test_chaque_jour_compte_une_fois(self):
        self.assertTrue(self.r['semaines_rejouees'] >= 5)
        self.assertEqual(set(self.r['jours_comptes_deux_fois'].values()), {0})

    def test_aucune_decision_sur_le_rejeu(self):
        self.assertEqual(self.r['statut'], 'controle')
        self.assertIn('aucune décision', self.r['regle'])

    def test_public(self):
        t = json.dumps(self.r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t)
        for cle in ('joueur', 'nom', 'home', 'away'):           # pas de joueurs : des poids et des comptes
            self.assertNotIn(f'"{cle}', t)

    def test_rejeu_reproductible(self):
        H = PC.charger(os.path.join(SIM, 'pronostics_hors_echantillon.jsonl.gz'))
        self.assertTrue(all(0 < ps < 1 and 0 < pe < 1 for _, ps, pe in H))


if __name__ == '__main__':
    unittest.main()
