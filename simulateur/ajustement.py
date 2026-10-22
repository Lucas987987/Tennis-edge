#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ajustement.py — statistiques de service et de retour AJUSTÉES AU NIVEAU DES ADVERSAIRES (22/10/2026).

Problème : un joueur qui sert très bien en Challenger face à des relanceurs faibles
paraît meilleur serveur qu'il ne l'est ; face à un joueur du circuit principal, la
simulation le surévalue.

Correction (même modèle que notes.py, étendu à chaque statistique du point) : pour
chaque composante X du point de service,
    logit P(X | A sert contre B) = mu_X[circuit, surface]
                                   + S_X[A] + S_X[A, surface]      (qualité au service)
                                   − R_X[B] − R_X[B, surface]      (qualité au retour)
  X = f   : 1re balle dans le court        (sur les points de service)
      a   : ace                            (sur les 1res balles dans le court)
      w1  : point gagné derrière la 1re    (sur les 1res balles dans le court)
      d   : double faute                   (sur les 2es balles)
      w2j : point gagné, 2e balle jouée    (sur les 2es balles jouées)
Ajustement par maximum de vraisemblance (binomiale), chaque match pondéré par son
ancienneté (demi-vie 1 an, 4 ans de données), chaque effet ramené vers 0 par un
« prior » de N0 essais (N0 × 3 pour les écarts par surface) : un joueur qui a peu
joué reste proche de la moyenne. N0 est CHOISI SUR 2023 SEULEMENT (choisir_n0 :
grille 150 / 300 / 500, vraisemblance des points des 4 mois suivant chaque
ajustement), jamais sur la période de jugement (2024 → 2026). Les joueurs qui jouent sur plusieurs circuits relient les échelles :
un Challenger qui bat des joueurs du circuit principal remonte, l'inverse aussi.

POINT-IN-TIME : ajuster(matchs, date) n'utilise que les tournois terminés avant `date`.

