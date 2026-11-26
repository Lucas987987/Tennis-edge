# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_pente_melange.py (paquet 465), sur données factices : aucune archive nécessaire."""
import datetime as dt
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
import etude_pente_melange as PM  # noqa: E402
import etude_peu_documentes as PD  # noqa: E402

CFG = {'elo': 0.78, 'simulation': 0.24, 'pente_doc': 1.11, 'fmd': {'pente': 0.775, 'de': 500, 'a': 1500},
       'surfaces': {'Clay': 1.065}}
CFGS = {c: dict(CFG) for c in PM.CIRCUITS}
DOCS = {'moins_de_500': (120, 4000), '500_a_1500': (900, 5000), '1500_a_3000': (2000, 6000), '3000_et_plus': (5000, 9000)}
APPRIS, JUGES = ('2025-03-10', '2026-02-02'), ('2024-07-01', '2024-10-14')
INTERDIT = 'march' + 'é'


def _sg(z):
    return 1 / (1 + math.exp(-z))


def lignes(pentes, n=650, graine=5, circuits=PM.CIRCUITS, jours=APPRIS + JUGES, cfg=CFG):
    """Lignes factices au format du rejeu (avec surface). La réalité suit σ(k · logit du % « comme en place ») ;
    pentes : {(circuit, jour)}, {circuit} ou nombre → k (1 par défaut : rien à corriger). n lignes par jour et par
    tranche."""
    rnd = random.Random(graine)
    rows = []
    for c in circuits:
        for jour in jours:
            k = pentes if isinstance(pentes, (int, float)) else pentes.get((c, jour), pentes.get(c, 1.0))
            for nom, (peu, beaucoup) in DOCS.items():
                for i in range(n):
                    x = rnd.gauss(0, 1.1)
                    ze, zs = x + rnd.gauss(0, 0.3), 0.9 * x + rnd.gauss(0, 0.5)
                    d_g, d_p = (peu, beaucoup) if rnd.random() < 0.5 else (beaucoup, peu)
                    r = [c, jour, ze, zs, d_g, d_p, ('Clay', 'Hard', 'Hard')[i % 3]]
                    if rnd.random() < _sg(k * PM.z_base(r, cfg)):
                        rows.append(r)
                    else:
                        rows.append([c, jour, -ze, -zs, d_p, d_g, r[6]])
    return rows


class TestBase(unittest.TestCase):
    def test_base_egale_au_melange_462_hors_surface(self):
        for r in (['CH', '2025-01-01', 1.0, 0.5, 5000, 6000, 'Hard'], ['CH', '2025-01-01', 1.0, 0.5, 300, 6000, None],
                  ['CH', '2025-01-01', 1.0, 0.5, 900, 6000, 'Grass'], ['CH', '2025-01-01', 1.0, 0.5, 900, 6000]):
            self.assertAlmostEqual(PM.z_base(r, CFG), PD.z_melange(r, CFG))

    def test_pente_de_surface_en_dernier(self):
        r = ['CH', '2025-01-01', 1.0, 0.5, 300, 6000, 'Clay']            # sous 500 points ET terre
        self.assertAlmostEqual(PM.z_base(r, CFG), 1.065 * 1.11 * (0.78 + 0.12))
        r2 = ['CH', '2025-01-01', -1.0, -0.5, 6000, 300, 'Clay']         # même match, le favori a perdu
        self.assertAlmostEqual(PM.z_base(r2, CFG), -PM.z_base(r, CFG))

    def test_melange_nu(self):
        nu = PM.sans_signaux(CFG)
        r = ['CH', '2025-01-01', 1.0, 0.5, 300, 6000, 'Clay']
        self.assertAlmostEqual(PM.z_base(r, nu), 0.78 + 0.12)
        self.assertEqual(CFG['pente_doc'], 1.11)                          # l'original n'est pas touché

    def test_en_place_lit_les_fichiers_du_depot(self):
        cfgs = PM.en_place(RACINE)
        for c in PM.CIRCUITS:
            self.assertGreater(cfgs[c]['elo'], 0)
            self.assertIsInstance(cfgs[c]['surfaces'], dict)
        with tempfile.TemporaryDirectory() as d:
            vide = PM.en_place(d)
        self.assertEqual(vide['CH']['surfaces'], {})
        self.assertIsNone(vide['CH']['pente_doc'])


