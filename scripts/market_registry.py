#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market_registry.py — registres Polymarket / Kalshi en ajout seul (16/10/2026).

POURQUOI
polymarket_markets.json (3,4 Mo, ~2 800 marchés) et kalshi_markets.json
(1,6 Mo, ~4 000 marchés) sont réécrits EN ENTIER à chaque run des
collecteurs (~87 fois par jour chacun) alors qu'un run n'ajoute que quelques
marchés : ~440 Mo de nouvelles versions par jour pour quelques Ko d'info.

LE PRINCIPE
  registres_marches/<fournisseur>_base.jsonl        (dans git, écrit UNE fois)
      l'instantané de migration : tous les marchés connus ce jour-là.
  registres_marches/<fournisseur>_AAAA-MM-JJ.jsonl  (dans git, ajout seul)
      une ligne {"id": …, "m": {marché complet}} écrite quand un marché
      APPARAÎT ou quand un de ses champs STABLES change (joueurs, horaire…).
  registres_marches/.volatil_<fournisseur>.json     (HORS git, .gitignore)
      les champs qui bougent à chaque run (Polymarket : liquidity, volume,
      discovered_at) des marchés vus pendant le run.

LECTURE : load(fournisseur) rend la MÊME liste qu'avant (mêmes marchés, même
ordre, première apparition d'abord ; la dernière version d'un marché gagne).
Les champs volatils viennent du cache du run s'il existe, sinon de la ligne
de registre. Aucun lecteur hors des collecteurs n'utilise ces champs
(vérifié le 16/10/2026 : scripts/, Tennis_Edge_Lab/, workflows, workers).

AVANT LA MIGRATION (pas de dossier registres_marches/) : rien ne change, les
collecteurs écrivent leur JSON comme avant.

    python scripts/market_registry.py migrer | verifier | supprimer_ancien | annuler
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys

DIRNAME = "registres_marches"
PROVIDERS = {
    "polymarket": {"legacy": "polymarket_markets.json", "id": "market_id",
                   "volatil": ("liquidity", "volume", "discovered_at")},
    "kalshi": {"legacy": "kalshi_markets.json", "id": "ticker", "volatil": ()},
}


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _iso():
    return _now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def reg_dir(root="."):
    return os.path.join(root, DIRNAME)


def active(root=".") -> bool:
    """La migration a-t-elle eu lieu ?"""
    return os.path.isdir(reg_dir(root))


def files(provider, root="."):
    """<fournisseur>_base.jsonl (instantané de migration, écrit une fois)
    puis <fournisseur>_AAAA-MM-JJ.jsonl (ajouts du jour), dans l'ordre.
    Un fichier PAR JOUR : chaque version committée reste petite (quelques
    dizaines de Ko), au lieu de réécrire un gros fichier à chaque run."""
    pat = re.compile(rf"^{provider}_(\d{{4}}-\d{{2}}-\d{{2}})\.jsonl$")
    days = sorted(p for p in glob.glob(os.path.join(reg_dir(root), f"{provider}_*.jsonl"))
                  if pat.match(os.path.basename(p)))
    base = os.path.join(reg_dir(root), f"{provider}_base.jsonl")
    return ([base] if os.path.exists(base) else []) + days


def _cache_path(provider, root="."):
    return os.path.join(reg_dir(root), f".volatil_{provider}.json")


def _id(provider, m):
    return str(m.get(PROVIDERS[provider]["id"]) or "")


def stable(provider, m):
    vol = PROVIDERS[provider]["volatil"]
    return {k: v for k, v in m.items() if k not in vol}


