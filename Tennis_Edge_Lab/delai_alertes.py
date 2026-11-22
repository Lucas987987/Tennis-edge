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

22/11/2026 (paquet 335, Lucas : « test prix encore là sur le canal, découpage ATP / WTA / Challenger pour toutes les
hypothèses ») :
  — CANAL : chaque book en retard annoncé par le canal public (canal_public_log.jsonl, champ « retards »), une fois par
    (match, joueur, book), books jouables seulement ; « CANAL FR » : les mêmes, books à licence française seulement ;
  — MISER : chaque alerte MISER (miser_signal_log.jsonl, marché du match, relances exclues) ;
  — par_circuit : chaque hypothèse (et le canal) découpée ATP / WTA / Challenger (tournoi de l'alerte, sinon celui de
    la cote Pinnacle), avec une lecture à +5 min : « tient » si la CLV au prix encore disponible est positive avec son
    intervalle à 95 % au-dessus de 0, « ne tient pas » si l'intervalle est sous 0, « incertain » sinon ;
    rien n'est lu sous 30 alertes (« trop tôt »). Le circuit le plus fort n'est pas choisi après coup : les trois sont
    toujours affichés côte à côte.
Les alertes du canal et de MISER restent comptées à part (« toutes » = H13 à H19, comme avant).
"""
from __future__ import annotations

import collections
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys

LAB = pathlib.Path(__file__).resolve().parent
OUTPUT = "Tennis_Edge_Lab/live/delai_alertes.json"
CODES = ("H13", "H14", "H15", "H16", "H16B", "H17", "H18", "H19")
DELAIS = (0, 2, 5, 10, 30)
DELAI_LECTURE = 5
N_MIN = 30
CIRCUITS = ("ATP", "WTA", "Challenger")


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
                        "cote": float(r["cote"]), "t": t, "tournoi": r.get("tournoi") or ""})
    return out


def circuit(*textes):
    """ATP / WTA / Challenger / ITF / inconnu, d'après le tournoi ou la catégorie (premier texte parlant)."""
    for t in textes:
        v = f" {str(t or '').lower()} "
        if "challenger" in v:
            return "Challenger"
        if "itf" in v:
            return "ITF"
        if " wta" in v or re.search(r"\bwomen", v):
            return "WTA"
        if " atp" in v or re.search(r"\bmen\b", v):
            return "ATP"
    return "inconnu"


def lire_canal(root):
    """Canal public : un « pari » par (match, joueur, book en retard annoncé), books jouables seulement."""
    path = pathlib.Path(root) / "canal_public_log.jsonl"
    out, vus = [], set()
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t = _ts(r.get("t"))
        if t is None or not r.get("uid") or not r.get("joueur"):
            continue
        for ret in r.get("retards") or []:
            try:
                book, cote = str(ret[0]).lower(), float(ret[1])
            except (TypeError, ValueError, IndexError):
                continue
            fl = books.flags(book)
            if not fl["jouable"] or cote <= 1:
                continue
            key = (r["uid"], r["joueur"], books.canonical(book))
            if key in vus:
                continue
            vus.add(key)
            out.append({"code": "CANAL", "uid": r["uid"], "joueur": r["joueur"], "book": book, "cote": cote, "t": t,
                        "tournoi": r.get("tournoi") or r.get("categorie") or ""})
    return out


def lire_miser(root):
    """Canal MISER : première alerte de chaque (match, joueur), marché du match, relances exclues."""
    path = pathlib.Path(root) / "miser_signal_log.jsonl"
    out, vus = [], set()
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("relance") or (r.get("marche") or "match") != "match":
            continue
        t = _ts(r.get("signale_le"))
        if t is None or not r.get("uid") or not r.get("book") or not r.get("cote"):
            continue
        key = (r["uid"], r.get("joueur"))
        if key in vus:
            continue
        vus.add(key)
        out.append({"code": "MISER", "uid": r["uid"], "joueur": r.get("joueur"), "book": str(r["book"]).lower(),
                    "cote": float(r["cote"]), "t": t, "tournoi": r.get("tournoi") or ""})
    return out


def toutes_alertes(root):
    return lire_alertes(root) + lire_canal(root) + lire_miser(root)


