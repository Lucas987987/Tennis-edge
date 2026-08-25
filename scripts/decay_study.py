#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decay_study.py — Combien de CLV reste-t-il selon la latence d'exécution ?

PISTE GELÉE LE 2026-08-25. Pour chaque alerte (logged_at), on mesure le prix
du côté steamé chez chaque book soft à T+0/2/10/30/60 min, et le CLV
atteignable = (prix à T+d / closing - 1). C'est la quantification de la
course : la vraie fenêtre d'action, et la correction de latence du ROI.
Mesure descriptive (pas de H0) — médianes + n, coupées au pré-match.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
import json
import statistics as st
import pistes_common as pc

DELTAS = (0, 2, 10, 30, 60)
SOFTS_EXCLUS = {'pinnacle', 'betfair-ex'}


def cle_match(home, away, jour):
    """Clé robuste noms+jour — les uids des alertes suivent une 4e
    convention (slug tronqué à ~45 caractères) : toute jointure par uid est
    condamnée. On rejoue la leçon de results_join : jetons de noms triés."""
    import unicodedata
    def norm(x):
        x = unicodedata.normalize('NFKD', str(x or '')).encode('ascii', 'ignore').decode()
        return ' '.join(sorted(w for w in x.lower().replace('-', ' ').split() if len(w) > 1))
    return (frozenset((norm(home), norm(away))), str(jour or '')[:10])


def charge_alertes(max_n=400):
    out = []
    if not os.path.exists('odds_alerts_log.jsonl'):
        print('⚠️ odds_alerts_log.jsonl absent.')
        return out
    for l in open('odds_alerts_log.jsonl', encoding='utf-8'):
        try:
            a = json.loads(l)
            cote_steame = ('home' if float(a.get('mv_home_pct', 0))
                           <= float(a.get('mv_away_pct', 0)) else 'away')
            out.append({'cle': cle_match(a.get('home'), a.get('away'),
                                          a.get('commence_time')),
                        'ts': a['logged_at'],
                        'ct': a.get('commence_time'), 'side': cote_steame})
        except (ValueError, KeyError, TypeError):
            continue
    return out[-max_n:]                    # les plus récentes, budget borné


def main():
    pc.entete('PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE')
    alertes = charge_alertes()
    cles = {a['cle'] for a in alertes}
    # une seule passe sur hist, on ne garde que les matchs utiles
    courbes = {}
    for r in pc.iter_hist('book'):
        c = cle_match(r.get('home'), r.get('away'), r.get('commence_time'))
        if c in cles and r.get('book') not in SOFTS_EXCLUS:
            courbes.setdefault(c, {})[r['book']] = r
    par_delta = {}                       # (tranche_lead, delta) -> [clv]
    n_alertes_utiles = 0
    for a in alertes:
        bks = courbes.get(a['cle'])
        if not bks:
            continue
        try:
            t0 = datetime.datetime.fromisoformat(pc.ts_norm(a['ts']))
        except ValueError:
            continue
        touche = False
        try:
            lead_h = (datetime.datetime.fromisoformat(pc.ts_norm(a['ct']))
                      - t0).total_seconds() / 3600
        except (ValueError, TypeError):
            continue
        tranche = ('<1h' if lead_h < 1 else
                   '1-6h' if lead_h < 6 else '>6h')
        for r in bks.values():
            cle = f"{a['side']}_curve"
            close = pc.closing_prematch(r.get(cle), r.get('commence_time'))
            if not close:
                continue
            for d in DELTAS:
                td = (t0 + datetime.timedelta(minutes=d)).isoformat()
                v = pc.val_at(r.get(cle), td, r.get('commence_time'))
                if v:
                    par_delta.setdefault((tranche, d), []).append(
                        (v / close - 1) * 100)
                    touche = True
        n_alertes_utiles += touche
    print(f'  {n_alertes_utiles} alertes appariées à au moins un book soft')
    if n_alertes_utiles < 30:
        print('  trop tôt (<30 alertes appariées).')
        return
    # La moyenne globale MENT ici : une alerte à 13 min du match n'a plus de
    # jus, une alerte à J-1 en a — on segmente par avance (leçon piste 5 :
    # <1h = 69 % de retournements).
    for tranche in ('>6h', '1-6h', '<1h'):
        print(f'  — alertes à {tranche} du coup d\'envoi —')
        for d in DELTAS:
            vals = par_delta.get((tranche, d)) or []
            if len(vals) < 30:
                continue
            pos = sum(1 for v in vals if v > 0)
            print(f'    T+{d:>2}min : CLV atteignable médian '
                  f'{st.median(vals):+.1f}% | {100 * pos / len(vals):.0f}% '
                  f'positifs | n={len(vals)}')
    print('  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —')
    print("  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.")


if __name__ == '__main__':
    main()
