#!/usr/bin/env python3
"""V7.3 — Registre de TOUS les matchs collectés, de l'ouverture à la clôture.

Appelé par explorer_matchs.py (une seule lecture des partitions) :
    python Tennis_Edge_Lab/explorer_matchs.py .

Écrit :
  Tennis_Edge_Lab/live/registre/registre_AAAA-MM.json.gz   un fichier par mois de match
  Tennis_Edge_Lab/live/registre/index.json                 liste des mois
  Tennis_Edge_Lab/live/lectures_profils.json               évaluation après coup

Un mois clos ne change plus : seul le mois en cours est réécrit (croissance du
dépôt limitée). Un fichier n'est réécrit que si son contenu change.

Par match : tournoi, circuit, surface, joueurs, vainqueur ; pour chaque book
(Pinnacle d'abord) et chaque joueur, la cote à l'ouverture, à 24 h, 6 h, 1 h,
10 min et à la clôture ; la courbe Pinnacle complète (points où elle bouge) ;
les alertes (type, heure, book, cote, envoyée ou non) ; et à chaque horizon le
meilleur prix jouable / FR, la CLV, le P&L, et la LECTURE « matchs similaires
passés » telle qu'on l'aurait eue à ce moment-là (lectures_profils.py).
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import importlib.util
import io
import json
import pathlib
import sys

LAB = pathlib.Path(__file__).resolve().parent
OUT_DIR = "Tennis_Edge_Lab/live/registre"
OUT_EVAL = "Tennis_Edge_Lab/live/lectures_profils.json"
DETECTIONS = "Tennis_Edge_Lab/live/explorateur_detections.json.gz"
ALERTES = "Tennis_Edge_Lab/live/explorateur_alertes.json.gz"
MAX_SERIE = 80                      # points max de la courbe Pinnacle par joueur
CHECKPOINTS = ("open", "24h", "6h", "1h", "10m", "close")
HZ_COLS = ["horizon", "cote_pin", "proba_juste", "book_jouable", "cote_jouable", "book_fr", "cote_fr",
           "ecart_jouable_pct", "move_pin_pct", "alerte_avant", "clv_pinnacle", "clv_jouable", "clv_fr",
           "pnl_pinnacle", "pnl_jouable", "pnl_fr",
           "lecture_verdict", "lecture_n", "lecture_relaches", "lecture_exces", "lecture_exces_lo",
           "lecture_exces_hi", "lecture_base"]
ALERT_COLS = ["type", "cote_de", "minutes_avant", "book", "cote", "ampleur_pts", "envoyee", "clv_pin", "pnl"]


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_rm_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(LAB))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(LAB))
    return module


books = _load("books.py")
meta = _load("tennis_meta.py")
lp = _load("lectures_profils.py")


def _r(x, d=3):
    return None if x is None else round(x, d)


def _minutes(start, stamp):
    return round((start - stamp).total_seconds() / 60)


def _norm(name):
    return meta.norm_text(name or "").replace(" ", "")


def _downsample(points, n=MAX_SERIE):
    if len(points) <= n:
        return points
    step = (len(points) - 1) / (n - 1)
    keep = sorted({round(i * step) for i in range(n)})
    return [points[i] for i in keep]


def _dataset(root, rel):
    path = pathlib.Path(root) / rel
    if not path.is_file():
        return []
    doc = json.loads(gzip.decompress(path.read_bytes()))
    cols = doc["columns"]
    if cols and isinstance(cols[0], dict):
        cols = [c["name"] for c in cols]
    return [dict(zip(cols, r)) for r in doc.get("rows", [])]


def alerts_by_uid(root):
    """uid -> [alerte] depuis les alertes envoyées ET les détections du suivi officiel."""
    out = collections.defaultdict(list)
    seen = set()
    for rel, envoyee in ((DETECTIONS, None), (ALERTES, True)):
        for a in _dataset(root, rel):
            uid = a.get("uid")
            if not uid:
                continue
            key = (uid, a.get("type"), _norm(a.get("joueur")), str(a.get("_at"))[:16])
            if key in seen:
                continue
            seen.add(key)
            sent = envoyee if envoyee is not None else (a.get("envoyee") == "oui")
            out[uid].append({"type": a.get("type"), "joueur": a.get("joueur"), "at": a.get("_at"),
                             "book": a.get("book"), "cote": a.get("cote"), "ampleur_pts": a.get("ampleur_pts"),
                             "envoyee": sent, "gagne": a.get("gagne"), "pnl": a.get("pnl"),
                             "clv_pin": a.get("clv_pin"), "tournoi": a.get("tournoi"),
                             "circuit": a.get("circuit"), "surface": a.get("surface"),
                             "delai_min": a.get("delai_min")})
    return out


def _parse(at):
    try:
        t = dt.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def build_matches(sink, readings):
    records, series, rows = sink["records"], sink.get("series") or {}, sink["rows"]
    results, surfaces, pair_results = sink["results"], sink["surfaces"], sink.get("pair_results")
    alerts = alerts_by_uid(sink["root"])
    by_uid = collections.defaultdict(dict)
    for (uid, book), rec in records.items():
        by_uid[uid][book] = rec
    hz = collections.defaultdict(list)
    for r, L in zip(rows, readings):
        hz[r["_uid"]].append((r, L))
    book_ix = {}
    matches = []
    for uid, bks in by_uid.items():
        pin = bks.get("pinnacle")
        if pin is None:
            continue
        circuit = meta.circuit_of(pin["tournament"])
        if circuit not in ("ATP", "WTA", "Challenger", "Grand Chelem") or "double" in pin["tournament"].lower():
            continue
        start = pin["start"]
        players = (pin["home"], pin["away"])
        winner = (results.get(uid) or {}).get("match")
        if winner not in ("home", "away") and pair_results is not None:
            won = pair_results(players[0], players[1], start)
            winner = None if won is None else ("home" if won else "away")
        cotes = []
        order = sorted(bks, key=lambda b: (b != "pinnacle", not books.flags(b)["jouable"], b))
        for book in order:
            rec = bks[book]
            line = [book_ix.setdefault(book, len(book_ix))]
            for side in ("home", "away"):
                anchors = rec["curves"][side]
                pts = []
                for cp in CHECKPOINTS:
                    p = anchors[cp] if cp in ("open", "close") else anchors["horizons"].get(cp)
                    pts.append(None if p is None else [_minutes(start, p[0]), _r(p[1])])
                line.append(pts)
            if any(p for side in line[1:] for p in side):
                cotes.append(line)
        serie = {}
        for i, side in enumerate(("home", "away")):
            pts, last = [], None
            for t, o in sorted(set((series.get(uid) or {}).get(side) or [])):
                if o != last:
                    pts.append((t, o))
                    last = o
            serie[i] = [[_minutes(start, t), _r(o)] for t, o in _downsample(pts)]
        names = [_norm(p) for p in players]
        al = _alert_rows(alerts.get(uid, []), names, start)
        horizons = []
        for r, L in sorted(hz.get(uid, []), key=lambda x: (-lp.LEADS[x[0]["horizon"]], x[0]["joueur"] or "")):
            side = names.index(_norm(r["joueur"])) if _norm(r["joueur"]) in names else -1
            L = L or {}
            ci = L.get("exces_ci") or [None, None]
            horizons.append([side] + [
                r["horizon"], _r(r["cote_pin"]), _r(r.get("proba_juste"), 4), r.get("book_jouable"),
                _r(r.get("cote_jouable")), r.get("book_fr"), _r(r.get("cote_fr")), _r(r.get("ecart_jouable_pct"), 2),
                _r(r.get("move_pin_pct"), 2), r.get("alerte_avant"), _r(r.get("clv_pinnacle"), 2),
                _r(r.get("clv_jouable"), 2), _r(r.get("clv_fr"), 2), _r(r.get("pnl_pinnacle"), 4),
                _r(r.get("pnl_jouable"), 4), _r(r.get("pnl_fr"), 4),
                L.get("verdict"), L.get("n"), L.get("relaches"), _r(L.get("exces"), 2),
                _r(ci[0], 2), _r(ci[1], 2), _r(L.get("base"), 2)])
        matches.append({
            "uid": uid, "debut": start.isoformat(timespec="minutes"), "mois": start.strftime("%Y-%m"),
            "tournoi": pin["tournament"], "circuit": circuit, "surface": surfaces.lookup(pin["tournament"])[0],
            "joueurs": list(players), "vainqueur": {"home": 0, "away": 1}.get(winner),
            "cotes": cotes, "pinnacle": [serie[0], serie[1]], "alertes": al, "horizons": horizons,
        })
    merged, alone = attach_orphans(matches, alerts)
    matches.extend(alone)
    print(f"  alertes rattachées à un match à courbes par les joueurs : {merged} uid ; "
          f"matchs connus par leurs seules alertes : {len(alone)}")
    matches.sort(key=lambda m: (m["debut"], m["uid"]))
    return matches, list(book_ix)


def _pretty(slug):
    return " ".join(w.capitalize() for w in slug.split("_") if w)


def players_from_uid(uid, known, tournoi=None):
    """Les deux joueurs d'un uid d'alerte. Deux formats :
      « 2026-09-07_valerio_aboian_lorenzo_rottoli »  (date_joueur1_joueur2)
      « atp_stuttgart_alejandro_davidovich_fokina_vs_mattia_bellucci » (tournoi_joueur1_vs_joueur2)
    `known` = le joueur nommé par l'alerte, qui sert à couper au bon endroit."""
    slug = "_".join(meta.norm_text(known or "").split())
    if "_vs_" in uid:
        left, right = uid.split("_vs_", 1)
        prefix = ["_".join(meta.norm_text(tournoi or "").split())]
        for pre in prefix:
            if pre and left.startswith(pre + "_"):
                left = left[len(pre) + 1:]
        if slug and right == slug:
            return [_pretty(left), known]
        if slug and left.endswith(slug):
            return [known, _pretty(right)]
        return [_pretty(left), _pretty(right)]
    rest = uid.split("_", 1)[1] if uid[:4].isdigit() and "_" in uid else uid
    if slug and rest.startswith(slug + "_"):
        return [known, _pretty(rest[len(slug) + 1:])]
    if slug and rest.endswith("_" + slug):
        return [_pretty(rest[: -len(slug) - 1]), known]
    return [_pretty(rest), "?"]


