#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_markets.py (v5) — étiquette les marchés d'un match via le timing d'activation.
Pour chaque marché : #issues, #points, et QUAND il s'active vs le coup d'envoi
(commence_time). Les marchés dont le 1er point arrive APRÈS le début = in-play
(ex. set 2 = marketId 125). Sert à vérifier le timing "fin de set 1".

USAGE (Actions, secret RAPIDAPI_KEY) :
    FIXTURE_ID=pn129... COMMENCE=2026-06-11T09:00:00Z BOOKMAKER=pinnacle python scripts/probe_markets.py
COMMENCE auto-cherché dans book_curves.jsonl / matches_oddspapi.json / closing_lines.json si absent.
"""
import os, sys, json, datetime
import oddspapi_v5 as ov


def parse(ts):
    try:
        return datetime.datetime.fromisoformat((ts or '').replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def find_commence(fid):
    # book_curves.jsonl
    p = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            try:
                d = json.loads(line)
                if d.get('fixture_id') == fid and d.get('commence_time'):
                    return parse(d['commence_time']), 'book_curves'
            except Exception:
                pass
    # matches_oddspapi.json / closing_lines.json
    for path, idk, ctk in (('matches_oddspapi.json', 'id', 'commence_time'),
                           ('closing_lines.json', None, 'commence_time')):
        if not os.path.exists(path):
            continue
        try:
            obj = json.load(open(path, encoding='utf-8'))
            items = obj if isinstance(obj, list) else obj.values()
            for m in items:
                mid = m.get('id') or m.get('fixture_id')
                if mid == fid and m.get(ctk):
                    return parse(m[ctk]), path
        except Exception:
            pass
    return None, None


def main():
    if not ov.KEY:
        sys.exit("RAPIDAPI_KEY manquant.")
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    fid = args[0] if args else os.environ.get('FIXTURE_ID')
    commence = parse(args[1] if len(args) > 1 else os.environ.get('COMMENCE', ''))
    book = (args[2] if len(args) > 2 else os.environ.get('BOOKMAKER', 'pinnacle')).split(',')[0].strip()
    if not fid:
        sys.exit("FIXTURE_ID manquant.")
    src = 'arg/env'
    if not commence:
        commence, src = find_commence(fid)
    print(f"fixtureId={fid} | book={book} | commence={commence} [{src}]\n")
    timing = ov.historical_market_timing(fid, book)
    if not timing:
        sys.exit("pas d'historique pour ce book.")
    cms = int(commence.timestamp() * 1000) if commence else None
    rows = []
    for mid, d in timing.items():
        off_f = (d['first_ms'] - cms) / 60000 if cms else None
        off_l = (d['last_ms'] - cms) / 60000 if cms else None
        rows.append((mid, d['n_outcomes'], d['n_points'], off_f, off_l))
    rows.sort(key=lambda r: (r[3] if r[3] is not None else 0))
    print(f"  {'marché':>8} {'#iss':>4} {'#pts':>5}  {'1er pt':>9}  {'dernier':>9}  type")
    for mid, no, np_, off_f, off_l in rows:
        ff = f"{off_f:+7.0f}m" if off_f is not None else "   ?  "
        fl = f"{off_l:+7.0f}m" if off_l is not None else "   ?  "
        typ = ""
        if off_f is not None:
            typ = "IN-PLAY" if off_f > 5 else "pré-match"
        print(f"  {str(mid):>8} {no:4d} {np_:5d}  {ff:>9}  {fl:>9}  {typ}")
    print("\nRappel v5 : 121=match · 123=set1 · 125=set2 (les set s'activent en in-play).")


if __name__ == '__main__':
    main()
