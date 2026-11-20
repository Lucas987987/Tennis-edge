# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 231) — départ des joueuses vues d'abord en ITF : étude jugée, rejetée, rien en production."""
import datetime as dt
import json
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import elo as E  # noqa: E402
import etude_depart_itf_femmes as EF  # noqa: E402


def match(g, p, jour, circuit, niveau='P', abandon=False):
    return {'nom_g': g, 'nom_p': p, 'circuit': circuit, 'surface': 'Hard', 'date': jour, 'bo': 3, 'sets': [(6, 3), (6, 4)],
            'complet': True, 'abandon': abandon, 'niveau': niveau}


class Etude(unittest.TestCase):
    def test_rejeu_le_depart_ne_touche_que_les_joueuses_vues_d_abord_en_itf(self):
        j = dt.date(2019, 2, 4)
        M = [match('Ana A', 'Bea B', j, 'ITF'), match('Cleo C', 'Dia D', j, 'WTA'),
             match('Cleo C', 'Ana A', j + dt.timedelta(days=7), 'WTA'), match('Cleo C', 'Dia D', j + dt.timedelta(days=8), 'WTA', abandon=True),
             match('Cleo C', 'Dia D', j + dt.timedelta(days=9), 'WTA', niveau='D'), match('Eli E', 'Fab F', j + dt.timedelta(days=9), 'CH')]
        base, bas = EF.rejouer(M, RACINE), EF.rejouer(M, RACINE, depart_itf=1000.0)
        self.assertEqual(len(base), 2)                                              # ni l'ITF, ni l'abandon, ni le niveau « D », ni les hommes
        self.assertEqual(base[0][1], bas[0][1])                                     # deux joueuses du circuit : inchangé
        self.assertGreater(bas[1][1], base[1][1])                                   # face à la joueuse venue de l'ITF : plus tranché

    def test_la_regle_est_celle_ecrite_au_paquet_230(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_depart_itf_femmes.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('AVANT TOUT ESSAI', src)
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
        self.assertEqual(EF.DEPARTS, (1150.0, 1100.0, 1050.0, 1000.0, 950.0))
        self.assertEqual((EF.MIN_JUGES, EF.MARGE, EF.COUPURE), (1000, 0.001, dt.date(2023, 1, 1)))
        with open(os.path.join(RACINE, 'simulateur', 'rapport_audit.json'), encoding='utf-8') as f:
            regles = [x for x in json.load(f)['paquet_230_le_11_11']['a_juger'] if x['id'] == 'depart_itf_femmes']
        self.assertIn('1150, 1100, 1050, 1000 ou 950', regles[0]['regle'])


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_depart_itf_femmes.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_public_avec_brier(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['2023 → juin 2026'])

    def test_la_forme_a_ete_choisie_sur_2018_2022(self):
        c = self.R['candidats_2018_2022']
        self.assertEqual(self.R['forme_choisie'], max(c, key=lambda n: c[n]['2018–2022']['gain']))

    def test_rien_n_est_en_production_qui_n_ait_passe(self):
        j = self.R['2023 → juin 2026']
        self.assertEqual(self.R['retenue'], j['matchs'] >= 1000 and j['gain'] >= 0.001
                         and self.R['candidats_2018_2022'][self.R['forme_choisie']]['2018–2022']['gain'] > 0)
        if not self.R['retenue']:
            self.assertFalse(self.R['en_production'])
            self.assertNotIn('ITF', E.DEPARTS_PAR_NIVEAU)                           # les joueuses gardent leur départ à 1200


if __name__ == '__main__':
    unittest.main()
