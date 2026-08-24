#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pm_calibration_track.py — Suivi de l'hypothèse GELÉE n°12.

L'HYPOTHÈSE, FIXÉE LE 24/08/2026 ET NON MODIFIABLE
Les marchés de prédiction sont mal calibrés dans la zone médiane :
    tranche 30–45 %  ->  SOUS-évaluée (le résultat arrive plus souvent que le prix)
    tranche 55–70 %  ->  SUR-évaluée
Observé ce jour-là, avant tout suivi :
    Polymarket  30–45 % : +5,2 pts (n=40) · 55–70 % : −2,8 pts (n=42)
    Kalshi      30–45 % : +7,2 pts (n=41) · 55–70 % : −4,7 pts (n=41)

POURQUOI ÇA MÉRITE UN SUIVI PLUTÔT QU'UNE CONCLUSION
Un marché de prédiction n'a PAS de marge : son prix est directement une
probabilité. Un biais y serait donc exploitable, contrairement à celui des
bookmakers que la marge absorbe — c'est la première piste de tout le projet
qui pointe vers quelque chose d'actionnable.
Mais avec ~40 observations par tranche, l'erreur type sur une proportion de
40 % vaut 7,8 points. Un écart de +5,2 est à moins d'une erreur type de zéro.
Et Polymarket et Kalshi ne sont PAS indépendants : ils s'accordent à 0,56 point
près, donc leur concordance ne double pas la preuve.

CE QUI EST GELÉ, ET NE DOIT PLUS BOUGER
  • les bornes des tranches (30–45 % et 55–70 %) ;
  • le sens attendu (sous- puis sur-évaluation) ;
  • la mesure : dernier prix STRICTEMENT pré-match, une observation par match
    et par côté ;
  • le seuil de validation : IC95 de l'écart excluant zéro, sur des données
    POSTÉRIEURES au gel.
Ajuster l'un de ces éléments après coup transformerait le test en recherche du
meilleur découpage — le mode d'erreur qui a produit quatre faux positifs dans
ce projet.

CE QUE LE SCRIPT AFFICHE À CHAQUE PASSAGE
  • l'échantillon HORS ÉCHANTILLON (postérieur au gel), seul décisif ;
  • l'échantillon d'origine, pour mémoire, clairement séparé ;
  • le nombre d'observations encore nécessaires pour trancher.

Env : DATE_GEL, OUT.
Usage : python scripts/pm_calibration_track.py
"""
import os
import sys
import json
import gzip
import math
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov              # noqa: E402
from results_join import ResultIndex  # noqa: E402

DATE_GEL = os.environ.get('DATE_GEL', '2026-08-24')
OUT = os.environ.get('OUT', 'pm_calibration_track.json')

# GELÉ — ne pas modifier.
TRANCHES = [(0.30, 0.45, '30 – 45 %', +1),   # +1 = sous-évaluation attendue
            (0.55, 0.70, '55 – 70 %', -1)]   # -1 = sur-évaluation attendue


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def ic_prop(v):
    """Wilson : reste dans [0,1] même sur petits effectifs, contrairement à
    l'approximation normale."""
    n = len(v)
    if n < 2:
        return None, None, None
    p = sum(v) / n
    z = 1.96
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    e = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - e) / d, (c + e) / d


def n_requis(p, ecart_pts):
    """Observations pour qu'un écart de cette taille exclue zéro à 95 %."""
    if ecart_pts <= 0:
        return None
    return int(math.ceil((1.96 ** 2) * p * (1 - p) / ((ecart_pts / 100) ** 2)))


def charger(pre):
    """Dernier prix STRICTEMENT pré-match, par (match, côté)."""
    ct_par_uid, noms = {}, {}
    for ligne in ov.iter_hist_lines('book'):
        try:
            r = json.loads(ligne)
        except Exception:
            continue
        u = r.get('uid')
        if u and u not in ct_par_uid:
            ct_par_uid[u] = _dt(r.get('commence_time'))
            noms[u] = (r.get('home_team') or r.get('home'),
                       r.get('away_team') or r.get('away'))

    dernier = {}
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
            # Kalshi n'écrit pas market_type : son collecteur ne suit que les
            # séries « vainqueur du match », donc tout tick est du bon type.
            if r.get('market_type') not in (None, 'match'):
                continue
            u, s, t = r.get('local_uid'), r.get('local_side'), _dt(r.get('ts'))
            m = r.get('mid')
            if not u or s not in ('home', 'away') or t is None or m is None:
                continue
            ct = ct_par_uid.get(u)
            if not ct or t >= ct:
                continue                    # coupe pré-match stricte
            try:
                m = float(m)
            except (TypeError, ValueError):
                continue
            if not (0.0 < m < 1.0):
                continue
            k = (u, s)
            if k not in dernier or t > dernier[k][0]:
                dernier[k] = (t, m, ct)
    return dernier, noms


