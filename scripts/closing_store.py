#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""closing_store.py — closing_lines.json allégé + archives mensuelles (16/10/2026).

POURQUOI
closing_lines.json (9,5 Mo, ~1 960 matchs) est réécrit EN ENTIER à chaque
capture, ~275 fois par jour : ~2,6 Go de nouvelles versions par jour dans
git, la première source de croissance du dépôt. Pire : chaque passage
incrémente `absent_count` de TOUS les matchs absents, y compris ceux joués
il y a deux mois — chaque version diffère donc partout.

LE PRINCIPE
  closing_lines.json                     fichier CHAUD (même format qu'avant)
      matchs encore utiles aux écrivains : commencés il y a moins de
      HOT_DAYS jours (2), à venir, ou dont la CLV n'est pas encore réglée.
  closing_lines/closing_lines_YYYY-MM.jsonl     archives FROIDES
      une ligne {"uid": …, "entry": {…}} par match, écrite UNE fois quand il
      quitte la fenêtre chaude ; mois = mois de commence_time ; ajout seul.

LES ÉCRIVAINS (capture_closing, fetch_clv, purge_data) chargent load_hot()
et enregistrent par save_hot(), qui fait la bascule chaud -> archive.
TOUS LES LECTEURS passent par load_all() : même dict qu'avant (archives +
chaud, le chaud gagne), avec la même rétention de 60 jours qu'appliquaient
capture_closing (PURGE_DAYS) et purge_data (CLOSING_DAYS). Les archives,
elles, ne perdent plus rien : load_all(max_age_days=None) rend tout.

MIGRATION (idempotente) : python scripts/closing_store.py migrate | verify
RETOUR ARRIÈRE          : python scripts/closing_store.py restore
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys

HOT = "closing_lines.json"
DIRNAME = "closing_lines"
MARKER = "MIGRATION.json"
# 16/10/2026 (étape 4) : 3 -> 2 jours. Mesuré sur le fichier chaud réel :
# 0,99 Mo à 3 jours, 0,47 Mo à 2 jours, soit la moitié des ~270 Mo de
# versions brutes par jour. Sans risque pour les écrivains : capture_closing
# ne modifie que les matchs encore annoncés ou tout juste disparus (clôture
# par disparition en ~15 min), et les matchs dont la CLV n'est pas réglée
# restent chauds quel que soit leur âge (is_hot). Seul cas limite : un match
# reporté de PLUS de 2 jours qui réapparaît repart d'une entrée neuve
# (l'ancienne reste dans l'archive) — accepté, rarissime en tennis.
HOT_DAYS = float(os.environ.get("CLOSING_HOT_DAYS", "2"))
# Bascule GROUPÉE : on n'archive que lorsqu'au moins un match froid a dépassé
# HOT_DAYS + ROLL_BATCH_DAYS ; tous les froids partent alors ensemble. Sans
# cela, presque chaque capture (toutes les 5-10 min) ajouterait une ligne à
# l'archive du mois, qui deviendrait à son tour un fichier réécrit 275 fois
# par jour. Avec un lot d'un jour : ~1 écriture d'archive par jour.
ROLL_BATCH_DAYS = float(os.environ.get("CLOSING_ROLL_BATCH_DAYS", "1"))
RETENTION_DAYS = int(os.environ.get("CLOSING_DAYS", os.environ.get("PURGE_DAYS", "60")))
MAX_CLV_ATTEMPTS = 3            # fetch_clv.MAX_ATTEMPTS
_NAME = re.compile(r"^closing_lines_(\d{4}-\d{2})\.jsonl$")


