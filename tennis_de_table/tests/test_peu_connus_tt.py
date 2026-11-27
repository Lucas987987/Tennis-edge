"""Paquet 503 : joueurs peu connus au tennis de table — bornes des classes, compteur n_min, monde factice où le % des
nouveaux est mal étalonné (classe signalée, correction retenue), monde où il est juste (rien de signalé, rien de retenu),
ligue hors produit jamais retenue, rapport et journal sans nom."""
import datetime as dt
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402
import etude_peu_connus_tt as PC  # noqa: E402
from test_elo_tt import ecrire_monde  # noqa: E402

REGLAGE = [12, 0.0, 0.0, 20]          # K fixe de 12, sans marge : Elo simple, peu bruité


def monde(nouveaux_au_hasard, ligue='International', jours=730, seed=6):
    """Matchs factices en mémoire (tuples de ET.matchs). 40 habitués de force fixe ; chaque jour un nouveau joueur
    arrive, joue 8 matchs contre des habitués puis disparaît. nouveaux_au_hasard : ses matchs sont des pile ou face
    (le % annoncé ne vaut rien) ; sinon il a exactement la force de départ de l'Elo (le % est juste)."""
    rng = random.Random(seed)
    force = {i: rng.gauss(0, 150) for i in range(1, 41)}
    debut = dt.date(2024, 1, 1)
    M = []
    for k in range(jours):
        d = debut + dt.timedelta(days=k)
        t0 = int(dt.datetime(d.year, d.month, d.day, 8, tzinfo=dt.timezone.utc).timestamp())
        paires = [tuple(rng.sample(range(1, 41), 2)) for _ in range(12)]
        nouveau = 1000 + k
        for _ in range(8):
            h = rng.randrange(1, 41)
            paires.append((h, nouveau) if rng.random() < 0.5 else (nouveau, h))
        for j, (h, a) in enumerate(paires):
            if nouveaux_au_hasard and max(h, a) >= 1000:
                p = 0.5
            else:
                p = ET.proba(force.get(h, 0.0), force.get(a, 0.0))
            y = 1 if rng.random() < p else 0
            M.append((t0 + 60 * j, d.isoformat(), ligue, f'Joueur {h}', f'Joueur {a}', y, 0.55 if y else 0.45, 3,
                      (3, 1) if y else (1, 3)))
    return M


class Classes(unittest.TestCase):
    def test_bornes(self):
        self.assertEqual([PC.classe(n) for n in (0, 9, 10, 29, 30, 99, 100, 5000)], [0, 0, 1, 1, 2, 2, 3, 3])
        self.assertEqual(len(PC.CLASSES), 4)

    def test_compteur_n_min(self):
        M = [(i, '2025-10-02', 'X', 'a', 'b', 1, 0.6, 3, (3, 0)) for i in range(3)]
        M.append((3, '2025-10-02', 'X', 'a', 'c', 1, 0.6, 3, (3, 0)))
        M.append((4, '2025-10-02', 'X', 'c', 'b', 1, 0.6, 3, (3, 0)))
        self.assertEqual(PC.compteurs(M), [0, 1, 2, 0, 1])
        etat = {}
        ET.rejouer(M, a=400, c=0.6, etat=etat)          # même compteur que l'Elo de production
        self.assertEqual(etat['N'], {'a': 4, 'b': 4, 'c': 2})

    def test_moins_fiable(self):
        self.assertTrue(PC.moins_fiable(300, 0.5, 0.7))
        self.assertTrue(PC.moins_fiable(300, 1.3, 1.2))
        self.assertFalse(PC.moins_fiable(299, 0.5, 0.7))          # trop peu de matchs jugés
        self.assertFalse(PC.moins_fiable(5000, 0.5, 1.3))         # pas du même côté
        self.assertFalse(PC.moins_fiable(5000, 0.5, 0.9))         # une seule période hors bande
        self.assertFalse(PC.moins_fiable(5000, None, 0.5))        # pente d'apprentissage non calculée
        self.assertFalse(PC.moins_fiable(5000, 0.85, 1.15))       # bornes incluses dans la bande

    def test_temoin_applique_la_pente_de_la_ligue(self):
        M = [(i, '2025-10-02', 'International' if i % 2 else 'Poland', 'a', 'b', 1, 0.6, 3, (3, 0)) for i in range(6)]
        P0, P1 = PC.temoin(M, REGLAGE, {}), PC.temoin(M, REGLAGE, {'International': 1.5})
        self.assertEqual(P0[4], P1[4])
        self.assertGreater(P1[5], P0[5])                # favori (> 50 %) renforcé par une pente > 1


