#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
identify_set_markets.py — trouve l'ID du marché OddsPapi qui marque la FIN DU
SET 1 (un marché 'set 2' qui ne s'active qu'après le set 1).

Principe : sur plusieurs matchs terminés, on calcule pour chaque marché son
instant d'apparition (min après le coup d'envoi) et on le rapproche du NOMBRE
DE JEUX DU SET 1 (lu dans resultats.json via le score). Le marqueur 'set 2' :
  - apparaît une fois par match dans la 2e vague (offset > seuil) ;
  - son offset CORRÈLE positivement avec le nb de jeux du set 1 (set 1 long ->
    apparition tardive) — les marchés de jeux du set 1 démarrent toujours ~+8m ;
  - PERSISTE ensuite (longue traîne) — un marché de jeu éphémère, non ;
  - 14 issues = score exact de set (indice fort).

ENTRÉE : book_curves.jsonl (fixtures + commence + noms) + resultats.json.
SORTIE : tableau des marchés classés, et le meilleur candidat 'fin de set 1'.

USAGE (GitHub Actions, secret RAPIDAPI_KEY) :
    python scripts/identify_set_markets.py
ENV : IDSM_N [8] nb de matchs à sonder | IDSM_SLEEP [8] s entre appels
      IDSM_MIN_OFFSET [25] seuil 2e vague (min) | BOOKMAKERS [bwin,unibet,betsson]
      BOOK_CURVES [book_curves.jsonl] IPS_RESULTS [resultats.json] IPS_RESULTS_FAST [resultats_fast.json]

