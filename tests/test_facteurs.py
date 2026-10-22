"""Facteurs du match (22/10/2026) : sur des feuilles synthétiques où l'on a mis une fatigue, une
vitesse de court et un avantage des gauchers (mais AUCUN effet « points importants »), l'étude
retrouve les trois premiers, les adopte, et n'adopte pas le quatrième ; variables point-in-time ;
contexte exporté relu à l'identique."""
import datetime as dt
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import ajustement as AJ  # noqa: E402
import elo as E  # noqa: E402
import facteurs as FA  # noqa: E402
import feuilles as FE  # noqa: E402
import feuilles_match as FM  # noqa: E402
import match_simule as S  # noqa: E402
import modele as MO  # noqa: E402
import joueurs_infos as JI  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402

lg = lambda p: math.log(p / (1 - p))
sg = lambda z: 1 / (1 + math.exp(-z))


def generer(graine=4):
    rnd = random.Random(graine)
    joueurs = {f"Joueur {chr(97 + i // 26)}{chr(97 + i % 26)}x": {'lvl': rnd.gauss(0, 0.25), 'gaucher': rnd.random() < 0.2}
               for i in range(90)}
    noms = list(joueurs)
    VILLES = ['Vienne', 'Bale', 'Lyon', 'Anvers', 'Stockholm', 'Metz', 'Astana', 'Tokyo', 'Pekin', 'Shanghai', 'Paris', 'Turin',
              'Madrid', 'Rome', 'Halle', 'Eastbourne', 'Gstaad', 'Hambourg', 'Kitzbuhel', 'Umag', 'Atlanta', 'Washington',
              'Montreal', 'Cincinnati', 'Winston', 'Chengdu', 'Zhuhai', 'Almaty', 'Belgrade', 'Florence', 'Naples', 'Gijon',
              'Seoul', 'Osaka', 'Ningbo', 'Wuhan', 'Monastir', 'Linz', 'Cluj', 'Hongkong']
    tournois = {k: rnd.choice((-0.25, 0.0, 0.25)) for k in range(40)}
    fiches, infos, derniers = [], {}, {}
    debut = dt.datetime(2026, 6, 1, 10, tzinfo=dt.timezone.utc)
    idm = 0
    for sem in range(21):
        for t in rnd.sample(list(tournois), 3):
            ent = rnd.sample(noms, 16)
            for rd in range(4):
                nxt = []
                for k in range(0, len(ent), 2):
                    a, b = ent[k], ent[k + 1]
                    ts = debut + dt.timedelta(days=7 * sem + rd + rnd.random() * 0.3)
                    comps = []
                    for j, o in ((a, b), (b, a)):
                        sets3 = sum(s for tt, s in derniers.get(j, []) if 0 < (ts - tt).total_seconds() <= 3 * 86400)
                        d = joueurs[j]['lvl'] - joueurs[o]['lvl'] * 0.5 + tournois[t] - 0.08 * sets3 + (0.25 if joueurs[j]['gaucher'] and not joueurs[o]['gaucher'] else 0)
                        comps.append(S.borner({'f': 0.62, 'a': sg(lg(0.10) + 2 * tournois[t]), 'w1': sg(lg(0.72) + d),
                                               'd': 0.07, 'w2j': sg(lg(0.55) + d)}))
                    g, sets, st, br, ntb = S.un_match(comps[0], comps[1], 2, 7, rnd, rnd.random() < 0.5)
                    it = lambda key, x, y, xt=None, yt=None: {'key': key, 'homeValue': x, 'homeTotal': xt, 'awayValue': y, 'awayTotal': yt}
                    h, aw = st[0], st[1]
                    stats = {'statistics': [{'period': 'ALL', 'groups': [{'statisticsItems': [
                        it('aces', h[S.ACE], aw[S.ACE]), it('doubleFaults', h[S.DF], aw[S.DF]),
                        it('firstServeAccuracy', h[S.IN1], aw[S.IN1], h[S.SVPT], aw[S.SVPT]),
                        it('firstServePointsAccuracy', h[S.W1], aw[S.W1], h[S.IN1], aw[S.IN1]),
                        it('secondServePointsAccuracy', h[S.W2], aw[S.W2], h[S.SVPT] - h[S.IN1], aw[S.SVPT] - aw[S.IN1]),
                        it('breakPointsSaved', h[S.BPS], aw[S.BPS], h[S.BPF], aw[S.BPF]), it('serviceGamesTotal', h[S.SG], aw[S.SG])]}]}]}
                    idm += 1
                    e = {'id': idm, 'startTimestamp': int(ts.timestamp()), 'winnerCode': 1 if g == 0 else 2,
                         'tournament': {'name': VILLES[t], 'uniqueTournament': {'id': t, 'name': VILLES[t], 'groundType': 'Hardcourt'}},
                         'status': {'description': 'Ended', 'type': 'finished'}, 'homeTeam': {'name': a, 'id': noms.index(a) + 1},
                         'awayTeam': {'name': b, 'id': noms.index(b) + 1},
                         'homeScore': {f'period{i + 1}': s[0] for i, s in enumerate(sets)},
                         'awayScore': {f'period{i + 1}': s[1] for i, s in enumerate(sets)}}
                    r = FM.fiche(e, 'ATP')
                    r['stats'] = FM.stats_compactes(stats)
                    fiches.append(r)
                    for j in (a, b):
                        derniers.setdefault(j, []).append((ts, len(sets)))
                    nxt.append(a if g == 0 else b)
                ent = nxt
    infos = {E.cle(j): {'main': 'gauche' if v['gaucher'] else 'droite', 'taille_cm': 185} for j, v in joueurs.items()}
    return fiches, infos, VILLES


