#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""croissance_depot.py — d'où vient la croissance du dépôt ? (16/10/2026)

Compte, sur les dernières 24 h de main, combien de NOUVELLES VERSIONS de
chaque fichier ont été committées, et multiplie par sa taille actuelle :
« versions × taille » = volume brut ajouté à l'historique (avant la
compression delta de git, donc un majorant, mais le bon classement).

BON MARCHÉ (< 1 min) : l'historique est récupéré SANS les contenus
(`git fetch --filter=blob:none --shallow-since`), les versions sont comptées
par `git log --name-only` (commits et arbres seulement), et les tailles sont
lues dans l'arbre de HEAD (`git ls-tree -l`), dont les fichiers sont déjà
là après un checkout normal. Un fichier supprimé depuis n'a pas de taille
connue : il est compté en versions, taille « ? ».

    python scripts/croissance_depot.py [--heures 24] [--top 8] [--json croissance_depot.json]
Sortie : croissance_depot.json, lu par health_check.py pour la ligne
« croissance 24 h : X Mo bruts, top : … » du message Telegram.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import subprocess
import sys


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}… : {r.stderr.strip()[:200]}")
    return r.stdout


def versions_since(hours, ref="HEAD", cwd=None):
    """{chemin: nombre de commits (non-merge) qui l'ont modifié/créé}."""
    since = f"{hours} hours ago"
    out = git("log", ref, f"--since={since}", "--no-merges", "--format=%x00",
              "--name-only", "--diff-filter=AM", "--no-renames", cwd=cwd)
    counts = collections.Counter()
    for line in out.split("\n"):
        line = line.strip().strip("\x00")
        if line:
            counts[line] += 1
    commits = out.count("\x00")
    return counts, commits


def sizes_at(paths, ref="HEAD", cwd=None):
    """{chemin: taille en octets à `ref`} (absent si supprimé depuis)."""
    sizes = {}
    paths = list(paths)
    for i in range(0, len(paths), 400):
        chunk = paths[i:i + 400]
        out = git("ls-tree", "-l", ref, "--", *chunk, cwd=cwd, check=False)
        for line in out.split("\n"):
            if "\t" not in line:
                continue
            meta, path = line.split("\t", 1)
            parts = meta.split()
            if len(parts) >= 4 and parts[1] == "blob" and parts[3].isdigit():
                sizes[path] = int(parts[3])
    return sizes


def family(path):
    """Regroupe les partitions datées (parts/pm_ticks_<jour>…) en une ligne."""
    import re
    return re.sub(r"\d{4}-\d{2}(-\d{2})?(_\d+)?|W\d{2}(_\d+)?", "*", path)


def measure(hours=24, top=8, ref="HEAD", cwd=None):
    counts, commits = versions_since(hours, ref, cwd)
    sizes = sizes_at(counts, ref, cwd)
    fams = collections.defaultdict(lambda: {"versions": 0, "octets": 0, "taille_inconnue": 0})
    for path, n in counts.items():
        f = fams[family(path)]
        f["versions"] += n
        if path in sizes:
            f["octets"] += n * sizes[path]
        else:
            f["taille_inconnue"] += n
    rows = sorted(({"fichier": k, **v} for k, v in fams.items()),
                  key=lambda r: (-r["octets"], -r["versions"]))
    total = sum(r["octets"] for r in rows)
    return {"genere_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "fenetre_heures": hours, "commits": commits,
            "versions": sum(counts.values()), "octets_bruts": total,
            "top": rows[:top]}


def _mo(octets):
    return f"{octets / 1e6:,.0f}".replace(",", "\u202f")


def ligne_telegram(rep):
    """« croissance 24 h : 3 210 Mo bruts (912 commits), top : closing_lines.json 2 610 Mo (275×), … »"""
    if not rep:
        return None
    tops = ", ".join(f"{r['fichier']} {_mo(r['octets'])} Mo ({r['versions']}×)"
                     for r in rep["top"][:3])
    return (f"croissance {rep['fenetre_heures']} h : {_mo(rep['octets_bruts'])} Mo bruts "
            f"({rep['commits']} commits), top : {tops}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--heures", type=int, default=24)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--json", default="croissance_depot.json")
    ap.add_argument("--ref", default="HEAD")
    a = ap.parse_args(argv)
    try:
        rep = measure(a.heures, a.top, a.ref)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ croissance_depot : mesure impossible ({exc})")
        return 0
    print(f"Croissance des {a.heures} dernières heures : {rep['commits']} commits, "
          f"{rep['versions']} versions, {rep['octets_bruts']/1e6:.0f} Mo bruts")
    for r in rep["top"]:
        inc = f" (+{r['taille_inconnue']} sans taille)" if r["taille_inconnue"] else ""
        print(f"  {r['octets']/1e6:9.1f} Mo  {r['versions']:5}×  {r['fichier']}{inc}")
    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