def _utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _start(entry):
    """commence_time (naïf UTC) ou None."""
    ct = (entry or {}).get("commence_time") or ""
    try:
        return dt.datetime.fromisoformat(str(ct).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _root(path):
    return os.path.dirname(os.path.abspath(path or HOT))


def archive_dir(path=HOT):
    return os.path.join(_root(path), DIRNAME)


def archives(path=HOT):
    out = []
    for p in glob.glob(os.path.join(archive_dir(path), "closing_lines_*.jsonl")):
        if _NAME.match(os.path.basename(p)):
            out.append(p)
    return sorted(out)


def is_settled(entry) -> bool:
    """CLV réglée : fetch_clv ne rouvrira plus jamais ce match (même règle que
    son « self-heal » : done sans courbe ET tentatives < 3 -> rouvert)."""
    if not entry.get("clv_hist_done"):
        return False
    return bool(entry.get("clv_home")) or entry.get("clv_attempts", 0) >= MAX_CLV_ATTEMPTS


def is_hot(entry, now=None, hot_days=None) -> bool:
    """Faut-il garder ce match dans le fichier chaud ?"""
    now = now or _utcnow()
    hot_days = HOT_DAYS if hot_days is None else hot_days
    start = _start(entry)
    if start is None:
        return True                                    # non daté : on ne décide rien
    if start >= now - dt.timedelta(days=hot_days):
        return True                                    # à venir ou récent
    if start < now - dt.timedelta(days=RETENTION_DAYS):
        return False                                   # au-delà de la rétention : archive
    return not is_settled(entry)                       # CLV encore à faire


def in_retention(entry, now=None, days=None) -> bool:
    """Mêmes règles que les deux anciennes purges (60 j) :
    capture_closing gardait date >= coupure (texte), purge_data gardait
    commence_time >= coupure ou non daté."""
    if days is None:
        return True
    now = now or _utcnow()
    cut = now - dt.timedelta(days=days)
    if (entry.get("date") or "") < cut.strftime("%Y-%m-%d"):
        return False
    start = _start(entry)
    return start is None or start >= cut


# ── lecture ──────────────────────────────────────────────────────────────────

def load_hot(path=HOT) -> dict:
    """Le fichier chaud tel quel ({} s'il est absent). Lève si illisible —
    comme avant (un accumulateur illisible ne doit pas être écrasé)."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iter_archive(path=HOT):
    """(uid, entrée) dans l'ordre d'écriture (mois puis lignes)."""
    for p in archives(path):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("uid") is not None:
                    yield rec["uid"], rec.get("entry") or {}


def load_all(path=HOT, max_age_days="default", now=None) -> dict:
    """Le dict de TOUJOURS : archives + chaud (le chaud gagne en cas de
    doublon), restreint par défaut à la rétention historique de 60 jours.
    max_age_days=None : tout l'historique archivé.

    Un chemin qui ne s'appelle pas closing_lines.json (fixture de test,
    variable CLOSING=…) est lu tel quel, sans archives."""
    if os.path.basename(str(path)) != HOT:
        return load_hot(path)
    days = RETENTION_DAYS if max_age_days == "default" else max_age_days
    hot = load_hot(path)
    if not archives(path):
        return hot
    out = {}
    for uid, entry in iter_archive(path):
        if in_retention(entry, now, days):
            out.pop(uid, None)                 # la ligne la plus récente gagne
            out[uid] = entry
        else:
            out.pop(uid, None)
    for uid, entry in hot.items():
        out.pop(uid, None)
        out[uid] = entry
    return _original_order(out, path)


def _original_order(d, path):
    """Rétablit l'ordre des clés d'avant la migration (mémorisé dans le
    marqueur) : certains lecteurs, comme curves_common.build_closing_index,
    laissent le dernier uid gagner quand deux formats d'uid désignent le même
    match. Les matchs apparus depuis suivent, dans leur ordre d'arrivée."""
    try:
        with open(os.path.join(archive_dir(path), MARKER), encoding="utf-8") as f:
            order = json.load(f).get("ordre_avant") or []
    except (OSError, ValueError):
        return d
    rank = {uid: i for i, uid in enumerate(order)}
    base = len(rank)
    keys = sorted(d, key=lambda u, pos={u: i for i, u in enumerate(d)}:
                  rank.get(u, base + pos[u]))
    return {k: d[k] for k in keys}


def load_all_or(path=HOT, default=None, **kw):
    """load_all(), ou `default` si rien n'existe ou si c'est illisible
    (remplace les anciens « _load_json(CLOSING_FILE, None) »)."""
    if not exists(path):
        return default
    try:
        return load_all(path, **kw)
    except (OSError, ValueError):
        return default


