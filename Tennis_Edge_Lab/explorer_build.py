#!/usr/bin/env python3
"""V6.7 — Jeux de données de l'onglet « Explorateur » (lecture seule).

A) live/explorateur_alertes.json.gz : une ligne par alerte envoyée
   - H13…H18 : *_signal_log.jsonl, envoye=true et sans doublon ;
   - PUBLIC   : canal_public_log.jsonl (« Évolution de cote »), première
                alerte par uid + joueur ; prix d'entrée = meilleur book EN RETARD
                jouable (books.py : 4casters, sbobet, sharpbet exclus) ;
   - MOUVEMENT: odds_alerts_log.jsonl (« Mouvement de cote », privé), première
                alerte par uid + côté renforcé (cote en baisse) ; le journal
                ne nomme aucun book : prix = dernière cote de référence du
                journal, book « médiane/ref », NON jouable.
   Clôture Pinnacle (deux côtés) : clv_history.jsonl, points strictement avant
   le début ; CLV via books.clv_pin_pct (dé-margination puissance) ; P&L via
   books.pnl (commission Betfair). Résultat : set_results.json par uid
   clv_history et côté, sinon index des matchs d'autoresearch (date + paire).
B) live/explorateur_histo.json.gz : cube agrégé tennis-data (clôture Pinnacle
   brute) par année × circuit × surface × niveau × côté × tranche de cote.

Les champs connus seulement APRÈS l'entrée (post_entree) ne sont jamais des
filtres. `suivie_public` est connu après l'alerte H (mais avant le match) :
filtre descriptif signalé, interdit dans un gel.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import importlib.util
import io
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = pathlib.Path(__file__).resolve().parent
OUT_ALERTS = "Tennis_Edge_Lab/live/explorateur_alertes.json.gz"
OUT_HISTO = "Tennis_Edge_Lab/live/explorateur_histo.json.gz"
H_LOGS = ("h13", "h15", "h16", "h16b", "h17", "h18")
REF_BOOK = "médiane/ref"


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_x_" + name[:-3], path)
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


books = _load("books.py")
meta = _load("tennis_meta.py")

# (nom, libellé, rôle) — rôle : filtre | filtre_apres_alerte | mesure | descriptif | post_entree
FIELDS = [
    ("type", "Type d'alerte", "filtre"),
    ("mois", "Mois", "filtre"),
    ("circuit", "Circuit", "filtre"),
    ("tournoi", "Tournoi", "filtre"),
    ("surface", "Surface", "filtre"),
    ("tranche_cote", "Cote d'entrée", "filtre"),
    ("cote_pinnacle", "Favori/outsider (Pinnacle)", "filtre"),
    ("tranche_delai", "Délai avant match", "filtre"),
    ("tranche_ampleur", "Ampleur du mouvement", "filtre"),
    ("book", "Book d'entrée", "filtre"),
    ("jouable", "Book jouable", "filtre"),
    ("jouable_fr", "Jouable en France", "filtre"),
    ("bourse", "Bourse (Betfair…)", "filtre"),
    ("precede_par_H", "Précédée d'une alerte H", "filtre"),
    ("nb_alertes_match", "Alertes sur le match", "filtre"),
    ("pin_move_avant", "Mouvement Pinnacle ouverture→entrée", "filtre"),
    ("pin_points", "Points Pinnacle avant entrée", "filtre"),
    ("pin_age", "Ancienneté du marché Pinnacle", "filtre"),
    ("suivie_public", "Suivie d'une alerte publique", "filtre_apres_alerte"),
    ("date", "Date", "descriptif"),
    ("joueur", "Joueur", "descriptif"),
    ("uid", "Match", "descriptif"),
    ("cote", "Cote d'entrée", "mesure"),
    ("gagne", "Gagné (1/0)", "mesure"),
    ("pnl", "P&L (1 unité)", "mesure"),
    ("clv_pin", "CLV Pinnacle %", "mesure"),
    ("pin_close", "Clôture Pinnacle (côté)", "descriptif"),
    ("pin_close_adv", "Clôture Pinnacle (adverse)", "descriptif"),
    ("minutes_vers_public", "Minutes jusqu'à l'alerte publique", "descriptif"),
    ("minutes_depuis_H", "Minutes depuis l'alerte H", "descriptif"),
    ("pin_move_entree_cloture", "Mouvement Pinnacle entrée→clôture (après coup)", "post_entree"),
]
FILTER_FIELDS = [name for name, _, role in FIELDS if role == "filtre"]
FREEZE_FORBIDDEN = {name for name, _, role in FIELDS if role != "filtre"}


def parse_time(value):
    if not value:
        return None
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    # Les journaux du dépôt sont écrits en UTC sans fuseau.
    return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def name_key(value):
    return meta.norm_text(value).replace(" ", "")


def read_jsonl(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


class PinnacleIndex:
    """clv_history.jsonl : courbes Pinnacle par match, points avant le début uniquement."""

    def __init__(self, path):
        self.by_player = collections.defaultdict(list)
        for record in read_jsonl(path):
            start = parse_time(record.get("commence_time"))
            if start is None:
                continue
            curves = {}
            for side in ("home", "away"):
                pts = []
                for point in record.get(f"{side}_curve") or []:
                    t = parse_time(point[0]) if isinstance(point, (list, tuple)) and len(point) >= 2 else None
                    try:
                        odds = float(point[1])
                    except (TypeError, ValueError, IndexError):
                        continue
                    if t is not None and t < start and odds > 1:
                        pts.append((t, odds))
                pts.sort()
                curves[side] = pts
            item = {"uid": record.get("uid"), "start": start, "home": record.get("home"),
                    "away": record.get("away"), "curves": curves}
            for side in ("home", "away"):
                self.by_player[name_key(record.get(side))].append(item)

    def find(self, player, start, opponent=None):
        best = None
        for item in self.by_player.get(name_key(player), []):
            gap = abs((item["start"] - start).total_seconds()) if start else 0
            if gap > 36 * 3600:
                continue
            if opponent and name_key(opponent) not in (name_key(item["home"]), name_key(item["away"])):
                continue
            if best is None or gap < best[0]:
                best = (gap, item)
        if best is None:
            return None, None
        item = best[1]
        side = "home" if name_key(item["home"]) == name_key(player) else "away"
        return item, side


def _last_at(points, t):
    last = None
    for when, odds in points:
        if when > t:
            break
        last = (when, odds)
    return last


def pinnacle_features(item, side, at):
    other = "away" if side == "home" else "home"
    pts, opp = item["curves"].get(side) or [], item["curves"].get(other) or []
    out = {"pin_close": None, "pin_close_adv": None, "pin_move_avant": "sans courbe",
           "pin_points": "sans courbe", "pin_age": "sans courbe", "cote_pinnacle": "inconnu",
           "pin_move_entree_cloture": None}
    if pts and opp:
        out["pin_close"], out["pin_close_adv"] = pts[-1][1], opp[-1][1]
    before = [p for p in pts if p[0] <= at]
    entry, entry_adv = _last_at(pts, at), _last_at(opp, at)
    if before:
        move = 100 * (before[-1][1] / before[0][1] - 1)
        out["pin_move_avant"] = meta.band(move, meta.PIN_MOVE_BANDS)
        out["pin_points"] = meta.band(len(before), ((0, 10, "< 10"), (10, 50, "10–50"),
                                                    (50, 200, "50–200"), (200, None, "≥ 200")))
        age_h = (at - before[0][0]).total_seconds() / 3600
        out["pin_age"] = meta.band(age_h, ((0, 6, "< 6 h"), (6, 24, "6–24 h"), (24, 72, "24–72 h"),
                                           (72, None, "≥ 72 h")))
        if out["pin_close"]:
            out["pin_move_entree_cloture"] = round(100 * (out["pin_close"] / before[-1][1] - 1), 2)
    if entry and entry_adv:
        out["cote_pinnacle"] = "favori" if entry[1] < entry_adv[1] else "outsider"
    return out


class Results:
    """Résultat : set_results.json (uid clv_history), sinon index autoresearch."""

    def __init__(self, root):
        root = pathlib.Path(root)
        path = root / "set_results.json"
        self.sets = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        self.index = {}
        try:
            ar = _load("autoresearch.py")
            ar.ROOT = root
            _, matches, _ = ar.create_match_index()
            for m in matches if isinstance(matches, list) else matches.values():
                if m.get("winner") and m.get("status") != "conflit":
                    pair = tuple(sorted((name_key(m.get("home")), name_key(m.get("away")))))
                    self.index[(m["date"], pair)] = name_key(m["winner"])
        except Exception as exc:  # repli silencieux interdit : on le signale
            print(f"Avertissement : index des résultats autoresearch indisponible ({exc})")

    def won(self, item, side, player, start, opponent=None):
        """Jamais par le seul nom du joueur : la PAIRE de joueurs est exigée.

        (Un repli « joueur + jour voisin » biaiserait vers les gagnants, qui
        rejouent le lendemain.)"""
        if item is not None:
            res = (self.sets.get(item["uid"]) or {}).get("match")
            if res in ("home", "away"):
                return res == side, "set_results"
            opponent = opponent or (item["away"] if side == "home" else item["home"])
        if start is not None and opponent:
            pair = tuple(sorted((name_key(player), name_key(opponent))))
            for delta in (0, -1, 1):
                day = (start + dt.timedelta(days=delta)).date().isoformat()
                winner = self.index.get((day, pair))
                if winner:
                    return winner == name_key(player), "index des matchs (paire)"
        return None, "inconnu"


def _alert(kind, uid, player, opponent, tournament, at, start, odds, book, ampleur):
    return {"type": kind, "uid": uid, "joueur": player, "adversaire": opponent,
            "tournoi": tournament or "?", "at": at, "start": start, "cote": odds,
            "book": book, "ampleur": ampleur}


def collect_alerts(root):
    root = pathlib.Path(root)
    alerts = []
    for name in H_LOGS:
        for r in read_jsonl(root / f"{name}_signal_log.jsonl"):
            if r.get("envoye") is not True or r.get("doublon"):
                continue
            at = parse_time(r.get("signale_le")) or parse_time(r.get("detecte_le"))
            start = parse_time(r.get("commence"))
            try:
                odds = float(r.get("cote"))
            except (TypeError, ValueError):
                continue
            alerts.append(_alert(name.upper(), r.get("uid"), r.get("joueur"), r.get("adversaire"),
                                 r.get("tournoi"), at, start, odds, books.normalize(r.get("book")),
                                 r.get("ampleur_pts")))
    seen = set()
    for r in sorted(read_jsonl(root / "canal_public_log.jsonl"), key=lambda x: str(x.get("t"))):
        key = (r.get("uid"), name_key(r.get("joueur")))
        if key in seen:
            continue
        seen.add(key)
        lagging = [(books.normalize(b[0]), float(b[1])) for b in (r.get("retards_tous") or r.get("retards") or [])
                   if isinstance(b, (list, tuple)) and len(b) >= 2 and books.flags(b[0])["jouable"]]
        if lagging:
            book, odds = max(lagging, key=lambda item: item[1])
        else:
            book, odds = "aucun retard jouable", r.get("cote_ref_apres")
        at, start = parse_time(r.get("t")), parse_time(r.get("commence"))
        ampleur = r.get("ampleur_pts")
        if ampleur is None and r.get("cote_ref_avant") and r.get("cote_ref_apres"):
            ampleur = 100 * (1 / r["cote_ref_apres"] - 1 / r["cote_ref_avant"])
        alerts.append(_alert("PUBLIC", r.get("uid"), r.get("joueur"), None, r.get("tournoi"),
                             at, start, odds, book, ampleur))
    seen = set()
    for r in sorted(read_jsonl(root / "odds_alerts_log.jsonl"), key=lambda x: str(x.get("logged_at"))):
        mh, ma = r.get("mv_home_pct"), r.get("mv_away_pct")
        if mh is None or ma is None:
            continue
        side = "home" if mh < ma else "away"
        key = (r.get("uid"), side)
        if key in seen:
            continue
        seen.add(key)
        first, last = r.get(f"o_{side}_first"), r.get(f"o_{side}_last")
        if not first or not last:
            continue
        player = r.get(side)
        opponent = r.get("away" if side == "home" else "home")
        alerts.append(_alert("MOUVEMENT", r.get("uid"), player, opponent, r.get("tournament"),
                             parse_time(r.get("logged_at")), parse_time(r.get("commence_time")),
                             float(last), REF_BOOK, 100 * (1 / last - 1 / first)))
    return [a for a in alerts if a["at"] is not None and a["cote"]]


def build_alerts(root=ROOT) -> dict:
    root = pathlib.Path(root)
    pin = PinnacleIndex(root / "clv_history.jsonl")
    results = Results(root)
    surfaces = meta.SurfaceMap(root / "historique/tennis_data.csv.gz")
    alerts = collect_alerts(root)
    by_player = collections.defaultdict(list)
    by_match = collections.Counter()
    for a in alerts:
        by_player[(a["uid"], name_key(a["joueur"]))].append(a)
        by_match[a["uid"]] += 1
    rows, stats = [], collections.Counter()
    surface_source = collections.Counter()
    for a in alerts:
        group = by_player[(a["uid"], name_key(a["joueur"]))]
        later_public = [b for b in group if b["type"] == "PUBLIC" and b["at"] > a["at"]]
        earlier_h = [b for b in group if b["type"].startswith("H") and b["at"] < a["at"]]
        item, side = pin.find(a["joueur"], a["start"], a.get("adversaire"))
        feats = pinnacle_features(item, side, a["at"]) if item else pinnacle_features(
            {"curves": {}}, "home", a["at"])
        won, result_source = results.won(item, side, a["joueur"], a["start"], a.get("adversaire"))
        stats["résultat " + result_source] += 1
        clv = None
        if feats["pin_close"] and feats["pin_close_adv"]:
            clv = books.clv_pin_pct(a["book"], a["cote"], feats["pin_close"], feats["pin_close_adv"])
        flags = books.flags(a["book"])
        jouable = flags["jouable"] and a["book"] not in (REF_BOOK, "aucun retard jouable")
        surface, source = surfaces.lookup(a["tournoi"])
        surface_source[source] += 1
        lead = (a["start"] - a["at"]).total_seconds() / 60 if a["start"] else None
        pnl = books.pnl(a["book"], a["cote"], won) if won is not None else None
        n_match = by_match[a["uid"]]
        row = {
            "type": a["type"], "mois": a["at"].strftime("%Y-%m"), "circuit": meta.circuit_of(a["tournoi"]),
            "tournoi": a["tournoi"], "surface": surface, "tranche_cote": meta.odds_band(a["cote"]),
            "cote_pinnacle": feats["cote_pinnacle"], "tranche_delai": meta.band(lead, meta.LEAD_BANDS),
            "tranche_ampleur": meta.band(abs(a["ampleur"]) if a["ampleur"] is not None else None, meta.MOVE_BANDS),
            "book": a["book"], "jouable": "oui" if jouable else "non",
            "jouable_fr": "oui" if flags["jouable_fr"] else "non",
            "bourse": "oui" if flags["exchange"] else "non",
            "precede_par_H": ("oui" if earlier_h else "non") if not a["type"].startswith("H") else "sans objet",
            "nb_alertes_match": "1" if n_match == 1 else "2" if n_match == 2 else "3+",
            "pin_move_avant": feats["pin_move_avant"], "pin_points": feats["pin_points"],
            "pin_age": feats["pin_age"],
            "suivie_public": ("oui" if later_public else "non") if a["type"].startswith("H") else "sans objet",
            "date": a["at"].date().isoformat(), "joueur": a["joueur"], "uid": a["uid"],
            "cote": round(a["cote"], 3), "gagne": None if won is None else int(won),
            "pnl": None if pnl is None else round(pnl, 4),
            "clv_pin": None if clv is None else round(clv, 3),
            "pin_close": feats["pin_close"], "pin_close_adv": feats["pin_close_adv"],
            "minutes_vers_public": round((later_public[0]["at"] - a["at"]).total_seconds() / 60, 1) if later_public else None,
            "minutes_depuis_H": round((a["at"] - earlier_h[-1]["at"]).total_seconds() / 60, 1) if earlier_h else None,
            "pin_move_entree_cloture": feats["pin_move_entree_cloture"],
            "_at": a["at"].isoformat(timespec="seconds"),
        }
        rows.append(row)
    rows.sort(key=lambda r: (r["_at"], r["type"], r["uid"] or ""))
    names = [name for name, _, _ in FIELDS] + ["_at"]
    n = len(rows)
    with_surface = sum(1 for r in rows if r["surface"] != "inconnue")
    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "fields": [{"name": name, "label": label, "role": role} for name, label, role in FIELDS]
                  + [{"name": "_at", "label": "Heure de l'alerte (UTC)", "role": "descriptif"}],
        "columns": names,
        "rows": [[r[c] for c in names] for r in rows],
        "summary": {
            "rows": n,
            "by_type": dict(collections.Counter(r["type"] for r in rows)),
            "with_result": sum(1 for r in rows if r["gagne"] is not None),
            "with_clv_pin": sum(1 for r in rows if r["clv_pin"] is not None),
            "surface_coverage_pct": round(100 * with_surface / n, 1) if n else 0,
            "surface_sources": dict(surface_source),
            "result_sources": dict(stats),
            "period": {"start": rows[0]["date"] if rows else None, "end": rows[-1]["date"] if rows else None},
        },
        "notes": {
            "mouvement_book": "odds_alerts_log.jsonl ne nomme pas de book : prix = dernière cote de référence du journal, book « médiane/ref », non jouable.",
            "public_entree": "Meilleur book en retard jouable de retards_tous (flux de données exclus) ; sinon cote de référence après mouvement, non jouable.",
            "post_entree": "pin_move_entree_cloture utilise la clôture : colonne descriptive, jamais un filtre.",
            "suivie_public": "Connue après l'alerte H (avant le match) : filtre descriptif, interdit dans un gel.",
            "periode": "Alertes surtout de juin à octobre 2026 : échantillons courts.",
        },
    }


def build_histo(root=ROOT) -> dict:
    root = pathlib.Path(root)
    cube = collections.defaultdict(lambda: [0, 0, 0.0, 0.0])
    with gzip.open(root / "historique/tennis_data.csv.gz", "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                w, l = float(row["psw"]), float(row["psl"])
            except (TypeError, ValueError, KeyError):
                continue
            if w <= 1 or l <= 1 or w == l or len(str(row.get("date", ""))) < 4:
                continue
            year = row["date"][:4]
            circuit = str(row.get("circuit") or "?").upper()
            surface = str(row.get("surface") or "inconnue").capitalize()
            level = meta.level_of(row.get("tournoi"))
            for odds, won in ((w, True), (l, False)):
                side = "favori" if odds < (l if won else w) else "outsider"
                pnl = odds - 1 if won else -1.0
                cell = cube[(year, circuit, surface, level, side, meta.odds_band(odds))]
                cell[0] += 1
                cell[1] += int(won)
                cell[2] += pnl
                cell[3] += pnl * pnl
    keys = ["annee", "circuit", "surface", "niveau", "cote_pinnacle", "tranche_cote"]
    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "keys": keys, "labels": {"annee": "Année", "circuit": "Circuit", "surface": "Surface",
                                 "niveau": "Niveau", "cote_pinnacle": "Favori/outsider",
                                 "tranche_cote": "Cote (clôture Pinnacle)"},
        "values": ["n", "gagnes", "somme_pnl", "somme_pnl2"],
        "cells": [list(k) + [v[0], v[1], round(v[2], 4), round(v[3], 4)] for k, v in sorted(cube.items())],
        "notes": "Clôture Pinnacle brute (marge incluse). Niveau déduit du nom du tournoi.",
    }


def write_gz(path: pathlib.Path, doc: dict) -> bool:
    """Écrit un gz déterministe ; ne réécrit pas si seul generated_at changerait."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            old = json.loads(gzip.decompress(path.read_bytes()))
            if {k: v for k, v in old.items() if k != "generated_at"} == \
                    {k: v for k, v in doc.items() if k != "generated_at"}:
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
    alerts = build_alerts(root)
    histo = build_histo(root)
    changed_a = write_gz(root / OUT_ALERTS, alerts)
    changed_h = write_gz(root / OUT_HISTO, histo)
    s = alerts["summary"]
    print(f"Explorateur : {s['rows']} alertes {s['by_type']} · résultat {s['with_result']} · "
          f"CLV Pinnacle {s['with_clv_pin']} · surface {s['surface_coverage_pct']} % "
          f"({'modifié' if changed_a else 'inchangé'}) ; cube historique {len(histo['cells'])} cellules "
          f"({'modifié' if changed_h else 'inchangé'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
