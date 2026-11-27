"""Paquet 503 : un Elo qui oublie plus vite — O1 (plancher) égal à E2 quand N est très grand, O2 (temps) qui remonte K
après une absence, règle de jugement sur un monde factice dont les forces dérivent (retenu) puis sur un monde stable
(non retenu), ligues hors produit jamais retenues, rapport et journal sans nom ni identifiant."""
import contextlib
import datetime as dt
import io
import json
import math
import os
import random
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402
import etude_oubli_tt as EO  # noqa: E402
from test_elo_tt import ecrire_monde  # noqa: E402

E2 = [400, 0.6, 0.5, 20]


def monde(derive, jours=730, par_jour=24, joueurs=16, seed=5):
    """Matchs factices au format de ET.matchs(). derive > 0 : la force de chaque joueur ondule dans le temps (forme
    qui change) ; derive = 0 : forces fixes. Deux ligues qui ne se mélangent pas : Poland (produit) et Czech Republic."""
    rng = random.Random(seed)
    ids = [900001 + i for i in range(2 * joueurs)]
    base = {i: rng.gauss(0, 0.8) for i in ids}
    phase = {i: rng.uniform(0, 2 * math.pi) for i in ids}
    duree = {i: rng.uniform(120, 260) for i in ids}
    debut = dt.date(2024, 1, 1)
    M = []
    for k in range(jours):
        d = debut + dt.timedelta(days=k)
        t0 = int(dt.datetime(d.year, d.month, d.day, 8, tzinfo=dt.timezone.utc).timestamp())
        for j in range(par_jour):
            pl = j % 3 != 2                                   # 2 matchs sur 3 en Pologne
            h, a = rng.sample(ids[:joueurs] if pl else ids[joueurs:], 2)
            fh = base[h] + derive * math.sin(2 * math.pi * k / duree[h] + phase[h])
            fa = base[a] + derive * math.sin(2 * math.pi * k / duree[a] + phase[a])
            p = 1 / (1 + math.exp(-(fh - fa)))
            y = 1 if rng.random() < p else 0
            part = min(max(0.5 + 0.04 * (fh - fa) + rng.gauss(0, 0.03), 0.3), 0.7)
            k_perdant = rng.randrange(3)
            M.append((t0 + 600 * j, d.isoformat(), 'Poland' if pl else 'Czech Republic', h, a, y, part, 3,
                      (3, k_perdant) if y else (k_perdant, 3)))
    M.sort(key=lambda x: (x[0], x[3], x[4]))
    return M


class Rejeu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.M = monde(1.0, jours=60)

    def test_plancher_tres_grand_egale_e2(self):
        a, c, w, s = E2
        self.assertEqual(EO.rejouer_oubli(self.M, a, c, w, s, plafond=10 ** 9), ET.rejouer(self.M, a=a, c=c, w=w, s=s))
        self.assertEqual(EO.rejouer_oubli(self.M, a, c, w, s), ET.rejouer(self.M, a=a, c=c, w=w, s=s))
        self.assertEqual(EO.rejouer_oubli(self.M, a, c), ET.rejouer(self.M, a=a, c=c))

    def test_plancher_change_l_elo(self):
        a, c, w, s = E2
        self.assertNotEqual(EO.rejouer_oubli(self.M, a, c, w, s, plafond=5), ET.rejouer(self.M, a=a, c=c, w=w, s=s))

    def test_plancher_k_minimum(self):
        # 3 matchs entre les mêmes joueurs, plafond 0 : K reste a / 5^c ; le 3e % se calcule à la main
        M = [(i * 600, '2024-01-01', 'X', 1, 2, 1, 0.5, 3, (3, 0)) for i in range(3)]
        P = EO.rejouer_oubli(M, 100, 1.0, plafond=0)
        k = 100 / 5
        r = 0.5 * k
        r2 = r + k * (1 - ET.proba(1500 + r, 1500 - r))
        self.assertAlmostEqual(P[2], ET.proba(1500 + r2, 1500 - r2))
        self.assertLess(ET.rejouer(M, a=100, c=1.0)[2], P[2])     # sans plafond, K baisse : l'Elo monte moins

    def test_temps_oublie_apres_une_absence(self):
        j = 86400
        avant = [(i * 600, '2024-01-01', 'X', 1, 2, 1, 0.5, 3, (3, 0)) for i in range(20)]
        vite = avant + [(20 * 600, '2024-01-01', 'X', 1, 2, 0, 0.5, 3, (0, 3)), (21 * 600, '2024-01-01', 'X', 1, 2, 1, 0.5, 3, (3, 0))]
        tard = avant + [(400 * j, '2025-02-04', 'X', 1, 2, 0, 0.5, 3, (0, 3)), (400 * j + 600, '2025-02-04', 'X', 1, 2, 1, 0.5, 3, (3, 0))]
        pv, pt = EO.rejouer_oubli(vite, 400, 0.6, demi_vie=30), EO.rejouer_oubli(tard, 400, 0.6, demi_vie=30)
        self.assertAlmostEqual(pv[20], pt[20])                       # même % avant la défaite surprise
        self.assertLess(pt[21], pv[21])                              # après 400 jours d'absence, K est remonté
        # sans absence (matchs à 10 minutes), O2 reste tout près de E2
        self.assertAlmostEqual(pv[21], ET.rejouer(vite, a=400, c=0.6)[21], places=2)
        # heures de début absentes (t = 0) : jamais d'écart négatif, O2 = E2
        Z = [(0,) + m[1:] for m in avant]
        self.assertEqual(EO.rejouer_oubli(Z, 400, 0.6, demi_vie=30), ET.rejouer(Z, a=400, c=0.6))

    def test_pentes(self):
        M = [(0, '2024-01-01', 'Poland', 1, 2, 1, 0.5, 3, (3, 0)), (0, '2024-01-01', 'X', 1, 2, 1, 0.5, 3, (3, 0))]
        P = EO.avec_pentes(M, [0.7, 0.7], {'Poland': 1.25})
        self.assertGreater(P[0], 0.7)
        self.assertEqual(P[1], 0.7)

    def test_comparer(self):
        c = EO.comparer([0.5, 0.5, 0.5, 0.5], [0.6, 0.6, 0.4, 0.4], [1, 1, 0, 0], [0, 1, 2, 3])
        self.assertEqual(c['matchs'], 4)
        self.assertAlmostEqual(c['gain'], round(math.log(0.6 / 0.5), 5))
        self.assertEqual(c['erreur_type'], 0.0)
        self.assertEqual(EO.comparer([], [], [], []), {'matchs': 0})