def exists(path=HOT) -> bool:
    if os.path.basename(str(path)) != HOT:
        return os.path.exists(path)
    return os.path.exists(path) or bool(archives(path))


# ── écriture ─────────────────────────────────────────────────────────────────

def _month_of(entry):
    start = _start(entry)
    if start is not None:
        return start.strftime("%Y-%m")
    d = (entry.get("date") or "")[:7]
    return d if re.match(r"^\d{4}-\d{2}$", d) else _utcnow().strftime("%Y-%m")


def append_archive(items, path=HOT) -> int:
    """Ajoute [(uid, entrée)] aux archives mensuelles (ajout seul).
    Une entrée STRICTEMENT identique à la dernière version archivée du même
    uid n'est pas réécrite : un match ressuscité dans le fichier chaud par une
    fusion de conflit (merge_json_state fait l'union des clés) ne double pas
    l'archive."""
    last = {}
    for uid, entry in iter_archive(path):
        last[uid] = _canon(entry)
    by_month = {}
    for uid, entry in items:
        if last.get(uid) == _canon(entry):
            continue
        by_month.setdefault(_month_of(entry), []).append((uid, entry))
    os.makedirs(archive_dir(path), exist_ok=True)
    n = 0
    for month, rows in sorted(by_month.items()):
        target = os.path.join(archive_dir(path), f"closing_lines_{month}.jsonl")
        with open(target, "a", encoding="utf-8") as f:
            for uid, entry in rows:
                f.write(json.dumps({"uid": uid, "entry": entry}, ensure_ascii=False) + "\n")
                n += 1
    return n


def split(closing, now=None, hot_days=None):
    hot, cold = {}, []
    for uid, entry in closing.items():
        if is_hot(entry, now, hot_days):
            hot[uid] = entry
        else:
            cold.append((uid, entry))
    return hot, cold


def _write_hot(path, hot):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hot, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def roll(closing, path=HOT, now=None, legacy_purge=None) -> dict:
    """Pour les écrivains, juste AVANT d'écrire le fichier chaud : renvoie le
    dict chaud à écrire et ajoute aux archives les matchs sortis de la
    fenêtre (archive écrite d'abord : un crash laisse un doublon, jamais un
    trou). Avant la migration (pas de dossier closing_lines/) : rien ne
    bascule, seule l'ancienne purge `legacy_purge` s'applique, à l'identique."""
    if not os.path.isdir(archive_dir(path)):
        return legacy_purge(closing) if legacy_purge else closing
    now = now or _utcnow()
    hot, cold = split(closing, now)
    seuil = now - dt.timedelta(days=HOT_DAYS + ROLL_BATCH_DAYS)
    if cold and not any((_start(e) or now) < seuil for _, e in cold):
        return closing                     # lot pas encore mûr : rien ne bouge
    if cold:
        append_archive(cold, path)
        print(f"  [closing_store] {len(cold)} match(s) archivé(s) -> {DIRNAME}/, "
              f"{len(hot)} restent dans {os.path.basename(path)}")
    return hot


def save_hot(closing, path=HOT, now=None) -> dict:
    """Écrit le fichier chaud. AVANT la migration (pas de dossier
    closing_lines/), écrit tout tel quel : comportement d'avant, rien ne
    bascule tant que le workflow de migration n'a pas tourné.
    Après : les matchs sortis de la fenêtre partent d'abord dans l'archive
    (écrite AVANT le fichier chaud : un crash entre les deux laisse un
    doublon, jamais un trou)."""
    if not os.path.isdir(archive_dir(path)):
        _write_hot(path, closing)
        return {"chaud": len(closing), "archives": 0}
    hot, cold = split(closing, now)
    if cold:
        append_archive(cold, path)
    _write_hot(path, hot)
    return {"chaud": len(hot), "archives": len(cold)}


# ── migration ────────────────────────────────────────────────────────────────

