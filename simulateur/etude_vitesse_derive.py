#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_vitesse_derive.py — la vitesse des courts et la hausse du service d'année en année (22/11/2026, paquet 340,
demande de Lucas : « les courts sont de plus en plus rapides chaque année », « il faudra le faire pour tous les
circuits »).

CE QUI EST TESTÉ, circuit par circuit (ATP, WTA, Challenger ; l'ITF sert de donnée, jamais jugée) :
  probabilité de gagner un point au service = Elo service / retour d'avant-match (elo_service_retour.py : le niveau
  des deux joueurs est retiré), puis, en logit :
  • REF   : + une constante (apprise) ;
  • COURS : + β · ce que les serveurs ont gagné au-delà de l'attendu DANS CETTE ÉDITION, jusqu'à la veille (c'est ce
            que fait la production : facteurs.py, groupe « vitesse_court », qui ne connaît que les feuilles depuis
            juin 2026 — en début de tournoi elle ne sait donc rien du court) ;
  • ÉGAL  : COURS + β' · même mesure sur TOUTES les éditions précédentes du tournoi, à poids égal ;
  • RÉCENT: COURS + β' · éditions précédentes, une édition de 2 ans de plus pèse deux fois moins ;
  • DERN.  : COURS + β' · la dernière édition seulement ;
  • DÉRIVE: REF + γ · (année − 2022,5) : le service monte-t-il d'année en année au-delà de ce que l'Elo absorbe ?
  Chaque mesure d'édition est rapprochée de 0 quand elle a peu de points (K = 1 500 points en cours, 2 000 pour les
  éditions passées), et ne contient que des matchs joués AVANT le match prédit (tours précédents : l'archive date
  tous les matchs d'un tournoi du jour de son début).

RÈGLE FIXÉE AVANT DE REGARDER (22/11/2026) :
  • mesure : log loss moyenne par point au service (binomiale, par match, les deux serveurs) ;
  • APPRENTISSAGE 2018–2022 (coefficients appris ici), JUGEMENT 2023 → mai 2026 (archive, jamais vue) ; les feuilles
    TennisApi (depuis juin 2026) sont données à titre d'information ;
  • comparaisons : COURS contre REF ; ÉGAL, RÉCENT et DERN. contre COURS (le passé du tournoi ajoute-t-il quelque
    chose à ce que la production sait déjà ?) ; RÉCENT contre ÉGAL (les éditions récentes comptent-elles plus ?) ;
    DÉRIVE contre REF ;
  • RETENU pour une case (circuit × comparaison) si : gain de log loss ≥ 0,001 sur ≥ 1 000 matchs jugés, gain du même
    sens sur l'apprentissage, et significatif après correction de Holm sur TOUTES les cases (test apparié par match,
    unilatéral, 5 %) ;
  • rien n'est changé dans la production ici : une case retenue devra passer la vérification « comme en production »
    sur les feuilles (facteurs.py) avant tout usage.
DIAGNOSTIC (ne décide rien) : par circuit et par année, l'écart moyen entre points gagnés au service et attendu de
l'Elo (en points de %), et la mesure « cours » moyenne : une dérive se verrait comme un écart qui grandit.
Sortie : simulateur/rapport_vitesse_derive.json (aucun nom, aucune cote). Usage :
  python simulateur/etude_vitesse_derive.py <archive Sackmann> [racine]
