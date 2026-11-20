# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 232) — qualifications de Grand Chelem : format corrigé chez les hommes (2 sets gagnants), pente de
l'Elo chez les femmes (étude retenue), rien chez les hommes (étude rejetée)."""
import datetime as dt
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
import etude_qualifs_grand_chelem as EQ  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
lg = lambda p: math.log(p / (1 - p))
HOMMES, FEMMES = 'US Open Men Singles', 'US Open Women Singles'


class Format(unittest.TestCase):
    def test_qualification_reconnue_par_le_tour(self):
        for tour in ('Qualification Round 1', 'Qualification Round 2', 'Qualification Final', 'Qualifications'):
            self.assertTrue(PJ.qualification_gc(HOMMES, tour), tour)
        for tour in ('Round of 128', 'Round of 64', 'Quarterfinals', 'Final', None, ''):
            self.assertFalse(PJ.qualification_gc(HOMMES, tour), tour)
        self.assertFalse(PJ.qualification_gc('Hersonissos 3, Greece', 'Qualification Final'))    # pas un Grand Chelem

    def test_les_qualifications_masculines_se_jouent_en_deux_sets_gagnants(self):
        self.assertEqual(PJ.sets_gagnants(HOMMES, 'Qualification Round 1'), 2)                 # la correction
        self.assertEqual(PJ.sets_gagnants('Wimbledon Men Singles', 'Qualification Final'), 2)
        self.assertEqual(PJ.sets_gagnants(HOMMES, 'Round of 128'), 3)
        self.assertEqual(PJ.sets_gagnants(HOMMES, None), 3)                                    # tour inconnu : comme avant
        self.assertEqual(PJ.sets_gagnants(FEMMES, 'Round of 128'), 2)
        self.assertEqual(PJ.sets_gagnants('Paris Masters Men Singles', 'Final'), 2)

    def test_la_boucle_des_pronostics_passe_par_la_et_ecarte_la_pente_du_format(self):
        with open(os.path.join(RACINE, 'simulateur', 'pronostics_du_jour.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn("sg = sets_gagnants(x['tournoi'], tour_)", src)
        self.assertNotIn("sg = 3 if NR.cinq_sets(x['tournoi']) else 2", src)
        self.assertIn("sg_fmt = None if qualification_gc(x['tournoi'], tour_) else sg", src)
        self.assertEqual(src.count('c, sg_fmt)'), 2)                                           # appliqué et fantôme
        self.assertIsNone(PJ.controle_format(0.68, 0.70, 'ATP', None))


class Production(unittest.TestCase):
    def setUp(self):
        self._avant = (PJ.QUALIFS_GC, PJ.GRAND_CHELEM, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT)
        PJ.QUALIFS_GC = {'WTA': 1.247}
        PJ.GRAND_CHELEM = {'ATP': 1.235, 'WTA': 1.235}
        PJ.COMBINAISON = {'elo': 0.78, 'simulation': 0.24}
        PJ.SIGNAUX_CIRCUIT = {'qualifs_grand_chelem': ['WTA'], 'grand_chelem': ['ATP', 'WTA']}

    def tearDown(self):
        PJ.QUALIFS_GC, PJ.GRAND_CHELEM, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT = self._avant

    def test_le_reglage_du_depot(self):
        self.assertEqual(PJ.charger_qualifs_gc(RACINE), {'WTA': 1.247})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(PJ.charger_qualifs_gc(d), {})

    def test_femmes_en_qualifications_seulement(self):
        f = PJ.controle_qualifs_gc(0.62, 0.64, 'WTA', FEMMES, 'Qualification Round 1')
        self.assertAlmostEqual(f['decalage'], 0.78 * 0.247 * lg(0.64), places=4)
        self.assertGreater(f['p_home'], 0.62)
        self.assertIsNone(PJ.controle_qualifs_gc(0.62, 0.64, 'WTA', FEMMES, 'Round of 128'))   # tableau principal
        self.assertIsNone(PJ.controle_qualifs_gc(0.62, 0.64, 'WTA', FEMMES, None))
        self.assertIsNone(PJ.controle_qualifs_gc(0.62, 0.64, 'ATP', HOMMES, 'Qualification Round 1'))   # hommes : rejeté
        self.assertIsNone(PJ.controle_qualifs_gc(0.62, 0.64, 'WTA', 'Linz Women Singles', 'Qualification Final'))

    def test_jamais_deux_pentes_sur_le_meme_match(self):
        for tour in ('Qualification Round 1', 'Round of 128'):
            a = PJ.controle_qualifs_gc(0.62, 0.64, 'WTA', FEMMES, tour)
            b = PJ.controle_grand_chelem(0.62, 0.64, 'WTA', FEMMES, tour)
            self.assertEqual((a is None) + (b is None), 1, tour)

    def test_applique_seulement_ou_il_est_adopte(self):
        f = PJ.controle_qualifs_gc(0.62, 0.64, 'WTA', FEMMES, 'Qualification Final')
        self.assertEqual(PJ.signaux_du_match('WTA', 0.62, None, None, None, None, qgc_ctl=f), {'qualifs_grand_chelem': f['decalage']})
        PJ.SIGNAUX_CIRCUIT = {}
        self.assertEqual(PJ.signaux_du_match('WTA', 0.62, None, None, None, None, qgc_ctl=f), {})


class Suivi(unittest.TestCase):
    def test_fantome_et_regle_cumulee(self):
        f = {'debut': '2027-01-11T10:00:00+00:00', 'circuit': 'WTA', 'home': 'A Un', 'away': 'B Deux',
             'dernier': {'p_home': 0.62, 'controle': {'qualifs_grand_chelem': {'p_home': 0.64, 'decalage': 0.09}}}}
        e = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-3 6-3', 'sets': '2-0'})['ecarts']
        self.assertLess(e['fantome_qualifs_grand_chelem']['ll_reference'], e['fantome_qualifs_grand_chelem']['ll_elo'])
        self.assertIn('qualifs_grand_chelem', FC.SIGNAUX)
        self.assertIn('qualifs_grand_chelem', FC.REGLE_CUMULEE)

    def test_adoption_directe_wta_seulement(self):
        d_ = FC.directs(RACINE)
        self.assertIn(('qualifs_grand_chelem', 'WTA'), d_)
        self.assertNotIn(('qualifs_grand_chelem', 'ATP'), d_)
        self.assertNotIn(('qualifs_grand_chelem', 'CH'), d_)

    def test_le_site_sait_nommer_le_signal(self):
        with open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8') as f:
            page = f.read()
        self.assertEqual(page.count('jc_f_fantome_qualifs_grand_chelem:'), 2)
        self.assertIn('qualifs_grand_chelem:', page)
        with open(os.path.join(RACINE, 'simulateur', 'vitrine.py'), encoding='utf-8') as f:
            self.assertIn("'fantome_qualifs_grand_chelem'", f.read())


class Etude(unittest.TestCase):
    def test_lignes_les_seules_qualifications_de_grand_chelem(self):
        j = dt.date(2019, 1, 8)
        m = lambda g, p, c, niv, ab=False: {'nom_g': g, 'nom_p': p, 'circuit': c, 'surface': 'Hard', 'date': j, 'bo': 3,
                                            'sets': [(6, 3), (6, 4)], 'complet': True, 'abandon': ab, 'niveau': niv}
        M = [m('Ana A', 'Bea B', 'ITF', 'G'), m('Cal C', 'Dan D', 'CH', 'G'), m('Cal C', 'Eli E', 'CH', 'C'),
             m('Fay F', 'Gil G', 'ATP', 'G'), m('Ana A', 'Hea H', 'ITF', 'G', ab=True), m('Ida I', 'Joy J', 'ITF', '')]
        self.assertEqual([r[0] for r in EQ.lignes(M, RACINE)], ['femmes', 'hommes'])

    def test_juger_suit_la_regle(self):
        rnd, rows = random.Random(4), []
        for jour in (dt.date(2020, 1, 14), dt.date(2024, 1, 9)):
            for groupe, vraie in (('femmes', 1.3), ('hommes', 1.0)):
                for _ in range(3000):
                    z = rnd.gauss(0, 0.8)
                    rows.append((groupe, jour, z if rnd.random() < sg(vraie * z) else -z))
        self.assertTrue(EQ.juger(rows, 'femmes')['retenue'])
        self.assertFalse(EQ.juger(rows, 'hommes')['retenue'])
        self.assertIn('moins de 1000 matchs jugés', EQ.juger(rows[:6000] + rows[6000:6500], 'femmes')['raisons'])

    def test_regle_ecrite_avant_et_elo_de_production(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_qualifs_grand_chelem.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('avant toute mesure', src)
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
        self.assertEqual((EQ.MIN_JUGES, EQ.MARGE, EQ.COUPURE), (1000, 0.001, dt.date(2023, 1, 1)))


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_qualifs_grand_chelem.json'), encoding='utf-8') as f:
            cls.R = json.load(f)
        with open(os.path.join(RACINE, 'simulateur', 'qualifs_grand_chelem.json'), encoding='utf-8') as f:
            cls.C = json.load(f)

    def test_public_avec_brier(self):
        for doc in (self.R, self.C):
            txt = json.dumps(doc, ensure_ascii=False).lower()
            for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
                self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['groupes']['femmes']['2023 → juin 2026'])

    def test_les_verdicts_suivent_la_regle(self):
        for g, v in self.R['groupes'].items():
            j = v['2023 → juin 2026']
            passe = (j['matchs'] >= 1000 and j['gain'] >= 0.001 and v['pente_sur_2023'] is not None
                     and (v['pente_sur_2023'] - 1) * (v['pente_apprise'] - 1) > 0)
            self.assertEqual(v['retenue'], passe, g)

    def test_rien_n_est_en_production_qui_n_ait_passe(self):
        attendu = {'WTA': self.R['groupes']['femmes']['pente_apprise']} if self.R['groupes']['femmes']['retenue'] else {}
        if self.R['groupes']['hommes']['retenue']:
            attendu['ATP'] = self.R['groupes']['hommes']['pente_apprise']
        self.assertEqual(self.C['pentes'], attendu)
        self.assertEqual(self.R['en_production'], {g: v['retenue'] for g, v in self.R['groupes'].items()})
        self.assertIn('300 matchs', self.C['retrait'])

    def test_l_ecart_entre_l_archive_et_nos_matchs_chez_les_hommes_est_dit(self):
        self.assertIn('à surveiller', self.R['controle_nos_matchs']['hommes']['lecture'])


if __name__ == '__main__':
    unittest.main()