Dépendances : aucune (stdlib).
"""
import os, sys, json, glob, time, math, unicodedata
from datetime import datetime, timezone
import oddspapi_v5 as ov   # client commun OddsPapi v5

N        = int(os.environ.get('IDSM_N', '8'))
SLEEP    = float(os.environ.get('IDSM_SLEEP', '3'))
MIN_OFF  = float(os.environ.get('IDSM_MIN_OFFSET', '25'))
MAX_OFF  = float(os.environ.get('IDSM_MAX_OFFSET', '75'))   # au-delà = set 3 / fin de match
MIN_PAIRS = int(os.environ.get('IDSM_MIN_PAIRS', '8'))      # paires mini pour fier à la corr
BOOKS    = [b.strip() for b in os.environ.get('BOOKMAKERS', 'pinnacle,unibet,bwin,betsson').split(',') if b.strip()]
CURVES   = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
RES      = os.environ.get('IPS_RESULTS', 'resultats.json')
RES_FAST = os.environ.get('IPS_RESULTS_FAST', 'resultats_fast.json')


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d
    except Exception:
        return None


def toks(name):
    s = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().lower()
    return {t for t in ''.join(c if c.isalpha() else ' ' for c in s).split() if len(t) >= 3}


def parse_set1_games(score):
    if not isinstance(score, str):
        return None
    for tok in score.replace(',', ' ').split():
        t = tok.split('(')[0]
        if '-' in t:
            a, _, b = t.partition('-')
            try:
                return int(a) + int(b)
            except ValueError:
                return None
    return None


def load_results_games():
    out, seen = [], set()
    for path, official in ((RES, True), (RES_FAST, False)):
        if not glob.glob(path):
            continue
        try:
            data = json.load(open(path, encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        for r in data.get('results', []):
            g = parse_set1_games(r.get('score'))
            ht, at = toks(r.get('home_team', '')), toks(r.get('away_team', ''))
            if g is None or not ht or not at:
                continue
            key = frozenset(ht | at)
            if official:
                seen.add(key)
            elif key in seen:
                continue
            out.append({'ht': ht, 'at': at, 'games': g})
    return out


def set1_games_for(home, away, results):
    ch, ca = toks(home), toks(away)
    for r in results:
        if (ch & r['ht'] and ca & r['at']) or (ch & r['at'] and ca & r['ht']):
            return r['games']
    return None


def market_offsets_v5(fid, commence):
    """mid -> (first_off, last_off, npts, n_out) agrégé sur BOOKS (1er point = le + tôt).
    Offsets en minutes vs commence. v5 : 1 appel historique par book."""
    cms = commence.replace(tzinfo=timezone.utc).timestamp() * 1000.0
    agg = {}
    for book in BOOKS:
        try:
            timing = ov.historical_market_timing(fid, book)
        except Exception:
            continue
        for mid, d in timing.items():
            fo = (d['first_ms'] - cms) / 60000.0
            lo = (d['last_ms'] - cms) / 60000.0
            if mid not in agg or fo < agg[mid][0]:
                agg[mid] = (fo, lo, d['n_points'], d['n_outcomes'])
    return agg


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def median(v):
    v = sorted(v)
    n = len(v)
    return 0 if n == 0 else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)


def main():
    if not ov.KEY:
        sys.exit("RAPIDAPI_KEY manquant.")
    if not glob.glob(CURVES):
        sys.exit(f"Introuvable : {CURVES}")

    # fixtures distincts (les plus récents), avec commence + noms
    fixtures = {}
    with open(CURVES, encoding='utf-8') as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            fid = r.get('fixture_id')
            ct = parse(r.get('commence_time'))
            if fid and ct and fid not in fixtures:
                fixtures[fid] = {'commence': ct, 'home': r.get('home', ''), 'away': r.get('away', '')}
    picks = sorted(fixtures.items(), key=lambda kv: kv[1]['commence'], reverse=True)[:N]
    if not picks:
        sys.exit("Aucun fixture exploitable dans book_curves.jsonl.")

    results = load_results_games()
    # par marché : listes d'offsets, de spans, de npts ; et paires (offset, set1_games)
    M = {}
    used = 0
    print(f"Sondage de {len(picks)} matchs (sleep {SLEEP}s entre appels)...\n")
    for fid, meta in picks:
        try:
            offs = market_offsets_v5(fid, meta['commence'])
        except Exception as e:
            print(f"  {fid}: erreur {e}, ignoré"); time.sleep(SLEEP); continue
        g = set1_games_for(meta['home'], meta['away'], results)
        used += 1
        print(f"  {fid}: {len(offs)} marchés | set1_jeux={g if g is not None else '?'} "
              f"| {meta['home']} vs {meta['away']}")
        for mid, (fo, lo, npts, n_out) in offs.items():
            d = M.setdefault(mid, {'first': [], 'span': [], 'npts': [], 'out': n_out,
                                   'pair_off': [], 'pair_g': []})
            d['first'].append(fo); d['span'].append(lo - fo); d['npts'].append(npts)
            if g is not None and fo > MIN_OFF:
                d['pair_off'].append(fo); d['pair_g'].append(g)
        time.sleep(SLEEP)

    # candidats 'fin de set 1' : 2e vague, présents souvent, persistants
    rows = []
    for mid, d in M.items():
        n_seen = len(d['first'])
        med_first = median(d['first'])
        med_span = median(d['span'])
        med_npts = median(d['npts'])
        npairs = len(d['pair_off'])
        corr = pearson(d['pair_off'], d['pair_g']) if npairs >= 3 else None
        rows.append((mid, n_seen, d['out'], med_first, med_span, med_npts, corr, npairs))

    def qualified(r):
        mid, n_seen, n_out, mf, ms, mp, corr, npairs = r
        return (npairs >= MIN_PAIRS and corr is not None and corr > 0.4
                and MIN_OFF < mf < MAX_OFF)

    def keyf(r):
        corr = r[6] if r[6] is not None else -2
        return (1 if qualified(r) else 0, corr, r[4])
    rows.sort(key=keyf, reverse=True)

    print("\n" + "=" * 90)
    print(f"MARCHÉS CLASSÉS (sur {used} matchs) — fiable seulement si paires>={MIN_PAIRS} "
          f"et offset {MIN_OFF:.0f}-{MAX_OFF:.0f} min")
    print("=" * 90)
    print(f"  {'marché':>8s} {'vus':>4s} {'paires':>6s} {'#iss':>4s} {'1er(méd)':>9s} "
          f"{'traîne':>7s} {'#pts':>5s} {'corr':>6s}")
    print("  " + "-" * 86)
    for r in rows[:15]:
        mid, n_seen, n_out, mf, ms, mp, corr, npairs = r
        cs = f"{corr:+.2f}" if corr is not None else "   —"
        tag = "  <- candidat FIABLE" if qualified(r) else ""
        if n_out >= 10:
            tag += "  [score exact de set]"
        print(f"  {mid:>8s} {n_seen:4d} {npairs:6d} {n_out:4d} {mf:8.0f}m {ms:6.0f}m "
              f"{int(mp):5d} {cs:>6s}{tag}")

    best = next((r for r in rows if qualified(r)), None)
    print("\n" + "=" * 90)
    if best:
        print(f"MEILLEUR CANDIDAT 'fin de set 1' : marché {best[0]} "
              f"(corr {best[6]:+.2f} sur {best[7]} paires, ~+{best[3]:.0f} min, traîne {best[4]:.0f} min).")
        print("Vérifie sur quelques matchs de plus, puis on capture son 1er timestamp.")
    else:
        print(f"AUCUN candidat fiable (paires>={MIN_PAIRS}, corr>0.4, offset {MIN_OFF:.0f}-{MAX_OFF:.0f}m).")
        print("Les fortes corrélations vues sont des artefacts de petit échantillon "
              "(marché présent dans trop peu de matchs).")
        print("=> Volume insuffisant pour identifier proprement. Laisse book_curves grossir "
              "et relance plus tard (ou monte IDSM_N).")
    print("=" * 90)


if __name__ == '__main__':
    main()
