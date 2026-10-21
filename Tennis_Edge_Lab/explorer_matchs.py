#!/usr/bin/env python3
"""V6.9 — Jeu « Tous les matchs collectés » de l'Explorateur (lecture seule).

Une ligne par (match, côté, horizon de décision ∈ {24h, 6h, 1h, 10m}) pour
chaque match suivi depuis juin (ATP, WTA, Challenger, Grand Chelem), seulement
si Pinnacle cote les DEUX côtés à cet horizon (fenêtres de fraîcheur
HORIZONS de bookmakers_sets_v5 : 12 h, 3 h, 1 h, 50 min).

Sources : parts/hist_book_* (historique figé servi par R2 : matérialisé quand
R2_HIST_MATERIALIZE=1) + ticks récents parts/live_match_* (points avant le
début seulement). Résultat : set_results.json (uid), sinon index des matchs
(paire de joueurs). Clôture = dernier point Pinnacle avant le début.

Prix d'entrée possibles (choisis dans l'Explorateur) :
  pinnacle : cote Pinnacle à l'horizon ;
  jouable  : meilleur prix d'un book jouable hors Pinnacle, cote de moins de
             30 min à la décision, commission de bourse déduite ;
  fr       : meilleur prix d'un opérateur agréé ANJ (mêmes règles).
CLV : books.clv_pin_pct (dé-margination puissance) ; P&L : books.pnl.
Les champs après coup (clôture, mouvement horizon→clôture) sont descriptifs.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import gzip
import importlib.util
import io
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = pathlib.Path(__file__).resolve().parent
OUTPUT = "Tennis_Edge_Lab/live/explorateur_matchs.json.gz"
SINCE = "2026-06-01"
CIRCUITS = ("ATP", "WTA", "Challenger", "Grand Chelem")
MAX_ENTRY_AGE_MIN = 30
HORIZON_ORDER = ("24h", "6h", "1h", "10m")


def _load(name, folder=LAB):
    path = pathlib.Path(folder) / name
    spec = importlib.util.spec_from_file_location("tennis_edge_m_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    added = str(path.parent) not in sys.path
    if added:
        sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(str(path.parent))
    return module


books = _load("books.py")
meta = _load("tennis_meta.py")
engine = _load("bookmakers_sets_v5.py")

# (nom, libellé, type, rôle). type : cat | num ; rôle : filtre | mesure | descriptif | post_entree
FIELDS = [
    ("mois", "Mois", "cat", "filtre"),
    ("circuit", "Circuit", "cat", "filtre"),
    ("tournoi", "Tournoi", "cat", "filtre"),
    ("surface", "Surface", "cat", "filtre"),
    ("horizon", "Horizon de décision", "cat", "filtre"),
    ("tranche_cote", "Cote Pinnacle (tranche)", "cat", "filtre"),
    ("cote_pinnacle", "Favori/outsider (Pinnacle)", "cat", "filtre"),
    ("alerte_avant", "Alerte avant l'horizon", "cat", "filtre"),
    ("book_jouable", "Meilleur book jouable", "cat", "filtre"),
    ("book_fr", "Meilleur book FR", "cat", "filtre"),
    ("cote_pin", "Cote Pinnacle", "num", "filtre"),
    ("move_pin_pct", "Mouvement Pinnacle ouverture→horizon (%)", "num", "filtre"),
    ("ampleur_pts", "Mouvement de probabilité (pts)", "num", "filtre"),
    ("age_marche_h", "Âge du marché Pinnacle (h)", "num", "filtre"),
    ("nb_books", "Books qui cotent", "num", "filtre"),
    ("ecart_jouable_pct", "Écart meilleur jouable vs Pinnacle juste (%)", "num", "filtre"),
    ("ecart_fr_pct", "Écart meilleur FR vs Pinnacle juste (%)", "num", "filtre"),
    ("cote_jouable", "Meilleure cote jouable (nette)", "num", "filtre"),
    ("cote_fr", "Meilleure cote FR", "num", "filtre"),
    ("date", "Date", "cat", "descriptif"),
    ("joueur", "Joueur", "cat", "descriptif"),
    ("gagne", "Gagné (1/0)", "num", "mesure"),
    ("clv_pinnacle", "CLV Pinnacle — entrée Pinnacle", "num", "mesure"),
    ("clv_jouable", "CLV Pinnacle — entrée meilleur jouable", "num", "mesure"),
    ("clv_fr", "CLV Pinnacle — entrée meilleur FR", "num", "mesure"),
    ("pnl_pinnacle", "P&L — entrée Pinnacle", "num", "mesure"),
    ("pnl_jouable", "P&L — entrée meilleur jouable", "num", "mesure"),
    ("pnl_fr", "P&L — entrée meilleur FR", "num", "mesure"),
    ("decision_ts", "Heure de décision (UTC)", "cat", "descriptif"),
    # V7.2 : probabilité Pinnacle JUSTE (puissance) à l'horizon, pour « gagnés vs implicite ».
    ("proba_juste", "Probabilité Pinnacle juste à l'horizon", "num", "descriptif"),
    ("cloture_pin", "Clôture Pinnacle (après coup)", "num", "post_entree"),
    ("move_cloture_pct", "Mouvement horizon→clôture (après coup)", "num", "post_entree"),
]
FILTER_FIELDS = [f[0] for f in FIELDS if f[3] == "filtre"]
ENTRIES = ("pinnacle", "jouable", "fr")
ROUND = {"cote_pin": 3, "move_pin_pct": 2, "ampleur_pts": 2, "age_marche_h": 1, "ecart_jouable_pct": 2,
         "ecart_fr_pct": 2, "cote_jouable": 3, "cote_fr": 3, "clv_pinnacle": 2, "clv_jouable": 2,
         "clv_fr": 2, "pnl_pinnacle": 4, "pnl_jouable": 4, "pnl_fr": 4, "cloture_pin": 3,
         "move_cloture_pct": 2, "gagne": 0, "nb_books": 0, "proba_juste": 4}


# ---------------------------------------------------------------- lecture
def materialize(environ=None) -> dict:
    """Rapatrie depuis R2 l'historique figé (parts/hist_book_*) si R2_HIST_MATERIALIZE=1.

    Délégué à scripts/r2_io.materialize_hist (ne lève jamais)."""
    environ = os.environ if environ is None else environ
    if environ.get("R2_HIST_MATERIALIZE") != "1":
        return {}
    try:
        r2_io = _load("r2_io.py", ROOT / "scripts")
        return r2_io.materialize_hist("book", environ=environ) or {}
    except Exception as exc:  # noqa: BLE001
        print(f"  [r2] historique non rapatrié ({type(exc).__name__}) — copies locales seules")
        return {}


@contextlib.contextmanager
def _cwd(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def hist_paths(root) -> list[pathlib.Path]:
    """Partitions hist_book_* sans doublon .jsonl/.jsonl.gz (règle d'oddspapi_v5)."""
    parts = pathlib.Path(root) / "parts"
    plain = {p.name: p for p in parts.glob("hist_book_*.jsonl")}
    gz = {p.name[:-3]: p for p in parts.glob("hist_book_*.jsonl.gz")}
    names = sorted(set(plain) | set(gz))
    return [gz.get(n) or plain[n] for n in names]


def _lines(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield line


def collect(root, counters, series=None, series_books=None, uids_books=None):
    """records[(uid, book)] = {start, home, away, tournament, curves: {side: anchors}}.

    V7.3 : si `series` est un dict, la courbe Pinnacle complète (points où la cote
    change) y est gardée : series[uid][side] = [(heure, cote)] — pour le registre."""
    records = {}

    def add(uid, book, start, home, away, tournament, home_curve, away_curve):
        points = {side: engine._curve_points(curve, start, counters)
                  for side, curve in (("home", home_curve), ("away", away_curve))}
        curves = {side: engine._anchors(points[side], start) for side in ("home", "away")}
        if series_books is not None and uids_books and uid in uids_books:
            # V7.5 : courbe complète de CHAQUE book pour les matchs alertés (délai alerte → pari).
            dest_b = series_books.setdefault(uid, {}).setdefault(book, {"home": [], "away": []})
            for side in ("home", "away"):
                for stamp, odds, _ in points[side]:
                    dest_b[side].append((stamp, odds))
        if series is not None and book == "pinnacle":
            dest = series.setdefault(uid, {"home": [], "away": []})
            for side in ("home", "away"):
                last = None
                for stamp, odds, _ in points[side]:
                    if odds != last:
                        dest[side].append((stamp, odds))
                        last = odds
        key = (uid, book)
        prev = records.get(key)
        if prev is None:
            records[key] = {"start": start, "home": home, "away": away, "tournament": tournament or "",
                            "curves": curves}
        elif prev["start"] == start:
            prev["curves"] = {s: engine._merge_anchor(prev["curves"][s], curves[s]) for s in ("home", "away")}
            if not prev["tournament"] and tournament:
                prev["tournament"] = tournament
        else:
            counters["conflits_horaire"] += 1

    for path in hist_paths(root):
        counters["partitions_hist"] += 1
        for line in _lines(path):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            start = engine.parse_time(row.get("commence_time"))
            if start is None or not row.get("uid") or not row.get("book"):
                continue
            if start.date().isoformat() < SINCE:
                continue
            add(row["uid"], str(row["book"]).lower(), start, row.get("home"), row.get("away"),
                row.get("tournament"), row.get("home_curve"), row.get("away_curve"))
    # Ticks récents (live_match) : points avant le début, regroupés par match et book.
    ticks = collections.defaultdict(lambda: {"home": [], "away": [], "info": None})
    for path in sorted((pathlib.Path(root) / "parts").glob("live_match_*.jsonl*")):
        counters["partitions_live"] += 1
        for line in _lines(path):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not row.get("uid") or not row.get("book") or not row.get("t"):
                continue
            key = (row["uid"], str(row["book"]).lower())
            t = ticks[key]
            t["info"] = (row.get("commence_time"), row.get("home"), row.get("away"), row.get("tournament"))
            if row.get("ho"):
                t["home"].append([row["t"], row["ho"]])
            if row.get("ao"):
                t["away"].append([row["t"], row["ao"]])
    for (uid, book), t in ticks.items():
        start = engine.parse_time(t["info"][0])
        if start is None or start.date().isoformat() < SINCE:
            continue
        add(uid, book, start, t["info"][1], t["info"][2], t["info"][3], t["home"], t["away"])
    return records


def alert_index(root):
    """(uid, joueur) -> [(heure, type)] depuis le jeu des alertes de l'Explorateur."""
    path = pathlib.Path(root) / "Tennis_Edge_Lab/live/explorateur_alertes.json.gz"
    out = collections.defaultdict(list)
    if not path.is_file():
        return out
    doc = json.loads(gzip.decompress(path.read_bytes()))
    cols = doc["columns"]
    iu, ij, it, ia = cols.index("uid"), cols.index("joueur"), cols.index("type"), cols.index("_at")
    for r in doc["rows"]:
        group = "H" if str(r[it]).startswith("H") else r[it]
        out[(r[iu], meta.norm_text(r[ij]).replace(" ", ""))].append((engine.parse_time(r[ia]), group))
    return out


# ---------------------------------------------------------------- lignes
def _side_quote(record, side, horizon):
    return record["curves"][side]["horizons"].get(horizon) if record else None


def build_rows(records, results, alerts, surfaces, pair_results=None):
    by_uid = collections.defaultdict(dict)
    for (uid, book), rec in records.items():
        by_uid[uid][book] = rec
    rows = []
    for uid, bks in by_uid.items():
        pin = bks.get("pinnacle")
        if pin is None:
            continue
        circuit = meta.circuit_of(pin["tournament"])
        if circuit not in CIRCUITS or "double" in pin["tournament"].lower():
            continue
        start = pin["start"]
        winner = (results.get(uid) or {}).get("match")
        for horizon in HORIZON_ORDER:
            lead, _ = engine.HORIZONS[horizon]
            decision = start - dt.timedelta(minutes=lead)
            ph, pa = _side_quote(pin, "home", horizon), _side_quote(pin, "away", horizon)
            if ph is None or pa is None or abs((ph[0] - pa[0]).total_seconds()) > 1800:
                continue
            for side in ("home", "away"):
                other = "away" if side == "home" else "home"
                quote, opp = (ph, pa) if side == "home" else (pa, ph)
                player = pin[side]
                won = None
                if winner in ("home", "away"):
                    won = winner == side
                elif pair_results is not None:
                    won = pair_results(player, pin[other], start)
                op_s, op_o = pin["curves"][side]["open"], pin["curves"][other]["open"]
                cl_s, cl_o = pin["curves"][side]["close"], pin["curves"][other]["close"]
                fair_h = books.fair_close(quote[1], opp[1])
                fair_open = books.fair_close(op_s[1], op_o[1]) if op_s and op_o else None
                best = {"jouable": None, "fr": None}
                n_books = 0
                for book, rec in bks.items():
                    q = _side_quote(rec, side, horizon)
                    if q is None:
                        continue
                    n_books += 1
                    if book == "pinnacle":
                        continue
                    flags = books.flags(book)
                    if not flags["jouable"] or (decision - q[0]).total_seconds() / 60 > MAX_ENTRY_AGE_MIN:
                        continue
                    eff = books.effective_odds(book, q[1])
                    for kind, ok in (("jouable", True), ("fr", flags["jouable_fr"])):
                        if ok and (best[kind] is None or eff > best[kind][1]):
                            best[kind] = (book, eff, q[1])
                closing_ok = cl_s and cl_o and cl_s[0] > decision and cl_o[0] > decision
                def clv(book, odds):
                    return books.clv_pin_pct(book, odds, cl_s[1], cl_o[1]) if closing_ok and odds else None
                def pnl(book, odds):
                    return books.pnl(book, odds, won) if won is not None and odds else None
                key = (uid, meta.norm_text(player).replace(" ", ""))
                fired = sorted({kind for at, kind in alerts.get(key, []) if at is not None and at < decision})
                row = {
                    "mois": start.strftime("%Y-%m"), "circuit": circuit, "tournoi": pin["tournament"],
                    "surface": surfaces.lookup(pin["tournament"])[0], "horizon": horizon,
                    "tranche_cote": meta.odds_band(quote[1]),
                    "cote_pinnacle": "favori" if quote[1] < opp[1] else "outsider",
                    "alerte_avant": "+".join(fired) if fired else "aucune",
                    "book_jouable": best["jouable"][0] if best["jouable"] else "aucun",
                    "book_fr": best["fr"][0] if best["fr"] else "aucun",
                    "cote_pin": quote[1],
                    "move_pin_pct": 100 * (quote[1] / op_s[1] - 1) if op_s else None,
                    "ampleur_pts": 100 * (1 / fair_h - 1 / fair_open) if fair_h and fair_open else None,
                    "age_marche_h": (decision - op_s[0]).total_seconds() / 3600 if op_s else None,
                    "nb_books": n_books,
                    "ecart_jouable_pct": 100 * (best["jouable"][1] / fair_h - 1) if best["jouable"] and fair_h else None,
                    "ecart_fr_pct": 100 * (best["fr"][1] / fair_h - 1) if best["fr"] and fair_h else None,
                    "cote_jouable": best["jouable"][1] if best["jouable"] else None,
                    "cote_fr": best["fr"][2] if best["fr"] else None,
                    "date": start.date().isoformat(), "joueur": player, "_uid": uid,
                    "gagne": None if won is None else int(won),
                    "clv_pinnacle": clv("pinnacle", quote[1]),
                    "clv_jouable": clv(best["jouable"][0], best["jouable"][2]) if best["jouable"] else None,
                    "clv_fr": clv(best["fr"][0], best["fr"][2]) if best["fr"] else None,
                    "pnl_pinnacle": pnl("pinnacle", quote[1]),
                    "pnl_jouable": pnl(best["jouable"][0], best["jouable"][2]) if best["jouable"] else None,
                    "pnl_fr": pnl(best["fr"][0], best["fr"][2]) if best["fr"] else None,
                    "decision_ts": decision.isoformat(timespec="minutes"),
                    "proba_juste": 1 / fair_h if fair_h else None,
                    "cloture_pin": cl_s[1] if closing_ok else None,
                    "move_cloture_pct": 100 * (cl_s[1] / quote[1] - 1) if closing_ok else None,
                }
                rows.append(row)
    rows.sort(key=lambda r: (r["decision_ts"], r["joueur"] or ""))
    return rows


def encode(rows) -> dict:
    """Colonnes : catégories codées en entiers (dictionnaire), nombres arrondis, null si absent."""
    columns, dicts, data = [], {}, {}
    for name, label, kind, role in FIELDS:
        columns.append({"name": name, "label": label, "type": kind, "role": role})
        values = [r.get(name) for r in rows]
        if kind == "cat":
            index, codes = {}, []
            for v in values:
                v = "inconnu" if v is None else str(v)
                if v not in index:
                    index[v] = len(index)
                codes.append(index[v])
            dicts[name] = list(index)
            data[name] = codes
        else:
            digits = ROUND.get(name, 3)
            data[name] = [None if v is None else (round(v) if digits == 0 else round(v, digits)) for v in values]
    return {"columns": columns, "dicts": dicts, "data": data, "n": len(rows)}


def build(root=ROOT, environ=None, sink=None) -> dict:
    """`sink` (dict, facultatif) reçoit les matériaux du registre V7.3 : records,
    courbes Pinnacle, lignes, résultats, surfaces — une seule lecture des partitions."""
    root = pathlib.Path(root)
    materialize(environ)
    counters = collections.Counter()
    explorer = _load("explorer_build.py")
    series = {} if sink is not None else None
    series_books, uids_books = None, None
    if sink is not None:
        try:
            uids_books = _load("delai_alertes.py").alert_uids(root)
            series_books = {}
        except Exception as exc:  # noqa: BLE001
            print(f"  [délai alertes] journaux illisibles ({type(exc).__name__}) — étude sautée")
    records = collect(root, counters, series, series_books, uids_books)
    if series_books is not None:
        for uid, bks in series_books.items():
            for book, sides in bks.items():
                for side in ("home", "away"):
                    pts, last = [], None
                    for t, o in sorted(set(sides[side])):
                        if o != last:
                            pts.append((t, o))
                            last = o
                    sides[side] = pts
    results = engine.load_results(root)
    pair = explorer.Results(root)

    def pair_results(player, opponent, start):
        won, _ = pair.won(None, None, player, start, opponent)
        return won
    surfaces = meta.SurfaceMap(root / "historique/tennis_data.csv.gz")
    rows = build_rows(records, results, alert_index(root), surfaces, pair_results)
    if sink is not None:
        sink.update({"records": records, "series": series, "series_books": series_books or {},
                     "rows": rows, "results": results,
                     "surfaces": surfaces, "pair_results": pair_results, "root": root})
    doc = encode(rows)
    doc.update({
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "entrees": {"pinnacle": "Cote Pinnacle à l'horizon",
                    "jouable": "Meilleur book jouable (hors Pinnacle, < 30 min, commission déduite)",
                    "fr": "Meilleur opérateur agréé ANJ (< 30 min)"},
        "summary": {
            "lignes": len(rows), "matchs": len({r["_uid"] for r in rows}),
            "avec_resultat": sum(1 for r in rows if r["gagne"] is not None),
            "avec_clv": sum(1 for r in rows if r["clv_pinnacle"] is not None),
            "avec_jouable": sum(1 for r in rows if r["cote_jouable"] is not None),
            "avec_fr": sum(1 for r in rows if r["cote_fr"] is not None),
            "par_horizon": dict(collections.Counter(r["horizon"] for r in rows)),
            "periode": [rows[0]["date"], rows[-1]["date"]] if rows else None,
            "sources": dict(counters),
        },
        "notes": {
            "horizon": "Pinnacle doit coter les deux côtés à l'horizon (fenêtres 12 h, 3 h, 1 h, 50 min).",
            "entree": "Meilleur prix jouable/FR : cote de moins de 30 min à la décision, commission Betfair déduite.",
            "post_entree": "Clôture et mouvement horizon→clôture : descriptifs, jamais des filtres.",
            "cotes": "Collecte des courbes en pause jusqu'au 27/10 : peu de nouveaux matchs d'ici là.",
        },
    })
    return doc


def write(root, doc) -> bool:
    path = pathlib.Path(root) / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            old = json.loads(gzip.decompress(path.read_bytes()))
            if {k: v for k, v in old.items() if k != "generated_at"} == \
                    json.loads(json.dumps({k: v for k, v in doc.items() if k != "generated_at"})):
                return False
        except (OSError, ValueError, EOFError):
            pass
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as stream:
        stream.write(raw)
    path.write_bytes(buffer.getvalue())
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(ROOT))
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    sink = {}
    doc = build(root, sink=sink)
    changed = write(root, doc)
    s = doc["summary"]
    size = (root / OUTPUT).stat().st_size
    print(f"Explorateur — tous les matchs : {s['lignes']} lignes, {s['avec_resultat']} avec résultat, "
          f"{s['avec_clv']} avec CLV ; {size / 1e6:.2f} Mo gz ({'modifié' if changed else 'inchangé'}) ; "
          f"horizons {s['par_horizon']}")
    # V7.3 : registre de tous les matchs + lectures des profils rejouées dans le temps.
    # Une panne ici ne bloque jamais le jeu de l'Explorateur (déjà écrit).
    try:
        _load("registre_matchs.py").run(sink)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"::warning::Registre des matchs non mis à jour ({type(exc).__name__}: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
