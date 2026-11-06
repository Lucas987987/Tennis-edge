#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_live_reevaluation.py — le % EN DIRECT gagne-t-il à RÉÉVALUER les joueurs pendant le match ? (06/11/2026,
question de Lucas après les paquets 201–203 : « revoir notre copie, recalculer en direct, réévaluer »).

AUJOURD'HUI (paquet 202) : le % en direct repart du score réel avec les probabilités au service d'AVANT match, fixes
pendant toute la partie (aucune réévaluation).

RÉÉVALUATION TESTÉE : la « forme du jour » du modèle (un décalage dz, en logit, du service de A et du retour contre B :
le même que la simulation de la fiche, σ = 0,15) n'est plus tirée au hasard mais LUE dans les points déjà joués :
poids de chaque forme possible ∝ loi a priori (gaussienne, σ) × vraisemblance des points de service gagnés et perdus par
chacun depuis le début du match. σ = 0 redonne exactement le % actuel. Un seul réglage : σ, appris sur l'apprentissage.

DONNÉES : les feuilles point par point TennisApi (feuilles_points/, juin → novembre 2026), matchs ATP, WTA, Challenger
terminés sans abandon, dont le déroulé redonne exactement le score final. Avant match, POINT-IN-TIME comme le pipeline :
  — probabilités au service : la base ajustée aux adversaires au 1er du mois (facteurs.preparer) ;
  — Elo d'avant le jour du match (archive Sackmann + feuilles) ;
  — % d'avant match = combinaison Elo / simulation (poids de choix_simulation.json), puis ancrage des probabilités au
    service sur ce % (comme la page) — à 0-0 toutes les variantes donnent ce même %.
MESURE : log loss du vainqueur à des moments fixés à l'avance : début de chaque set (sauf le 1er) et après 2, 4, 6, 8,
10 jeux de chaque set, et au début de chaque tie-break ; moyenne par match (chaque match pèse pareil).

