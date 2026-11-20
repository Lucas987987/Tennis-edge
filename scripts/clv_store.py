#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clv_store.py — clv_history partitionné par MOIS (créé le 15/10/2026).

POURQUOI
clv_history.jsonl pesait 83 Mo et grossissait de ~5 versions complètes par
jour : à ce rythme il touchait le MUR GitHub de 100 Mo par fichier en
quelques semaines (push refusé = collecte bloquée). Même remède que les
courbes (parts/hist_*) : un fichier par mois, en ajout seul.

    clv_history/clv_history_2026-10.jsonl     (puis _2, _3 au-delà de 8 Mo)

ORDRE IDENTIQUE, À LA LIGNE PRÈS
Les lecteurs construisent des dicts « dernier gagnant » : l'ordre compte.
La partition d'une ligne est le mois du MAXIMUM COURANT des commence_time
(migration) ou le mois courant UTC (ajouts) : les deux ne décroissent
jamais, donc concaténer les partitions dans l'ordre redonne EXACTEMENT
l'ancien fichier, octet pour octet (vérifié par `migrate`).

LECTEURS
    import clv_store
    if clv_store.exists(CLV_FILE): ...
    with clv_store.open_text(CLV_FILE) as f:
        for line in f: ...
Un chemin nommé clv_history.jsonl est résolu vers les partitions dès
qu'elles existent (l'ancien fichier, gardé comme sauvegarde jusqu'à sa
suppression, n'est alors PLUS lu : jamais de double lecture). Tout autre
chemin (CLV_FILE=fixture.jsonl dans un test) est lu tel quel.

MIGRATION (idempotente)
    python scripts/clv_store.py migrate        # découpe + vérification
    python scripts/clv_store.py verify         # concat(partitions) ⊇ ancien fichier
    python scripts/clv_store.py remove-legacy  # commit suivant, après vérification
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import sys

LEGACY = "clv_history.jsonl"
DIRNAME = "clv_history"
MARKER = "MIGRATION.json"
# 16/10/2026 : 90 -> 8 Mo. La partition du mois courant est réécrite à
# chaque run de fetch_clv (~5 fois par jour) : à 17-35 Mo, cela faisait
# ~100 Mo de nouvelles versions par jour. À 8 Mo max, la partition en cours
# reste petite (rotation en _2, _3… dans le mois, ordre conservé).
MAX_MB = float(os.environ.get("CLV_PART_MAX_MB", "8"))
_NAME = re.compile(r"^clv_history_(\d{4}-\d{2})(?:_(\d+))?\.jsonl$")


def _root_of(path):
    """Racine (dossier) qui contient clv_history.jsonl / clv_history/."""
    return os.path.dirname(os.path.abspath(path)) if path else os.getcwd()


def part_dir(root="."):
    return os.path.join(root, DIRNAME)


def partitions(root="."):
    """Partitions mensuelles triées (mois, numéro de rotation)."""
    out = []
    for p in glob.glob(os.path.join(part_dir(root), "clv_history_*.jsonl")):
        m = _NAME.match(os.path.basename(p))
        if m:
            out.append(((m.group(1), int(m.group(2) or 1)), p))
    return [p for _, p in sorted(out)]


def resolve(path=LEGACY):
    """Liste des fichiers à lire pour `path`, dans l'ordre."""
    path = path or LEGACY
    if os.path.basename(path) == LEGACY:
        parts = partitions(_root_of(path))
        if parts:
            return parts
    return [path] if os.path.exists(path) else []


def exists(path=LEGACY) -> bool:
    return bool(resolve(path))


def iter_lines(path=LEGACY):
    """Lignes brutes (avec leur \\n), dans l'ordre historique."""
    for p in resolve(path):
        with open(p, encoding="utf-8") as f:
            for line in f:
                yield line


def iter_records(path=LEGACY):
    """Objets JSON (lignes vides ou illisibles ignorées)."""
    for line in iter_lines(path):
        if line.strip():
            try:
                yield json.loads(line)
            except ValueError:
                continue


class _Lines(io.TextIOBase):
    """Objet « fichier texte » en lecture seule sur plusieurs partitions :
    `for line in f`, f.read(), f.readlines(), with … as f."""

    def __init__(self, paths):
        super().__init__()
        self._paths = list(paths)
        self._gen = self._lines()

    def _lines(self):
        for p in self._paths:
            with open(p, encoding="utf-8") as f:
                yield from f

    def readable(self):
        return True

    def __iter__(self):
        return self._gen

    def __next__(self):
        return next(self._gen)

    def readline(self, size=-1):
        return next(self._gen, "")

    def read(self, size=-1):
        return "".join(self._gen)

    def readlines(self, hint=-1):
        return list(self._gen)