class Facteurs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fiches, cls.infos, cls.villes = generer()
        M = [FE.en_match(r) for r in cls.fiches]
        adj = AJ.ajuster([m for m in M if m], dt.date(2026, 11, 1), E.cle, n0=150)
        cls.lignes = FA.preparer(cls.fiches, lambda jour: adj)
        FA.avec_variables(cls.lignes, cls.infos)
        cls.appr = [x for x in cls.lignes if x['jour'] < FA.DEBUT_JUGE]
        cls.juge = [x for x in cls.lignes if x['jour'] >= FA.DEBUT_JUGE]

    def test_point_in_time(self):
        x = self.lignes[0]
        self.assertEqual(x['var'][0]['sets3_srv'], 0.0)                       # premier match : aucun passé
        self.assertEqual(x['var'][0]['vit_srv'], 0.0)
        tard = [y for y in self.lignes if y['var'][0]['sets3_srv'] > 0]
        self.assertTrue(tard)

    def test_effets_retrouves_et_regle(self):
        self.assertGreater(len(self.appr), 600)
        r = {g: FA.juger_groupe(self.appr, self.juge, g) for g in ('forme_fatigue', 'vitesse_court', 'morphologie')}
        self.assertLess(r['forme_fatigue']['coefs']['service']['sets3_srv'], -0.05)     # fatigue : sert moins bien
        self.assertGreater(r['vitesse_court']['coefs']['service']['vit_srv'], 0.1)      # court rapide : service avantagé
        self.assertGreater(r['vitesse_court']['coefs']['aces']['vit_ace'], 0.1)
        # gaucher contre droitier : l'effet moyen d'un gaucher est déjà dans son niveau (modèle ajusté) ;
        # reste l'effet du DUEL, gaucher contre droitier plutôt que contre un autre gaucher
        self.assertGreater(r['morphologie']['coefs']['service']['gaucher_contre_droitier'], 0.05)
        self.assertTrue(r['vitesse_court']['adopte'], r['vitesse_court']['raison'])
        self.assertTrue(r['forme_fatigue']['adopte'], r['forme_fatigue']['raison'])
        self.assertTrue(r['forme_fatigue']['vainqueur_mieux_trouve'])
        # pas d'effet « points importants » dans ce monde : la constante reste petite
        bp = FA.juger_groupe(self.appr, self.juge, 'points_importants')
        self.assertLess(abs(bp['coefs']['bp']['bp_constante']), 0.1)

    def test_styles_et_face_a_face(self):
        vus = set()
        for x in self.lignes:
            paire = (x['a'], x['b'])
            v = x['var'][0]
            if paire not in vus and (x['b'], x['a']) not in vus:
                self.assertEqual(v['h2h_srv'], 0.0)                         # première rencontre : rien
            vus.add(paire)
            for f in ('style_ace_x_retour', 'style_1re_x_retour', 'style_2e_x_retour'):
                self.assertIn(f, v)
        self.assertTrue(any(x['var'][0]['h2h_srv'] != 0 for x in self.lignes))
        st = FA.style(None, 'x')
        self.assertEqual(st, (0.0,) * 5)
        # pas d'effet de style dans ce monde : le groupe ne trouve pas mieux le vainqueur de façon nette
        r = FA.juger_groupe(self.appr, self.juge, 'styles')
        self.assertLess(abs(r['coefs']['service']['style_1re_x_retour']), 0.3)

    def test_contexte_relu(self):
        H = FA.avec_variables([dict(x) for x in self.lignes], self.infos, final=True)
        noms = {str(t): v for t, v in enumerate(self.villes)}
        doc = FA.contexte(H, self.infos, noms, self.lignes[-1]['t'] + 3600)
        C = FA.Contexte(doc)
        x = self.lignes[-1]
        v = C.variables(x['a'], x['b'], 'ATP ' + self.villes[int(x['tournoi'])] + ' Men Singles', x['t'] + 3600)
        self.assertEqual(v['gaucher_srv'], 1.0 if self.infos[x['a']]['main'] == 'gauche' else 0.0)
        self.assertGreater(v['sets3_srv'], 0)                                  # il vient de jouer
        self.assertEqual(C.tournoi('ATP Tokyo Men Singles'), '7')


