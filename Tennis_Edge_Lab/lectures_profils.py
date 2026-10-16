#!/usr/bin/env python3
"""V7.3 — « Matchs similaires passés » rejoué sur TOUS les matchs, point par point dans le temps.

Pour chaque ligne de explorateur_matchs (match, côté, horizon), on refait EXACTEMENT
la lecture de l'onglet « Matchs en direct » (direct_profils : mêmes critères, même
ordre de relâchement, même n ≥ 30, même excès vs matchs de même horizon et même
cote), mais avec SEULEMENT les matchs qui étaient connus à ce moment-là :
commencés au moins 4 h avant l'heure de décision (clôture et résultat connus).

Puis on regarde ce qui s'est passé ENSUITE pour cette ligne (sa propre CLV, son
P&L). Si les lectures « sur-coté » / « sous-coté » ne prédisent rien, elles ne
servent qu'à décrire le passé — c'est ce que ce module mesure.

Il mesure aussi si la CLV se transforme en gains :
  — fiabilité de la clôture Pinnacle sans marge : probabilité annoncée contre
    taux de victoire réel, par tranche, circuit, surface ;
  — cohérence CLV → ROI : P&L réel contre P&L attendu d'après la CLV
    (CLV Pinnacle sans marge = gain attendu par unité si la clôture est juste).

Lecture seule ; aucune ligne ne sert à choisir quoi que ce soit.
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import importlib.util
import math
import pathlib
import sys


LAB = pathlib.Path(__file__).resolve().parent


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_lp_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dp = _load("direct_profils.py")

LEADS = dict(dp.HORIZONS)                     # horizon -> minutes avant le début
DELAI_CONNU_H = 4                              # un match est « connu » 4 h après son début
VERDICTS = ("sous-coté", "sur-coté", "le marché a raison", "trop peu de matchs (n<30)")
ALPHA = 0.05


def _ts(iso):
    t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def profile_of(row):
    """Le profil « Matchs en direct » d'une ligne (grandeurs connues à l'horizon)."""
    mv = row.get("move_pin_pct")
    return {"horizon": row["horizon"], "circuit": row.get("circuit"), "surface": row.get("surface"),
            "cote_pin": row["cote_pin"], "move_dir": dp.direction(mv), "move_band": dp.band(mv, dp.MOVE_BANDS),
            "ecart_band": dp.band(row.get("ecart_jouable_pct"), dp.GAP_BANDS),
            "alerte": "non" if row.get("alerte_avant") in (None, "aucune") else "oui"}


# Niveau de relâchement à partir duquel chaque critère disparaît (ordre dp.RELAX).
_LEVEL = {name: i + 1 for i, name in enumerate(dp.RELAX)}


class _Horizon:
    """Lignes d'un horizon triées par heure de début, plus un index trié par cote.

    Bibliothèque standard seulement (le Lab tourne sans dépendance)."""

    def __init__(self, rows):
        self.rows = sorted(rows, key=lambda r: r["_start"])
        self.start = [r["_start"].timestamp() for r in self.rows]
        self.by_cote = sorted((r["cote_pin"], i) for i, r in enumerate(self.rows) if r.get("cote_pin") is not None)
        self.cotes = [c for c, _ in self.by_cote]
        self.feat = []
        for r in self.rows:
            mv = r.get("move_pin_pct")
            self.feat.append((r.get("circuit"), r.get("surface"), dp.direction(mv), dp.band(mv, dp.MOVE_BANDS),
                              dp.band(r.get("ecart_jouable_pct"), dp.GAP_BANDS) or "sans jouable",
                              "non" if r.get("alerte_avant") in (None, "aucune") else "oui",
                              r.get("clv_pinnacle"), r.get("date")))

    def min_level(self, i, p, cote):
        """Plus petit niveau de relâchement auquel la ligne i satisfait les critères du profil p
        (mêmes règles que dp.criteria + dp.row_matches ; None si jamais)."""
        circuit, surface, mdir, mband, eband, alerte, _, _ = self.feat[i]
        c0 = p["cote_pin"]
        if c0 / 1.10 <= cote <= c0 * 1.10:
            lv = 0
        elif c0 / 1.20 <= cote <= c0 * 1.20:
            lv = _LEVEL["cote20"]
        elif c0 / 1.35 <= cote <= c0 * 1.35:
            lv = _LEVEL["cote35"]
        else:
            return None
        if alerte != p["alerte"]:
            lv = max(lv, _LEVEL["alerte"])
        if eband != (p.get("ecart_band") or "sans jouable"):
            lv = max(lv, _LEVEL["ecart"])
        if p.get("move_band") and mband != p["move_band"]:
            lv = max(lv, _LEVEL["move_band"])
        if p.get("surface") not in (None, "inconnue") and surface != p["surface"]:
            lv = max(lv, _LEVEL["surface"])
        if p.get("move_dir") and mdir != p["move_dir"]:
            lv = max(lv, _LEVEL["move_dir"])
        if circuit != p["circuit"]:
            lv = max(lv, _LEVEL["circuit"])
        return lv


def lecture(H, k, profile):
    """Lecture d'un profil sur les k premières lignes (connues) d'un horizon."""
    c0 = profile["cote_pin"]
    lo = bisect.bisect_left(H.cotes, c0 / 1.35 - 1e-12)
    hi = bisect.bisect_right(H.cotes, c0 * 1.35 + 1e-12)
    cand = []                                   # (niveau, i)
    for cote, i in H.by_cote[lo:hi]:
        if i >= k:
            continue
        lv = H.min_level(i, profile, cote)
        if lv is not None:
            cand.append((lv, i))
    # n (avec CLV) à chaque niveau, cumulé
    per_level = [0] * (len(dp.RELAX) + 1)
    for lv, i in cand:
        if H.feat[i][6] is not None:
            per_level[lv] += 1
    level, n_clv = len(dp.RELAX), 0
    for L in range(len(dp.RELAX) + 1):
        n_clv += per_level[L]
        if n_clv >= dp.MIN_N:
            level = L
            break
    ok = n_clv >= dp.MIN_N
    crit = dp.criteria(profile, list(dp.RELAX[:level]))
    wlo, whi = crit["cote"]
    sel = [i for lv, i in cand if lv <= level]
    # base : CLV moyenne des lignes CONNUES de même horizon et même fenêtre de cote
    blo = bisect.bisect_left(H.cotes, wlo)
    bhi = bisect.bisect_right(H.cotes, whi)
    vals = [H.feat[i][6] for _, i in H.by_cote[blo:bhi] if i < k and H.feat[i][6] is not None]
    base = sum(vals) / len(vals) if vals else 0.0
    exces = dp.cluster_summary([None if H.feat[i][6] is None else H.feat[i][6] - base for i in sel],
                               [H.feat[i][7] for i in sel])
    clv = dp.cluster_summary([H.feat[i][6] for i in sel], [H.feat[i][7] for i in sel])
    return {"n": len(sel), "relaches": level, "ok": ok, "base": base,
            "clv": clv["mean"], "exces": exces["mean"], "exces_ci": exces["ci"], "p": exces["p"],
            "verdict": dp.verdict({"exces": exces}, ALPHA)}


def compute(rows):
    """Une lecture par ligne (même ordre que rows), point dans le temps."""
    for r in rows:
        r["_start"] = _ts(r["decision_ts"]) + dt.timedelta(minutes=LEADS[r["horizon"]])
    by_h = collections.defaultdict(list)
    for r in rows:
        if r.get("cote_pin") is not None:
            by_h[r["horizon"]].append(r)
    tables = {h: _Horizon(rs) for h, rs in by_h.items()}
    out = []
    for r in rows:
        H = tables.get(r["horizon"])
        if H is None or r.get("cote_pin") is None:
            out.append(None)
            continue
        cutoff = (_ts(r["decision_ts"]) - dt.timedelta(hours=DELAI_CONNU_H)).timestamp()
        k = bisect.bisect_right(H.start, cutoff)
        out.append(lecture(H, k, profile_of(r)))
    for r in rows:
        r.pop("_start", None)
    return out


# ---------------------------------------------------------------- évaluation après coup
def _summary(values, days):
    c = dp.cluster_summary(list(values), list(days))
    return {"n": c["n"], "moyenne": c["mean"], "ic95": c["ci"]}


def _corr(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy) if sx and sy else None


def evaluate(rows, readings):
    """Ce qui s'est passé APRÈS chaque lecture : la ligne a-t-elle fait mieux / moins bien
    que les matchs de même horizon et même cote ? (excès réalisé = sa CLV − base de la lecture)."""
    day_ix = {}
    groups = collections.defaultdict(lambda: {"exces": [], "clv": [], "roi_jouable": [], "roi_pinnacle": [], "days": []})
    quint = []
    for r, L in zip(rows, readings):
        if L is None:
            continue
        day = day_ix.setdefault(r.get("date"), len(day_ix))
        g = groups[(L["verdict"], r["horizon"])], groups[(L["verdict"], "tous")]
        realised = None if r.get("clv_pinnacle") is None else r["clv_pinnacle"] - L["base"]
        for x in g:
            x["exces"].append(realised)
            x["clv"].append(r.get("clv_pinnacle"))
            x["roi_jouable"].append(None if r.get("pnl_jouable") is None else 100 * r["pnl_jouable"])
            x["roi_pinnacle"].append(None if r.get("pnl_pinnacle") is None else 100 * r["pnl_pinnacle"])
            x["days"].append(day)
        if L["ok"] and L["exces"] is not None and realised is not None:
            quint.append((L["exces"], realised, day, None if r.get("pnl_jouable") is None else 100 * r["pnl_jouable"]))
    par_verdict = []
    for (verdict, horizon), g in sorted(groups.items(), key=lambda kv: (VERDICTS.index(kv[0][0]), kv[0][1])):
        par_verdict.append({"verdict": verdict, "horizon": horizon, "lignes": len(g["days"]),
                            "exces_realise": _summary(g["exces"], g["days"]),
                            "clv_realisee": _summary(g["clv"], g["days"]),
                            "roi_jouable": _summary(g["roi_jouable"], g["days"]),
                            "roi_pinnacle": _summary(g["roi_pinnacle"], g["days"])})
    # Par quintile de l'excès PRÉDIT : la pente dit si la lecture porte de l'information.
    par_quintile = []
    if len(quint) >= 50:
        quint.sort(key=lambda q: q[0])
        size = len(quint) / 5
        for i in range(5):
            part = quint[int(i * size): int((i + 1) * size)]
            par_quintile.append({"quintile": i + 1,
                                 "exces_predit": [part[0][0], part[-1][0]],
                                 "exces_predit_moyen": sum(p[0] for p in part) / len(part),
                                 "exces_realise": _summary([p[1] for p in part], [p[2] for p in part]),
                                 "roi_jouable": _summary([p[3] for p in part], [p[2] for p in part])})
        corr = _corr([q[0] for q in quint], [q[1] for q in quint])
    else:
        corr = None
    return {"par_verdict": par_verdict, "par_quintile": par_quintile, "correlation": corr,
            "lignes_lues": sum(1 for L in readings if L is not None)}


def _calib_bin(p):
    for lo, hi in ((.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01)):
        if lo <= p < hi:
            return f"{round(100 * lo)}–{min(100, round(100 * hi))} %"
    return None


def fiabilite(rows):
    """Clôture Pinnacle sans marge : probabilité annoncée vs taux de victoire réel.

    UN côté par match, le FAVORI à la clôture (prendre les deux côtés donnerait
    50 % contre 50 % par construction). La clôture est la même à tous les horizons.
    p juste = (1 + CLV/100) / cote d'entrée Pinnacle (identité de books.clv_pin_pct)."""
    seen, sides = set(), []
    for r in sorted(rows, key=lambda r: LEADS[r["horizon"]]):
        if r.get("gagne") is None or r.get("clv_pinnacle") is None or not r.get("cote_pin"):
            continue
        if not r.get("cloture_pin"):
            continue
        p = (1 + r["clv_pinnacle"] / 100) / r["cote_pin"]
        if p < 0.5 or r.get("_uid") in seen:
            continue
        seen.add(r.get("_uid"))
        sides.append({"p": p, "brut": 1 / r["cloture_pin"], "gagne": r["gagne"], "circuit": r.get("circuit"),
                      "surface": r.get("surface") or "inconnue", "tranche": _calib_bin(p), "date": r.get("date")})

    def table(key):
        g = collections.defaultdict(list)
        for s in sides:
            g[s[key]].append(s)
        out = []
        for k, ss in sorted(g.items(), key=lambda kv: str(kv[0])):
            n = len(ss)
            if n < 30:
                continue
            p = sum(s["p"] for s in ss) / n
            brut = sum(s["brut"] for s in ss) / n
            w = sum(s["gagne"] for s in ss) / n
            se = math.sqrt(sum(s["p"] * (1 - s["p"]) for s in ss)) / n
            z = (w - p) / se if se else None
            out.append({"groupe": k, "n": n, "proba_juste": p, "proba_brute": brut, "victoires": w,
                        "ecart_pts": 100 * (w - p), "ic95_pts": [100 * (w - p - 1.96 * se), 100 * (w - p + 1.96 * se)],
                        "z": z, "etat": "conforme" if z is None or abs(z) < 2 else ("sous-estime" if z > 0 else "surestime")})
        return out
    brier = sum((s["p"] - s["gagne"]) ** 2 for s in sides) / len(sides) if sides else None
    return {"cotes_jugees": len(sides), "brier": brier,
            "par_tranche": table("tranche"), "par_circuit": table("circuit"), "par_surface": table("surface")}