def open_text(path=LEGACY):
    """Remplace open(CLV_FILE, encoding='utf-8') chez les lecteurs.
    FileNotFoundError si rien n'existe (même contrat que open())."""
    paths = resolve(path)
    if not paths:
        raise FileNotFoundError(path)
    return _Lines(paths)


# ── écrivains ────────────────────────────────────────────────────────────────

def _month(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m")


def append_path(root=".", now=None, legacy_ok=True):
    """Fichier où AJOUTER une ligne maintenant.

    Avant migration (aucune partition, ancien fichier présent) : l'ancien
    fichier, pour qu'un déploiement partiel ne disperse jamais l'historique.
    Après : partition du mois courant UTC, avec rotation à MAX_MB."""
    legacy = os.path.join(root, LEGACY)
    parts = partitions(root)
    if not parts and legacy_ok and os.path.exists(legacy):
        return legacy
    month = _month(now)
    # Jamais revenir à un mois antérieur à la dernière partition (ordre).
    if parts:
        last = _NAME.match(os.path.basename(parts[-1])).group(1)
        month = max(month, last)
    os.makedirs(part_dir(root), exist_ok=True)
    seq = 1
    for p in parts:
        m = _NAME.match(os.path.basename(p))
        if m.group(1) == month:
            seq = max(seq, int(m.group(2) or 1))
    path = _part_name(root, month, seq)
    while os.path.exists(path) and os.path.getsize(path) / 1e6 >= MAX_MB:
        seq += 1
        path = _part_name(root, month, seq)
    return path


def _part_name(root, month, seq):
    suffix = "" if seq == 1 else f"_{seq}"
    return os.path.join(part_dir(root), f"clv_history_{month}{suffix}.jsonl")


def rewrite(transform, path=LEGACY):
    """Applique transform(list[str]) -> list[str] à CHAQUE fichier résolu et ne
    réécrit que ceux qui changent (un mois clos intact ne crée aucun blob git).
    Renvoie le nombre de fichiers réécrits."""
    changed = 0
    for p in resolve(path):
        with open(p, encoding="utf-8") as f:
            lines = [l for l in f.read().split("\n") if l.strip()]
        new = transform(lines)
        if new != lines:
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(new) + ("\n" if new else ""))
            os.replace(tmp, p)
            changed += 1
    return changed


# ── migration ────────────────────────────────────────────────────────────────

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _month_of_line(line: bytes, current: str | None) -> str | None:
    try:
        ct = json.loads(line).get("commence_time") or ""
    except (ValueError, AttributeError):
        return current
    m = re.match(r"^(\d{4}-\d{2})", str(ct))
    if not m:
        return current
    return max(current, m.group(1)) if current else m.group(1)


def split_bytes(data: bytes):
    """[(mois, octets)] dans l'ordre ; concaténation == data exactement."""
    chunks, current, order = {}, None, []
    lines = data.splitlines(keepends=True)
    # Mois de départ : celui de la 1re ligne datée (les lignes non datées en
    # tête rejoignent ce mois-là).
    for line in lines:
        current = _month_of_line(line, None)
        if current:
            break
    current = current or _month()
    for line in lines:
        current = _month_of_line(line, current)
        if current not in chunks:
            chunks[current] = []
            order.append(current)
        chunks[current].append(line)
    return [(m, b"".join(chunks[m])) for m in order]


def _read_concat(root):
    return b"".join(open(p, "rb").read() for p in partitions(root))


def _marker_path(root):
    return os.path.join(part_dir(root), MARKER)