"""
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_service_retour as SR  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_vitesse_derive.json')
CIRCUITS = ('ATP', 'WTA', 'CH')
APP = (dt.date(2018, 1, 1), dt.date(2023, 1, 1))
JUG = (dt.date(2023, 1, 1), dt.date(2026, 6, 1))
FEU = dt.date(2026, 6, 1)
K_COURS, K_PASSE, DEMI_VIE = 1500.0, 2000.0, 2.0
GAIN_MIN, N_MIN, ALPHA = 0.001, 1000, 0.05
ETA = 0.0015
# (nom, colonnes du modèle, référence)
MODELES = {'REF': [], 'COURS': ['cours'], 'EGAL': ['cours', 'egal'], 'RECENT': ['cours', 'recent'],
           'DERN': ['cours', 'dern'], 'DERIVE': ['an']}
COMPARAISONS = [('COURS', 'REF'), ('EGAL', 'COURS'), ('RECENT', 'COURS'), ('DERN', 'COURS'), ('RECENT', 'EGAL'),
                ('DERIVE', 'REF')]
COL = {'cours': 0, 'egal': 1, 'recent': 2, 'dern': 3, 'an': 4}


def annee_edition(d):
    return d.year + 1 if (d.month == 12 and d.day > 25) else d.year


def _sg(z):
    return 1 / (1 + math.exp(-z)) if z > -40 else 0.0


def passe(prec, an):
    """(égal, récent, dernière) depuis {année: [résidu, points]} des éditions d'avant l'année an."""
    av = [(a, v) for a, v in prec.items() if a < an]
    if not av:
        return 0.0, 0.0, 0.0
    r = sum(v[0] for _, v in av)
    p = sum(v[1] for _, v in av)
    wr = sum(v[0] * 0.5 ** ((an - a) / DEMI_VIE) for a, v in av)
    wp = sum(v[1] * 0.5 ** ((an - a) / DEMI_VIE) for a, v in av)
    a_, v_ = max(av)
    return r / (p + K_PASSE), wr / (wp + K_PASSE), v_[0] / (v_[1] + K_PASSE)


def lignes(M, eta=ETA):
    """Une ligne par match des trois circuits : (circuit, date, [(n, w, z0, x[5])] pour les deux serveurs).
    Tout est calculé AVANT le match (Elo et mesures de tournoi mis à jour à la fin de chaque jour)."""
    el, jour, attente = SR.EloSR(eta), None, []
    ED = {}                       # (circuit, tournoi) → {année: [résidu, points]}
    out = []
    for d, tour, _, c, s, t, nom, g, p, st, det in M:
        # l'archive date chaque match du jour de DÉBUT du tournoi : on met à jour à chaque changement de TOUR (un joueur
        # ne joue qu'un match par tour), sans quoi la mesure « en cours » resterait vide pendant tout le tournoi
        if (d, tour) != jour:
            for (c_, t_, an_, srvs, g_, p_, s_, st_) in attente:
                acc = ED.setdefault((c_, t_), {}).setdefault(an_, [0.0, 0.0])
                for srv, rel, n, w in srvs:
                    acc[0] += w - n * el.p_service(srv, rel, c_, s_)
                    acc[1] += n
                el.maj(g_, p_, c_, s_, st_)
            attente, jour = [], (d, tour)
        an = annee_edition(d)
        prec = ED.get((c, t), {})
        cur = prec.get(an, [0.0, 0.0])
        x_cours = cur[0] / (cur[1] + K_COURS)
        x_egal, x_rec, x_dern = passe(prec, an)
        x_an = (d.year + (d.timetuple().tm_yday - 1) / 365.25) - 2022.5
        srvs, cotes = [], []
        for srv, rel, cle in ((g, p, 'w'), (p, g, 'l')):
            n, w = st.get(cle) or (0, 0)
            if not n:
                continue
            srvs.append((srv, rel, n, w))
            z0 = math.log(max(1e-6, el.p_service(srv, rel, c, s)) / max(1e-6, 1 - el.p_service(srv, rel, c, s)))
            cotes.append((n, w, z0, (4 * x_cours, 4 * x_egal, 4 * x_rec, 4 * x_dern, x_an)))
        if c in CIRCUITS and cotes:
            out.append((c, d, cotes))
        attente.append((c, t, an, srvs, g, p, s, st))
    return out


def resoudre(A, b):
    k = len(b)
    A = [r[:] for r in A]
    b = b[:]
    for i in range(k):
        piv = max(range(i, k), key=lambda r: abs(A[r][i]))
        A[i], A[piv], b[i], b[piv] = A[piv], A[i], b[piv], b[i]
        if abs(A[i][i]) < 1e-12:
            return [0.0] * k
        for r in range(k):
            if r != i:
                f = A[r][i] / A[i][i]
                A[r] = [A[r][j] - f * A[i][j] for j in range(k)]
                b[r] -= f * b[i]
    return [b[i] / A[i][i] for i in range(k)]


def apprendre(L, cols, tours=12, ridge=1e-3):
    """Régression logistique binomiale (points gagnés sur points joués) avec l'Elo en décalage : [constante, β…]."""
    k = 1 + len(cols)
    th = [0.0] * k
    for _ in range(tours):
        g, H = [0.0] * k, [[0.0] * k for _ in range(k)]
        for _, _, cotes in L:
            for n, w, z0, x in cotes:
                v = [1.0] + [x[COL[c]] for c in cols]
                p = _sg(z0 + sum(a * b for a, b in zip(th, v)))
                r, q = w - n * p, n * p * (1 - p)
                for i in range(k):
                    g[i] += r * v[i]
                    for j in range(k):
                        H[i][j] += q * v[i] * v[j]
        for i in range(k):
            H[i][i] += ridge
            g[i] -= ridge * th[i]
        pas = resoudre(H, g)
        th = [a + b for a, b in zip(th, pas)]
        if max(abs(x) for x in pas) < 1e-7:
            break
    return th


def pertes(L, cols, th):
    """Log loss moyenne par point, une valeur par match."""
    out = []
    for _, _, cotes in L:
        tot, npts = 0.0, 0
        for n, w, z0, x in cotes:
            v = [1.0] + [x[COL[c]] for c in cols]
            p = min(max(_sg(z0 + sum(a * b for a, b in zip(th, v))), 1e-9), 1 - 1e-9)
            tot -= w * math.log(p) + (n - w) * math.log(1 - p)
            npts += n
        out.append(tot / npts)
    return out


def p_unilaterale(diffs):
    """P(gain ≤ 0) sous l'hypothèse nulle, test apparié (moyenne des différences par match, approximation normale)."""
    n = len(diffs)
    if n < 2:
        return 1.0
    m = sum(diffs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in diffs) / (n - 1))
    if sd == 0:
        return 0.0 if m > 0 else 1.0
    z = m / (sd / math.sqrt(n))
    return 0.5 * math.erfc(z / math.sqrt(2))


