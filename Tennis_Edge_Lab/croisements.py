#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
croisements.py — l'issue des matchs selon les circonstances (V7.6, 21/10/2026).

Pour chaque match joué (clôture Pinnacle connue, score en sets connu, au
meilleur des 3 sets), on a un ATTENDU :
  * victoire du favori = probabilité juste de Pinnacle à la clôture (puissance,
    vérifiée sur 56 461 matchs tennis-data : 69,28 % annoncés, 69,44 % réels) ;
  * 2-0, 3 sets, set 1 = moteur du simulateur (forme du jour σ = 0,15),
    lu dans simulateur/table_sets.json.
Croiser = mesurer RÉEL − ATTENDU dans une circonstance (marché, contexte,
profils de joueurs, nos alertes). Un écart nul : la circonstance est déjà dans
la cote. Un écart net et répété : une information.

PROTOCOLE (fixé avant tout résultat) :
  * pour chaque circonstance, ses matchs sont rangés par date et coupés en deux
    moitiés : DÉCOUVERTE = la première, CONFIRMATION = la seconde (les alertes
    n'existent que depuis septembre : une date de coupure fixe les exclurait) ;
  * correction de Holm sur tous les tests de la découverte (n ≥ N_MIN) ;
  * « confirmé » = Holm < 0,05 en découverte ET même sens avec z ≥ 1,96 en
    confirmation (n ≥ N_MIN) ; « à suivre » = |z| ≥ 2 en découverte seulement.
Un croisement confirmé n'est PAS un pari : il devient une hypothèse à geler et
à juger sur la CLV. Bibliothèque standard seulement. 0 requête API.

Sortie : Tennis_Edge_Lab/live/croisements.json
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import importlib.util
import json
import math
import pathlib
import re
import sys
import unicodedata

LAB = pathlib.Path(__file__).resolve().parent
OUTPUT = "Tennis_Edge_Lab/live/croisements.json"
N_MIN = 50
CODES = ("H13", "H14", "H15", "H16", "H16B", "H17", "H18", "H19", "MISER")
ISSUES = (("victoire", "victoire du favori"), ("2-0", "favori gagne 2-0"), ("3 sets", "match en 3 sets"),
          ("set1", "favori gagne le set 1"))

_sp = importlib.util.spec_from_file_location("tennis_edge_cr_books", LAB / "books.py")
books = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(books)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def circuit(t):
    t = str(t or "").lower()
    if "wta" in t or "women" in t:
        return "WTA"
    if "itf" in t:
        return "ITF"
    if "challenger" in t:
        return "CH"
    return "ATP"


def grand_chelem(t):
    return bool(re.search(r"(wimbledon|us open|french open|roland|australian open)", str(t or ""), re.I))


def cinq_sets(t):
    t = str(t or "")
    return grand_chelem(t) and bool(re.search(r"\bmen", t, re.I)) and not re.search(r"women", t, re.I)


def juste(c1, c2):
    k = books.power_exponent(c1, c2)
    return (1 / c1) ** k if k else (1 / c1) / (1 / c1 + 1 / c2)


def lire_jsonl(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


# ------------------------------------------------------------------ table du moteur
class Table:
    def __init__(self, root):
        doc = json.loads((pathlib.Path(root) / "simulateur" / "table_sets.json").read_text(encoding="utf-8"))
        self.t = doc["circuits"]
        self.sigma = doc.get("sigma")

    def __call__(self, c, p):
        """{'2-0','2-1','1-2','0-2','set1'} pour un favori de probabilité p (≥ 0,5), interpolé."""
        L = self.t.get(c) or self.t["ATP"]
        p = min(max(p, L[0][0]), L[-1][0])
        i = min(int((p - L[0][0]) / 0.01), len(L) - 2)
        a, b = L[i], L[i + 1]
        w = (p - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
        v = [a[k] + w * (b[k] - a[k]) for k in range(1, 6)]
        return dict(zip(("2-0", "2-1", "1-2", "0-2", "set1"), v))


# ------------------------------------------------------------------ matchs
def charger_matchs(root):
    root = pathlib.Path(root)
    rows = {}
    for f in sorted(glob.glob(str(root / "clv_history" / "*.jsonl"))) + [str(root / "clv_history.jsonl")]:
        for r in lire_jsonl(f):
            if r.get("uid"):
                rows[r["uid"]] = r
    try:
        sr = json.loads((root / "set_results.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sr = {}
    joue = collections.defaultdict(set)          # joueur -> jours où il a un match
    for r in rows.values():
        d = str(r.get("commence_time") or "")[:10]
        for k in ("home", "away"):
            if r.get(k) and d:
                joue[norm(r[k])].add(d)
    out = []
    for u, r in rows.items():
        try:
            ch, ca = float(r["home_metrics"]["close"]), float(r["away_metrics"]["close"])
            oh, oa = float(r["home_metrics"]["open"]), float(r["away_metrics"]["open"])
        except (KeyError, TypeError, ValueError):
            continue
        if min(ch, ca, oh, oa) <= 1 or cinq_sets(r.get("tournament")):
            continue
        try:
            d0 = dt.date.fromisoformat(str(r.get("commence_time"))[:10])
        except ValueError:
            continue
        res, sens = (sr.get(u), 1) if u in sr else (None, 1)
        if not res:
            for d in (d0, d0 - dt.timedelta(days=1), d0 + dt.timedelta(days=1)):
                k1, k2 = f"{d}_{norm(r['home'])}_{norm(r['away'])}", f"{d}_{norm(r['away'])}_{norm(r['home'])}"
                if k1 in sr:
                    res, sens = sr[k1], 1
                    break
                if k2 in sr:
                    res, sens = sr[k2], -1
                    break
        if not res or any(res.get(k) not in ("home", "away") for k in ("match", "set1", "set2")):
            continue
        o = (lambda v: v) if sens == 1 else (lambda v: "away" if v == "home" else "home")
        m, s1, s2 = o(res["match"]), o(res["set1"]), o(res["set2"])
        if s1 == s2 and m != s1:
            continue                                   # incohérent (abandon)
        ph = juste(ch, ca)
        fav = "home" if ph >= 0.5 else "away"
        dog = "away" if fav == "home" else "home"
        pf = ph if fav == "home" else 1 - ph
        po = juste(oh, oa)
        po = po if fav == "home" else 1 - po
        jour = d0.isoformat()
        veille = (d0 - dt.timedelta(days=1)).isoformat()
        met = r.get(f"{fav}_metrics") or {}
        out.append({
            "uid": u, "jour": jour, "circuit": circuit(r.get("tournament")), "tournoi": r.get("tournament") or "",
            "favori": r[fav], "outsider": r[dog], "pf": pf, "po": po, "cote_fav": ch if fav == "home" else ca,
            "amplitude": met.get("amplitude_pct"), "points": met.get("n_points"),
            "veille_fav": veille in joue[norm(r[fav])], "veille_out": veille in joue[norm(r[dog])],
            "y_victoire": int(m == fav), "y_set1": int(s1 == fav),
            "y_2-0": int(s1 == fav and s2 == fav), "y_3 sets": int(s1 != s2),
            "cle": (jour, frozenset((norm(r["home"]), norm(r["away"])))),
        })
    return out


def notes(root):
    try:
        doc = json.loads((pathlib.Path(root) / "simulateur" / "notes_joueurs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, None
    m = {}
    for j in doc.get("joueurs", {}).values():
        k = norm(j.get("nom"))
        if k and (k not in m or j.get("points", 0) > m[k][2]):
            m[k] = (j.get("service", 0.0), j.get("retour", 0.0), j.get("points", 0))
    return m, doc.get("donnees_jusqu_au")


def alertes(root):
    """{(jour, paire) : {code: {'fav'|'out' -> True}}} — toutes les détections, envoyées ou non."""
    out = collections.defaultdict(lambda: collections.defaultdict(set))
    for code in CODES:
        nom = "miser_signal_log.jsonl" if code == "MISER" else f"{code.lower()}_signal_log.jsonl"
        for r in lire_jsonl(pathlib.Path(root) / nom):
            j, a = r.get("joueur"), r.get("adversaire")
            d = str(r.get("commence") or "")[:10]
            if not (j and a and d):
                continue
            out[(d, frozenset((norm(j), norm(a))))][code].add(norm(j))
    return out


# ------------------------------------------------------------------ statistiques
def stat(items, issue):
    """items : [(y, p)] -> n, réel %, attendu %, écart pts, z."""
    n = len(items)
    if not n:
        return {"n": 0}
    o = sum(y for y, _ in items)
    e = sum(p for _, p in items)
    v = sum(p * (1 - p) for _, p in items)
    z = (o - e) / math.sqrt(v) if v > 0 else None
    return {"n": n, "reel": round(100 * o / n, 1), "attendu": round(100 * e / n, 1),
            "ecart": round(100 * (o - e) / n, 1), "z": None if z is None else round(z, 2)}


def p_bilat(z):
    return math.erfc(abs(z) / math.sqrt(2)) if z is not None else 1.0


def holm(ps):
    """ps : {clé: p} -> {clé: p ajusté}."""
    ordre = sorted(ps.items(), key=lambda kv: kv[1])
    m, res, run = len(ordre), {}, 0.0
    for i, (k, p) in enumerate(ordre):
        run = max(run, min(1.0, (m - i) * p))
        res[k] = run
    return res


def circonstances(M, N, A):
    """[(famille, libellé, prédicat)] — définies AVANT de regarder les résultats."""
    sv = sorted(v[0] for v in N.values()) if N else []
    rt = sorted(v[1] for v in N.values()) if N else []
    q = lambda L, f: L[int(f * (len(L) - 1))] if L else 0.0
    s75, s25, r75 = q(sv, 0.75), q(sv, 0.25), q(rt, 0.75)
    nf = lambda x: N.get(norm(x["favori"]))
    no = lambda x: N.get(norm(x["outsider"]))
    al = lambda x, code, cote: code in A.get(x["cle"], {}) and (
        (norm(x["favori"]) in A[x["cle"]][code]) == (cote == "fav"))
    C = [
        ("Marché", "cote du favori < 1,30", lambda x: x["cote_fav"] < 1.30),
        ("Marché", "cote du favori 1,30–1,60", lambda x: 1.30 <= x["cote_fav"] < 1.60),
        ("Marché", "cote du favori 1,60–1,85", lambda x: 1.60 <= x["cote_fav"] < 1.85),
        ("Marché", "cote du favori ≥ 1,85", lambda x: x["cote_fav"] >= 1.85),
        ("Marché", "favori renforcé (≥ +3 pts depuis l'ouverture)", lambda x: x["pf"] - x["po"] >= 0.03),
        ("Marché", "cote stable (−3 à +3 pts)", lambda x: abs(x["pf"] - x["po"]) < 0.03),
        ("Marché", "favori affaibli (≤ −3 pts)", lambda x: x["pf"] - x["po"] <= -0.03),
        ("Marché", "outsider à l'ouverture, favori à la clôture", lambda x: x["po"] < 0.5),
        ("Marché", "forte amplitude (≥ 8 %)", lambda x: (x["amplitude"] or 0) >= 8),
        ("Marché", "peu de cotations Pinnacle (< 15)", lambda x: (x["points"] or 0) < 15),
        ("Contexte", "circuit ATP", lambda x: x["circuit"] == "ATP"),
        ("Contexte", "Challengers", lambda x: x["circuit"] == "CH"),
        ("Contexte", "circuit WTA", lambda x: x["circuit"] == "WTA"),
        ("Contexte", "ITF", lambda x: x["circuit"] == "ITF"),
        ("Contexte", "Grand Chelem (dames)", lambda x: grand_chelem(x["tournoi"])),
        ("Contexte", "qualifications", lambda x: "qualif" in x["tournoi"].lower()),
        ("Contexte", "favori a joué la veille", lambda x: x["veille_fav"] and not x["veille_out"]),
        ("Contexte", "outsider a joué la veille", lambda x: x["veille_out"] and not x["veille_fav"]),
        ("Contexte", "les deux ont joué la veille", lambda x: x["veille_fav"] and x["veille_out"]),
        ("Profils", "notes connues pour les deux joueurs", lambda x: bool(nf(x) and no(x))),
        ("Profils", "deux gros serveurs", lambda x: bool(nf(x) and no(x)) and nf(x)[0] >= s75 and no(x)[0] >= s75),
        ("Profils", "deux petits serveurs", lambda x: bool(nf(x) and no(x)) and nf(x)[0] <= s25 and no(x)[0] <= s25),
        ("Profils", "favori gros serveur, outsider gros relanceur",
         lambda x: bool(nf(x) and no(x)) and nf(x)[0] >= s75 and no(x)[1] >= r75),
        ("Alertes", "au moins une alerte (H13–H19, MISER)", lambda x: x["cle"] in A),
    ]
    for code in CODES:
        C.append(("Alertes", f"{code} sur le favori", lambda x, c=code: al(x, c, "fav")))
        C.append(("Alertes", f"{code} sur l'outsider", lambda x, c=code: al(x, c, "out")))
    return C


def build(root):
    root = pathlib.Path(root)
    T = Table(root)
    M = charger_matchs(root)
    N, notes_au = notes(root)
    A = alertes(root)
    for x in M:
        t = T(x["circuit"], x["pf"])
        x["p_victoire"], x["p_2-0"], x["p_3 sets"], x["p_set1"] = x["pf"], t["2-0"], t["2-1"] + t["1-2"], t["set1"]
    M.sort(key=lambda x: (x["jour"], x["uid"]))
    C = [("Tous", "tous les matchs", lambda x: True)] + circonstances(M, N, A)
    lignes, ps = [], {}
    for fam, lib, f in C:
        g = [x for x in M if f(x)]
        h = (len(g) + 1) // 2
        gd, gc = g[:h], g[h:]
        coupe = gc[0]["jour"] if gc else None
        for iss, _ in ISSUES:
            sd = stat([(x[f"y_{iss}"], x[f"p_{iss}"]) for x in gd], iss)
            sc = stat([(x[f"y_{iss}"], x[f"p_{iss}"]) for x in gc], iss)
            k = (fam, lib, iss)
            if sd["n"] >= N_MIN and sd.get("z") is not None:
                ps[k] = p_bilat(sd["z"])
            lignes.append({"famille": fam, "circonstance": lib, "issue": iss, "coupure": coupe,
                           "decouverte": sd, "confirmation": sc})
    H = holm(ps)
    for L in lignes:
        k = (L["famille"], L["circonstance"], L["issue"])
        d, c = L["decouverte"], L["confirmation"]
        L["p_holm"] = None if k not in H else round(H[k], 4)
        ok_d = k in H and H[k] < 0.05
        ok_c = c.get("n", 0) >= N_MIN and c.get("z") is not None and d.get("z") is not None and \
            (c["z"] >= 1.96 if d["z"] > 0 else c["z"] <= -1.96)
        L["statut"] = ("confirmé" if ok_d and ok_c else
                       "à suivre" if d.get("n", 0) >= N_MIN and d.get("z") is not None and abs(d["z"]) >= 2 else "rien")
    return {
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "protocole": "par circonstance : 1re moitié chronologique = découverte, 2de = confirmation",
        "n_min": N_MIN, "sigma": T.sigma, "notes_jusqu_au": notes_au, "matchs": len(M),
        "periode": [min((x["jour"] for x in M), default=None), max((x["jour"] for x in M), default=None)],
        "tests_holm": len(ps),
        "issues": [{"cle": k, "libelle": v} for k, v in ISSUES],
        "attendu": {"victoire": "probabilité juste Pinnacle à la clôture (méthode puissance)",
                    "autres": f"moteur du simulateur, forme du jour σ = {T.sigma}, depuis cette même probabilité"},
        "lignes": lignes,
    }


def run(sink_or_root):
    root = sink_or_root["root"] if isinstance(sink_or_root, dict) else sink_or_root
    doc = build(root)
    path = pathlib.Path(root) / OUTPUT
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        old.pop("genere_le", None)
        new = json.loads(json.dumps(doc, ensure_ascii=False))
        new.pop("genere_le", None)
        if old == new:
            return doc
    except (OSError, ValueError):
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    conf = [L for L in doc["lignes"] if L["statut"] == "confirmé"]
    suiv = [L for L in doc["lignes"] if L["statut"] == "à suivre"]
    print(f"Croisements : {doc['matchs']} matchs, "
          f"{doc['tests_holm']} tests ; {len(conf)} confirmé(s), {len(suiv)} à suivre")
    return doc


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else str(LAB.parent))