class TestMesures(unittest.TestCase):
    def test_pente_retrouvee_et_bornee(self):
        rnd = random.Random(3)
        Z = []
        for _ in range(6000):
            z = rnd.gauss(0, 1.0)
            Z.append(z if rnd.random() < _sg(1.3 * z) else -z)
        a, et = PM.pente_de(Z)
        self.assertAlmostEqual(a, 1.3, delta=0.12)
        self.assertGreater(et, 0)
        self.assertEqual(PM.pente_de([0.01] * 50)[0], PM.PENTE_MAX)     # le favori gagne toujours : pente bornée

    def test_cote_de_un(self):
        self.assertEqual([PM.cote(a) for a in (1.2, 0.8, 1.004, 0.996, 1.006)], [1, -1, 0, 0, 1])

    def test_gain(self):
        Z = [1.0, -0.5, 2.0]
        self.assertEqual(PM.gain(Z, 1.0)['gain'], 0.0)
        self.assertEqual(PM.gain(Z, 1.0)['matchs'], 3)
        self.assertGreater(PM.gain([1.0] * 10, 1.5)['gain'], 0)            # le favori gagne : étirer fait gagner
        self.assertLess(PM.gain([-1.0] * 10, 1.5)['gain'], 0)

    def test_elo_en_chauffe(self):
        rnd = random.Random(9)
        R = []
        for jour, k in (('2025-05-05', 1.0), ('2024-07-01', 0.5), ('2024-10-14', 0.5)):
            for _ in range(2500):
                z = rnd.gauss(0, 1.0)
                R.append(['CH', jour, z if rnd.random() < _sg(k * z) else -z, 0.0, 1, 1, 'Hard'])
        e = PM.elo_en_chauffe(R)
        self.assertEqual([e[k]['matchs'] for k in ('apprentissage', 'jugement', 'jugement_06_08_2024', 'jugement_09_12_2024')],
                         [2500, 5000, 2500, 2500])
        self.assertTrue(e['en_chauffe'])
        self.assertLess(e['ecart_en_erreurs_types'], -2)
        self.assertIsNone(PM.elo_en_chauffe([])['en_chauffe'])


