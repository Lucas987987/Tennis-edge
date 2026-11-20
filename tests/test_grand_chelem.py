# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 231) — pente Grand Chelem commune ATP + WTA : décision de Lucas, tableau principal seulement,
suivie « avec / sans » et retirée par la règle cumulée."""
import datetime as dt
import json
import math
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import apres_match as AM  # noqa: E402
import etude_grand_chelem as EG  # noqa: E402
import etude_outsiders as EO  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
lg = lambda p: math.log(p / (1 - p))
US = 'US Open Men Singles'


class Production(unittest.TestCase):
    def setUp(self):
        self._avant = (PJ.GRAND_CHELEM, PJ.FORMAT_MATCH, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT)
        PJ.GRAND_CHELEM = {'ATP': 1.235, 'WTA': 1.235}
        PJ.FORMAT_MATCH = {'ATP': {2: 0.826}}
        PJ.COMBINAISON = {'elo': 0.78, 'simulation': 0.24}
        PJ.SIGNAUX_CIRCUIT = {'grand_chelem': ['ATP', 'WTA'], 'format_match': ['ATP']}

    def tearDown(self):
        PJ.GRAND_CHELEM, PJ.FORMAT_MATCH, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT = self._avant

    def test_le_reglage_du_depot(self):
        self.assertEqual(PJ.charger_grand_chelem(RACINE), {'ATP': 1.235, 'WTA': 1.235})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(PJ.charger_grand_chelem(d), {})

    def test_le_favori_de_l_elo_est_renforce_sur_la_seule_part_de_l_elo(self):
        f = PJ.controle_grand_chelem(0.68, 0.70, 'ATP', US, 'Round of 64')
        self.assertAlmostEqual(f['decalage'], 0.78 * 0.235 * lg(0.70), places=4)
        self.assertAlmostEqual(f['p_home'], sg(lg(0.68) + f['decalage']), places=4)
        self.assertGreater(f['p_home'], 0.68)
        o = PJ.controle_grand_chelem(0.32, 0.30, 'WTA', 'US Open Women Singles', 'Final')
        self.assertAlmostEqual(o['decalage'], -f['decalage'], places=4)             # symétrique : l'outsider baisse d'autant

    def test_tableau_principal_seulement(self):
        for tour in ('Qualification Round 1', 'Qualification Final', 'Qualifications', None, ''):
            self.assertIsNone(PJ.controle_grand_chelem(0.68, 0.70, 'ATP', US, tour), tour)   # qualifications, ou tour inconnu

    def test_ni_hors_grand_chelem_ni_hors_des_deux_circuits(self):
        self.assertIsNone(PJ.controle_grand_chelem(0.68, 0.70, 'ATP', 'Paris Masters Men Singles', 'Round of 32'))
        self.assertIsNone(PJ.controle_grand_chelem(0.68, 0.70, 'CH', US, 'Round of 64'))
        self.assertIsNone(PJ.controle_grand_chelem(0.68, 0.50, 'ATP', US, 'Round of 64'))     # Elo à 50 % : rien à déplacer
        self.assertIsNone(PJ.controle_grand_chelem(None, 0.70, 'ATP', US, 'Round of 64'))

    def test_jamais_deux_pentes_sur_le_meme_match(self):
        """En ATP un Grand Chelem se joue en 3 sets gagnants : le format n'y a pas de pente, seule celle du Grand Chelem joue."""
        self.assertIsNone(PJ.controle_format(0.68, 0.70, 'ATP', 3))
        with open(os.path.join(RACINE, 'simulateur', 'format_match.json'), encoding='utf-8') as f:
            F = json.load(f)
        self.assertNotIn('3', F['pentes'].get('ATP') or {})
        self.assertEqual(F['en_attente'], {})
        self.assertIn('3', F['remplace']['ATP'])

    def test_applique_seulement_ou_il_est_adopte(self):
        f = PJ.controle_grand_chelem(0.68, 0.70, 'WTA', 'Wimbledon Women Singles', 'Round of 128')
        self.assertEqual(PJ.signaux_du_match('WTA', 0.68, None, None, None, None, gc_ctl=f), {'grand_chelem': f['decalage']})
        PJ.SIGNAUX_CIRCUIT = {'grand_chelem': ['ATP']}                                        # retiré en WTA
        self.assertEqual(PJ.signaux_du_match('WTA', 0.68, None, None, None, None, gc_ctl=f), {})


