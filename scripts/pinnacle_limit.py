#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pinnacle_limit.py — La limite de mise Pinnacle rend-elle un mouvement plus fiable ?

CE QU'EST LA LIMITE
Pinnacle expose, sur /fixtures/odds/historical, le montant maximum qu'il accepte
sur un prix donné. Elle monte par paliers à mesure que le marché mûrit
(25 → 50 → 100 → 125 → 162...) : c'est un proxy direct de la CONFIANCE du book
dans son propre prix. Un mouvement à limite élevée engage beaucoup d'argent ;
un mouvement à limite basse est une hypothèse prudente.

CE QUI A ÉTÉ CONSTATÉ
On croyait le suivi perdu dans une migration. En réalité il tourne :
fetch_book_curves appelle historical_curves(..., with_limit=True) et
build_entry écrit la limite en TROISIÈME élément de chaque point quand elle
existe. Mesuré sur 200 208 points Pinnacle : 20 036 en portent une, soit 10 %.
Le format est donc hétérogène — [ts, prix] ou [ts, prix, limite] — et tout
script qui déballe en deux valeurs planterait. C'est pourquoi ce module fournit
un accès unique.

LES DEUX QUESTIONS
  1. Un mouvement Pinnacle à limite ÉLEVÉE se referme-t-il mieux qu'un
     mouvement à limite basse ? Si oui, la limite est un filtre gratuit :
     elle est déjà dans les données, sans requête supplémentaire.
  2. La limite au moment de l'alerte dit-elle quelque chose du CLV obtenu chez
     les books mous ?

POURQUOI C'EST DIFFÉRENT DES AUTRES SIGNAUX
Polymarket, Kalshi et les books mous sont tous des PRIX, corrélés entre eux —
mesuré : 0,56 point d'écart médian. La limite n'est pas un prix : c'est une
déclaration d'engagement. C'est le seul signal du projet, avec l'Elo, qui ne
soit pas une redite du marché.

GARDE-FOUS
  • Coupe pré-match stricte ;
  • une observation par match ;
  • comparaison par TRANCHE de limite, pas par seuil choisi a posteriori ;
  • test de permutation sur l'étiquette de tranche.

