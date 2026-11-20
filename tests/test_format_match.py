# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 228) — format du match : l'étude, le signal en production, son suivi et sa règle de retrait."""
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
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import apres_match as AM  # noqa: E402
import etude_format_match as EF  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
lg = lambda p: math.log(p / (1 - p))


def tirage(n, k, graine, ecart=1.0):
    """n matchs dont le favori gagne selon σ(k·z) : z rendu du point de vue du VAINQUEUR, comme dans l'étude."""
    rnd, out = random.Random(graine), []
    for _ in range(n):
        z = rnd.gauss(0, ecart)
        out.append(z if rnd.random() < sg(k * z) else -z)
    return out


class Etude(unittest.TestCase):
    def test_la_pente_retrouve_un_elo_trop_sur_de_lui(self):
        self.assertAlmostEqual(EF.pente(tirage(20000, 0.8, 1)), 0.8, delta=0.05)
        self.assertAlmostEqual(EF.pente(tirage(20000, 1.2, 2)), 1.2, delta=0.07)
        self.assertAlmostEqual(EF.pente(tirage(20000, 1.0, 3)), 1.0, delta=0.06)

    def test_mesure_gain_positif_quand_la_pente_est_la_bonne(self):
        m = EF.mesure(tirage(20000, 0.8, 4), 0.8)
        self.assertGreater(m['gain'], 0.001)
        self.assertGreater(m['erreurs_types'], 2)
        self.assertGreater(m['favori_annonce_pct'], m['favori_reel_pct'])       # trop sûr de lui
        self.assertEqual(EF.mesure([]), {'matchs': 0})

    def test_la_regle_demande_les_quatre_conditions(self):
        bon = {'matchs': 5000, 'gain': 0.003, 'erreurs_types': 3.0, 'pente_propre': 0.82}
        self.assertEqual(EF.verdict({}, bon, 0.815), (True, []))
        self.assertFalse(EF.verdict({}, dict(bon, matchs=900), 0.815)[0])
        self.assertFalse(EF.verdict({}, dict(bon, gain=0.0009), 0.815)[0])
        self.assertFalse(EF.verdict({}, dict(bon, pente_propre=1.05), 0.815)[0])   # biais de sens contraire
        # la condition « 2 erreurs types » est jugée à part : elle ne fait pas échouer la règle du brief
        self.assertTrue(EF.verdict({}, dict(bon, erreurs_types=1.9), 0.815)[0])
        self.assertFalse(EF.deux_erreurs_types(dict(bon, erreurs_types=1.9)))
        self.assertTrue(EF.deux_erreurs_types(bon))

    def test_rien_n_est_adopte_si_un_seul_format_passe(self):
        d1, d2 = dt.date(2020, 1, 1), dt.date(2024, 1, 1)
        rows = ([('ATP', d1, 3, z) for z in tirage(9000, 0.8, 5)] + [('ATP', d2, 3, z) for z in tirage(9000, 0.8, 6)]
                + [('ATP', d1, 5, z) for z in tirage(2000, 1.2, 7)] + [('ATP', d2, 5, z) for z in tirage(300, 1.2, 8)])
        doc = EF.etudier(rows)
        atp = doc['circuits']['ATP']
        self.assertTrue(atp['2_sets_gagnants']['passe_la_regle'])
        self.assertFalse(atp['3_sets_gagnants']['passe_la_regle'])
        self.assertIn('moins de 1000 matchs jugés', atp['3_sets_gagnants']['raisons'])
        self.assertFalse(doc['adopte'])
        self.assertLess(doc['pentes_atp']['2_sets_gagnants'], 1)

    def test_les_competitions_par_equipes_sont_hors_jugement(self):
        """Paquet 229 : la Coupe Davis (niveau « D ») gonflait le résultat ; elle reste dans l'Elo, pas dans le jugement."""
        self.assertTrue(EF.par_equipes({'niveau': 'D'}))
        self.assertFalse(EF.par_equipes({'niveau': 'A'}))
        self.assertFalse(EF.par_equipes({}))
        with open(os.path.join(RACINE, 'simulateur', 'rapport_format_match.json'), encoding='utf-8') as f:
            R = json.load(f)
        eq = R['competitions_par_equipes_atp_pour_memoire']['2023 → juin 2026']
        self.assertGreater(eq['matchs'], 500)
        self.assertLess(eq['pente_propre'], 0.75)                    # bien plus mal étalonné que le circuit
        self.assertIn('exclues', R['regle'])

    def test_l_etude_prend_l_elo_de_production(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_format_match.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
        self.assertIn('AVANT DE REGARDER', src)


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_format_match.json'), encoding='utf-8') as f:
            cls.R = json.load(f)
        with open(os.path.join(RACINE, 'simulateur', 'format_match.json'), encoding='utf-8') as f:
            cls.C = json.load(f)

    def test_rapport_public(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)

    def test_une_pente_en_production_a_passe_la_regle(self):
        """Rien n'est en production qui n'ait passé la règle du brief sur la période de jugement, avec au moins
        1,9 erreur type (la condition des 2 erreurs types est publiée à part dans le rapport)."""
        nom = {'2': '2_sets_gagnants', '3': '3_sets_gagnants'}
        for c, pentes in (self.C.get('pentes') or {}).items():
            for sets_gagnants, k in pentes.items():
                bloc = self.R['circuits'][c][nom[sets_gagnants]]
                self.assertTrue(bloc['passe_la_regle'], (c, sets_gagnants))
                self.assertAlmostEqual(k, bloc['pente_apprise'], places=3)
                j = bloc['2023 → juin 2026']
                self.assertGreaterEqual(j['matchs'], 1000)
                self.assertGreaterEqual(j['gain'], 0.001)
                self.assertGreaterEqual(j['erreurs_types'], 1.9)
                self.assertIn('passe_deux_erreurs_types', bloc)

    def test_un_format_qui_ne_passe_pas_reste_en_attente(self):
        for c, bloc in self.R['circuits'].items():
            for f_, v in bloc.items():
                if not v['passe_la_regle'] or (v['2023 → juin 2026'].get('erreurs_types') or 0) < 1.9:
                    self.assertNotIn(f_[0], (self.C.get('pentes') or {}).get(c) or {}, (c, f_))
        self.assertNotIn('WTA', self.C.get('pentes') or {})
        self.assertNotIn('CH', self.C.get('pentes') or {})


class Production(unittest.TestCase):
    def setUp(self):
        self._avant = (PJ.FORMAT_MATCH, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT)
        PJ.FORMAT_MATCH = {'ATP': {2: 0.815}}
        PJ.COMBINAISON = {'elo': 0.78, 'simulation': 0.24}
        PJ.SIGNAUX_CIRCUIT = {'format_match': ['ATP']}

    def tearDown(self):
        PJ.FORMAT_MATCH, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT = self._avant

    def test_le_reglage_du_depot(self):
        self.assertEqual(PJ.charger_format_match(RACINE), {'ATP': {2: 0.826}})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(PJ.charger_format_match(d), {})

    def test_decalage_vers_50_en_deux_sets_gagnants(self):
        c = PJ.controle_format(0.70, 0.70, 'ATP', 2)
        self.assertAlmostEqual(c['decalage'], 0.78 * (0.815 - 1) * lg(0.70), places=4)
        self.assertLess(c['p_home'], 0.70)
        self.assertGreater(c['p_home'], 0.65)                       # 2 à 3 points, pas plus
        d = PJ.controle_format(0.30, 0.30, 'ATP', 2)
        self.assertAlmostEqual(d['decalage'], -c['decalage'], places=4)   # symétrique
        self.assertAlmostEqual(d['p_home'], 1 - c['p_home'], places=3)

    def test_seule_la_part_de_l_elo_bouge(self):
        """Même % affiché, Elo plus tranché → décalage plus grand ; Elo à 50 % → rien."""
        a, b = PJ.controle_format(0.60, 0.60, 'ATP', 2), PJ.controle_format(0.60, 0.80, 'ATP', 2)
        self.assertLess(b['decalage'], a['decalage'])
        self.assertIsNone(PJ.controle_format(0.60, 0.50, 'ATP', 2))

    def test_rien_ailleurs(self):
        self.assertIsNone(PJ.controle_format(0.70, 0.70, 'ATP', 3))     # 3 sets gagnants : en attente
        self.assertIsNone(PJ.controle_format(0.70, 0.70, 'WTA', 2))
        self.assertIsNone(PJ.controle_format(0.70, 0.70, 'CH', 2))
        self.assertIsNone(PJ.controle_format(None, 0.70, 'ATP', 2))
        self.assertIsNone(PJ.controle_format(0.70, None, 'ATP', 2))

    def test_sans_melange_la_pente_porte_sur_tout_l_elo(self):
        PJ.COMBINAISON = None
        self.assertAlmostEqual(PJ.controle_format(0.70, 0.70, 'ATP', 2)['decalage'], (0.815 - 1) * lg(0.70), places=4)

    def test_applique_seulement_sur_le_circuit_adopte(self):
        f = PJ.controle_format(0.70, 0.70, 'ATP', 2)
        self.assertEqual(PJ.signaux_du_match('ATP', 0.70, None, None, None, None, fmt_ctl=f), {'format_match': f['decalage']})
        self.assertEqual(PJ.signaux_du_match('WTA', 0.70, None, None, None, None, fmt_ctl=f), {})
        PJ.SIGNAUX_CIRCUIT = {'age': ['ATP']}                              # retiré : plus appliqué
        self.assertEqual(PJ.signaux_du_match('ATP', 0.70, None, None, None, None, fmt_ctl=f), {})


def bilan(circuit, jour, ll_affiche, ll_sans_format, uid):
    return {'circuit': circuit, 'debut': jour + 'T12:00:00+00:00', 'home': 'A' + uid, 'away': 'B' + uid,
            'ecarts': {'signaux_circuit': {'appliques': ['age', 'format_match'], 'll_affiche': ll_affiche, 'll_sans': 9.9,
                                           'sans_chacun': {'format_match': ll_sans_format, 'age': 5.5}}}}


class Suivi(unittest.TestCase):
    def test_bilan_apres_match_mesure_chaque_signal_seul(self):
        f = {'debut': '2026-11-12T10:00:00+00:00', 'circuit': 'ATP', 'home': 'A Un', 'away': 'B Deux',
             'dernier': {'p_home': 0.66, 'controle': {'signaux_circuit': {
                 'appliques': ['age', 'format_match'], 'p_home_sans': 0.70, 'decalages': {'age': -0.05, 'format_match': -0.13}}}}}
        e = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-3 6-3', 'sets': '2-0'})['ecarts']['signaux_circuit']
        sans_format = sg(lg(0.66) + 0.13)
        self.assertAlmostEqual(e['sans_chacun']['format_match'], -math.log(sans_format), places=4)
        self.assertLess(e['sans_chacun']['format_match'], e['ll_affiche'])    # le favori a gagné : la pente a coûté
        self.assertIn('age', e['sans_chacun'])

    def test_fantome_tant_que_le_signal_n_est_pas_applique(self):
        f = {'debut': '2026-11-12T10:00:00+00:00', 'circuit': 'ATP', 'home': 'A Un', 'away': 'B Deux',
             'dernier': {'p_home': 0.70, 'controle': {'format_match': {'p_home': 0.675, 'decalage': -0.12}}}}
        e = AM.bilan_match('u', f, {'gagnant': 'away', 'score': '3-6 3-6', 'sets': '0-2'})['ecarts']
        self.assertLess(e['fantome_format_match']['ll_reference'], e['fantome_format_match']['ll_elo'])

    def test_le_signal_est_juge_sur_son_effet_propre(self):
        b = bilan('ATP', '2026-11-12', 0.60, 0.62, '1')
        self.assertEqual(FC.paires(b, 'format_match'), (0.62, 0.60))        # pas le 9,9 de tous les signaux
        self.assertEqual(FC.paires(b, 'age'), (5.5, 0.60))                  # 12/11/2026 : les autres aussi, sur leur effet propre
        del b['ecarts']['signaux_circuit']['sans_chacun']
        self.assertIsNone(FC.paires(b, 'format_match'))                     # bilan d'avant le paquet : pas compté

    def test_adoption_directe_lue_dans_le_reglage(self):
        self.assertIn(('format_match', 'ATP'), FC.directs(RACINE))
        self.assertIn('format_match', FC.SIGNAUX)
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn(('format_match', 'ATP'), FC.directs(d))

    def test_regle_de_retrait_cumulee(self):
        self.assertFalse(FC.retrait_cumule({'matchs_total': 299, 'gain_total': -0.05, 'erreur_type_total': 0.001}))
        self.assertFalse(FC.retrait_cumule({'matchs_total': 500, 'gain_total': -0.004, 'erreur_type_total': 0.003}))
        self.assertTrue(FC.retrait_cumule({'matchs_total': 500, 'gain_total': -0.007, 'erreur_type_total': 0.003}))
        self.assertFalse(FC.retrait_cumule({'matchs_total': 500, 'gain_total': 0.002, 'erreur_type_total': 0.003}))
        self.assertFalse(FC.retrait_cumule({'matchs_total': 500, 'gain_total': None, 'erreur_type_total': None}))

    def _jouer(self, bilans, jour):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur', 'journal_pronostics', 'apres_match'))
            with open(os.path.join(d, 'simulateur', 'format_match.json'), 'w', encoding='utf-8') as f:
                json.dump({'pentes': {'ATP': {'2': 0.815}}}, f)
            with gzip.open(os.path.join(d, 'simulateur', 'journal_pronostics', 'apres_match', 'x.json.gz'), 'wt', encoding='utf-8') as f:
                json.dump({str(i): b for i, b in enumerate(bilans)}, f)
            ancien = os.environ.get('FANTOMES_JOUR')
            os.environ['FANTOMES_JOUR'] = jour
            try:
                FC.main(['fantomes_circuits.py', d])
            finally:
                if ancien is None:
                    os.environ.pop('FANTOMES_JOUR', None)
                else:
                    os.environ['FANTOMES_JOUR'] = ancien
            with open(os.path.join(d, 'simulateur', 'fantomes_circuits.json'), encoding='utf-8') as f:
                doc = json.load(f)
            return doc, FC.lire(d)

    def test_une_mauvaise_semaine_ne_retire_rien(self):
        """40 matchs, tous défavorables : sous 300 matchs, le signal reste (l'ancienne règle comptait une semaine « pire »)."""
        B = [bilan('ATP', '2026-11-1%d' % (2 + i % 4), 0.70, 0.60, str(i)) for i in range(40)]
        doc, lus = self._jouer(B, '2026-11-17')
        d = doc['decisions']['format_match|ATP']
        self.assertTrue(d['adopte'])
        self.assertTrue(d['direct'])
        self.assertIn('ATP', lus['format_match'])
        self.assertEqual(doc['semaine']['format_match|ATP']['matchs_total'], 40)

    def test_retire_quand_le_bilan_cumule_est_nettement_negatif(self):
        rnd = random.Random(9)
        B = [bilan('ATP', '2026-11-%02d' % (12 + i % 4), 0.65, 0.65 - 0.02 + rnd.gauss(0, 0.05), str(i)) for i in range(400)]
        doc, lus = self._jouer(B, '2026-11-17')
        d = doc['decisions']['format_match|ATP']
        self.assertFalse(d['adopte'])
        self.assertTrue(d['retire'])
        self.assertNotIn('ATP', lus.get('format_match', []))

    def test_garde_quand_le_bilan_cumule_est_positif(self):
        rnd = random.Random(10)
        B = [bilan('ATP', '2026-11-%02d' % (12 + i % 4), 0.65, 0.65 + 0.003 + rnd.gauss(0, 0.05), str(i)) for i in range(400)]
        doc, lus = self._jouer(B, '2026-11-17')
        self.assertTrue(doc['decisions']['format_match|ATP']['adopte'])
        self.assertIn('ATP', lus['format_match'])


class Page(unittest.TestCase):
    def test_libelle_du_signal_sur_la_page(self):
        with open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8') as f:
            page = f.read()
        self.assertIn('format_match:', page)
        self.assertIn('format du match', page)


if __name__ == '__main__':
    unittest.main()
