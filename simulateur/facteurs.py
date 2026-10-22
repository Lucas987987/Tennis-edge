#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
facteurs.py — ce qui fait basculer un match, au-delà du niveau habituel des joueurs (22/10/2026).

Quatre groupes de facteurs, mesurés sur les feuilles de match collectées (TennisApi),
chacun appris sur juin–août 2026 et JUGÉ sur septembre–octobre 2026, jamais vus :

  1. forme_fatigue : forme des 30 derniers jours (points gagnés au service et au retour,
     au-delà de ce que prévoit le modèle ajusté aux adversaires), sets joués les 3
     derniers jours, jours de repos — pour le serveur et pour le relanceur ;
  2. vitesse_court : ce que les joueurs obtiennent au service et en aces dans CE tournoi
     (tours déjà joués, éditions précédentes collectées), au-delà de leur niveau habituel ;
  3. morphologie : gaucher (serveur, relanceur, gaucher contre droitier), taille ;
  4. points_importants : balles de break sauvées au-delà de ce que le joueur gagne sur ses
     autres points de service (archive Sackmann + feuilles), et balles de break converties
     au retour ; plus l'effet moyen d'une balle de break.

Chaque facteur décale, en logit, les points gagnés au service (1re et 2e balle), les aces,
ou le point joué sur balle de break, PAR RAPPORT AU MODÈLE AJUSTÉ AUX ADVERSAIRES (base).
Coefficients : régression logistique avec la base en décalage (petit rappel vers 0).

RÈGLE FIXÉE D'AVANCE, par groupe : adopté si, sur septembre–octobre, il améliore la
vraisemblance des points concernés ET ne dégrade pas l'erreur (log loss) du vainqueur de la
simulation pure de plus de 0,001. (Un facteur qui touche les deux joueurs pareil — la vitesse
du court — change surtout la FORME du match : aces, jeux, tie-breaks, presque pas le
vainqueur ; il doit donc aider sur les points sans nuire au vainqueur.) Le rapport dit aussi
si le vainqueur est mieux trouvé. Les groupes adoptés sont ensuite ré-appris sur toutes les
feuilles pour les pronostics.

Usage : python simulateur/facteurs.py <archive Sackmann> [racine]
Sorties : simulateur/facteurs.json (coefficients, groupes adoptés, rapport) ;
          contexte_actuel() / exporter_contexte() pour les pronostics du jour.