Usage : python scripts/pinnacle_limit.py
"""
import os
import sys
import json
import math
import random
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
PALIER = float(os.environ.get('PALIER_PTS', '5')) / 100
MIN_LEAD = float(os.environ.get('MIN_LEAD_MIN', '45'))
MAX_MAG = float(os.environ.get('MAX_MAG_PTS', '20')) / 100
N_PERMUT = int(os.environ.get('N_PERMUT', '400'))
OUT = os.environ.get('OUT', 'pinnacle_limit_report.json')
EXCHANGES = set(b.strip() for b in os.environ.get(
    'EXCHANGES', 'betfair-ex,betfair,matchbook,smarkets,betdaq').split(',') if b.strip())


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def point(c):
    """(datetime, prix, limite|None) — quel que soit le format du point.

    Les points valent [ts, prix] OU [ts, prix, limite] : déballer en deux
    valeurs planterait sur 10 % des données Pinnacle.
    """
    if not c or len(c) < 2:
        return None
    t = _dt(c[0])
    if t is None or not c[1]:
        return None
    try:
        p = float(c[1])
    except (TypeError, ValueError):
        return None
    if p <= 1:
        return None
    lim = None
    if len(c) > 2 and c[2] is not None:
        try:
            lim = float(c[2])
        except (TypeError, ValueError):
            lim = None
    return t, p, lim


def shin_ph(oh, oa):
    try:
        ih, ia = 1.0 / float(oh), 1.0 / float(oa)
    except Exception:
        return None
    s = ih + ia
    if s <= 0:
        return None
    if s <= 1:
        return ih / s
    z, ph, pa = 0.02, None, None
    for _ in range(50):
        ph = (math.sqrt(z * z + 4 * (1 - z) * ih * ih / s) - z) / (2 * (1 - z))
        pa = (math.sqrt(z * z + 4 * (1 - z) * ia * ia / s) - z) / (2 * (1 - z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z = min(max(z + (t - 1), 0.0), 0.3)
    return ph / (ph + pa) if (ph and pa) else None


def valeur_a(seq, t):
    v = None
    for x in seq:
        if x[0] > t:
            break
        v = x
    return v


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def main():
    # ── Charger, en regroupant par (paire de joueurs, date) ──────────────
    par_match = collections.defaultdict(dict)
    for src in ('book_curves_live.jsonl', 'book_curves.jsonl'):
        try:
            lignes = list(ov.open_curves(src, verbose=False))
        except Exception:
            lignes = []
        for ligne in lignes:
            _ajouter(par_match, ligne)
    for ligne in ov.iter_hist_lines('book'):
        _ajouter(par_match, ligne)
    print(f"{len(par_match)} match(s) chargé(s)")

    obs = []
    sans_limite = 0
    for k, d in par_match.items():
        pin = d.get(SHARP)
        ct = d.get('_ct')
        if not pin or not ct:
            continue
        h, a = pin['h'], pin['a']
        p0 = shin_ph(h[0][1], a[0][1])
        if p0 is None:
            continue
        decl = None
        for t in sorted({x[0] for x in h} | {x[0] for x in a}):
            ph_, pa_ = valeur_a(h, t), valeur_a(a, t)
            if not ph_ or not pa_:
                continue
            lead = (ct - t).total_seconds() / 60
            if lead < MIN_LEAD:
                break
            p1 = shin_ph(ph_[1], pa_[1])
            if p1 is None:
                continue
            if PALIER <= abs(p1 - p0) <= MAX_MAG:
                # La limite au moment du mouvement : celle du côté qui monte.
                lim = ph_[2] if (p1 - p0) > 0 else pa_[2]
                decl = (t, p1 - p0, p1, lim)
                break
        if not decl:
            continue
        t, shift, p_now, lim = decl
        if lim is None:
            sans_limite += 1
            continue

        # Refermeture du mouvement : Pinnacle continue-t-il dans le même sens ?
        pf = shin_ph(h[-1][1], a[-1][1])
        if pf is None:
            continue
        suite = (pf - p_now) * 100 * (1 if shift > 0 else -1)

        # CLV du meilleur book mou au même instant.
        side = 'h' if shift > 0 else 'a'
        ps = p_now if side == 'h' else 1 - p_now
        clv = None
        if ps > 0:
            juste = 1.0 / ps
            best = None
            for bk, s in d.items():
                if bk.startswith('_') or bk == SHARP:
                    continue
                cur = valeur_a(s[side], t)
                if not cur:
                    continue
                g = cur[1] / juste - 1
                if best is None or g > best[0]:
                    best = (g, (cur[1] / s[side][-1][1] - 1) * 100)
            if best:
                clv = best[1]

        obs.append({'limite': lim, 'suite_pts': suite, 'clv': clv,
                    'ampleur_pts': abs(shift) * 100})

    print(f"{len(obs)} mouvement(s) avec limite · {sans_limite} sans limite\n")
    if len(obs) < 40:
        print("⏳ trop peu pour conclure. La limite n'est présente que sur 10 %")
        print("   des points : il faut laisser l'historique grossir.")
        return

    lims = sorted(o['limite'] for o in obs)
    q = [lims[int(f * (len(lims) - 1))] for f in (0.25, 0.5, 0.75)]
    print(f"limite : médiane {q[1]:.0f} · quartiles {q[0]:.0f} / {q[2]:.0f} "
          f"· max {lims[-1]:.0f}")

    tranches = [(0, q[0], f'≤ {q[0]:.0f}'), (q[0], q[1], f'{q[0]:.0f}–{q[1]:.0f}'),
                (q[1], q[2], f'{q[1]:.0f}–{q[2]:.0f}'), (q[2], 1e9, f'> {q[2]:.0f}')]

    print()
    print("=" * 76)
    print("LE MOUVEMENT SE POURSUIT-IL SELON LA LIMITE ENGAGÉE ?")
    print("(suite = déplacement Pinnacle APRÈS l'alerte, dans le même sens)")
    print("=" * 76)
    print(f"  {'tranche de limite':<22}{'n':>5}{'suite méd.':>13}{'suite moy.':>13}{'IC95':>18}")
    print("-" * 76)
    rapport = {}
    for lo, hi, lab in tranches:
        g = [o['suite_pts'] for o in obs if lo <= o['limite'] < hi]
        if len(g) < 8:
            print(f"  {lab:<22}{len(g):>5}   trop peu")
            continue
        m, l, hh = ic(g)
        rapport[lab] = {'n': len(g), 'suite_moy': round(m, 2),
                        'ic': [round(l, 2), round(hh, 2)]}
        print(f"  {lab:<22}{len(g):>5}{st.median(g):>+12.2f}{m:>+13.2f}"
              f"  [{l:>+6.2f} ; {hh:>+6.2f}]")

    clvs = [o for o in obs if o['clv'] is not None]
    if len(clvs) >= 40:
        print()
        print("=" * 76)
        print("CLV DU MEILLEUR BOOK MOU SELON LA LIMITE")
        print("=" * 76)
        print(f"  {'tranche de limite':<22}{'n':>5}{'CLV médian':>13}{'CLV moyen':>13}{'IC95':>18}")
        print("-" * 76)
        for lo, hi, lab in tranches:
            g = [o['clv'] for o in clvs if lo <= o['limite'] < hi]
            if len(g) < 8:
                print(f"  {lab:<22}{len(g):>5}   trop peu")
                continue
            m, l, hh = ic(g)
            rapport.setdefault(lab, {})['clv_moy'] = round(m, 2)
            print(f"  {lab:<22}{len(g):>5}{st.median(g):>+12.1f}%{m:>+12.1f}%"
                  f"  [{l:>+6.1f} ; {hh:>+6.1f}]")

    # ── Permutation : l'étiquette de tranche est-elle informative ? ───────
    bas = [o['suite_pts'] for o in obs if o['limite'] < q[1]]
    haut = [o['suite_pts'] for o in obs if o['limite'] >= q[1]]
    if len(bas) >= 8 and len(haut) >= 8:
        ecart = st.mean(haut) - st.mean(bas)
        tous = bas + haut
        rng = random.Random(20260822)
        nul = []
        for _ in range(N_PERMUT):
            rng.shuffle(tous)
            nul.append(st.mean(tous[:len(haut)]) - st.mean(tous[len(haut):]))
        nul.sort()
        seuil = nul[int(0.95 * (len(nul) - 1))]
        print()
        print(f"  limite haute vs basse : {ecart:+.2f} pts de suite")
        print(f"  seuil de bruit ({N_PERMUT} rebattages) : {seuil:+.2f}")
        if ecart <= seuil:
            print("  → n'excède pas une étiquette tirée au hasard. Rien de démontré.")
        else:
            print("  → dépasse le bruit. À geler et valider hors échantillon.")
        rapport['_permutation'] = {'ecart': round(ecart, 3),
                                   'seuil': round(seuil, 3),
                                   'depasse': bool(ecart > seuil)}

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'n_mouvements': len(obs), 'sans_limite': sans_limite,
        'quartiles_limite': q, 'tranches': rapport,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")


def _ajouter(par_match, ligne):
    try:
        r = json.loads(ligne)
    except Exception:
        return
    bk = r.get('book')
    ct = _dt(r.get('commence_time'))
    if not bk or not ct or bk in EXCHANGES:
        return
    h = [x for x in (point(c) for c in (r.get('home_curve') or [])) if x and x[0] < ct]
    a = [x for x in (point(c) for c in (r.get('away_curve') or [])) if x and x[0] < ct]
    if len(h) < 2 or len(a) < 2:
        return
    h.sort()
    a.sort()
    k = (str(r.get('home') or r.get('home_team')),
         str(r.get('away') or r.get('away_team')), str(ct)[:10])
    if bk in par_match[k]:
        return
    par_match[k][bk] = {'h': h, 'a': a}
    par_match[k]['_ct'] = ct


if __name__ == '__main__':
    main()
