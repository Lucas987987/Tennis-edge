# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_plus_sur.py (paquet 469), sur données factices : aucune archive nécessaire."""
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, os.path.dirname(ICI))
import etude_plus_sur as PS  # noqa: E402
import etude_pente_melange as PM  # noqa: E402

NU = {'elo': 0.8, 'simulation': 0.3, 'pente_doc': None, 'fmd': None, 'surfaces': {}}
SIGNAUX = {'elo': 0.78, 'simulation': 0.24, 'pente_doc': 1.11, 'fmd': {'pente': 0.775, 'de': 500, 'a': 1500},
           'surfaces': {'Clay': 1.065}}
CFGS = {c: dict(NU) for c in PS.CIRCUITS}
APPRIS, JUGES = ('2025-03-10', '2026-02-02'), ('2024-07-01', '2024-10-14')
SYMETRIQUE = {PS.ELO: (0.8, 0.3), PS.SIM: (0.8, 0.3)}
ASYMETRIQUE = {PS.ELO: (1.1, 0.0), PS.SIM: (0.2, 0.9)}          # chaque modèle a raison quand il est le plus sûr
INTERDIT = 'march' + 'é'


def _sg(z):
    return 1 / (1 + math.exp(-z))


def lignes(verite, n=2500, graine=5, circuits=PS.CIRCUITS, jours=APPRIS + JUGES):
    """Lignes factices au format du rejeu. La réalité suit σ(a · z Elo + b · z simulation), (a, b) selon le modèle le
    plus sûr ; verite : {régime: (a, b)}, ou {(circuit, jour): {régime: (a, b)}} (SYMETRIQUE par défaut)."""
    rnd = random.Random(graine)
    rows = []
    for c in circuits:
        for jour in jours:
            v = verite if PS.ELO in verite else verite.get((c, jour), SYMETRIQUE)
            for i in range(n):
                x = rnd.gauss(0, 0.9)
                ze, zs = x + rnd.gauss(0, 0.6), x + rnd.gauss(0, 0.6)
                a, b = v[PS.regime_2(ze, zs)]
                if rnd.random() < _sg(a * ze + b * zs):
                    rows.append([c, jour, ze, zs, 5000, 6000, 'Hard'])
                else:
                    rows.append([c, jour, -ze, -zs, 6000, 5000, 'Hard'])
    return rows


class TestRegimes(unittest.TestCase):
    def test_le_plus_sur(self):
        self.assertEqual(PS.plus_sur(1.0, 0.5), PS.ELO)
        self.assertEqual(PS.plus_sur(0.5, -1.0), PS.SIM)
        self.assertEqual(PS.plus_sur(0.7, 0.7), PS.ELO)                      # à égalité : l'Elo
        self.assertEqual(PS.regime_2(-1.0, 0.5), PS.ELO)

    def test_trois_regimes_selon_l_ecart(self):
        lg = lambda p: math.log(p / (1 - p))
        self.assertEqual(PS.regime_3(lg(0.60), lg(0.65)), PS.PROCHES)
        self.assertEqual(PS.regime_3(lg(0.77), lg(0.61)), PS.ELO10)
        self.assertEqual(PS.regime_3(lg(0.61), lg(0.76)), PS.SIM10)
        self.assertEqual(PS.regime_3(lg(0.58), lg(0.45)), PS.ELO10)          # vainqueurs différents, 13 points : le plus sûr
        self.assertEqual(PS.regime_3(lg(0.56), lg(0.42)), PS.SIM10)
        self.assertAlmostEqual(PS.ecart_points(lg(0.77), lg(0.61)), 16.0, places=6)

    def test_meme_regime_vu_du_perdant(self):
        rnd = random.Random(1)
        for _ in range(200):
            ze, zs = rnd.gauss(0, 1), rnd.gauss(0, 1)
            self.assertEqual(PS.regime_2(ze, zs), PS.regime_2(-ze, -zs))
            self.assertEqual(PS.regime_3(ze, zs), PS.regime_3(-ze, -zs))
            self.assertEqual(PS.groupe(ze, zs), PS.groupe(-ze, -zs))

    def test_groupes_de_la_table(self):
        lg = lambda p: math.log(p / (1 - p))
        self.assertEqual(PS.groupe(lg(0.77), lg(0.61)), 'meme_favori_10_points_elo_plus_sur')
        self.assertEqual(PS.groupe(lg(0.39), lg(0.24)), 'meme_favori_10_points_simulation_plus_sure')
        self.assertEqual(PS.groupe(lg(0.60), lg(0.65)), 'meme_favori_moins_de_10_points')
        self.assertEqual(PS.groupe(lg(0.55), lg(0.48)), 'vainqueurs_differents')
        self.assertIsNone(PS.groupe(0.0, 1.0))
        for g in (PS.groupe(1.0, 0.2), PS.groupe(0.2, 1.0), PS.groupe(0.2, 0.25), PS.groupe(0.2, -0.2)):
            self.assertIn(g, PS.GROUPES)


