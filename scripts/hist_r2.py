#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hist_r2.py — l'historique figé des courbes (parts/hist_*) sort de git vers R2.

    python scripts/hist_r2.py inventaire     # lecture seule : état git / R2
    python scripts/hist_r2.py migrer         # figées -> R2 vérifié -> git rm
    python scripts/hist_r2.py verifier [--complet]
    python scripts/hist_r2.py annuler        # R2 -> git (retour arrière)
    python scripts/hist_r2.py pull           # rapatrie dans parts/ ce qui manque

POURQUOI (16/10/2026)
parts/hist_* pèse ~500 Mo dans le working tree : chaque checkout qui
l'inclut le télécharge, et le dépôt ne peut pas repartir propre tant que
cet historique vit dans git. Ces partitions sont FIGÉES dès que leur
semaine (ou leur mois) est close : fetch_book_curves n'écrit que dans la
partition courante (ov.current_hist_partition_path).

RÈGLES
  • Figée = période strictement antérieure à la période courante, avec 6 h
    de marge après le changement de semaine (un run de fetch_book_curves
    lancé dimanche 23:45 peut encore écrire dans la semaine précédente).
  • Une partition ne quitte git que si R2 en détient une copie OCTET POUR
    OCTET identique, vérifiée par RE-TÉLÉCHARGEMENT (SHA-256).
  • Clé R2 : parts/hist/<fichier>, manifeste parts/hist/_manifest.json
    (conventions de r2_io, avec empreintes). La copie horaire de
    courbes_r2.py (parts/<fichier>, sans empreinte) reste une 2e copie.
  • Doublon .jsonl + .jsonl.gz d'une même période : si le .gz décompressé
    est identique au .jsonl, seul le .gz part dans R2 (canonique) ; sinon
    les DEUX partent dans R2 et c'est signalé, y compris le cas « inclus »
    (le .jsonl est le DÉBUT du .gz : W37 set1/set2 au 16/10, 827 lignes lues
    deux fois par load_partitions aujourd'hui). La lecture reste identique à
    aujourd'hui ; corriger ce double comptage est une décision à part.
  • Les fichiers retirés sont listés dans un bloc de .gitignore : un
    `git add -A` ne peut plus les remettre dans git quand un lecteur les a
    rapatriés depuis R2.
  • Rien n'est jamais supprimé dans R2.

LECTEURS : oddspapi_v5 (iter_hist_lines, hist_partitions, load_partitions,
open_curves), restore_curves et les études à glob direct appellent
r2_io.materialize_hist() quand R2_HIST_MATERIALIZE=1 (posé par les
workflows qui lisent l'historique).
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_io  # noqa: E402

PARTS = "parts"
GITIGNORE = ".gitignore"
BEGIN = "# >>> hist_r2 : partitions historiques FIGÉES, servies par R2 (scripts/hist_r2.py) — ne pas éditer à la main"
END = "# <<< hist_r2"
GRACE_HOURS = float(os.environ.get("HIST_GRACE_HOURS", "6"))
_NAME = re.compile(r"^hist_(book|set1|set2)_(\d{4})-(W\d{2}|\d{2})(?:_(\d+))?\.jsonl(\.gz)?$")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lines(name, data):
    if name.endswith(".gz"):
        return r2_io.gz_lines(data)
    return sum(1 for line in data.split(b"\n") if line.strip())


def _git(*args, check=False):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])} : {r.stderr.strip()[:200]}")
    return r


def tracked_hist():
    out = _git("ls-files", "--", f"{PARTS}/hist_*").stdout.split()
    return sorted(os.path.basename(p) for p in out if _NAME.match(os.path.basename(p)))


