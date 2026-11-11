# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 230) — départ des joueurs vus d'abord en ITF hommes : l'étude, la production, le suivi, le retrait."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import backtest_pronostic as BP  # noqa: E402
import elo as E  # noqa: E402
import etude_depart_itf as ED  # noqa: E402


def match(g, p, jour, circuit, niveau='C', abandon=False):
    return {'nom_g': g, 'nom_p': p, 'circuit': circuit, 'surface': 'Hard', 'date': jour, 'bo': 3, 'sets': [(6, 3), (6, 4)],
            'complet': True, 'abandon': abandon, 'niveau': niveau}


class Depart(unittest.TestCase):
    def test_seul_l_itf_hommes_a_un_depart_propre(self):
        self.assertEqual(E.DEPARTS_PAR_NIVEAU, {'ITFH': 1000.0})
        self.assertEqual(E.depart_du_niveau('ITFH', 1200.0), 1000.0)
        for c in ('CH', 'ITF', 'ATP', 'WTA'):
            self.assertEqual(E.depart_du_niveau(c, 1200.0), 1200.0)
        self.assertEqual(E.depart_du_niveau('ITFH', 1200.0, {}), 1200.0)             # l'ancien réglage, pour le suivi

    def test_departs_en_place_suit_l_etat_du_classement(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            self.assertEqual(E.departs_en_place(d), {'ITFH': 1000.0})               # pas d'état : le réglage du code
            chemin = os.path.join(d, 'simulateur', 'elo_etat.json')
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump({'depart_bas': 1200.0}, f)                               # état d'avant le paquet 230
            self.assertEqual(E.departs_en_place(d), {'ITFH': 1000.0})
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump({'depart_bas': 1200.0, 'departs_par_niveau': {}}, f)     # retiré par le suivi
            self.assertEqual(E.departs_en_place(d), {})

    def test_le_classement_de_production_applique_le_depart(self):
        j = dt.date(2025, 3, 3)
        M = [match('Ana A', 'Bob B', j, 'ITFH'), match('Cal C', 'Dan D', j, 'CH')]
        R = BP.rejouer(M, [], [], E.cle, None, True, options={})
        a, b, c, d = (E.cle(n) for n in ('Ana A', 'Bob B', 'Cal C', 'Dan D'))
        self.assertAlmostEqual(R['elo'].g[a] + R['elo'].g[b], 2000.0, places=6)     # ITF hommes : 1000 chacun
        self.assertAlmostEqual(R['elo'].g[c] + R['elo'].g[d], 2400.0, places=6)     # Challenger : toujours 1200
        T = BP.rejouer(M, [], [], E.cle, None, True, options={}, departs={})
        self.assertAlmostEqual(T['elo'].g[a] + T['elo'].g[b], 2400.0, places=6)     # le témoin du suivi
        self.assertEqual(T['elo'].g[c], R['elo'].g[c])

    def test_un_joueur_deja_vu_ne_repart_pas(self):
        j = dt.date(2025, 3, 3)
        M = [match('Cal C', 'Dan D', j, 'CH'), match('Cal C', 'Bob B', j + dt.timedelta(days=7), 'ITFH')]
        R = BP.rejouer(M, [], [], E.cle, None, True, options={})
        self.assertGreater(R['elo'].g[E.cle('Cal C')], 1200.0)                      # vu d'abord en Challenger : parti de 1200

    def test_l_etude_de_l_itf_et_le_classement_lisent_la_meme_source(self):
        for nom in ('backtest_pronostic.py', 'etude_itf_elo.py'):
            with open(os.path.join(RACINE, 'simulateur', nom), encoding='utf-8') as f:
                self.assertIn('E.depart_du_niveau(', f.read(), nom)


class Suivi(unittest.TestCase):
    def paires(self, n, p_avec, p_sans, jour='2026-12-01'):
        return [(jour, p_avec)] * n, [(jour, p_sans)] * n

    def test_rien_avant_300_matchs(self):
        s = E.suivi_departs(*self.paires(299, 0.55, 0.60))
        self.assertEqual(s['matchs'], 299)
        self.assertLess(s['gain_log_loss'], 0)
        self.assertFalse(s['retrait'])

    def test_retrait_si_le_cumul_est_nettement_negatif(self):
        avec = [('2026-12-01', 0.55 if k % 2 else 0.52) for k in range(400)]
        sans = [('2026-12-01', 0.60 if k % 2 else 0.58) for k in range(400)]
        s = E.suivi_departs(avec, sans)
        self.assertTrue(s['retrait'])
        self.assertGreater(s['brier'], s['brier_avant'])
        self.assertFalse(E.suivi_departs(sans, avec)['retrait'])                    # dans l'autre sens : il reste

    def test_un_cumul_negatif_mais_bruite_ne_retire_pas(self):
        avec = [('2026-12-01', 0.9 if k % 2 else 0.30) for k in range(400)]
        sans = [('2026-12-01', 0.6 if k % 2 else 0.46) for k in range(400)]
        s = E.suivi_departs(avec, sans)
        self.assertLess(s['gain_log_loss'], 0)
        self.assertLess(abs(s['gain_log_loss']), 2 * s['erreur_type'])
        self.assertFalse(s['retrait'])

    def test_seuls_les_matchs_depuis_le_debut_du_suivi_comptent(self):
        a, b = self.paires(500, 0.55, 0.60, jour='2026-11-11')
        self.assertEqual(E.suivi_departs(a, b), {'depuis': '2026-11-12', 'matchs': 0, 'retrait': False})
        self.assertEqual(E.suivi_departs(a, b, depuis='0000')['matchs'], 500)

    def test_la_regle_est_ecrite_dans_le_code(self):
        self.assertEqual((E.DEPARTS_SUIVI_DEPUIS, E.DEPARTS_RETRAIT_MIN_MATCHS, E.DEPARTS_RETRAIT_ERREURS_TYPES),
                         ('2026-11-12', 300, 2.0))
        with open(os.path.join(RACINE, 'simulateur', 'backtest_pronostic.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn("departs={})", src)                                           # le témoin est rejoué à chaque passage
        self.assertIn("'depart_itf_hommes': depart_itf", src)
        self.assertIn("'departs_par_niveau': departs_places if depart_itf.get('en_place') else {}", src)


class Etude(unittest.TestCase):
    def test_rejeu_le_depart_itf_ne_touche_que_les_joueurs_vus_d_abord_en_itf(self):
        j = dt.date(2025, 2, 3)
        M = [match('Ana A', 'Bob B', j, 'ITFH'), match('Cal C', 'Dan D', j, 'CH'),
             match('Cal C', 'Ana A', j + dt.timedelta(days=7), 'CH'), match('Cal C', 'Dan D', j + dt.timedelta(days=8), 'CH', abandon=True),
             match('Eve E', 'Fay F', j + dt.timedelta(days=9), 'ATP', niveau='D'), match('Eve E', 'Fay F', j + dt.timedelta(days=10), 'ATP', niveau='A')]
        base, bas = ED.rejouer(M, RACINE), ED.rejouer(M, RACINE, depart_itf=1000.0)
        self.assertEqual([r[0] for r in base], ['CH', 'CH', 'ATP'])                 # ni l'ITF, ni l'abandon, ni le niveau « D »
        self.assertEqual(base[0][2], bas[0][2])                                     # deux joueurs du Challenger : inchangé
        self.assertGreater(bas[1][2], base[1][2])                                   # face au joueur venu de l'ITF : plus tranché
        self.assertEqual(base[2][2], bas[2][2])

    def test_la_regle_est_ecrite_avant_et_l_elo_est_celui_de_production(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_depart_itf.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('AVANT TOUT ESSAI', src)
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
        self.assertEqual(ED.DEPARTS_ITF, (1150.0, 1100.0, 1050.0, 1000.0))
        self.assertEqual((ED.MIN_JUGES, ED.MARGE, ED.DEGRADATION_MAX), (1000, 0.001, 0.0005))


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_depart_itf.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_rapport_public_avec_brier(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['challenger_2025_10_a_2026_06'])

    def test_la_forme_a_ete_choisie_sur_la_periode_d_apprentissage(self):
        c = self.R['candidats_2025_01_a_2025_09']
        self.assertEqual(self.R['forme_choisie'], max(c, key=lambda n: c[n]['appr']['gain']))

    def test_le_verdict_suit_la_regle(self):
        j, a = self.R['challenger_2025_10_a_2026_06'], self.R['atp_2025_10_a_2026_06']
        passe = (j['matchs'] >= 1000 and j['gain'] >= 0.001 and a['gain'] >= -0.0005
                 and self.R['candidats_2025_01_a_2025_09'][self.R['forme_choisie']]['appr']['gain'] > 0)
        self.assertEqual(self.R['retenue'], passe)

    def test_rien_n_est_en_production_qui_n_ait_passe(self):
        if self.R['retenue']:
            c = self.R['controle_production']
            self.assertLessEqual(c['nos_matchs_tous_niveaux']['log_loss'], c['nos_matchs_tous_niveaux']['log_loss_avant'])
            self.assertEqual(E.DEPARTS_PAR_NIVEAU, {'ITFH': self.R['reglage']['depart_itf']})
            self.assertEqual(self.R['production']['depart'], E.DEPARTS_PAR_NIVEAU)
            self.assertIn('300 matchs', self.R['production']['retrait'])
        else:
            self.assertEqual(E.DEPARTS_PAR_NIVEAU, {})

    def test_la_limite_est_dite(self):
        self.assertIn('bord de la grille', self.R['limite'])


if __name__ == '__main__':
    unittest.main()