class MoteurPointsImportants(unittest.TestCase):
    def test_tenue_sans_ecart_egale_jeu(self):
        for p in (0.55, 0.62, 0.7):
            self.assertAlmostEqual(S.tenue(p, p), MO.p_jeu(p), places=12)

    def test_mieux_sur_balle_de_break_tient_plus(self):
        self.assertGreater(S.tenue(0.62, 0.70), S.tenue(0.62, 0.62))
        self.assertLess(S.tenue(0.62, 0.55), S.tenue(0.62, 0.62))
        base = S.victoire(0.64, 0.64, 2)
        self.assertAlmostEqual(base, 0.5, places=6)
        self.assertGreater(S.victoire(0.64, 0.64, 2, None, 0.3, 0.0), 0.5)

    def test_appliquer_facteurs(self):
        c = S.borner({'f': 0.62, 'a': 0.1, 'w1': 0.72, 'd': 0.07, 'w2j': 0.55})
        self.assertIs(S.appliquer_facteurs(c), c)
        x = S.appliquer_facteurs(c, 0.2, 0.0, 0.1)
        self.assertGreater(x['w1'], c['w1'])
        self.assertGreater(x['w2j'], c['w2j'])
        self.assertEqual(x['bp'], 0.1)
        self.assertGreater(S.victoire_pure(x, c, 2), 0.5)


class Infos(unittest.TestCase):
    def test_lire_infos(self):
        doc = {'team': {'name': 'X', 'playerTeamInfo': {'plays': 'Left-handed', 'height': 1.88, 'birthDateTimestamp': 946684800}}}
        self.assertEqual(JI.lire_infos(doc), {'main': 'gauche', 'taille_cm': 188, 'naissance': '2000-01-01'})
        self.assertEqual(JI.lire_infos({'plays': 'right-handed', 'height': 193})['taille_cm'], 193)
        self.assertNotIn('taille_cm', JI.lire_infos({'height': 9}))      # valeur absurde écartée
        self.assertEqual(JI.lire_infos(None), {})


class PronosticAvecFacteurs(unittest.TestCase):
    def test_impact_et_application(self):
        doc = {'instant': 0, 'joueurs': {'arthur fils': {'sets': [[1000, 3], [90000, 3]]}}, 'vitesse': {}, 'noms_tournois': {}}
        PJ.FACTEURS = {'adoptes': ['forme_fatigue'], 'coefs': {'service': {'sets3_srv': -0.3}}}
        PJ.CONTEXTE = FA.Contexte(doc)
        try:
            debut = dt.datetime.fromtimestamp(100000, dt.timezone.utc).replace(tzinfo=None)
            fct = PJ.facteurs_du_match('arthur fils', 'hugo gaston', 'ATP Brussels', debut)
            (dH, _, _), (dA, _, _) = fct['total']
            self.assertAlmostEqual(dH, -0.3 * 2.0)                     # 6 sets en 3 jours → 2 × (−0,3)
            self.assertEqual(dA, 0.0)
            c = S.borner({'f': 0.62, 'a': 0.1, 'w1': 0.72, 'd': 0.07, 'w2j': 0.55})
            imp = PJ.impact_facteurs(c, c, 2, fct)
            self.assertAlmostEqual(imp['sans'], 0.5, places=3)
            self.assertLess(imp['avec'], 0.45)                          # le joueur fatigué perd du terrain
            self.assertLess(imp['groupes']['forme_fatigue'], -5)
        finally:
            PJ.FACTEURS, PJ.CONTEXTE = None, None
        self.assertIsNone(PJ.facteurs_du_match('a', 'b', 'x', dt.datetime(2026, 10, 22)))


