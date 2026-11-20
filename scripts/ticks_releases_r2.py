#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ticks_releases_r2.py — copie dans R2 les ticks archivés en GitHub Releases.

    python scripts/ticks_releases_r2.py inventaire
    python scripts/ticks_releases_r2.py copier --max 10

POURQUOI (16/10/2026)
archive_ticks.py sortait de git les ticks Polymarket/Kalshi de plus de 7
jours vers des Releases mensuelles (ticks-AAAA-MM). Ces Releases restent dans
l'ANCIEN dépôt si l'on repart un jour d'un dépôt neuf : il faut donc que R2
en détienne une copie vérifiée. Les Releases ne sont JAMAIS supprimées ici.

PRINCIPE
  • Source : parts/ARCHIVE_INDEX.json (entrées dont la release commence par
    « ticks- » ; celles notées « r2:… » sont déjà dans R2).
  • Copie : `gh release download <tag> -p <fichier>` -> contrôle gzip ->
    R2 parts/ticks/<fichier> en création exclusive, manifeste r2_io (même
    disposition que les collecteurs depuis l'étape 1) -> RE-TÉLÉCHARGEMENT et
    comparaison SHA-256.
  • Si R2 a déjà une version de ce fichier : identique -> « copie » ; la
    version R2 prolonge celle de la Release -> « r2_plus_complet » (rien
    n'est écrasé) ; sinon -> « conflit », signalé, rien n'est touché.
  • Progression : parts/RELEASES_R2_STATE.json (petit, committé).
  • Lots bornés (--max, 10 par défaut) : un run reste court et rejouable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_io  # noqa: E402

INDEX = os.environ.get("ARCHIVE_INDEX", "parts/ARCHIVE_INDEX.json")
STATE = os.environ.get("RELEASES_R2_STATE", "parts/RELEASES_R2_STATE.json")
FINAL = {"copie", "r2_plus_complet", "conflit"}


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def load_index(path=INDEX):
    try:
        return json.load(open(path, encoding="utf-8")).get("archives", [])
    except (OSError, ValueError):
        return []


def load_state(path=STATE):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {"fichiers": {}}


def save_state(state, path=STATE):
    state["maj"] = r2_io.now_iso()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def release_assets():
    """{tag: {fichier: octets}} pour les releases ticks-*, ou None si gh échoue."""
    code, out = gh("release", "list", "--limit", "200", "--json", "tagName", "--jq", ".[].tagName")
    if code:
        print(f"⚠️ liste des releases illisible : {out.strip()[:160]}")
        return None
    assets = {}
    for tag in out.split():
        if not tag.startswith("ticks-"):
            continue
        c2, o2 = gh("release", "view", tag, "--json", "assets",
                    "--jq", '.assets[] | "\\(.name)\\t\\(.size)"')
        if c2:
            assets[tag] = None
            continue
        assets[tag] = {}
        for line in o2.splitlines():
            if "\t" in line:
                name, size = line.split("\t", 1)
                assets[tag][name] = int(size) if size.strip().isdigit() else None
    return assets


def plan(index, assets, state, mans):
    """Une ligne par fichier indexé, avec son état."""
    rows = []
    for a in index:
        name, tag = a.get("fichier"), str(a.get("release") or "")
        if not name:
            continue
        row = {"fichier": name, "release": tag, "octets_index": a.get("octets")}
        fam = r2_io.family_of(name)
        if tag.startswith("r2:"):
            row["etat"] = "deja_r2"
        elif not tag.startswith("ticks-"):
            row["etat"] = "hors_perimetre"
        elif fam not in ("pm", "kx"):
            row["etat"] = "nom_non_reconnu"
        elif assets is not None and tag not in assets:
            row["etat"] = "release_absente"
        elif assets is not None and assets[tag] is None:
            row["etat"] = "release_illisible"
        elif assets is not None and name not in assets[tag]:
            row["etat"] = "asset_absent"
        else:
            done = state["fichiers"].get(name, {}).get("etat")
            if done not in FINAL:
                done = None                      # erreurs : on retentera au prochain lot
            ent = mans.get(fam, {}).get(name) if fam else None
            row["etat"] = done or ("dans_r2_a_verifier" if ent else "a_copier")
        rows.append(row)
    return rows


def _manifests(r2):
    if r2 is None:
        return {}
    return {fam: r2_io.load_manifest(r2, fam, use_cache=False)[0]["files"] for fam in ("pm", "kx")}


def inventaire(report_path="ticks_releases_inventaire.json", environ=None):
    r2 = r2_io.client(environ)
    assets = release_assets()
    rows = plan(load_index(), assets, load_state(), _manifests(r2))
    counts = {}
    for r in rows:
        counts[r["etat"]] = counts.get(r["etat"], 0) + 1
    missing_tags = sorted({r["release"] for r in rows if r["etat"] == "release_absente"})
    missing_assets = [r["fichier"] for r in rows if r["etat"] == "asset_absent"]
    rep = {"genere_le": r2_io.now_iso(), "fichiers_indexes": len(rows), "etats": counts,
           "releases_absentes": missing_tags, "assets_absents": missing_assets,
           "lignes": rows}
    if report_path:
        json.dump(rep, open(report_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Ticks indexés en Releases : {len(rows)} — {counts}")
    if missing_tags:
        print(f"❌ RELEASES ABSENTES ({len(missing_tags)}) : {', '.join(missing_tags)} — "
              f"{sum(1 for r in rows if r['etat'] == 'release_absente')} fichier(s) indexé(s) "
              f"sans source. Vérifier sur github.com → Releases.")
    if missing_assets:
        print(f"❌ ASSETS ABSENTS ({len(missing_assets)}) : {', '.join(missing_assets[:10])}"
              f"{' …' if len(missing_assets) > 10 else ''}")
    if assets is None:
        print("⚠️ gh indisponible : états release non vérifiés.")
    print(r2_io.ops_summary())
    return rep


def copier(max_files=10, environ=None):
    r2 = r2_io.client(environ)
    if r2 is None:
        print("❌ R2 indisponible : rien n'est copié.")
        return 1
    assets = release_assets()
    if assets is None:
        print("❌ gh indisponible : rien n'est copié.")
        return 1
    state = load_state()
    mans = _manifests(r2)
    todo = [r for r in plan(load_index(), assets, state, mans)
            if r["etat"] in ("a_copier", "dans_r2_a_verifier")][:max_files]
    updates = {"pm": {}, "kx": {}}
    errors = 0
    with tempfile.TemporaryDirectory() as tmp:
        for row in todo:
            name, tag = row["fichier"], row["release"]
            fam = r2_io.family_of(name)
            key = r2_io.FAMILIES[fam]["prefix"] + name
            code, out = gh("release", "download", tag, "-p", name, "--dir", tmp, "--clobber")
            path = os.path.join(tmp, name)
            if code or not os.path.exists(path):
                state["fichiers"][name] = {"etat": "erreur_telechargement", "release": tag}
                errors += 1
                print(f"  ❌ {name} : téléchargement impossible ({out.strip()[:120]})")
                continue
            data = open(path, "rb").read()
            try:
                lines = r2_io.gz_lines(data)
            except Exception as exc:  # noqa: BLE001
                state["fichiers"][name] = {"etat": "asset_illisible", "release": tag}
                errors += 1
                print(f"  ❌ {name} : gzip illisible ({type(exc).__name__})")
                continue
            sha = _sha(data)
            etat, etag = None, None
            existing = r2.get_with_etag(key)
            if existing is None:
                try:
                    etag = r2.put(key, data, create_only=True, content_type="application/gzip",
                                  metadata={"lines": str(lines), "source": f"release:{tag}"})
                except r2_io.PreconditionFailed:
                    existing = r2.get_with_etag(key)
            if existing is not None:
                if _sha(existing[0]) == sha:
                    etat = "copie"
                elif existing[0].startswith(data):
                    etat = "r2_plus_complet"
                else:
                    etat = "conflit"
            if etat is None:                       # vient d'être écrit : on relit
                back = r2.get(key)
                etat = "copie" if back is not None and _sha(back) == sha else "erreur_verification"
            entry = {"etat": etat, "release": tag, "octets": len(data), "lignes": lines,
                     "sha256": sha, "copie_le": r2_io.now_iso()}
            state["fichiers"][name] = entry
            if etat == "copie" and name not in mans.get(fam, {}):
                updates[fam][name] = r2_io.entry_for(fam, name, data, etag or hashlib.md5(data).hexdigest(), lines)
            if etat in ("conflit", "erreur_verification"):
                errors += 1
            print(f"  {'✅' if etat in ('copie', 'r2_plus_complet') else '❌'} {name:36} "
                  f"{len(data)/1e6:6.2f} Mo  {etat}")
            os.remove(path)
    for fam, ups in updates.items():
        if ups:
            r2_io.save_manifest(r2, fam, ups)
    save_state(state)
    restants = sum(1 for r in plan(load_index(), assets, state, mans) if r["etat"] == "a_copier")
    print(f"Lot : {len(todo)} traité(s), {errors} problème(s), {restants} restant(s) à copier. "
          f"{r2_io.ops_summary()}")
    return 1 if errors else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("command", choices=["inventaire", "copier"])
    ap.add_argument("--max", type=int, default=10)
    a = ap.parse_args(argv)
    if a.command == "inventaire":
        inventaire()
        return 0
    return copier(a.max)


if __name__ == "__main__":
    sys.exit(main())