"""
import collections
import datetime as dt
import heapq
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import ajustement as AJ  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as S  # noqa: E402

SORTIE = os.path.join(ICI, 'facteurs.json')
CONTEXTE = os.path.join(ICI, 'facteurs_contexte.json')
SIGMA = 0.15
DEBUT_APPR, DEBUT_JUGE = dt.date(2026, 6, 1), dt.date(2026, 9, 1)
FENETRE_FORME_J = 30
K_FORME, K_VITESSE, K_CLUTCH = 200.0, 1500.0, 60.0
DISPO_H = 3                     # un match compte dans l'historique 3 h après son début
RIDGE = 2.0
TOLERANCE_VAINQUEUR = 0.001
GROUPES = {
    'forme_fatigue': {'service': ['forme_srv', 'forme_ret_adv', 'sets3_srv', 'sets3_adv', 'repos_srv', 'repos_adv']},
    'vitesse_court': {'service': ['vit_srv'], 'aces': ['vit_ace']},
    'morphologie': {'service': ['gaucher_srv', 'gaucher_adv', 'gaucher_contre_droitier', 'taille_srv', 'taille_adv'],
                    'aces': ['taille_srv', 'gaucher_srv', 'gaucher_adv']},
    'points_importants': {'bp': ['bp_constante', 'clutch_srv', 'clutch_ret_adv']},
}


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


# ------------------------------------------------------------------ historique (accumulateurs point-in-time)
class Historique:
    """Ce qu'on sait de chaque joueur et de chaque tournoi à un instant donné."""

    def __init__(self):
        self.forme = collections.defaultdict(collections.deque)   # joueur -> (t, res_srv, n_srv, res_ret, n_ret)
        self.sets = collections.defaultdict(list)                 # joueur -> [(t, sets joués)]
        self.clutch = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])   # Σ(sauvées−attendu), Σ bp, Σ(conv−att), Σ bp obtenues
        self.vit = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])      # tournoi -> Σres srv, Σn, Σres aces, Σ in1

    def ajouter_clutch(self, j, adv, det_j, det_adv):
        sv, in1, w1, w2 = det_j[:4]
        bpf, bps = det_j[6], det_j[7]
        p = (w1 + w2) / sv if sv else 0.6
        c = self.clutch[j]
        c[0] += bps - bpf * p
        c[1] += bpf
        osv, _, ow1, ow2 = det_adv[:4]
        obpf, obps = det_adv[6], det_adv[7]
        po = (ow1 + ow2) / osv if osv else 0.6
        c[2] += (obpf - obps) - obpf * (1 - po)
        c[3] += obpf

    def ajouter(self, x):
        """x : ligne préparée (après le match)."""
        t = x['t']
        for k, j in enumerate((x['a'], x['b'])):
            r = x['srv'][k]
            ro = x['srv'][1 - k]
            self.forme[j].append((t, r['res'], r['n'], -ro['res'], ro['n']))
            self.sets[j].append((t, x['nb_sets']))
        da, db = x['det']
        self.ajouter_clutch(x['a'], x['b'], da, db)
        self.ajouter_clutch(x['b'], x['a'], db, da)
        v = self.vit[x['tournoi']]
        for r in x['srv']:
            v[0] += r['res']
            v[1] += r['n']
            v[2] += r['res_ace']
            v[3] += r['in1']

    def variables(self, j, adv, tournoi, t, infos):
        """Variables du point de vue de j au service contre adv, à l'instant t (secondes)."""
        def forme(p):
            q = self.forme[p]
            while q and q[0][0] < t - FENETRE_FORME_J * 86400:
                q.popleft()
            rs = sum(e[1] for e in q)
            ns = sum(e[2] for e in q)
            rr = sum(e[3] for e in q)
            nr = sum(e[4] for e in q)
            return rs / (ns + K_FORME), rr / (nr + K_FORME)

        def fatigue(p):
            L = self.sets[p]
            s3 = sum(s for tt, s in L if t - 3 * 86400 <= tt < t)
            der = max((tt for tt, _ in L if tt < t), default=None)
            repos = min((t - der) / 86400, 10.0) if der else 10.0
            return s3, repos

        fs, _ = forme(j)
        _, fr_adv = forme(adv)
        s3, rep = fatigue(j)
        s3a, repa = fatigue(adv)
        v = self.vit.get(tournoi) or [0.0, 0.0, 0.0, 0.0]
        cj, ca = self.clutch.get(j) or [0, 0, 0, 0], self.clutch.get(adv) or [0, 0, 0, 0]
        ij, ia = infos.get(j) or {}, infos.get(adv) or {}
        g_j, g_a = 1.0 if ij.get('main') == 'gauche' else 0.0, 1.0 if ia.get('main') == 'gauche' else 0.0
        taille = lambda i: ((i.get('taille_cm') or 185) - 185) / 10.0
        return {'forme_srv': 4 * fs, 'forme_ret_adv': 4 * fr_adv, 'sets3_srv': s3 / 3, 'sets3_adv': s3a / 3,
                'repos_srv': rep / 10, 'repos_adv': repa / 10,
                'vit_srv': 4 * v[0] / (v[1] + K_VITESSE), 'vit_ace': 10 * v[2] / (v[3] + K_VITESSE),
                'gaucher_srv': g_j, 'gaucher_adv': g_a, 'gaucher_contre_droitier': g_j * (1 - g_a),
                'taille_srv': taille(ij), 'taille_adv': taille(ia),
                'bp_constante': 1.0, 'clutch_srv': 4 * cj[0] / (cj[1] + K_CLUTCH), 'clutch_ret_adv': 4 * ca[2] / (ca[3] + K_CLUTCH)}


