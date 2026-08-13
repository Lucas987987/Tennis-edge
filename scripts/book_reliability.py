#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book_reliability.py — Score de fiabilité par book + détection de clusters.

CONTEXTE (mesuré sur ~1046 matchs, 08/2026) :
  1. La "paresse" d'un book est PERSISTANTE : un book en retard sur un match
     l'est structurellement, pas par hasard (rho lag_t/lag_t+1 = 0,50 à 0,90
     sur la quasi-totalité des opérateurs testés).
  2. Beaucoup de books BOUGENT ENSEMBLE (rho jusqu'à 0,90-1,00 entre paires) :
     ils partagent très probablement un flux de données commun. 3 books en
     retard simultanément peuvent donc n'être QU'UN SEUL signal répété, pas
     3 confirmations indépendantes.

CE QUE CE SCRIPT PRODUIT (book_scores.json), recalculé chaque nuit à partir
de l'historique complet (book_curves.jsonl -- jamais figé, évolue avec les
données) :
  - reliability_score : retard médian historique de chaque book (0 = très
    réactif, élevé = structurellement lent) -- indicatif, PAS un filtre.
  - cluster_id : books qui bougent ensemble (rho>=CLUSTER_RHO) regroupés
    sous le même identifiant, via composantes connexes sur le graphe de
    corrélation.

USAGE : les scripts de messages (steam_alert.py, canal_public.py) lisent ce
fichier pour ANNOTER leurs alertes -- ceci n'est PAS encore un filtre qui
change ce qui est publié. Cohérent avec la discipline du projet : une
observation, même solide, s'observe avant de piloter des décisions.
"""
import os, json, math, datetime, statistics as st
from collections import defaultdict

CURVES   = os.environ.get('CURVES', 'book_curves.jsonl')
OUT_FILE = os.environ.get('OUT', 'book_scores.json')
MIN_N_SCORE   = int(os.environ.get('MIN_N_SCORE', '15'))    # min matchs pour un score fiable
MIN_N_CLUSTER = int(os.environ.get('MIN_N_CLUSTER', '20'))  # min matchs communs pour tester une paire
CLUSTER_RHO   = float(os.environ.get('CLUSTER_RHO', '0.92'))  # relevé après test : 0.85 fusionne presque tout
EXCLUDE_BOOKS = {'pinnacle', 'betfair-ex', 'betfair', 'matchbook', 'smarkets'}
MOVE_MIN = 0.03  # seuil de mouvement Pinnacle pour qu'un match soit exploitable ici


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def shin_ph(oh, oa):
    ih, ia = 1/oh, 1/oa
    s = ih + ia
    if s <= 1:
        return ih / s
    z = 0.02
    for _ in range(40):
        ph = (math.sqrt(z*z + 4*(1-z)*ih*ih/s) - z) / (2*(1-z))
        pa = (math.sqrt(z*z + 4*(1-z)*ia*ia/s) - z) / (2*(1-z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z = min(max(z + (t-1), 0.0), 0.3)
    return ph / (ph + pa)


def spearman(xs, ys):
    def rk(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for i, idx in enumerate(order):
            r[idx] = i
        return r
    rx, ry = rk(xs), rk(ys)
    mx, my = st.mean(rx), st.mean(ry)
    cov = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
    sx = (sum((a-mx)**2 for a in rx)) ** .5
    sy = (sum((b-my)**2 for b in ry)) ** .5
    return cov / (sx*sy) if sx*sy else 0


def load_games():
    games = {}
    if not os.path.exists(CURVES):
        return games
    for line in open(CURVES, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        ct = _dt(r.get('commence_time'))
        if not ct:
            continue
        def pre(seq):
            pts = [(_dt(p[0]), p[1]) for p in (seq or []) if _dt(p[0]) and p[1] and p[1] > 1]
            return sorted(p for p in pts if p[0] < ct)
        h, a = pre(r.get('home_curve')), pre(r.get('away_curve'))
        if len(h) < 3 or len(a) < 3:
            continue
        g = games.setdefault(r['uid'], {'_ct': ct})
        g[r['book']] = {'h': h, 'a': a}
    return games


def compute_lags(games):
    """{book: {uid: lag%}} -- retard de chaque book, sur les matchs où Pinnacle
    a bougé d'au moins MOVE_MIN, au dernier point pré-match."""
    lags = defaultdict(dict)
    for uid, g in games.items():
        pin = g.get('pinnacle')
        if not pin:
            continue
        p0 = shin_ph(pin['h'][0][1], pin['a'][0][1])
        p1 = shin_ph(pin['h'][-1][1], pin['a'][-1][1])
        if abs(p1 - p0) < MOVE_MIN:
            continue
        steam = 'h' if p1 > p0 else 'a'
        fair = 1 / (p1 if steam == 'h' else 1 - p1)
        for book, sb in g.items():
            if book.startswith('_') or book in EXCLUDE_BOOKS or not isinstance(sb, dict):
                continue
            price = sb[steam][-1][1]
            if price and price > 1:
                lags[book][uid] = max(0.0, (price/fair - 1) * 100)
    return lags


