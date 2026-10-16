#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r2_parts.py — partitions à forte rotation (ticks pm/kx, courbes live) dans R2.

    python scripts/r2_parts.py pull   --kinds pm        # avant l'écrivain (mode on)
    python scripts/r2_parts.py push   --kinds pm        # après l'écrivain (double|on)
    python scripts/r2_parts.py gate                     # juste avant git commit
    python scripts/r2_parts.py verify --kinds all       # R2 vs copies git (lecture seule)
    python scripts/r2_parts.py status

Mode : variable de dépôt R2_PRIMARY = off | double | on (voir r2_io.py).

ÉCRITURE GROUPÉE
`push` écrit UNE fois par partition modifiée et par run, puis UNE fois le
manifeste de la famille : ~2 opérations classe A par collecteur et par run,
au lieu d'une par tick (ce que faisait le shadow V6.4, corrigé aussi).

FILET GIT (jamais de perte)
`gate` ne retire du commit QUE les partitions dont R2 détient exactement le
même contenu (SHA-256 du manifeste). Si l'envoi R2 a échoué, la partition
part dans git comme avant : la croissance revient pour ce run, pas la perte.

CONCURRENCE
Écritures conditionnelles (If-Match / If-None-Match). Si R2 a bougé depuis
le début du run, les membres gzip ajoutés par ce run sont greffés sur la
version distante (r2_io.merge_gz) au lieu de l'écraser.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_io  # noqa: E402

STATE_FILE = os.environ.get(
    "R2_STATE_FILE",
    os.path.join(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir(),
                 "r2_parts_state.json"))


def _annotate(level, msg):
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{level}::{msg}")
    else:
        print(f"{level.upper()}: {msg}")


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1, sort_keys=True)
    except OSError as exc:
        r2_io.log(f"état local non écrit ({exc})")


def local_files(fam, parts_dir=r2_io.PARTS_DIR):
    spec = r2_io.FAMILIES[fam]
    pattern = os.path.join(parts_dir, os.path.basename(spec["glob"]))
    return sorted(p for p in glob.glob(pattern) if spec["regex"].match(os.path.basename(p)))


def _record_bases(fams, parts_dir, state):
    """Mémorise la version de départ de chaque partition locale (après pull) :
    push s'en sert pour savoir ce que CE run a ajouté."""
    for fam in fams:
        for path in local_files(fam, parts_dir):
            name = os.path.basename(path)
            state.setdefault("base", {})[name] = {
                "sha256": r2_io.file_sha256(path), "size": os.path.getsize(path)}


# ── pull ─────────────────────────────────────────────────────────────────────

def cmd_pull(fams, parts_dir=r2_io.PARTS_DIR, days=None, environ=None):
    m = r2_io.mode(environ)
    state = load_state()
    if m == "off":
        print("pull — mode off : rien à rapatrier.")
        _record_bases(fams, parts_dir, state)
        save_state(state)
        return 0
    if m == "double":
        # git fait foi. Seule exception : une partition d'aujourd'hui ou
        # d'hier ABSENTE du checkout (retour de « on » à « double ») est
        # reprise de R2 pour que le collecteur la prolonge au lieu de
        # repartir de zéro. Rien n'est jamais remplacé.
        r2 = r2_io.client(environ)
        if r2 is not None:
            rep = r2_io.sync_from_r2(fams, parts_dir=parts_dir, days=1,
                                     only_missing=True, r2=r2)
            got = sorted(n for n, v in rep.items() if v == "telecharge")
            print(f"pull — mode double : {len(got)} partition(s) absente(s) de git "
                  f"reprise(s) de R2 {got if got else ''}")
            print(r2_io.ops_summary())
        _record_bases(fams, parts_dir, state)
        save_state(state)
        return 0
    r2 = r2_io.client(environ)
    if r2 is None:
        _annotate("warning", "R2_PRIMARY=on mais R2 indisponible : partitions "
                             "du checkout git utilisées telles quelles.")
        _record_bases(fams, parts_dir, state)
        save_state(state)
        return 0
    report = r2_io.sync_from_r2(fams, parts_dir=parts_dir, days=days, r2=r2)
    counts = {}
    for v in report.values():
        counts[v] = counts.get(v, 0) + 1
    print(f"pull — {', '.join(fams)} : {counts or 'rien dans la fenêtre'}")
    for name, v in sorted(report.items()):
        if v == "erreur":
            _annotate("warning", f"{name} non rapatrié depuis R2")
    _record_bases(fams, parts_dir, state)
    save_state(state)
    print(r2_io.ops_summary())
    return 0