def holm(pv, alpha=ALPHA):
    """{clé: significatif} — correction de Holm sur toutes les cases."""
    ordre = sorted(pv, key=lambda k: pv[k])
    m, out, encore = len(ordre), {}, True
    for i, k in enumerate(ordre):
        encore = encore and pv[k] <= alpha / (m - i)
        out[k] = encore
    return out


def diagnostic(L):
    """{circuit: {année: {n, ecart_service_pts, cours_moyen_pts}}}."""
    D = {}
    for c, d, cotes in L:
        e = D.setdefault(c, {}).setdefault(str(d.year), [0, 0.0, 0.0, 0.0])
        e[0] += 1
        for n, w, z0, x in cotes:
            e[1] += w - n * _sg(z0)
            e[2] += n
            e[3] += x[0] / 4 * n
    return {c: {a: {'n': v[0], 'ecart_service_pts': round(100 * v[1] / v[2], 2) if v[2] else None,
                    'cours_moyen_pts': round(100 * v[3] / v[2], 2) if v[2] else None}
                for a, v in sorted(A.items())} for c, A in D.items()}


def etudier(L):
    rapport = {'cases': {}, 'coefs': {}}
    pv, brut = {}, {}
    for c in CIRCUITS:
        app = [r for r in L if r[0] == c and APP[0] <= r[1] < APP[1]]
        jug = [r for r in L if r[0] == c and JUG[0] <= r[1] < JUG[1]]
        feu = [r for r in L if r[0] == c and r[1] >= FEU]
        th = {m: apprendre(app, cols) for m, cols in MODELES.items()}
        rapport['coefs'][c] = {m: [round(x, 4) for x in v] for m, v in th.items()}
        P = {(m, nom): pertes(D, MODELES[m], th[m]) for m in MODELES for nom, D in (('app', app), ('jug', jug), ('feu', feu))}
        for a, b in COMPARAISONS:
            cle = f'{c}|{a}>{b}'
            dif = {nom: [y - x for x, y in zip(P[(a, nom)], P[(b, nom)])] for nom in ('app', 'jug', 'feu')}
            moy = {nom: (sum(v) / len(v) if v else None) for nom, v in dif.items()}
            pv[cle] = p_unilaterale(dif['jug'])
            brut[cle] = {'n_app': len(app), 'n_jug': len(jug), 'n_feuilles': len(feu),
                         'gain_app': round(moy['app'], 5) if moy['app'] is not None else None,
                         'gain_jug': round(moy['jug'], 5) if moy['jug'] is not None else None,
                         'gain_feuilles': round(moy['feu'], 5) if moy['feu'] is not None else None,
                         'p_jug': pv[cle]}
    sig = holm(pv)
    for cle, v in brut.items():
        raisons = []
        if v['n_jug'] < N_MIN:
            raisons.append(f"moins de {N_MIN} matchs jugés")
        if v['gain_jug'] is None or v['gain_jug'] < GAIN_MIN:
            raisons.append(f"gain jugé {v['gain_jug']} < {GAIN_MIN}")
        if v['gain_app'] is None or v['gain_app'] <= 0 or (v['gain_jug'] or 0) <= 0:
            raisons.append('pas le même sens sur les deux périodes')
        if not sig[cle]:
            raisons.append('non significatif après Holm')
        v['significatif_holm'] = sig[cle]
        v['retenu'] = not raisons
        v['raison'] = 'RETENU' if not raisons else ' ; '.join(raisons)
        rapport['cases'][cle] = v
    return rapport


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    archive, racine = argv[0], (argv[1] if len(argv) > 1 else os.path.join(ICI, '..'))
    import vitesse_courts as VC
    t0 = time.time()
    M = VC.matchs(archive, racine, depuis=2015)
    L = lignes(M)
    print(f"matchs : {len(M)} lus · {len(L)} ATP/WTA/Challenger avec feuille")
    rapport = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               'regle': "log loss par point au service ; appris 2018–2022, jugé 2023 → mai 2026 ; retenu si gain ≥ 0,001 "
                        "sur ≥ 1 000 matchs jugés, même sens sur l'apprentissage, significatif après Holm sur toutes les "
                        "cases ; rien ne change en production sans la vérification sur les feuilles",
               'diagnostic': diagnostic(L)}
    rapport.update(etudier(L))
    rapport['duree_s'] = round(time.time() - t0)
    for c, A in rapport['diagnostic'].items():
        print(c, 'écart au service par année (pts) :',
              ' '.join(f"{a}:{v['ecart_service_pts']:+.2f}" for a, v in A.items() if v['ecart_service_pts'] is not None))
    for cle, v in rapport['cases'].items():
        print(f"{cle:22} jugés {v['n_jug']:>6} · gain app {v['gain_app']} · jug {v['gain_jug']} · feuilles "
              f"{v['gain_feuilles']} → {v['raison']}")
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