class TestMelange(unittest.TestCase):
    R = (['CH', '2025-01-01', 1.0, 0.5, 5000, 6000, 'Hard'], ['CH', '2025-01-01', 1.0, 0.5, 300, 6000, 'Clay'],
         ['CH', '2025-01-01', 1.0, -0.5, 900, 6000, 'Grass'], ['CH', '2025-01-01', -1.0, 0.5, 900, 6000])

    def test_poids_en_place_egale_la_base_du_465(self):
        for r in self.R:
            self.assertAlmostEqual(PS.z_de(r, SIGNAUX, SIGNAUX['elo'], SIGNAUX['simulation']), PM.z_base(r, SIGNAUX))

    def test_lineaire_en_a_et_b(self):
        for r in self.R:
            t = PS.termes(r, SIGNAUX)
            for w in ((0.5, 0.5), (1.2, 0.0), (0.0, 0.7)):
                self.assertAlmostEqual(PS.z_t(t, w), PS.z_de(r, SIGNAUX, *w))

    def test_poids_retrouves(self):
        rnd = random.Random(4)
        T = []
        for _ in range(8000):
            ze, zs = rnd.gauss(0, 1.0), rnd.gauss(0, 1.0)
            s = 1 if rnd.random() < _sg(0.9 * ze + 0.4 * zs) else -1
            T.append((0.0, s * ze, s * zs))
        a, b = PS.apprendre(T, (0.5, 0.5))
        self.assertAlmostEqual(a, 0.9, delta=0.1)
        self.assertAlmostEqual(b, 0.4, delta=0.1)
        self.assertAlmostEqual(PS.part_simulation((a, b)), b / (a + b), places=3)

    def test_poids_bornes(self):
        rnd = random.Random(8)
        T = []
        for _ in range(3000):
            ze, zs = rnd.gauss(0, 1.0), rnd.gauss(0, 1.0)
            s = 1 if rnd.random() < _sg(1.0 * ze - 0.6 * zs) else -1          # la simulation se trompe de sens
            T.append((0.0, s * ze, s * zs))
        a, b = PS.apprendre(T, (0.8, 0.3))
        self.assertEqual(b, PS.POIDS_MIN)
        self.assertGreater(a, 0.5)
        self.assertIsNone(PS.part_simulation((0.0, 0.0)))