def coherence(items):
    """P&L réel vs P&L attendu d'après la CLV. items : [(cote nette, clv %, pnl)] pour des paris RÉGLÉS.

    Attendu par pari = CLV/100 (si la clôture sans marge est juste) ; variance = c²·p·(1−p).
    z = (réel − attendu) / √Σ variance : |z| < 2 cohérent, z ≤ −2 la CLV ne se transforme pas en gains."""
    items = [(c, v, g) for c, v, g in items if c and c > 1 and v is not None and g is not None]
    n = len(items)
    if not n:
        return {"n": 0, "roi_attendu": None, "roi_reel": None, "z": None, "etat": "aucun pari réglé"}
    exp = sum(v / 100 for _, v, _ in items)
    real = sum(g for _, _, g in items)
    var = 0.0
    for c, v, _ in items:
        p = min(max((1 + v / 100) / c, 1e-6), 1 - 1e-6)
        var += c * c * p * (1 - p)
    z = (real - exp) / math.sqrt(var) if var else None
    if n < 30:
        etat = "trop peu de paris"
    elif z is None or abs(z) < 2:
        etat = "cohérent"
    else:
        etat = "gains au-dessus de la CLV" if z > 0 else "la CLV ne se transforme pas en gains"
    return {"n": n, "roi_attendu": 100 * exp / n, "roi_reel": 100 * real / n, "z": z, "etat": etat}


def coherence_rows(rows):
    """Cohérence sur tous les matchs, par horizon et par prix d'entrée."""
    out = []
    for horizon in [h for h, _ in dp.HORIZONS] + ["tous"]:
        rs = [r for r in rows if horizon == "tous" or r["horizon"] == horizon]
        for entree, cote, clv, pnl in (("pinnacle", "cote_pin", "clv_pinnacle", "pnl_pinnacle"),
                                       ("jouable", "cote_jouable", "clv_jouable", "pnl_jouable"),
                                       ("fr", "cote_fr", "clv_fr", "pnl_fr")):
            c = coherence([(r.get(cote), r.get(clv), r.get(pnl)) for r in rs])
            c.update({"horizon": horizon, "entree": entree})
            out.append(c)
    return out
