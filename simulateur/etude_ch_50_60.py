#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_ch_50_60.py — CHALLENGER, FAVORI ANNONCÉ ENTRE 50 ET 60 % : TROP CONFIANT ? (22/11/2026, paquet 350, demande de
Lucas : « A et B »).

CONSTAT (nos pronostics en direct du 22/10 au 22/11/2026) : en Challenger, quand le favori est annoncé entre 50 et
60 %, il gagne 51,5 % des matchs pour 54,8 % annoncés (427 matchs : pas significatif). Ailleurs le Challenger est bien
calibré (64,5 % annoncés, 64,4 % gagnés). Question : faut-il, dans cette tranche seulement, rapprocher le % de 50 % ?

DONNÉES : la production elle-même (controle_candidates.charger) : dernier % figé avant le début, vainqueur, sans
abandon ni forfait. La tranche est définie par le % annoncé, connu avant le match.

RÈGLE ÉCRITE LE 22/11/2026, AVANT DE VOIR LE MOINDRE MATCH DE JUGEMENT (ne pas la modifier après coup) :
  • population : Challenger, favori annoncé ≥ 50 % et < 60 % ;
  • variante : logit du favori + δ (δ < 0 : moins confiant), grille δ = −0,4 · −0,3 · −0,2 · −0,15 · −0,1 · −0,05 · 0 ·
    0,05 · 0,1 ; mesure : log loss du vainqueur sur les matchs de la tranche ;
  • APPRENTISSAGE : matchs commencés jusqu'au 22/11/2026 inclus (δ choisi là ; δ = 0 : rien à juger) ;
    JUGEMENT : matchs à partir du 23/11/2026, une seule fois, quand il y en a ≥ 1 000 (avant : « pas encore
    jugeable », rien n'est conclu) ;
  • RETENU si, sur le jugement : gain ≥ 0,001 par rapport à la production, δ réappris sur le jugement du même signe
    que δ appris, et gain significatif (test apparié par match, unilatéral, 5 %) ;
  • ce script n'écrit qu'un rapport : rien ne change dans les pronostics. Si c'est retenu, la mise en place (sans
    marche à 60 %, par exemple en atténuant δ près des bords) passe par un paquet à part avec sa règle de retrait.
DIAGNOSTIC (ne décide rien) : annoncé / gagné par tranche de 10 points, Challenger, ATP et WTA, sur chaque période.
Sortie : simulateur/rapport_ch_50_60.json (aucun nom, aucune cote). Usage : python simulateur/etude_ch_50_60.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import controle_candidates as CC  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_ch_50_60.json')
GRILLE = (-0.4, -0.3, -0.2, -0.15, -0.1, -0.05, 0.0, 0.05, 0.1)
COUPURE = '2026-11-23'
N_MIN, GAIN_MIN, Z_UNI = 1000, 0.001, 1.6449
BAS, HAUT = 0.5, 0.6
TRANCHES = ((.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01))


def favori(x):
    """(% du favori, 1 si le favori a gagné)."""
    if x['p'] >= .5:
        return x['p'], x['y']
    return 1 - x['p'], 1 - x['y']


def dans_tranche(x):
    return x['circuit'] == 'CH' and BAS <= favori(x)[0] < HAUT


def pertes(X, delta):
    out = []
    for x in X:
        q, y = favori(x)
        out.append(CC._ll(CC._sg(CC._lg(q) + delta), y))
    return out


def ll(X, delta):
    v = pertes(X, delta)
    return sum(v) / len(v) if v else None


def meilleur(X):
    return min(GRILLE, key=lambda d: (ll(X, d), abs(d))) if X else 0.0


def diagnostic(X):
    out = {}
    for c in ('CH', 'ATP', 'WTA'):
        for a, b in TRANCHES:
            Y = [favori(x) for x in X if x['circuit'] == c and a <= favori(x)[0] < b]
            if Y:
                out.setdefault(c, []).append({'tranche': f'{int(100 * a)}–{min(100, int(100 * b))} %', 'matchs': len(Y),
                                              'annonce_pct': round(100 * sum(q for q, _ in Y) / len(Y), 1),
                                              'gagne_pct': round(100 * sum(y for _, y in Y) / len(Y), 1)})
    return out


def etudier(X):
    A = [x for x in X if dans_tranche(x) and x['debut'] < COUPURE]
    J = [x for x in X if dans_tranche(x) and x['debut'] >= COUPURE]
    d = meilleur(A)
    doc = {'apprentissage': {'matchs': len(A), 'delta': d,
                             'log_loss_production': round(ll(A, 0.0), 5) if A else None,
                             'log_loss_variante': round(ll(A, d), 5) if A else None},
           'jugement': {'matchs': len(J)}}
    if d == 0.0:
        doc['verdict'] = "rien à juger (δ appris = 0 : la production est déjà la meilleure sur l'apprentissage)"
        return doc
    if len(J) < N_MIN:
        doc['verdict'] = f'pas encore jugeable ({len(J)} matchs jugés sur {N_MIN})'
        return doc
    p0, p1 = pertes(J, 0.0), pertes(J, d)
    g = [a - b for a, b in zip(p0, p1)]
    n, moy = len(g), sum(g) / len(g)
    et = math.sqrt(sum((v - moy) ** 2 for v in g) / (n - 1) / n) if n > 1 else float('inf')
    dj = meilleur(J)
    doc['jugement'].update({'log_loss_production': round(sum(p0) / n, 5), 'log_loss_variante': round(sum(p1) / n, 5),
                            'gain': round(moy, 5), 'erreur_type': round(et, 5), 'delta_rejuge': dj})
    raisons = []
    if moy < GAIN_MIN:
        raisons.append(f'gain sous {GAIN_MIN}')
    if dj * d <= 0:
        raisons.append('δ réappris pas du même signe')
    if not et or moy / et < Z_UNI:
        raisons.append('gain pas significatif')
    doc['verdict'] = 'RETENU' if not raisons else 'NON RETENU'
    doc['raisons'] = raisons
    return doc


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    X = CC.charger(racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), 'paquet': 350,
           'regle': ("Challenger, favori annoncé 50–60 % ; logit du favori + δ ; δ appris jusqu'au 22/11/2026, jugé à "
                     "partir du 23/11/2026 sur ≥ 1 000 matchs ; retenu si gain ≥ 0,001, même signe, significatif. "
                     "Rien ne change dans les pronostics."),
           **etudier(X),
           'diagnostic': {'apprentissage': diagnostic([x for x in X if x['debut'] < COUPURE]),
                          'jugement': diagnostic([x for x in X if x['debut'] >= COUPURE])}}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    a = doc['apprentissage']
    print(f"Challenger, favori 50–60 % — apprentissage : {a['matchs']} matchs, δ = {a['delta']} "
          f"(log loss {a['log_loss_production']} → {a['log_loss_variante']}) · jugement : {doc['jugement']['matchs']} matchs")
    print(f"Verdict : {doc['verdict']}")
    for t in (doc['diagnostic']['apprentissage'].get('CH') or []):
        print(f"  CH {t['tranche']} : {t['matchs']} matchs, annoncé {t['annonce_pct']} %, gagné {t['gagne_pct']} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