def tirage(pente_nouveaux, pente_autres=1.0, n=6000, seed=11):
    """Témoin et résultats fabriqués à la main pour juger la règle seule : un match sur trois est dans la classe
    « moins de 10 », où la vraie probabilité est σ(pente_nouveaux · logit p) ; ailleurs σ(pente_autres · logit p)."""
    rng = random.Random(seed)
    M, P, NMIN = [], [], []
    for i in range(n):
        p = min(max(rng.gauss(0.5, 0.17), 0.05), 0.95)
        nouveau = i % 3 == 0
        vrai = PC.E3._sg(pente_nouveaux * PC.E3._lg(p)) if nouveau else PC.E3._sg(pente_autres * PC.E3._lg(p))
        y = 1 if rng.random() < vrai else 0
        M.append((i, '', 'Poland', f'Joueur {i}', 'Joueur 0', y, 0.5, 3, (3, 1) if y else (1, 3)))
        P.append(p)
        NMIN.append(3 if nouveau else 250)
    return M, P, NMIN, list(range(0, n, 2)), list(range(1, n, 2))


class Regle(unittest.TestCase):
    def test_classe_mal_etalonnee_signalee_et_corrigee(self):
        lignes = []
        v = PC.analyser(*tirage(0.4, 1.12, seed=14), lignes.append)['Poland']
        self.assertEqual(v['classes_moins_fiables'], ['moins de 10'])          # elle seule
        self.assertTrue(v['avertissement_permis'])
        r = v['Q2_correction']
        self.assertAlmostEqual(r['pentes_apprises']['moins de 10'], 0.4, delta=0.15)
        self.assertGreater(r['pentes_apprises']['100 et plus'], 1.0)
        self.assertGreater(r['pentes_sens_inverse']['100 et plus'], 1.0)
        self.assertEqual(r['classes_comparables'], ['moins de 10', '100 et plus'])
        self.assertEqual(r['pentes_apprises']['30 à 99'], 1.0)
        self.assertTrue(r['regle_remplie'] and r['retenu'])
        self.assertNotIn('Joueur', json.dumps(v, ensure_ascii=False) + '\n'.join(lignes))

    def test_classe_deja_juste_ne_bloque_pas(self):
        # précision du 27/11 : la classe « 100 et plus », bien étalonnée, change de côté de 1 par simple bruit ; elle
        # ne compte pas dans le sens (pente apprise à moins de 0,05 de 1) et ne bloque plus le vrai gain
        r = PC.analyser(*tirage(0.4), lambda x: None)['Poland']['Q2_correction']
        self.assertGreaterEqual(r['gain'], max(0.001, 2 * r['erreur_type']))
        self.assertGreater(r['sens_inverse'], 0)
        a, b = r['pentes_apprises']['100 et plus'], r['pentes_sens_inverse']['100 et plus']
        self.assertLess((a - 1) * (b - 1), 0)
        self.assertLess(abs(a - 1), PC.ECART_SENS)
        self.assertEqual(r['classes_comparables'], ['moins de 10'])
        self.assertTrue(r['pentes_du_meme_cote'] and r['retenu'])

    def test_classe_juste_ni_signalee_ni_corrigee(self):
        v = PC.analyser(*tirage(1.0), lambda x: None)['Poland']
        self.assertEqual(v['classes_moins_fiables'], [])
        self.assertFalse(v['avertissement_permis'])
        self.assertFalse(v['Q2_correction']['retenu'])

    def test_trop_peu_de_matchs_juges(self):
        M, P, NMIN, A, B = tirage(0.4)
        v = PC.analyser(M, P, NMIN, A, B[:900], lambda x: None)['Poland']          # 900 jugés dont 300 nouveaux
        self.assertEqual(v['classes_moins_fiables'], ['moins de 10'])
        self.assertFalse(v['Q2_correction']['retenu'])                             # moins de 1 000 matchs jugés
        v = PC.analyser(M, P, NMIN, A, B[:600], lambda x: None)['Poland']          # 200 nouveaux jugés seulement
        self.assertEqual(v['classes_moins_fiables'], [])
        self.assertEqual(v['Q2_correction']['classes_comparables'], [])            # « 100 et plus » déjà juste
        self.assertFalse(v['Q2_correction']['retenu'])