class Suivi(unittest.TestCase):
    def test_fantome_tant_que_le_signal_n_est_pas_applique(self):
        f = {'debut': '2027-01-18T10:00:00+00:00', 'circuit': 'ATP', 'home': 'A Un', 'away': 'B Deux',
             'dernier': {'p_home': 0.70, 'controle': {'grand_chelem': {'p_home': 0.72, 'decalage': 0.10}}}}
        e = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-3 6-3 6-3', 'sets': '3-0'})['ecarts']
        self.assertLess(e['fantome_grand_chelem']['ll_reference'], e['fantome_grand_chelem']['ll_elo'])

    def test_juge_sur_son_effet_propre_par_la_regle_cumulee(self):
        self.assertIn('grand_chelem', FC.SIGNAUX)
        self.assertIn('grand_chelem', FC.REGLE_CUMULEE)
        b = {'circuit': 'WTA', 'debut': '2027-01-18T12:00:00+00:00', 'home': 'A', 'away': 'B',
             'ecarts': {'signaux_circuit': {'appliques': ['age', 'grand_chelem'], 'll_affiche': 0.50, 'll_sans': 9.9,
                                            'sans_chacun': {'grand_chelem': 0.53, 'age': 5.5}}}}
        self.assertEqual(FC.paires(b, 'grand_chelem'), (0.53, 0.50))
        self.assertTrue(FC.retrait_cumule({'matchs_total': 300, 'gain_total': -0.02, 'erreur_type_total': 0.008}))
        self.assertFalse(FC.retrait_cumule({'matchs_total': 299, 'gain_total': -0.02, 'erreur_type_total': 0.008}))
        self.assertFalse(FC.retrait_cumule({'matchs_total': 400, 'gain_total': -0.01, 'erreur_type_total': 0.008}))

    def test_adoption_directe_lue_dans_le_reglage(self):
        d_ = FC.directs(RACINE)
        self.assertIn(('grand_chelem', 'ATP'), d_)
        self.assertIn(('grand_chelem', 'WTA'), d_)
        self.assertNotIn(('grand_chelem', 'CH'), d_)
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn(('grand_chelem', 'ATP'), FC.directs(d))

    def test_le_site_sait_nommer_le_signal(self):
        with open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8') as f:
            page = f.read()
        self.assertEqual(page.count('jc_f_fantome_grand_chelem:'), 2)                         # fr et en
        self.assertIn('grand_chelem:', page)
        with open(os.path.join(RACINE, 'simulateur', 'vitrine.py'), encoding='utf-8') as f:
            self.assertIn("'fantome_grand_chelem'", f.read())


class Etude(unittest.TestCase):
    def test_la_pente_vient_de_2018_2022_seulement(self):
        import random
        rnd, rows = random.Random(11), []
        for jour, vraie in ((dt.date(2020, 1, 20), 1.25), (dt.date(2024, 1, 20), 0.9)):   # la période vue ne doit pas compter
            for c in ('ATP', 'WTA'):
                for _ in range(4000):
                    z = rnd.gauss(0, 0.9)
                    rows.append({'zb': z if rnd.random() < sg(vraie * z) else -z, 'c': c, 'niveau': 'G', 'd': jour})
        for _ in range(3000):
            z = rnd.gauss(0, 0.9)
            rows.append({'zb': z if rnd.random() < sg(z) else -z, 'c': 'ATP', 'niveau': 'A', 'd': dt.date(2020, 3, 2)})
        for _ in range(3000):
            z = rnd.gauss(0, 0.9)
            rows.append({'zb': z if rnd.random() < sg(z) else -z, 'c': 'WTA', 'niveau': 'P', 'd': dt.date(2020, 3, 2)})
        d = EG.etudier(rows)
        self.assertAlmostEqual(d['pente_commune_apprise_sur_2018_2022'], 1.25, delta=0.07)
        self.assertEqual(d['2018–2022']['matchs'], 8000)
        self.assertLess(d['pour_memoire_2023_juin_2026']['ATP + WTA']['gain'], 0)             # publié tel quel, même s'il déplaît
        self.assertAlmostEqual(d['hors_grand_chelem_pente_propre_2018_2022']['ATP']['pente'], 1.0, delta=0.08)


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_grand_chelem.json'), encoding='utf-8') as f:
            cls.R = json.load(f)
        with open(os.path.join(RACINE, 'simulateur', 'grand_chelem.json'), encoding='utf-8') as f:
            cls.C = json.load(f)

    def test_public_avec_brier(self):
        for doc in (self.R, self.C):
            txt = json.dumps(doc, ensure_ascii=False).lower()
            for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
                self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['pour_memoire_2023_juin_2026']['ATP + WTA'])

    def test_c_est_dit_comme_une_decision_pas_comme_une_etude_qui_passe(self):
        self.assertIn('DÉCISION DE LUCAS', self.R['statut'])
        self.assertIn("n'est pas", self.R['statut'])
        self.assertIn('DÉCISION DE LUCAS', self.C['decision'])
        self.assertIn('pas une preuve', self.C['decision'])
        with open(os.path.join(RACINE, 'simulateur', 'rapport_outsiders.json'), encoding='utf-8') as f:
            self.assertFalse(json.load(f)['grand_chelem_wta']['retenue'])                     # la règle écrite reste « non passée »

    def test_la_pente_en_place_est_celle_du_rapport(self):
        k = self.R['pente_commune_apprise_sur_2018_2022']
        self.assertEqual(self.C['pentes'], {'ATP': k, 'WTA': k})
        self.assertEqual(self.R['production']['pentes'], self.C['pentes'])
        self.assertIn('300 matchs', self.C['retrait'])

    def test_le_controle_sur_nos_matchs_ne_pretend_pas_conclure(self):
        c = self.R['controle_nos_matchs']
        self.assertLess(c['matchs'], 1000)
        self.assertIn('trop peu', c['lecture'])


if __name__ == '__main__':
    unittest.main()
