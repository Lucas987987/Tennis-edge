#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capture_quality.py — Audit du systeme de capture + triangulation des closings.

DIAGNOSTIC (pas une etude de marche) : mesure la sante de la chaine
worker -> capture -> snapshots -> closing, et la BARRE D'ERREUR de mesure du CLV.

  Q1 COUVERTURE DES FENETRES : pour les matchs commences, % ayant chaque
     snapshot t25/t15/t7/t3, % avec closing fiable (reliable), % par disparition.

  Q2 CHAOS DE PROGRAMMATION : les matchs avec schedule_changes>0 perdent-ils
     leurs snapshots plus souvent ? (mesure l'impact reel des reports/decalages)

  Q3 TRIANGULATION DES CLOSINGS : trois sources mesurent le meme closing
     Pinnacle — (A) clv_history (courbe historique), (B) snapshot le plus tardif
     de closing_lines, (C) courbe pinnacle de book_curves. Les ecarts mesures :
       |A-B|, |A-C|, |B-C| en % de cote, par fixture.
     La mediane de ces ecarts = la precision de mesure du CLV. Tout CLV
     inferieur a cette barre est du bruit de mesure, pas du signal.
     (Resout aussi l'anomalie du controle pinnacle de book_asymmetry.)

Sources (lecture seule) : CLOSING=closing_lines.json, CLV_FILE=clv_history.jsonl,
BOOK_FILE=book_curves.jsonl
"""
import json, os, sys, datetime, statistics as st

CLOSING   = os.environ.get('CLOSING', 'closing_lines.json')
CLV_FILE  = os.environ.get('CLV_FILE', 'clv_history.jsonl')
BOOK_FILE = os.environ.get('BOOK_FILE', 'book_curves.jsonl')
SNAPS = ('t25', 't15', 't7', 't3')


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def curve_close(curve_raw, start):
    """(prix, age_min) du dernier point PRE-match d'une courbe brute.
    age_min = minutes entre ce point et le coup d'envoi (la FRAICHEUR de la
    'cloture' vue par cette source — clef du diagnostic de resolution)."""
    best_t, best_p = None, None
    for t, p in (curve_raw or []):
        dt = parse_dt(t)
        if dt is None or (start is not None and dt > start):
            continue
        if best_t is None or dt > best_t:
            best_t, best_p = dt, float(p)
    age = None
    if best_t is not None and start is not None:
        age = (start - best_t).total_seconds() / 60.0
    return best_p, age




def book_curves_aligned(be, ref_home, ref_away):
    """Retourne (home_curve, away_curve) du book ALIGNES sur l'ordre de reference.
    Certaines vieilles lignes de book_curves ont home/away INVERSES (ecrites avant
    le correctif "canonique") : on detecte par les noms et on re-swappe."""
    hc, ac = be.get('home_curve'), be.get('away_curve')
    bh = (be.get('home') or '').strip().lower()
    ba = (be.get('away') or '').strip().lower()
    rh = (ref_home or '').strip().lower()
    ra = (ref_away or '').strip().lower()
    if bh and rh and bh == ra and ba == rh:
        return ac, hc        # swap detecte -> on inverse
    return hc, ac

def main():
    if not os.path.exists(CLOSING):
        print(f"❌ {CLOSING} manquant"); sys.exit(0)
    with open(CLOSING, encoding='utf-8') as f:
        closing = json.load(f)
    now = datetime.datetime.utcnow()

    started = []
    for uid, e in closing.items():
        if not isinstance(e, dict):
            continue
        ct = parse_dt(e.get('commence_time'))
        if ct and ct < now:
            started.append((uid, e))
    print(f"=== capture_quality — {len(closing)} entrees, {len(started)} matchs commences ===\n")
    if not started:
        return

    # Q1 — couverture
    print("── Q1 COUVERTURE DES FENETRES (matchs commences) ────────────")
    n = len(started)
    for lab in SNAPS:
        c = sum(1 for _, e in started if e.get(f'pinnacle_{lab}'))
        print(f"  {lab:<4} {c}/{n} ({c/n:.0%})")
    has_cl = [(u, e) for u, e in started if e.get('closing')]
    rel = sum(1 for _, e in has_cl if (e['closing'] or {}).get('reliable'))
    disp = sum(1 for _, e in has_cl if (e['closing'] or {}).get('closing_method') == 'disappearance')
    all4 = sum(1 for _, e in started if all(e.get(f'pinnacle_{l}') for l in SNAPS))
    print(f"  closing present : {len(has_cl)}/{n} ({len(has_cl)/n:.0%}) | fiable : {rel}/{n} ({rel/n:.0%})"
          f" | par disparition : {disp}")
    print(f"  les 4 snapshots : {all4}/{n} ({all4/n:.0%})")

    # Q2 — chaos de programmation
    print("\n── Q2 CHAOS DE PROGRAMMATION (schedule_changes) ─────────────")
    chg = [(u, e) for u, e in started if e.get('schedule_changes', 0) > 0]
    sta = [(u, e) for u, e in started if not e.get('schedule_changes')]
    for lab, g in (('horaire change', chg), ('horaire stable', sta)):
        if not g:
            print(f"  {lab:<15} n=0"); continue
        snap_ok = sum(1 for _, e in g if any(e.get(f'pinnacle_{l}') for l in SNAPS))
        rel_ok = sum(1 for _, e in g if (e.get('closing') or {}).get('reliable'))
        print(f"  {lab:<15} n={len(g):<4} >=1 snapshot {snap_ok/len(g):.0%} | closing fiable {rel_ok/len(g):.0%}")
    if chg:
        dist = {}
        for _, e in chg:
            dist[e['schedule_changes']] = dist.get(e['schedule_changes'], 0) + 1
        print("  distribution :", ', '.join(f"{k} chg: {v}" for k, v in sorted(dist.items())))

    # Q3 — triangulation
    print("\n── Q3 TRIANGULATION DES CLOSINGS (A=clv, B=snapshot, C=book_curves pinnacle) ──")
    clv = {}
    if os.path.exists(CLV_FILE):
        with open(CLV_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                clv[str(e.get('fixture_id') or '')] = e
    bookp = {}
    if os.path.exists(BOOK_FILE):
        with open(BOOK_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get('book') == 'pinnacle':
                    bookp[str(e.get('fixture_id') or '')] = e

    diffs = {'A-B': [], 'A-C': [], 'B-C': []}
    ages = {'A': [], 'C': []}
    detail = []
    for uid, e in started:
        fid = str(e.get('fixture_id') or '')
        start = parse_dt(e.get('commence_time'))
        # B : snapshot le plus tardif
        B = None
        cl = e.get('closing') or {}
        if cl.get('home') and cl.get('closing_method') != 'disappearance':
            B = float(cl['home'])
        ce, be = clv.get(fid), bookp.get(fid)
        A = age_A = C = age_C = None
        if ce:
            A, age_A = curve_close(ce.get('home_curve'), start)
        if be:
            b_hc, _ = book_curves_aligned(be, e.get('home'), e.get('away'))
            C, age_C = curve_close(b_hc, start)
        if A and age_A is not None:
            ages['A'].append(age_A)
        if C and age_C is not None:
            ages['C'].append(age_C)
        for k, x, y in (('A-B', A, B), ('A-C', A, C), ('B-C', B, C)):
            if x and y:
                d = abs(x - y) / x * 100.0
                diffs[k].append(d)
                if d > 3.0:
                    detail.append((k, uid, x, y, d))
    for k, lab in (('A-B', 'clv vs snapshot'), ('A-C', 'clv vs book_curves'), ('B-C', 'snapshot vs book_curves')):
        g = diffs[k]
        if g:
            print(f"  {lab:<24} n={len(g):<4} ecart median {st.median(g):.2f}% | moyen {st.mean(g):.2f}% | max {max(g):.2f}%")
        else:
            print(f"  {lab:<24} n=0 (pas de recouvrement)")
    # FRAICHEUR du dernier point pre-match par source : si une source 'cloture'
    # bien plus tot que l'autre (sous-echantillonnage de l'endpoint historique
    # selon la date du fetch), les ecarts de prix sont un artefact de TIMING.
    for k, lab in (('A', 'clv_history'), ('C', 'book_curves pinnacle')):
        g = ages[k]
        if g:
            print(f"  age du dernier point pre-match ({lab}) : median {st.median(g):.0f} min avant le match"
                  f" | p90 {sorted(g)[int(len(g)*0.9)]:.0f} min (n={len(g)})")
    if detail:
        print(f"  ⚠️ {len(detail)} ecarts > 3% (a inspecter) :")
        for k, uid, x, y, d in detail[:8]:
            print(f"    [{k}] {uid}: {x} vs {y} ({d:.1f}%)")

    print("\nLecture :")
    print(" - Q3 : la mediane des ecarts = la precision de mesure du CLV. Tout CLV sous")
    print("   cette barre est indistinguable du bruit de mesure.")
    print(" - un ecart A-C systematique explique l'anomalie du controle pinnacle de")
    print("   book_asymmetry (les deux sources ne voient pas le meme closing).")


if __name__ == '__main__':
    main()
