#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
results_bridge.py — Alimente les études en résultats depuis la source QUI MARCHE.

PROBLÈME RÉSOLU (16/08/2026)
Deux workflows quotidiens de résultats produisent un fichier VIDE depuis des
semaines, sans jamais échouer :
  - update_results.yml      -> resultats.json       "count": 0   (Sackmann
    injoignable depuis le runner GitHub : egress bloqué -- déjà constaté)
  - update_results_fast.yml -> resultats_fast.json  "count": 0
Or ce sont EXACTEMENT les deux seuls fichiers lus par calibration_buckets.py et
opening_value.py. Résultat : ces deux études répondent "Aucun résultat" à chaque
run et calibration_buckets_report.json vaut {"status": "no_results"} -- alors que
l'hypothèse gelée n°1 (calibration 2,20-3,50, résidu +5,8 pts) repose dessus.

Pendant ce temps, DEUX autres sources sont pleines et à jour :
  - resultats_oddspapi.json  (1057 matchs, settlement API : noms + vainqueur)
  - set_results.json         (1762 matchs, vainqueur match + set1 + set2)
C'est le même symptôme que les crises précédentes : rien ne plante, tout est
vide. Ce pont convertit la source vivante vers le format canonique attendu
(liste 'results' avec home_team/away_team/winner_code/date), pour que les
études repartent SANS toucher à leur logique.

SORTIE : resultats_derived.json  (à passer via RESULTS= aux études)

Env : SRC_ODDSPAPI (resultats_oddspapi.json), SRC_SET (set_results.json),
      OUT (resultats_derived.json).
"""
import os, sys, json, re, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov

SRC_ODDSPAPI = os.environ.get('SRC_ODDSPAPI', 'resultats_oddspapi.json')
SRC_SET      = os.environ.get('SRC_SET', 'set_results.json')
OUT          = os.environ.get('OUT', 'resultats_derived.json')


def _date_of(r):
    """Date au format YYYY-MM-DD depuis resolved_at (règlement = jour du match
    à quelques heures près ; les études tolèrent DATE_TOL=3 jours)."""
    s = str(r.get('resolved_at') or '')[:10]
    try:
        datetime.date.fromisoformat(s)
        return s
    except Exception:
        return None


def from_oddspapi(path):
    if not os.path.exists(path):
        return []
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception:
        return []
    rows = d.values() if isinstance(d, dict) else d
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        h, a, w = r.get('home'), r.get('away'), r.get('winner')
        if not h or not a or w not in ('home', 'away'):
            continue
        out.append({
            'home_team': h, 'away_team': a,
            'winner': r.get('winner_name') or (h if w == 'home' else a),
            'winner_code': 1 if w == 'home' else 2,
            'date': _date_of(r),
            'tournament': r.get('tournament') or '',
            'sets': r.get('sets') or '',
            'set1': r.get('set1'), 'set2': r.get('set2'),
            'source': 'oddspapi_settlement',
            'provisional': bool(r.get('provisional', True)),
        })
    return out


def _index_curves():
    """{uid: (home, away, commence, tournoi)} depuis les courbes.

    INDISPENSABLE — BUG CORRIGÉ LE 16/08/2026.
    La version précédente reconstruisait home/away depuis l'ORDRE du slug
    'tournoi_joueurA_vs_joueurB'. Or cet ordre ne suit PAS home/away : mesuré,
    il diverge dans 2634 cas sur 2700. Le champ v['match'] ('home' ou 'away')
    de set_results.json désigne, lui, le VRAI home. Croiser les deux revenait
    donc à tirer le vainqueur à pile ou face : vérification contre
    resultats_oddspapi.json -> 16 corrects et 16 INVERSÉS sur 32 contrôlables,
    soit exactement 50 %.
    Les clés de set_results.json sont en réalité des uid (60 % se retrouvent
    tels quels dans les courbes) : on y lit donc le home/away réel, et une
    entrée non résolue est ÉCARTÉE plutôt que devinée.
    """
    idx = {}
    for src in ('book_curves.jsonl', 'book_curves_live.jsonl'):
        try:
            lines = ov.open_curves(src, verbose=False)
        except FileNotFoundError:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except Exception:
                continue
            u = r.get('uid')
            if u and u not in idx:
                idx[u] = (r.get('home_team') or r.get('home'),
                          r.get('away_team') or r.get('away'),
                          str(r.get('commence_time') or '')[:10],
                          r.get('tournament') or '')
    return idx


def from_set_results(path):
    """Complément depuis set_results.json, home/away résolus via les courbes.
    Toute entrée dont l'uid est introuvable est ÉCARTÉE : mieux vaut un
    échantillon plus petit qu'un vainqueur sur deux inversé."""
    if not os.path.exists(path):
        return []
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception:
        return []
    curves = _index_curves()
    out = []
    global _SKIPPED
    _SKIPPED = 0
    for k, v in (d.items() if isinstance(d, dict) else []):
        if not isinstance(v, dict):
            continue
        w = v.get('match')
        if w not in ('home', 'away'):
            continue
        got = curves.get(str(k))
        if not got:
            _SKIPPED += 1
            continue
        h, a, date, tour = got
        if not h or not a:
            _SKIPPED += 1
            continue
        out.append({
            'home_team': h, 'away_team': a,
            'winner': h if w == 'home' else a,
            'winner_code': 1 if w == 'home' else 2,
            'date': date or None,
            'tournament': tour,
            'set1': v.get('set1'), 'set2': v.get('set2'),
            'source': 'set_results',
            'provisional': True,
        })
    return out


_SKIPPED = 0


def _key(r):
    def n(s):
        return re.sub(r'[^a-z]', '', str(s).lower())
    return tuple(sorted((n(r['home_team']), n(r['away_team']))))


def main():
    prim = from_oddspapi(SRC_ODDSPAPI)          # avec date : prioritaire
    comp = from_set_results(SRC_SET)
    seen = {_key(r) for r in prim}
    kept = [r for r in comp if _key(r) not in seen]
    res = prim + kept
    payload = {
        'updated': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
        'generated_at': datetime.datetime.utcnow().isoformat(),
        'source': f'{SRC_ODDSPAPI} + {SRC_SET} (via results_bridge.py)',
        'count': len(res),
        'results': res,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"RESULTS_BRIDGE -> {OUT}")
    print(f"  {len(prim)} depuis {SRC_ODDSPAPI} (avec date)")
    print(f"  {len(kept)} ajoutés depuis {SRC_SET} (home/away résolus via les courbes)")
    if _SKIPPED:
        print(f"  {_SKIPPED} entrées de {SRC_SET} ÉCARTÉES (uid introuvable dans les "
              f"courbes -> home/away indéterminable, on refuse de deviner)")
    print(f"  TOTAL {len(res)} résultats exploitables")
    if not res:
        raise SystemExit("❌ 0 résultat produit — les DEUX sources sont vides, à vérifier.")


if __name__ == '__main__':
    main()