def alert_only(uid, als):
    """Match connu SEULEMENT par ses alertes (pas de courbe collectée) : fiche réduite.
    Heure de début ESTIMÉE (heure de l'alerte + délai annoncé)."""
    starts = []
    for a in als:
        at = _parse(a["at"])
        if at is not None and a.get("delai_min") is not None:
            starts.append(at + dt.timedelta(minutes=a["delai_min"]))
    if not starts:
        return None
    starts.sort()
    start = starts[len(starts) // 2].replace(second=0, microsecond=0)
    first = next((a for a in als if a.get("tournoi")), als[0])
    players = players_from_uid(uid, als[0]["joueur"], first.get("tournoi"))
    names = [_norm(p) for p in players]
    winner = None
    for a in als:
        side = names.index(_norm(a["joueur"])) if _norm(a["joueur"]) in names else -1
        if winner is None and side >= 0 and a.get("gagne") is not None:
            winner = side if a["gagne"] else 1 - side
    return {"uid": uid, "debut": start.isoformat(timespec="minutes"), "mois": start.strftime("%Y-%m"),
            "debut_estime": True,
            "tournoi": first.get("tournoi") or "?", "circuit": first.get("circuit") or "?",
            "surface": next((a["surface"] for a in als if a.get("surface")), "inconnue"),
            "joueurs": players, "vainqueur": winner, "sans_courbe": True,
            "cotes": [], "pinnacle": [[], []], "alertes": _alert_rows(als, names, start), "horizons": []}


def _alert_rows(als, names, start):
    out = []
    for a in sorted(als, key=lambda a: str(a["at"])):
        side = names.index(_norm(a["joueur"])) if _norm(a["joueur"]) in names else -1
        at = _parse(a["at"])
        out.append([a["type"], side, None if at is None else _minutes(start, at), a["book"],
                    _r(a["cote"]), _r(a["ampleur_pts"], 2), 1 if a["envoyee"] else 0,
                    _r(a["clv_pin"], 2), _r(a["pnl"], 4)])
    return out


def attach_orphans(matches, alerts):
    """Alertes dont l'uid n'est pas celui d'un match à courbes : on cherche le même match
    (mêmes deux joueurs, début à moins de 3 jours de l'alerte) ; sinon fiche « alertes seules »."""
    by_pair = collections.defaultdict(list)
    for m in matches:
        by_pair[frozenset(_norm(p) for p in m["joueurs"])].append(m)
    known = {m["uid"] for m in matches}
    merged, alone = 0, []
    for uid, als in alerts.items():
        if uid in known:
            continue
        first = next((a for a in als if a.get("tournoi")), als[0])
        players = players_from_uid(uid, als[0]["joueur"], first.get("tournoi"))
        cands = by_pair.get(frozenset(_norm(p) for p in players), [])
        at = _parse(als[0]["at"])
        best = None
        for m in cands:
            gap = abs((dt.datetime.fromisoformat(m["debut"]) - at).total_seconds()) if at else None
            if gap is not None and gap <= 3 * 86400 and (best is None or gap < best[0]):
                best = (gap, m)
        if best:
            m = best[1]
            start = dt.datetime.fromisoformat(m["debut"])
            names = [_norm(p) for p in m["joueurs"]]
            m["alertes"] = sorted(m["alertes"] + _alert_rows(als, names, start),
                                  key=lambda a: -(a[2] if a[2] is not None else -1e9))
            merged += 1
        else:
            o = alert_only(uid, als)
            if o:
                alone.append(o)
    return merged, alone


def _gz(doc):
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as stream:
        stream.write(raw)
    return buffer.getvalue()


def _same(path, doc):
    """Même contenu, hors generated_at ?"""
    try:
        if path.suffix == ".gz":
            old = json.loads(gzip.decompress(path.read_bytes()))
        else:
            old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, EOFError):
        return False
    strip = lambda d: {k: v for k, v in d.items() if k != "generated_at"}
    return strip(old) == json.loads(json.dumps(strip(doc), ensure_ascii=False))


