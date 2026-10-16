#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""depot_neuf.py — repartir d'un dépôt neuf SANS l'historique lourd (5 Go).

    python scripts/depot_neuf.py controle                 # lecture seule, à tout moment
    python scripts/depot_neuf.py instantane DOSSIER       # copie de l'état actuel, sans ce que R2 détient
    python scripts/depot_neuf.py verifier DOSSIER_NEUF    # l'ancien == le neuf + R2, fichier par fichier

Appelé par le workflow « Dépôt neuf » (.github/workflows/depot_neuf.yml).
Déroulé complet : docs/README_DEPOT_NEUF.md.

PRINCIPE (rien n'est jamais perdu)
- L'ancien dépôt est RENOMMÉ (Tennis-edge-archive-2026), jamais supprimé ni
  réécrit : tout son historique et ses Releases y restent.
- Le nouveau `Tennis-edge` reçoit l'état actuel en UN commit, poussé
  normalement dans un dépôt vide (aucun push forcé).
- Une partition parts/ n'est laissée hors du nouveau dépôt QUE si R2 contient
  TOUTES ses lignes (même empreinte, ou chaque ligne présente côté R2). Sinon
  elle part dans le nouveau dépôt comme avant.
- `verifier` reprend chaque fichier suivi de l'ancien : identique dans le
  neuf, ou laissé de côté ET couvert par R2. Sinon : ❌.
"""
from __future__ import annotations

import collections
import gzip
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_io  # noqa: E402
import hist_r2  # noqa: E402

FAMILLES_R2 = ("pm", "kx", "live", "hist")
IMPORT_JSON = "depot_neuf/IMPORT.json"
# Anciens fichiers remplacés par des partitions : leur suppression
# (« supprimer_ancien ») est un prérequis.
ANCIENS = ("clv_history.jsonl",)


def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], capture_output=True, cwd=cwd)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)} : {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout


def fichiers_suivis(cwd=None):
    return [p for p in _git("ls-files", "-z", cwd=cwd).decode("utf-8").split("\0") if p]


def blobs(cwd=None):
    """{chemin: sha1 du blob} de HEAD."""
    out = {}
    for rec in _git("ls-tree", "-r", "-z", "HEAD", cwd=cwd).decode("utf-8").split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        out[path] = meta.split()[2]
    return out


def _lignes(nom, data):
    if nom.endswith(".gz"):
        data = gzip.decompress(data)
    return [x for x in data.splitlines() if x.strip()]


def couverture(path, r2, manifestes, now=None):
    """État d'une partition suivie par git, vis-à-vis de R2 :
      None               pas une partition R2 (reste dans le dépôt neuf)
      'courante'         hist de la période en cours : reste dans git
      'absent_r2'        R2 ne la connaît pas : reste dans git
      'identique'        R2 a exactement ce contenu       -> hors du dépôt neuf
      'r2_contient'      R2 a toutes ses lignes (et plus) -> hors du dépôt neuf
      'different'        R2 n'a PAS toutes ses lignes : reste dans git
    """
    nom = os.path.basename(path)
    if os.path.dirname(path) != r2_io.PARTS_DIR:
        return None
    fam = r2_io.family_of(nom)
    if fam not in FAMILLES_R2:
        return None
    if fam == "hist" and not hist_r2.is_frozen(nom, now=now):
        return "courante"
    if fam not in manifestes:
        manifestes[fam] = r2_io.load_manifest(r2, fam, use_cache=False)[0]
    ent = manifestes[fam]["files"].get(nom)
    if not ent:
        return "absent_r2"
    if ent.get("sha256") == r2_io.file_sha256(path):
        return "identique"
    distant = r2.get(ent.get("key") or (r2_io.FAMILIES[fam]["prefix"] + nom))
    if distant is None:
        return "absent_r2"
    with open(path, "rb") as f:
        local = f.read()
    try:
        manque = collections.Counter(_lignes(nom, local)) - collections.Counter(_lignes(nom, distant))
    except (OSError, EOFError, ValueError):
        return "different"
    return "different" if manque else "r2_contient"


HORS = ("identique", "r2_contient")


# ── controle ────────────────────────────────────────────────────────────────

def _gh_json(*args):
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True)
    except OSError:
        return None
    if r.returncode:
        return None
    try:
        return json.loads(r.stdout or "null")
    except ValueError:
        return None


def releases_restantes():
    """(nb de fichiers de Releases pas encore copiés dans R2, détail) ou (None, msg)."""
    try:
        import ticks_releases_r2 as trr
    except ImportError:
        return None, "ticks_releases_r2.py absent"
    try:
        assets = trr.release_assets()
    except OSError:
        assets = None
    if assets is None:
        return None, "liste des Releases illisible"
    r2 = r2_io.client()
    rows = trr.plan(trr.load_index(), assets, trr.load_state(), trr._manifests(r2))
    etats = collections.Counter(r["etat"] for r in rows)
    reste = sum(n for e, n in etats.items() if e in ("a_copier", "dans_r2_a_verifier"))
    return reste, dict(etats)


def cmd_controle(report="depot_neuf_controle.json"):
    lignes, bloquants = [], []

    def ok(cond, texte, bloquant=True):
        lignes.append(f"{'✅' if cond else ('❌' if bloquant else '⚠️ ')} {texte}")
        if not cond and bloquant:
            bloquants.append(texte)

    mode = r2_io.mode()
    ok(mode == "on", f"R2_PRIMARY = {mode} (attendu : on)")

    runs = _gh_json("run", "list", "--workflow", "r2_parts_verify.yml", "--limit", "7",
                    "--json", "conclusion,createdAt") or []
    verts = sum(1 for r in runs if r.get("conclusion") == "success")
    ok(len(runs) >= 7 and verts == 7,
       f"« R2 — vérifier partitions » : {verts} vert(s) sur les {len(runs)} derniers (attendu 7/7)")

    r2 = r2_io.client()
    ok(r2 is not None, "R2 joignable")
    etats, poids = collections.Counter(), collections.Counter()
    if r2 is not None:
        mans = {}
        for p in fichiers_suivis():
            e = couverture(p, r2, mans)
            if e:
                etats[e] += 1
                poids[e] += os.path.getsize(p)
    hors = sum(poids[e] for e in HORS)
    ok(r2 is not None and etats["different"] == 0 and etats["absent_r2"] == 0,
       f"Partitions parts/ : {dict(etats)} — {hors/1e6:.0f} Mo resteront hors du dépôt neuf "
       f"(R2 les détient) ; 'absent_r2'/'different' doivent être à 0")

    for a in ANCIENS:
        ok(not os.path.exists(a), f"{a} supprimé (« supprimer_ancien » fait)")

    reste, detail = releases_restantes()
    if reste is None:
        ok(False, f"Releases → R2 : non vérifiable ({detail})")
    else:
        ok(reste == 0, f"Releases → R2 : {reste} fichier(s) encore à copier — {detail}")

    # Seuls les NOMS sont lus : les valeurs ne sont jamais affichées.
    secrets = sorted(k for k in json.loads(os.environ.get("SECRETS_JSON") or "{}") if k.lower() != "github_token")
    variables = sorted(k for k in json.loads(os.environ.get("VARS_JSON") or "{}") if not k.startswith("DEPOT_NEUF_"))
    ok(bool(secrets), f"{len(secrets)} secret(s) seront copiés : {', '.join(secrets)}", bloquant=False)
    ok(True, f"{len(variables)} variable(s) seront copiées : {', '.join(variables)}", bloquant=False)

    total = sum(os.path.getsize(p) for p in fichiers_suivis() if os.path.isfile(p))
    ok(True, f"Taille de l'état actuel : {total/1e6:.0f} Mo ; dépôt neuf estimé "
             f"≈ {(total - hors)/1e6:.0f} Mo (contre ~5 Go d'historique aujourd'hui)", bloquant=False)
    try:
        with open("repo_size_status.json", encoding="utf-8") as f:
            taille = json.load(f).get("taille_go")
        ok(True, f"Taille actuelle du dépôt sur GitHub : {taille} Go", bloquant=False)
    except (OSError, ValueError):
        pass

    print("\n".join(lignes))
    print()
    if bloquants:
        print(f"⛔ PAS ENCORE PRÊT — {len(bloquants)} point(s) bloquant(s). Ne pas lancer « geler ».")
    else:
        print("🟢 PRÊT — on peut lancer « geler » (voir docs/README_DEPOT_NEUF.md).")
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"pret": not bloquants, "bloquants": bloquants, "lignes": lignes,
                   "partitions": dict(etats), "hors_depot_mo": round(hors / 1e6, 1)},
                  f, ensure_ascii=False, indent=1)
    return 0


# ── instantane ──────────────────────────────────────────────────────────────

def cmd_instantane(dest):
    r2 = r2_io.client()
    if r2 is None:
        print("::error::R2 indisponible : instantané refusé (sans R2, impossible de savoir "
              "quelles partitions il détient). Relancer plus tard.")
        return 1
    if os.path.exists(dest) and os.listdir(dest):
        print(f"::error::{dest} n'est pas vide")
        return 1
    os.makedirs(dest, exist_ok=True)
    source = _git("rev-parse", "HEAD").decode().strip()
    mans, laisses, copies, octets = {}, {}, 0, 0
    for p in fichiers_suivis():
        if os.path.islink(p) or not os.path.isfile(p):
            continue
        e = couverture(p, r2, mans)
        if e in HORS:
            laisses[p] = e
            continue
        cible = os.path.join(dest, p)
        os.makedirs(os.path.dirname(cible) or dest, exist_ok=True)
        shutil.copy2(p, cible)
        copies += 1
        octets += os.path.getsize(p)
    rapport = {"source_depot": os.environ.get("GITHUB_REPOSITORY", ""), "source_sha": source,
               "genere_le": r2_io.now_iso(), "fichiers_copies": copies,
               "octets_copies": octets, "laisses_dans_r2": laisses}
    os.makedirs(os.path.join(dest, os.path.dirname(IMPORT_JSON)), exist_ok=True)
    with open(os.path.join(dest, IMPORT_JSON), "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Instantané de {source[:10]} : {copies} fichiers, {octets/1e6:.0f} Mo ; "
          f"{len(laisses)} partition(s) laissée(s) dans R2 (couvertes).")
    print(r2_io.ops_summary())
    return 0


# ── verifier ────────────────────────────────────────────────────────────────

def cmd_verifier(neuf):
    """À lancer dans l'ANCIEN dépôt (checkout de HEAD), avec le neuf cloné dans NEUF."""
    try:
        with open(os.path.join(neuf, IMPORT_JSON), encoding="utf-8") as f:
            imp = json.load(f)
    except (OSError, ValueError):
        print(f"::error::{IMPORT_JSON} introuvable dans le dépôt neuf")
        return 1
    ancien, nouveau = blobs(), blobs(cwd=neuf)
    head = _git("rev-parse", "HEAD").decode().strip()
    pb = []
    if imp.get("source_sha") != head:
        pb.append(f"l'ancien dépôt a bougé depuis l'instantané ({imp.get('source_sha', '')[:10]} → {head[:10]}) : "
                  "un workflow n'était pas gelé ?")
    r2 = r2_io.client()
    mans = {}
    identiques = 0
    for p, sha in sorted(ancien.items()):
        if nouveau.get(p) == sha:
            identiques += 1
            continue
        if p in imp.get("laisses_dans_r2", {}):
            if r2 is None:
                pb.append(f"{p} : laissé dans R2, mais R2 injoignable pour le revérifier")
            elif couverture(p, r2, mans) not in HORS:
                pb.append(f"{p} : laissé hors du dépôt neuf mais PLUS couvert par R2")
            continue
        pb.append(f"{p} : {'absent du' if p not in nouveau else 'différent dans le'} dépôt neuf")
    en_trop = sorted(set(nouveau) - set(ancien) - {IMPORT_JSON})
    for p in en_trop:
        pb.append(f"{p} : présent dans le neuf mais pas dans l'ancien")
    print(f"{identiques} fichier(s) identiques, {len(imp.get('laisses_dans_r2', {}))} "
          f"partition(s) servie(s) par R2, {len(pb)} problème(s).")
    for x in pb[:60]:
        print(f"  ❌ {x}")
    if pb:
        print("::error::Vérification KO — ne pas lancer « degeler ». Voir le retour arrière.")
        return 1
    print("✅ Le dépôt neuf contient tout l'état de l'ancien (le reste est dans R2).")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]
    if cmd == "controle":
        return cmd_controle()
    if cmd == "instantane" and len(rest) == 1:
        return cmd_instantane(rest[0])
    if cmd == "verifier" and len(rest) == 1:
        return cmd_verifier(rest[0])
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