class TestRegle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        v = {(c, j): ASYMETRIQUE for c in ('CH',) for j in APPRIS + JUGES}
        v.update({('WTA', j): {PS.ELO: (1.2, 0.6), PS.SIM: (1.2, 0.6)} for j in APPRIS + JUGES})
        cls.jug = PS.juger(lignes(v, graine=6), CFGS)      # CH : asymétrie réelle ; WTA : poids en place faux ; ATP : justes

    def test_asymetrie_reelle_retenue(self):
        d = self.jug['CH']
        self.assertEqual((d['matchs_apprentissage'], d['matchs_jugement']), (5000, 5000))
        for nom, _ in PS.CANDIDATS:
            x = d[nom]
            self.assertEqual(x['verdict'], 'retenu', (nom, x.get('raisons')))
            self.assertEqual(x['sens'], 'plus de simulation quand elle est la plus sûre')
            self.assertEqual(x['sens_inverse']['sens'], x['sens'])
            self.assertGreaterEqual(x['gain_jugement_matchs_concernes']['matchs'], PS.MIN_JUGES)
            self.assertGreaterEqual(x['gain_jugement_matchs_concernes']['gain'], PS.MARGE)
            self.assertGreater(x['erreurs_types'], PS.MIN_ERREURS_TYPES)
            self.assertGreater(x['sens_inverse']['gain_sur_l_apprentissage_matchs_concernes']['gain'], 0)
        r = d['deux_regimes']['regimes']
        self.assertGreater(r[PS.SIM]['poids_appris']['part_simulation'], r[PS.ELO]['poids_appris']['part_simulation'] + 0.3)
        self.assertEqual(r[PS.ELO]['matchs_apprentissage'] + r[PS.SIM]['matchs_apprentissage'], 5000)
        self.assertEqual(d['retenus'], ['deux_regimes', 'trois_regimes'])
        self.assertIn('gain', d['trois_regimes_moins_deux_regimes_jugement'])
        # c'est la part qui compte : le candidat fait mieux qu'une simple pente par régime
        self.assertGreater(d['deux_regimes']['temoin_une_pente_par_regime']['candidat_moins_pentes_jugement']['gain'], 0)

    def test_poids_en_place_faux_sans_asymetrie_le_temoin_suffit(self):
        d = self.jug['WTA']
        for nom, _ in PS.CANDIDATS:
            x = d[nom]
            self.assertIn(x['verdict'], ('non retenu', 'aucune décision'), nom)      # peu de % bougent d'un point
            self.assertTrue(x['raisons'])
            t = x['temoin_poids_uniques_reappris']
            self.assertAlmostEqual(t['elo'], 1.2, delta=0.2)
            self.assertAlmostEqual(t['simulation'], 0.6, delta=0.2)
            f = x['face_aux_poids_en_place_jugement']
            self.assertGreater(f['temoin']['gain'], 0.003)                # réapprendre les poids gagne…
            self.assertGreater(f['candidat']['gain'], 0.002)              # … le candidat aussi, face aux poids en place…
            self.assertLess(abs(x['gain_jugement_tous_les_matchs']['gain']), PS.MARGE)    # … mais pas face au témoin
        self.assertEqual(d['retenus'], [])

    def test_rien_a_corriger_non_retenu(self):
        d = self.jug['ATP']
        self.assertEqual(d['retenus'], [])
        for nom, _ in PS.CANDIDATS:
            self.assertIn(d[nom]['verdict'], ('non retenu', 'aucune décision'))

    def test_sens_oppose_entre_les_periodes_non_retenu(self):
        v = {('CH', j): ASYMETRIQUE for j in APPRIS}
        v.update({('CH', j): {PS.ELO: ASYMETRIQUE[PS.SIM], PS.SIM: ASYMETRIQUE[PS.ELO]} for j in JUGES})
        x = PS.juger(lignes(v, circuits=('CH',)), CFGS)['CH']['deux_regimes']
        self.assertEqual(x['verdict'], 'non retenu')
        self.assertIn('la part de la simulation ne bouge pas dans le même sens sur la période jugée', x['raisons'])
        self.assertIn('pas de gain en sens inverse', x['raisons'])
        self.assertLess(x['gain_jugement_matchs_concernes']['gain'], 0)

    def test_moins_de_1000_concernes_aucune_decision(self):
        jug = PS.juger(lignes(ASYMETRIQUE, n=400, circuits=('CH',)), CFGS)
        x = jug['CH']['deux_regimes']
        self.assertEqual(x['verdict'], 'aucune décision')
        self.assertLess(x['gain_jugement_matchs_concernes']['matchs'], PS.MIN_JUGES)
        self.assertIn('sens_inverse', x)                                   # chiffres publiés quand même
        self.assertEqual(jug['ATP']['matchs'], 0)
        self.assertEqual(jug['ATP']['deux_regimes']['verdict'], 'aucune décision')

    def test_regime_trop_petit_garde_le_temoin(self):
        rows = [r for r in lignes(ASYMETRIQUE, n=700, circuits=('CH',)) if PS.regime_2(r[2], r[3]) == PS.ELO or r[1] < '2025']
        rows += [r for r in lignes(ASYMETRIQUE, n=60, graine=9, circuits=('CH',), jours=APPRIS)
                 if PS.regime_2(r[2], r[3]) == PS.SIM]
        x = PS.juger(rows, CFGS)['CH']['deux_regimes']
        self.assertFalse(x['regimes'][PS.SIM]['appris'])
        self.assertLess(x['regimes'][PS.SIM]['matchs_apprentissage'], PS.MIN_APPRIS)
        t = x['temoin_poids_uniques_reappris']
        self.assertEqual((x['regimes'][PS.SIM]['poids_appris']['elo'], x['regimes'][PS.SIM]['poids_appris']['simulation']),
                         (t['elo'], t['simulation']))
        self.assertEqual(x['regimes'][PS.SIM]['matchs_concernes_jugement'], 0)

    def test_concernes_au_moins_un_point(self):
        T = [(0.0, 1.0, 1.0), (0.0, 0.01, 0.01)]
        E = PS._ecarts(T, [PS.ELO, PS.ELO], (0.5, 0.5), {PS.ELO: (0.6, 0.6)})
        self.assertEqual([e[1] for e in E], [True, False])
        self.assertGreater(E[0][2], 0)                                     # le favori a gagné : plus de confiance gagne

    def test_meme_resultat_deux_fois(self):
        a = PS.juger(lignes(ASYMETRIQUE, n=300, circuits=('CH',)), CFGS)
        b = PS.juger(lignes(ASYMETRIQUE, n=300, circuits=('CH',)), CFGS)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_periodes_du_465(self):
        self.assertEqual((PS.DEBUT, PS.COUPURE, PS.FIN), (PM.DEBUT, PM.COUPURE, PM.FIN))
        self.assertEqual([c for c, _ in PS.CANDIDATS], ['deux_regimes', 'trois_regimes'])


