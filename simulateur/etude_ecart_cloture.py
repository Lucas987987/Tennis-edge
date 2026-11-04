#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_ecart_cloture.py — LOUPE (04/11/2026, question de Lucas) : quand notre % (Elo + signaux adoptés, appris sur
2016–2022) s'écarte de la clôture Pinnacle (sans marge), qui a raison ? Constat chiffré, PAS un conseil : la cote
n'entre jamais dans l'algo, elle sert ici à mesurer après coup.

Population : ATP et WTA 2023 → 2026 (le Challenger n'a pas de clôtures dans tennis-data), matchs appariés.
Cas « écart » : notre probabilité pour un joueur dépasse celle de Pinnacle d'au moins SEUIL (5 points) ; le joueur
« vu plus fort par nous » est classé favori ou outsider selon Pinnacle.
Mesures : réussite réelle du joueur contre la probabilité Pinnacle (moyenne) et contre la nôtre ; rendement à la COTE
JUSTE Pinnacle (sans marge) = moyenne(gagné / p_pinnacle) − 1 — avec la marge réelle d'un bookmaker, c'est moins.
RÈGLE FIXÉE AVANT DE REGARDER : un cas n'est noté « au-dessus de la clôture » que si le réel dépasse la probabilité
Pinnacle avec z ≥ 2 sur au moins 300 matchs ; sinon « rien de solide ». Aucune conclusion de pari dans ce rapport.
Usage : python simulateur/etude_ecart_cloture.py /tmp/sackmann .
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_pistes_tournoi as EPT  # noqa: E402
import etude_signaux_combines as ESC  # noqa: E402

COUPURE = dt.date(2023, 1, 1)
SEUILS = (0.05, 0.10)
MIN_N = 300
SORTIE = os.path.join(ICI, 'rapport_ecart_cloture.json')


def bloc(L):
    """L : [(p_nous, p_pin, gagne)] pour le joueur vu plus fort par nous."""
    n = len(L)
    if not n:
        return None
    pin = sum(x[1] for x in L) / n
    reel = sum(x[2] for x in L) / n
    z = (reel - pin) / math.sqrt(max(pin * (1 - pin), 1e-9) / n)
    rend = sum((x[2] / x[1]) for x in L) / n - 1
    return {'matchs': n, 'nous_pct': round(100 * sum(x[0] for x in L) / n, 1), 'pinnacle_pct': round(100 * pin, 1),
            'reel_pct': round(100 * reel, 1), 'z': round(z, 2), 'rendement_cote_juste_pct': round(100 * rend, 1),
            'au_dessus_de_la_cloture': bool(n >= MIN_N and z >= 2)}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = EPT.lignes(archive, racine, avec_pinnacle=True)
    out = {}
    for c in ('ATP', 'WTA'):
        R = [r for r in rows if r['c'] == c]
        av = [r for r in R if r['d'] < COUPURE]
        ju = [r for r in R if r['d'] >= COUPURE and r.get('pin') is not None]
        X = lambda r: r['x6'] + ((r['parcours_tournoi'],) if c == 'ATP' else ())
        b = ESC.apprendre([(r['z'], X(r)) for r in av], k=7 if c == 'ATP' else 6)
        bloc_c = {'matchs_apparies': len(ju)}
        for base, f in (('elo_seul', lambda r: r['z']), ('elo_et_signaux', lambda r: r['z'] + sum(bi * xi for bi, xi in zip(b, X(r))))):
            for s_ in SEUILS:
                cas = {'outsider': [], 'favori': []}
                for r in ju:
                    pn, pp = ESC._sg(f(r)), r['pin']          # joueur A = vainqueur réel
                    for q_n, q_p, g in ((pn, pp, 1), (1 - pn, 1 - pp, 0)):
                        if q_n - q_p >= s_:
                            cas['favori' if q_p >= 0.5 else 'outsider'].append((q_n, q_p, g))
                bloc_c[f'{base}|écart ≥ {int(100 * s_)} pts'] = {k: bloc(v) for k, v in cas.items()}
        out[c] = bloc_c
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'nature': 'loupe descriptive : la cote mesure après coup, jamais une entrée ; aucun conseil de pari',
           'regle': "« au-dessus de la clôture » seulement si réel > Pinnacle avec z ≥ 2 sur ≥ 300 matchs (2023 →)",
           'circuits': out}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