class Etude(unittest.TestCase):
    def test_forces_qui_derivent_retenu(self):
        lignes = []
        M = monde(1.2)
        rep = EO.etudier(M, E2, {'Poland': 1.1}, lignes.append)
        self.assertEqual(rep['paquet'], 503)
        self.assertIn(rep['candidat']['famille'], ('O1', 'O2'))
        self.assertIn(rep['candidat']['reglage'], EO.GRILLE_O1 + EO.GRILLE_O2)
        self.assertEqual(len(rep['log_loss_apprentissage']), len(EO.GRILLE_O1) + len(EO.GRILLE_O2) + 1)
        po = rep['par_ligue']['Poland']
        self.assertTrue(po['produit'])
        self.assertGreaterEqual(po['matchs'], 1000)
        self.assertGreaterEqual(po['gain'], 0.001)
        self.assertGreaterEqual(po['gain'], 2 * po['erreur_type'])
        self.assertGreater(po['gain_apprentissage'], 0)
        self.assertTrue(po['retenu'])
        self.assertAlmostEqual(po['log_loss_temoin'] - po['log_loss_candidat'], po['gain'], places=4)
        self.assertIn('pente_etalonnage_temoin', po)
        self.assertIn('pente_etalonnage_candidat', po)
        self.assertEqual(rep['ligues_retenues'], ['Poland'])
        self.assertEqual(rep['verdict'], 'candidat_retenu')
        # ligue hors produit : décrite, jamais retenue ; ligue du produit sans match : non retenue
        cz = rep['par_ligue']['Czech Republic']
        self.assertFalse(cz['produit'])
        self.assertFalse(cz['retenu'])
        self.assertGreater(cz['matchs'], 0)
        self.assertEqual(rep['par_ligue']['International']['matchs'], 0)
        self.assertFalse(rep['par_ligue']['International']['retenu'])
        # ni nom ni identifiant de joueur dans le rapport ou le journal
        texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(lignes)
        self.assertNotIn('Joueur', texte)
        self.assertNotIn('9000', texte)
        self.assertTrue(any('RETENU' in x for x in lignes))

    def test_monde_stable_non_retenu(self):
        rep = EO.etudier(monde(0.0), E2, {}, lambda x: None)
        po = rep['par_ligue']['Poland']
        self.assertFalse(po['retenu'])
        self.assertLess(po['gain'], 0.001)
        self.assertEqual(rep['ligues_retenues'], [])
        self.assertEqual(rep['verdict'], 'candidat_non_retenu')

    def test_pas_assez(self):
        rep = EO.etudier(monde(1.0, jours=30), E2, {}, lambda x: None)
        self.assertEqual(rep['verdict'], 'donnees_insuffisantes')


class Principal(unittest.TestCase):
    def test_main_ecrit_le_rapport_ailleurs_que_dans_le_depot(self):
        d = tempfile.mkdtemp()
        try:
            ecrire_monde(d, jours=20)
            sortie = os.path.join(d, 'rapport_oubli_tt.json')
            with mock.patch.object(EO, 'SORTIE', sortie), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(EO.main(['x', d]), 0)
            with open(sortie, encoding='utf-8') as f:
                brut = f.read()
            self.assertEqual(json.loads(brut)['verdict'], 'donnees_insuffisantes')
            self.assertNotIn('Joueur', brut)
        finally:
            shutil.rmtree(d)

    def test_regle_ecrite_dans_l_en_tete(self):
        doc = EO.__doc__
        for mot in ('AVANT TOUT ESSAI', 'plancher', 'temps', '0,001', '2 erreurs types', '1 000', 'même sens'):
            self.assertIn(mot, doc)
        self.assertEqual((EO.PAQUET, EO.MIN_JUGES, EO.MARGE, EO.ERREURS_TYPES), (503, 1000, 0.001, 2.0))
        self.assertEqual((EO.GRILLE_O1, EO.GRILLE_O2), ([50, 100, 200, 400, 800], [30, 90, 180, 365]))
        self.assertEqual(EO.LIGUES_PRODUIT, ('International', 'Poland'))


if __name__ == '__main__':
    unittest.main()