class TestTable(unittest.TestCase):
    def test_qui_a_raison(self):
        lg = lambda p: math.log(p / (1 - p))
        L = ([(lg(0.77), lg(0.61), lg(0.75))] * 3 + [(-lg(0.77), -lg(0.61), -lg(0.75))]          # Elo plus sûr : 3 sur 4
             + [(lg(0.61), lg(0.76), lg(0.68))] * 2                                              # simulation plus sûre : 2 sur 2
             + [(lg(0.56), lg(0.45), lg(0.53))] * 3 + [(lg(0.44), lg(0.55), lg(0.47))] * 2)      # désaccord : Elo 3 sur 5
        q = PS.qui_a_raison(L)
        a = q['meme_favori_10_points_elo_plus_sur']
        self.assertEqual((a['matchs'], a['elo_pct'], a['simulation_pct'], a['en_place_pct'], a['favori_gagne_pct']),
                         (4, 77.0, 61.0, 75.0, 75.0))
        self.assertAlmostEqual(a['erreur_type_points'], 21.7, places=1)
        s = q['meme_favori_10_points_simulation_plus_sure']
        self.assertEqual((s['matchs'], s['elo_pct'], s['simulation_pct'], s['en_place_pct'], s['favori_gagne_pct']),
                         (2, 61.0, 76.0, 68.0, 100.0))
        v = q['vainqueurs_differents']
        self.assertEqual((v['matchs'], v['elo_a_raison_pct'], v['simulation_a_raison_pct'], v['en_place_a_raison_pct']),
                         (5, 60.0, 40.0, 60.0))
        self.assertEqual(q['meme_favori_moins_de_10_points'], {'matchs': 0})

    def test_table_dans_le_jugement(self):
        d = PS.juger(lignes(SYMETRIQUE, n=200, circuits=('CH',)), CFGS)['CH']
        for per, n in (('jugement', 400), ('apprentissage', 400)):
            self.assertEqual(sum(x['matchs'] for x in d['qui_a_raison'][per].values()), n)
        self.assertIn('en_chauffe', d['elo_seul'])