def _canon(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _registry(provider, root="."):
    """{id: marché} dans l'ordre de première apparition, dernière version."""
    out = {}
    for p in files(provider, root):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                mid = str(rec.get("id") or "")
                if mid:
                    out[mid] = rec.get("m") or {}
    return out


def _versions(provider, root="."):
    """{id: {empreintes complètes de toutes ses lignes}}."""
    out = {}
    for p in files(provider, root):
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                mid = str(rec.get("id") or "")
                if mid:
                    out.setdefault(mid, set()).add(_canon(rec.get("m") or {}))
    return out


def _load_cache(provider, root="."):
    try:
        with open(_cache_path(provider, root), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load(provider, root=".") -> list:
    """Liste des marchés, comme l'ancien fichier `markets`."""
    if not active(root):
        legacy = os.path.join(root, PROVIDERS[provider]["legacy"])
        try:
            with open(legacy, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("markets", []) if isinstance(data, dict) else data
        except (OSError, ValueError):
            return []
    reg = _registry(provider, root)
    cache = _load_cache(provider, root)
    out = []
    for mid, m in reg.items():
        if mid in cache:
            m = {**m, **cache[mid]}
        out.append(m)
    return out


def save(provider, current, root=".", now_iso=None) -> dict:
    """Enregistre les marchés vus pendant ce run (fusion, jamais écrasement).

    Avant la migration : écrit l'ancien JSON, exactement comme avant.
    Après : ajoute une ligne de registre pour chaque marché nouveau ou dont
    un champ stable a changé ; les champs volatils vont au cache hors git."""
    now_iso = now_iso or _iso()
    if not active(root):
        anciens = {}
        for m in load(provider, root):
            if _id(provider, m):
                anciens[_id(provider, m)] = m
        for m in current:
            if _id(provider, m):
                anciens[_id(provider, m)] = m
        payload = {"updated_at": now_iso, "count": len(anciens), "actifs": len(current),
                   "markets": list(anciens.values())}
        _write_json(os.path.join(root, PROVIDERS[provider]["legacy"]), payload)
        return {"mode": "ancien", "count": len(anciens)}
    reg = _registry(provider, root)
    new_lines = []
    for m in current:
        mid = _id(provider, m)
        if not mid:
            continue
        old = reg.get(mid)
        if old is None or _canon(stable(provider, old)) != _canon(stable(provider, m)):
            new_lines.append({"id": mid, "ts": now_iso, "m": m})
            reg[mid] = m
    if new_lines:
        target = os.path.join(reg_dir(root), f"{provider}_{now_iso[:10]}.jsonl")
        with open(target, "a", encoding="utf-8") as f:
            for rec in new_lines:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    vol = PROVIDERS[provider]["volatil"]
    if vol:
        cache = _load_cache(provider, root)
        for m in current:
            mid = _id(provider, m)
            if mid:
                cache[mid] = {k: m[k] for k in vol if k in m}
        _write_json(_cache_path(provider, root), cache)
    return {"mode": "registre", "nouvelles_lignes": len(new_lines), "count": len(reg)}


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


# ── migration ────────────────────────────────────────────────────────────────

def _legacy_markets(provider, root):
    path = os.path.join(root, PROVIDERS[provider]["legacy"])
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("markets", []) if isinstance(data, dict) else data


def migrer(root=".", verbose=True) -> dict:
    """Recopie chaque marché de l'ancien JSON dans le registre s'il y manque
    ou diffère (idempotent : relancé, il ne rattrape que ce qu'un ancien
    collecteur aurait ajouté entre-temps). Puis vérifie."""
    say = print if verbose else (lambda *a, **k: None)
    os.makedirs(reg_dir(root), exist_ok=True)
    res = {}
    for prov in PROVIDERS:
        legacy = _legacy_markets(prov, root)
        if legacy is None:
            res[prov] = {"ajoutees": 0, "ancien": "absent"}
            continue
        vus = _versions(prov, root)
        lines = []
        for m in legacy:
            mid = _id(prov, m)
            # Déjà enregistré tel quel (dans n'importe quelle ligne) : rien.
            # Sinon (1re migration, ou ancien collecteur passé entre-temps) : ajout.
            if mid and _canon(m) not in vus.get(mid, set()):
                lines.append({"id": mid, "ts": "migration", "m": m})
                vus.setdefault(mid, set()).add(_canon(m))
        if lines:
            # 1re migration -> instantané « base » ; rattrapage -> fichier du jour.
            base = os.path.join(reg_dir(root), f"{prov}_base.jsonl")
            target = base if not os.path.exists(base) else os.path.join(
                reg_dir(root), f"{prov}_{_iso()[:10]}.jsonl")
            with open(target, "a", encoding="utf-8") as f:
                for rec in lines:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        res[prov] = {"ajoutees": len(lines)}
        say(f"market_registry — {prov} : {len(lines)} ligne(s) ajoutée(s) au registre.")
    ver = verifier(root, verbose=verbose)
    return {"ok": ver["ok"], "migration": res, "verification": ver}


def verifier(root=".", verbose=True) -> dict:
    """Chaque marché de l'ancien JSON se retrouve À L'IDENTIQUE et dans le
    même ordre au début de load() (load peut en contenir plus : marchés
    découverts depuis)."""
    say = print if verbose else (lambda *a, **k: None)
    out = {"ok": True}
    for prov in PROVIDERS:
        legacy = _legacy_markets(prov, root)
        if not active(root):
            out[prov] = "non migré"
            out["ok"] = False
            continue
        reg = _registry(prov, root)
        if legacy is None:
            out[prov] = {"ancien": "absent", "registre": len(reg)}
            say(f"market_registry verify — {prov} : ancien fichier absent, {len(reg)} marchés.")
            continue
        vus = _versions(prov, root)
        legacy = [m for m in legacy if _id(prov, m)]
        ids = [_id(prov, m) for m in legacy]
        # Ordre : les marchés de l'ancien fichier, dans son ordre, en tête.
        same_order = list(reg)[:len(ids)] == ids
        # Contenu : chaque version de l'ancien fichier est dans le registre
        # (le registre peut en avoir une plus récente depuis : c'est normal).
        stale = [mid for mid, m in zip(ids, legacy) if _canon(m) not in vus.get(mid, set())]
        ok = same_order and not stale
        out[prov] = {"ancien": len(ids), "registre": len(reg), "ordre_identique": same_order,
                     "differents": len(stale)}
        out["ok"] = out["ok"] and ok
        say(f"market_registry verify — {prov} : {'✅' if ok else '❌'} {len(ids)} marchés de "
            f"l'ancien fichier retrouvés{'' if ok else ' (ÉCARTS : relancer migrer)'} ; "
            f"registre {len(reg)}.")
    return out


def supprimer_ancien(root=".") -> bool:
    ver = verifier(root)
    if not ver["ok"]:
        print("market_registry — suppression REFUSÉE (vérification non concluante).")
        return False
    for prov, spec in PROVIDERS.items():
        p = os.path.join(root, spec["legacy"])
        if os.path.exists(p):
            os.remove(p)
            print(f"market_registry — {spec['legacy']} supprimé (reste dans l'historique git).")
    return True


def annuler(root=".") -> bool:
    """RETOUR ARRIÈRE : réécrit les anciens JSON depuis le registre, puis
    retire registres_marches/. Les collecteurs reprennent l'ancien format."""
    if not active(root):
        print("market_registry — rien à annuler.")
        return True
    for prov, spec in PROVIDERS.items():
        markets = load(prov, root)
        _write_json(os.path.join(root, spec["legacy"]),
                    {"updated_at": _iso(), "count": len(markets), "actifs": 0,
                     "markets": markets})
        print(f"market_registry — {spec['legacy']} réécrit ({len(markets)} marchés).")
    for p in glob.glob(os.path.join(reg_dir(root), "*")) + \
            glob.glob(os.path.join(reg_dir(root), ".*")):
        os.remove(p)
    os.rmdir(reg_dir(root))
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "verifier"
    root = argv[1] if len(argv) > 1 else "."
    if cmd == "migrer":
        return 0 if migrer(root)["ok"] else 1
    if cmd == "verifier":
        return 0 if verifier(root)["ok"] else 1
    if cmd == "supprimer_ancien":
        return 0 if supprimer_ancien(root) else 1
    if cmd == "annuler":
        return 0 if annuler(root) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