def alert_uids(root):
    return {a["uid"] for a in toutes_alertes(root)}


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
        circ = circuit(a.get("tournoi"), pin.get("tournament"))
        fr = books.flags(a["book"])["jouable_fr"]
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
            lignes.append({"code": a["code"], "delai": d, "date": a["t"].date().isoformat(), "circuit": circ, "fr": fr,
                           "tient": eff >= eff0 - 1e-9, "variation_pct": 100 * (eff / eff0 - 1),
                           "clv": 100 * (eff / fair - 1) if fair else None,
                           "clv_meilleur": 100 * (meilleur / fair - 1) if fair else None,
                           "clv_alerte": 100 * (eff0 / fair - 1) if fair else None})
    return lignes, sans_courbe


def _ligne(g):
    n = len(g)
    clv = dp.cluster_summary([x["clv"] for x in g], [x["date"] for x in g])
    clv_m = dp.cluster_summary([x["clv_meilleur"] for x in g], [x["date"] for x in g])
    clv_a = dp.cluster_summary([x["clv_alerte"] for x in g], [x["date"] for x in g])
    return {"n": n, "prix_tenu": sum(x["tient"] for x in g) / n,
            "variation_moyenne_pct": sum(x["variation_pct"] for x in g) / n,
            "clv_au_prix_disponible": clv["mean"], "clv_ic95": clv["ci"],
            "clv_meilleur_book": clv_m["mean"], "clv_au_prix_alerte": clv_a["mean"]}


def lecture(r):
    """Lecture à +5 min (règle écrite avant de regarder) : rien sous 30 alertes."""
    if not r or r["n"] < N_MIN:
        return "trop tôt (n < 30)"
    ci = r.get("clv_ic95")
    if not ci or r.get("clv_au_prix_disponible") is None:
        return "incertain"
    if ci[0] > 0:
        return "tient"
    if ci[1] < 0:
        return "ne tient pas"
    return "incertain"


def par_circuit(lignes):
    """(hypothèse, circuit) × délai, H13 à H19 réunies sous « toutes », et la lecture à +5 min."""
    groupes = collections.defaultdict(list)
    for l in lignes:
        if l["circuit"] not in CIRCUITS:
            continue
        groupes[(l["code"], l["circuit"], l["delai"])].append(l)
        if l["code"].startswith("H"):
            groupes[("toutes", l["circuit"], l["delai"])].append(l)
        if l["code"] == "CANAL" and l["fr"]:
            groupes[("CANAL FR", l["circuit"], l["delai"])].append(l)
    out = []
    ordre = lambda k: (k[0] == "toutes", k[0], CIRCUITS.index(k[1]), k[2])
    for (code, circ, d), g in sorted(groupes.items(), key=lambda kv: ordre(kv[0])):
        r = dict(_ligne(g), hypothese=code, circuit=circ, delai_min=d)
        if d == DELAI_LECTURE:
            r["lecture"] = lecture(r)
        out.append(r)
    return out


def resume(lignes):
    out = []
    groupes = collections.defaultdict(list)
    for l in lignes:
        groupes[(l["code"], l["delai"])].append(l)
        if l["code"].startswith("H"):
            groupes[("toutes", l["delai"])].append(l)
        if l["code"] == "CANAL" and l.get("fr"):
            groupes[("CANAL FR", l["delai"])].append(l)
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
        if d == DELAI_LECTURE:
            out[-1]["lecture"] = lecture(out[-1])
    return out


def build(sink):
    alertes = toutes_alertes(sink["root"])
    lignes, sans = mesurer(alertes, sink["records"], sink.get("series_books") or {})
    n_code = collections.Counter(a["code"] for a in alertes)
    return {"schema_version": 1,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "alertes_envoyees": sum(v for k, v in n_code.items() if k.startswith("H")), "sans_courbe_du_book": sans,
            "alertes_par_source": dict(sorted(n_code.items())),
            "delais_min": list(DELAIS), "resume": resume(lignes), "par_circuit": par_circuit(lignes),
            "regle_lecture": f"à +{DELAI_LECTURE} min : « tient » si l'IC 95 % de la CLV au prix disponible est au-dessus de 0, "
                             f"« ne tient pas » s'il est en dessous, « incertain » sinon ; rien sous {N_MIN} alertes",
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
    # 335 : les journaux des runs sont publics — seulement des comptes, jamais de CLV ni de prix
    print(f"Délai alertes : {doc['alertes_envoyees']} alertes H, sources {doc['alertes_par_source']}, "
          f"{doc['sans_courbe_du_book']} sans courbe du book ; détail dans le Lab (privé)")
    return doc
