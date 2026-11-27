"""Étude Elo du badminton (27/11/2026) : filtres des matchs (comptés motif par motif), lecture de l'épreuve (nom du
tournoi, puis autres matchs des mêmes joueurs, puis convention), Elo qui apprend sur des données factices, règle de
l'étude (périodes, retenue, « l'Elo tient »), aucun nom de joueur dans le rapport ni dans le journal."""
import datetime as dt
import glob
import gzip
import json
import math
import os
import random
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
import elo_badminton as EB  # noqa: E402
import etude_elo_badminton as EE  # noqa: E402

# épreuve → (premier identifiant, double ?, noms de tournoi possibles ; le dernier ne dit pas le sexe)
MONDE = {'simple messieurs': (1, False, ['Open Factice (SS), MS', 'Open Factice, Men Singles', 'Open Factice 2018']),
         'simple dames': (101, False, ['Open Factice (SS), WS', 'Open Factice, Women', 'Coupe Factice, Singles']),
         'double messieurs': (201, True, ['Open Factice (SS), MD', 'Open Factice (MD)', 'Open Factice, Doubles']),
         'double dames': (301, True, ['Open Factice (SS), WD', 'Open Factice, Women, Doubles', 'Coupe Factice, Doubles']),
         'double mixte': (401, True, ['Open Factice (SS), XD', 'Open Factice, Mixed Doubles', 'Open Factice, Mixed, Doubles'])}
N_PAR_EPREUVE, PAR_JOUR, JOURS = 40, 30, 700


def manche(rng, p):
    a = b = 0
    while True:
        if rng.random() < p:
            a += 1
        else:
            b += 1
        if (max(a, b) >= 21 and abs(a - b) >= 2) or max(a, b) == 30:
            return [a, b]


def nom(i, double):
    return f'Joueur {i} / Joueur {i}b' if double else f'Joueur {i}'


