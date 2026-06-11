#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
move_vs_set1.py
---------------
Question : le MOUVEMENT de cote pre-match est-il correle au DEROULE du match,
en particulier au gain du 1er SET — au-dela de ce que la cote de cloture
implique deja ?

Cote "steamed" = le joueur dont la cote a RACCOURCI pre-match (move_pct < 0 sur
sa propre cote, courbes Pinnacle nettoyees du in-play). Pour chaque match :
  - taille du raccourcissement (|move_pct| du cote steamed), en tranches ;
  - proba de cloture DEVIGEE du cote steamed (p_close) ;
  - resultat : a-t-il gagne le SET 1 ? le MATCH ?

Lectures attendues si le marche est efficient :
  - MATCH : taux realise ~= p_close dans chaque tranche (residu ~ 0). Un residu
    systematique signerait une sur/sous-correction du move (angle move_vs_outcome).
  - SET 1 : pas de baseline propre depuis la cote match (la proba de set 1 est
    plus proche de 50% que la proba match). On compare donc ENTRE tranches :
    si "plus gros move => set 1 plus souvent", le move encode quelque chose sur
    le debut de match (forme du jour, compo) et pas seulement sur l'issue.
  - Bonus descriptif : taux de comeback (set 1 perdu mais match gagne) par tranche.

GARDE-FOU : n >= MIN_N (30) par tranche pour conclure ; en-dessous = DIRECTIONNEL.
Donnees provisoires (settlement OddsPapi) : exploration seulement, ne valide
jamais le CLV ni un signal — Sackmann confirmera.

Sources (lecture seule, AUCUNE API) :
  CLV_FILE  = clv_history.jsonl        (courbes/metriques Pinnacle par fixture_id)
  RESULTS   = resultats_oddspapi.json  (winner + set1 par fixtureId, settlement)
"""
import json, os, sys

CLV_FILE = os.environ.get('CLV_FILE', 'clv_history.jsonl')
RESULTS  = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N    = int(os.environ.get('MIN_N', '30'))
# Tranches sur |move_pct| du cote steamed (raccourcissement de SA cote, en %)
BUCKETS = [(0.0, 2.0, 'quasi stable (0-2%)'),
           (2.0, 5.0, 'move modere (2-5%)'),
           (5.0, 100.0, 'gros move (>5%)')]


def devig(o_self, o_other):
    """Proba devigee du cote o_self a partir des deux cotes de cloture."""
    try:
        a, b = 1.0 / float(o_self), 1.0 / float(o_other)
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def load_join():
    if not os.path.exists(CLV_FILE) or not os.path.exists(RESULTS):
        print(f"❌ fichier manquant ({CLV_FILE} / {RESULTS})"); sys.exit(1)
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
                continue   # dedup : 1 ligne par fixture (la 1re fait foi)
            seen.add(fid)
            r = results.get(fid)
            if not r or r.get('void') or not r.get('winner'):
                continue
            hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
            if hm.get('move_pct') is None or am.get('move_pct') is None:
                continue
            # cote steamed = celui dont la cote a raccourci. Si les deux ont
            # raccourci/derive (incoherent, bruit de cloture), on prend le plus net.
            cand = [('home', hm, am), ('away', am, hm)]
            side, m_self, m_other = min(cand, key=lambda c: c[1]['move_pct'])
            if m_self['move_pct'] >= 0:
                # personne n'a raccourci (les deux >= 0) -> stable, classe en tranche 0
                pass
            p_close = devig(m_self.get('close'), m_other.get('close'))
            if p_close is None:
                continue
            set1 = r.get('set1')
            rows.append({
                'fid': fid,
                'home': e.get('home'), 'away': e.get('away'),
                'steam_side': side,
                'steam_move': abs(min(m_self['move_pct'], 0.0)),  # % de raccourcissement
                'p_close': p_close,
                'won_match': 1 if r['winner'] == side else 0,
                'won_set1': (1 if set1 == side else 0) if set1 in ('home', 'away') else None,
            })
    return rows


def bucket_of(mv):
    for lo, hi, label in BUCKETS:
        if lo <= mv < hi:
            return label
    return BUCKETS[-1][2]


def main():
    rows = load_join()
    n_set1 = sum(1 for r in rows if r['won_set1'] is not None)
    print(f"=== move_vs_set1 — {len(rows)} matchs joints (CLV ∩ settlement), "
          f"{n_set1} avec set1 connu ===")
    print("(donnees provisoires settlement — exploration, pas de validation)\n")
    if not rows:
        print("rien a analyser."); return

    groups = {}
    for r in rows:
        groups.setdefault(bucket_of(r['steam_move']), []).append(r)

    hdr = f"{'tranche':<22} {'n':>4} {'p_close moy':>11} {'match realise':>13} {'residu':>8} {'n_s1':>5} {'set1 realise':>12} {'comeback':>9}"
    print(hdr); print('-' * len(hdr))
    for lo, hi, label in BUCKETS:
        g = groups.get(label, [])
        if not g:
            continue
        n = len(g)
        pc = sum(r['p_close'] for r in g) / n
        wm = sum(r['won_match'] for r in g) / n
        s1 = [r for r in g if r['won_set1'] is not None]
        ws1 = (sum(r['won_set1'] for r in s1) / len(s1)) if s1 else None
        # comeback = set 1 perdu mais match gagne (cote steamed)
        cb_pool = [r for r in s1 if r['won_set1'] == 0]
        cb = (sum(r['won_match'] for r in cb_pool) / len(cb_pool)) if cb_pool else None
        tag = '' if n >= MIN_N else '  [DIRECTIONNEL n<%d]' % MIN_N
        ws1_s = f"{ws1:>11.1%}" if ws1 is not None else f"{'-':>11}"
        cb_s = f"{cb:>8.1%}" if cb is not None else f"{'-':>8}"
        print(f"{label:<22} {n:>4} {pc:>10.1%} {wm:>12.1%} {wm - pc:>+7.1%} "
              f"{len(s1):>5} {ws1_s} {cb_s}" + tag)

    print("\nLecture :")
    print(" - residu (match realise - p_close) ~ 0 => la cloture dit deja tout, le move n'ajoute rien.")
    print(" - set1 realise croissant avec la taille du move => le move encode le debut de match.")
    print(" - tout ecart sous n>=%d est du bruit. Sackmann confirmera les resultats provisoires." % MIN_N)


if __name__ == '__main__':
    main()