RÈGLE FIXÉE LE 06/11/2026, AVANT DE REGARDER LE RÉSULTAT, circuit par circuit :
  σ appris sur juin → août 2026 dans {0 ; 0,075 ; 0,15 ; 0,225 ; 0,3 ; 0,45 ; 0,6} ; la réévaluation est ADOPTÉE si,
  sur septembre → novembre 2026 :
    a) la log loss baisse d'au moins 0,001 par rapport au % actuel (σ = 0), sur au moins 1 000 matchs jugés, ET
    b) le σ appris sur septembre → novembre est lui aussi > 0 (même sens).
  Moins de 1 000 matchs jugés → « en attente » (à relancer quand les feuilles s'accumulent).
  Adoptée → elle remplace le calcul du % en direct de la page (une ligne d'explication) ; sinon le % reste tel quel.
Usage : python simulateur/etude_live_reevaluation.py /tmp/sackmann [racine]            (étude complète)
       python simulateur/etude_live_reevaluation.py /tmp/sackmann [racine] --suivi    (chaque semaine)
"""
import collections
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

COUPURE = dt.date(2026, 9, 1)
SIGMAS = (0.0, 0.075, 0.15, 0.225, 0.3, 0.45, 0.6)
MIN_JUGES, MARGE = 1000, 0.001
CIRCUITS = ('ATP', 'WTA', 'CH')
# Gauss–Hermite (probabilistes) à 9 nœuds : z et poids pour une loi normale centrée réduite
_GH = [(-4.5127458633997, 2.23458440077e-05), (-3.2054290028565, 0.00278914132123), (-2.0768479786779, 0.0499164067652),
       (-1.0232556637891, 0.244097502895), (0.0, 0.406349206349), (1.0232556637891, 0.244097502895),
       (2.0768479786779, 0.0499164067652), (3.2054290028565, 0.00278914132123), (4.5127458633997, 2.23458440077e-05)]
SORTIE = os.path.join(ICI, 'rapport_live_reevaluation.json')
GRANDS = ('australian open', 'roland garros', 'wimbledon', 'us open')


def _lg(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 40), -40)))


# ------------------------------------------------------------------ moteur depuis un état (même logique que la page)
class Etat:
    """P(A gagne) depuis (sets, jeux, serveur) en début de jeu ; pa, pb = P(gagner le point sur SON service)."""

    def __init__(self, pa, pb, n, tbf):
        self.pa, self.pb, self.n, self.tbf = pa, pb, n, tbf
        self.m = {}
        self.ga = self._jeu(pa)
        self.gb = self._jeu(pb)

    @staticmethod
    def _jeu(p):
        q = 1 - p
        d = p * p / (1 - 2 * p * q)
        return p ** 4 * (1 + 4 * q + 10 * q * q) + 20 * p ** 3 * q ** 3 * d

    def _srv_tb(self, k, s0):
        return s0 if k == 0 or ((k - 1) >> 1) % 2 == 1 else 1 - s0

    def tb(self, i, j, s0, cible):
        if i >= cible and i - j >= 2:
            return 1.0
        if j >= cible and j - i >= 2:
            return 0.0
        pt = lambda s: self.pa if s == 0 else 1 - self.pb   # noqa: E731
        if i == j and i >= cible - 1:
            k = i + j
            p1, p2 = pt(self._srv_tb(k, s0)), pt(self._srv_tb(k + 1, s0))
            w, l_ = p1 * p2, (1 - p1) * (1 - p2)
            return w / (w + l_)
        cle = ('t', i, j, s0, cible)
        if cle in self.m:
            return self.m[cle]
        p = pt(self._srv_tb(i + j, s0))
        v = p * self.tb(i + 1, j, s0, cible) + (1 - p) * self.tb(i, j + 1, s0, cible)
        self.m[cle] = v
        return v

    def set_(self, gh, ga, srv, fin):
        """[A gagne & A sert ensuite, A gagne & B sert, B gagne & A sert, B gagne & B sert]."""
        if (gh >= 6 and gh - ga >= 2) or gh == 7:
            return (1.0 if srv == 0 else 0.0, 1.0 if srv == 1 else 0.0, 0.0, 0.0)
        if (ga >= 6 and ga - gh >= 2) or ga == 7:
            return (0.0, 0.0, 1.0 if srv == 0 else 0.0, 1.0 if srv == 1 else 0.0)
        cle = ('s', gh, ga, srv, fin)
        if cle in self.m:
            return self.m[cle]
        if gh == 6 and ga == 6:
            p = self.tb(0, 0, srv, self.tbf if fin else 7)
            v = (0.0, p, 0.0, 1 - p) if srv == 0 else (p, 0.0, 1 - p, 0.0)
        else:
            pg = self.ga if srv == 0 else 1 - self.gb
            x, y = self.set_(gh + 1, ga, 1 - srv, fin), self.set_(gh, ga + 1, 1 - srv, fin)
            v = tuple(pg * a + (1 - pg) * b for a, b in zip(x, y))
        self.m[cle] = v
        return v

    def match(self, sh, sa, srv):
        if sh >= self.n:
            return 1.0
        if sa >= self.n:
            return 0.0
        cle = ('m', sh, sa, srv)
        if cle in self.m:
            return self.m[cle]
        d = self.set_(0, 0, srv, sh == self.n - 1 and sa == self.n - 1)
        v = (d[0] * self.match(sh + 1, sa, 0) + d[1] * self.match(sh + 1, sa, 1)
             + d[2] * self.match(sh, sa + 1, 0) + d[3] * self.match(sh, sa + 1, 1))
        self.m[cle] = v
        return v

    def depuis(self, sh, sa, gh, ga, srv):
        """Début de jeu (ou de tie-break à 6-6 : srv = premier serveur du tie-break)."""
        fin = sh == self.n - 1 and sa == self.n - 1
        d = self.set_(gh, ga, srv, fin)
        return (d[0] * self.match(sh + 1, sa, 0) + d[1] * self.match(sh + 1, sa, 1)
                + d[2] * self.match(sh, sa + 1, 0) + d[3] * self.match(sh, sa + 1, 1))

    def avant_match(self):
        return 0.5 * (self.match(0, 0, 0) + self.match(0, 0, 1))


def noeuds(sigma):
    return [(0.0, 1.0)] if sigma <= 0 else [(sigma * z, w) for z, w in _GH]


def ancrer(a0, b0, p, n, tbf, sigma):
    """Décalage d (a0 + d, b0 − d en logit) tel que le % d'avant match, forme du jour comprise, vaille p."""
    la, lb, N = _lg(a0), _lg(b0), noeuds(sigma)
    lo, hi = -4.0, 4.0
    for _ in range(22):
        d = (lo + hi) / 2
        v = sum(w * Etat(_sg(la + d + z), _sg(lb - d - z), n, tbf).avant_match() for z, w in N)
        lo, hi = (d, hi) if v < p else (lo, d)
    d = (lo + hi) / 2
    return _sg(la + d), _sg(lb - d)


# ------------------------------------------------------------------ déroulé point par point
def gagnant_jeu(s, tb):
    """Vainqueur ('H'/'A') d'un jeu d'après sa suite de points, ou None si la suite est incohérente."""
    h = a = 0
    cible = 7 if tb else 4
    for i, c in enumerate(s):
        if c == 'H':
            h += 1
        elif c == 'A':
            a += 1
        else:
            return None
        if (h >= cible or a >= cible) and abs(h - a) >= 2:
            return ('H' if h > a else 'A') if i == len(s) - 1 else None
    return None


def deroule(jeux, sets_h, sets_a, n, tbf):
    """Liste des moments jugés : (sets h, sets a, jeux h, jeux a, serveur, srv A gagnés, srv A joués, srv B gagnés,
    srv B joués), ou None si le déroulé ne redonne pas le score final."""
    jeux = sorted(jeux, key=lambda g: (g[0], g[1]))
    sh = sa = gh = ga = 0
    nA = wA = nB = wB = 0
    cur_set, out, fini = 1, [], []
    for st, _, serveur, pts in jeux:
        if st != cur_set:
            return None
        srv = 0 if serveur == 1 else 1
        tb = gh == 6 and ga == 6
        fin = sh == n - 1 and sa == n - 1
        cible_tb = tbf if fin else 7
        if tb:
            g = None
            h = a = 0
            for c in pts:
                h += c == 'H'
                a += c == 'A'
            if (h >= cible_tb or a >= cible_tb) and abs(h - a) >= 2 and all(c in 'HA' for c in pts):
                g = 'H' if h > a else 'A'
        else:
            g = gagnant_jeu(pts, False)
        if g is None:
            return None
        jeux_set = gh + ga
        if (jeux_set == 0 and (sh + sa) > 0) or (jeux_set in (2, 4, 6, 8, 10) and not tb) or tb:
            out.append((sh, sa, gh, ga, srv, wA, nA, wB, nB))
        # points de service
        for k, c in enumerate(pts):
            s = srv if not tb else (srv if k == 0 or ((k - 1) >> 1) % 2 == 1 else 1 - srv)
            if s == 0:
                nA += 1
                wA += c == 'H'
            else:
                nB += 1
                wB += c == 'A'
        if g == 'H':
            gh += 1
        else:
            ga += 1
        if (gh >= 6 and gh - ga >= 2) or (ga >= 6 and ga - gh >= 2) or gh == 7 or ga == 7:
            fini.append((gh, ga))
            sh, sa = sh + (gh > ga), sa + (ga > gh)
            gh = ga = 0
            cur_set += 1
    if [x for x, _ in fini] != list(sets_h) or [y for _, y in fini] != list(sets_a):
        return None
    if max(sh, sa) != n:
        return None
    return out


def p_live(a, b, n, tbf, sigma, m, lire=True):
    """P(A gagne) au moment m, forme du jour lue dans les points déjà joués (σ = 0 : % actuel de la page).
    lire=False (contrôle) : même mélange de formes, sans lire les points."""
    sh, sa, gh, ga, srv, wA, nA, wB, nB = m
    if not lire:
        wA = nA = wB = nB = 0
    la, lb = _lg(a), _lg(b)
    post, tot = [], 0.0
    for z, w in noeuds(sigma):
        pa, pb = _sg(la + z), _sg(lb - z)
        lw = math.log(w) + wA * math.log(pa) + (nA - wA) * math.log(1 - pa) + wB * math.log(pb) + (nB - wB) * math.log(1 - pb)
        post.append((lw, pa, pb))
    mx = max(x[0] for x in post)
    v = 0.0
    for lw, pa, pb in post:
        e = math.exp(lw - mx)
        tot += e
        v += e * Etat(pa, pb, n, tbf).depuis(sh, sa, gh, ga, srv)
    return v / tot


# ------------------------------------------------------------------ données point-in-time
def lignes_matchs(archive, racine):
    import ajustement as AJ
    import donnees
    import elo as E
    import facteurs as FC
    import feuilles as FE
    M = donnees.charger(archive, 2016)
    fiches = FE.lire(racine)
    fin_sack = max(x['date'] for x in M) if M else None
    F = [m for m in FE.charger(racine) if fin_sack is None or m['date'] > fin_sack]
    tout = sorted(M + F, key=lambda m: m['date'])
    try:
        with open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        choix = {}
    poids = (choix.get('combinaison') or {}).get('poids') or choix.get('combinaison') or {}
    w_elo, w_sim = float(poids.get('elo', 0.7816)), float(poids.get('simulation', 0.2377))
    n0 = float(choix.get('n0') or AJ.N0)
    cache = {}

    def adj_pour(jour):
        m0 = jour.replace(day=1)
        if m0 not in cache:
            prec = cache[max(cache)] if cache else None
            cache[m0] = AJ.ajuster_choisi(tout, m0, E.cle, n0=n0, dyn=AJ.lire_dynamique(choix), depart=prec,
                                          tours=6 if prec is None else 2,
                                          n0_par_composante=choix.get('n0_par_composante') or None)
            print(f"  base ajustée au {m0}", flush=True)
        return cache[m0]

    L = [x for x in FC.preparer(fiches, adj_pour) if x['jour'] >= dt.date(2026, 6, 1)]
    # Elo d'avant le jour du match
    L.sort(key=lambda x: x['jour'])
    el, i, jour, attente = E.Elo(), 0, None, []
    k = E.cle
    for m in tout:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
            while i < len(L) and L[i]['jour'] <= d:
                x = L[i]
                x['p_elo'] = min(max(el.proba(x['a'], x['b'], x['surface']), 0.01), 0.99)
                i += 1
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        if m['circuit'] in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        attente.append((g, p, m['surface'], m.get('niveau') == 'G'))
    for g, p, s, gc in attente:
        el.maj(g, p, s, gc, None)
    while i < len(L):
        x = L[i]
        x['p_elo'] = min(max(el.proba(x['a'], x['b'], x['surface']), 0.01), 0.99)
        i += 1
    return L, (w_elo, w_sim), fiches


def juger_match(t):
    c, jour, a0, b0, p_elo, w_elo, w_sim, n, tbf, y, mom = t[:11]
    sigmas = t[11] if len(t) > 11 else SIGMAS
    p_sim = sum(w * Etat(_sg(_lg(a0) + z), _sg(_lg(b0) - z), n, tbf).avant_match() for z, w in noeuds(0.15))
    p = _sg(w_elo * _lg(p_elo) + w_sim * _lg(p_sim))
    ll = {}
    for s in sigmas:
        a, b = ancrer(a0, b0, p, n, tbf, s)
        tot = 0.0
        for m in mom:
            q = min(max(p_live(a, b, n, tbf, s, m), 1e-6), 1 - 1e-6)
            tot -= math.log(q if y else 1 - q)
        ll[s] = tot / len(mom)
        if s in (0.15, 0.225) and sigmas is SIGMAS:  # contrôle (étude complète seulement) : le mélange seul, sans réévaluation
            tot = 0.0
            for m in mom:
                q = min(max(p_live(a, b, n, tbf, s, m, lire=False), 1e-6), 1 - 1e-6)
                tot -= math.log(q if y else 1 - q)
            ll[f'sans_lecture_{s}'] = tot / len(mom)
    return {'c': c, 'jour': jour, 'll': ll, 'n_moments': len(mom), 'p_avant': p, 'y': y}


def construire_taches(L, P, scores, w_elo, w_sim, sigmas=None):
    taches, rejets = [], collections.Counter()
    for x in L:
        jeux = P.get(x['id'])
        if not jeux:
            rejets['sans point par point'] += 1
            continue
        n = 3 if x['bo'] == 5 else 2
        tbf = 10 if any(g in str(x.get('nom_tournoi') or '').lower() for g in GRANDS) else 7
        sh_, sa_ = scores.get(x['id'], ([], []))
        mom = deroule(jeux, sh_, sa_, n, tbf)
        if not mom:
            rejets['déroulé incohérent avec le score'] += 1
            continue
        t = (x['circuit'], x['jour'], x['srv'][0]['p'], x['srv'][1]['p'], x['p_elo'], w_elo, w_sim, n, tbf,
             1 if x['vainqueur'] == 0 else 0, mom)
        if sigmas is not None:
            t = t + (sigmas,)
        taches.append(t)
    return taches, rejets


def rejouer(taches, t0):
    import multiprocessing as mp
    rows = []
    with mp.Pool(max(1, os.cpu_count() or 1)) as pool:
        for r in pool.imap_unordered(juger_match, taches, chunksize=20):
            rows.append(r)
            if len(rows) % 500 == 0:
                print(f"  {len(rows)} matchs ({round(time.time() - t0)} s)", flush=True)
    return rows


def _charger(archive, racine):
    import facteurs as FC
    L, (w_elo, w_sim), fiches = lignes_matchs(archive, racine)
    P = FC.charger_points(racine)
    scores = {r.get('id'): (r['score_home'].get('sets') or [], r['score_away'].get('sets') or []) for r in fiches}
    return L, P, scores, w_elo, w_sim


def etude(archive, racine):
    t0 = time.time()
    L, P, scores, w_elo, w_sim = _charger(archive, racine)
    taches, rejets = construire_taches(L, P, scores, w_elo, w_sim)
    print(f"{len(taches)} matchs à rejouer · rejets {dict(rejets)}", flush=True)
    rows = rejouer(taches, t0)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par circuit : σ appris juin → août 2026 ; réévaluation adoptée si sur sept. → nov. 2026 la log loss "
                     "baisse d'au moins 0,001 face au % actuel (σ = 0) sur ≥ 1 000 matchs jugés, et σ appris sur "
                     "sept. → nov. aussi > 0"),
           'matchs_retenus': len(rows), 'rejets': dict(rejets), 'circuits': {}}

    def moy(R, s):
        return sum(r['ll'][s] for r in R) / len(R) if R else None

    for c in CIRCUITS + ('tous',):
        R = [r for r in rows if c == 'tous' or r['c'] == c]
        ap, ju = [r for r in R if r['jour'] < COUPURE], [r for r in R if r['jour'] >= COUPURE]
        if not ap or not ju:
            doc['circuits'][c] = {'matchs': {'appr': len(ap), 'juge': len(ju)}, 'verdict': 'pas assez de matchs'}
            continue
        s_ap = min(SIGMAS, key=lambda s: moy(ap, s))
        s_ju = min(SIGMAS, key=lambda s: moy(ju, s))
        gain = moy(ju, 0.0) - moy(ju, s_ap)
        ok = len(ju) >= MIN_JUGES and gain >= MARGE and s_ap > 0 and s_ju > 0
        verdict = ('ADOPTÉE' if ok else ('en attente (moins de 1 000 matchs jugés)' if len(ju) < MIN_JUGES and c != 'tous'
                                         else 'non adoptée'))
        doc['circuits'][c] = {
            'matchs': {'appr': len(ap), 'juge': len(ju)},
            'sigma_appris_juin_aout': s_ap, 'sigma_appris_sept_nov': s_ju,
            'log_loss_juge': {str(s): round(moy(ju, s), 5) for s in SIGMAS},
            'log_loss_appr': {str(s): round(moy(ap, s), 5) for s in SIGMAS},
            'gain_juge': round(gain, 5),
            'controle_meme_melange_sans_lire_les_points': {k: round(moy(ju, k), 5)
                                                           for k in ('sans_lecture_0.15', 'sans_lecture_0.225')},
            'verdict': verdict if c != 'tous' else 'information'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(doc, ensure_ascii=False, indent=1, default=str))
    return 0


