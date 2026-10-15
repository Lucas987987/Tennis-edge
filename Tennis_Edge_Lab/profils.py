#!/usr/bin/env python3
"""V6.8 — Profil automatique des hypothèses (lecture seule, aucun gel).

Pour chaque sujet (H13…H18 selon deux sources, PUBLIC, MOUVEMENT, gels de
l'Explorateur) et chaque critère connu AVANT la décision (circuit, surface,
cote, favori/outsider, délai, ampleur, famille de book, mouvement Pinnacle),
le module teste si la CLV Pinnacle (dé-margination puissance) diffère selon
les modalités, puis rédige des phrases prudentes.

Test d'hétérogénéité : test de Wald de type Welch (variances inégales) sur les
moyennes de CLV par modalité, avec erreurs-types robustes aux grappes par
jour (plusieurs alertes d'un même jour ne sont pas indépendantes) ; la
statistique suit asymptotiquement un χ² à g−1 degrés de liberté. Choix
justifié : la CLV est une variable continue aux queues modérées (pas des
gains 0/1 à grosses cotes), Kruskal–Wallis ne sait pas tenir compte des
grappes par jour, et une ANOVA classique supposerait des variances égales,
fausses entre circuits. Holm est appliqué sur TOUS les tests du jour.

Règles des phrases (jamais de conclusion positive à partir du ROI seul) :
 ✅ Écart prouvé : p Holm < 0,05, modalité avec n ≥ 30 et p (vs reste) < 0,05,
    même signe dans les deux moitiés chronologiques.
 🟡 Piste : p brute < 0,05 sans Holm, ou une seule moitié, ou n < 30.
 ⚪ Aucune différence prouvée.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import importlib.util
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = pathlib.Path(__file__).resolve().parent
OUTPUT = "Tennis_Edge_Lab/live/profils_hypotheses.json"
MIN_LEVEL = 15
MIN_PROVEN = 30
ALPHA = 0.05
OFFICIAL = ("H13", "H14", "H15", "H16", "H16B", "H17", "H18")
CRITERIA = (
    ("circuit", "circuit"), ("surface", "surface"), ("tranche_cote", "cote d'entrée"),
    ("cote_pinnacle", "favori/outsider"), ("tranche_delai", "délai avant match"),
    ("tranche_ampleur", "ampleur du mouvement"), ("famille_book", "famille de book"),
    ("pin_move_avant", "mouvement Pinnacle avant l'entrée"),
)
# Valeurs « famille de book » -> critères équivalents de l'Explorateur (pour les variantes).
BOOK_FAMILY_SPEC = {"FR jouable": ("jouable_fr", ["oui"], ["non"]),
                    "bourse": ("bourse", ["oui"], ["non"])}


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_p_" + name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    added = str(LAB) not in sys.path
    if added:
        sys.path.insert(0, str(LAB))
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(str(LAB))
    return module


clv_stats = _load("clv_stats.py")
books = _load("books.py")
meta = _load("tennis_meta.py")


# ---------------------------------------------------------------- statistiques
def _gammq(a, x):
    """Gamma incomplète régularisée supérieure Q(a, x) (Numerical Recipes)."""
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1:
        ap, total, delta = a, 1 / a, 1 / a
        for _ in range(500):
            ap += 1
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 1e-14:
                break
        return max(0.0, 1 - total * math.exp(-x + a * math.log(x) - gln))
    b, c, d = x + 1 - a, 1e300, 1 / (x + 1 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-14:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - gln) * h)


def chi2_sf(x, df):
    return _gammq(df / 2, x / 2)


def level_summary(values, dates):
    """Moyenne, IC95, erreur-type (grappes par jour)."""
    s = clv_stats.summary(values, dates)
    se = (s["ci95"][1] - s["ci95"][0]) / 3.92 if s.get("ci95") else None
    return {"n": s["n"], "mean": s["mean_pct"], "ci": s["ci95"], "se": se}


def heterogeneity(groups):
    """Test de Wald (Welch, grappes par jour) : H0 = même CLV moyenne dans toutes les modalités."""
    usable = [g for g in groups if g["se"] and g["se"] > 0 and g["mean"] is not None]
    if len(usable) < 2:
        return None, None
    weights = [1 / g["se"] ** 2 for g in usable]
    center = sum(w * g["mean"] for w, g in zip(weights, usable)) / sum(weights)
    stat = sum(w * (g["mean"] - center) ** 2 for w, g in zip(weights, usable))
    return stat, chi2_sf(stat, len(usable) - 1)


def diff_test(a, b):
    """Écart de moyennes (Welch, grappes) : différence et p bilatérale."""
    if not a["se"] or not b["se"] or a["mean"] is None or b["mean"] is None:
        return None, None
    diff = a["mean"] - b["mean"]
    se = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
    if se == 0:
        return diff, None
    return diff, math.erfc(abs(diff / se) / math.sqrt(2))


def holm(values):
    return clv_stats.holm(values)


# ---------------------------------------------------------------- données
def book_family(book, jouable, jouable_fr, bourse):
    if bourse:
        return "bourse"
    if jouable_fr:
        return "FR jouable"
    return "autres jouables" if jouable else "non jouable"


def bettable_entry(row):
    """PUBLIC sans book en retard jouable : prix de référence, pas un prix obtenu."""
    return not (row["type"] == "PUBLIC" and row["book"] == "aucun retard jouable")


def rows_from_explorer(root):
    explorer = _load("explorer_build.py")
    path = pathlib.Path(root) / explorer.OUT_ALERTS
    if not path.is_file():
        return {}
    import gzip
    doc = json.loads(gzip.decompress(path.read_bytes()))
    out = collections.defaultdict(list)
    for raw in doc["rows"]:
        r = dict(zip(doc["columns"], raw))
        r["famille_book"] = book_family(r["book"], r["jouable"] == "oui", r["jouable_fr"] == "oui", r["bourse"] == "oui")
        if bettable_entry(r):
            out[r["type"]].append(r)
    return out


def rows_from_official(root):
    """Suivi officiel : populations post-gel d'autoresearch (moves_detail_hist), CLV puissance."""
    ar = _load("autoresearch.py")
    ar.ROOT = pathlib.Path(root)
    ar._external_features = None
    ar._pin_close = None
    path = pathlib.Path(root) / "moves_detail_hist.csv"
    if not path.is_file():
        return {}, None
    with path.open(encoding="utf-8-sig", newline="") as stream:
        raw = list(csv.DictReader(stream))
    by_uid = {r.get("uid"): r for r in raw}
    _, qualified = ar.frozen_results(raw)
    feats = ar.external_features()
    surfaces = meta.SurfaceMap(pathlib.Path(root) / "historique/tennis_data.csv.gz")
    out = {}
    for code, rows in qualified.items():
        items = []
        for r in rows:
            src = by_uid.get(r["uid"], {})
            f = feats.get(r["uid"], {})
            pin_now = f.get("pin_at_decision")
            flags = books.flags(r["book"])
            try:
                pts = float(src.get("mag_proba_pts"))
            except (TypeError, ValueError):
                pts = None
            items.append({
                "date": r["date"], "clv_pin": r.get("clv_pin"), "pnl": r["pnl"],
                "circuit": meta.circuit_of(r["tour"]), "surface": surfaces.lookup(r["tour"])[0],
                "tranche_cote": meta.odds_band(r["odd"]),
                # Seule la cote Pinnacle du côté joué est connue ici : favori si < 2.
                "cote_pinnacle": ("favori" if pin_now < 2 else "outsider") if pin_now else "inconnu",
                "tranche_delai": meta.band(r["lead"], meta.LEAD_BANDS),
                "tranche_ampleur": meta.band(abs(pts) if pts is not None else None, meta.MOVE_BANDS),
                "famille_book": book_family(r["book"], flags["jouable"], flags["jouable_fr"], flags["exchange"]),
                "pin_move_avant": meta.band(100 * (pin_now / r["pin"] - 1), meta.PIN_MOVE_BANDS)
                if pin_now and r["pin"] else "sans courbe",
            })
        out[code] = items
    return out, "moves_detail_hist.csv (après la date de gel, règle officielle)"


