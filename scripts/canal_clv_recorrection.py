#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canal_clv_recorrection.py — Réécrit `canal_clv_detail.csv` avec les
clôtures recalculées (décision du 13/09/2026).

POURQUOI ON ROUVRE UN REGISTRE QUI NE DEVAIT JAMAIS L'ÊTRE
La règle « on n'y retouche JAMAIS » existe pour empêcher de réécrire
l'histoire après avoir vu les résultats. Elle suppose que les valeurs gelées
sont justes. Ce n'était pas le cas : la cascade de sources d'avant le
13/09/2026 retenait le PREMIER résultat trouvé, donc une fenêtre `live`
tronquée l'emportait sur une courbe complète. 62 lignes sur les 165
recalculables portent une clôture qui n'est pas la dernière d'avant-match.

Le registre sert de base d'analyse (taux de refermeture, CLV médian,
baromètres). L'analyser sur 38 % de valeurs fausses n'a pas de sens. Le
fichier d'origine est archivé, daté et versionné : la correction est
traçable, pas silencieuse.

CE QUE CE SCRIPT NE FAIT PAS
Il ne touche ni à `prix_signale`, ni à `date`, ni à `uid`, ni à `book` :
l'alerte publiée reste ce qu'elle était. Seule la MESURE de clôture est
recalculée, avec le CLV qui en découle.

Env : LEDGER, ARCHIVE_AVANT, CURVES, EPS (0.005), DRY_RUN=1
"""
import csv
import datetime
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov            # noqa: E402

LEDGER = os.environ.get('LEDGER', 'canal_clv_detail.csv')
ARCHIVE_AVANT = os.environ.get(
    'ARCHIVE_AVANT', 'canal_clv_detail_avant_correction_2026-09-13.csv')
CURVES = [c.strip() for c in os.environ.get(
    'CURVES', 'book_curves_live.jsonl,book_curves.jsonl').split(',') if c.strip()]
EPS = float(os.environ.get('EPS', '0.005'))
DRY = os.environ.get('DRY_RUN', '') == '1'

# colonnes ajoutées par la correction
COL_STATUT = 'statut_verif'
COL_ANCIENNE = 'cloture_avant_correction'
COL_DATE = 'corrige_le'


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(
            str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def load_closes():
    """Dernier point pré-match, source la plus TARDIVE (cascade corrigée)."""
    closes = {}
    for src in CURVES:
        try:
            lignes = ov.open_curves(src, verbose=False)
        except Exception:
            continue
        for line in lignes:
            line = line.strip() if isinstance(line, str) else line
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            ct = _dt(r.get('commence_time'))
            if not ct:
                continue
            home = r.get('home_team') or r.get('home') or ''
            away = r.get('away_team') or r.get('away') or ''
            for key, name in (('home_curve', home), ('away_curve', away)):
                pts = [(_dt(p[0]), p[1]) for p in (r.get(key) or [])
                       if _dt(p[0]) and p[1] and p[1] > 1]
                pts = sorted(p for p in pts if p[0] < ct)
                if pts and name:
                    k = (r.get('uid'), r.get('book'), name)
                    if k not in closes or pts[-1][0] > closes[k][1]:
                        closes[k] = (pts[-1][1], pts[-1][0])
    return closes


def main():
    if not os.path.exists(LEDGER):
        print(f"{LEDGER} introuvable"); return 1
    with open(LEDGER, encoding='utf-8-sig', newline='') as f:
        lecteur = csv.DictReader(f)
        champs = list(lecteur.fieldnames or [])
        rows = list(lecteur)
    if not rows:
        print("registre vide"); return 1

    # idempotence : si la correction a déjà eu lieu, on ne rejoue pas
    if COL_STATUT in champs:
        deja = sum(1 for r in rows if r.get(COL_DATE))
        print(f"correction déjà appliquée sur {deja} ligne(s) — rien à faire.")
        return 0

    closes = load_closes()
    aujourdhui = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    n_corr = n_conf = n_nv = 0

    for r in rows:
        r[COL_ANCIENNE] = ''
        r[COL_DATE] = ''
        try:
            prix = float(r['prix_signale']); cl_gel = float(r['cloture'])
        except Exception:
            r[COL_STATUT] = 'non verifiable'; n_nv += 1
            continue
        got = closes.get((r['uid'], r['book'], r['joueur']))
        if not got:
            r[COL_STATUT] = 'non verifiable'; n_nv += 1
            continue
        cl_vrai = got[0]
        if abs(cl_vrai - cl_gel) <= EPS:
            r[COL_STATUT] = 'confirmee'; n_conf += 1
            continue
        # correction effective
        r[COL_ANCIENNE] = f"{cl_gel:g}"
        r['cloture'] = f"{cl_vrai:g}"
        r['clv'] = f"{round((prix / cl_vrai - 1) * 100, 1):g}"
        r[COL_STATUT] = 'corrigee'
        r[COL_DATE] = aujourdhui
        n_corr += 1

    print(f"registre : {len(rows)} lignes")
    print(f"  corrigées      : {n_corr}")
    print(f"  confirmées     : {n_conf}")
    print(f"  non vérifiables: {n_nv}")

    if DRY:
        print("\n(DRY_RUN : aucun fichier écrit)")
        return 0

    # archive du fichier d'origine — la correction doit rester traçable
    if not os.path.exists(ARCHIVE_AVANT):
        shutil.copy2(LEDGER, ARCHIVE_AVANT)
        print(f"\n→ original archivé : {ARCHIVE_AVANT}")
    else:
        print(f"\n→ archive déjà présente : {ARCHIVE_AVANT} (non écrasée)")

    champs_out = champs + [COL_STATUT, COL_ANCIENNE, COL_DATE]
    tmp = LEDGER + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=champs_out, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, LEDGER)          # écriture atomique
    print(f"→ {LEDGER} réécrit ({n_corr} clôture(s) corrigée(s)).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