# ── push ─────────────────────────────────────────────────────────────────────

def _push_one(r2, fam, path, ent, base, m):
    """Écrit une partition. Renvoie (entrée de manifeste, octets écrits),
    ou (None, None) si R2 a déjà exactement ce contenu."""
    name = os.path.basename(path)
    key = r2_io.FAMILIES[fam]["prefix"] + name
    with open(path, "rb") as f:
        data = f.read()
    sha = r2_io._sha256_hex(data)
    if ent and ent.get("sha256") == sha:
        return None, None
    lines = r2_io.gz_lines(data)          # illisible -> exception, rien n'est envoyé

    # Écriture directe seulement si R2 n'a pas encore cette partition
    # (création exclusive) ou si le local PROLONGE exactement la version R2
    # du début de run. Sinon (R2 a bougé, ou checkout sans cette partition,
    # p. ex. après un retour de « on » à « double ») : on relit R2 et on
    # greffe nos membres — jamais d'écrasement d'une version plus complète.
    direct = ent is None or bool(
        base and base.get("sha256") == ent.get("sha256")
        and len(data) >= base["size"]
        and r2_io._sha256_hex(data[:base["size"]]) == base["sha256"])
    target, n, cond = data, lines, (ent or {}).get("etag")
    for _attempt in range(4):
        if not direct:
            got = r2.get_with_etag(key)
            if got is None:
                target, n, cond = data, lines, None
            else:
                target = r2_io.merge_gz(got[0], data, base_size=(base or {}).get("size"))
                n = lines if target is data else r2_io.gz_lines(target)
                cond = got[1]
                if target == got[0]:          # R2 contient déjà tout
                    return r2_io.entry_for(fam, name, target, got[1], n), target
        try:
            etag = r2.put(key, target, create_only=cond is None, if_match=cond,
                          content_type="application/gzip", metadata={"lines": str(n)})
            return r2_io.entry_for(fam, name, target, etag, n), target
        except r2_io.PreconditionFailed:
            # Quelqu'un a écrit entre-temps : relire et greffer nos membres.
            direct = False
    raise RuntimeError(f"{name} : conflits d'écriture répétés")


def cmd_push(fams, parts_dir=r2_io.PARTS_DIR, environ=None):
    m = r2_io.mode(environ)
    if m == "off":
        print("push — mode off : rien n'est envoyé à R2.")
        return 0
    r2 = r2_io.client(environ)
    if r2 is None:
        _annotate("warning", f"push — mode {m} : R2 indisponible, les partitions "
                             "restent dans git (filet).")
        return 0
    state = load_state()
    bases = state.get("base", {})
    failures = 0
    for fam in fams:
        files = local_files(fam, parts_dir)
        if not files:
            print(f"push — {fam} : aucune partition locale.")
            continue
        man, etag = r2_io.load_manifest(r2, fam, use_cache=False)
        updates = {}
        for path in files:
            name = os.path.basename(path)
            try:
                entry, target = _push_one(r2, fam, path, man["files"].get(name),
                                          bases.get(name), m)
                if entry is not None and m == "on" and target is not None:
                    # Fusion avec une version distante plus récente : le local
                    # devient identique à R2 (gate pourra le retirer du commit).
                    with open(path, "rb") as f:
                        if f.read() != target:
                            r2_io._write_atomic(path, target)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                _annotate("warning", f"{name} : envoi R2 impossible "
                                     f"({type(exc).__name__}: {exc}) — reste dans git.")
                continue
            if entry is None:
                continue
            updates[name] = entry
            print(f"  ↑ {name:40} {entry['lines']:>9} lignes  {entry['size']/1e6:7.2f} Mo")
        if updates:
            try:
                r2_io.save_manifest(r2, fam, updates, etag=etag)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                _annotate("warning", f"manifeste {fam} non écrit ({exc}) — "
                                     "les partitions restent dans git.")
                continue
        print(f"push — {fam} : {len(updates)} partition(s) envoyée(s), "
              f"{len(files) - len(updates)} inchangée(s).")
    print(r2_io.ops_summary())
    return 0 if not failures else (1 if os.environ.get("R2_PUSH_STRICT") == "1" else 0)


