#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal_clv.py — CLV réalisé des écarts publiés sur le canal.

C'EST LA MÉTRIQUE DU CANAL. Pour chaque opérateur signalé « en retard » dans un
message publié, on compare le prix affiché à ce moment-là à la CLÔTURE réelle du
MÊME opérateur (dernier prix pré-match). Si le prix signalé était plus élevé que
sa clôture, l'écart s'est bien refermé : CLV positif.

Exemple vécu : winamax.fr signalé à 2.30 sur Talia Gibson, descendu à 2.00 avant
le match -> CLV = 2.30/2.00 - 1 = +15 %.

Deux garanties méthodologiques :
  • le prix comparé est celui du MÊME opérateur (pas une clôture sharp), donc on
    mesure bien le refermement de l'écart, sans effet de marge entre books ;
  • seuls les points PRÉ-MATCH sont utilisés (aucun point in-play ne peut entrer
    dans la clôture, sinon le résultat contaminerait la mesure).

Sortie : CLV médian, % d'écarts qui se sont refermés, détail par opérateur et
par ampleur d'écart annoncé. Aucun pronostic, aucune notion de gain.

Env : LOG (canal_public_log.jsonl), CURVES (book_curves_live.jsonl,
      séparés par virgule pour ajouter l'historique), MIN_N (5), OUT (csv optionnel).
"""
import os, json, glob, csv, datetime, statistics as st

LOG    = os.environ.get('LOG', 'canal_public_log.jsonl')
CURVES = [c.strip() for c in os.environ.get(
    'CURVES', 'book_curves_live.jsonl,book_curves.jsonl').split(',') if c.strip()]
MIN_N  = int(os.environ.get('MIN_N', '5'))
OUT    = os.environ.get('OUT', 'canal_clv_detail.csv')


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def load_closes():
    """{(uid, book, side_name): dernier prix PRÉ-MATCH}"""
    closes = {}
    for src in CURVES:
        for path in glob.glob(src):
            if not os.path.exists(path):
                continue
            for line in open(path, encoding='utf-8'):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                ct = _dt(r.get('commence_time'))
                if not ct:
                    continue
                home = r.get('home_team') or r.get('home') or ''
                away = r.get('away_team') or r.get('away') or ''
                for key, name in (('home_curve', home), ('away_curve', away)):
                    pts = [(_dt(p[0]), p[1]) for p in (r.get(key) or []) if _dt(p[0]) and p[1] and p[1] > 1]
                    pts = sorted(p for p in pts if p[0] < ct)      # PRÉ-MATCH uniquement
                    if pts and name:
                        closes[(r.get('uid'), r.get('book'), name)] = pts[-1][1]
    return closes


def main():
    if not os.path.exists(LOG):
        print(f"{LOG} introuvable"); return
    closes = load_closes()
    rows = []
    for line in open(LOG, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        joueur = m.get('joueur')
        for entry in (m.get('retards') or []):
            try:
                book, prix, ecart = entry[0], float(entry[1]), float(entry[2])
            except Exception:
                continue
            cl = closes.get((m.get('uid'), book, joueur))
            if not cl:
                continue
            rows.append(dict(
                date=str(m.get('t'))[:16], joueur=joueur, book=book,
                prix_signale=prix, cloture=cl,
                ecart_annonce=round(ecart, 1),
                clv=round((prix/cl - 1) * 100, 1)))
    if not rows:
        print("Aucun écart signalé n'a encore de clôture connue "
              "(matchs trop récents, ou courbes à reconstruire).")
        return

    clv = [r['clv'] for r in rows]
    pos = 100 * sum(1 for x in clv if x > 0) / len(clv)
    print(f"=== CLV RÉALISÉ DES ÉCARTS PUBLIÉS ===")
    print(f"n = {len(rows)} écarts signalés, sur {len(set(r['joueur'] for r in rows))} matchs")
    print(f"CLV médian : {st.median(clv):+.1f}%  |  moyen : {st.mean(clv):+.1f}%")
    print(f"Écarts qui se sont refermés : {pos:.0f}%")

    byb = {}
    for r in rows:
        byb.setdefault(r['book'], []).append(r['clv'])
    print(f"\nPar opérateur (min {MIN_N} écarts) :")
    for b, v in sorted(byb.items(), key=lambda x: -len(x[1])):
        if len(v) < MIN_N:
            continue
        p = 100 * sum(1 for x in v if x > 0) / len(v)
        print(f"  {b:14} n={len(v):3} | CLV médian {st.median(v):+5.1f}% | refermés {p:3.0f}%")

    print("\nPar ampleur de l'écart annoncé :")
    for lo, hi, lab in [(0, 5, '2-5%'), (5, 10, '5-10%'), (10, 20, '10-20%'), (20, 999, '20%+')]:
        g = [r['clv'] for r in rows if lo <= r['ecart_annonce'] < hi]
        if len(g) < 3:
            continue
        p = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  {lab:7} n={len(g):3} | CLV médian {st.median(g):+5.1f}% | refermés {p:3.0f}%")

    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in sorted(rows, key=lambda x: -x['clv']):
            w.writerow(r)
    print(f"\nDétail écrit dans {OUT} ({len(rows)} lignes)")


if __name__ == '__main__':
    main()