# ------------------------------------------------------------------ en place + suivi chaque semaine (06/11/2026)
# Décision de Lucas le 06/11/2026 : ADOPTION DIRECTE sur les trois circuits (ATP et WTA sous le seuil de 1 000 matchs
# jugés, même gain et même σ que le Challenger), avec la règle de retrait habituelle : chaque semaine, la dernière
# semaine complète (lundi → dimanche) est jugée par circuit ; σ en place contre σ = 0. RETRAIT après 2 semaines de
# suite moins bonnes ; RETOUR après 2 semaines de suite meilleures. Moins de 30 matchs dans la semaine : rien à
# conclure, la série ne bouge pas.
ETAT = os.path.join(ICI, 'live_reevaluation.json')
SIGMA_EN_PLACE = {'ATP': 0.15, 'WTA': 0.15, 'CH': 0.225}
MIN_SEMAINE = 30


def lire_etat(chemin=ETAT):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'sigma': dict(SIGMA_EN_PLACE), 'en_place': {c: True for c in CIRCUITS},
                'series': {c: {'pire': 0, 'mieux': 0} for c in CIRCUITS}, 'semaines': []}


def sigma_site(etat):
    """σ publié pour la page : 0 pour un circuit retiré."""
    return {c: (etat['sigma'].get(c, 0.0) if etat['en_place'].get(c) else 0.0) for c in CIRCUITS}