# ── gate ─────────────────────────────────────────────────────────────────────

def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def staged_partitions():
    """[(statut, chemin)] des partitions R2 indexées pour le prochain commit."""
    out = _git("diff", "--cached", "--name-status", "--no-renames")
    res = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0][:1], parts[-1]
        if (os.path.dirname(path) == r2_io.PARTS_DIR
                and r2_io.family_of(path) in r2_io.STREAM_FAMILIES):
            res.append((status, path))
    return res


def cmd_gate(environ=None):
    m = r2_io.mode(environ)
    staged = [(s, p) for s, p in staged_partitions() if s != "D"]
    if m != "on":
        print(f"gate — mode {m} : partitions committées dans git comme avant "
              f"({len(staged)} indexée(s)).")
        return 0
    if not staged:
        print("gate — mode on : aucune partition R2 dans l'index.")
        return 0
    r2 = r2_io.client(environ)
    if r2 is None:
        _annotate("warning", "gate — R2 indisponible : partitions LAISSÉES dans le "
                             "commit (filet git, aucune perte).")
        return 0
    mans = {}
    removed, kept = 0, 0
    for status, path in staged:
        fam = r2_io.family_of(path)
        if fam not in mans:
            mans[fam] = r2_io.load_manifest(r2, fam, use_cache=False)[0]
        ent = mans[fam]["files"].get(os.path.basename(path))
        if ent and os.path.exists(path) and r2_io.file_sha256(path) == ent.get("sha256"):
            # R2 a exactement ce contenu : on ne l'ajoute pas à git.
            if status == "A":
                _git("restore", "--staged", "--", path)
            else:
                _git("restore", "--staged", "--worktree", "--", path)
            removed += 1
        else:
            kept += 1
            _annotate("warning", f"gate — {path} absent ou différent dans R2 : "
                                 "gardé dans le commit (filet git).")
    print(f"gate — mode on : {removed} partition(s) retirée(s) du commit "
          f"(déjà dans R2), {kept} gardée(s).")
    print(r2_io.ops_summary())
    return 0


# ── verify ───────────────────────────────────────────────────────────────────

