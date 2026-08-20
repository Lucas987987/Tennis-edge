#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polymarket_flow.py — Polymarket anticipe-t-il, et ses mouvements sont-ils réels ?

DEUX QUESTIONS, DANS CET ORDRE
  1. Ces marchés sont-ils assez liquides pour que leurs mouvements veuillent
     dire quelque chose ? Un prix qui bouge de 5 points sur un carnet de 20 $
     n'est pas une information, c'est un ordre isolé.
  2. Quand Polymarket bouge FRANCHEMENT et AVEC DU VOLUME, Pinnacle suit-il
     ensuite ? Et cette réaction dépasse-t-elle ce que produit le hasard ?

POURQUOI UNE ÉTUDE D'ÉVÉNEMENT ET PAS UNE CORRÉLATION
La corrélation croisée (polymarket_leadlag.py) répond à « qui mène en moyenne ».
Elle dilue les rares mouvements informatifs dans une masse de micro-bruit. Ici on
inverse : on isole les mouvements Polymarket qui MÉRITENT attention (amplitude
ET volume), puis on regarde ce que fait Pinnacle APRÈS. C'est la forme qui colle
à la question « Polymarket anticipe-t-il ? », et elle exploite les mises, que la
corrélation ignore.

RECONSTRUCTION DE LA PROBABILITÉ
Un marché binaire a deux jetons dont les prix devraient sommer à 1. On dispose
des deux : p = moyenne de mid(jeton_home) et 1 - mid(jeton_away). Cela réduit le
bruit et fournit un contrôle de cohérence gratuit (|p_home + p_away - 1|), qui
mesure directement la qualité du carnet.

TROIS GARDE-FOUS
  • Pré-match uniquement, des deux côtés.
  • La réaction de Pinnacle est mesurée APRÈS l'événement, jamais autour :
    une fenêtre centrée ferait entrer le passé dans la mesure.
  • Distribution nulle par appariement croisé : on rejoue l'étude en associant
    les événements Polymarket d'un match aux courbes Pinnacle d'un AUTRE match.
    Si la réaction est aussi forte, il n'y a rien. C'est le test qui a démonté
    quatre faux positifs de ce projet.

Env : PM_TICKS_GLOB, CURVES, MARKET_TYPE (match), MOVE_MIN_PTS (3),
      HORIZONS_MIN (15,30,60), MIN_NOTIONAL (0 = pas de filtre), N_PERMUT (200).
