#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drift_predictability.py
-----------------------
Teste UNE question, proprement : la derive open->close des cotes Pinnacle
est-elle previsible, et combien de CLV capterait-on en misant le FAVORI
(ou l'outsider) DES L'OUVERTURE de la cote ?

Lecture seule. Source : clv_history.jsonl (courbes completes stockees par
fetch_clv quand STORE_FULL_CURVE=True). Aucune API, aucun quota.

IMPORTANT (a garder en tete en lisant le rapport) :
- Les courbes sont des cotes PINNACLE. Donc on teste si la cote SHARP derive
  de facon previsible. Si meme Pinnacle ne derive pas de facon exploitable,
  c'est mort. Si oui, ce serait un debut de piste -- mais ta mise reelle se
  ferait sur Betclic/Unibet, dont l'ouverture n'est pas capturee ici.
- "open" = premier point capture de la courbe, pas forcement la vraie
  ouverture du marche (OddsPapi peut commencer a capturer en cours de route).
- Le CLV n'est pas un profit garanti : il faut qu'il batte la marge que tu
  paies a l'ouverture, et que le book ne te limite pas.
"""
import json, os, sys, math
from statistics import mean, median

HIST = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
OUT  = os.environ.get('DRIFT_REPORT', 'drift_report.json')

GRASS = ['wimbledon', 'queen', 'halle', 'eastbourne', 'newport', 's-hertogenbosch',
         'stuttgart', 'mallorca', 'birmingham', 'nottingham']
CLAY  = ['french open', 'roland', 'monte', 'madrid', 'rome', 'barcelona', 'hamburg',
         'estoril', 'munich', 'bucharest', 'gstaad', 'kitzbuhel', 'umag', 'bastad',
         'geneva', 'lyon', 'rio', 'buenos aires', 'santiago', 'cordoba', 'houston',
         'charleston', 'stuttgart wta', 'strasbourg', 'rabat', 'parma', 'palermo']

def surface_of(t):
    tl = (t or '').lower()
    for k in CLAY:
        if k in tl: return 'clay'
    for k in GRASS:
        if k in tl: return 'grass'
    return 'hard'

def level_of(t):
    tl = (t or '').lower()
    return 'WTA' if tl.startswith('wta') else 'ATP'

def curve_open_close(curve):
    """curve = [[iso_ts, price], ...] -> (open, close, n_points) ou None."""
    if not curve: return None
    pts = []
    for p in curve:
        if not p or len(p) < 2: continue
        try:
            pr = float(p[1])
        except (TypeError, ValueError):
            continue
        if pr and pr > 1.0:
            pts.append((str(p[0]), pr))
    if len(pts) < 2:
        return None
    pts.sort(key=lambda x: x[0])
    return pts[0][1], pts[-1][1], len(pts)

def load_rows():
    rows = []
    if not os.path.exists(HIST):
        return rows
    with open(HIST, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows

def stats_block(xs):
    """Renvoie moyenne, mediane, ecart-type echantillon, IC95 de la moyenne, %positifs."""
    n = len(xs)
    if n == 0:
        return {'n': 0}
    m = mean(xs)
    med = median(xs)
    if n > 1:
        var = sum((x - m) ** 2 for x in xs) / (n - 1)
        sd = math.sqrt(var)
        se = sd / math.sqrt(n)
    else:
        sd = se = 0.0
    return {
        'n': n,
        'moyenne': round(m, 3),
        'mediane': round(med, 3),
        'ecart_type': round(sd, 3),
        'ic95_bas': round(m - 1.96 * se, 3),
        'ic95_haut': round(m + 1.96 * se, 3),
        'pct_positifs': round(100 * sum(1 for x in xs if x > 0) / n, 1),
    }

def main():
    rows = load_rows()

    if not rows:
        print("=" * 60)
        print("DRIFT PREDICTABILITY — 0 ligne dans", HIST)
        print("=" * 60)
        print("clv_history.jsonl est vide ou absent.")
        print("-> Declenche fetch_clv pour remplir les courbes, puis relance.")
        json.dump({'status': 'empty', 'source': HIST, 'n_matchs': 0},
                  open(OUT, 'w'), ensure_ascii=False, indent=2)
        return 0

    recs = []
    sans_courbe = 0
    courbe_trop_courte = 0
    for r in rows:
        hc = r.get('home_curve')
        ac = r.get('away_curve')
        if not hc or not ac:
            sans_courbe += 1
            continue
        ho = curve_open_close(hc)
        ao = curve_open_close(ac)
        if not ho or not ao:
            courbe_trop_courte += 1
            continue
        h_open, h_close, h_n = ho
        a_open, a_close, a_n = ao

        # favori a l'ouverture = prix le plus bas a l'open
        if h_open <= a_open:
            fav_open, fav_close = h_open, h_close
            dog_open, dog_close = a_open, a_close
            fav_side = 'home'
        else:
            fav_open, fav_close = a_open, a_close
            dog_open, dog_close = h_open, h_close
            fav_side = 'away'

        ip_f, ip_d = 1.0 / fav_open, 1.0 / dog_open
        margin = ip_f + ip_d - 1.0           # marge bookmaker a l'ouverture
        fav_prob = ip_f / (ip_f + ip_d)       # proba favori devigee a l'open

        # derive : <0 = la cote a RACCOURCI (le cote s'est renforce)
        drift_fav = (fav_close / fav_open - 1.0) * 100.0
        drift_dog = (dog_close / dog_open - 1.0) * 100.0
        # CLV si on MISE a l'ouverture : >0 = on a battu la cloture
        clv_fav = (fav_open / fav_close - 1.0) * 100.0
        clv_dog = (dog_open / dog_close - 1.0) * 100.0

        recs.append({
            'uid': r.get('uid'),
            'tournoi': r.get('tournament'),
            'surface': surface_of(r.get('tournament', '')),
            'niveau': level_of(r.get('tournament', '')),
            'fav_side': fav_side,
            'fav_open': round(fav_open, 3),
            'fav_close': round(fav_close, 3),
            'fav_prob_open': round(fav_prob, 4),
            'margin_open_pct': round(margin * 100, 2),
            'drift_fav_pct': round(drift_fav, 3),
            'drift_dog_pct': round(drift_dog, 3),
            'clv_fav_pct': round(clv_fav, 3),
            'clv_dog_pct': round(clv_dog, 3),
            'n_points': h_n + a_n,
        })

    if not recs:
        print("=" * 60)
        print("DRIFT PREDICTABILITY — aucun match analysable")
        print("=" * 60)
        print(f"Lignes lues          : {len(rows)}")
        print(f"Sans courbe          : {sans_courbe}")
        print(f"Courbe < 2 points    : {courbe_trop_courte}")
        print("-> fetch_clv doit tourner avec STORE_FULL_CURVE=True sur des")
        print("   matchs ayant assez de points captures.")
        json.dump({'status': 'no_curves', 'lignes': len(rows),
                   'sans_courbe': sans_courbe, 'courbe_trop_courte': courbe_trop_courte},
                  open(OUT, 'w'), ensure_ascii=False, indent=2)
        return 0

    n = len(recs)
    drift_fav = [r['drift_fav_pct'] for r in recs]
    clv_fav   = [r['clv_fav_pct']   for r in recs]
    clv_dog   = [r['clv_dog_pct']   for r in recs]
    marges    = [r['margin_open_pct'] for r in recs]

    s_drift = stats_block(drift_fav)
    s_clv_f = stats_block(clv_fav)
    s_clv_d = stats_block(clv_dog)
    marge_moy = mean(marges)

    # Buckets par proba favori a l'ouverture
    buckets = [
        ('grand favori (>=80%)', lambda p: p >= 0.80),
        ('favori marque (65-80%)', lambda p: 0.65 <= p < 0.80),
        ('favori leger (55-65%)', lambda p: 0.55 <= p < 0.65),
        ('quasi pile-ou-face (<55%)', lambda p: p < 0.55),
    ]
    bucket_report = {}
    for label, cond in buckets:
        sub = [r for r in recs if cond(r['fav_prob_open'])]
        if not sub:
            bucket_report[label] = {'n': 0}
            continue
        bucket_report[label] = {
            'n': len(sub),
            'drift_fav': stats_block([r['drift_fav_pct'] for r in sub]),
            'clv_fav': stats_block([r['clv_fav_pct'] for r in sub]),
        }

    # Correlation proba_open <-> drift (le favori est-il d'autant plus raccourci ?)
    ps = [r['fav_prob_open'] for r in recs]
    ds = [r['drift_fav_pct'] for r in recs]
    if n > 2:
        mp, md = mean(ps), mean(ds)
        cov = sum((p - mp) * (d - md) for p, d in zip(ps, ds))
        vp = sum((p - mp) ** 2 for p in ps)
        vd = sum((d - md) ** 2 for d in ds)
        corr = cov / math.sqrt(vp * vd) if vp > 0 and vd > 0 else 0.0
    else:
        corr = 0.0

    report = {
        'status': 'ok',
        'n_matchs': n,
        'marge_open_moyenne_pct': round(marge_moy, 2),
        'derive_favori_pct': s_drift,
        'clv_favori_joue_open_pct': s_clv_f,
        'clv_outsider_joue_open_pct': s_clv_d,
        'corr_proba_open_vs_derive': round(corr, 3),
        'par_niveau_de_favori': bucket_report,
        'rappel': "CLV>0 = on bat la cloture Pinnacle. Pour profiter il faut "
                  "CLV moyen > ~marge/2 ET un book qui ne te limite pas.",
    }
    json.dump(report, open(OUT, 'w'), ensure_ascii=False, indent=2)

    # ---- Sortie lisible ----
    print("=" * 64)
    print(f"DRIFT PREDICTABILITY — {n} matchs avec courbe exploitable")
    print("=" * 64)
    print(f"Marge Pinnacle moyenne a l'ouverture : {marge_moy:.2f}%")
    print(f"Correlation proba_open <-> derive    : {corr:+.3f}")
    print()
    print("DERIVE DU FAVORI (open->close, <0 = raccourcit)")
    print(f"  moyenne {s_drift['moyenne']:+.2f}%  mediane {s_drift['mediane']:+.2f}%"
          f"  | raccourcit dans {100 - s_drift['pct_positifs']:.0f}% des cas")
    print()
    print(">>> TON IDEE : miser le FAVORI des l'ouverture <<<")
    print(f"  CLV moyen : {s_clv_f['moyenne']:+.2f}%  "
          f"[IC95 {s_clv_f['ic95_bas']:+.2f} ; {s_clv_f['ic95_haut']:+.2f}]")
    print(f"  positif sur {s_clv_f['pct_positifs']:.0f}% des matchs")
    seuil = marge_moy / 2.0
    if s_clv_f['ic95_bas'] > seuil:
        verdict = f"SIGNAL : CLV bat le seuil de marge (~{seuil:.2f}%). A creuser."
    elif s_clv_f['ic95_bas'] > 0:
        verdict = (f"FAIBLE : CLV>0 mais sous le seuil de marge (~{seuil:.2f}%) "
                   f"-> pas de profit net.")
    else:
        verdict = "NUL : l'IC95 inclut 0 -> aucune derive favori exploitable."
    print(f"  VERDICT : {verdict}")
    print()
    print("  (comparaison) miser l'OUTSIDER a l'open : "
          f"CLV {s_clv_d['moyenne']:+.2f}% sur {s_clv_d['n']} matchs")
    print()
    print("PAR NIVEAU DE FAVORI (proba devigee a l'open) :")
    for label, b in bucket_report.items():
        if b.get('n', 0) == 0:
            print(f"  - {label:26s} : 0 match")
            continue
        cf = b['clv_fav']
        print(f"  - {label:26s} : n={b['n']:3d}  "
              f"CLV {cf['moyenne']:+.2f}% [IC95 {cf['ic95_bas']:+.2f};{cf['ic95_haut']:+.2f}]")
    print("=" * 64)
    if n < 150:
        print(f"NB : {n} matchs, c'est trop peu pour conclure. Vise quelques centaines.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