class ConditionsEtContexte(unittest.TestCase):
    def test_variables(self):
        H = FA.Historique()
        H.lieux = {'1': {'lon': 2.35, 'altitude': 35, 'code': 'FR', 'interieur': True},
                   '2': {'lon': -74.0, 'altitude': 2600, 'code': 'CO'}}
        H.meteo = {'2': {'2026-09-05': [31.0, 25.0, 'archive']}}
        J = 86400
        t0 = dt.datetime(2026, 9, 1, 12, tzinfo=dt.timezone.utc).timestamp()
        H.parcours['a'] = [(t0 - 60 * J, '1')]
        H.parcours['b'] = [(t0, '1'), (t0 + 2 * J, '2')]
        H.pays['a'], H.pays['b'] = 'FRA', 'COL'
        t = t0 + 4 * J
        va = H.variables('a', 'b', '2', t, {})
        self.assertAlmostEqual(va['altitude'], 2.6)
        self.assertEqual(va['interieur'], 0.0)
        self.assertAlmostEqual(va['chaleur'], 0.6)
        self.assertAlmostEqual(va['vent'], 1.0)
        self.assertEqual(va['domicile_srv'], 0.0)
        self.assertEqual(va['domicile_adv'], 1.0)                    # b est Colombien, le tournoi en Colombie
        self.assertEqual(va['absence_srv'], 1.0)                     # a n'a pas joué depuis 64 jours
        self.assertEqual(va['deja_ici_adv'], 0.25)                   # b a déjà joué un match ici
        self.assertEqual(va['voyage_srv'], 0.0)                      # a revient de trop loin dans le temps
        vb = H.variables('b', 'a', '2', t, {})
        self.assertEqual(vb['voyage_srv'], 0.0)                      # dernier match de b : ici même
        H.parcours['c'] = [(t - 3 * J, '1')]
        vc = H.variables('c', 'a', '2', t, {})
        self.assertAlmostEqual(vc['voyage_srv'], (76.35 / 15) / 6, places=3)   # Paris → Bogotá : ~5 h de décalage
        self.assertEqual(vc['enchaine_srv'], 0.2)
        vi = H.variables('a', 'b', '1', t, {})
        self.assertEqual(vi['interieur'], 1.0)
        self.assertEqual(vi['chaleur'], 0.0)
        self.assertEqual(vi['domicile_srv'], 1.0)

    def test_contexte_garde_parcours_et_lieux(self):
        H = FA.Historique()
        H.lieux = {'1': {'lon': 2.35, 'altitude': 35, 'code': 'FR'}}
        H.parcours['a'] = [(1000.0, '1')]
        H.pays['a'] = 'FRA'
        doc = FA.contexte(H, {}, {'1': 'Paris, France'}, 2000.0)
        C = FA.Contexte(json_rond(doc))
        v = C.variables('a', 'z', 'Paris', 3000.0)
        self.assertEqual(v['domicile_srv'], 1.0)
        self.assertEqual(v['deja_ici_srv'], 0.25)


def json_rond(doc):
    import json
    return json.loads(json.dumps(doc))


if __name__ == '__main__':
    unittest.main()


class Blessure(unittest.TestCase):
    def test_abandons(self):
        fiches = [{'statut': {'texte': 'Retired'}, 'vainqueur': 1, 'debut': 1000.0, 'home': {'nom': 'A B'}, 'away': {'nom': 'C D'}},
                  {'statut': {'texte': 'Ended'}, 'vainqueur': 1, 'debut': 2000.0, 'home': {'nom': 'A B'}, 'away': {'nom': 'C D'}},
                  {'statut': {'texte': 'Walkover'}, 'vainqueur': 2, 'debut': 3000.0, 'home': {'nom': 'E F'}, 'away': {'nom': 'A B'}}]
        self.assertEqual(FA.abandons_des_fiches(fiches), [(1000.0, E.cle('C D')), (3000.0, E.cle('E F'))])
        H = FA.Historique()
        J = 86400
        H.abandons['c'] = [0.0]
        v = H.variables('c', 'x', 't', 15 * J, {})
        self.assertAlmostEqual(v['abandon_srv'], 0.5)                 # demi-vie 15 jours
        self.assertAlmostEqual(v['retour_abandon_srv'], 0.5)          # pas rejoué depuis
        self.assertEqual(v['abandons90_srv'], 0.5)
        H.parcours['c'] = [(5 * J, 't')]
        self.assertEqual(H.variables('c', 'x', 't', 15 * J, {})['retour_abandon_srv'], 0.0)
        self.assertEqual(H.variables('x', 'c', 't', 15 * J, {})['abandon_adv'], 0.5)
        self.assertEqual(H.variables('c', 'x', 't', 0.0, {})['abandon_srv'], 0.0)   # rien avant l'abandon
