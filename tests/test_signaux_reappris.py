# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 233) — signaux par circuit réappris sur l'Elo de production : l'étude, ce qu'elle garde, ce
qu'elle écarte, et ce que les pronostics lisent."""
import datetime as dt
import json
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_outsiders as EO  # noqa: E402
import etude_signaux_reappris as ER  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402


def lignes_synthetiques(vrais, n=6000, graine=3, concernes_absence=1.0):
    """Lignes vues du vainqueur ; `vrais` : les sept β qui ont produit les résultats."""
    rnd, rows = random.Random(graine), []
    for jour in (dt.date(2020, 3, 2), dt.date(2024, 3, 4)):
        for _ in range(n):
            z = rnd.gauss(0, 0.8)
            x = [float(rnd.choice((-1, 0, 0, 1))), 0.0, 0.0, rnd.gauss(0, 3), rnd.gauss(0, 2), rnd.gauss(0, 0.05), float(rnd.choice((-2, -1, 0, 0, 1, 2)))]
            if rnd.random() < 0.15 * concernes_absence:
                x[rnd.choice((1, 1, 2))] = float(rnd.choice((-1, 1)))      # absence courte, plus rarement longue
            za = z + sum(b * v for b, v in zip(vrais, x))
            if rnd.random() < EO._sg(za):
                rows.append({'d': jour, 'c': 'ATP', 'z': z, 'x': tuple(x), 'role_en_place': x[5]})
            else:
                rows.append({'d': jour, 'c': 'ATP', 'z': -z, 'x': tuple(-v for v in x), 'role_en_place': -x[5]})
    return rows