def _canon(d) -> str:
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def migrate(path=HOT, now=None, verbose=True) -> dict:
    """Première bascule. Idempotent : sans rien à archiver, ne fait rien."""
    say = print if verbose else (lambda *a, **k: None)
    if not os.path.exists(path):
        say("closing_store — closing_lines.json absent : rien à faire.")
        return {"ok": False, "status": "absent"}
    before = load_hot(path)
    before_all = load_all(path, max_age_days=None) if archives(path) else dict(before)
    marker = os.path.join(archive_dir(path), MARKER)
    first = not os.path.isdir(archive_dir(path))
    os.makedirs(archive_dir(path), exist_ok=True)
    hot, cold = split(before, now)
    if cold:
        append_archive(cold, path)
    _write_hot(path, hot)
    if first:
        with open(marker, "w", encoding="utf-8") as f:
            json.dump({"ordre_avant": list(before)}, f)
    after_all = load_all(path, max_age_days=None)
    ok = after_all == before_all and (not first or list(after_all) == list(before_all))
    info = {"migre_le": _utcnow().isoformat(timespec="seconds"), "chaud": len(hot),
            "archives_ajoutees": len(cold), "total": len(after_all),
            "empreinte_dict": _canon(after_all),
            "octets_chaud": os.path.getsize(path)}
    if first:
        info["avant"] = {"matchs": len(before), "empreinte_dict": _canon(before)}
        info["ordre_avant"] = list(before)
        with open(marker, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
    say(f"closing_store — {'première migration' if first else 'relance'} : "
        f"{len(cold)} match(s) archivé(s), {len(hot)} restent chauds "
        f"({info['octets_chaud']/1e6:.2f} Mo).")
    say(f"closing_store — {'✅' if ok else '❌'} dict complet "
        f"{'identique' if ok else 'DIFFÉRENT'} ({len(after_all)} matchs, "
        f"{info['empreinte_dict'][:12]}…).")
    if not ok:
        raise RuntimeError("le dict reconstitué diffère : NE PAS committer.")
    return {"ok": ok, "status": "migre" if cold else "rien_a_archiver", **info}


def verify(path=HOT, verbose=True) -> dict:
    """Contrôle de cohérence : aucun uid à la fois perdu, archive lisible,
    le marqueur de migration retrouve tous les matchs d'avant."""
    say = print if verbose else (lambda *a, **k: None)
    marker = os.path.join(archive_dir(path), MARKER)
    full = load_all(path, max_age_days=None)
    res = {"total": len(full), "chaud": len(load_hot(path)), "archives": len(archives(path))}
    res["ok"] = bool(full) or not os.path.exists(path)
    if os.path.exists(marker):
        m = json.load(open(marker, encoding="utf-8"))
        res["matchs_avant_migration"] = m.get("avant", {}).get("matchs")
    say(f"closing_store verify — {res['total']} matchs (chaud {res['chaud']}, "
        f"{res['archives']} fichier(s) d'archive) : {'✅' if res['ok'] else '❌'}")
    return res


def restore(path=HOT, verbose=True) -> dict:
    """RETOUR ARRIÈRE : réécrit closing_lines.json avec le dict complet de la
    rétention (exactement ce que l'ancien code attendait), puis supprime le
    dossier closing_lines/ du disque. Le contenu des archives reste dans
    l'historique git. À committer, puis revert du code si voulu."""
    say = print if verbose else (lambda *a, **k: None)
    full = load_all(path)
    _write_hot(path, full)
    if os.path.isdir(archive_dir(path)):
        for p in glob.glob(os.path.join(archive_dir(path), "*")):
            os.remove(p)
        os.rmdir(archive_dir(path))
    say(f"closing_store — retour arrière : {len(full)} matchs réécrits dans "
        f"{os.path.basename(path)}, dossier {DIRNAME}/ retiré.")
    return {"ok": True, "total": len(full)}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "verify"
    path = argv[1] if len(argv) > 1 else HOT
    if cmd == "migrate":
        return 0 if migrate(path)["ok"] else 1
    if cmd == "verify":
        return 0 if verify(path)["ok"] else 1
    if cmd == "restore":
        return 0 if restore(path)["ok"] else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