def rows_from_explorer_freezes(root, explorer_rows):
    gel = _load("explorer_gel.py")
    all_rows = [r for rows in explorer_rows.values() for r in rows]
    out = {}
    for record in gel.read_registry(root):
        rows = gel.prospective(record, all_rows)
        if rows:
            out[f"Gel Explorateur {record['candidate_id']}"] = rows
    return out


# ---------------------------------------------------------------- analyse
def analyse_criterion(rows, field):
    counts = collections.Counter(r.get(field) for r in rows if r.get("clv_pin") is not None)
    rare = {v for v, c in counts.items() if c < MIN_LEVEL or v in (None, "inconnu", "inconnue", "sans courbe")}
    def level(r):
        v = r.get(field)
        return "autres" if v in rare else v
    groups = collections.defaultdict(list)
    for r in rows:
        if r.get("clv_pin") is not None:
            groups[level(r)].append(r)
    if "autres" in groups and len(groups["autres"]) < MIN_LEVEL:
        del groups["autres"]
    if len(groups) < 2:
        return None
    dates = sorted({r["date"] for r in rows})
    cut = dates[len(dates) // 2] if dates else None
    out_levels = []
    for value, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        rest = [r for v, m in groups.items() if v != value for r in m]
        s = level_summary([r["clv_pin"] for r in members], [r["date"] for r in members])
        o = level_summary([r["clv_pin"] for r in rest], [r["date"] for r in rest])
        diff, p = diff_test(s, o)
        halves = []
        for part in (lambda d: d < cut, lambda d: d >= cut):
            a = [r["clv_pin"] for r in members if part(r["date"])]
            b = [r["clv_pin"] for r in rest if part(r["date"])]
            halves.append(round(sum(a) / len(a) - sum(b) / len(b), 3) if len(a) >= 5 and len(b) >= 5 else None)
        settled = [r for r in members if r.get("pnl") is not None]
        roi = level_summary([100 * r["pnl"] for r in settled], [r["date"] for r in settled])
        out_levels.append({
            "valeur": value, "n": len(members), "clv": s["mean"], "clv_ic95": s["ci"], "se": s["se"],
            "reste_clv": o["mean"], "ecart": None if diff is None else round(diff, 3),
            "p_vs_reste": p, "moities": halves, "regles": len(settled),
            "roi": roi["mean"], "roi_ic95": roi["ci"],
        })
    stat, p = heterogeneity([{"mean": lv["clv"], "se": lv["se"]} for lv in out_levels])
    return {"levels": out_levels, "stat": stat, "p": p}


def fmt(x, digits=1):
    return "—" if x is None else f"{x:+.{digits}f}".replace(".", ",").replace("+-", "−").replace("-", "−")


def variant_spec(subject_type, field, level, worse, levels):
    """Spécification prête à geler (format « Préparer le gel » de l'Explorateur)."""
    if level == "autres":
        return None
    if field == "famille_book":
        if level not in BOOK_FAMILY_SPEC:
            return None
        explorer_field, keep, drop = BOOK_FAMILY_SPEC[level]
        values = drop if worse else keep
    else:
        explorer_field = field
        others = [lv["valeur"] for lv in levels if lv["valeur"] not in (level, "autres")]
        values = others if worse else [level]
        if not values:
            return None
    return {"jeu": "alertes", "criteres": {"type": [subject_type], explorer_field: values},
            "origine": "profil automatique (variante)"}


def sentences(subject, subject_type, label, field, res, p_holm, explorable):
    """Phrases prudentes ; jamais de ✅ sans CLV (le ROI seul ne suffit pas)."""
    out = []
    levels = res["levels"]
    real = [lv for lv in levels if lv["valeur"] != "autres"]
    for lv in levels:
        if lv["valeur"] == "autres" or lv["p_vs_reste"] is None:
            continue
        # Deux modalités seulement : une seule phrase (l'autre en est le miroir).
        if len(levels) == 2 and len(real) == 2 and lv is not real[0]:
            continue
        halves = [h for h in lv["moities"] if h is not None]
        same_sign = len(halves) == 2 and (halves[0] > 0) == (halves[1] > 0) == (lv["ecart"] > 0)
        worse = lv["ecart"] < 0
        word = "moins bonne" if worse else "meilleure"
        proven = (p_holm is not None and p_holm < ALPHA and lv["p_vs_reste"] < ALPHA
                  and lv["n"] >= MIN_PROVEN and same_sign)
        base = (f"{subject} : {'nettement ' if proven else 'peut-être '}{word} "
                f"en {label} « {lv['valeur']} » (CLV {fmt(lv['clv'])} % sur {lv['n']}) "
                f"qu'ailleurs ({fmt(lv['reste_clv'])} %).")
        if proven:
            spec = variant_spec(subject_type, field, lv["valeur"], worse, levels) if explorable else None
            variant_clv = lv["reste_clv"] if worse else lv["clv"]
            variant = ""
            if spec:
                variant = (f" Variante à étudier : {subject_type} {'hors' if worse else 'uniquement'} "
                           f"« {lv['valeur']} »")
                variant += ("." if variant_clv is not None and variant_clv > 0 else
                            f", mais sa CLV reste négative ou nulle ({fmt(variant_clv)} %) : "
                            "moins mauvaise, pas un avantage.")
            out.append({"force": "prouve", "texte": "✅ Écart prouvé — " + base + variant, "variante": spec,
                        "niveau": lv["valeur"]})
        elif lv["p_vs_reste"] < ALPHA and (res["p"] is not None and res["p"] < ALPHA or lv["n"] >= MIN_LEVEL):
            reason = []
            if not (p_holm is not None and p_holm < ALPHA):
                reason.append("non significatif après correction de Holm")
            if not same_sign:
                reason.append("pas dans les deux moitiés de la période")
            if lv["n"] < MIN_PROVEN:
                reason.append(f"n < {MIN_PROVEN}")
            out.append({"force": "piste", "texte": "🟡 Piste — " + base + " À confirmer (" + ", ".join(reason) + ").",
                        "variante": None, "niveau": lv["valeur"]})
    if not out:
        rois = [lv["roi"] for lv in levels if lv["roi"] is not None and lv["regles"] >= MIN_LEVEL]
        text = f"⚪ {subject} selon {label} : aucune différence de CLV prouvée."
        if len(rois) >= 2 and max(rois) - min(rois) >= 20:
            text += (f" L'écart de ROI selon {label} (de {fmt(min(rois), 0)} % à {fmt(max(rois), 0)} %) "
                     "n'est pas confirmé par la CLV : probablement du hasard.")
        out.append({"force": "aucune", "texte": text, "variante": None, "niveau": None})
    return out


def build(root=ROOT, explorer_rows=None, official_rows=None) -> dict:
    root = pathlib.Path(root)
    explorer_rows = explorer_rows if explorer_rows is not None else rows_from_explorer(root)
    if official_rows is None:
        official_rows, _ = rows_from_official(root)
    subjects = []
    for code in OFFICIAL:
        subjects.append((code, "alertes envoyées", code, explorer_rows.get(code, []), True))
        subjects.append((code, "suivi officiel", code, official_rows.get(code, []), True))
    for kind in ("PUBLIC", "MOUVEMENT"):
        subjects.append((kind, "alertes envoyées", kind, explorer_rows.get(kind, []), True))
    for name, rows in rows_from_explorer_freezes(root, explorer_rows).items() if explorer_rows else []:
        subjects.append((name, "suivi prospectif", None, rows, False))
    tests, cards = [], []
    for name, source, subject_type, rows, explorable in subjects:
        clv_rows = [r for r in rows if r.get("clv_pin") is not None]
        settled = [r for r in rows if r.get("pnl") is not None]
        overall = level_summary([r["clv_pin"] for r in clv_rows], [r["date"] for r in clv_rows])
        roi = level_summary([100 * r["pnl"] for r in settled], [r["date"] for r in settled])
        dates = sorted(r["date"] for r in rows)
        card = {"sujet": name, "source": source, "n": len(rows), "n_clv": len(clv_rows),
                "clv": overall["mean"], "clv_ic95": overall["ci"], "roi": roi["mean"], "roi_ic95": roi["ci"],
                "regles": len(settled), "periode": [dates[0], dates[-1]] if dates else None, "criteres": []}
        for field, label in CRITERIA:
            res = analyse_criterion(rows, field)
            if res is None or res["p"] is None:
                continue
            entry = {"critere": field, "libelle": label, "p": res["p"], "stat": res["stat"],
                     "modalites": res["levels"], "_subject": (name, subject_type, explorable)}
            card["criteres"].append(entry)
            tests.append(entry)
        cards.append(card)
    for entry, adj in zip(tests, holm([t["p"] for t in tests])):
        entry["p_holm"] = adj
        name, subject_type, explorable = entry.pop("_subject")
        entry["phrases"] = sentences(name, subject_type, entry["libelle"], entry["critere"],
                                     {"levels": entry["modalites"], "p": entry["p"]}, adj, explorable)
        for lv in entry["modalites"]:
            lv.pop("se", None)
    rank = {"prouve": 0, "piste": 1, "aucune": 2}
    for card in cards:
        card["criteres"].sort(key=lambda e: (min(rank[p["force"]] for p in e["phrases"]), e["p"]))
    all_dates = sorted(d for c in cards if c["periode"] for d in c["periode"])
    counts = collections.Counter(p["force"] for t in tests for p in t["phrases"])
    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "k_tests": len(tests), "alpha": ALPHA,
        "periode": [all_dates[0], all_dates[-1]] if all_dates else None,
        "compte": {"prouve": counts.get("prouve", 0), "piste": counts.get("piste", 0), "aucune": counts.get("aucune", 0)},
        "methode": ("Test de Wald de type Welch sur la CLV Pinnacle moyenne par modalité, erreurs-types "
                    "robustes aux grappes par jour, χ² à g−1 ddl ; Holm sur les k tests du jour ; "
                    "modalités de moins de 15 alertes regroupées en « autres » ; stabilité : même signe "
                    "dans les deux moitiés chronologiques."),
        "note": ("CLV Pinnacle dé-marginée par la méthode puissance : obligatoire pour comparer des circuits, "
                 "car la marge de Pinnacle n'est pas la même en Challenger, ATP ou WTA. Une différence "
                 "prouvée n'est pas une stratégie : la variante doit être gelée puis suivie."),
        "sujets": cards,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(ROOT))
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    doc = build(root)
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            strip = lambda d: {k: v for k, v in d.items() if k != "generated_at"}
            if strip(old) == json.loads(json.dumps(strip(doc))):
                doc["generated_at"] = old["generated_at"]
        except (ValueError, KeyError):
            pass
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    c = doc["compte"]
    print(f"Profils : {len(doc['sujets'])} sujets, k = {doc['k_tests']} tests ; "
          f"{c['prouve']} écart(s) prouvé(s), {c['piste']} piste(s), {c['aucune']} sans différence")
    for card in doc["sujets"]:
        for crit in card["criteres"]:
            for p in crit["phrases"]:
                if p["force"] != "aucune":
                    print(f"  [{card['source']}] {p['texte']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
