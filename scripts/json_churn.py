#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""json_churn.py — ne pas committer un JSON dont seuls les champs volatils ont bougé.

    python scripts/json_churn.py gate            # après git add, avant git commit

POURQUOI (mesure du 15/10/2026, 24 h)
  polymarket_markets.json   87 versions × 3,4 Mo   (registre du collecteur)
  kalshi_markets.json       87 versions × 1,6 Mo   (idem)
  resultats_derived.json   247 versions × 1,0 Mo   (pont de résultats)
Pour kalshi_markets.json, entre deux runs seul `updated_at` change ; pour
resultats_derived.json, très souvent seul `generated_at` ; pour Polymarket,
`liquidity`/`volume`/`discovered_at` de quelques marchés. Ces versions ne
portent aucune information utile à l'historique.

RÈGLE
Pour chaque fichier connu (PROFILS) indexé pour le commit, on compare la
version HEAD et la version indexée APRÈS retrait des champs volatils. Si
elles sont identiques, le fichier est retiré du commit et remis à sa version
HEAD (sinon le `git merge` suivant pourrait refuser de toucher un fichier
modifié localement). Garde-fou de fraîcheur : si la version HEAD date de plus
de MAX_AGE_HEURES (6 h, horodatage interne du fichier), on committe quand
même — les champs volatils ne vieillissent jamais plus de 6 h dans git.

Rien d'autre n'est touché : tout fichier hors PROFILS, ou illisible, ou dont
le contenu utile change, part dans le commit comme avant. Désactivable sans
code : variable de dépôt JSON_CHURN=off.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

MAX_AGE_HEURES = float(os.environ.get("JSON_CHURN_MAX_AGE_H", "6"))

PROFILS = {
    "kalshi_markets.json": {
        "racine": ("updated_at", "count", "actifs"),
        "liste": "markets", "element": (),
        "horodatage": "updated_at",
    },
    "polymarket_markets.json": {
        "racine": ("updated_at", "count", "actifs"),
        "liste": "markets", "element": ("liquidity", "volume", "discovered_at"),
        "horodatage": "updated_at",
    },
    "resultats_derived.json": {
        "racine": ("updated", "generated_at"),
        "liste": None, "element": (),
        "horodatage": "generated_at",
    },
}


def normalise(nom, obj):
    """Copie de `obj` sans les champs volatils du profil `nom`."""
    prof = PROFILS[nom]
    if not isinstance(obj, dict):
        return obj
    out = {k: v for k, v in obj.items() if k not in prof["racine"]}
    cle = prof["liste"]
    if cle and isinstance(out.get(cle), list):
        out[cle] = [{k: v for k, v in e.items() if k not in prof["element"]}
                    if isinstance(e, dict) else e for e in out[cle]]
    return out


def _parse_ts(v):
    try:
        t = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def seulement_volatil(nom, avant, apres, maintenant=None):
    """True si `apres` ne diffère de `avant` que par des champs volatils ET
    que `avant` n'est pas plus vieux que MAX_AGE_HEURES."""
    if nom not in PROFILS or not isinstance(avant, dict) or not isinstance(apres, dict):
        return False
    if normalise(nom, avant) != normalise(nom, apres):
        return False
    ts = _parse_ts(avant.get(PROFILS[nom]["horodatage"]))
    if ts is None:
        return False                     # pas d'horodatage fiable : on committe
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    return (maintenant - ts) < dt.timedelta(hours=MAX_AGE_HEURES)


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _json_de(ref_chemin):
    r = _git("show", ref_chemin)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def gate(maintenant=None):
    if os.environ.get("JSON_CHURN", "on").lower() == "off":
        print("json_churn — désactivé (JSON_CHURN=off).")
        return 0
    staged = _git("diff", "--cached", "--name-only", "--diff-filter=M").stdout.split()
    retires = []
    for chemin in staged:
        nom = os.path.basename(chemin)
        if nom not in PROFILS or os.path.dirname(chemin):
            continue
        avant, apres = _json_de(f"HEAD:{chemin}"), _json_de(f":{chemin}")
        if seulement_volatil(nom, avant, apres, maintenant):
            _git("restore", "--staged", "--worktree", "--", chemin)
            retires.append(chemin)
    if retires:
        print(f"json_churn — {len(retires)} fichier(s) retiré(s) du commit (seuls des "
              f"champs volatils avaient changé) : {', '.join(retires)}")
    else:
        print("json_churn — rien à retirer.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "gate":
        sys.exit(gate())
    print(__doc__)
    sys.exit(2)