def is_frozen(name, now=None) -> bool:
    m = _NAME.match(name)
    if not m:
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    year, period = m.group(2), m.group(3)
    if period.startswith("W"):
        cur_y, cur_w, _ = now.isocalendar()
        current = f"{cur_y}-W{cur_w:02d}"
        this = f"{year}-{period}"
        if this >= current:
            return False
        week_start = (now - dt.timedelta(days=now.isoweekday() - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        prev = (week_start - dt.timedelta(days=1)).isocalendar()
        prev_label = f"{prev[0]}-W{prev[1]:02d}"
        if this == prev_label and now < week_start + dt.timedelta(hours=GRACE_HOURS):
            return False
        return True
    return f"{year}-{period}" < now.strftime("%Y-%m")


# ── bloc .gitignore ──────────────────────────────────────────────────────────

def read_block(path=GITIGNORE):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return []
    if BEGIN not in text:
        return []
    body = text.split(BEGIN, 1)[1].split(END, 1)[0]
    return [l.strip().lstrip("/").split("/")[-1] for l in body.splitlines() if l.strip()]


def write_block(names, path=GITIGNORE):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        text = ""
    if BEGIN in text:
        head, rest = text.split(BEGIN, 1)
        tail = rest.split(END, 1)[1] if END in rest else ""
        text = head.rstrip("\n") + "\n" + tail.lstrip("\n")
    names = sorted(set(names))
    if names:
        block = "\n".join([BEGIN] + [f"/{PARTS}/{n}" for n in names] + [END])
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ── inventaire ───────────────────────────────────────────────────────────────

def _legacy_manifest(r2):
    raw = r2.get("parts/_manifest.json")
    try:
        return json.loads(raw).get("fichiers", {}) if raw else {}
    except ValueError:
        return {}


def duplicates(names):
    """{base .jsonl: base .jsonl.gz} quand les deux existent."""
    s = set(names)
    return {n: n + ".gz" for n in names if n.endswith(".jsonl") and n + ".gz" in s}


def compare_dup(plain_path, gz_path) -> str:
    """'identique' | 'inclus' (le .jsonl est un début du .gz) | 'different'."""
    try:
        full = gzip.decompress(open(gz_path, "rb").read())
        plain = open(plain_path, "rb").read()
    except (OSError, EOFError, gzip.BadGzipFile):
        return "different"
    if full == plain:
        return "identique"
    return "inclus" if full.startswith(plain) else "different"


def same_content(plain_path, gz_path) -> bool:
    return compare_dup(plain_path, gz_path) == "identique"


def inventaire(now=None, report_path="hist_r2_inventaire.json", environ=None):
    r2 = r2_io.client(environ)
    man = r2_io.load_manifest(r2, "hist", use_cache=False)[0] if r2 else {"files": {}}
    legacy = _legacy_manifest(r2) if r2 else {}
    listed = dict(r2.list("parts/hist/")) if r2 else {}
    names = tracked_hist()
    dups = duplicates(names)
    rows = []
    for n in names:
        path = os.path.join(PARTS, n)
        data = open(path, "rb").read() if os.path.exists(path) else b""
        ent = man["files"].get(n)
        row = {"fichier": n, "octets": len(data), "fige": is_frozen(n, now),
               "sha256": _sha(data) if data else None,
               "r2": ("identique" if ent and ent.get("sha256") == _sha(data)
                      and listed.get(ent["key"]) == len(data)
                      else "different" if ent else "absent"),
               "copie_courbes_r2": ("taille_ok" if legacy.get(n, {}).get("octets") == len(data)
                                    else "absente" if n not in legacy else "taille_differente")}
        if n in dups:
            row["doublon_de"] = dups[n]
            row["doublon"] = compare_dup(path, os.path.join(PARTS, dups[n]))
            row["doublon_identique"] = row["doublon"] == "identique"
        rows.append(row)
    migrated = read_block()
    summary = {"genere_le": r2_io.now_iso(), "dans_git": len(names),
               "octets_dans_git": sum(r["octets"] for r in rows),
               "figees": sum(1 for r in rows if r["fige"]),
               "octets_figees": sum(r["octets"] for r in rows if r["fige"]),
               "deja_dans_r2_identiques": sum(1 for r in rows if r["r2"] == "identique"),
               "deja_migrees": len(migrated), "r2_disponible": r2 is not None,
               "fichiers": rows}
    if report_path:
        json.dump(summary, open(report_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Historique dans git : {summary['dans_git']} fichiers, "
          f"{summary['octets_dans_git']/1e6:.0f} Mo ; figés : {summary['figees']} "
          f"({summary['octets_figees']/1e6:.0f} Mo) ; déjà migrés : {len(migrated)}")
    print(f"{'fichier':40} {'Mo':>7} {'figé':>5} {'R2':>11}  courbes_r2   doublon")
    for r in rows:
        dup = ""
        if "doublon_de" in r:
            dup = {"identique": "identique au .gz (seul le .gz part)",
                   "inclus": "DÉBUT du .gz : lignes lues 2 fois aujourd'hui (les deux gardés)",
                   "different": "≠ .gz (les deux gardés)"}[r["doublon"]]
        print(f"{r['fichier']:40} {r['octets']/1e6:7.2f} {'oui' if r['fige'] else 'NON':>5} "
              f"{r['r2']:>11}  {r['copie_courbes_r2']:11}  {dup}")
    if not r2:
        print("⚠️ R2 indisponible : colonnes R2 non renseignées.")
    print(r2_io.ops_summary())
    return summary


# ── migration ────────────────────────────────────────────────────────────────

def _ensure_in_r2(r2, name, data, ent):
    """Copie (si besoin) puis VÉRIFIE par re-téléchargement. Renvoie l'entrée
    de manifeste, ou None si R2 détient une AUTRE version (conflit)."""
    key = r2_io.FAMILIES["hist"]["prefix"] + name
    sha = _sha(data)
    etag = None
    if not (ent and ent.get("sha256") == sha):
        try:
            etag = r2.put(key, data, create_only=True,
                          content_type="application/gzip" if name.endswith(".gz")
                          else "application/x-ndjson",
                          metadata={"lines": str(_lines(name, data))})
        except r2_io.PreconditionFailed:
            pass                                  # déjà là : on compare ci-dessous
    got = r2.get_with_etag(key)
    if got is None or _sha(got[0]) != sha:
        return None
    return r2_io.entry_for("hist", name, data, etag or got[1], _lines(name, data))


def migrer(now=None, environ=None, dry=False):
    r2 = r2_io.client(environ)
    if r2 is None:
        print("❌ R2 indisponible : rien n'est retiré de git.")
        return 1
    man, etag = r2_io.load_manifest(r2, "hist", use_cache=False)
    names = tracked_hist()
    dups = duplicates(names)
    frozen = [n for n in names if is_frozen(n, now)]
    updates, removed, conflicts, notes = {}, [], [], []
    for n in frozen:
        path = os.path.join(PARTS, n)
        data = open(path, "rb").read()
        if n in dups and dups[n] in frozen and same_content(path, os.path.join(PARTS, dups[n])):
            notes.append(f"{n} : identique à {dups[n]} — seul le .gz est copié (canonique)")
            removed.append(n)          # retiré de git, le .gz couvre son contenu
            continue
        if n in dups:
            kind = compare_dup(path, os.path.join(PARTS, dups[n]))
            notes.append(f"{n} : {'inclus au début de' if kind == 'inclus' else 'DIFFÉRENT de'} "
                         f"{dups[n]} — les deux sont copiés (lecture inchangée)")
        try:
            _lines(n, data)
        except Exception as exc:  # noqa: BLE001
            conflicts.append(f"{n} : illisible ({type(exc).__name__}) — gardé dans git")
            continue
        if dry:
            print(f"  [simulation] {n} ({len(data)/1e6:.1f} Mo)")
            continue
        entry = _ensure_in_r2(r2, n, data, man["files"].get(n))
        if entry is None:
            conflicts.append(f"{n} : R2 détient une autre version — gardé dans git")
            continue
        updates[n] = entry
        removed.append(n)
        print(f"  ✅ {n:40} {len(data)/1e6:7.2f} Mo  vérifié dans R2 ({entry['lines']} lignes)")
    # Un .jsonl « doublon identique » ne sort que si son .gz est bien arrivé.
    removed = [n for n in removed if n in updates or dups.get(n) in updates]
    if dry:
        print(f"Simulation : {len(frozen)} figée(s) sur {len(names)}.")
        return 0
    if updates:
        r2_io.save_manifest(r2, "hist", updates, etag=etag)
    for n in removed:
        _git("rm", "-q", "--cached", "--", os.path.join(PARTS, n), check=True)
    write_block(read_block() + removed)
    for x in notes:
        print(f"  ℹ️ {x}")
    for x in conflicts:
        print(f"  ❌ {x}")
    print(f"Bilan : {len(removed)} partition(s) retirée(s) de git "
          f"({sum(os.path.getsize(os.path.join(PARTS, n)) for n in removed)/1e6:.0f} Mo), "
          f"{len(conflicts)} gardée(s). {r2_io.ops_summary()}")
    return 1 if conflicts else 0


def verifier(complet=False, environ=None):
    r2 = r2_io.client(environ)
    if r2 is None:
        print("❌ R2 indisponible.")
        return 2
    man = r2_io.load_manifest(r2, "hist", use_cache=False)[0]
    listed = dict(r2.list("parts/hist/"))
    migrated = read_block()
    still = set(tracked_hist()) & set(migrated)
    bad = []
    for n in migrated:
        ent = man["files"].get(n)
        if ent is None:
            gz = man["files"].get(n + ".gz")
            if n.endswith(".jsonl") and gz:
                continue                          # doublon identique couvert par son .gz
            bad.append(f"{n} : absent du manifeste R2")
            continue
        if listed.get(ent["key"]) != ent["size"]:
            bad.append(f"{n} : objet R2 absent ou de taille différente")
            continue
        if complet:
            data = r2.get(ent["key"]) or b""
            if _sha(data) != ent["sha256"]:
                bad.append(f"{n} : empreinte R2 différente du manifeste")
    for n in sorted(still):
        bad.append(f"{n} : encore suivi par git alors qu'il est listé comme migré")
    print(f"Vérification historique R2 : {len(migrated)} partition(s) migrée(s), "
          f"{len(man['files'])} dans le manifeste, {len(bad)} anomalie(s)"
          f"{' (re-téléchargement complet)' if complet else ''}.")
    for x in bad:
        print(f"  ❌ {x}")
    print(r2_io.ops_summary())
    return 1 if bad else 0


def annuler(environ=None):
    """Remet dans git toutes les partitions migrées (téléchargées et
    vérifiées depuis R2), puis retire le bloc .gitignore."""
    r2 = r2_io.client(environ)
    migrated = read_block()
    if not migrated:
        print("Rien à annuler.")
        return 0
    if r2 is None:
        print("❌ R2 indisponible : impossible de restaurer.")
        return 1
    man = r2_io.load_manifest(r2, "hist", use_cache=False)[0]
    restored, failed = [], []
    os.makedirs(PARTS, exist_ok=True)
    for n in migrated:
        src = n if n in man["files"] else (n + ".gz" if n + ".gz" in man["files"] else None)
        if src is None:
            failed.append(n)
            continue
        ent = man["files"][src]
        data = r2.get(ent["key"])
        if data is None or _sha(data) != ent["sha256"]:
            failed.append(n)
            continue
        if src != n:                              # doublon identique : on le régénère
            data = gzip.decompress(data)
        r2_io._write_atomic(os.path.join(PARTS, n), data)
        restored.append(n)
    if failed:
        print(f"❌ {len(failed)} partition(s) non restaurée(s) : {failed[:5]} — rien n'est modifié.")
        return 1
    write_block([])
    for n in restored:
        _git("add", "-f", "--", os.path.join(PARTS, n), check=True)
    print(f"✅ {len(restored)} partition(s) remise(s) dans git. {r2_io.ops_summary()}")
    return 0


def _cache_in(cache_dir, environ=None):
    """Copie dans parts/ les partitions figées présentes dans le cache
    (actions/cache) et identiques au manifeste (taille + SHA-256)."""
    r2 = r2_io.client(environ)
    if r2 is None or not cache_dir or not os.path.isdir(cache_dir):
        return 0
    man = r2_io.load_manifest(r2, "hist")[0]
    n = 0
    for name, ent in man["files"].items():
        dst, src = os.path.join(PARTS, name), os.path.join(cache_dir, name)
        if os.path.exists(dst) or not os.path.exists(src):
            continue
        if os.path.getsize(src) == ent.get("size") and r2_io.file_sha256(src) == ent.get("sha256"):
            os.makedirs(PARTS, exist_ok=True)
            with open(src, "rb") as f:
                r2_io._write_atomic(dst, f.read())
            n += 1
    return n


def _cache_out(cache_dir, names):
    if not cache_dir:
        return
    os.makedirs(cache_dir, exist_ok=True)
    for name in names:
        src = os.path.join(PARTS, name)
        if os.path.exists(src):
            with open(src, "rb") as f:
                r2_io._write_atomic(os.path.join(cache_dir, name), f.read())


def pull(environ=None, cache_dir=None):
    """Rapatrie l'historique figé. Avec --cache DIR (hors du dépôt, conservé
    par actions/cache) : on réutilise d'abord les copies vérifiées du cache,
    on ne télécharge que le reste, puis on complète le cache. Le cache ne
    remplace JAMAIS un fichier présent (la partition courante, suivie par
    git, n'est donc jamais touchée)."""
    from_cache = _cache_in(cache_dir, environ)
    rep = r2_io.materialize_hist(force=True, environ=environ)
    _cache_out(cache_dir, [n for n, v in rep.items() if v == "telecharge"])
    if from_cache:
        print(f"Historique : {from_cache} partition(s) reprise(s) du cache.")
    got = sum(1 for v in rep.values() if v == "telecharge")
    print(f"Historique R2 : {got} partition(s) rapatriée(s), "
          f"{sum(1 for v in rep.values() if v == 'present')} déjà présente(s). "
          f"{r2_io.ops_summary()}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("command", choices=["inventaire", "migrer", "verifier", "annuler", "pull"])
    ap.add_argument("--complet", action="store_true", help="verifier : re-télécharge tout")
    ap.add_argument("--simulation", action="store_true", help="migrer : ne fait rien")
    ap.add_argument("--cache", default=None, help="pull : dossier de cache hors dépôt")
    a = ap.parse_args(argv)
    if a.command == "inventaire":
        inventaire()
        return 0
    if a.command == "migrer":
        return migrer(dry=a.simulation)
    if a.command == "verifier":
        return verifier(complet=a.complet)
    if a.command == "annuler":
        return annuler()
    return pull(cache_dir=a.cache)


if __name__ == "__main__":
    sys.exit(main())
