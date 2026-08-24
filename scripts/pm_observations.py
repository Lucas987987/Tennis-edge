#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pm_observations.py — Table consolidée des observations de marché de prédiction.

POURQUOI CETTE TABLE
Deux problèmes qu'elle résout d'un coup.

1. CHAQUE ANALYSE REPARCOURT TOUT. Les scripts d'étude relisent 3,4 millions de
   ticks à chaque exécution — plus de trois minutes par passage, pour
   reconstruire exactement la même chose. Toute exploration devient coûteuse,
   donc on explore moins.

2. ON NE GARDE QUE CE QU'ON A DÉCIDÉ DE REGARDER. Le suivi de l'hypothèse
   gelée n'enregistre que les tranches 30–45 % et 55–70 %. Si demain une
   question se pose sur les extrêmes, la liquidité, le délai avant match ou
   le niveau de tournoi, il faut tout recalculer — et les partitions anciennes
   auront été compressées puis purgées.

La table capture donc TOUT ce qui est connu au moment de l'observation, une
ligne par (match, côté, marché). Les études lisent ensuite ce fichier, qui
tient en quelques milliers de lignes.

CE QU'ELLE CONTIENT, ET POURQUOI CHAQUE CHAMP
  prix, spread, volume, liquidité   l'état du carnet — un prix sur un carnet
                                    vide ne vaut pas un prix liquide
  lead_min                          délai avant match ; un prix à 10 min du
                                    coup d'envoi n'a pas le statut d'un prix
                                    à 24 h
  p_sharp, ecart_sharp              le prix Pinnacle dévigé au même instant :
                                    permet toute comparaison ultérieure sans
                                    relire les courbes
  niveau, tournoi                   Challenger, Grand Chelem... le découpage
                                    le plus discriminant depuis l'élargissement
  n_ticks                           nombre de ticks derrière l'observation :
                                    un marché vu 3 fois n'est pas un marché
  gagne                             le résultat, quand il est connu
  apres_gel                         postérieur au 24/08/2026, date de gel de
                                    l'hypothèse n°12 — figé ici pour qu'aucune
                                    étude ne puisse le recalculer autrement

GARDE-FOUS
  • Prix STRICTEMENT pré-match : un tick postérieur au coup d'envoi encode le
    déroulement de la rencontre.
  • Une ligne par (match, côté, marché), jamais par tick.
  • Polymarket et Kalshi restent SÉPARÉS : liquidité, participants et frais
    diffèrent. On les réunira si les données le justifient, pas avant.

