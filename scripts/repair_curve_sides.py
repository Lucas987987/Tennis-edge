#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair_curve_sides.py — Reparation ONE-SHOT : courbes home/away inversees.

CONTEXTE (diagnostic 12/06) : les entrees de l'ere The Odds API (avant la
migration v5 du 11/06) ont parfois un ordre home/away different du
participant1/2 OddsPapi. fetch_clv et fetch_book_curves, en recuperant les
courbes OddsPapi (outcome 121 = participant1) pour ces vieux matchs, les ont
rangees sous les noms de l'ANCIEN ordre -> ~50% des entrees v4 ont leurs
courbes inversees (8/43 detectees sur l'echantillon de diagnostic).

REPARATION : pour chaque ligne de clv_history.jsonl et book_curves.jsonl,
on compare les derniers prix pre-match des courbes a l'HISTORY de
closing_lines.json (meme uid) — la capture est la verite terrain de
l'orientation (ses prix et ses noms viennent de la meme reponse API).
  - d_direct = ecart (clv_h vs cap_h) + (clv_a vs cap_a)
  - d_swap   = ecart (clv_a vs cap_h) + (clv_h vs cap_a)
  - si d_swap < 0.5 * d_direct  -> SWAP detecte : on inverse courbes ET metriques
  - si d_direct < 0.5 * d_swap  -> aligne, rien a faire
  - sinon -> ambigu : non modifie, marque side_check='ambiguous'
Chaque ligne traitee recoit side_check ('ok'/'repaired'/'ambiguous'/'no_ref')
pour ne JAMAIS re-traiter et pour permettre aux etudes d'exclure les ambigus.

Sauvegardes .bak ecrites avant modification. A lancer UNE fois.
"""
import json, os, datetime, shutil

CLOSING  = os.environ.get('CLOSING', 'closing_lines.json')
TARGETS  = [t for t in os.environ.get('TARGETS', 'clv_history.jsonl,book_curves.jsonl').split(',') if t.strip()]
RATIO    = 0.5   # d_swap doit etre < RATIO * d_direct pour declarer un swap


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def last_pre_curve(curve, start):
    best_t, best_p = None, None
    for t, p in (curve or []):
        dt = parse_dt(t)
        if dt is None or (start is not None and dt > start):
            continue
        if best_t is None or dt > best_t:
            best_t, best_p = dt, float(p)
    return best_p


def cap_reference(closing):
    """uid -> (cap_home_close, cap_away_close, start) depuis l'history de la capture."""
    ref = {}
    for uid, e in closing.items():
        if not isinstance(e, dict):
            continue
        start = parse_dt(e.get('commence_time'))
        hist = [p for p in (e.get('history') or [])
                if p.get('mins_before') is not None and p['mins_before'] >= 0
                and p.get('home') and p.get('away')]
        if len(hist) < 2:
            continue
        ref[uid] = (float(hist[-1]['home']), float(hist[-1]['away']), start)
    return ref


def swap_entry(e):
    """Inverse courbes ET metriques home<->away (les noms restent : c'etaient eux la verite)."""
    for a, b in (('home_curve', 'away_curve'), ('home_metrics', 'away_metrics')):
        e[a], e[b] = e.get(b), e.get(a)


def repair_file(path, ref):
    if not os.path.exists(path):
        print(f"  (absent: {path})"); return
    lines = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    counts = {'ok': 0, 'repaired': 0, 'ambiguous': 0, 'no_ref': 0, 'already': 0}
    for e in lines:
        if e.get('side_check'):
            counts['already'] += 1
            continue
        uid = e.get('uid')
        r = ref.get(uid)
        ch = last_pre_curve(e.get('home_curve'), r[2] if r else None) if r else None
        ca = last_pre_curve(e.get('away_curve'), r[2] if r else None) if r else None
        if not r or not ch or not ca:
            e['side_check'] = 'no_ref'
            counts['no_ref'] += 1
            continue
        cap_h, cap_a, _ = r
        d_direct = abs(ch - cap_h) / cap_h + abs(ca - cap_a) / cap_a
        d_swap = abs(ca - cap_h) / cap_h + abs(ch - cap_a) / cap_a
        if d_swap < RATIO * d_direct:
            swap_entry(e)
            e['side_check'] = 'repaired'
            counts['repaired'] += 1
            print(f"  🔁 SWAP repare: {uid} (cap {cap_h}/{cap_a} | courbes {ch}/{ca})")
        elif d_direct < RATIO * d_swap:
            e['side_check'] = 'ok'
            counts['ok'] += 1
        else:
            e['side_check'] = 'ambiguous'
            counts['ambiguous'] += 1
            print(f"  ⚠️ ambigu (non modifie): {uid}")
    shutil.copy(path, path + '.bak')
    with open(path, 'w', encoding='utf-8') as f:
        for e in lines:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    print(f"  {path}: {counts['ok']} ok | {counts['repaired']} repares | "
          f"{counts['ambiguous']} ambigus | {counts['no_ref']} sans ref | {counts['already']} deja traites")


def main():
    if not os.path.exists(CLOSING):
        print(f"❌ {CLOSING} manquant"); return
    with open(CLOSING, encoding='utf-8') as f:
        closing = json.load(f)
    ref = cap_reference(closing)
    print(f"Reference capture : {len(ref)} matchs avec history exploitable\n")
    for path in TARGETS:
        print(f"── {path}")
        repair_file(path.strip(), ref)
    print("\nFait. Les .bak peuvent etre supprimes apres verification.")
    print("Relancer ensuite 'Etudes Mouvement' : les cases dependant du cote steame")
    print("(gros move, asymetrie, set1) vont BOUGER — c'est attendu et c'est la correction.")


if __name__ == '__main__':
    main()