class Etude(unittest.TestCase):
    def test_nouveaux_mal_etalonnes(self):
        lignes = []
        rep = PC.etudier(monde(True), REGLAGE, {}, lignes.append)
        v = rep['par_ligue']['International']
        self.assertTrue(v['produit'])
        q1 = v['Q1_par_classe']
        self.assertGreaterEqual(q1['moins de 10']['jugement']['matchs'], 300)
        self.assertTrue(q1['moins de 10']['moins_fiable'])
        self.assertLess(q1['moins de 10']['jugement']['pente_etalonnage'], 0.85)
        self.assertIn('moins de 10', v['classes_moins_fiables'])
        self.assertIn('moins de 10', rep['avertissement_permis']['International'])
        self.assertTrue(v['avertissement_permis'])
        r = v['Q2_correction']
        self.assertLess(r['pentes_apprises']['moins de 10'], 0.5)
        self.assertEqual(r['pentes_apprises']['10 à 29'], 1.0)          # classe presque vide : pente 1
        self.assertGreaterEqual(r['gain'], 0.001)
        self.assertGreaterEqual(r['gain'], 2 * r['erreur_type'])
        self.assertGreater(r['sens_inverse'], 0)
        self.assertIn('moins de 10', r['classes_comparables'])
        self.assertTrue(r['pentes_du_meme_cote'])
        self.assertTrue(r['retenu'])
        self.assertEqual(rep['retenu'], {'International': True})
        self.assertAlmostEqual(r['log_loss_temoin'] - r['log_loss_candidat'], r['gain'], places=4)
        texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(lignes)
        self.assertNotIn('Joueur', texte)                # aucun nom, aucun identifiant
        self.assertEqual(rep['paquet'], 503)

    def test_nouveaux_bien_etalonnes(self):
        rep = PC.etudier(monde(False), REGLAGE, {}, lambda x: None)
        v = rep['par_ligue']['International']
        self.assertGreaterEqual(v['Q1_par_classe']['moins de 10']['jugement']['matchs'], 300)
        self.assertEqual(v['classes_moins_fiables'], [])
        self.assertFalse(v['avertissement_permis'])
        self.assertFalse(v['Q2_correction']['retenu'])
        self.assertEqual(rep['retenu'], {'International': False})

    def test_ligue_hors_produit_jamais_retenue(self):
        rep = PC.etudier(monde(True, ligue='Czech Republic'), REGLAGE, {}, lambda x: None)
        v = rep['par_ligue']['Czech Republic']
        self.assertFalse(v['produit'])
        self.assertTrue(v['Q2_correction']['regle_remplie'])          # décrit…
        self.assertFalse(v['Q2_correction']['retenu'])                # … mais jamais retenu
        self.assertFalse(v['avertissement_permis'])
        self.assertEqual(rep['retenu'], {})

    def test_pas_assez(self):
        rep = PC.etudier(monde(True, jours=100), REGLAGE, {}, lambda x: None)
        self.assertEqual(rep['verdict'], 'donnees_insuffisantes')


class Principal(unittest.TestCase):
    def test_main_ecrit_le_rapport_a_cote(self):
        d = tempfile.mkdtemp()
        ancien = PC.SORTIE
        try:
            ecrire_monde(d, jours=30)
            PC.SORTIE = os.path.join(d, 'rapport.json')
            self.assertEqual(PC.main(['x', d]), 0)
            with open(PC.SORTIE, encoding='utf-8') as f:
                texte = f.read()
            self.assertEqual(json.loads(texte)['verdict'], 'donnees_insuffisantes')
            self.assertNotIn('Joueur', texte)
        finally:
            PC.SORTIE = ancien
            shutil.rmtree(d)
        self.assertTrue(ancien.endswith(os.path.join('tennis_de_table', 'rapport_peu_connus_tt.json')))


if __name__ == '__main__':
    unittest.main()
