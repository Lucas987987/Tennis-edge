#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
curves_parts.py — Partitionnement append-only des courbes live.

PROBLÈME RÉSOLU
Les fichiers *_curves_live.jsonl étaient RÉÉCRITS entièrement à chaque cycle
(toutes les 8-10 min). Git stocke un nouveau blob complet à chaque réécriture :
~24 Mo × 150 cycles/jour, soit des Go d'historique par semaine. Résultat :
checkout/push de plus en plus lents, runs qui dépassent la cadence, file
d'attente qui s'empile, échecs en cascade.

SOLUTION
Les points sont désormais ajoutés (append) dans des partitions quotidiennes :
    parts/live_<market>_YYYY-MM-DD.jsonl
Un append en fin de fichier se stocke en delta très compact côté Git, et les
partitions des jours passés ne changent plus jamais. Le fichier plat
(*_curves_live.jsonl) est reconstruit au début de chaque run et n'est plus
commité (il est régénérable, donc dans .gitignore).

AUCUNE PERTE : les partitions contiennent exactement les mêmes points, et
rebuild() reconstitue un fichier identique en contenu.

Usage :
    python scripts/curves_parts.py rebuild      # avant build_live_curves
    (l'append est fait automatiquement par build_live_curves)
"""
import os, json, glob, sys
from datetime import datetime, timedelta

PARTS_DIR   = os.environ.get('PARTS_DIR', 'parts')
RETAIN_DAYS = float(os.environ.get('RETAIN_DAYS', '10'))
# marché -> fichier plat attendu par les scripts consommateurs
MARKETS = {
    'match': os.environ.get('OUT_MATCH', 'book_curves_live.jsonl'),
    'set1':  os.environ.get('OUT_SET1',  'set1_curves_live.jsonl'),
    'set2':  os.environ.get('OUT_SET2',  'set2_curves_live.jsonl'),
}


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def part_path(market, day=None):
    day = day or datetime.utcnow().strftime('%Y-%m-%d')
    os.makedirs(PARTS_DIR, exist_ok=True)
    return os.path.join(PARTS_DIR, f"live_{market}_{day}.jsonl")


def append(market, events):
    """events : liste de dicts {t, uid, book, ho, ao, commence_time, home, away, tournament}.
    Écrit en fin de partition du jour (jamais de réécriture)."""
    if not events:
        return 0
    path = part_path(market)
    with open(path, 'a', encoding='utf-8') as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    return len(events)


def rebuild(market, out_file=None, retain_days=None):
    """Reconstitue le fichier plat depuis toutes les partitions du marché.

    ÉCHEC BRUYANT SI AUCUNE PARTITION — AJOUTÉ LE 13/09/2026.

    Jusqu'ici, zéro partition produisait un fichier plat VIDE, un retour 0,
    et aucune erreur. Le pipeline enchaînait sur des courbes vides : pas
    d'alerte émise, pas de CLV mesurable, et rien dans les logs pour dire
    que la fenêtre d'entrée avait disparu. C'est le mode de panne le plus
    coûteux du projet -- le même que le canal, où une source tronquée
    donnait un « 0 % » qui ressemblait à un résultat.

    Un fichier plat vide n'est jamais un état légitime en production : les
    partitions sont écrites à chaque cycle de capture. Zéro partition veut
    dire que quelque chose a disparu (purge trop agressive, checkout
    incomplet, cache non restauré), pas que le marché est calme.

    AUTORISER_VIDE=1 pour les cas légitimes : premier démarrage, tests,
    rejeu sur un dépôt neuf.
    """
    out_file = out_file or MARKETS.get(market, f"{market}_curves_live.jsonl")
    retain = RETAIN_DAYS if retain_days is None else retain_days
    motif = os.path.join(PARTS_DIR, f"live_{market}_*.jsonl")
    n_parts = len(glob.glob(motif))
    if n_parts == 0 and os.environ.get('AUTORISER_VIDE', '') != '1':
        raise SystemExit(
            f"❌ rebuild({market}) : AUCUNE partition {motif}.\n"
            f"   Le fichier plat serait vide et le pipeline tournerait sur\n"
            f"   des courbes inexistantes sans le signaler. Arrêt.\n"
            f"   Causes usuelles : cache non restauré, checkout partiel,\n"
            f"   purge trop agressive (LIVE_DAYS).\n"
            f"   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.")
    now = datetime.utcnow()
    cutoff = now - timedelta(days=retain)
    curves, n_pts = {}, 0
    for path in sorted(glob.glob(os.path.join(PARTS_DIR, f"live_{market}_*.jsonl"))):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            ct = _dt(e.get('commence_time'))
            if ct and ct < cutoff:
                continue                      # match trop ancien : hors rétention
            key = (e.get('uid'), e.get('book'))
            if not key[0] or not key[1]:
                continue
            c = curves.get(key)
            if c is None:
                c = {'uid': e['uid'], 'book': e['book'],
                     'commence_time': e.get('commence_time'),
                     'home': e.get('home'), 'away': e.get('away'),
                     'tournament': e.get('tournament'),
                     'home_curve': [], 'away_curve': []}
                curves[key] = c
            t, ho, ao = e.get('t'), e.get('ho'), e.get('ao')
            if t and ho and ao:
                c['home_curve'].append([t, ho])
                c['away_curve'].append([t, ao])
                n_pts += 1
    # tri chronologique (les partitions sont déjà ordonnées, ceci garantit l'invariant)
    for c in curves.values():
        c['home_curve'].sort(key=lambda p: p[0])
        c['away_curve'].sort(key=lambda p: p[0])
    with open(out_file, 'w', encoding='utf-8') as f:
        for c in curves.values():
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    print(f"  {out_file}: {len(curves)} courbes reconstruites | {n_pts} points "
          f"| {n_parts} partitions")
    # Des partitions présentes mais aucun point exploitable : autre symptôme
    # du même mal (partitions tronquées, format inattendu). On refuse aussi.
    if n_pts == 0 and n_parts > 0 and os.environ.get('AUTORISER_VIDE', '') != '1':
        raise SystemExit(
            f"❌ rebuild({market}) : {n_parts} partition(s) lue(s), 0 point "
            f"retenu.\n   Partitions tronquées ou hors fenêtre de rétention "
            f"({retain} j). Arrêt.")
    return len(curves)


def migrate(market, flat_file=None):
    """Migration UNE FOIS : convertit un fichier plat existant en partitions,
    réparties par date réelle de chaque point. Idempotent si relancé sur un plat vide."""
    flat_file = flat_file or MARKETS.get(market)
    if not flat_file or not os.path.exists(flat_file):
        print(f"  {market}: pas de fichier plat à migrer")
        return 0
    by_day = {}
    for line in open(flat_file, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        away = {p[0]: p[1] for p in e.get('away_curve', [])}
        for pt in e.get('home_curve', []):
            t, ho = pt[0], pt[1]
            ao = away.get(t)
            if not ao:
                continue
            day = str(t)[:10]
            by_day.setdefault(day, []).append({
                't': t, 'uid': e.get('uid'), 'book': e.get('book'),
                'ho': ho, 'ao': ao, 'commence_time': e.get('commence_time'),
                'home': e.get('home'), 'away': e.get('away'),
                'tournament': e.get('tournament')})
    total = 0
    os.makedirs(PARTS_DIR, exist_ok=True)
    for day, evs in sorted(by_day.items()):
        evs.sort(key=lambda x: x['t'])
        with open(part_path(market, day), 'w', encoding='utf-8') as f:
            for e in evs:
                f.write(json.dumps(e, ensure_ascii=False) + '\n')
        total += len(evs)
    print(f"  {market}: {total} points migrés vers {len(by_day)} partitions")
    return total


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'rebuild'
    only = sys.argv[2] if len(sys.argv) > 2 else None
    markets = [only] if only else list(MARKETS)
    if cmd == 'migrate':
        print("Migration des fichiers plats vers les partitions :")
        for m in markets:
            migrate(m)
    else:
        print("Reconstruction des fichiers plats depuis les partitions :")
        for m in markets:
            rebuild(m)