def cmd_verify(fams, parts_dir=r2_io.PARTS_DIR, report_path=None, environ=None,
               today=None):
    """Compare les copies git (checkout) au manifeste et aux objets R2.

    Jours clos (avant aujourd'hui UTC) : SHA-256 et lignes doivent être
    identiques, sinon échec. Jour courant : comparé, jamais bloquant (les
    collecteurs écrivent pendant la vérification)."""
    r2 = r2_io.client(environ)
    if r2 is None:
        print("verify — R2 indisponible (secrets absents) : rien à comparer.")
        return 2
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    mode_now = r2_io.mode(environ)
    rows, bad = [], 0
    for fam in fams:
        man, _ = r2_io.load_manifest(r2, fam, use_cache=False)
        listed = dict(r2.list(r2_io.FAMILIES[fam]["prefix"]))
        for path in local_files(fam, parts_dir):
            name = os.path.basename(path)
            day = r2_io.day_of(name)
            closed = day < today
            ent = man["files"].get(name)
            with open(path, "rb") as f:
                local = f.read()
            row = {"famille": fam, "fichier": name, "jour": day, "clos": closed,
                   "git_octets": len(local), "git_lignes": r2_io.gz_lines(local)}
            if not ent:
                row["statut"] = "absent_r2"
            else:
                row.update(r2_octets=ent["size"], r2_lignes=ent["lines"])
                if listed.get(ent["key"]) != ent["size"]:
                    row["statut"] = "objet_manquant_ou_taille"
                elif ent["sha256"] == r2_io._sha256_hex(local):
                    row["statut"] = "identique"
                else:
                    remote = r2.get(ent["key"]) or b""
                    if remote.startswith(local):
                        row["statut"] = "r2_plus_complet"
                    elif local.startswith(remote):
                        row["statut"] = "git_plus_complet"
                    else:
                        row["statut"] = "different"
            # En « on », la copie git est figée (sauvegarde) : R2 plus complet
            # est l'état normal. En « double », seul le jour en cours peut
            # différer (les collecteurs écrivent pendant la vérification).
            ok = row["statut"] == "identique" or (
                not closed and row["statut"] in {"git_plus_complet", "r2_plus_complet"}) or (
                mode_now == "on" and row["statut"] == "r2_plus_complet")
            row["ok"] = ok
            if closed and not ok:
                bad += 1
            rows.append(row)
    total = len(rows)
    same = sum(1 for r in rows if r["statut"] == "identique")
    summary = {"verifie_le": r2_io.now_iso(), "mode": r2_io.mode(environ),
               "partitions": total, "identiques": same,
               "anomalies_jours_clos": bad, "lignes": rows}
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1)
    lines = [f"## Vérification R2 ↔ git — {summary['verifie_le']}", "",
             f"Mode : **{summary['mode']}** · partitions : {total} · identiques : {same} · "
             f"anomalies (jours clos) : **{bad}**", "",
             "| fichier | jour | git lignes | R2 lignes | statut |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['fichier']} | {r['jour']}{'' if r['clos'] else ' (en cours)'} | "
                     f"{r['git_lignes']} | {r.get('r2_lignes', '—')} | "
                     f"{'✅' if r['ok'] else '❌'} {r['statut']} |")
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    print(r2_io.ops_summary())
    if bad:
        print(f"❌ {bad} partition(s) de jours clos ne correspondent pas : NE PAS passer en 'on'.")
        return 1
    print("✅ Toutes les partitions de jours clos sont identiques dans R2.")
    return 0


def cmd_status(environ=None):
    m = r2_io.mode(environ)
    print(f"R2_PRIMARY = {m}")
    r2 = r2_io.client(environ)
    if r2 is None:
        return 0
    for fam in r2_io.FAMILIES:
        man, etag = r2_io.load_manifest(r2, fam, use_cache=False)
        files = man.get("files", {})
        size = sum(e.get("size", 0) for e in files.values())
        print(f"  {fam:5} : {len(files):4} partition(s), {size/1e6:8.1f} Mo, "
              f"maj {man.get('updated_at')}")
    print(r2_io.ops_summary())
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("command", choices=["pull", "push", "gate", "verify", "status"])
    ap.add_argument("--kinds", default="all", help="pm, kx, live, ticks, all")
    ap.add_argument("--days", type=int, default=None,
                    help="pull : fenêtre en jours (défaut : 7 ticks, 4 live)")
    ap.add_argument("--parts-dir", default=r2_io.PARTS_DIR)
    ap.add_argument("--report", default=None, help="verify : rapport JSON")
    args = ap.parse_args(argv)
    fams = r2_io.families(args.kinds)
    if args.command == "pull":
        return cmd_pull(fams, args.parts_dir, args.days)
    if args.command == "push":
        return cmd_push(fams, args.parts_dir)
    if args.command == "gate":
        return cmd_gate()
    if args.command == "verify":
        return cmd_verify(fams, args.parts_dir, args.report)
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