"""
import os
import sys
import json
import glob
import gzip
import math
import random
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

# Kalshi d'abord si des ticks existent : couverture plus large (Challengers,
# ITF) et 40x moins de volume. PM_TICKS_GLOB force une source précise.
PM_GLOB      = os.environ.get(
    'PM_TICKS_GLOB',
    'parts/kx_ticks_*.jsonl' if glob.glob('parts/kx_ticks_*.jsonl')
    else 'parts/pm_ticks_*.jsonl')
CURVES       = os.environ.get('CURVES', 'book_curves_live.jsonl')
MARKET_TYPE  = os.environ.get('MARKET_TYPE', 'match')
SHARP        = os.environ.get('SHARP_BOOK', 'pinnacle')
MOVE_MIN     = float(os.environ.get('MOVE_MIN_PTS', '3')) / 100.0
HORIZONS     = [float(x) for x in os.environ.get('HORIZONS_MIN', '15,30,60').split(',')]
MIN_NOTIONAL = float(os.environ.get('MIN_NOTIONAL', '0'))
N_PERMUT     = int(os.environ.get('N_PERMUT', '200'))
LOOKBACK     = float(os.environ.get('LOOKBACK_MIN', '15'))
OUT          = os.environ.get('OUT', 'polymarket_flow_report.json')


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def _open(p):
    return gzip.open(p, 'rt', encoding='utf-8') if p.endswith('.gz') else open(p, encoding='utf-8')


def charger_ticks():
    """(prix par côté, échanges) pour chaque match."""
    prix = collections.defaultdict(lambda: {'home': [], 'away': []})
    trades = collections.defaultdict(list)
    n = 0
    for p in sorted(set(glob.glob(PM_GLOB) + glob.glob(PM_GLOB + '.gz'))):
        try:
            f = _open(p)
        except Exception:
            continue
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            n += 1
            # Kalshi n'écrit PAS market_type : son collecteur ne suit que les
            # séries « vainqueur du match », donc tout tick est déjà du bon
            # type. Exiger le champ rejetait 100 % des ticks Kalshi — et en
            # silence, ce qui est le pire cas.
            mt = r.get('market_type')
            if mt is not None and mt != MARKET_TYPE:
                continue
            if mt is None and MARKET_TYPE != 'match':
                continue
            uid, side, t = r.get('local_uid'), r.get('local_side'), _dt(r.get('ts'))
            if not uid or side not in ('home', 'away') or t is None:
                continue
            mid = r.get('mid')
            if mid is not None:
                try:
                    m = float(mid)
                except Exception:
                    m = None
                if m is not None and 0.0 < m < 1.0:
                    prix[uid][side].append((t, m, r.get('spread'),
                                            r.get('bid_size'), r.get('ask_size')))
            if r.get('event_type') == 'last_trade_price':
                notional = r.get('trade_notional')
                taille = r.get('trade_size')
                if notional is None and taille is not None and r.get('last_trade') is not None:
                    try:
                        notional = float(taille) * float(r['last_trade'])
                    except Exception:
                        notional = None
                trades[uid].append((t, side, notional))
    for uid in prix:
        for s in ('home', 'away'):
            prix[uid][s].sort()
    print(f"Ticks : {n} lus · {len(prix)} match(s) '{MARKET_TYPE}' · "
          f"{sum(len(v) for v in trades.values())} échange(s) horodaté(s)")
    return prix, trades


def proba_home(d):
    """Série (t, p_home) reconstruite à partir des DEUX jetons.

    Le jeton away apporte une seconde estimation : p = 1 - mid(away). En
    moyennant, on divise le bruit de carnet par racine de 2 et on obtient un
    contrôle de cohérence. Si un seul côté est disponible, on l'utilise seul.
    """
    ev = []
    for t, m, sp, bs, asz in d['home']:
        ev.append((t, 'home', m, sp))
    for t, m, sp, bs, asz in d['away']:
        ev.append((t, 'away', m, sp))
    ev.sort()
    serie, incoh = [], []
    ch = ca = None
    for t, s, m, sp in ev:
        if s == 'home':
            ch = m
        else:
            ca = m
        if ch is not None and ca is not None:
            incoh.append(abs(ch + ca - 1.0))
            serie.append((t, (ch + (1.0 - ca)) / 2.0))
        elif ch is not None:
            serie.append((t, ch))
    return serie, incoh


def charger_pinnacle(uids):
    out = {}
    for src in (CURVES, 'book_curves.jsonl'):
        try:
            lines = list(ov.open_curves(src, verbose=False))
        except Exception:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get('book') != SHARP or r.get('uid') not in uids:
                continue
            ct = _dt(r.get('commence_time'))
            if not ct:
                continue
            h = sorted((_dt(q[0]), float(q[1])) for q in (r.get('home_curve') or [])
                       if _dt(q[0]) and q[1] and float(q[1]) > 1)
            a = sorted((_dt(q[0]), float(q[1])) for q in (r.get('away_curve') or [])
                       if _dt(q[0]) and q[1] and float(q[1]) > 1)
            h = [x for x in h if x[0] < ct]
            a = [x for x in a if x[0] < ct]
            if len(h) < 2 or len(a) < 2:
                continue
            ad = dict(a)
            serie, last = [], None
            for t, ph in h:
                last = ad.get(t, last)
                if last is None:
                    continue
                s = 1.0 / ph + 1.0 / last
                if s > 0:
                    serie.append((t, (1.0 / ph) / s))
            if len(serie) >= 2 and r['uid'] not in out:
                out[r['uid']] = (serie, ct)
    print(f"Pinnacle : {len(out)} match(s) avec courbe exploitable")
    return out


def valeur_a(serie, t):
    """Dernière valeur connue à l'instant t (escalier, sans anticipation)."""
    v = None
    for ts, p in serie:
        if ts > t:
            break
        v = p
    return v


