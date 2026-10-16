#!/usr/bin/env python3
"""V7.1 — Réconciliation : verdicts EN DIRECT ↔ reconstruction (contrôle) ↔ Worker.

DÉCISION DU 16/10/2026 (Lucas) : les verdicts se rendent sur les alertes EN
DIRECT. La population « Détections (suivi officiel) » est donc le journal
h*_signal_log.jsonl (données figées à la détection), complété par
scripts/suivi_direct.py (résultat, clôture Pinnacle, CLV, P&L — fichier
suivi_direct/resultats.json) et résumé dans verdicts_direct.json. Le Lab
RECOPIE ces chiffres (aucun recalcul) et ne lit que ces fichiers committés.

* **Suivi officiel (direct)** : verdicts_direct.json, ligne à ligne via
  suivi_direct.detections() (mêmes règles de comptage : première détection
  par (H, uid, côté), strictement après le gel, doublons comptés pour chaque H).
* **Reconstruction (contrôle)** : moves_detail_hist.csv filtré par les règles
  gelées de validation_report.py (autoresearch.official_definitions), égalité
  vérifiée avec les fonctions *_watch. Ne juge plus.
* **Worker** : capture /api/hypotheses recopiée (avant le 16/10 : ancien
  Worker D1 ; ensuite : verdicts_direct.json servi tel quel).

Rapprochement direct ↔ reconstruction : uid + joueur normalisé, à défaut paire
de joueurs + date ±1 jour. Chaque écart reçoit UNE raison ; « inexpliqué »
signale une incohérence (drapeau rouge dans l'onglet). Lecture seule.
"""
from __future__ import annotations

import collections
import contextlib
import os
import csv
import datetime as dt
import gzip
import importlib.util
import io
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = pathlib.Path(__file__).resolve().parent
OUTPUT = "Tennis_Edge_Lab/live/reconciliation_hypotheses.json"
OUTPUT_DETECTIONS = "Tennis_Edge_Lab/live/explorateur_detections.json.gz"
WORKER_SNAPSHOT = "Tennis_Edge_Lab/worker_hypotheses.json"
OFFICIAL = ("H13", "H14", "H15", "H16", "H16B", "H17", "H18")
# Hypothèse -> journal en direct (H14 : canal créé le 16/10/2026).
LOGS = {"H13": "h13", "H14": "h14", "H15": "h15", "H16": "h16", "H16B": "h16b", "H17": "h17", "H18": "h18"}
# Fonctions du validateur officiel (égalité vérifiée à chaque calcul).
WATCH = {"H13": "roi_bande_watch", "H14": "roi_ampli_watch", "H15": "bande_240_310_watch",
         "H16": "bande_favori_watch", "H16B": "favori_sans_ultra_watch",
         "H17": "ecart_entree_watch", "H18": "favorite_steam_value_watch"}
# Inclusions de règles : une alerte envoyée par la clé implique la règle de la valeur.
# (H16-B ⊂ H16 ; H18 = H16 ∩ H17.) Une détection H16 non envoyée alors que H16-B
# l'a envoyée en direct est donc INEXPLIQUÉE.
IMPLIES = {"H16B": ("H16",), "H18": ("H16", "H17")}
MIN_LEAD = 5.0  # minutes, scripts/h1x_signal.py

REASONS = {
    # détectée par la reconstruction mais absente du journal en direct
    "sans_canal": ("Hypothèse sans canal en direct à cette date", True),
    "avant_canal": ("Avant la mise en service du canal", True),
    "cote_opposee_live": ("Autre joueur du match détecté en direct", True),
    "hors_delai": ("Hors fenêtre de délai (< 5 min)", True),
    "apres_coup": ("Vue seulement après coup (absente du journal en direct)", True),
    "inexplique_inclusion": ("Inexpliqué : règle incluse détectée en direct", False),
    # détectée en direct mais absente de la reconstruction
    "pas_encore_reconstruit": ("Pas encore dans la reconstruction", True),
    "absent_reconstruction": ("Absent de la reconstruction (aucun mouvement retenu)", True),
    "cote_opposee_reco": ("Reconstruction sur l'autre joueur", True),
    "hors_gel": ("Hors période de gel de la reconstruction", True),
    "prix_different": ("Prix/seuil différent (direct vs reconstruction)", True),
    "donnees_incompletes": ("Données incomplètes dans la reconstruction", True),
    "inexplique": ("Inexpliqué", False),
}


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_r_" + name[:-3], path)
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