def main():
    games = load_games()
    print(f"{len(games)} matchs chargés depuis {CURVES}")
    lags = compute_lags(games)

    scores = {}
    for book, series in lags.items():
        n = len(series)
        if n < MIN_N_SCORE:
            continue
        vals = list(series.values())
        # MOYENNE, pas médiane : la médiane est souvent 0 (le book suit
        # correctement la majorité du temps), ce qui écrase l'info utile.
        # La moyenne reflète la "valeur laissée sur la table" en moyenne,
        # y compris les retards occasionnels mais francs.
        pct_any_lag = 100 * sum(1 for v in vals if v > 0.5) / n
        scores[book] = {'reliability_score': round(st.mean(vals), 2),
                        'pct_any_lag': round(pct_any_lag, 0), 'n': n}
    print(f"{len(scores)} books avec un score calculable (n>={MIN_N_SCORE})")

    # ── Paires "jumelles" (rho élevé), SANS chaînage transitif ────────────
    # Un union-find naïf (testé d'abord) regroupe presque tous les books en
    # UN SEUL mega-cluster dès rho>=0.85 (A~B, B~C => A,B,C fusionnés même si
    # A et C ne se corrèlent pas directement) : inutilisable pour annoter une
    # alerte précise. On garde donc des paires DIRECTES uniquement : "ces deux
    # books précis bougent quasi à l'identique", sans effet de chaîne.
    books = [b for b in lags if len(lags[b]) >= MIN_N_CLUSTER]
    twins = defaultdict(list)   # book -> [(autre_book, rho), ...]
    pair_rhos = []
    for i, b1 in enumerate(books):
        for b2 in books[i+1:]:
            common = set(lags[b1]) & set(lags[b2])
            if len(common) < MIN_N_CLUSTER:
                continue
            xs = [lags[b1][u] for u in common]
            ys = [lags[b2][u] for u in common]
            r = spearman(xs, ys)
            pair_rhos.append((b1, b2, r, len(common)))
            if r >= CLUSTER_RHO:
                twins[b1].append([b2, round(r, 2)])
                twins[b2].append([b1, round(r, 2)])

    for b in scores:
        scores[b]['twins'] = sorted(twins.get(b, []), key=lambda x: -x[1])

    print(f"\nPaires 'jumelles' détectées (rho>={CLUSTER_RHO}, min {MIN_N_CLUSTER} matchs communs) :")
    seen = set()
    for b1, b2, r, n in sorted(pair_rhos, key=lambda x: -x[2]):
        if r < CLUSTER_RHO:
            continue
        key = tuple(sorted((b1, b2)))
        if key in seen:
            continue
        seen.add(key)
        print(f"  {b1:14} <-> {b2:14} rho={r:+.2f} (n={n})")

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'computed_at': datetime.datetime.utcnow().isoformat(),
                   'n_matches': len(games), 'scores': scores}, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {OUT_FILE} écrit : {len(scores)} books scorés, {len(seen)} paires jumelles")


if __name__ == '__main__':
    main()