# ------------------------------------------------------------------ préparation des lignes
def preparer(fiches, adj_pour, cle=E.cle):
    """Lignes chronologiques des feuilles (ATP/WTA/CH, terminées, feuille complète), avec la base
    du modèle ajusté au moment du match (adj_pour(date) -> Ajuste)."""
    out = []
    for r in sorted(fiches, key=lambda r: r.get('debut') or 0):
        if FE.circuit_de(r.get('categorie')) not in ('ATP', 'WTA', 'CH') or not r.get('debut'):
            continue
        if str((r.get('statut') or {}).get('texte') or '').lower() != 'ended':
            continue
        st = (r.get('stats') or {}).get('ALL') or {}
        dh, da = FE.detail(st, 0), FE.detail(st, 2)
        if not dh or not da:
            continue
        circ, surf = FE.circuit_de(r.get('categorie')), FE.surface_de(r.get('surface'))
        a, b = cle(r['home'].get('nom')), cle(r['away'].get('nom'))
        jour = dt.date.fromisoformat(r['jour'])
        adj = adj_pour(jour)
        srv = []
        for j, o, d in ((a, b, dh), (b, a, da)):
            tx = S.borner(adj.taux(j, o, circ, surf))
            sv, in1, w1, w2, ace, df = d[:6]
            sec = sv - in1
            p = S.p_service(tx)
            srv.append({'tx': tx, 'n': sv, 'res': (w1 + w2) - sv * p, 'in1': in1, 'res_ace': ace - in1 * tx['a'],
                        'w1': (in1, w1), 'w2j': (sec - df, w2), 'ace': (in1, ace), 'bp': (d[6], d[7]), 'p': p})
        nb_sets = len(r['score_home'].get('sets') or [])
        out.append({'id': r.get('id'), 't': r['debut'], 'jour': jour, 'a': a, 'b': b, 'circuit': circ, 'surface': surf,
                    'tournoi': str(r.get('tournoi_id') or r.get('tournoi')), 'nom_tournoi': r.get('tournoi_unique') or r.get('tournoi'),
                    'srv': srv, 'det': (dh, da), 'nb_sets': nb_sets,
                    'vainqueur': 0 if r.get('vainqueur') == 1 else 1, 'bo': r.get('meilleur_des') or 3})
    return out


def infos_par_cle(racine, fiches, cle=E.cle):
    """{clé joueur: {main, taille_cm}} depuis feuilles/joueurs.json (ids) et les noms des fiches."""
    try:
        with open(os.path.join(racine, 'feuilles', 'joueurs.json'), encoding='utf-8') as f:
            J = json.load(f)
    except (OSError, ValueError):
        J = {}
    out = {}
    for r in fiches:
        for c in ('home', 'away'):
            j = r.get(c) or {}
            i = str(j.get('id'))
            if i in J:
                out[cle(j.get('nom'))] = J[i]
    return out


def avec_variables(lignes, infos, avant=None, final=False):
    """Ajoute à chaque ligne les variables point-in-time des deux serveurs ; avant : matchs de
    l'archive pour les balles de break (format donnees.charger)."""
    H = Historique()
    for m in avant or []:
        d = m.get('detail')
        if d:
            H.ajouter_clutch(E.cle(m['nom_g']), E.cle(m['nom_p']), d['w'], d['l'])
            H.ajouter_clutch(E.cle(m['nom_p']), E.cle(m['nom_g']), d['l'], d['w'])
    attente = []
    for x in lignes:
        while attente and attente[0][0] <= x['t']:
            _, _, y = heapq.heappop(attente)
            H.ajouter(y)
        x['var'] = [H.variables(x['a'], x['b'], x['tournoi'], x['t'], infos),
                    H.variables(x['b'], x['a'], x['tournoi'], x['t'], infos)]
        heapq.heappush(attente, (x['t'] + DISPO_H * 3600, x['id'] or 0, x))
    while final and attente:                    # contexte du jour : tout ce qui est joué compte
        H.ajouter(heapq.heappop(attente)[2])
    return H


