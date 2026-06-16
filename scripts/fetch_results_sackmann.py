#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_results_sackmann.py — Résultats match + set depuis les CSV Sackmann (GRATUIT).

Lit atp_matches_YYYY.csv / wta_matches_YYYY.csv (repos Sackmann clonés par le
workflow), dérive le vainqueur du MATCH, du SET 1 et du SET 2 à partir de la chaîne
de score, joint à tes matchs (par paire de joueurs + fenêtre de dates) et écrit
set_results.json au format {uid: {match, set1, set2}} en 'home'/'away'.

Source AUTORITAIRE pour le backfill/validation (ROI match ET set), sans API.
Latence Sackmann = quelques jours à ~2 semaines -> pour le settlement FRAIS, garder
l'API ; ce script complète/corrige ensuite. Fusionne sans écraser les valeurs déjà
présentes (il remplit les trous et ajoute les matchs manquants).

Env : SACKMANN_ATP, SACKMANN_WTA (dossiers clonés ; sinon tente le réseau via meme
  logique que update_players n'est PAS importée -> on lit local uniquement ici).
  YEARS (def 2023-2026), DATE_WINDOW_DAYS (def 14), SET_RESULTS (def set_results.json),
  CURVES_GLOB (def 'book_curves*.jsonl,set1_curves*.jsonl,set2_curves*.jsonl'),
  CLOSING (def closing_lines.json).
"""
import os, csv, json, glob, re, unicodedata
from datetime import datetime, timedelta

SACK = {'atp': os.environ.get('SACKMANN_ATP', ''), 'wta': os.environ.get('SACKMANN_WTA', '')}
YEARS = [int(y) for y in os.environ.get('YEARS', '2023 2024 2025 2026').split()]
WIN_DAYS = int(os.environ.get('DATE_WINDOW_DAYS', '14'))
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
CURVES_GLOB = os.environ.get('CURVES_GLOB', 'book_curves*.jsonl,set1_curves*.jsonl,set2_curves*.jsonl')
CLOSING = os.environ.get('CLOSING', 'closing_lines.json')


def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]+', ' ', s).strip()

def _ln(s):
    t = [x for x in _norm(s).split() if x not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return t[-1] if t else ''

def _pairkey(a, b):
    return frozenset({_ln(a), _ln(b)})

def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def set_won_by_winner(a, b):
    """Le set 'a-b' (perspective vainqueur du match) est-il complet, et gagné par lui ?
    True / False / None(incomplet)."""
    hi = max(a, b)
    if hi < 6:
        return None
    if abs(a - b) < 2 and hi < 7:   # ex. 6-5 = set non terminé (abandon)
        return None
    return a > b


def parse_sets(score):
    """Liste des sets (jeux_vainqueur, jeux_perdant) jusqu'à un éventuel abandon."""
    out = []
    if not score:
        return out
    for tok in str(score).split():
        u = tok.upper()
        if u in ('RET', 'W/O', 'DEF', 'WALKOVER', 'UNK', 'UNKNOWN', 'NA', 'ABN'):
            break
        m = re.match(r'^(\d+)-(\d+)', tok)
        if m:
            out.append((int(m.group(1)), int(m.group(2))))
    return out


def load_system_matches():
    """uid -> (home, away, date) depuis les fichiers de courbes + closing_lines."""
    matches = {}
    for pat in CURVES_GLOB.split(','):
        for fn in glob.glob(pat.strip()):
            for line in open(fn, encoding='utf-8'):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                uid, h, a = r.get('uid'), r.get('home'), r.get('away')
                d = _dt(r.get('commence_time'))
                if uid and h and a and d and uid not in matches:
                    matches[uid] = (h, a, d)
    if os.path.exists(CLOSING):
        try:
            cl = json.load(open(CLOSING, encoding='utf-8'))
            for uid, v in cl.items():
                h, a = v.get('home'), v.get('away')
                d = _dt(v.get('commence_time'))
                if uid and h and a and d and uid not in matches:
                    matches[uid] = (h, a, d)
        except Exception:
            pass
    return matches


def load_sackmann():
    """pairkey -> liste de (date, winner_name, loser_name, score)."""
    idx = {}
    n = 0
    for tour, base in SACK.items():
        if not base:
            continue
        for y in YEARS:
            fn = os.path.join(base, f"{tour}_matches_{y}.csv")
            if not os.path.exists(fn):
                continue
            for r in csv.DictReader(open(fn, encoding='utf-8', errors='replace')):
                w, l, sc = r.get('winner_name'), r.get('loser_name'), r.get('score')
                td = r.get('tourney_date', '')
                if not (w and l and td):
                    continue
                try:
                    d = datetime.strptime(td[:8], '%Y%m%d')
                except Exception:
                    continue
                idx.setdefault(_pairkey(w, l), []).append((d, w, l, sc))
                n += 1
    return idx, n


def main():
    if not (SACK['atp'] or SACK['wta']):
        print("SACKMANN_ATP / SACKMANN_WTA non définis (repos Sackmann à cloner). Abandon.")
        return
    sysm = load_system_matches()
    sack, nrows = load_sackmann()
    print(f"{len(sysm)} matchs système | {nrows} matchs Sackmann ({sum(len(v) for v in sack.values())} indexés)")
    if not sysm or not sack:
        print("Rien à joindre."); return

    out = {}
    if os.path.exists(SET_RESULTS):
        try:
            out = json.load(open(SET_RESULTS, encoding='utf-8'))
        except Exception:
            out = {}

    matched = added = filled = 0
    for uid, (home, away, mdate) in sysm.items():
        cands = sack.get(_pairkey(home, away))
        if not cands:
            continue
        best = min(cands, key=lambda c: abs((c[0] - mdate).days))
        if abs((best[0] - mdate).days) > WIN_DAYS:
            continue
        _, wname, lname, score = best
        matched += 1
        home_is_winner = _ln(home) == _ln(wname)
        sets = parse_sets(score)
        def side_for(set_idx):
            if set_idx >= len(sets):
                return None
            mw = set_won_by_winner(*sets[set_idx])      # le vainqueur du match a-t-il pris ce set ?
            if mw is None:
                return None
            home_won = mw if home_is_winner else (not mw)
            return 'home' if home_won else 'away'
        res = {'match': 'home' if home_is_winner else 'away',
               'set1': side_for(0), 'set2': side_for(1)}
        cur = out.get(uid)
        if cur is None:
            out[uid] = {k: v for k, v in res.items() if v}; added += 1
        else:
            for k, v in res.items():
                if v and not cur.get(k):
                    cur[k] = v; filled += 1
    json.dump(out, open(SET_RESULTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f"✅ {matched} matchs appariés | {added} ajoutés, {filled} champs complétés -> {SET_RESULTS} ({len(out)} total)")


if __name__ == '__main__':
    main()