def nk(value):
    return meta.norm_text(value).replace(" ", "")


def fnum(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def read_jsonl(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def day(value):
    return str(value or "")[:10]


def shift(d, days):
    try:
        return (dt.date.fromisoformat(d) + dt.timedelta(days=days)).isoformat()
    except ValueError:
        return d


# ------------------------------------------------------------------ sources
def load_autoresearch(root):
    ar = _load("autoresearch.py")
    ar.ROOT = pathlib.Path(root)
    ar._external_features = None
    ar._pin_close = None
    return ar


def validator_watch(root):
    """Appelle les fonctions *_watch de validation_report.py (sorties muettes)."""
    root = pathlib.Path(root)
    scripts = root / "scripts"
    spec = importlib.util.spec_from_file_location("tennis_edge_vr", scripts / "validation_report.py")
    module = importlib.util.module_from_spec(spec)
    old_cwd, old_path = pathlib.Path.cwd(), list(sys.path)
    sink = io.StringIO()
    try:
        os.chdir(root)
        sys.path.insert(0, str(scripts))
        with contextlib.redirect_stdout(sink):
            spec.loader.exec_module(module)
            out = {}
            for code, fn in WATCH.items():
                res = getattr(module, fn)()
                out[code] = None if not res else {"k": int(res[0]), "n": int(res[1]), "p0": float(res[2])}
        return out
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path


def worker_block(root, snapshot_path=None):
    """Agrégats du Worker D1 recopiés SANS recalcul depuis la capture /api/hypotheses."""
    path = pathlib.Path(snapshot_path) if snapshot_path else pathlib.Path(root) / WORKER_SNAPSHOT
    base = {"source": "API Worker D1 /api/hypotheses (fetch_worker_snapshot.py)", "fichier": str(path.name),
            "status": "absent", "hypotheses": {}}
    if not path.is_file():
        return base
    try:
        snap = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        base["status"] = "illisible"
        return base
    base.update({"status": snap.get("status", "inconnu"), "fetched_at": snap.get("fetched_at"),
                 "worker_generated_at": snap.get("worker_generated_at")})
    for h in snap.get("hypotheses") or []:
        if not isinstance(h, dict) or not isinstance(h.get("out_of_sample"), dict):
            continue
        code = str(h.get("code", "")).upper().replace("-", "")
        oos = h["out_of_sample"]
        base["hypotheses"][code] = {
            "gele_le": h.get("gele_le"),
            # Copie intégrale : chaque champ numérique tel que l'API le publie.
            "out_of_sample": {k: v for k, v in oos.items() if isinstance(v, (int, float, str)) or v is None},
            "n": oos.get("n"), "roi": oos.get("roi"),
        }
    return base


def load_direct(root):
    """verdicts_direct.json + suivi_direct/resultats.json + journaux (fichiers committés)."""
    root = pathlib.Path(root)
    try:
        verdicts = json.loads((root / "verdicts_direct.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        verdicts = {"hypotheses": []}
    try:
        table = json.loads((root / "suivi_direct/resultats.json").read_text(encoding="utf-8")).get("paris", {})
    except (OSError, ValueError):
        table = {}
    return verdicts, table


class _Gels:
    """Dates de gel lues dans validation_report (via autoresearch), pour suivi_direct.detections()."""

    def __init__(self, freezes):
        for code, attr in (("H13", "FREEZE_DATE_ROIBANDE"), ("H14", "FREEZE_DATE_AMPLI"), ("H15", "FREEZE_DATE_H15"),
                           ("H16", "FREEZE_DATE_H16"), ("H16B", "FREEZE_DATE_H16B"), ("H17", "FREEZE_DATE_H17"),
                           ("H18", "FREEZE_DATE_H18")):
            setattr(self, attr, freezes[code])


# ------------------------------------------------------------------ mesures
def metrics(items):
    """items : [{odd, book, pnl, win, clv_pin}] dénoués. pts = taux − seuil (moyenne de 1/cote nette)."""
    items = [x for x in items if x.get("pnl") is not None and x.get("win") is not None]
    n = len(items)
    if not n:
        return {"n": 0, "gagnes": 0, "roi": None, "pts": None, "clv_pin": None, "clv_n": 0}
    k = sum(int(x["win"]) for x in items)
    p0 = sum(1 / books.effective_odds(x.get("book"), x["odd"]) for x in items) / n
    clv = [x["clv_pin"] for x in items if x.get("clv_pin") is not None]
    return {"n": n, "gagnes": k, "roi": round(100 * sum(x["pnl"] for x in items) / n, 2),
            "pts": round(100 * (k / n - p0), 2), "clv_pin": round(statistics.mean(clv), 2) if clv else None,
            "clv_n": len(clv)}


# ------------------------------------------------------------------ rapprochement
class Index:
    """Clé principale (uid, joueur) ; repli (paire de joueurs, joueur) à ±1 jour."""

    def __init__(self):
        self.main = {}
        self.alt = collections.defaultdict(list)
        self.by_uid = collections.defaultdict(list)

    def add(self, uid, player, opponent, date, value):
        self.main.setdefault((uid, nk(player)), value)
        if opponent:
            self.alt[(frozenset((nk(player), nk(opponent))), nk(player))].append((date, value))
        self.by_uid[uid].append(value)

    def find(self, uid, player, opponent, date):
        hit = self.main.get((uid, nk(player)))
        if hit is not None or not opponent:
            return hit
        for d, value in self.alt.get((frozenset((nk(player), nk(opponent))), nk(player)), []):
            if d and date and d in (date, shift(date, -1), shift(date, 1)):
                return value
        return None


def lenient(raw):
    return {"odd": fnum(raw.get("entry")), "pin": fnum(raw.get("pin_open")),
            "lead": fnum(raw.get("lead_min")), "mag": fnum(raw.get("mag_cote_pct"))}


def holds(pred, values):
    try:
        return bool(pred(values))
    except (TypeError, ZeroDivisionError):
        return False


def build(root=ROOT, worker_path=None, check_validator=True):
    root = pathlib.Path(root)
    ar = load_autoresearch(root)
    sd = _load_script(root, "suivi_direct.py")
    with (root / "moves_detail_hist.csv").open(encoding="utf-8-sig", newline="") as fh:
        raw = list(csv.DictReader(fh))
    csv_last = max((day(r.get("date")) for r in raw), default=None)
    raw_index = Index()
    for r in raw:
        raw_index.add(r.get("uid"), r.get("steame"), r.get("opp"), day(r.get("date")), r)
    definitions = {code: (freeze, rule, pred) for code, freeze, rule, pred in ar.official_definitions()}
    _, qualified = ar.frozen_results(raw)
    watch = validator_watch(root) if check_validator else {}
    worker = worker_block(root, worker_path)
    verdicts, table = load_direct(root)
    vby = {h.get("code"): h for h in verdicts.get("hypotheses", [])}
    live_all = sd.detections(root, _Gels({c: v[0] for c, v in definitions.items()}))
    raw_logs = {code: read_jsonl(root / f"{code.lower()}_signal_log.jsonl") for code in OFFICIAL}
    log_index = {}
    for code, rows in raw_logs.items():
        ix = Index()
        for r in rows:
            ix.add(r.get("uid"), r.get("joueur"), r.get("adversaire"), day(r.get("commence") or r.get("uid")), r)
        log_index[code] = ix

    report, detection_rows = {}, []
    for code in OFFICIAL:
        freeze, rule, pred = definitions[code]
        settled = {r["uid"]: r for r in qualified[code]}
        live = live_all[code]["lignes"]
        start = live_all[code]["premiere_detection"]

        def add(r):
            return table.get(f"{code}|{r['uid']}|{r.get('_side') or sd.norm(r.get('joueur'))}") or {}

        # Reconstruction (CONTRÔLE) : toutes les lignes post-gel satisfaisant la règle officielle.
        reco = []
        for r in raw:
            if day(r.get("date")) < freeze or not holds(pred, lenient(r)):
                continue
            status = ("réglée" if r.get("uid") in settled else
                      "non réglée" if r.get("steame_gagne") not in ("oui", "non") else "rejet contrôle qualité")
            reco.append((r, status))
        reco_index = Index()
        for r, status in reco:
            reco_index.add(r.get("uid"), r.get("steame"), r.get("opp"), day(r.get("date")), (r, status))
        live_index = Index()
        for r in live:
            live_index.add(r.get("uid"), r.get("joueur"), r.get("adversaire"), day(r.get("commence") or r.get("uid")), r)

        ecarts, communes, reco_seule = [], [], []
        reasons_rs, reasons_ds = collections.Counter(), collections.Counter()
        for r, status in reco:
            uid, player, opp, date = r.get("uid"), r.get("steame"), r.get("opp"), day(r.get("date"))
            hit = live_index.find(uid, player, opp, date)
            if hit is not None:
                communes.append((r, status, hit))
                continue
            detail = ""
            if not live and code == "H14":
                reason, detail = "sans_canal", "canal H14 en direct créé le 16/10/2026"
            elif not start or date < start:
                reason = "avant_canal"
                detail = f"première détection en direct le {start}" if start else "journal vide"
            elif any(nk(x.get("joueur")) != nk(player) for x in log_index[code].by_uid.get(uid, [])):
                other = log_index[code].by_uid[uid][0]
                reason = "cote_opposee_live"
                detail = f"le direct a détecté {other.get('joueur')} à {other.get('cote')} ({other.get('book')})"
            elif (fnum(r.get("lead_min")) or 0) < MIN_LEAD:
                reason, detail = "hors_delai", f"délai reconstitué {r.get('lead_min')} min"
            else:
                implied = [c for c, targets in IMPLIES.items() if code in targets
                           and log_index[c].find(uid, player, opp, date) is not None]
                if implied:
                    reason = "inexplique_inclusion"
                    detail = f"{', '.join(implied)} l'a détectée en direct ; la règle {code} est incluse"
                else:
                    reason = "apres_coup"
                    seen = [c for c, ix in log_index.items() if c != code and uid in ix.by_uid]
                    detail = ("match vu en direct par " + ", ".join(seen)) if seen else "match absent de tous les journaux en direct"
            reasons_rs[reason] += 1
            reco_seule.append((r, status, reason))
            ecarts.append({"sens": "reconstruction seule", "date": date, "match": f"{player} – {opp}",
                           "joueur": player, "uid": uid, "cote": fnum(r.get("entry")), "book": r.get("entry_book"),
                           "statut": status, "raison": reason, "libelle": REASONS[reason][0],
                           "detail": detail, "explique": REASONS[reason][1]})

        direct_seule = []
        common_keys = {id(hit) for _, _, hit in communes}
        for s_ in live:
            if id(s_) in common_keys:
                continue
            uid, player, opp = s_.get("uid"), s_.get("joueur"), s_.get("adversaire")
            date = day(s_.get("commence") or uid)
            row = raw_index.find(uid, player, opp, date)
            other = raw_index.by_uid.get(uid) or []
            detail = ""
            if row is None and other:
                reason = "cote_opposee_reco"
                detail = f"reconstruction sur {other[0].get('steame')} à {other[0].get('entry')} ({other[0].get('entry_book')})"
            elif row is None:
                if csv_last and date > csv_last:
                    reason, detail = "pas_encore_reconstruit", f"match du {date}, reconstruction arrêtée au {csv_last}"
                else:
                    reason, detail = "absent_reconstruction", "move_audit n'a retenu aucun mouvement sur ce match"
            elif day(row.get("date")) < freeze:
                reason, detail = "hors_gel", f"match du {day(row.get('date'))}, gel {code} le {freeze}"
            else:
                v = lenient(row)
                if None in (v["odd"], v["pin"], v["lead"], v["mag"]):
                    reason = "donnees_incompletes"
                elif not holds(pred, v):
                    reason = "prix_different"
                    detail = (f"direct {s_.get('cote')} ({s_.get('book')}) · reconstruction {row.get('entry')} "
                              f"({row.get('entry_book')}), Pinnacle ouv. {row.get('pin_open')}")
                else:
                    reason = "inexplique"
                    detail = "la reconstruction satisfait la règle mais la ligne n'a pas été rapprochée"
            reasons_ds[reason] += 1
            a = add(s_)
            direct_seule.append(s_)
            ecarts.append({"sens": "direct seule", "date": date, "match": f"{player} – {opp}",
                           "joueur": player, "uid": uid, "cote": fnum(s_.get("cote")), "book": s_.get("book"),
                           "statut": "dénouée" if a.get("gagne") is not None else "non dénouée",
                           "raison": reason, "libelle": REASONS[reason][0], "detail": detail,
                           "explique": REASONS[reason][1]})

        def reco_items(pairs):
            return [{"odd": settled[r["uid"]]["odd"], "book": settled[r["uid"]]["book"],
                     "pnl": settled[r["uid"]]["pnl"], "win": settled[r["uid"]]["win"],
                     "clv_pin": settled[r["uid"]].get("clv_pin")} for r, *_ in pairs if r.get("uid") in settled]

        def live_items(entries):
            out = []
            for r in entries:
                a = add(r)
                if a.get("gagne") is None:
                    continue
                out.append({"odd": float(r["cote"]), "book": books.normalize(r.get("book")), "pnl": a["pnl"],
                            "win": a["gagne"], "clv_pin": a.get("clv_pin")})
            return out

        sent = [r for r in live if r.get("envoye") is True and not r.get("doublon")]
        not_sent = [r for r in live if not (r.get("envoye") is True and not r.get("doublon"))]
        v = vby.get(code) or {}
        o = v.get("out_of_sample") or {}
        reco_metrics = metrics(reco_items([(r, s) for r, s in reco]))
        w = watch.get(code) if watch else None
        report[code] = {
            "regle": rule, "gel": freeze, "canal": LOGS.get(code) or code.lower(), "mise_en_service": start,
            "worker": worker["hypotheses"].get(code),
            # Suivi officiel = verdicts_direct.json RECOPIÉ (aucun recalcul).
            "suivi_officiel": {"n": o.get("n", 0), "gagnes": o.get("gains", 0), "roi": o.get("roi"),
                               "pts": o.get("ecart"), "clv_pin": o.get("clv_pin_moyen"),
                               "clv_pin_ic95": o.get("clv_pin_ic95"), "clv_n": o.get("clv_n", 0),
                               "n_detectees": o.get("n_detectees", 0), "n_envoyees": o.get("n_envoyees", 0),
                               "n_doublons": o.get("n_doublons", 0), "source": "verdicts_direct.json",
                               "sans_resultat_pct": o.get("sans_resultat_pct"), "statut": o.get("statut"),
                               "verrouillable": o.get("verrouillable"),
                               "genere_le": verdicts.get("genere_le")},
            "reconstruction": {**reco_metrics, "source": "moves_detail_hist.csv · validation_report.py (contrôle)",
                               "validation_report": w,
                               "egal_validation_report": None if not watch else bool(
                                   w and w["n"] == reco_metrics["n"] and w["k"] == reco_metrics["gagnes"])},
            "entonnoir": {
                "direct_detectees": len(live), "direct_envoyees": len(sent),
                "direct_doublons": sum(1 for r in live if r.get("doublon")),
                "direct_non_envoyees_autres": sum(1 for r in live if not r.get("doublon") and r.get("envoye") is not True),
                "direct_denouees": len(live_items(live)),
                "reconstruction_detectees": len(reco),
                "reconstruction_reglees": sum(1 for _, s in reco if s == "réglée"),
                "communes": len(communes),
                "reconstruction_seule": len(reco_seule), "reconstruction_seule_raisons": dict(reasons_rs),
                "direct_seule": len(direct_seule), "direct_seule_raisons": dict(reasons_ds),
                "inexpliques": sum(1 for e in ecarts if not e["explique"]),
            },
            "mesures": {
                "suivi_officiel": metrics(live_items(live)),
                "envoyees": metrics(live_items(sent)),
                "detectees_non_envoyees": metrics(live_items(not_sent)),
                "reconstruction": reco_metrics,
                "communes_direct": metrics(live_items([h for _, _, h in communes])),
                "communes_reconstruction": metrics(reco_items(communes)),
                "direct_seule": metrics(live_items(direct_seule)),
                "reconstruction_seule": metrics(reco_items(reco_seule)),
            },
            "ecarts": sorted(ecarts, key=lambda e: (e["explique"], e["date"])),
        }
        # Jeu « Détections (suivi officiel) » de l'Explorateur : le journal EN DIRECT.
        reco_keys = {id(h) for _, _, h in communes}
        for r in live:
            a = add(r)
            cote = float(r["cote"])
            po = fnum(r.get("pin_open"))
            pd = fnum(r.get("pin_decision"))
            flags = books.flags(r.get("book"))
            lead = fnum(r.get("lead_min"))
            amp = fnum(r.get("ampleur_pts"))
            when = str(r.get("detecte_le") or r.get("signale_le"))
            ref = pd or po
            detection_rows.append({
                "type": code, "mois": when[:7], "circuit": r.get("circuit") or meta.circuit_of(r.get("tournoi")),
                "tournoi": r.get("tournoi") or "?", "tranche_cote": meta.odds_band(cote),
                "cote_pinnacle": ("favori" if ref < 2 else "outsider") if ref else "inconnu",
                "tranche_delai": meta.band(lead, meta.LEAD_BANDS),
                "tranche_ampleur": meta.band(abs(amp) if amp is not None else None, meta.MOVE_BANDS),
                "book": books.normalize(r.get("book")), "jouable": "oui" if flags["jouable"] else "non",
                "jouable_fr": "oui" if flags["jouable_fr"] else "non", "bourse": "oui" if flags["exchange"] else "non",
                "envoyee": "oui" if (r.get("envoye") is True and not r.get("doublon")) else "non",
                "statut_envoi": r.get("statut_envoi") or ("doublon" if r.get("doublon") else
                                                         "envoyé" if r.get("envoye") else "non envoyé"),
                "dans_reconstruction": "oui" if id(r) in reco_keys else "non",
                "date": when[:10], "joueur": r.get("joueur"), "uid": r["uid"],
                "cote": round(cote, 3), "cote_pin_ouverture": po, "delai_min": None if lead is None else round(lead),
                "ampleur_pts": None if amp is None else round(abs(amp), 2),
                "gagne": a.get("gagne"), "pnl": a.get("pnl"), "clv_pin": a.get("clv_pin"),
                "_at": when,
            })

    doc = {
        "schema_version": 2,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sources": {
            "worker": {k: worker[k] for k in worker if k != "hypotheses"},
            "suivi_officiel": "alertes en direct : h*_signal_log.jsonl + suivi_direct/resultats.json "
                              f"(verdicts_direct.json du {verdicts.get('genere_le')})",
            "reconstruction": "moves_detail_hist.csv filtré par les règles gelées de validation_report.py "
                              f"(lignes jusqu'au {csv_last}) — contrôle, ne juge pas",
            "rapprochement": "uid + joueur normalisé ; à défaut paire de joueurs + date ±1 jour",
        },
        "raisons": {k: {"libelle": v[0], "explique": v[1]} for k, v in REASONS.items()},
        "notes": {
            "pts": "taux de gain − seuil de rentabilité (moyenne de 1/cote nette de commission), en points.",
            "worker_ecart": "Capture /api/hypotheses recopiée. Ancien Worker D1 : agrégats sur sa copie de la "
                            "reconstruction. Nouveau Worker (16/10/2026) : verdicts_direct.json tel quel.",
        },
        "hypotheses": report,
    }
    return doc, detection_rows


def _load_script(root, name):
    path = pathlib.Path(root) / "scripts" / name
    if not path.is_file():
        path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location("tennis_edge_r_" + name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DETECTION_FIELDS = [
    ("type", "Hypothèse", "filtre"), ("mois", "Mois", "filtre"), ("circuit", "Circuit", "filtre"),
    ("tournoi", "Tournoi", "filtre"), ("tranche_cote", "Cote d'entrée", "filtre"),
    ("cote_pinnacle", "Favori/outsider (Pinnacle à la détection)", "filtre"),
    ("tranche_delai", "Délai avant match", "filtre"), ("tranche_ampleur", "Ampleur du mouvement", "filtre"),
    ("book", "Book d'entrée", "filtre"), ("jouable", "Book jouable", "filtre"),
    ("jouable_fr", "Jouable en France", "filtre"), ("bourse", "Bourse (Betfair…)", "filtre"),
    ("envoyee", "Alerte envoyée", "filtre_apres_alerte"),
    ("statut_envoi", "Statut d'envoi", "filtre_apres_alerte"),
    ("dans_reconstruction", "Aussi dans la reconstruction", "filtre_apres_alerte"),
    ("date", "Date", "descriptif"), ("joueur", "Joueur", "descriptif"), ("uid", "Match", "descriptif"),
    ("cote", "Cote d'entrée", "filtre_num"), ("cote_pin_ouverture", "Cote Pinnacle à l'ouverture", "filtre_num"),
    ("delai_min", "Délai avant match (min)", "filtre_num"), ("ampleur_pts", "Ampleur du mouvement (pts)", "filtre_num"),
    ("gagne", "Gagné (1/0)", "mesure"), ("pnl", "P&L (1 unité)", "mesure"), ("clv_pin", "CLV Pinnacle %", "mesure"),
]


def detections_doc(rows):
    names = [n for n, _, _ in DETECTION_FIELDS] + ["_at"]
    rows = sorted(rows, key=lambda r: (r["_at"], r["type"], r["uid"]))
    return {"schema_version": 2, "population": "Détections (suivi officiel) — alertes en direct",
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "fields": [{"name": n, "label": l, "role": r} for n, l, r in DETECTION_FIELDS]
                      + [{"name": "_at", "label": "Détection (UTC)", "role": "descriptif"}],
            "columns": names, "rows": [[r[c] for c in names] for r in rows],
            "summary": {"rows": len(rows), "by_type": dict(collections.Counter(r["type"] for r in rows)),
                        "settled_by_type": dict(collections.Counter(r["type"] for r in rows if r["gagne"] is not None))}}


def write_gz(path, doc):
    data = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            old = json.loads(gzip.decompress(path.read_bytes()))
            old.pop("generated_at", None)
            new = dict(doc); new.pop("generated_at", None)
            if old == json.loads(json.dumps(new, ensure_ascii=False)):
                return False
        except (OSError, ValueError):
            pass
    path.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    return True


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("root", nargs="?", default=str(ROOT))
    p.add_argument("--worker", default=None, help="capture /api/hypotheses (défaut Tennis_Edge_Lab/worker_hypotheses.json)")
    a = p.parse_args(argv)
    root = pathlib.Path(a.root)
    doc, rows = build(root, a.worker)
    bad = [c for c, h in doc["hypotheses"].items() if h["reconstruction"]["egal_validation_report"] is False]
    if bad:
        print("ERREUR : contrôle reconstruction différent de validation_report.py pour " + ", ".join(bad))
        return 1
    out = root / OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_gz(root / OUTPUT_DETECTIONS, detections_doc(rows))
    for code, h in doc["hypotheses"].items():
        e, o = h["entonnoir"], h["suivi_officiel"]
        w = h["worker"] or {}
        print(f"{code}: direct {e['direct_detectees']} détectées · {e['direct_envoyees']} envoyées · "
              f"{o['n']} dénouées (ROI {o['roi']} %, CLV {o['clv_pin']} %) · reconstruction {e['reconstruction_detectees']}"
              f" ({h['reconstruction']['n']} réglées) · communes {e['communes']} · Worker n={w.get('n', '—')} · "
              f"inexpliqués {e['inexpliques']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