# ------------------------------------------------------------------ régression logistique avec décalage
def lignes_modele(lignes, modele, feats):
    """[(n, k, offset, x)] pour le modèle 'service' (1re et 2e balle), 'aces' ou 'bp'."""
    out = []
    for x in lignes:
        for k in (0, 1):
            r, v = x['srv'][k], x['var'][k]
            xs = [v[f] for f in feats]
            if modele == 'service':
                out.append((r['w1'][0], r['w1'][1], _lg(r['tx']['w1']), xs))
                out.append((r['w2j'][0], r['w2j'][1], _lg(r['tx']['w2j']), xs))
            elif modele == 'aces':
                out.append((r['ace'][0], r['ace'][1], _lg(r['tx']['a']), xs))
            else:
                out.append((r['bp'][0], r['bp'][1], _lg(r['p']), xs))
    return [o for o in out if o[0] > 0]


def ajuster_logit(L, nf, ridge=RIDGE, tours=25):
    b = [0.0] * nf
    for _ in range(tours):
        g = [0.0] * nf
        H = [[0.0] * nf for _ in range(nf)]
        for n, k, off, x in L:
            p = _sg(off + sum(bi * xi for bi, xi in zip(b, x)))
            w = n * p * (1 - p)
            for i in range(nf):
                g[i] += (k - n * p) * x[i]
                for j in range(nf):
                    H[i][j] += w * x[i] * x[j]
        for i in range(nf):
            g[i] -= ridge * b[i]
            H[i][i] += ridge
        pas = resoudre(H, g)
        b = [bi + pi for bi, pi in zip(b, pas)]
        if max(abs(p) for p in pas) < 1e-7:
            break
    return b


