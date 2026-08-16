#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
opening_value.py — Les ouvertures molles GAGNENT-elles vraiment ? (par bookmaker)

BIAIS DE SÉLECTION CORRIGÉ (16/08/2026) — lire avant d'interpréter tout chiffre.
La version précédente comparait la cote d'OUVERTURE d'un book au juste prix de
CLÔTURE de Pinnacle (pf[-1]), puis ne gardait que les ouvertures dont l'EV
dépassait 2%. Autrement dit : elle sélectionnait les prix qui ont bougé
favorablement EN LE SACHANT APRÈS COUP. Aucune de ces mises n'est plaçable à
l'ouverture : au moment de miser, la clôture n'existe pas encore. Le symptôme
qui a permis de le détecter : PINNACLE lui-même ressortait "ouverture molle
rentable" à +30,1% de ROI (IC95 +12,6;+47,5) — impossible pour un book sharp
contre son propre closing, et signature nette d'une sélection sur le futur.
C'est le biais de look-ahead sous une autre forme (cf. fil épinglé).

MODE = 'prospective' (défaut) : le juste prix de référence est celui de Pinnacle
  À L'INSTANT OÙ LE BOOK OUVRE (dernier point Pinnacle <= t_ouverture du book).
  Toute l'information utilisée est disponible au moment de miser -> le ROI
  affiché est réellement traçable. Les matchs où Pinnacle n'a pas encore ouvert
  sont EXCLUS (aucune référence disponible) : ce sous-ensemble est précisément
  l'objet de l'hypothèse gelée n°6 ("book ouvert avant Pinnacle"), à traiter là-bas.
MODE = 'close' : ancien comportement, CONSERVÉ pour diagnostic uniquement.
  Ne mesure PAS un edge misable, seulement l'amplitude du mouvement à venir.
  Ne jamais publier un ROI issu de ce mode.

Multi-books : groupe par le champ 'book' de book_curves.jsonl. Lecture seule.
EV>0 dit "bat la référence" ; ROI réel dit "gagne vraiment". C'est le ROI qui tranche.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov
import player_key as pk
import json, os, sys, math, re, unicodedata, datetime
from statistics import mean

HIST    = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
BOOKF   = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
RESULTS = os.environ.get('RESULTS', 'resultats.json')
OUT     = os.environ.get('OPENING_VALUE_REPORT', 'opening_value_report.json')
EV_TH   = 0.02
DATE_TOL = 3
# 'prospective' = référence Pinnacle à l'instant de l'ouverture (misable).
# 'close'       = référence = clôture Pinnacle (look-ahead, diagnostic seul).
MODE    = os.environ.get('OPENING_VALUE_MODE', 'prospective').strip().lower()