class TestRegle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jug = PM.juger(lignes({'CH': 1.6}, graine=6), CFGS)                  # Challenger trop timide, ATP et WTA justes

    def test_effet_reel_retenu_case_par_case(self):
        d = self.jug['CH']
        self.assertEqual((d['matchs_apprentissage'], d['matchs_jugement']), (4 * 1300, 4 * 1300))
        for nom, _, _ in PM.TRANCHES:
            t = d['tranches'][nom]
            self.assertEqual(t['verdict'], 'retenu', (nom, t.get('raisons')))
            self.assertEqual(t['sens'], 'étirer')
            self.assertGreater(t['pente_apprise'], 1.25)
            self.assertGreaterEqual(t['gain_jugement']['gain'], PM.MARGE)
            self.assertGreaterEqual(t['gain_jugement']['matchs'], PM.MIN_JUGES)
            self.assertGreater(t['erreurs_types'], PM.MIN_ERREURS_TYPES)
            self.assertGreater(t['sens_inverse']['pente_apprise_sur_la_periode_jugee'], 1.0)
            self.assertGreater(t['sens_inverse']['gain_sur_l_apprentissage']['gain'], 0)
        self.assertEqual(d['cases_retenues'], [n for n, _, _ in PM.TRANCHES])
        self.assertEqual(d['une_seule_pente']['verdict'], 'retenu')
        self.assertEqual(d['toutes_les_tranches_jugement']['matchs'], 4 * 1300)
        self.assertGreater(d['toutes_les_tranches_jugement']['gain'], 0)
        self.assertIn('gain', d['tranches_moins_une_seule_pente_jugement'])

    def test_rien_a_corriger_non_retenu(self):
        for c in ('ATP', 'WTA'):
            d = self.jug[c]
            self.assertEqual(d['cases_retenues'], [])
            self.assertEqual(d['une_seule_pente']['verdict'], 'non retenu')
            for nom, _, _ in PM.TRANCHES:
                t = d['tranches'][nom]
                self.assertEqual(t['verdict'], 'non retenu')
                self.assertTrue(t['raisons'])

    def test_le_melange_nu_est_publie(self):
        t = self.jug['CH']['tranches']['moins_de_500']
        # la base porte déjà 1,11 (et 1,065 sur terre) : la pente du mélange nu est plus haute que celle qui reste à apprendre
        self.assertGreater(t['pente_du_melange_nu_apprentissage'], t['pente_apprise'])

    def test_sens_oppose_entre_les_periodes_non_retenu(self):
        p = {('CH', j): 1.4 for j in APPRIS}
        p.update({('CH', j): 0.7 for j in JUGES})
        jug = PM.juger(lignes(p, circuits=('CH',)), CFGS)
        for nom, _, _ in PM.TRANCHES:
            t = jug['CH']['tranches'][nom]
            self.assertEqual(t['verdict'], 'non retenu')
            self.assertIn("la pente apprise sur la période jugée n'est pas du même côté de 1", t['raisons'])
            self.assertLess(t['gain_jugement']['gain'], 0)

    def test_moins_de_1000_juges_aucune_decision(self):
        jug = PM.juger(lignes({'CH': 1.35}, n=400, circuits=('CH',)), CFGS)
        for nom, _, _ in PM.TRANCHES:
            t = jug['CH']['tranches'][nom]
            self.assertEqual(t['verdict'], 'aucune décision')
            self.assertEqual(t['gain_jugement']['matchs'], 800)           # chiffres publiés quand même
            self.assertIn('sens_inverse', t)
        self.assertEqual(jug['CH']['cases_retenues'], [])
        self.assertEqual(jug['CH']['une_seule_pente']['verdict'], 'retenu')      # 3 200 matchs jugés pour le circuit
        self.assertEqual(jug['ATP']['matchs'], 0)
        self.assertEqual(jug['ATP']['une_seule_pente']['verdict'], 'aucune décision')

    def test_trop_peu_pour_apprendre(self):
        jug = PM.juger(lignes({'CH': 1.35}, n=100, circuits=('CH',)), CFGS)
        t = jug['CH']['tranches']['500_a_1500']
        self.assertEqual(t['verdict'], 'aucune décision')
        self.assertNotIn('pente_apprise', t)
        self.assertEqual(t['jugement']['matchs'], 200)

    def test_meme_resultat_deux_fois(self):
        a = PM.juger(lignes(1.2, n=200, circuits=('CH',)), CFGS)
        b = PM.juger(lignes(1.2, n=200, circuits=('CH',)), CFGS)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class TestRejeu(unittest.TestCase):
    M = [{'nom_g': 'Aa Bb', 'nom_p': 'Cc Dd', 'circuit': 'CH', 'date': dt.date(2024, 7, 1), 'surface': 'Clay'},
         {'nom_g': 'Ee Ff', 'nom_p': 'Gg Hh', 'circuit': 'ITFH', 'date': dt.date(2024, 7, 2), 'surface': 'Hard'},
         {'nom_g': 'Aa Bb', 'nom_p': 'Gg Hh', 'circuit': 'ATP', 'date': dt.date(2024, 7, 3), 'surface': 'Grass', 'abandon': True},
         {'nom_g': 'Aa Bb', 'nom_p': 'Ee Ff', 'circuit': 'ATP', 'date': dt.date(2024, 7, 4), 'surface': 'Hard', 'niveau': 'D'},
         {'nom_g': 'Cc Dd', 'nom_p': 'Ee Ff', 'circuit': 'WTA', 'date': dt.date(2025, 2, 3), 'surface': 'Hard'},
         {'nom_g': 'Cc Dd', 'nom_p': 'Aa Bb', 'circuit': 'CH', 'date': dt.date(2026, 6, 1), 'surface': 'Clay'},
         {'nom_g': 'Cc Dd', 'nom_p': 'Aa Bb', 'circuit': 'CH', 'date': dt.date(2024, 5, 31), 'surface': 'Clay'}]
    ROWS = [['CH', '2024-07-01', 0.1, 0.2, 10, 20], ['WTA', '2025-02-03', -0.3, 0.1, 30, 40]]

    def test_surfaces_alignees(self):
        self.assertEqual(PM.surfaces_des_lignes(self.M, self.ROWS), ['Clay', 'Hard'])

    def test_surfaces_desalignees_arret(self):
        with self.assertRaises(SystemExit):
            PM.surfaces_des_lignes(self.M, self.ROWS[:1])
        with self.assertRaises(SystemExit):
            PM.surfaces_des_lignes(self.M, [self.ROWS[0], ['ATP', '2025-02-03', 0.0, 0.0, 1, 1]])

    def test_rejeu_elargit_les_dates_puis_les_remet(self):
        avant = (PD.DEBUT, PD.FIN, PD.charger, PD.rejeu)
        vus = {}

        def faux_rejeu(archive, racine, journal=print):
            vus['dates'] = (PD.DEBUT, PD.FIN)
            PD.charger(archive, racine)
            return [list(r) for r in self.ROWS], 7, 3

        PD.charger, PD.rejeu = (lambda a, r: (self.M, 7, None, None, None)), faux_rejeu
        try:
            rows, n_itf, n_adj = PM.rejeu('archive', 'racine')
            apres = (PD.DEBUT, PD.FIN)
            PD.rejeu = lambda *a, **k: (_ for _ in ()).throw(SystemExit('aucun résultat ITF'))
            with self.assertRaises(SystemExit):
                PM.rejeu('archive', 'racine')
            apres_echec = (PD.DEBUT, PD.FIN)
        finally:
            PD.DEBUT, PD.FIN, PD.charger, PD.rejeu = avant
        self.assertEqual(vus['dates'], (PM.DEBUT, PM.FIN))
        self.assertEqual(apres, avant[:2])
        self.assertEqual(apres_echec, avant[:2])
        self.assertEqual((n_itf, n_adj), (7, 3))
        self.assertEqual([r[6] for r in rows], ['Clay', 'Hard'])

    def test_periodes(self):
        self.assertEqual((PM.DEBUT, PM.COUPURE, PM.FIN), (dt.date(2024, 6, 1), dt.date(2025, 1, 1), dt.date(2026, 6, 1)))
        self.assertEqual((PD.DEBUT, PD.FIN), (dt.date(2025, 1, 1), dt.date(2026, 6, 1)))      # l'étude 462 n'est pas touchée


