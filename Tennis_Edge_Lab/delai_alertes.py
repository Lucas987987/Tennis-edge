#!/usr/bin/env python3
"""V7.5 — Le prix tient-il après l'alerte ?

Pour chaque alerte ENVOYÉE (H13 à H19, journaux h*_signal_log.jsonl), on relit la
courbe COMPLÈTE du book alerté (courbes historiques, chaque changement de cote)
et on regarde son prix 0, 2, 5, 10 et 30 minutes après l'envoi :
  — part des alertes où le prix est encore au moins celui de l'alerte ;
  — variation moyenne du prix ;
  — CLV au prix réellement disponible (clôture Pinnacle sans marge) ;
  — meilleur prix d'un AUTRE book au même instant (si le book alerté a bougé).

C'est la CLV que Lucas obtient vraiment s'il parie 2, 5 ou 10 minutes après le
message. Lecture seule ; écrit Tennis_Edge_Lab/live/delai_alertes.json.
"""
from __future__ import annotations

import collections
import datetime as dt
import importlib.util
import json
import pathlib
import sys

LAB = pathlib.Path(__file__).resolve().parent
OUTPUT = "Tennis_Edge_Lab/live/delai_alertes.json"
CODES = ("H13", "H14", "H15", "H16", "H16B", "H17", "H18", "H19")
DELAIS = (0, 2, 5, 10, 30)


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_da_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(LAB))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(LAB))
    return module


books = _load("books.py")
meta = _load("tennis_meta.py")
dp = _load("direct_profils.py")


def _ts(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def lire_alertes(root):
    """Alertes envoyées de tous les journaux : [{code, uid, joueur, book, cote, t}]."""
    out = []
    for code in CODES:
        path = pathlib.Path(root) / f"{code.lower()}_signal_log.jsonl"
        if not path.is_file():
            continue
        vus = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("envoye") is not True or r.get("doublon"):
                continue
            t = _ts(r.get("signale_le") or r.get("detecte_le"))
            if t is None or not r.get("uid") or not r.get("book") or not r.get("cote"):
                continue
            key = (r["uid"], r.get("joueur"))
            if key in vus:
                continue
            vus.add(key)
            out.append({"code": code, "uid": r["uid"], "joueur": r.get("joueur"), "book": str(r["book"]).lower(),
                        "cote": float(r["cote"]), "t": t})
    return out


def alert_uids(root):
    return {a["uid"] for a in lire_alertes(root)}


def _at(serie, t):
    v = None
    for tt, o in serie:
        if tt <= t:
            v = o
        else:
            break
    return v


def mesurer(alertes, records, series_books):
    """Une mesure par (alerte, délai)."""
    by_uid = collections.defaultdict(dict)
    for (uid, book), rec in records.items():
        by_uid[uid][book] = rec
    lignes, sans_courbe = [], 0
    for a in alertes:
        bks = by_uid.get(a["uid"])
        sb = series_books.get(a["uid"]) or {}
        pin = (bks or {}).get("pinnacle")
        if not pin or a["book"] not in sb:
            sans_courbe += 1
            continue
        names = [meta.norm_text(pin["home"]).replace(" ", ""), meta.norm_text(pin["away"]).replace(" ", "")]
        j = meta.norm_text(a["joueur"] or "").replace(" ", "")
        if j not in names:
            sans_courbe += 1
            continue
        side = "home" if names.index(j) == 0 else "away"
        other = "away" if side == "home" else "home"
        start = pin["start"]
        cl_s, cl_o = pin["curves"][side]["close"], pin["curves"][other]["close"]
        fair = books.fair_close(cl_s[1], cl_o[1]) if cl_s and cl_o else None
        serie = sb[a["book"]][side]
        eff0 = books.effective_odds(a["book"], a["cote"])
        for d in DELAIS:
            t = a["t"] + dt.timedelta(minutes=d)
            if t >= start:
                continue
            p = _at(serie, t)
            if p is None:
                continue
            eff = books.effective_odds(a["book"], p)
            ailleurs = None
            for b, s in sb.items():
                if b in ("pinnacle", a["book"]) or not books.flags(b)["jouable"]:
                    continue
                q = _at(s[side], t)
                if q is not None:
                    e = books.effective_odds(b, q)
                    if ailleurs is None or e > ailleurs[1]:
                        ailleurs = (b, e)
            meilleur = max(eff, ailleurs[1]) if ailleurs else eff
            lignes.append({"code": a["code"], "delai": d, "date": a["t"].date().isoformat(),
                           "tient": eff >= eff0 - 1e-9, "variation_pct": 100 * (eff / eff0 - 1),
                           "clv": 100 * (eff / fair - 1) if fair else None,
                           "clv_meilleur": 100 * (meilleur / fair - 1) if fair else None,
                           "clv_alerte": 100 * (eff0 / fair - 1) if fair else None})
    return lignes, sans_courbe


def resume(lignes):
    out = []
    groupes = collections.defaultdict(list)
    for l in lignes:
        groupes[(l["code"], l["delai"])].append(l)
        groupes[("toutes", l["delai"])].append(l)
    for (code, d), g in sorted(groupes.items(), key=lambda kv: (kv[0][0] == "toutes", kv[0][0], kv[0][1])):
        n = len(g)
        clv = dp.cluster_summary([x["clv"] for x in g], [x["date"] for x in g])
        clv_m = dp.cluster_summary([x["clv_meilleur"] for x in g], [x["date"] for x in g])
        clv_a = dp.cluster_summary([x["clv_alerte"] for x in g], [x["date"] for x in g])
        out.append({"hypothese": code, "delai_min": d, "n": n,
                    "prix_tenu": sum(x["tient"] for x in g) / n,
                    "variation_moyenne_pct": sum(x["variation_pct"] for x in g) / n,
                    "clv_au_prix_disponible": clv["mean"], "clv_ic95": clv["ci"],
                    "clv_meilleur_book": clv_m["mean"], "clv_au_prix_alerte": clv_a["mean"]})
    return out


def build(sink):
    alertes = lire_alertes(sink["root"])
    lignes, sans = mesurer(alertes, sink["records"], sink.get("series_books") or {})
    return {"schema_version": 1,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "alertes_envoyees": len(alertes), "sans_courbe_du_book": sans,
            "delais_min": list(DELAIS), "resume": resume(lignes),
            "notes": {"prix": "prix NET (commission déduite) du book alerté, dernier changement de cote avant l'instant",
                      "clv": "contre la clôture Pinnacle sans marge (méthode puissance)",
                      "meilleur": "meilleur prix entre le book alerté et les autres books jouables au même instant"}}


def run(sink):
    doc = build(sink)
    path = pathlib.Path(sink["root"]) / OUTPUT
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        old.pop("generated_at", None)
        new = dict(doc)
        new.pop("generated_at", None)
        if old == json.loads(json.dumps(new, ensure_ascii=False)):
            return doc
    except (OSError, ValueError):
        pass
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    t = {(r["hypothese"], r["delai_min"]): r for r in doc["resume"]}
    a = t.get(("toutes", 5))
    print(f"Délai alertes : {doc['alertes_envoyees']} alertes envoyées, {doc['sans_courbe_du_book']} sans courbe du book"
          + (f" ; à +5 min, prix tenu {100 * a['prix_tenu']:.0f} %, CLV {a['clv_au_prix_disponible']:+.2f} %"
             if a and a["clv_au_prix_disponible"] is not None else ""))
    return doc