def resoudre(A, y):
    n = len(y)
    M = [row[:] + [y[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def log_vrais(L, b):
    tot, n_tot = 0.0, 0
    for n, k, off, x in L:
        p = min(max(_sg(off + sum(bi * xi for bi, xi in zip(b, x))), 1e-9), 1 - 1e-9)
        tot -= k * math.log(p) + (n - k) * math.log(1 - p)
        n_tot += n
    return tot / n_tot if n_tot else None


# ------------------------------------------------------------------ deltas et vainqueur
def deltas(v, coefs):
    """(d_service, d_aces, d_bp) en logit pour un serveur, depuis ses variables et les coefficients."""
    d = {}
    for modele in ('service', 'aces', 'bp'):
        c = coefs.get(modele) or {}
        d[modele] = sum(b * v.get(f, 0.0) for f, b in c.items())
    return d['service'], d['aces'], d['bp']


def victoire_ligne(x, coefs):
    """P(vrai vainqueur) de la simulation pure (exacte), base + facteurs."""
    ca = S.appliquer_facteurs(x['srv'][0]['tx'], *deltas(x['var'][0], coefs))
    cb = S.appliquer_facteurs(x['srv'][1]['tx'], *deltas(x['var'][1], coefs))
    sg = 3 if x['bo'] == 5 else 2
    p = S.victoire_pure(ca, cb, sg, SIGMA)
    return p if x['vainqueur'] == 0 else 1 - p


def log_loss_vainqueur(lignes, coefs):
    L = [victoire_ligne(x, coefs) for x in lignes]
    if not L:
        return None, None
    ll = -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L)
    ok = sum(1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0 for p in L) / len(L)
    return round(ll, 5), round(100 * ok, 1)


def apprendre(lignes, groupes):
    """Coefficients {modèle: {variable: β}} pour un ensemble de groupes."""
    coefs = {}
    for modele in ('service', 'aces', 'bp'):
        feats = []
        for g in groupes:
            for f in GROUPES[g].get(modele, []):
                if f not in feats:
                    feats.append(f)
        if feats:
            b = ajuster_logit(lignes_modele(lignes, modele, feats), len(feats))
            coefs[modele] = {f: round(x, 5) for f, x in zip(feats, b)}
    return coefs


def juger_groupe(appr, juge, g):
    coefs = apprendre(appr, [g])
    rapport = {'coefs': coefs, 'points': {}}
    mieux_points = True
    for modele, c in coefs.items():
        L = lignes_modele(juge, modele, list(c))
        base, avec = log_vrais(L, [0.0] * len(c)), log_vrais(L, list(c.values()))
        rapport['points'][modele] = {'base': round(base, 6) if base else None, 'avec': round(avec, 6) if avec else None}
        if base is None or avec is None or avec >= base:
            mieux_points = False
    ll0, ok0 = log_loss_vainqueur(juge, {})
    ll1, ok1 = log_loss_vainqueur(juge, coefs)
    rapport['vainqueur'] = {'base': {'log_loss': ll0, 'reussite_pct': ok0}, 'avec': {'log_loss': ll1, 'reussite_pct': ok1}}
    rapport['adopte'] = bool(mieux_points and ll0 is not None and ll1 <= ll0 + TOLERANCE_VAINQUEUR)
    rapport['vainqueur_mieux_trouve'] = bool(ll0 is not None and ll1 < ll0)
    rapport['raison'] = (f"points {'mieux' if mieux_points else 'pas mieux'} ; vainqueur log loss {ll0} → {ll1} "
                         f"(réussite {ok0} % → {ok1} %)")
    return rapport


# ------------------------------------------------------------------ contexte pour les pronostics du jour
def contexte(H, infos, noms_tournois, maintenant_ts):
    """Ce que les pronostics du jour doivent savoir, à exporter en JSON."""
    t = maintenant_ts
    joueurs = {}
    tous = set(H.forme) | set(H.sets) | set(H.clutch) | set(infos)
    for j in tous:
        q = [e for e in H.forme.get(j, ()) if e[0] >= t - FENETRE_FORME_J * 86400]
        sets = [(tt, s) for tt, s in H.sets.get(j, ()) if tt >= t - 10 * 86400]
        c = H.clutch.get(j)
        i = infos.get(j) or {}
        e = {}
        if q:
            e['forme'] = [round(sum(x[1] for x in q), 2), round(sum(x[2] for x in q)), round(sum(x[3] for x in q), 2), round(sum(x[4] for x in q))]
        if sets:
            e['sets'] = [[int(tt), s] for tt, s in sets]
        if c and (c[1] or c[3]):
            e['clutch'] = [round(c[0], 2), round(c[1], 1), round(c[2], 2), round(c[3], 1)]
        if i.get('main') or i.get('taille_cm'):
            e['infos'] = {k: i[k] for k in ('main', 'taille_cm') if i.get(k)}
        if e:
            joueurs[j] = e
    vit = {k: [round(x, 2) for x in v] for k, v in H.vit.items() if v[1] > 0}
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'instant': t,
            'joueurs': joueurs, 'vitesse': vit, 'noms_tournois': noms_tournois}


class Contexte:
    """Lecture du contexte exporté : variables d'un serveur pour un match à venir."""

    def __init__(self, doc):
        self.doc = doc or {}
        self.H = Historique()
        for j, e in (self.doc.get('joueurs') or {}).items():
            if 'forme' in e:
                rs, ns, rr, nr = e['forme']
                self.H.forme[j].append((self.doc.get('instant', 0), rs, ns, rr, nr))
            for tt, s in e.get('sets') or []:
                self.H.sets[j].append((tt, s))
            if 'clutch' in e:
                self.H.clutch[j] = list(e['clutch'])
        for k, v in (self.doc.get('vitesse') or {}).items():
            self.H.vit[k] = list(v)
        self.infos = {j: e['infos'] for j, e in (self.doc.get('joueurs') or {}).items() if e.get('infos')}
        self.noms = self.doc.get('noms_tournois') or {}

    def tournoi(self, nom):
        """Identifiant du tournoi collecté dont le nom partage le plus de mots avec `nom`."""
        import nos_resultats as NR
        cible = set(NR.mots_tournoi(nom))
        best, bs = None, 0
        for k, n in self.noms.items():
            s = len(cible & set(NR.mots_tournoi(n)))
            if s > bs:
                best, bs = k, s
        return best

    def variables(self, j, adv, nom_tournoi, debut_ts):
        return self.H.variables(j, adv, self.tournoi(nom_tournoi), debut_ts, self.infos)


# ------------------------------------------------------------------ programme principal
def main(argv):
    t0 = time.time()
    dossier = argv[1] if len(argv) > 1 else 'sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    M = donnees.charger(dossier, 2016)
    fiches = FE.lire(racine)
    F = [m for m in FE.charger(racine) if not M or m['date'] > max(x['date'] for x in M)]
    tout = sorted(M + F, key=lambda m: m['date'])
    try:
        with open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8') as f:
            n0 = float(json.load(f).get('n0') or AJ.N0)
    except (OSError, ValueError):
        n0 = AJ.N0
    cache = {}

    def adj_pour(jour):
        m0 = jour.replace(day=1)
        if m0 not in cache:
            prec = cache[max(cache)] if cache else None
            cache[m0] = AJ.ajuster(tout, m0, E.cle, n0=n0, depart=prec, tours=6 if prec is None else 2)
            print(f"  base ajustée aux adversaires au {m0} ({round(time.time() - t0)} s)", flush=True)
        return cache[m0]

    lignes = preparer(fiches, adj_pour)
    infos = infos_par_cle(racine, fiches)
    H = avec_variables(lignes, infos, avant=M)
    appr = [x for x in lignes if DEBUT_APPR <= x['jour'] < DEBUT_JUGE]
    juge = [x for x in lignes if x['jour'] >= DEBUT_JUGE]
    print(f"Feuilles : {len(lignes)} matchs ATP/WTA/Challenger · apprentissage {len(appr)} (juin–août) · "
          f"jugement {len(juge)} (septembre →) · infos joueurs {len(infos)}", flush=True)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("Chaque groupe appris sur juin–août 2026, jugé sur septembre → : adopté s'il améliore la "
                     "vraisemblance des points concernés et ne dégrade pas l'erreur (log loss) du vainqueur de la "
                     "simulation pure de plus de 0,001."),
           'apprentissage': len(appr), 'jugement': len(juge), 'groupes': {}, 'adoptes': [], 'coefs': {}}
    if len(appr) < 300 or len(juge) < 300:
        doc['verdict'] = f"en attente de feuilles : {len(appr)} matchs d'apprentissage, {len(juge)} de jugement (300 de chaque au moins)"
        print(doc['verdict'])
    else:
        for g in GROUPES:
            rap = juger_groupe(appr, juge, g)
            doc['groupes'][g] = rap
            print(f"  {g:<18} {'ADOPTÉ' if rap['adopte'] else 'non adopté'} — {rap['raison']} · coefs {rap['coefs']}", flush=True)
        doc['adoptes'] = [g for g, r in doc['groupes'].items() if r['adopte']]
        if doc['adoptes']:
            doc['coefs'] = apprendre(appr + juge, doc['adoptes'])          # ré-appris sur toutes les feuilles
            ll0, ok0 = log_loss_vainqueur(juge, {})
            ll1, ok1 = log_loss_vainqueur(juge, apprendre(appr, doc['adoptes']))
            doc['ensemble_sur_le_jugement'] = {'base': {'log_loss': ll0, 'reussite_pct': ok0},
                                               'avec': {'log_loss': ll1, 'reussite_pct': ok1}}
        doc['verdict'] = f"groupes adoptés : {', '.join(doc['adoptes']) or 'aucun'}"
    doc['duree_s'] = round(time.time() - t0)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(doc['verdict'])
    return 0


def exporter_contexte(racine, M, adj, cle=E.cle):
    """Contexte actuel (pour pronostics_du_jour) : toutes les feuilles + archive ; adj = ajustement actuel."""
    fiches = FE.lire(racine)
    lignes = preparer(fiches, lambda jour: adj, cle)
    infos = infos_par_cle(racine, fiches, cle)
    H = avec_variables(lignes, infos, avant=M, final=True)
    noms = {str(r.get('tournoi_id') or r.get('tournoi')): (r.get('tournoi_unique') or r.get('tournoi') or '') for r in fiches}
    doc = contexte(H, infos, noms, dt.datetime.now(dt.timezone.utc).timestamp())
    with open(CONTEXTE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    return doc


if __name__ == '__main__':
    sys.exit(main(sys.argv))
