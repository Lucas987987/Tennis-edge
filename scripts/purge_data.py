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
import os, json, glob, datetime, re, unicodedata

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


def _bad_pair(oh, oa):
    return not (oh and oa and oh > 1 and oa > 1 and (1/oh + 1/oa) <= 1.35)


def purge_corrupt_quotes_flat(path):
    """Fichiers 'courbe' (home_curve/away_curve alignés point à point) :
    book_curves.jsonl, set1_curves.jsonl, set2_curves.jsonl (historique permanent).
    Retire les POINTS dont la marge implicite est déraisonnable (>35%) -- signature
    d'un mauvais parsing (ex. bug betfair-ex : prix lay pris pour un prix back,
    marge ~94%). On ne jette que les points fautifs, pas toute la courbe."""
    if not os.path.exists(path):
        return
    kept_lines, fixed, dropped_pts = [], 0, 0
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            kept_lines.append(line)
            continue
        h, a = r.get('home_curve') or [], r.get('away_curve') or []
        if len(h) != len(a):
            kept_lines.append(json.dumps(r, ensure_ascii=False))
            continue
        nh, na = [], []
        for ph, pa in zip(h, a):
            oh, oa = ph[1], pa[1]
            if _bad_pair(oh, oa):
                dropped_pts += 1
            else:
                nh.append(list(ph)); na.append(list(pa))   # conserve la limite si presente
        if len(nh) != len(h):
            fixed += 1
        if nh:
            r['home_curve'], r['away_curve'] = nh, na
            kept_lines.append(json.dumps(r, ensure_ascii=False))
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(kept_lines) + ("\n" if kept_lines else ""))
    if fixed or dropped_pts:
        print(f"  {path}: {fixed} courbes nettoyées, {dropped_pts} points corrompus retirés "
              f"(marge implicite >35%)")
    else:
        print(f"  {path}: rien à nettoyer")


def purge_corrupt_quotes_parts(pattern='parts/live_*.jsonl'):
    """Fichiers PARTITION (événement par ligne : t/uid/book/ho/ao) -- la source
    réelle des courbes live (les fichiers plats sont régénérés depuis elles à
    chaque cycle, donc les nettoyer directement serait sans effet)."""
    total_dropped = 0
    for path in sorted(glob.glob(pattern)):
        kept, dropped = [], 0
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                kept.append(line); continue
            if _bad_pair(e.get('ho'), e.get('ao')):
                dropped += 1
            else:
                kept.append(json.dumps(e, ensure_ascii=False))
        if dropped:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("\n".join(kept) + ("\n" if kept else ""))
            total_dropped += dropped
    if total_dropped:
        print(f"  {pattern}: {total_dropped} points corrompus retirés des partitions "
              f"(marge implicite >35%)")
    else:
        print(f"  {pattern}: rien à nettoyer")


def purge_old_partitions(days=None, pattern_dir='parts'):
    """Rétention RÉELLE des courbes live : supprime les fichiers de PARTITION
    (parts/live_<market>_<YYYY-MM-DD>.jsonl) plus vieux que `days`, en se basant
    sur la date dans le NOM du fichier (jour de capture des points qu'il
    contient -- pas le commence_time des matchs, une partition peut mélanger
    plusieurs matchs).
    Purger les fichiers PLATS (book_curves_live.jsonl etc.) ne sert à rien :
    ils sont entièrement régénérés à chaque cycle depuis les partitions
    (curves_parts.py rebuild), donc une purge sur le plat serait effacée au
    prochain rebuild. C'est ICI, sur parts/, que la rétention doit s'appliquer
    -- ce sont ces fichiers qui s'accumulent et sont commités dans git."""
    days = LIVE_DAYS if days is None else days
    cutoff_day = (now - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    removed, kept_size = 0, 0
    for path in glob.glob(os.path.join(pattern_dir, 'live_*_*.jsonl')):
        base = os.path.basename(path)
        # live_<market>_<YYYY-MM-DD>.jsonl -> extraire les 10 derniers car. utiles
        day = base.rsplit('_', 1)[-1].replace('.jsonl', '')
        if len(day) == 10 and day < cutoff_day:
            os.remove(path)
            removed += 1
        else:
            kept_size += os.path.getsize(path)
    print(f"  {pattern_dir}/: {removed} partition(s) supprimée(s) (jour < {cutoff_day}) "
          f"| {kept_size/1e6:.1f} Mo conservés")


def main():
    print(f"Rétention @ {now.isoformat()}Z "
          f"(live {LIVE_DAYS}j · historique {HIST_DAYS}j · clv {CLV_DAYS}j · closing {CLOSING_DAYS}j)")
    purge_old_partitions()
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
    # Nettoyage des cotes corrompues (marge implicite >35%, ex. bug betfair-ex) :
    # sur les PARTITIONS (source réelle des données live) + l'historique permanent.
    purge_corrupt_quotes_parts()
    for f in sorted(glob.glob('book_curves.jsonl') + glob.glob('set[12]_curves.jsonl')):
        purge_corrupt_quotes_flat(f)
    total = sum(os.path.getsize(f) for f in glob.glob('*.json*') if os.path.isfile(f))
    print(f"✅ total fichiers de données : {total/1e6:.1f} Mo")


if __name__ == '__main__':
    main()