def write_month(root, mois, matches, book_names, now):
    path = pathlib.Path(root) / OUT_DIR / f"registre_{mois}.json.gz"
    used = sorted({c[0] for m in matches for c in m["cotes"]})
    remap = {old: new for new, old in enumerate(used)}
    for m in matches:
        for c in m["cotes"]:
            c[0] = remap[c[0]]
    doc = {"schema_version": 1, "mois": mois, "generated_at": now,
           "books": [{"nom": book_names[i], "jouable": books.flags(book_names[i])["jouable"],
                      "fr": books.flags(book_names[i])["jouable_fr"],
                      "commission": books.flags(book_names[i])["commission"]} for i in used],
           "points": list(CHECKPOINTS), "colonnes_horizons": HZ_COLS, "colonnes_alertes": ALERT_COLS,
           "matchs": matches}
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and _same(path, doc):
        return False, path
    path.write_bytes(_gz(doc))
    return True, path


def hypotheses_coherence(root):
    """Cohérence CLV → ROI des détections du suivi officiel, par hypothèse."""
    by_type = collections.defaultdict(list)
    for a in _dataset(root, DETECTIONS):
        if a.get("gagne") is None or a.get("pnl") is None or a.get("clv_pin") is None:
            continue
        eff = books.effective_odds(a.get("book"), a.get("cote"))
        for k in (a.get("type"), "toutes"):
            by_type[k].append((eff, a["clv_pin"], a["pnl"]))
    out = []
    for k in sorted(by_type, key=lambda t: (t == "toutes", str(t))):
        c = lp.coherence(by_type[k])
        c["hypothese"] = k
        out.append(c)
    return out