def appliquer_semaine(etat, semaine, mesures):
    """mesures : {circuit: (matchs, log loss σ = 0, log loss σ en place)} → état mis à jour (une fois par semaine)."""
    if any(x.get('semaine') == semaine for x in etat.get('semaines', [])):
        return etat
    ligne = {'semaine': semaine, 'circuits': {}}
    for c in CIRCUITS:
        n, l0, l1 = mesures.get(c, (0, None, None))
        sr = etat['series'].setdefault(c, {'pire': 0, 'mieux': 0})
        if n < MIN_SEMAINE or l0 is None:
            ligne['circuits'][c] = {'matchs': n, 'verdict': 'rien à conclure'}
            continue
        mieux = l1 < l0
        sr['mieux'], sr['pire'] = (sr['mieux'] + 1, 0) if mieux else (0, sr['pire'] + 1)
        avant = etat['en_place'].get(c, True)
        if avant and sr['pire'] >= 2:
            etat['en_place'][c] = False
        elif not avant and sr['mieux'] >= 2:
            etat['en_place'][c] = True
        ligne['circuits'][c] = {'matchs': n, 'log_loss_actuel': round(l0, 5), 'log_loss_reevalue': round(l1, 5),
                                'gain': round(l0 - l1, 5), 'en_place': etat['en_place'][c]}
    etat.setdefault('semaines', []).append(ligne)
    etat['semaines'] = etat['semaines'][-26:]
    return etat