def migrate(root=".", verbose=True) -> dict:
    """Découpe clv_history.jsonl en partitions mensuelles. Idempotent :
    - déjà migré et ancien fichier inchangé -> vérification seule ;
    - ancien fichier prolongé depuis (vieil écrivain) -> la suite est ajoutée
      à la partition courante, une seule fois ;
    - partitions sans marqueur ou divergence -> ERREUR, rien n'est touché."""
    say = print if verbose else (lambda *a, **k: None)
    legacy = os.path.join(root, LEGACY)
    if not os.path.exists(legacy):
        if partitions(root):
            say("clv_store — ancien fichier absent, partitions présentes : rien à faire.")
            return {"status": "deja_migre_sans_ancien"}
        say("clv_store — ni ancien fichier ni partitions : rien à faire.")
        return {"status": "vide"}
    data = open(legacy, "rb").read()
    if data and not data.endswith(b"\n"):
        data_for_split = data + b"\n"
    else:
        data_for_split = data
    marker_path = _marker_path(root)
    if partitions(root):
        if not os.path.exists(marker_path):
            raise RuntimeError("partitions présentes SANS marqueur de migration : "
                               "situation inconnue, rien n'est modifié.")
        marker = json.load(open(marker_path, encoding="utf-8"))
        size = marker["legacy_size"]
        if _sha(data_for_split[:size]) != marker["legacy_sha256"]:
            raise RuntimeError("l'ancien fichier ne prolonge pas la version migrée : "
                               "rien n'est modifié.")
        extra = data_for_split[size:]
        if extra:
            target = append_path(root, legacy_ok=False)
            with open(target, "ab") as f:
                f.write(extra)
            marker["legacy_size"] = len(data_for_split)
            marker["legacy_sha256"] = _sha(data_for_split)
            marker.setdefault("rattrapages", []).append(
                {"le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 "lignes": extra.count(b"\n"), "vers": os.path.basename(target)})
            json.dump(marker, open(marker_path, "w", encoding="utf-8"), indent=1)
            n_extra = extra.count(b"\n")
            say(f"clv_store — {n_extra} ligne(s) ajoutée(s) à l'ancien "
                f"fichier depuis la migration, reportées dans {os.path.basename(target)}.")
        res = verify(root, verbose=verbose)
        res["status"] = "deja_migre" if not extra else "rattrape"
        return res
    os.makedirs(part_dir(root), exist_ok=True)
    pieces = split_bytes(data_for_split)
    written = []
    for month, chunk in pieces:
        path = _part_name(root, month, 1)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(chunk)
        os.replace(tmp, path)
        written.append({"fichier": os.path.basename(path), "octets": len(chunk),
                        "lignes": chunk.count(b"\n"), "sha256": _sha(chunk)})
    marker = {"migre_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "legacy_size": len(data_for_split), "legacy_sha256": _sha(data_for_split),
              "legacy_lignes": data_for_split.count(b"\n"), "partitions": written}
    json.dump(marker, open(marker_path, "w", encoding="utf-8"), indent=1)
    say(f"clv_store — {len(written)} partition(s) écrite(s) :")
    for w in written:
        say(f"  {w['fichier']:32} {w['lignes']:>7} lignes  {w['octets']/1e6:7.2f} Mo")
    res = verify(root, verbose=verbose)
    res["status"] = "migre"
    return res


def verify(root=".", verbose=True) -> dict:
    """concat(partitions) doit COMMENCER par l'ancien fichier, octet pour
    octet (les lignes ajoutées depuis viennent après)."""
    say = print if verbose else (lambda *a, **k: None)
    legacy = os.path.join(root, LEGACY)
    concat = _read_concat(root)
    res = {"partitions": len(partitions(root)), "lignes_partitions": concat.count(b"\n")}
    if not os.path.exists(legacy):
        res["ok"] = bool(partitions(root))
        say(f"clv_store verify — ancien fichier absent ; {res['partitions']} partition(s), "
            f"{res['lignes_partitions']} lignes.")
        return res
    data = open(legacy, "rb").read()
    if data and not data.endswith(b"\n"):
        data += b"\n"
    res["lignes_ancien"] = data.count(b"\n")
    res["ok"] = concat.startswith(data)
    if res["ok"]:
        say(f"clv_store verify — ✅ {res['lignes_ancien']} lignes de l'ancien fichier "
            f"retrouvées à l'identique ({_sha(data)[:12]}…), "
            f"{res['lignes_partitions'] - res['lignes_ancien']} ajoutée(s) depuis.")
    else:
        say("clv_store verify — ❌ les partitions ne reproduisent PAS l'ancien fichier.")
    return res


def remove_legacy(root=".") -> bool:
    res = verify(root)
    if not res.get("ok") or not os.path.exists(os.path.join(root, LEGACY)):
        print("clv_store — suppression REFUSÉE (vérification non concluante ou fichier absent).")
        return False
    os.remove(os.path.join(root, LEGACY))
    print("clv_store — clv_history.jsonl supprimé (sauvegarde : historique git).")
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "verify"
    root = argv[1] if len(argv) > 1 else "."
    if cmd == "migrate":
        res = migrate(root)
    elif cmd == "verify":
        res = verify(root)
    elif cmd == "remove-legacy":
        return 0 if remove_legacy(root) else 1
    else:
        print(__doc__)
        return 2
    return 0 if res.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
