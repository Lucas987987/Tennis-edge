#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
purge_data.py — Rétention des données : garde le repo léger et les runs rapides.

Problème résolu : les fichiers de courbes sont réécrits ENTIÈREMENT à chaque
cycle (toutes les 8-10 min). Git stocke un blob complet à chaque écriture, donc
un fichier de 11 Mo réécrit 150 fois par jour = plusieurs Go d'historique par
semaine. Résultat : checkout/push de plus en plus lents, runs qui dépassent la
cadence, file d'attente qui s'empile, échecs en cascade.

Politique (jours, réglables par env) :
  • *_curves_live.jsonl  -> LIVE_DAYS (5)   : ne servent qu'aux matchs à venir
  • book_curves.jsonl et set*_curves.jsonl -> HIST_DAYS (90) : = fenêtre de
    calibration des seuils, donc aucune perte analytique
  • clv_history.jsonl    -> CLV_DAYS (60)
  • closing_lines.json   -> CLOSING_DAYS (45), par commence_time
  • canal_public_log.jsonl, paper_trades_*.jsonl : JAMAIS purgés (track record)

Usage : python scripts/purge_data.py   (une fois par jour dans le pipeline)
"""
import os, json, glob, datetime

LIVE_DAYS    = int(os.environ.get('LIVE_DAYS', '3'))
HIST_DAYS    = int(os.environ.get('HIST_DAYS', '0'))   # 0 = jamais purgé
CLV_DAYS     = int(os.environ.get('CLV_DAYS', '0'))    # 0 = jamais purgé
CLOSING_DAYS = int(os.environ.get('CLOSING_DAYS', '60'))

now = datetime.datetime.utcnow()


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def purge_jsonl(path, days, date_field='commence_time'):
    if not os.path.exists(path):
        return
    cut = now - datetime.timedelta(days=days)
    before = os.path.getsize(path)
    kept, dropped = [], 0
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            kept.append(line)          # ligne illisible : on ne jette pas
            continue
        d = _dt(r.get(date_field)) or _dt(r.get('t'))
        if d is None or d >= cut:
            kept.append(line)
        else:
            dropped += 1
    if not dropped:
        print(f"  {path}: rien à purger ({before/1e6:.1f} Mo)")
        return
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write("\n".join(kept) + ("\n" if kept else ""))
    os.replace(tmp, path)
    after = os.path.getsize(path)
    print(f"  {path}: -{dropped} lignes | {before/1e6:.1f} -> {after/1e6:.1f} Mo "
          f"(-{100*(before-after)/max(before,1):.0f}%)")


def purge_closing(path=  'closing_lines.json', days=None):
    days = days or CLOSING_DAYS
    if not os.path.exists(path):
        return
    cut = now - datetime.timedelta(days=days)
    before = os.path.getsize(path)
    try:
        data = json.load(open(path, encoding='utf-8'))
    except Exception:
        print(f"  {path}: illisible, ignoré"); return
    keep = {}
    for uid, m in data.items():
        d = _dt((m or {}).get('commence_time'))
        if d is None or d >= cut:
            keep[uid] = m
    dropped = len(data) - len(keep)
    if not dropped:
        print(f"  {path}: rien à purger ({len(data)} matchs)")
        return
    json.dump(keep, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    after = os.path.getsize(path)
    print(f"  {path}: -{dropped} matchs | {before/1e6:.1f} -> {after/1e6:.1f} Mo")


def main():
    print(f"Rétention @ {now.isoformat()}Z "
          f"(live {LIVE_DAYS}j · historique {HIST_DAYS}j · clv {CLV_DAYS}j · closing {CLOSING_DAYS}j)")
    for f in sorted(glob.glob('*_curves_live.jsonl')):
        purge_jsonl(f, LIVE_DAYS)
    if HIST_DAYS > 0:
        for f in sorted(glob.glob('book_curves.jsonl') + glob.glob('set[12]_curves.jsonl')):
            purge_jsonl(f, HIST_DAYS)
    else:
        print("  historique (book_curves/set*_curves) : conservé intégralement")
    if CLV_DAYS > 0:
        purge_jsonl('clv_history.jsonl', CLV_DAYS)
    else:
        print("  clv_history.jsonl : conservé intégralement")
    purge_closing()
    total = sum(os.path.getsize(f) for f in glob.glob('*.json*') if os.path.isfile(f))
    print(f"✅ total fichiers de données : {total/1e6:.1f} Mo")


if __name__ == '__main__':
    main()