def run(sink):
    root = pathlib.Path(sink["root"])
    rows = sink["rows"]
    readings = lp.compute(rows)
    matches, book_names = build_matches(sink, readings)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    by_month = collections.defaultdict(list)
    for m in matches:
        by_month[m["mois"]].append(m)
    months, changed = [], 0
    for mois in sorted(by_month):
        ch, path = write_month(root, mois, by_month[mois], book_names, now)
        changed += ch
        months.append({"mois": mois, "matchs": len(by_month[mois]), "fichier": path.name,
                       "octets": path.stat().st_size})
    index = {"schema_version": 1, "generated_at": now, "mois": months,
             "matchs": len(matches), "points": list(CHECKPOINTS)}
    ipath = root / OUT_DIR / "index.json"
    if not (ipath.is_file() and _same(ipath, index)):
        ipath.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ev = {"schema_version": 1, "generated_at": now,
          "lectures": lp.evaluate(rows, readings),
          "fiabilite_cloture": lp.fiabilite(rows),
          "coherence_matchs": lp.coherence_rows(rows),
          "coherence_hypotheses": hypotheses_coherence(root),
          "regles": {"connu": f"un match passé n'entre dans une lecture que {lp.DELAI_CONNU_H} h après son début",
                     "alpha": lp.ALPHA,
                     "attendu": "gain attendu par pari = CLV Pinnacle sans marge / 100 (si la clôture est juste)"}}
    epath = root / OUT_EVAL
    if not (epath.is_file() and _same(epath, ev)):
        epath.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # V7.5 : le prix tient-il après l'alerte ? (délai alerte -> pari)
    try:
        _load("delai_alertes.py").run(sink)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"::warning::delai_alertes.json non mis à jour ({type(exc).__name__}: {exc})")
    # V7.4 : H19 « valeur contre Pinnacle juste » et sa grille (même lecture des partitions).
    try:
        _load("valeur.py").run(sink)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"::warning::valeur.json non mis à jour ({type(exc).__name__}: {exc})")
    L = ev["lectures"]
    print(f"Registre : {len(matches)} matchs sur {len(months)} mois ({changed} fichier(s) réécrit(s)) ; "
          f"{L['lignes_lues']} lectures rejouées ; corrélation excès prédit/réalisé "
          f"{'—' if L['correlation'] is None else round(L['correlation'], 3)}")
    return ev
