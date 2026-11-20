#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_qualifs_grand_chelem.py — l'Elo est-il mal étalonné en qualifications de Grand Chelem ? (11/11/2026, paquet 232)

D'où vient la question. Sur nos 280 matchs de qualifications de Grand Chelem de 2026, le favori a gagné 68,2 % du temps
pour 62,2 % annoncés. C'est trop peu pour conclure : l'archive tranche. Les qualifications y sont rangées avec le
Challenger (hommes) et l'ITF (femmes), niveau « G », toutes en 2 sets gagnants depuis 2022.

Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match. Matchs jugés : qualifications de Grand Chelem, sans abandon. « Hommes » et « femmes » jugés à part.

RÈGLE ÉCRITE LE 11/11/2026 DANS rapport_audit.json (paquet 231), avant toute mesure sur l'archive :
  une pente propre aux qualifications de Grand Chelem, p' = σ(pente · logit p), APPRISE sur 2018–2022, jugée UNE SEULE
  FOIS sur 2023 → juin 2026 : gain ≥ 0,001 sur ≥ 1 000 matchs, même sens sur les deux périodes (biais du même côté).
  Erreur type et Brier publiés ; « 2 erreurs types » publié à part.
  Leçon des paquets 229 et 230 : avant toute mise en production, contrôle « comme en production ».

Usage : python simulateur/etude_qualifs_grand_chelem.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402
import etude_outsiders as EO  # noqa: E402

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
GROUPES = {'hommes': 'CH', 'femmes': 'ITF'}       # où l'archive range les qualifications
SORTIE = os.path.join(ICI, 'rapport_qualifs_grand_chelem.json')
# Contrôle fait le 11/11/2026 sur NOS matchs de qualifications de 2026 (classement de production rejoué, résultats ITF
# compris). Femmes : même sens, la pente ne fait pas moins bien. Hommes : nos matchs disent autre chose que l'archive.
CONTROLE_NOS_MATCHS = {
    'fait_le': '2026-11-11',
    'femmes': {'matchs': 109, 'pente_propre': 1.2, 'gain_de_la_pente': 0.00121, 'erreur_type': 0.00541,
               'lecture': "même sens que l'archive, ne fait pas moins bien ; trop peu de matchs pour conclure seul"},
    'hommes': {'matchs': 171, 'favori_reel_pct': 73.1, 'favori_annonce_pct': 62.6, 'pente_propre': 1.6,
               'lecture': ("l'archive ne montre rien (pente 0,88 puis 0,96), nos 171 matchs de 2026 montrent un Elo trop prudent : "
                           "à surveiller. Piste : le classement de production contient les résultats ITF hommes, pas l'archive ; "
                           "le départ ITF plus bas (règle écrite au paquet 230) sera jugé sur les matchs à venir")},
}


def lignes(M, racine):
    """[(groupe, date, z du vainqueur)] des qualifications de Grand Chelem — Elo de production, lu avant le match."""
    el, bas = E.de_production(racine)
    par_circuit = {c: g for g, c in GROUPES.items()}
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if m.get('niveau') == 'G' and c in par_circuit and DEBUT <= m['date'] < FIN and not m.get('abandon'):
            rows.append((par_circuit[c], m['date'], EO._lg(el.proba(g, p, s))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def juger(rows, groupe):
    A = [z for g, d, z in rows if g == groupe and d < COUPURE]
    J = [z for g, d, z in rows if g == groupe and d >= COUPURE]
    k = EO.pente(A) if len(A) >= 200 else 1.0
    kj = EO.pente(J) if len(J) >= 200 else None
    appr, juge = EO.bilan(A, [k * z for z in A]), EO.bilan(J, [k * z for z in J])
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if kj is None or (kj - 1) * (k - 1) <= 0:
        raisons.append("biais de sens contraire sur 2023 →")
    return {'pente_apprise': round(k, 3), 'pente_sur_2023': round(kj, 3) if kj is not None else None,
            '2018–2022': appr, '2023 → juin 2026': juge, 'retenue': not raisons, 'raisons': raisons,
            'passe_deux_erreurs_types': (not raisons) and (juge.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows = lignes(DN.charger(archive, 2012), racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("pente propre aux qualifications de Grand Chelem apprise sur 2018–2022, jugée une seule fois sur 2023 → "
                     "juin 2026 : gain ≥ 0,001 sur ≥ 1 000 matchs, même sens sur les deux périodes ; hommes et femmes à part"),
           'elo': "réglé comme la production (elo.de_production), mis à jour après chaque match",
           'groupes': {g: juger(rows, g) for g in GROUPES},
           'controle_nos_matchs': CONTROLE_NOS_MATCHS}
    doc['en_production'] = {g: v['retenue'] for g, v in doc['groupes'].items()}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for g, v in doc['groupes'].items():
        a, j = v['2018–2022'], v['2023 → juin 2026']
        print(f"{g:7s} pente {v['pente_apprise']} (sur 2023 → : {v['pente_sur_2023']}) | 2018–2022 : {a['matchs']} matchs, favori {a['favori_reel_pct']} % pour "
              f"{a['favori_annonce_pct']} %, gain {a['gain']} | 2023 → : {j['matchs']} matchs, favori {j['favori_reel_pct']} % pour {j['favori_annonce_pct']} %, "
              f"gain {j['gain']} ± {j['erreur_type']} ({j['erreurs_types']} e.t.), Brier {j['brier_base']} → {j['brier']} | retenue : {v['retenue']} {v['raisons']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