22/10/2026 — STATISTIQUES QUI ÉVOLUENT DANS LE TEMPS (etude_dynamique.py) : au niveau de
fond (demi-vie 1 an) s'ajoute une DÉRIVE RÉCENTE, ajustée sur la dernière année seulement
avec une demi-vie courte (45 ou 90 jours), par-dessus le niveau de fond (offset) et
ramenée vers 0 par le même prior : un joueur qui progresse (ou régresse) depuis quelques
semaines est vu comme tel, sans que trois bons matchs ne le transforment. Deux couches =
version simple du modèle d'Ingram (compétences qui dérivent semaine après semaine).
"""
import datetime as dt
import math

COMPOSANTES = ('f', 'a', 'w1', 'd', 'w2j')
N0 = 300.0
FACTEUR_SURFACE = 3.0
DEMI_VIE = 365.0
ANNEES = 4
REPLI_CIRCUIT = {'CH': 'ATP', 'ITF': 'WTA', 'ITFH': 'CH'}
REPLI = {'f': 0.62, 'a': 0.10, 'w1': 0.72, 'd': 0.08, 'w2j': 0.56}


def _sg(z):
    return 1 / (1 + math.exp(-z))


def _lg(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def essais(det, det_adv):
    """{composante: (n, k)} du serveur, depuis un tuple donnees.DETAIL (svpt, in1, w1, w2, ace, df, …)."""
    sv, in1, w1, w2, ace, df = det[:6]
    sec = sv - in1
    return {'f': (sv, in1), 'a': (in1, ace), 'w1': (in1, w1), 'd': (sec, df), 'w2j': (sec - df, w2)}


def observations(matchs, date, cle, demi_vie=DEMI_VIE, annees=ANNEES):
    """[(serveur, relanceur, (circuit, surface), surface, {comp: (n, k)}, poids)] — tournois finis avant date."""
    debut = date - dt.timedelta(days=int(365.25 * annees))
    out = []
    for m in matchs:
        d = m.get('detail')
        if not d or m['fin'] >= date or m['date'] < debut:
            continue
        w = 0.5 ** ((date - m['fin']).days / demi_vie)
        g, s = (m['circuit'], m['surface']), m['surface']
        a, b = cle(m['nom_g']), cle(m['nom_p'])
        out.append((a, b, g, s, essais(d['w'], d['l']), w))
        out.append((b, a, g, s, essais(d['l'], d['w']), w))
    return out


class Ajuste:
    def __init__(self, date, eff):
        self.date = date
        self.eff = eff          # comp -> {'mu': {g: z}, 'S': {i: x}, 'Ss': {(i, s): x}, 'R': {...}, 'Rs': {...}}

    def mu(self, comp, circuit, surface):
        M = self.eff[comp]['mu']
        for c in (circuit, REPLI_CIRCUIT.get(circuit), REPLI_CIRCUIT.get(REPLI_CIRCUIT.get(circuit))):
            if c is None:
                continue
            if (c, surface) in M:
                return M[(c, surface)]
            v = [z for (cc, _), z in M.items() if cc == c]
            if v:
                return sum(v) / len(v)
        return _lg(REPLI[comp])

    def taux(self, serveur, relanceur, circuit, surface):
        """Composantes du point quand `serveur` sert contre `relanceur` (dict f, a, w1, d, w2j)."""
        out = {}
        for c in COMPOSANTES:
            e = self.eff[c]
            z = (self.mu(c, circuit, surface) + e['S'].get(serveur, 0.0) + e['Ss'].get((serveur, surface), 0.0)
                 - e['R'].get(relanceur, 0.0) - e['Rs'].get((relanceur, surface), 0.0))
            out[c] = _sg(z)
        return out

    def connu(self, joueur):
        return joueur in self.eff['w1']['S'] or joueur in self.eff['w1']['R']

    # ------------------------------------------------------------ export / import
    def exporter(self, joueurs=None, seuil=0.004):
        def garder(d, cle_j):
            return {(f"{k[0]}|{k[1]}" if isinstance(k, tuple) else k): round(v, 3) for k, v in d.items()
                    if abs(v) >= seuil and (joueurs is None or cle_j(k) in joueurs)}
        out = {'date': self.date.isoformat()}
        for c, e in self.eff.items():
            out[c] = {'mu': {f"{g[0]}|{g[1]}": round(z, 4) for g, z in e['mu'].items()},
                      'S': garder(e['S'], lambda k: k), 'R': garder(e['R'], lambda k: k),
                      'Ss': garder(e['Ss'], lambda k: k[0]), 'Rs': garder(e['Rs'], lambda k: k[0])}
        return out

    @classmethod
    def importer(cls, doc):
        eff = {}
        for c in COMPOSANTES:
            e = doc[c]
            tup = lambda d: {tuple(k.split('|', 1)): v for k, v in d.items()}
            eff[c] = {'mu': tup(e['mu']), 'S': dict(e['S']), 'R': dict(e['R']), 'Ss': tup(e['Ss']), 'Rs': tup(e['Rs'])}
        return cls(dt.date.fromisoformat(doc['date']), eff)


class AjusteDeux:
    """Niveau de fond + dérive récente (même interface que Ajuste pour taux / connu / exporter)."""

    def __init__(self, fond, recent):
        self.fond, self.recent = fond, recent
        self.date = fond.date

    def ecart_recent(self, comp, serveur, relanceur, surface):
        e = self.recent.eff[comp]
        return (e['S'].get(serveur, 0.0) + e['Ss'].get((serveur, surface), 0.0)
                - e['R'].get(relanceur, 0.0) - e['Rs'].get((relanceur, surface), 0.0))

    def taux(self, serveur, relanceur, circuit, surface):
        t = self.fond.taux(serveur, relanceur, circuit, surface)
        return {c: _sg(_lg(t[c]) + self.ecart_recent(c, serveur, relanceur, surface)) for c in COMPOSANTES}

    def connu(self, joueur):
        return self.fond.connu(joueur)

    def exporter(self, joueurs=None, seuil=0.004):
        return dict(self.fond.exporter(joueurs, seuil), recent=self.recent.exporter(joueurs, seuil))

    @classmethod
    def importer(cls, doc):
        return cls(Ajuste.importer(doc), Ajuste.importer(doc['recent']))


def importer(doc):
    """Ajuste ou AjusteDeux selon le document exporté."""
    return AjusteDeux.importer(doc) if doc.get('recent') else Ajuste.importer(doc)


def ajuster_recent(matchs, date, cle, fond, n0=N0, demi_vie=90.0, annees=1, depart=None, tours=4):
    """Dérive récente par-dessus `fond` (Ajuste) : dernière(s) année(s), demi-vie courte."""
    rec = ajuster(matchs, date, cle, n0=n0, depart=depart, tours=tours, demi_vie=demi_vie, annees=annees, base=fond)
    return AjusteDeux(fond, rec)


def ajuster(matchs, date, cle, n0=N0, depart=None, tours=6, demi_vie=DEMI_VIE, annees=ANNEES, base=None):
    """Effets au `date` (exclu). depart : ajustement précédent (démarrage à chaud, moins de tours).
    base : un Ajuste servant de niveau de fond (offset) — les effets estimés sont alors des écarts
    à ce fond, et les moyennes mu restent à 0."""
    obs = observations(matchs, date, cle, demi_vie, annees)
    eff = {}
    off_cache = {}

    def offset(i, j, g, s, c):
        if base is None:
            return 0.0
        k = (i, j, g, s)
        if k not in off_cache:
            t = base.taux(i, j, g[0], s)
            off_cache[k] = {cc: _lg(t[cc]) for cc in COMPOSANTES}
        return off_cache[k][c]
    for c in COMPOSANTES:
        ob = [(i, j, g, s, x[c][0], x[c][1], w, offset(i, j, g, s, c)) for i, j, g, s, x, w in obs if x[c][0] > 0]
        if depart is not None:
            d = depart.eff[c]
            mu, S, Ss, R, Rs = dict(d['mu']), dict(d['S']), dict(d['Ss']), dict(d['R']), dict(d['Rs'])
        else:
            mu, S, Ss, R, Rs = {}, {}, {}, {}, {}
        tot_n = sum(w * n for _, _, _, _, n, _, w, _ in ob) or 1.0
        p_moy = sum(w * k for _, _, _, _, _, k, w, _ in ob) / tot_n
        lam = n0 * max(p_moy * (1 - p_moy), 0.02)          # prior de n0 essais (information de Fisher)
        lam_s = lam * FACTEUR_SURFACE
        for _, _, g, _, n, k, w, _ in ob:
            if g not in mu:
                mu[g] = 0.0 if base is not None else _lg(p_moy)
        for _ in range(tours):
            for etape in (('S', 'Ss', 'R', 'Rs') if base is not None else ('mu', 'S', 'Ss', 'R', 'Rs')):
                grad, hess = {}, {}
                for i, j, g, s, n, k, w, o in ob:
                    z = o + mu[g] + S.get(i, 0.0) + Ss.get((i, s), 0.0) - R.get(j, 0.0) - Rs.get((j, s), 0.0)
                    p = _sg(z)
                    gr, he = w * (k - n * p), w * n * p * (1 - p)
                    cle_e = {'mu': g, 'S': i, 'Ss': (i, s), 'R': j, 'Rs': (j, s)}[etape]
                    grad[cle_e] = grad.get(cle_e, 0.0) + (-gr if etape in ('R', 'Rs') else gr)
                    hess[cle_e] = hess.get(cle_e, 0.0) + he
                if etape == 'mu':
                    for x in grad:
                        if hess[x] > 0:
                            mu[x] += grad[x] / hess[x]
                    continue
                T, L = {'S': (S, lam), 'Ss': (Ss, lam_s), 'R': (R, lam), 'Rs': (Rs, lam_s)}[etape]
                for x in grad:
                    v = T.get(x, 0.0)
                    T[x] = v + (grad[x] - L * v) / (hess[x] + L)
        eff[c] = {'mu': mu, 'S': S, 'Ss': Ss, 'R': R, 'Rs': Rs}
    return Ajuste(date, eff)


def log_vraisemblance(A, matchs, debut, fin, cle):
    """−log-vraisemblance moyenne (par essai) des composantes des matchs [debut ; fin[ prédites par A."""
    tot, n_tot = 0.0, 0
    for m in matchs:
        d = m.get('detail')
        if not d or not (debut <= m['date'] < fin) or m['circuit'] not in ('ATP', 'WTA', 'CH'):
            continue
        a, b = cle(m['nom_g']), cle(m['nom_p'])
        for srv, ret, det, dadv in ((a, b, d['w'], d['l']), (b, a, d['l'], d['w'])):
            t = A.taux(srv, ret, m['circuit'], m['surface'])
            for c, (n, k) in essais(det, dadv).items():
                if n <= 0:
                    continue
                p = min(max(t[c], 1e-6), 1 - 1e-6)
                tot -= k * math.log(p) + (n - k) * math.log(1 - p)
                n_tot += n
    return tot / n_tot if n_tot else None


def choisir_n0(matchs, cle, grille=(150.0, 300.0, 500.0), dates=None, journal=print):
    """N0 choisi sur 2023 seulement : ajustements au 1er janvier, mai, septembre 2023, chacun jugé
    sur les 4 mois suivants. Renvoie (n0 retenu, {n0: score})."""
    dates = dates or [dt.date(2023, 1, 1), dt.date(2023, 5, 1), dt.date(2023, 9, 1)]
    scores = {}
    for n0 in grille:
        L = []
        for d in dates:
            A = ajuster(matchs, d, cle, n0=n0)
            fin = (d.replace(day=1) + dt.timedelta(days=125)).replace(day=1)
            v = log_vraisemblance(A, matchs, d, fin, cle)
            if v is not None:
                L.append(v)
        scores[n0] = sum(L) / len(L) if L else float('inf')
        journal(f"  choix du prior sur 2023 : N0 = {n0:g} -> {scores[n0]:.5f}")
    return min(scores, key=scores.get), scores


def lire_dynamique(choix):
    """Réglage « dans le temps » adopté (choix_simulation.json['dynamique']), sinon None."""
    d = (choix or {}).get('dynamique') or {}
    return d if d.get('adopte') else None


def ajuster_choisi(matchs, date, cle, n0=N0, dyn=None, depart=None, tours=6):
    """Ajustement tel que retenu par les tests : niveau de fond (demi-vie choisie) et, si adoptée,
    dérive récente par-dessus. depart : ajustement précédent (Ajuste ou AjusteDeux)."""
    h = float((dyn or {}).get('demi_vie_fond') or DEMI_VIE)
    d_fond = depart.fond if isinstance(depart, AjusteDeux) else depart
    fond = ajuster(matchs, date, cle, n0=n0, depart=d_fond, tours=tours, demi_vie=h)
    r = (dyn or {}).get('demi_vie_recent')
    if not r:
        return fond
    d_rec = depart.recent if isinstance(depart, AjusteDeux) else None
    return ajuster_recent(matchs, date, cle, fond, n0=n0, demi_vie=float(r), depart=d_rec, tours=4 if d_rec is None else 2)