def evenements(serie, trades, ct):
    """Mouvements Polymarket d'au moins MOVE_MIN sur LOOKBACK minutes."""
    out = []
    for i, (t, p) in enumerate(serie):
        if t >= ct:
            break
        t0 = t - datetime.timedelta(minutes=LOOKBACK)
        p0 = valeur_a(serie[:i], t0)
        if p0 is None:
            continue
        d = p - p0
        if abs(d) < MOVE_MIN:
            continue
        vol = sum(n for tt, _, n in trades
                  if n is not None and t0 <= tt <= t)
        out.append({'t': t, 'delta_pm': d, 'p': p, 'notional': vol})
    # un seul événement par fenêtre : sinon un mouvement unique est compté
    # dix fois et gonfle artificiellement le n.
    garde, dernier = [], None
    for e in out:
        if dernier is None or (e['t'] - dernier).total_seconds() / 60.0 >= LOOKBACK:
            garde.append(e)
            dernier = e['t']
    return garde


def reaction(pin, ct, t, horizon):
    """Variation de Pinnacle APRÈS l'événement, jamais autour."""
    p0 = valeur_a(pin, t)
    t1 = t + datetime.timedelta(minutes=horizon)
    if t1 > ct:
        return None
    p1 = valeur_a(pin, t1)
    if p0 is None or p1 is None or p1 == p0:
        return None
    return p1 - p0


def etude(prix, trades, pins, appariement=None):
    res = {h: [] for h in HORIZONS}
    n_ev = 0
    for uid, (pin, ct) in pins.items():
        src_uid = appariement.get(uid, uid) if appariement else uid
        d = prix.get(src_uid)
        if not d:
            continue
        serie, _ = proba_home(d)
        if len(serie) < 3:
            continue
        for e in evenements(serie, trades.get(src_uid, []), ct):
            if MIN_NOTIONAL and (e['notional'] or 0) < MIN_NOTIONAL:
                continue
            n_ev += 1
            for h in HORIZONS:
                r = reaction(pin, ct, e['t'], h)
                if r is None:
                    continue
                # signe aligné : +1 si Pinnacle bouge DANS LE SENS de Polymarket
                res[h].append(1.0 if (r * e['delta_pm']) > 0 else 0.0)
    return res, n_ev


def ic_prop(v):
    n = len(v)
    if n < 2:
        return None, None, None
    p = st.mean(v)
    se = math.sqrt(max(p * (1 - p), 1e-9) / n)
    return p, p - 1.96 * se, p + 1.96 * se