def ecrire_monde(racine, jours=JOURS, debut=dt.date(2022, 1, 1), seed=5):
    rng = random.Random(seed)
    force = {}
    for ep, (d0, _, _) in MONDE.items():
        for i in range(d0, d0 + N_PAR_EPREUVE):
            force[i] = rng.gauss(0, 0.05)
    eps = list(MONDE)
    for k in range(jours):
        d = debut + dt.timedelta(days=k)
        t0 = int(dt.datetime(d.year, d.month, d.day, 8, tzinfo=dt.timezone.utc).timestamp())
        L = []
        for j in range(PAR_JOUR):
            ep = eps[j % 5]
            d0, double, noms = MONDE[ep]
            h, a = rng.sample(range(d0, d0 + N_PAR_EPREUVE), 2)
            p = 0.5 + force[h] - force[a]
            M, mh, ma = [], 0, 0
            while mh < 2 and ma < 2:
                x = manche(rng, p)
                M.append(x)
                mh += x[0] > x[1]
                ma += x[1] > x[0]
            L.append({'id': k * 100 + j, 't': t0 + 600 * j, 'ligue': 'International', 'tournoi': noms[(k + j) % 3],
                      'tournoi_id': None, 'h': [h, nom(h, double)], 'a': [a, nom(a, double)], 'g': 1 if mh > ma else 2,
                      'manches': M, 'statut': 'finished'})
        base = {'t': t0, 'ligue': 'International', 'tournoi': 'Open Factice, MS', 'h': [1, nom(1, False)],
                'a': [2, nom(2, False)], 'statut': 'finished'}
        L.append(dict(base, id=k * 100 + 90, g=1, manches=[[21, 3], [5, 2]], detail='Retired'))     # abandon
        L.append(dict(base, id=k * 100 + 91, g=0, manches=[], statut='canceled', detail='Canceled'))  # annulé
        L.append(dict(base, id=k * 100 + 92, g=2, manches=[[21, 3], [21, 4]]))                       # vainqueur incohérent
        L.append(dict(base, id=k * 100 + 93, g=1, manches=[[15, 3], [15, 4]]))                       # manches à 15
        L.append(dict(base, id=k * 100 + 94, g=1, manches=[]))                                       # sans manche
        L.append(dict(L[0]))                                                                         # doublon d'id
        if k < 200:                                                                                  # série hors circuits
            L.append(dict(base, id=k * 100 + 95, g=1, manches=[[21, 10], [21, 12]], tournoi='Armenia Infinity Cup',
                          h=[901, nom(901, False)], a=[902, nom(902, False)]))
        p = os.path.join(racine, EB.DOSSIER, str(d.year), f'{d.isoformat()}.jsonl.gz')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with gzip.open(p, 'wt', encoding='utf-8') as f:
            for r in L:
                f.write(json.dumps(r) + '\n')


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ecrire_monde(cls.dir)
        cls.M, cls.comptes = EB.lire(cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def test_filtres_et_comptes(self):
        self.assertEqual(len(self.M), JOURS * PAR_JOUR + 200)
        self.assertTrue(all(m[0] <= n[0] for m, n in zip(self.M, self.M[1:])))
        c = self.comptes
        self.assertEqual(c['lignes_lues'], JOURS * (PAR_JOUR + 6) + 200)
        self.assertEqual(c['matchs_gardes'] + c['matchs_ecartes'], c['lignes_lues'])
        self.assertEqual(c['ecartes_par_motif'], {'abandon_forfait': JOURS, 'non_termine': JOURS, 'vainqueur_incoherent': JOURS,
                                                  'manches_non_a_21': JOURS, 'manches_absentes': JOURS, 'doublon': JOURS})
        self.assertEqual(c['hors_circuit'], 200)

    def test_manches(self):
        for x, y, ok in [(21, 19, True), (21, 0, True), (22, 20, True), (30, 29, True), (30, 28, True), (21, 20, False),
                         (25, 22, False), (15, 9, False), (20, 18, False), (31, 29, False)]:
            self.assertEqual(EB.manche_reguliere(x, y), ok, (x, y))
            self.assertEqual(EB.manche_reguliere(y, x), ok, (y, x))

    def test_sexe_du_nom(self):
        for t, s in [('French Open (SS), WS', 'D'), ('French Open (SS) 2017, Mixed Doubles', 'X'), ('Arctic Open, XD', 'X'),
                     ('Latvia International 2025  MS ', 'M'), ('Chinese Taipei Open 2018 (XD)', 'X'), ('Uber Cup, Singles', 'D'),
                     ('Thomas Cup', 'M'), ('Canada Open, Men Singles', 'M'), ('China Masters, Women, Doubles', 'D'),
                     ('German Open (WT) 2018', None), ('Odisha Masters, Doubles', None), ('Sudirman Cup', None)]:
            self.assertEqual(EB.sexe_du_nom(t), s, t)

    def test_epreuves(self):
        # chaque entité factice n'appartient qu'à une épreuve : la lecture doit la retrouver, quel que soit le nom
        for m in self.M:
            if m[7]:
                self.assertEqual((m[2], m[8]), ('simple messieurs', 'convention'))
                continue
            attendu = [ep for ep, (d0, _, _) in MONDE.items() if d0 <= m[3] < d0 + N_PAR_EPREUVE][0]
            self.assertEqual(m[2], attendu)
        self.assertEqual(set(self.comptes['epreuve_lue_par']), {'nom', 'joueurs', 'convention'})
        self.assertEqual(self.comptes['epreuve_lue_par']['convention'], 200)

    def test_l_elo_apprend(self):
        Y = [m[5] for m in self.M]
        P = EB.rejouer(self.M, a=200, c=0.45)
        fin = list(range(len(self.M) // 2, len(self.M)))
        self.assertLess(EB.log_loss(P, Y, fin), math.log(2) - 0.02)
        self.assertTrue(0.7 < EB.pente(P, Y, fin) < 1.4)

    def test_etude(self):
        lignes = []
        rep = EE.etudier(self.M, self.comptes, lignes.append)
        self.assertEqual(rep['donnees']['premier_jour'], '2022-01-01')
        self.assertIn(rep['modele_retenu'], ('E0', 'E1', 'E2'))
        self.assertEqual(list(rep['jugement_par_epreuve']), EB.EPREUVES)
        jug = rep['jugement_toutes_epreuves']
        self.assertEqual(jug['matchs'], rep['periodes']['jugement'])
        self.assertEqual(jug['matchs'], sum(d['matchs'] for d in rep['jugement_par_epreuve'].values()))
        self.assertIn(rep['verdict'], ('l_elo_tient', 'l_elo_ne_tient_pas'))
        self.assertIn('part_peu_connus_pct', jug)
        # le jugement commence le 01/01/2023, l'apprentissage après 120 jours de mise en route (01/05/2022)
        fin = dt.date(2022, 1, 1) + dt.timedelta(days=JOURS)
        self.assertEqual(rep['periodes']['jugement'], (fin - dt.date(2023, 1, 1)).days * PAR_JOUR)
        appr = (dt.date(2023, 1, 1) - dt.date(2022, 5, 1)).days
        self.assertEqual(rep['periodes']['apprentissage'], appr * PAR_JOUR + 200 - 120)
        self.assertEqual(sum(sum(v.values()) for v in rep['matchs_par_epreuve_et_par_an'].values()), len(self.M))
        # la série hors circuits : publiée à part, mêmes périodes, même nombre de matchs jugés
        sans = rep['sans_hors_circuit_publie_sans_decider']
        self.assertEqual(sans['matchs_retires'], 200)
        self.assertEqual(sans['periodes']['jugement'], rep['periodes']['jugement'])
        self.assertEqual(sans['periodes']['apprentissage'], appr * PAR_JOUR)
        texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(lignes)
        self.assertNotIn('Joueur', texte)
        for interdit in ('cote', 'value', 'marché'):
            self.assertNotIn(interdit, texte.lower())

    def test_regle_figee(self):
        self.assertEqual((EE.JUGEMENT, EE.FIN_APPRENTISSAGE, EE.CHAUFFE_J), (dt.date(2023, 1, 1), dt.date(2022, 12, 31), 120))
        self.assertEqual((EE.MARGE, EE.MIN_JUGES, EE.MIEUX_QUE_PILE, EE.PENTE_MIN, EE.PENTE_MAX), (0.001, 1000, 0.02, 0.85, 1.15))
        self.assertEqual(EE.GRILLE_E0, [16, 24, 32, 48, 64])
        self.assertEqual(len(EE.GRILLE_E1), 9)
        self.assertEqual(EE.GRILLE_E2, [(0.25, 8), (0.25, 16), (0.5, 8), (0.5, 16)])
        ok = {'matchs': 1000, 'log_loss': 0.67, 'pente_etalonnage': 1.0}
        self.assertTrue(EE.tient(ok))
        self.assertFalse(EE.tient(dict(ok, matchs=999)))
        self.assertFalse(EE.tient(dict(ok, log_loss=0.68)))
        self.assertFalse(EE.tient(dict(ok, pente_etalonnage=1.16)))
        self.assertFalse(EE.tient({'matchs': 0}))

    def test_pas_assez(self):
        rep = EE.etudier(self.M[:500], None, lambda x: None)
        self.assertEqual(rep['verdict'], 'donnees_insuffisantes')
        self.assertEqual(EE.etudier([], None, lambda x: None)['verdict'], 'donnees_insuffisantes')

    def test_sources_propres(self):
        chemin_interdit = 'historique/' + 'feuilles'
        for p in glob.glob(os.path.join(ICI, '..', '*.py')) + glob.glob(os.path.join(ICI, '*.py')):
            with open(p, encoding='utf-8') as f:
                src = f.read()
            self.assertNotIn(chemin_interdit, src, p)
            for l in src.splitlines():
                if l.startswith(('import ', 'from ')):
                    self.assertNotIn('yaml', l, p)
                    self.assertNotIn('scripts', l, p)


if __name__ == '__main__':
    unittest.main()