class Regle(unittest.TestCase):
    def test_un_signal_vrai_reste_un_signal_vide_part(self):
        vrais = [-0.5, -0.9, -1.3, -0.08, 0.0, 0.0, 0.0]           # surface, absence, âge (vieux) ; rien d'autre
        en_place = [-0.3, -0.5, -0.5, -0.05, 0.05, 1.5, 0.12]      # la configuration actuelle applique tout
        v = ER.juger_circuit(lignes_synthetiques(vrais, n=9000), en_place)     # ≈ 1 350 matchs concernés par l'absence
        self.assertIn('changement_surface', v['signaux_gardes'])
        self.assertIn('retour_absence', v['signaux_gardes'])
        self.assertNotIn('favori_outsider', v['signaux_gardes'])
        self.assertNotIn('parcours_tournoi', v['signaux_gardes'])
        self.assertEqual(set(v['signaux_ecartes']), set(ER.SIGNAUX) - set(v['signaux_gardes']) - set(v['signaux_en_sursis']))
        self.assertNotIn('favori_outsider', v['betas'])
        self.assertNotIn('parcours_tournoi', v['betas'])
        self.assertAlmostEqual(v['betas']['changement_surface'], -0.5, delta=0.12)
        self.assertGreater(v['contre_la_configuration_en_place_2023']['gain'], 0)
        self.assertTrue(v['adopte'])

    def test_sursis_un_signal_en_place_qui_n_echoue_que_sur_le_nombre(self):
        vrais = [-0.5, -1.2, -1.6, 0.0, 0.0, 0.0, 0.0]
        en_place = [-0.3, -0.5, -0.5, 0.0, 0.0, 0.0, 0.0]
        v = ER.juger_circuit(lignes_synthetiques(vrais, concernes_absence=0.6), en_place)    # ≈ 540 matchs concernés par l'absence
        s = v['signaux']['retour_absence']
        self.assertLess(s['cout_du_retrait_2023']['concernes'], 1000)
        self.assertFalse(s['garde'])
        self.assertTrue(s['en_sursis'])
        self.assertIn('retour_absence_court', v['betas'])
        pas_en_place = ER.juger_circuit(lignes_synthetiques(vrais, concernes_absence=0.6), [-0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertFalse(pas_en_place['signaux']['retour_absence']['en_sursis'])              # le sursis ne fait rien ENTRER

    def test_la_configuration_reapprise_ne_remplace_pas_si_elle_fait_moins_bien(self):
        vrais = [-0.5, -0.9, -1.3, -0.08, 0.0, 0.0, 0.0]
        rows = lignes_synthetiques(vrais)
        for r in rows:                                             # la période jugée contredit l'apprentissage
            if r['d'] >= ER.COUPURE:
                r['x'] = tuple(-v for v in r['x'])
        v = ER.juger_circuit(rows, [0.5, 0.9, 1.3, 0.08, 0.0, 0.0, 0.0])      # la configuration en place y est la bonne
        self.assertEqual(v['signaux_gardes'], [])
        self.assertLess(v['contre_la_configuration_en_place_2023']['gain'], 0)
        self.assertFalse(v['adopte'])

    def test_pente_du_match(self):
        fmt, gc = {'ATP': {2: 0.826}}, {'ATP': 1.235, 'WTA': 1.235}
        self.assertEqual(ER.pente_du_match({'circuit': 'ATP', 'bo': 3, 'niveau': 'M'}, fmt, gc), 0.826)
        self.assertEqual(ER.pente_du_match({'circuit': 'ATP', 'bo': 5, 'niveau': 'G'}, fmt, gc), 1.235)
        self.assertEqual(ER.pente_du_match({'circuit': 'WTA', 'bo': 3, 'niveau': 'G'}, fmt, gc), 1.235)
        self.assertEqual(ER.pente_du_match({'circuit': 'WTA', 'bo': 3, 'niveau': 'P'}, fmt, gc), 1.0)
        self.assertEqual(ER.pente_du_match({'circuit': 'CH', 'bo': 3, 'niveau': 'G'}, fmt, gc), 1.0)      # qualifications : rien

    def test_la_regle_est_ecrite_avant_et_l_elo_est_celui_de_production(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_signaux_reappris.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('AVANT DE LANCER', src)
        self.assertIn('ÉCART À LA RÈGLE', src)                     # l'écart décidé après coup est dit dans le code
        self.assertIn('E.de_production(racine)', src)
        self.assertIn("m.get('niveau') != 'D'", src)
        self.assertEqual((ER.MIN_CONCERNES, ER.MARGE, ER.COUPURE), (1000, 0.001, dt.date(2023, 1, 1)))
        self.assertEqual(len(ER.NOMS), 7)


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_signaux_reappris.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_public_avec_brier(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['circuits']['ATP']['contre_la_configuration_en_place_2023'])

    def test_les_verdicts_suivent_la_regle(self):
        for c, v in self.R['circuits'].items():
            for nom, s in v['signaux'].items():
                j = s['cout_du_retrait_2023']
                signes = all(a * b > 0 for a, b in zip(s['betas_2018_2022'].values(), s['betas_2023'].values()))
                passe = (j['concernes'] >= 1000 and j['gain'] >= 0.001 and s['cout_du_retrait_2018_2022']['gain'] > 0 and signes)
                self.assertEqual(s['garde'], passe, (c, nom))
                if s['en_sursis']:
                    self.assertEqual(s['raisons'], ['moins de 1000 matchs concernés'], (c, nom))
                    self.assertGreaterEqual(j['erreurs_types'], 2.0, (c, nom))
                    self.assertIn(nom.split('_')[0], ' '.join(v['betas_en_place']), (c, nom))
            self.assertEqual(v['adopte'], v['contre_la_configuration_en_place_2023']['gain'] >= 0, c)
            self.assertEqual(set(v['betas']), {ER.NOMS[i] for n in v['signaux_gardes'] + v['signaux_en_sursis'] for i in ER.SIGNAUX[n]}, c)

    def test_le_favori_outsider_et_le_parcours_ne_tiennent_nulle_part_contre_l_elo_de_production(self):
        for c, v in self.R['circuits'].items():
            for nom in ('favori_outsider', 'parcours_tournoi'):
                self.assertFalse(v['signaux'][nom]['garde'], (c, nom))
                self.assertFalse(v['signaux'][nom]['en_sursis'], (c, nom))


class Production(unittest.TestCase):
    def test_les_pronostics_lisent_les_betas_reappris_la_ou_ils_sont_adoptes(self):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_signaux_reappris.json'), encoding='utf-8') as f:
            R = json.load(f)['circuits']
        B = PJ.charger_betas_combines(RACINE)
        for c, v in R.items():
            if v['adopte']:
                self.assertEqual(B[c], v['betas'], c)
                self.assertNotIn('favori_outsider', B[c])
                self.assertNotIn('parcours_tournoi', B[c])
            else:
                self.assertEqual(set(B[c]), set(v['betas_en_place']), c)    # circuit inchangé : la configuration d'avant

    def test_un_signal_ecarte_n_est_plus_applique_et_ne_peut_pas_revenir(self):
        places, ecartes = FC.reappris(RACINE)
        self.assertTrue(ecartes)
        D, L = FC.directs(RACINE), FC.lire(RACINE)
        for s, c in ecartes:
            self.assertNotIn((s, c), D)
            self.assertNotIn(c, L.get(s, []), (s, c))
        for s, c in places:
            self.assertIn((s, c), D)
        with tempfile.TemporaryDirectory() as d:                   # même avec une ancienne décision « adopté » sur le disque
            os.makedirs(os.path.join(d, 'simulateur'))
            with open(os.path.join(d, 'simulateur', 'rapport_signaux_reappris.json'), 'w', encoding='utf-8') as f:
                json.dump({'circuits': {'ATP': {'adopte': True, 'signaux_gardes': ['age'], 'signaux_en_sursis': [],
                                                'signaux_ecartes': ['favori_outsider']},
                                        'WTA': {'adopte': False, 'signaux_gardes': [], 'signaux_ecartes': ['age']}}}, f)
            with open(os.path.join(d, FC.SORTIE), 'w', encoding='utf-8') as f:
                json.dump({'decisions': {'favori_outsider|ATP': {'adopte': True, 'direct': True}, 'age|WTA': {'adopte': True}}}, f)
            L = FC.lire(d)
            self.assertNotIn('ATP', L.get('favori_outsider', []))
            self.assertIn('ATP', L['age'])
            self.assertIn('WTA', L['age'])                         # circuit non adopté : rien n'y est écarté

    def test_sans_rapport_rien_ne_change(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(FC.reappris(d), (set(), set()))
            self.assertEqual(PJ.charger_betas_combines(d), {})


if __name__ == '__main__':
    unittest.main()