def main():
    prix, trades = charger_ticks()
    if not prix:
        print("\n❌ aucune série Polymarket. Le collecteur a-t-il tourné ?")
        return
    pins = charger_pinnacle(set(prix))
    if not pins:
        print("\n❌ aucun match commun entre ticks et courbes.")
        return

    # ── 1. Profil de liquidité ────────────────────────────────────────────
    spreads, incohs, notionals = [], [], []
    for uid, d in prix.items():
        for s in ('home', 'away'):
            spreads += [float(x[2]) for x in d[s] if x[2] is not None]
        _, inc = proba_home(d)
        incohs += inc
    for uid, tl in trades.items():
        notionals += [n for _, _, n in tl if n is not None]

    print()
    print("=" * 72)
    print("1. CES MARCHÉS SONT-ILS LIQUIDES ?")
    print("=" * 72)
    if spreads:
        print(f"  fourchette médiane   : {st.median(spreads)*100:5.2f} points de proba")
        print(f"  fourchette 90e cent. : {sorted(spreads)[int(0.9*(len(spreads)-1))]*100:5.2f}")
    else:
        print("  aucune fourchette relevée")
    if incohs:
        print(f"  incohérence 2 jetons : {st.median(incohs)*100:5.2f} pts (|p_home + p_away - 1|)")
    if notionals:
        print(f"  échanges             : {len(notionals)} · médiane "
              f"{st.median(notionals):.0f} $ · total {sum(notionals):.0f} $")
        print(f"  plus gros échange    : {max(notionals):.0f} $")
    else:
        print("  ⚠️ AUCUN montant échangé relevé — soit le collecteur date d'avant")
        print("     l'enregistrement des mises, soit ces marchés ne s'échangent pas.")
    if spreads and st.median(spreads) > 0.05:
        print("  ⚠️ fourchette médiane > 5 points : carnet très mince. Un mouvement")
        print("     de prix y est faiblement informatif, quel que soit le résultat ci-dessous.")

    # ── 2. Étude d'événement ──────────────────────────────────────────────
    res, n_ev = etude(prix, trades, pins)
    print()
    print("=" * 72)
    print(f"2. QUAND POLYMARKET BOUGE DE ≥ {MOVE_MIN*100:.0f} PTS, PINNACLE SUIT-IL ?")
    print(f"   {n_ev} événement(s) · fenêtre de détection {LOOKBACK:.0f} min"
          + (f" · mise minimale {MIN_NOTIONAL:.0f} $" if MIN_NOTIONAL else ""))
    print("=" * 72)
    if n_ev == 0:
        print("  aucun événement — accumuler davantage, ou abaisser MOVE_MIN_PTS.")
        return

    # distribution nulle : événements d'un match, courbes d'un AUTRE
    uids = list(pins)
    rng = random.Random(20260819)
    nul = {h: [] for h in HORIZONS}
    for _ in range(max(20, N_PERMUT)):
        mel = uids[:]
        rng.shuffle(mel)
        app = {u: v for u, v in zip(uids, mel) if u != v}
        if not app:
            continue
        r2, _ = etude(prix, trades, pins, appariement=app)
        for h in HORIZONS:
            if r2[h]:
                nul[h].append(st.mean(r2[h]))

    print(f"{'horizon':>9} | {'n':>4} | {'suit le sens':>13} | {'IC95':>16} | {'seuil bruit':>11}")
    print("-" * 72)
    verdicts = {}
    for h in HORIZONS:
        v = res[h]
        if len(v) < 5:
            print(f"{h:>7.0f}mn | {len(v):>4} | trop peu d'observations")
            continue
        p, lo, hi = ic_prop(v)
        seuil = None
        if nul[h]:
            s = sorted(nul[h])
            seuil = s[int(0.95 * (len(s) - 1))]
        concluant = (lo is not None and lo > 0.5
                     and seuil is not None and p > seuil)
        verdicts[h] = {'n': len(v), 'p': round(p, 3),
                       'ic': [round(lo, 3), round(hi, 3)],
                       'seuil_bruit': None if seuil is None else round(seuil, 3),
                       'concluant': bool(concluant)}
        print(f"{h:>7.0f}mn | {len(v):>4} | {p*100:>12.1f}% | "
              f"[{lo*100:>5.1f};{hi*100:>5.1f}] | "
              f"{'—' if seuil is None else f'{seuil*100:>10.1f}%'}"
              + ("  ✅" if concluant else ""))

    print()
    print("Lecture : 50 % = Pinnacle bouge autant dans un sens que dans l'autre,")
    print("donc AUCUNE anticipation. Il faut que l'IC95 exclue 50 % ET que la")
    print("proportion dépasse le seuil de bruit (appariements croisés).")
    if not any(v.get('concluant') for v in verdicts.values()):
        print("\n→ NON CONCLUANT à ce stade. Aucune anticipation démontrée.")

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds'),
        'market_type': MARKET_TYPE, 'move_min_pts': MOVE_MIN * 100,
        'lookback_min': LOOKBACK, 'min_notional': MIN_NOTIONAL,
        'n_evenements': n_ev,
        'liquidite': {
            'spread_median_pts': round(st.median(spreads) * 100, 3) if spreads else None,
            'incoherence_median_pts': round(st.median(incohs) * 100, 3) if incohs else None,
            'n_echanges': len(notionals),
            'notional_median': round(st.median(notionals), 2) if notionals else None,
            'notional_total': round(sum(notionals), 2) if notionals else None,
        },
        'horizons': {str(k): v for k, v in verdicts.items()},
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
