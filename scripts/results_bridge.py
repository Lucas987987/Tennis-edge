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
import os, json, re, datetime

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


_SLUG = re.compile(r'^(?P<tour>.+?)_(?P<home>.+?)_vs_(?P<away>.+)$')


def _unslug(s):
    return ' '.join(w.capitalize() for w in str(s).replace('-', ' ').split('_') if w)


def from_set_results(path):
    """Complément : set_results.json est plus fourni (1762) mais n'a que la clé
    slug 'tournoi_home_vs_away' -- on en réextrait les noms. Pas de date
    disponible : les études sautent alors la contrainte de date (r['_d'] None)."""
    if not os.path.exists(path):
        return []
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception:
        return []
    out = []
    for k, v in (d.items() if isinstance(d, dict) else []):
        m = _SLUG.match(str(k))
        if not m or not isinstance(v, dict):
            continue
        w = v.get('match')
        if w not in ('home', 'away'):
            continue
        h, a = _unslug(m.group('home')), _unslug(m.group('away'))
        if not h or not a:
            continue
        out.append({
            'home_team': h, 'away_team': a,
            'winner': h if w == 'home' else a,
            'winner_code': 1 if w == 'home' else 2,
            'date': None,
            'tournament': _unslug(m.group('tour')),
            'set1': v.get('set1'), 'set2': v.get('set2'),
            'source': 'set_results',
            'provisional': True,
        })
    return out


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
    print(f"  {len(kept)} ajoutés depuis {SRC_SET} (sans date, non doublons)")
    print(f"  TOTAL {len(res)} résultats exploitables")
    if not res:
        raise SystemExit("❌ 0 résultat produit — les DEUX sources sont vides, à vérifier.")


if __name__ == '__main__':
    main()