def suivi(archive, racine, aujourdhui=None):
    t0 = time.time()
    aujourdhui = aujourdhui or dt.datetime.now(dt.timezone.utc).date()
    fin = aujourdhui - dt.timedelta(days=aujourdhui.weekday())          # lundi de cette semaine (exclu)
    debut = fin - dt.timedelta(days=7)
    etat = lire_etat()
    L, P, scores, w_elo, w_sim = _charger(archive, racine)
    L = [x for x in L if debut <= x['jour'] < fin]
    taches = []
    for c in CIRCUITS:
        t, _ = construire_taches([x for x in L if x['circuit'] == c], P, scores, w_elo, w_sim,
                                 sigmas=(0.0, etat['sigma'].get(c, SIGMA_EN_PLACE[c])))
        taches += t
    rows = rejouer(taches, t0)
    mesures = {}
    for c in CIRCUITS:
        R = [r for r in rows if r['c'] == c]
        s1 = etat['sigma'].get(c, SIGMA_EN_PLACE[c])
        mesures[c] = (len(R), sum(r['ll'][0.0] for r in R) / len(R) if R else None,
                      sum(r['ll'][s1] for r in R) / len(R) if R else None)
    etat = appliquer_semaine(etat, str(debut), mesures)
    etat['maj'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    with open(ETAT, 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, indent=1)
    print(json.dumps(etat['semaines'][-1], ensure_ascii=False, indent=1))
    return 0


def main(argv):
    if '--suivi' in argv:
        a = [x for x in argv if x != '--suivi']
        return suivi(a[1], a[2] if len(a) > 2 else os.path.join(ICI, '..'))
    return etude(argv[1], argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