class TestSorties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jug = PM.juger(lignes({'CH': 1.35}, n=520, circuits=('CH',)), CFGS)
        with open(PM.GABARIT_JOURNAL, encoding='utf-8') as f:
            cls.gabarit = json.load(f)

    def _direct(self, d):
        os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        rnd = random.Random(2)
        M = []
        for i in range(120):
            p = min(max(rnd.random(), 0.05), 0.95)
            M.append({'home': 'Nom Secret', 'away': 'Autre Secret', 'circuit': 'CH', 'p_affiche': round(p, 4),
                      'premier': {'combinaison': {'p_home': p}},
                      'reel': {'gagnant': 'home' if rnd.random() < p else 'away', 'interrompu': None},
                      'fiabilite': ({'correction_niveau': {'source': 'simulateur/correction_niveaux.json'}} if i % 10 == 0 else {})})
        M.append({'circuit': 'CH', 'p_affiche': 0.6, 'premier': {'combinaison': {'p_home': 0.6}},
                  'reel': {'gagnant': 'home', 'interrompu': 'abandon'}})                    # abandon : pas compté
        M.append({'circuit': 'CH', 'p_affiche': 0.6, 'premier': {'combinaison': None}, 'reel': {'gagnant': 'home'}})
        with open(os.path.join(d, PM.DIRECT), 'w', encoding='utf-8') as f:
            json.dump({'matchs': M}, f)

    def test_nos_matchs_publies_comptes_seulement(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(PM.direct(d, self.jug), {'lu': False})
            self._direct(d)
            x = PM.direct(d, self.jug)
        ch = x['circuits']['CH']
        self.assertEqual(ch['matchs'], 120)
        self.assertEqual(ch['deja_corriges_par'], {'correction_niveaux.json': 12})
        self.assertEqual(ch['gain_de_la_pente_unique_du_rejeu']['matchs'], 120)
        self.assertEqual(x['circuits']['ATP']['matchs'], 0)
        self.assertNotIn('Secret', json.dumps(x, ensure_ascii=False))

    def test_entree_journal(self):
        with tempfile.TemporaryDirectory() as d:
            self._direct(d)
            en_direct = PM.direct(d, self.jug)
        e = PM.entree_journal({'jugement': self.jug, 'nos_matchs_publies': en_direct}, self.gabarit)
        self.assertEqual((e['paquet'], e['statut']), (465, 'etude'))
        self.assertIn('RÉSULTAT', e['quoi'])
        self.assertIn('Challenger', e['quoi'])
        self.assertIn('une seule pente pour le circuit', e['quoi'])
        self.assertIn('Confirmation seulement', e['quoi'])
        self.assertTrue(e['quoi'].endswith('Le % de victoire ne change pas.'))
        for texte in (e['quoi'], e['garde_fou'], PM.REGLE, PM.LIMITES, PM.PERIODE_NEUVE, PM.NON_REJOUE, PM.__doc__,
                      json.dumps(self.jug, ensure_ascii=False)):
            self.assertNotIn(INTERDIT, texte.lower())
            self.assertNotIn('cote', texte.lower())
            self.assertNotIn('bookmaker', texte.lower())

    def test_gabarit_meme_forme_que_les_autres(self):
        self.assertEqual(sorted(self.gabarit), ['date', 'garde_fou', 'paquet', 'quoi_debut', 'statut'])
        with open(os.path.join(os.path.dirname(PM.GABARIT_JOURNAL), 'paquet_462.json'), encoding='utf-8') as f:
            self.assertEqual(sorted(json.load(f)), sorted(self.gabarit))

    def test_affichage_public_sans_erreur(self):
        sortie = []
        PM.afficher(PM.juger(lignes({'CH': 1.35}, n=120), CFGS), {'lu': True, 'circuits': {'CH': {'matchs': 0}}},
                    journal=sortie.append)
        self.assertTrue(any('Challenger' in x for x in sortie))
        self.assertTrue(any('Elo seul' in x for x in sortie))
        self.assertTrue(any('nos matchs publiés' in x for x in sortie))

    def test_journal_depuis_rapport(self):
        e = PM.entree_journal({'jugement': self.jug}, self.gabarit)
        with tempfile.TemporaryDirectory() as d:
            journal, rapport = os.path.join(d, 'journal.json'), os.path.join(d, 'rapport.json')
            with open(journal, 'w', encoding='utf-8') as f:
                json.dump({'regle': 'r', 'changements': [{'paquet': 464, 'quoi': 'avant'}]}, f)
            with open(rapport, 'w', encoding='utf-8') as f:
                json.dump({'entree_journal': e}, f, ensure_ascii=False)
            ancien, PM.JOURNAL = PM.JOURNAL, journal
            try:
                self.assertEqual(PM.main(['x', '--journal-depuis-rapport', rapport]), 0)
                self.assertEqual(PM.main(['x', '--journal-depuis-rapport', rapport]), 0)      # deux fois : une seule entrée
            finally:
                PM.JOURNAL = ancien
            with open(journal, encoding='utf-8') as f:
                L = json.load(f)['changements']
            self.assertEqual([x['paquet'] for x in L], [464, 465])
            self.assertEqual(L[1]['statut'], 'etude')


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        chemin = os.path.join(RACINE, '.github', 'workflows', 'etude_pente_melange.yml')
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
        self.assertIn('python simulateur/etude_pente_melange.py /tmp/sackmann .', self.texte)
        self.assertIn('--journal-depuis-rapport /tmp/rapport_pente_melange.json', self.texte)
        self.assertIn("paths: ['simulateur/etude_pente_melange.py']", self.texte)
        self.assertNotIn(INTERDIT, self.texte.lower())

    def test_arret_sans_resultat_itf(self):
        with open(os.path.join(os.path.dirname(ICI), 'etude_pente_melange.py'), encoding='utf-8') as f:
            source = f.read()
        self.assertIn('aucun résultat ITF hommes lu', source)
        self.assertNotIn('hash(', source)
        self.assertNotIn(INTERDIT, source.lower())


if __name__ == '__main__':
    unittest.main()