def main():
    gel = datetime.date.fromisoformat(DATE_GEL)
    idx = ResultIndex()
    if not idx.n:
        print("❌ resultats_derived.json absent — lancer results_bridge.py.")
        return

    print()
    print("=" * 78)
    print("HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction")
    print(f"Gelée le {DATE_GEL} · tranches et sens FIXÉS, non modifiables")
    print("=" * 78)
    print("  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)")
    print("  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)")

    rapport = {}
    for pre, lab in (('pm_ticks', 'POLYMARKET'), ('kx_ticks', 'KALSHI')):
        dernier, noms = charger(pre)
        avant, apres = [], []
        for (u, s), (t, m, ct) in dernier.items():
            h, a = noms.get(u, (None, None))
            if not h or not a:
                continue
            w = idx.winner(h, a, ct)
            if w is None:
                continue
            gagne = 1 if ((w == 'home') == (s == 'home')) else 0
            (apres if ct.date() > gel else avant).append((m, gagne))

        print()
        print("=" * 78)
        print(f"{lab}")
        print("=" * 78)
        bloc = {}
        for periode, lot, titre in (('apres', apres, 'HORS ÉCHANTILLON (décisif)'),
                                    ('avant', avant, "origine (pour mémoire)")):
            print(f"\n  {titre} — {len(lot)} observation(s)")
            if not lot:
                continue
            print(f"  {'tranche':<14}{'n':>5}{'annoncé':>10}{'observé':>10}"
                  f"{'écart':>9}{'IC95 écart':>20}")
            print("  " + "-" * 68)
            for lo, hi, nom, sens in TRANCHES:
                g = [(p, w) for p, w in lot if lo <= p < hi]
                if len(g) < 15:
                    print(f"  {nom:<14}{len(g):>5}   trop peu")
                    continue
                ann = st.mean(p for p, _ in g)
                obs, l, h = ic_prop([w for _, w in g])
                ec = (obs - ann) * 100
                # L'IC de l'écart : on décale l'IC de la proportion observée.
                el, eh = (l - ann) * 100, (h - ann) * 100
                conclut = (el > 0) if sens > 0 else (eh < 0)
                marque = '  ✅' if conclut else ''
                if periode == 'apres':
                    bloc[nom] = {'n': len(g), 'annonce': round(ann * 100, 2),
                                 'observe': round(obs * 100, 2),
                                 'ecart_pts': round(ec, 2),
                                 'ic_ecart': [round(el, 2), round(eh, 2)],
                                 'conclut': bool(conclut)}
                print(f"  {nom:<14}{len(g):>5}{ann*100:>9.1f}%{obs*100:>9.1f}%"
                      f"{ec:>+8.1f}  [{el:>+6.1f} ; {eh:>+6.1f}]{marque}")
                if periode == 'apres' and not conclut:
                    req = n_requis(ann, abs(ec))
                    if req:
                        bloc[nom]['n_requis'] = req
                        print(f"  {'':<14}{'':>5}   il faudrait ~{req} obs pour "
                              f"trancher à cet écart ({max(0, req-len(g))} manquantes)")
        rapport[lab] = bloc

    print()
    print("=" * 78)
    concluants = [f"{m} {t}" for m, b in rapport.items()
                  for t, v in b.items() if v.get('conclut')]
    if concluants:
        print(f"→ {len(concluants)} tranche(s) concluante(s) hors échantillon :")
        for c in concluants:
            print(f"   {c}")
        print("  ⚠️ Polymarket et Kalshi ne sont PAS indépendants (écart médian")
        print("     0,56 pt) : deux confirmations ne valent pas deux preuves.")
    else:
        print("→ rien de concluant hors échantillon. Laisser l'échantillon grossir.")
    print("=" * 78)

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'date_gel': DATE_GEL,
        'tranches_gelees': [[lo, hi, nom, sens] for lo, hi, nom, sens in TRANCHES],
        'marches': rapport,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
