#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jsonl_parts.py — un journal JSONL en ajout seul, découpé par MOIS (16/10/2026).

Généralisation de clv_store.py (qui reste tel quel, déjà en production) pour
d'autres journaux, à commencer par odds_alerts_log.jsonl (alerts_store.py).

    <dossier>/<préfixe>_AAAA-MM.jsonl   (puis _2, _3… au-delà de max_mb)

ORDRE IDENTIQUE À LA LIGNE PRÈS : le mois d'une ligne est celui du MAXIMUM
COURANT de son horodatage (migration) ou le mois UTC courant (ajouts) ; les
deux ne décroissent jamais, donc la concaténation des partitions redonne
exactement l'ancien fichier (vérifié octet pour octet par migrate()).

Un chemin portant le nom de l'ancien fichier est résolu vers les partitions
dès qu'elles existent ; tout autre chemin est lu tel quel.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import io
import json
import os
import re


class _Lines(io.TextIOBase):
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


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Store:
    MARKER = "MIGRATION.json"

    def __init__(self, legacy, dirname, prefix, time_field, max_mb_env, default_mb=8.0):
        self.legacy = legacy
        self.dirname = dirname
        self.prefix = prefix
        self.time_field = time_field
        self.max_mb_env = max_mb_env
        self.default_mb = default_mb
        self._name = re.compile(rf"^{re.escape(prefix)}_(\d{{4}}-\d{{2}})(?:_(\d+))?\.jsonl$")

    @property
    def max_mb(self):
        return float(os.environ.get(self.max_mb_env, self.default_mb))

    # ── chemins ──────────────────────────────────────────────────────────
    def part_dir(self, root="."):
        return os.path.join(root, self.dirname)

    def partitions(self, root="."):
        out = []
        for p in glob.glob(os.path.join(self.part_dir(root), f"{self.prefix}_*.jsonl")):
            m = self._name.match(os.path.basename(p))
            if m:
                out.append(((m.group(1), int(m.group(2) or 1)), p))
        return [p for _, p in sorted(out)]

    def _root_of(self, path):
        return os.path.dirname(os.path.abspath(path))

    def resolve(self, path=None):
        path = path or self.legacy
        if os.path.basename(path) == self.legacy:
            parts = self.partitions(self._root_of(path))
            if parts:
                return parts
        return [path] if os.path.exists(path) else []

    # ── lecture ──────────────────────────────────────────────────────────
    def exists(self, path=None) -> bool:
        return bool(self.resolve(path))

    def iter_lines(self, path=None):
        for p in self.resolve(path):
            with open(p, encoding="utf-8") as f:
                yield from f

    def iter_records(self, path=None):
        for line in self.iter_lines(path):
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError:
                    continue

    def open_text(self, path=None):
        paths = self.resolve(path)
        if not paths:
            raise FileNotFoundError(path or self.legacy)
        return _Lines(paths)

    # ── écriture ─────────────────────────────────────────────────────────
    def _part_name(self, root, month, seq):
        suffix = "" if seq == 1 else f"_{seq}"
        return os.path.join(self.part_dir(root), f"{self.prefix}_{month}{suffix}.jsonl")

    def append_path(self, root=".", now=None):
        """Fichier où AJOUTER maintenant. Avant migration : l'ancien fichier."""
        legacy = os.path.join(root, self.legacy)
        parts = self.partitions(root)
        if not parts and os.path.exists(legacy):
            return legacy
        if not parts and not os.path.isdir(self.part_dir(root)):
            return legacy
        month = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m")
        if parts:
            month = max(month, self._name.match(os.path.basename(parts[-1])).group(1))
        os.makedirs(self.part_dir(root), exist_ok=True)
        seq = 1
        for p in parts:
            m = self._name.match(os.path.basename(p))
            if m.group(1) == month:
                seq = max(seq, int(m.group(2) or 1))
        path = self._part_name(root, month, seq)
        while os.path.exists(path) and os.path.getsize(path) / 1e6 >= self.max_mb:
            seq += 1
            path = self._part_name(root, month, seq)
        return path

    # ── migration ────────────────────────────────────────────────────────
    def _month_of_line(self, line: bytes, current):
        try:
            ts = json.loads(line).get(self.time_field) or ""
        except (ValueError, AttributeError):
            return current
        m = re.match(r"^(\d{4}-\d{2})", str(ts))
        if not m:
            return current
        return max(current, m.group(1)) if current else m.group(1)

    def split_bytes(self, data: bytes):
        lines = data.splitlines(keepends=True)
        current = None
        for line in lines:
            current = self._month_of_line(line, None)
            if current:
                break
        current = current or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
        chunks, order = {}, []
        for line in lines:
            current = self._month_of_line(line, current)
            if current not in chunks:
                chunks[current] = []
                order.append(current)
            chunks[current].append(line)
        return [(m, b"".join(chunks[m])) for m in order]

    def _concat(self, root):
        return b"".join(open(p, "rb").read() for p in self.partitions(root))

    def _legacy_bytes(self, root):
        data = open(os.path.join(root, self.legacy), "rb").read()
        return data + b"\n" if data and not data.endswith(b"\n") else data

    def migrate(self, root=".", verbose=True) -> dict:
        say = print if verbose else (lambda *a, **k: None)
        legacy = os.path.join(root, self.legacy)
        marker = os.path.join(self.part_dir(root), self.MARKER)
        if not os.path.exists(legacy):
            say(f"{self.prefix} — ancien fichier absent : rien à faire.")
            return {"status": "absent", "ok": bool(self.partitions(root))}
        data = self._legacy_bytes(root)
        if self.partitions(root):
            if not os.path.exists(marker):
                raise RuntimeError("partitions présentes SANS marqueur : rien n'est modifié.")
            info = json.load(open(marker, encoding="utf-8"))
            size = info["legacy_size"]
            if _sha(data[:size]) != info["legacy_sha256"]:
                raise RuntimeError("l'ancien fichier ne prolonge pas la version migrée.")
            extra = data[size:]
            if extra:
                with open(self.append_path(root), "ab") as f:
                    f.write(extra)
                info.update(legacy_size=len(data), legacy_sha256=_sha(data))
                json.dump(info, open(marker, "w", encoding="utf-8"), indent=1)
                n_extra = extra.count(b"\n")
                say(f"{self.prefix} — {n_extra} ligne(s) tardive(s) reportée(s).")
            res = self.verify(root, verbose)
            res["status"] = "rattrape" if extra else "deja_migre"
            return res
        os.makedirs(self.part_dir(root), exist_ok=True)
        written = []
        for month, chunk in self.split_bytes(data):
            path = self._part_name(root, month, 1)
            with open(path + ".tmp", "wb") as f:
                f.write(chunk)
            os.replace(path + ".tmp", path)
            written.append({"fichier": os.path.basename(path), "lignes": chunk.count(b"\n"),
                            "octets": len(chunk), "sha256": _sha(chunk)})
        json.dump({"migre_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   "legacy_size": len(data), "legacy_sha256": _sha(data),
                   "legacy_lignes": data.count(b"\n"), "partitions": written},
                  open(marker, "w", encoding="utf-8"), indent=1)
        for w in written:
            say(f"  {w['fichier']:36} {w['lignes']:>7} lignes  {w['octets']/1e6:7.2f} Mo")
        res = self.verify(root, verbose)
        res["status"] = "migre"
        return res

    def verify(self, root=".", verbose=True) -> dict:
        say = print if verbose else (lambda *a, **k: None)
        legacy = os.path.join(root, self.legacy)
        concat = self._concat(root)
        res = {"partitions": len(self.partitions(root)), "lignes_partitions": concat.count(b"\n")}
        if not os.path.exists(legacy):
            res["ok"] = bool(self.partitions(root))
            say(f"{self.prefix} verify — ancien fichier absent ; {res['partitions']} "
                f"partition(s), {res['lignes_partitions']} lignes.")
            return res
        data = self._legacy_bytes(root)
        res["lignes_ancien"] = data.count(b"\n")
        res["ok"] = concat.startswith(data)
        say(f"{self.prefix} verify — {'✅' if res['ok'] else '❌'} "
            f"{res['lignes_ancien']} lignes de l'ancien fichier "
            f"{'retrouvées à l’identique' if res['ok'] else 'NON reproduites (relancer migrer)'} ; "
            f"{res['lignes_partitions'] - res['lignes_ancien']} ajoutée(s) depuis.")
        return res

    def remove_legacy(self, root=".") -> bool:
        if not self.verify(root).get("ok") or not os.path.exists(os.path.join(root, self.legacy)):
            print(f"{self.prefix} — suppression REFUSÉE (vérification non concluante).")
            return False
        os.remove(os.path.join(root, self.legacy))
        print(f"{self.prefix} — {self.legacy} supprimé (reste dans l'historique git).")
        return True

    def restore(self, root=".") -> bool:
        """RETOUR ARRIÈRE : reconstitue l'ancien fichier (concaténation) et
        retire le dossier des partitions."""
        if not self.partitions(root):
            print(f"{self.prefix} — rien à annuler.")
            return True
        data = self._concat(root)
        legacy = os.path.join(root, self.legacy)
        with open(legacy + ".tmp", "wb") as f:
            f.write(data)
        os.replace(legacy + ".tmp", legacy)
        for p in glob.glob(os.path.join(self.part_dir(root), "*")):
            os.remove(p)
        os.rmdir(self.part_dir(root))
        n_lignes = data.count(b"\n")
        print(f"{self.prefix} — {self.legacy} reconstitué ({n_lignes} lignes).")
        return True

    def main(self, argv):
        cmd = argv[0] if argv else "verifier"
        root = argv[1] if len(argv) > 1 else "."
        if cmd in ("migrer", "migrate"):
            return 0 if self.migrate(root)["ok"] else 1
        if cmd in ("verifier", "verify"):
            return 0 if self.verify(root)["ok"] else 1
        if cmd in ("supprimer_ancien", "remove-legacy"):
            return 0 if self.remove_legacy(root) else 1
        if cmd in ("annuler", "restore"):
            return 0 if self.restore(root) else 1
        print("commandes : migrer | verifier | supprimer_ancien | annuler")
        return 2