class TestSorties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jug = PS.juger(lignes(ASYMETRIQUE, n=900, circuits=('CH',)), CFGS)
        with open(PS.GABARIT_JOURNAL, encoding='utf-8') as f:
            cls.gabarit = json.load(f)

    def _direct(self, d):
        os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        rnd = random.Random(2)
        M = []
        for _ in range(150):
            pe, ps = min(max(rnd.random(), 0.05), 0.95), min(max(rnd.random(), 0.05), 0.95)
            p = (pe + ps) / 2
            M.append({'home': 'Nom Secret', 'away': 'Autre Secret', 'circuit': 'CH', 'p_affiche': round(p, 4),
                      'premier': {'combinaison': {'p_home': p}, 'stats': {'p_home': pe}, 'simulation': {'p_home': ps}},
                      'reel': {'gagnant': 'home' if rnd.random() < p else 'away', 'interrompu': None}})
        M.append({'circuit': 'CH', 'p_affiche': 0.6, 'reel': {'gagnant': 'home', 'interrompu': 'abandon'},
                  'premier': {'combinaison': {'p_home': 0.6}, 'stats': {'p_home': 0.6}, 'simulation': {'p_home': 0.6}}})
        M.append({'circuit': 'CH', 'p_affiche': 0.6, 'reel': {'gagnant': 'home'},
                  'premier': {'combinaison': None, 'simulation': None, 'stats': {'p_home': 0.6}}})
        with open(os.path.join(d, PS.DIRECT), 'w', encoding='utf-8') as f:
            json.dump({'matchs': M}, f)

    def test_nos_matchs_publies_comptes_seulement(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(PS.direct(d, self.jug), {'lu': False})
            self._direct(d)
            x = PS.direct(d, self.jug)
        ch = x['circuits']['CH']
        self.assertEqual(ch['matchs'], 150)                                # ni l'abandon ni le match sans simulation
        self.assertEqual(sum(v['matchs'] for v in ch['qui_a_raison'].values()), 150)
        self.assertEqual(ch['poids_du_rejeu_deux_regimes']['gain_tous_les_matchs']['matchs'], 150)
        self.assertEqual(x['circuits']['ATP']['matchs'], 0)
        self.assertNotIn('Secret', json.dumps(x, ensure_ascii=False))

    def test_entree_journal(self):
        with tempfile.TemporaryDirectory() as d:
            self._direct(d)
            en_direct = PS.direct(d, self.jug)
        e = PS.entree_journal({'jugement': self.jug, 'nos_matchs_publies': en_direct}, self.gabarit)
        self.assertEqual((e['paquet'], e['statut']), (469, 'etude'))
        for mot in ('RÉSULTAT', 'Challenger', 'deux régimes', 'trois régimes', 'qui a raison', 'Confirmation seulement',
                    'face au témoin'):
            self.assertIn(mot, e['quoi'])
        self.assertTrue(e['quoi'].endswith('Le % de victoire ne change pas.'))
        for texte in (e['quoi'], e['garde_fou'], PS.REGLE, PS.LIMITES, PS.PERIODE_JUGEE, PS.__doc__,
                      json.dumps(self.jug, ensure_ascii=False)):
            self.assertNotIn(INTERDIT, texte.lower())
            self.assertNotIn('cote', texte.lower())
            self.assertNotIn('bookmaker', texte.lower())

    def test_gabarit_meme_forme_que_le_465(self):
        self.assertEqual(sorted(self.gabarit), ['date', 'garde_fou', 'paquet', 'quoi_debut', 'statut'])
        with open(os.path.join(os.path.dirname(PS.GABARIT_JOURNAL), 'paquet_465.json'), encoding='utf-8') as f:
            self.assertEqual(sorted(json.load(f)), sorted(self.gabarit))
        self.assertEqual(self.gabarit['paquet'], PS.PAQUET)

    def test_affichage_public_sans_erreur(self):
        sortie = []
        with tempfile.TemporaryDirectory() as d:
            self._direct(d)
            PS.afficher(self.jug, PS.direct(d, self.jug), journal=sortie.append)
        PS.afficher(PS.juger([], CFGS), {'lu': False}, journal=sortie.append)                # aucun match : pas d'erreur
        texte = '\n'.join(sortie)
        for mot in ('Challenger', 'Elo seul', 'nos matchs publiés', 'vainqueurs_differents', 'sens inverse'):
            self.assertIn(mot, texte)
        self.assertNotIn('Secret', texte)

    def test_journal_depuis_rapport(self):
        e = PS.entree_journal({'jugement': self.jug}, self.gabarit)
        with tempfile.TemporaryDirectory() as d:
            journal, rapport = os.path.join(d, 'journal.json'), os.path.join(d, 'rapport.json')
            with open(journal, 'w', encoding='utf-8') as f:
                json.dump({'regle': 'r', 'changements': [{'paquet': 465, 'quoi': 'avant'}]}, f)
            with open(rapport, 'w', encoding='utf-8') as f:
                json.dump({'entree_journal': e}, f, ensure_ascii=False)
            ancien, PS.JOURNAL = PS.JOURNAL, journal
            try:
                self.assertEqual(PS.main(['x', '--journal-depuis-rapport', rapport]), 0)
                self.assertEqual(PS.main(['x', '--journal-depuis-rapport', rapport]), 0)      # deux fois : une seule entrée
            finally:
                PS.JOURNAL = ancien
            with open(journal, encoding='utf-8') as f:
                L = json.load(f)['changements']
            self.assertEqual([x['paquet'] for x in L], [465, 469])
            self.assertEqual(L[1]['statut'], 'etude')


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        chemin = os.path.join(RACINE, '.github', 'workflows', 'etude_plus_sur.yml')
        if not os.path.exists(chemin):
            self.skipTest('copie partielle du dépôt : pas de .github/')
        with open(chemin, encoding='utf-8') as f:
            self.texte = f.read()

    def test_sparse_checkout_complet(self):
        for chemin in ('/simulateur/', '/resultats_itf/', '/scripts/resultats_itf.py', '/scripts/feuilles_match.py',
                       '/feuilles/', '/Tennis_Edge_Lab/books.py', '/Tennis_Edge_Lab/live/pronostics_resultats.json'):
            self.assertIn('            ' + chemin + '\n', self.texte)

    def test_aucun_run_en_scalaire_simple(self):
        runs = [x.strip() for x in self.texte.splitlines() if x.strip().startswith('run:')]
        self.assertEqual(len(runs), 3)
        self.assertEqual(set(runs), {'run: |'})

    def test_lance_l_etude_et_son_journal(self):
        self.assertIn('python simulateur/etude_plus_sur.py /tmp/sackmann .', self.texte)
        self.assertIn('--journal-depuis-rapport /tmp/rapport_plus_sur.json', self.texte)
        self.assertIn("paths: ['simulateur/etude_plus_sur.py']", self.texte)
        self.assertNotIn('pente_melange', self.texte)
        self.assertNotIn(INTERDIT, self.texte.lower())

    def test_arret_sans_resultat_itf(self):
        with open(os.path.join(os.path.dirname(ICI), 'etude_plus_sur.py'), encoding='utf-8') as f:
            source = f.read()
        self.assertIn('aucun résultat ITF hommes lu', source)
        self.assertNotIn('hash' + '(', source)
        self.assertNotIn(INTERDIT, source.lower())
        with open(__file__, encoding='utf-8') as f:
            self.assertNotIn('hash' + '(', f.read())


if __name__ == '__main__':
    unittest.main()
