#!/usr/bin/env python3
"""V7.4 — « Valeur contre Pinnacle juste » : H19 (gelée le 16/10/2026) et la grille d'étude.

Appelé par registre_matchs.run (même lecture des partitions que l'Explorateur).
Écrit Tennis_Edge_Lab/live/valeur.json.

PRINCIPE
Un book jouable paie PLUS que la cote Pinnacle sans marge (méthode puissance) :
si la clôture Pinnacle est juste, le gain attendu = l'écart. Rien n'est « trouvé »
dans les données : c'est la définition même de notre CLV. Ce module mesure si
l'écart se transforme réellement en CLV et en gains, et où.

H19 — RÈGLE GELÉE LE 16/10/2026 (texte dans registry/gel_h19.json, empreinte vérifiée)
  matchs simples ATP, WTA, Challenger, Grand Chelem suivis par les courbes,
  commençant APRÈS le 16/10/2026 ;
  aux horizons 24 h, 6 h, 1 h, 10 min (dans cet ordre), Pinnacle cote les deux
  joueurs (même règle que l'Explorateur) ;
  meilleur prix d'un book JOUABLE hors Pinnacle, cote vieille de 30 min au plus,
  commission de bourse déduite ;
  écart = prix net / cote Pinnacle juste − 1, entre +2 % (inclus) et +8 % (exclu :
  au-delà, surtout des cotes erronées) ;
  UN pari par (match, joueur) : le premier horizon qui remplit la règle.
  Mesure principale : CLV contre la clôture Pinnacle sans marge. Cible n = 300.
  VALIDÉE si l'IC95 de la CLV est entièrement > 0 ; RÉFUTÉE si la CLV moyenne < 0 ;
  sinon NON CONCLUANT. Aucun verdict avant la cible.

GRILLE (rétrospective, exploratoire) : seuil d'écart × horizon × book, avec
correction de Holm sur toutes les cases, persistance du prix (le book paie-t-il
encore autant à la clôture ?) et âge de la cote. Elle sert à comprendre H19,
jamais à la modifier.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import importlib.util
import json
import math
import pathlib
import sys

LAB = pathlib.Path(__file__).resolve().parent
OUTPUT = "Tennis_Edge_Lab/live/valeur.json"
GEL_FILE = "Tennis_Edge_Lab/registry/gel_h19.json"


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_va_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(LAB))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(LAB))
    return module


books = _load("books.py")
meta = _load("tennis_meta.py")
engine = _load("bookmakers_sets_v5.py")
dp = _load("direct_profils.py")

# ── H19 : pré-enregistrement du 16/10/2026 — NE PAS MODIFIER ─────────────────
H19 = {
    "code": "H19",
    "nom": "Valeur contre Pinnacle juste",
    "gele_le": "2026-10-16",
    "circuits": ["ATP", "WTA", "Challenger", "Grand Chelem"],
    "horizons": ["24h", "6h", "1h", "10m"],
    "age_max_min": 30,
    "ecart_min_pct": 2.0,
    "ecart_max_pct": 8.0,
    "un_pari_par": "match et joueur, premier horizon qui remplit la règle",
    "mesure": "CLV contre la clôture Pinnacle sans marge (puissance), entrée nette de commission",
    "cible_n": 300,
    "verdict": "VALIDÉE si IC95 de la CLV > 0 ; RÉFUTÉE si CLV moyenne < 0 ; sinon NON CONCLUANT ; rien avant la cible",
    "juge_sur": "matchs commençant après le 16/10/2026 (jour UTC du début > 2026-10-16)",
    # Amendement du 16/10/2026, AVANT toute donnée prospective (la collecte des
    # courbes reprend le 27/10) : liste des books fixée, celle de la collecte.
    "books": ["betfair-ex", "bet365", "1xbet", "22bet", "unibet", "winamax.fr", "unibet.fr", "pmu", "bwin",
              "coolbet", "betsson", "betway", "williamhill", "888sport", "leovegas", "tipico", "netbet",
              "marathonbet", "bet365.fr"],
    "amendement": "16/10/2026 avant toute donnée prospective : books = liste de la collecte des courbes "
                  "(les 12 books jamais servis par l'API en tennis retirés)",
}
# ───────────────────────────────────────────────────────────────────────────

CIRCUITS = tuple(H19["circuits"])
HORIZONS = tuple(H19["horizons"])
SEUILS = (1.0, 2.0, 3.0, 4.0, 6.0)
ECART_MAX = H19["ecart_max_pct"]
MIN_CASE = 30


def empreinte(rule=H19):
    return hashlib.sha256(json.dumps(rule, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def check_gel(root):
    """Le gel committé doit avoir la même empreinte que la règle du code."""
    path = pathlib.Path(root) / GEL_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"etat": "absent", "attendu": empreinte()}
    ok = doc.get("sha256") == empreinte() and doc.get("regle") == H19
    return {"etat": "intact" if ok else "MODIFIÉ", "sha256": doc.get("sha256"), "attendu": empreinte()}


# ── opportunités : une ligne par (match, joueur, horizon) où un book jouable cote ──
def opportunites(records, results, pair_results=None):
    by_uid = collections.defaultdict(dict)
    for (uid, book), rec in records.items():
        by_uid[uid][book] = rec
    out = []
    for uid, bks in by_uid.items():
        pin = bks.get("pinnacle")
        if pin is None:
            continue
        circuit = meta.circuit_of(pin["tournament"])
        if circuit not in CIRCUITS or "double" in pin["tournament"].lower():
            continue
        start = pin["start"]
        winner = (results.get(uid) or {}).get("match")
        for horizon in HORIZONS:
            lead, _ = engine.HORIZONS[horizon]
            decision = start - dt.timedelta(minutes=lead)
            ph = pin["curves"]["home"]["horizons"].get(horizon)
            pa = pin["curves"]["away"]["horizons"].get(horizon)
            if ph is None or pa is None or abs((ph[0] - pa[0]).total_seconds()) > 1800:
                continue
            for side in ("home", "away"):
                other = "away" if side == "home" else "home"
                q, o = (ph, pa) if side == "home" else (pa, ph)
                fair = books.fair_close(q[1], o[1])
                if not fair:
                    continue
                cl_s, cl_o = pin["curves"][side]["close"], pin["curves"][other]["close"]
                closing_ok = cl_s and cl_o and cl_s[0] > decision and cl_o[0] > decision
                fair_close = books.fair_close(cl_s[1], cl_o[1]) if closing_ok else None
                won = None
                if winner in ("home", "away"):
                    won = winner == side
                elif pair_results is not None:
                    won = pair_results(pin[side], pin[other], start)
                cands = []
                for book, rec in bks.items():
                    if book == "pinnacle" or not books.flags(book)["jouable"]:
                        continue
                    bq = rec["curves"][side]["horizons"].get(horizon)
                    if bq is None:
                        continue
                    age = (decision - bq[0]).total_seconds() / 60
                    if age > H19["age_max_min"] or age < 0:
                        continue
                    eff = books.effective_odds(book, bq[1])
                    bclose = rec["curves"][side]["close"]
                    cands.append({"book": book, "raw": bq[1], "eff": eff, "age_min": age,
                                  "ecart_pct": 100 * (eff / fair - 1),
                                  "book_cloture": bclose[1] if bclose and bclose[0] > decision else None})
                if not cands:
                    continue
                best = max(cands, key=lambda c: c["eff"])
                fr = [c for c in cands if books.flags(c["book"])["jouable_fr"]]
                out.append({
                    "uid": uid, "joueur": pin[side], "horizon": horizon, "start": start, "date": start.date().isoformat(),
                    "mois": start.strftime("%Y-%m"), "circuit": circuit, "cote_pin": q[1], "juste": fair,
                    "favori": q[1] < o[1], "won": won, "fair_close": fair_close, "best": best,
                    "cands": cands, "best_fr": max(fr, key=lambda c: c["eff"]) if fr else None,
                })
    out.sort(key=lambda r: (r["start"], r["joueur"], -engine.HORIZONS[r["horizon"]][0]))
    return out


def pari(o, c):
    """Mesures d'un pari pris au prix c (dict candidat) pour l'opportunité o."""
    clv = 100 * (c["eff"] / o["fair_close"] - 1) if o["fair_close"] else None
    pnl = None if o["won"] is None else (c["eff"] - 1 if o["won"] else -1.0)
    persiste = None if c["book_cloture"] is None else books.effective_odds(c["book"], c["book_cloture"]) >= c["eff"]
    return {"clv": clv, "pnl": pnl, "persiste": persiste, "age": c["age_min"], "ecart": c["ecart_pct"],
            "book": c["book"], "date": o["date"], "mois": o["mois"], "uid": o["uid"], "joueur": o["joueur"],
            "horizon": o["horizon"], "circuit": o["circuit"], "favori": o["favori"], "cote": c["eff"]}


def premier(opps, test):
    """Un pari par (match, joueur) : le premier horizon où test(opportunité) donne un candidat."""
    seen, out = set(), []
    for o in opps:
        key = (o["uid"], o["joueur"])
        if key in seen:
            continue
        c = test(o)
        if c is not None:
            seen.add(key)
            out.append(pari(o, c))
    return out


def regle_h19(o):
    pool = [c for c in o["cands"] if c["book"] in H19["books"]]
    if not pool:
        return None
    c = max(pool, key=lambda c: c["eff"])
    return c if H19["ecart_min_pct"] <= c["ecart_pct"] < H19["ecart_max_pct"] else None


def books_table(opps):
    """Chaque book collecté : couverture, meilleur prix, écart médian à la cote juste,
    cotes au-dessus de la juste — sur TOUTES les décisions, pas seulement H19."""
    matchs = {o["uid"] for o in opps}
    cov, best, gaps, above = collections.defaultdict(set), collections.Counter(), collections.defaultdict(list), collections.Counter()
    for o in opps:
        for c in o["cands"]:
            cov[c["book"]].add(o["uid"])
            gaps[c["book"]].append(c["ecart_pct"])
            if c["ecart_pct"] >= 2:
                above[c["book"]] += 1
        best[o["best"]["book"]] += 1
    out = []
    for b in sorted(cov, key=lambda k: -len(cov[k])):
        g = sorted(gaps[b])
        f = books.flags(b)
        out.append({"book": b, "matchs": len(cov[b]), "couverture": len(cov[b]) / len(matchs) if matchs else None,
                    "meilleur_prix": best[b] / len(opps) if opps else None, "ecart_median": g[len(g) // 2],
                    "cotes": len(g), "au_dessus_2pct": above[b], "fr": f["jouable_fr"], "bourse": f["exchange"]})
    return {"matchs": len(matchs), "decisions": len(opps), "books": out}


# ── statistiques ──────────────────────────────────────────────────────────────
def resume(paris):
    clv = dp.cluster_summary([p["clv"] for p in paris], [p["date"] for p in paris])
    roi = dp.cluster_summary([None if p["pnl"] is None else 100 * p["pnl"] for p in paris], [p["date"] for p in paris])
    pers = [p["persiste"] for p in paris if p["persiste"] is not None]
    mois = collections.defaultdict(list)
    for p in paris:
        if p["clv"] is not None:
            mois[p["mois"]].append(p["clv"])
    pleins = {m: v for m, v in mois.items() if len(v) >= 10}
    return {"n": len(paris), "clv": clv, "roi": roi,
            "regles": sum(1 for p in paris if p["pnl"] is not None),
            "persistance": (sum(pers) / len(pers)) if pers else None,
            "age_median": sorted(p["age"] for p in paris)[len(paris) // 2] if paris else None,
            "mois_clv_positif": f"{sum(1 for v in pleins.values() if sum(v) > 0)}/{len(pleins)}" if pleins else None,
            "par_mois": {m: {"n": len(v), "clv": sum(v) / len(v)} for m, v in sorted(mois.items())}}


def verdict_h19(s):
    n = s["clv"]["n"]
    if n < H19["cible_n"]:
        return f"EN COURS — {n}/{H19['cible_n']}, aucun verdict avant la cible"
    ci = s["clv"]["ci"]
    if ci and ci[0] > 0:
        return "VALIDÉE — IC95 de la CLV entièrement au-dessus de zéro"
    if s["clv"]["mean"] is not None and s["clv"]["mean"] < 0:
        return "RÉFUTÉE — CLV moyenne négative"
    return "NON CONCLUANT — on ne joue pas"


def holm(cases):
    """Correction de Holm sur les p unilatéraux (CLV > 0) des cases testables."""
    ps = sorted((c["clv"]["p"], i) for i, c in enumerate(cases) if c["clv"]["p"] is not None and c["n"] >= MIN_CASE)
    m = len(ps)
    worst = 0.0
    for rank, (p, i) in enumerate(ps):
        adj = min(1.0, max(worst, (m - rank) * p))
        worst = adj
        cases[i]["p_holm"] = adj
    return m


def grille(opps):
    cases = []

    def add(nom, axes, test):
        s = resume(premier(opps, test))
        s.update({"case": nom, **axes})
        cases.append(s)

    def best_ge(lo, hz=None, book=None, fr=False):
        def test(o):
            if hz and o["horizon"] != hz:
                return None
            pool = o["cands"]
            if book:
                pool = [c for c in pool if c["book"] == book]
            if fr:
                pool = [c for c in pool if books.flags(c["book"])["jouable_fr"]]
            pool = [c for c in pool if lo <= c["ecart_pct"] < ECART_MAX]
            return max(pool, key=lambda c: c["eff"]) if pool else None
        return test

    for lo in SEUILS:
        add(f"écart ≥ {lo:g} %", {"seuil": lo, "horizon": "premier", "book": "tous"}, best_ge(lo))
        for hz in HORIZONS:
            add(f"écart ≥ {lo:g} % · {hz}", {"seuil": lo, "horizon": hz, "book": "tous"}, best_ge(lo, hz=hz))
        add(f"écart ≥ {lo:g} % · books FR", {"seuil": lo, "horizon": "premier", "book": "FR"}, best_ge(lo, fr=True))
    vol = collections.Counter(c["book"] for o in opps for c in o["cands"] if c["ecart_pct"] >= 2)
    for book, _ in vol.most_common(12):
        add(f"écart ≥ 2 % · {book}", {"seuil": 2.0, "horizon": "premier", "book": book}, best_ge(2.0, book=book))
    m = holm(cases)
    cases.sort(key=lambda c: (-(c["clv"]["mean"] if c["clv"]["mean"] is not None and c["n"] >= MIN_CASE else -1e9)))
    return {"cases": cases, "cases_testees": m}


def decoupes_h19(paris):
    def by(key, fn=None):
        g = collections.defaultdict(list)
        for p in paris:
            g[fn(p) if fn else p[key]].append(p)
        return [{"groupe": k, **resume(v)} for k, v in sorted(g.items(), key=lambda kv: str(kv[0]))]
    age = lambda p: "≤ 5 min" if p["age"] <= 5 else "5–15 min" if p["age"] <= 15 else "15–30 min"
    ecart = lambda p: "2–3 %" if p["ecart"] < 3 else "3–4 %" if p["ecart"] < 4 else "4–6 %" if p["ecart"] < 6 else "6–8 %"
    pers = lambda p: "prix encore là à la clôture" if p["persiste"] else ("prix disparu avant la clôture" if p["persiste"] is False else "clôture du book inconnue")
    return {"age_cote": by(None, age), "ecart": by(None, ecart), "persistance": by(None, pers),
            "horizon": by("horizon"), "circuit": by("circuit"), "book": by("book"),
            "favori": by(None, lambda p: "favori" if p["favori"] else "outsider")}


def alertes_direct(root, paris_lab):
    """Alertes H19 envoyées en direct (h19_signal_log.jsonl) contre la mesure du Lab :
    le canal direct voit-il les mêmes paris que les courbes complètes ?"""
    path = pathlib.Path(root) / "h19_signal_log.jsonl"
    if not path.is_file():
        return {"lignes": 0}
    recs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            recs.append(json.loads(line))
        except ValueError:
            pass
    lab = {(p["uid"], p["joueur"]): p for p in paris_lab}
    envoyees = [r for r in recs if r.get("envoye")]
    communs = [r for r in recs if (r.get("uid"), r.get("joueur")) in lab]
    dates_direct = sorted(str(r.get("commence", ""))[:10] for r in recs)
    debut = dates_direct[0] if dates_direct else None
    lab_periode = [p for p in paris_lab if debut and p["date"] >= debut]
    return {"lignes": len(recs), "envoyees": len(envoyees), "communes_avec_le_lab": len(communs),
            "paris_lab_meme_periode": len(lab_periode),
            "meme_book": sum(1 for r in communs if lab[(r["uid"], r["joueur"])]["book"] == r.get("book")),
            "derniers": recs[-15:]}


def build(sink):
    opps = opportunites(sink["records"], sink["results"], sink.get("pair_results"))
    tous = premier(opps, regle_h19)
    gel = H19["gele_le"]
    avant = [p for p in tous if p["date"] <= gel]
    apres = [p for p in tous if p["date"] > gel]
    s_apres = resume(apres)
    doc = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "h19": {"regle": H19, "gel": check_gel(sink["root"]),
                "prospectif": {**s_apres, "verdict": verdict_h19(s_apres),
                               "derniers": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items()}
                                            for p in apres[-30:]]},
                "retrospectif": {**resume(avant), "avertissement": "période qui a servi à CHOISIR la règle : ne compte pas"},
                "decoupes_retrospectives": decoupes_h19(avant),
                "alertes_direct": alertes_direct(sink["root"], apres)},
        "grille": grille(opps),
        "books": books_table(opps),
        "opportunites": len(opps),
        "notes": {"persistance": "le book paie-t-il encore au moins ce prix (net) à sa dernière cote avant le match ?",
                  "holm": "p unilatéral CLV > 0, corrigé de Holm sur toutes les cases d'au moins 30 paris",
                  "fr": "books agréés ANJ uniquement"},
    }
    return doc


def write(root, doc):
    path = pathlib.Path(root) / OUTPUT
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        old.pop("generated_at", None)
        new = json.loads(json.dumps(doc, ensure_ascii=False, default=str))
        new.pop("generated_at", None)
        if old == new:
            return False
    except (OSError, ValueError):
        pass
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return True


def run(sink):
    doc = build(sink)
    changed = write(sink["root"], doc)
    h = doc["h19"]
    r, p = h["retrospectif"], h["prospectif"]
    f = lambda s: "—" if s["clv"]["mean"] is None else f"{s['clv']['mean']:+.2f} %"
    print(f"H19 (gel {h['gel']['etat']}) : rétrospectif n={r['n']} CLV {f(r)} ; prospectif n={p['n']} CLV {f(p)} — "
          f"{p['verdict']} ; grille {doc['grille']['cases_testees']} cases ({'écrit' if changed else 'inchangé'})")
    return doc


if __name__ == "__main__":
    if "--gel" in sys.argv:
        out = LAB / "registry" / "gel_h19.json"
        out.write_text(json.dumps({"regle": H19, "sha256": empreinte(), "ecrit_le": H19["gele_le"]},
                                  ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"écrit {out} — {empreinte()}")