def norm_tokens(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return set(t for t in re.split(r'[^a-z0-9]+', s.lower()) if len(t) >= 2)

# Règle d'appariement centralisée dans player_key.py. L'ancienne version locale
# acceptait UN SEUL jeton commun de 4+ lettres -- donc un prénom partagé
# (Tallon Griekspoor ≡ Tallon Tien). 133 matchs sur 1286 recevaient ainsi un
# vainqueur erroné, ce qui gonflait le résidu de calibration de juin de
# -0,8 à +12,2 pts. Voir player_key.py pour la mesure complète.
def player_match(a, b):
    return pk.player_match(a, b)

def parse_date(s):
    try: return datetime.date.fromisoformat(str(s)[:10])
    except Exception: return None

def parse_curve(raw):
    out = []
    for p in raw or []:
        if not p or len(p) < 2: continue
        try:
            dt = datetime.datetime.fromisoformat(str(p[0]).replace('Z', '+00:00')).replace(tzinfo=None)
            pr = float(p[1])
        except (TypeError, ValueError, Exception):
            continue
        if pr > 1.0: out.append((dt, pr))
    out.sort(key=lambda x: x[0])
    return out

def fav_dog(c0, c1):
    if not c0 or not c1: return None, None
    return (c0, c1) if c0[-1][1] <= c1[-1][1] else (c1, c0)

def load_jsonl(path):
    rows = []
    # open_curves : legacy monolithique -> partitions hist ; plat live absent
    # -> rebuild depuis parts/ ; sinon lecture directe (cf. oddspapi_v5).
    try:
        src = ov.open_curves(path, verbose=False)
    except FileNotFoundError as e:
        print(f"⚠️ {e}"); return rows
    for line in src:
        line = line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
    return rows

RESULTS_FAST = os.environ.get('RESULTS_FAST', 'resultats_fast.json')
# Validation sur Sackmann confirmé seulement ; provisoire = directionnel (INCLUDE_PROVISIONAL=1).
INCLUDE_PROVISIONAL = os.environ.get('INCLUDE_PROVISIONAL', '0') == '1'
# Closing Pinnacle fiable si dernier point pré-match ≤ ce délai avant le coup d'envoi.
CLV_CLOSE_MAX_MINS = int(os.environ.get('CLV_CLOSE_MAX_MINS', '60'))

def _load_results_file(path, provisional):
    if not os.path.exists(path): return []
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception:
        return []
    res = d.get('results', d) if isinstance(d, dict) else d
    out = []
    for r in res:
        if not isinstance(r, dict): continue
        r['_H'] = norm_tokens(r.get('home_team', '')); r['_A'] = norm_tokens(r.get('away_team', ''))
        r['_d'] = parse_date(r.get('date'))
        r['_prov'] = provisional
        out.append(r)
    return out

def _same_match(p, a):
    direct = player_match(p['_H'], a['_H']) and player_match(p['_A'], a['_A'])
    swap   = player_match(p['_H'], a['_A']) and player_match(p['_A'], a['_H'])
    if not (direct or swap): return False
    if p['_d'] and a['_d'] and abs((p['_d'] - a['_d']).days) > DATE_TOL: return False
    return True

def load_results():
    """Sackmann (officiel) = base de VALIDATION. Le provisoire rapide n'est ajouté
    (pour les matchs que Sackmann n'a pas encore) que si INCLUDE_PROVISIONAL=1, et
    sert alors uniquement à un aperçu DIRECTIONNEL — il ne valide jamais le CLV."""
    auth = _load_results_file(RESULTS, False)
    if not INCLUDE_PROVISIONAL:
        print(f"✅ validation Sackmann seul : {len(auth)} résultats confirmés")
        return auth
    prov = _load_results_file(RESULTS_FAST, True)
    kept = [p for p in prov if not any(_same_match(p, a) for a in auth)]
    print(f"⚠️ PROVISOIRE INCLUS (directionnel) : {len(auth)} confirmés + {len(kept)} provisoires")
    return auth + kept

def find_winner_side(home, away, mdate, results):
    """Renvoie 'home'/'away' (orientation clv) gagnant, ou None."""
    H, A = norm_tokens(home), norm_tokens(away)
    for r in results:
        direct = player_match(H, r['_H']) and player_match(A, r['_A'])
        swap   = player_match(H, r['_A']) and player_match(A, r['_H'])
        if not (direct or swap): continue
        if mdate and r['_d'] and abs((mdate - r['_d']).days) > DATE_TOL: continue
        wc = r.get('winner_code')
        if wc not in (1, 2):
            wn = norm_tokens(r.get('winner', ''))
            wc = 1 if player_match(wn, r['_H']) else (2 if player_match(wn, r['_A']) else None)
        if wc not in (1, 2): return None
        res_home_won = (wc == 1)
        clvH_won = res_home_won if direct else (not res_home_won)
        return 'home' if clvH_won else 'away'
    return None

def main():
    pin = {r['uid']: r for r in load_jsonl(HIST) if r.get('uid')}
    book_rows = load_jsonl(BOOKF)
    results = load_results()
    if not pin or not book_rows:
        print("OPENING_VALUE — clv_history ou book_curves vide."); json.dump({'status':'empty'}, open(OUT,'w')); return 0
    if not results:
        print(f"OPENING_VALUE — {RESULTS} introuvable/vide."); json.dump({'status':'no_results'}, open(OUT,'w')); return 0

    by_book = {}
    for r in book_rows:
        by_book.setdefault(r.get('book', '?'), []).append(r)

    report = {'status': 'ok', 'mode': MODE, 'books': {}}
    print("="*66)
    print("OPENING VALUE — ouverture molle : gagne-t-on vraiment ? (par book)")
    if MODE == 'prospective':
        print("MODE prospective : référence = Pinnacle À L'INSTANT de l'ouverture.")
        print("Toute l'info utilisée est disponible au moment de miser -> ROI misable.")
    else:
        print("⚠️ MODE close : référence = CLÔTURE Pinnacle. Sélection sur le futur,")
        print("⚠️ chiffres NON misables (look-ahead). Diagnostic seul — ne pas publier.")
    print("="*66)

    for book, rows in by_book.items():
        flagged = []   # (profit, ev_open, odds, won)
        soft_found = 0; no_result = 0; n_eval = 0; n_stale = 0; n_no_ref = 0
        for br in rows:
            uid = br.get('uid')
            if uid not in pin: continue
            try:
                start = datetime.datetime.fromisoformat(str(pin[uid].get('commence_time','')).replace('Z','+00:00')).replace(tzinfo=None)
            except Exception:
                continue
            trunc = lambda c: [(dt, pr) for dt, pr in parse_curve(c) if dt <= start]
            pf, pd = fav_dog(trunc(pin[uid].get('home_curve')), trunc(pin[uid].get('away_curve')))
            bf, bd = fav_dog(trunc(br.get('home_curve')), trunc(br.get('away_curve')))
            if not pf or not pd or not bf or not bd: continue
            o_fav, o_dog = bf[0][1], bd[0][1]   # cotes d'OUVERTURE du book
            t_open = min(bf[0][0], bd[0][0])    # instant où CE book ouvre

            if MODE == 'prospective':
                # Pinnacle TEL QU'IL ÉTAIT à t_open : aucune information future.
                pf_at = [x for x in pf if x[0] <= t_open]
                pd_at = [x for x in pd if x[0] <= t_open]
                if not pf_at or not pd_at:
                    n_no_ref += 1; continue     # Pinnacle pas encore ouvert -> cf. hypothèse 6
                ref_f, ref_d = pf_at[-1][1], pd_at[-1][1]
                # Désaccord sur le favori évalué AU MÊME INSTANT (jamais sur la clôture).
                if abs(bf[0][1]-ref_f) > abs(bd[0][1]-ref_f): continue
            else:
                # DIAGNOSTIC SEUL : référence = clôture (information non disponible
                # au moment de miser). Chiffres non misables, ne pas publier.
                if abs(bf[-1][1]-pf[-1][1]) > abs(bd[-1][1]-pf[-1][1]): continue
                if (start - max(pf[-1][0], pd[-1][0])).total_seconds() / 60 > CLV_CLOSE_MAX_MINS:
                    n_stale += 1; continue
                ref_f, ref_d = pf[-1][1], pd[-1][1]

            n_eval += 1
            p_ref = (1/ref_f) / ((1/ref_f) + (1/ref_d))   # dévigage 2 voies
            ev_fav = o_fav * p_ref - 1
            ev_dog = o_dog * (1 - p_ref) - 1
            if max(ev_fav, ev_dog) <= EV_TH:    # pas d'ouverture molle
                continue
            soft_found += 1
            win_side = find_winner_side(br.get('home'), br.get('away'), parse_date(br.get('commence_time')), results)
            if win_side is None:
                no_result += 1; continue
            bh = trunc(br.get('home_curve'))
            fav_is_home = bh and bh[-1][1] == bf[-1][1]
            fav_won = (win_side == 'home') == fav_is_home
            if ev_fav >= ev_dog:
                odds, won = o_fav, fav_won
            else:
                odds, won = o_dog, (not fav_won)
            profit = (odds - 1) if won else -1.0
            flagged.append((profit, max(ev_fav, ev_dog), odds, won))

        n = len(flagged)
        if n == 0:
            report['books'][book] = {'flagged': 0, 'mode': MODE, 'closings_perimes_exclus': n_stale,
                                     'sans_reference_pinnacle': n_no_ref, 'matchs_evalues': n_eval,
                                     'ouvertures_molles': soft_found, 'sans_resultat': no_result}
            print(f"\n[{book}] 0 ouverture molle misable. "
                  f"(matchs évalués: {n_eval} | ouvertures molles détectées: {soft_found} | "
                  f"sans résultat dispo: {no_result})")
            continue
        profits = [x[0] for x in flagged]
        roi = mean(profits)
        wr = sum(1 for x in flagged if x[3]) / n
        ev_m = mean(x[1] for x in flagged) * 100
        odds_m = mean(x[2] for x in flagged)
        sd = math.sqrt(sum((p-roi)**2 for p in profits)/(n-1)) if n > 1 else 0
        se = sd/math.sqrt(n) if n else 0
        report['books'][book] = {'flagged': n, 'closings_perimes_exclus': n_stale, 'roi_pct': round(roi*100,2),
                                 'roi_ic95': [round((roi-1.96*se)*100,2), round((roi+1.96*se)*100,2)],
                                 'taux_victoire': round(wr,3), 'ev_open_moy_pct': round(ev_m,2),
                                 'cote_open_moy': round(odds_m,3)}
        print(f"\n[{book}] {n} ouvertures molles misées (jointes résultat)")
        print(f"   ROI RÉEL : {roi*100:+.1f}%  [IC95 {(roi-1.96*se)*100:+.1f} ; {(roi+1.96*se)*100:+.1f}]")
        print(f"   gagnées {wr*100:.0f}% | EV ouverture moy {ev_m:+.1f}% | cote moy {odds_m:.2f}")
        if n < 30:
            print(f"   -> n={n}<30, trop peu pour conclure.")
        elif (roi-1.96*se) > 0:
            print(f"   -> ROI significativement POSITIF : ouverture molle rentable sur {book}. ⚠️ vérifier limites de mise.")
        elif roi > 0:
            print(f"   -> positif mais IC inclut 0 : prometteur, accumuler.")
        else:
            print(f"   -> ROI négatif : l'ouverture molle ne gagne pas (marge/pertes l'emportent).")

    json.dump(report, open(OUT,'w'), ensure_ascii=False, indent=2)
    print("\n" + "="*66)
    return 0

if __name__ == '__main__':
    sys.exit(main())
