#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
opening_efficiency.py — La ligne d'OUVERTURE Pinnacle est-elle battable ?

PRE-ENREGISTREMENT (2026-06-12).

Depuis la passe etendue (12/06), les ouvertures sont captees des que Pinnacle
ouvre la ligne (J-2..J-4). Deux questions :

  O1 CLV MECANIQUE DE L'OUVERTURE (pas besoin de resultats) :
     si on "pariait" aveuglement chaque ouverture, quel CLV vs la cloture
     devigee ? Strategies : toujours le FAVORI d'ouverture / toujours
     l'OUTSIDER d'ouverture. Un CLV moyen significativement positif d'un cote
     = biais systematique de l'ouvreur (favorite-longshot ou autre).
     Decoupe par ANCIENNETE de l'ouverture (>24h, 6-24h, <6h avant le match) :
     les opens precoces sont-ils plus battables ?

  O2 CALIBRATION FAVORI/OUTSIDER A LA CLOTURE (resultats requis) :
     taux realise vs proba de cloture par tranche de proba (50-60/60-75/>75) —
     le favorite-longshot bias classique, mesure sur NOS donnees.

clv_pct(cote) = cote_ouverture / juste_prix_cloture - 1 (>0 = l'open battait la cloture).
Garde-fou n >= MIN_N (30) ; [DIR] en dessous.
Sources : CLV_FILE=clv_history.jsonl  RESULTS=resultats_oddspapi.json (optionnel pour O2)
"""
import json, os, sys, datetime, statistics as st

CLV_FILE = os.environ.get('CLV_FILE', 'clv_history.jsonl')
RESULTS  = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N    = int(os.environ.get('MIN_N', '30'))
LEAD_BUCKETS = [(24, 10**6, 'open >24h avant'), (6, 24, 'open 6-24h avant'), (0, 6, 'open <6h avant')]
P_BUCKETS = [(0.50, 0.60, '50-60%'), (0.60, 0.75, '60-75%'), (0.75, 1.01, '>75%')]


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def devig(o_self, o_other):
    try:
        a, b = 1.0 / float(o_self), 1.0 / float(o_other)
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def tag(n):
    return '' if n >= MIN_N else ' [DIR]'


def main():
    if not os.path.exists(CLV_FILE):
        print(f"❌ {CLV_FILE} manquant"); sys.exit(0)
    results = {}
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding='utf-8') as f:
            results = json.load(f)

    rows, seen = [], set()
    with open(CLV_FILE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            fid = str(e.get('fixture_id') or '')
            if not fid or fid in seen:
                continue
            seen.add(fid)
            hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
            if not all(hm.get(k) for k in ('open', 'close')) or not all(am.get(k) for k in ('open', 'close')):
                continue
            start = parse_dt(e.get('commence_time'))
            first = parse_dt(hm.get('first_t'))
            lead_h = (start - first).total_seconds() / 3600.0 if (start and first) else None
            # favori D'OUVERTURE
            fav = 'home' if hm['open'] <= am['open'] else 'away'
            fm, dm = (hm, am) if fav == 'home' else (am, hm)
            p_fav_close = devig(fm['close'], dm['close'])
            if p_fav_close is None:
                continue
            fair_fav = 1.0 / p_fav_close
            fair_dog = 1.0 / (1.0 - p_fav_close)
            r = results.get(fid)
            won_fav = None
            if r and not r.get('void') and r.get('winner'):
                won_fav = 1 if ((r['winner'] == 'home') == (fav == 'home')) else 0
            rows.append({
                'lead_h': lead_h,
                'clv_fav': fm['open'] / fair_fav - 1.0,    # >0 : ouverture favori battait la cloture
                'clv_dog': dm['open'] / fair_dog - 1.0,
                'p_fav_close': p_fav_close,
                'won_fav': won_fav,
            })

    print(f"=== opening_efficiency — {len(rows)} matchs (open+close des 2 cotes) ===")
    print(f"(exploration pre-enregistree 2026-06-12 — [DIR] = n<{MIN_N})\n")
    if not rows:
        return

    # O1 — CLV mecanique de l'ouverture
    print("── O1 CLV DE L'OUVERTURE vs cloture devigee (mecanique) ─────")
    def o1_line(label, g):
        if not g:
            print(f"  {label:<18} n=0"); return
        n = len(g)
        cf = [r['clv_fav'] for r in g]
        cd = [r['clv_dog'] for r in g]
        print(f"  {label:<18} n={n:<4} favori: {st.mean(cf):+.1%} (med {st.median(cf):+.1%})"
              f" | outsider: {st.mean(cd):+.1%} (med {st.median(cd):+.1%}){tag(n)}")
    o1_line('TOUS', rows)
    for lo, hi, lab in LEAD_BUCKETS:
        g = [r for r in rows if r['lead_h'] is not None and lo <= r['lead_h'] < hi]
        o1_line(lab, g)
    print("  >0 = parier ce cote a l'ouverture battait la cloture (CLV positif systematique")
    print("  = biais de l'ouvreur). ~0 des deux cotes = l'ouvreur est deja efficient.")

    # O2 — calibration favori/outsider (favorite-longshot bias)
    dec = [r for r in rows if r['won_fav'] is not None]
    print(f"\n── O2 CALIBRATION favori a la cloture (n={len(dec)} avec resultat) ──")
    for lo, hi, lab in P_BUCKETS:
        g = [r for r in dec if lo <= r['p_fav_close'] < hi]
        if not g:
            continue
        n = len(g)
        wr = sum(r['won_fav'] for r in g) / n
        pc = st.mean(r['p_fav_close'] for r in g)
        print(f"  favori {lab:<7} n={n:<4} realise {wr:.1%} vs close {pc:.1%} (residu {wr - pc:+.1%}){tag(n)}")
    print("  residu >0 sur les gros favoris + <0 sur les petits = favorite-longshot bias")
    print("  (les outsiders sont sur-payes) ; ~0 partout = cloture bien calibree.")


if __name__ == '__main__':
    main()