Sortie : pm_observations.jsonl
Env : DATE_GEL, OUT.
Usage : python scripts/pm_observations.py
"""
import os
import sys
import json
import gzip
import datetime
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov              # noqa: E402
import alert_control_test as act      # noqa: E402
from results_join import ResultIndex  # noqa: E402

DATE_GEL = os.environ.get('DATE_GEL', '2026-08-24')
OUT = os.environ.get('OUT', 'pm_observations.jsonl')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def niveau(t):
    t = (t or '').lower()
    if 'challenger' in t:
        return 'challenger'
    if 'itf' in t:
        return 'itf'
    if any(g in t for g in ('us open', 'wimbledon', 'roland', 'australian')):
        return 'grand_chelem'
    if 'wta' in t:
        return 'wta'
    return 'atp'


def contexte_matchs():
    """{uid: (commence, home, away, tournoi)} et les courbes Pinnacle."""
    ctx, courbes = {}, {}
    # Les courbes LIVE d'abord : les matchs du jour n'ont pas encore été
    # basculés dans les partitions historiques. Sans elles, 135 matchs
    # Polymarket sur 218 étaient sans contexte — donc absents de la table,
    # alors que ce sont les plus récents, ceux qui alimenteront le hors
    # échantillon de l'hypothèse gelée.
    sources = []
    for src in ('book_curves_live.jsonl', 'book_curves.jsonl'):
        try:
            sources.append(list(ov.open_curves(src, verbose=False)))
        except Exception:
            pass
    sources.append(ov.iter_hist_lines('book'))
    for ligne in (x for lot in sources for x in lot):
        try:
            r = json.loads(ligne)
        except Exception:
            continue
        u = r.get('uid')
        ct = _dt(r.get('commence_time'))
        if not u or not ct:
            continue
        if u not in ctx:
            ctx[u] = (ct, r.get('home_team') or r.get('home'),
                      r.get('away_team') or r.get('away'),
                      r.get('tournament') or '')
        if r.get('book') == SHARP and u not in courbes:
            h = sorted((_dt(q[0]), float(q[1])) for q in (r.get('home_curve') or [])
                       if _dt(q[0]) and q[1] and float(q[1]) > 1)
            a = sorted((_dt(q[0]), float(q[1])) for q in (r.get('away_curve') or [])
                       if _dt(q[0]) and q[1] and float(q[1]) > 1)
            if len(h) >= 2 and len(a) >= 2:
                courbes[u] = (h, a)
    return ctx, courbes


def valeur_a(seq, t):
    v = None
    for ts, p in seq:
        if ts > t:
            break
        v = p
    return v


def main():
    gel = datetime.date.fromisoformat(DATE_GEL)
    idx = ResultIndex()
    ctx, courbes = contexte_matchs()
    print(f"{len(ctx)} match(s) en contexte · {len(courbes)} avec courbe {SHARP}")

    lignes = []
    for pre, marche in (('pm_ticks', 'polymarket'), ('kx_ticks', 'kalshi')):
        # Dernier tick pré-match par (match, côté), plus les agrégats du carnet.
        dernier, compte, spreads, volumes = {}, collections.Counter(), {}, {}
        n_lus = 0
        for p in ov.load_partitions(f'parts/{pre}_*.jsonl'):
            o = gzip.open if p.endswith('.gz') else open
            try:
                f = o(p, 'rt', encoding='utf-8', errors='replace')
            except Exception:
                continue
            for ligne in f:
                try:
                    r = json.loads(ligne)
                except Exception:
                    continue
                n_lus += 1
                # Kalshi n'écrit pas market_type : son collecteur ne suit que
                # les séries « vainqueur du match ».
                if r.get('market_type') not in (None, 'match'):
                    continue
                u, s, t = r.get('local_uid'), r.get('local_side'), _dt(r.get('ts'))
                m = r.get('mid')
                if not u or s not in ('home', 'away') or t is None or m is None:
                    continue
                c = ctx.get(u)
                if not c or t >= c[0]:
                    continue                 # coupe pré-match stricte
                try:
                    m = float(m)
                except (TypeError, ValueError):
                    continue
                if not (0.0 < m < 1.0):
                    continue
                k = (u, s)
                compte[k] += 1
                sp = r.get('spread')
                if sp is not None:
                    spreads.setdefault(k, []).append(sp)
                vol = r.get('volume') or r.get('open_interest')
                if vol:
                    volumes[k] = max(volumes.get(k, 0), float(vol))
                if k not in dernier or t > dernier[k][0]:
                    dernier[k] = (t, m, r)
        print(f"{marche} : {n_lus:,} ticks lus · {len(dernier)} observation(s)")

        for (u, s), (t, m, r) in dernier.items():
            ct, home, away, tour = ctx[u]
            # Prix Pinnacle dévigé au MÊME instant : rend toute comparaison
            # ultérieure possible sans relire les courbes.
            p_sharp = None
            cb = courbes.get(u)
            if cb:
                oh, oa = valeur_a(cb[0], t), valeur_a(cb[1], t)
                if oh and oa:
                    ph = act.shin_ph(oh, oa)
                    if ph is not None:
                        p_sharp = ph if s == 'home' else 1 - ph
            w = idx.winner(home, away, ct)
            sp = spreads.get((u, s))
            lignes.append({
                'marche': marche, 'uid': u, 'side': s,
                'home': home, 'away': away, 'commence': ct.isoformat(),
                'tournoi': tour, 'niveau': niveau(tour),
                'ts': t.isoformat(timespec='seconds'),
                'lead_min': round((ct - t).total_seconds() / 60, 1),
                'prix': round(m, 4),
                'spread': round(float(sum(sp) / len(sp)), 4) if sp else None,
                'volume': volumes.get((u, s)),
                'n_ticks': compte[(u, s)],
                'p_sharp': round(p_sharp, 4) if p_sharp is not None else None,
                'ecart_sharp': round((m - p_sharp) * 100, 2)
                               if p_sharp is not None else None,
                'gagne': None if w is None else int((w == 'home') == (s == 'home')),
                'apres_gel': ct.date() > gel,
            })

    lignes.sort(key=lambda x: (x['commence'], x['marche'], x['side']))
    with open(OUT, 'w', encoding='utf-8') as f:
        for x in lignes:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')

    # ── Inventaire : ce que la table permet d'étudier ────────────────────
    print()
    print("=" * 74)
    print(f"TABLE CONSOLIDÉE — {len(lignes)} observation(s)")
    print("=" * 74)
    avec_res = [x for x in lignes if x['gagne'] is not None]
    apres = [x for x in avec_res if x['apres_gel']]
    print(f"  avec résultat connu     : {len(avec_res)}")
    print(f"  postérieures au gel     : {len(apres)}")
    print(f"  avec prix {SHARP:<12}: {sum(1 for x in lignes if x['p_sharp'] is not None)}")

    for cle, titre in (('marche', 'par marché'), ('niveau', 'par niveau')):
        c = collections.Counter(x[cle] for x in avec_res)
        print(f"\n  {titre} (avec résultat) : "
              + " · ".join(f"{k} {v}" for k, v in c.most_common()))

    # Répartition par tranche de prix : c'est elle qui dit si les extrêmes
    # sont couverts, or c'est là que vit le biais favori-outsider.
    print()
    print(f"  {'tranche de prix':<16}{'n':>6}{'dont après gel':>16}")
    print("  " + "-" * 40)
    for lo, hi, lab in ((0, .15, '0 – 15 %'), (.15, .30, '15 – 30 %'),
                        (.30, .45, '30 – 45 %'), (.45, .55, '45 – 55 %'),
                        (.55, .70, '55 – 70 %'), (.70, .85, '70 – 85 %'),
                        (.85, 1.01, '85 – 100 %')):
        g = [x for x in avec_res if lo <= x['prix'] < hi]
        ga = [x for x in g if x['apres_gel']]
        print(f"  {lab:<16}{len(g):>6}{len(ga):>16}")

    print(f"\n{OUT}")
    print("  Les études lisent désormais ce fichier au lieu de reparcourir")
    print("  3,4 millions de ticks à chaque exécution.")


if __name__ == '__main__':
    main()
