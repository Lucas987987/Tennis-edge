#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_premieres_balles_salle.py — en salle, plus de 1res balles que l'annoncé ? (12/11/2026, audit, paquet 238)

D'où vient la question (paquet 237). Contre l'archive, le % de 1res balles annoncé n'a pas de biais d'ensemble, mais il
suit la saison : trop bas en janvier, octobre et novembre, trop haut en juillet-août. Le mois n'était qu'un remplaçant
de « en salle » (pas de vent, pas de soleil : le serveur passe plus de 1res balles) ; le décalage par mois a été rejeté.
Ici la vraie information : tournois_en_salle.py, table écrite depuis le calendrier sans regarder un résultat.

Données : les lignes de etude_statistiques_annoncees.py (feuille annoncée rejouée sur l'archive, une ligne par joueur,
match et statistique), ATP et WTA. Le Challenger n'est pas étudié : l'archive ne permet pas d'y savoir qui joue en salle.

RÈGLE ÉCRITE AU PAQUET 237 (rapport_audit.json, « premieres_balles_en_salle »), avant la table et avant toute mesure :
  décalage « en salle » appris sur 2019–2022, jugé une fois sur 2023 → juin 2026 : retenu si le biais en salle baisse
  d'au moins moitié et si l'écart moyen ne monte pas, sur au moins 1 000 cas.
PRÉCISIONS ÉCRITES LE 12/11/2026, AVANT DE LANCER L'ÉTUDE :
  - deux décalages par circuit et par statistique : « en salle » et « plein air » (sans le second, corriger la salle
    déplacerait la moyenne d'ensemble) ; chacun = biais moyen (réel − annoncé) sur 2019–2022, réduit par n / (n + 300) ;
  - « au moins 1 000 cas » : les cas EN SALLE de la période jugée ; « écart moyen » : |annoncé − réel| sur tous les cas
    jugés du circuit dont on sait s'ils sont en salle ;
  - la statistique visée est le % de 1res balles ; aces, doubles fautes et breaks passent la même règle, à part ;
  - en production, « en salle » vient de la feuille du match, et le décalage s'applique AVANT le recalage appris en
    direct, à l'affichage comme à l'apprentissage (sinon il serait compté deux fois).
  Rien ne change le % de victoire.

Usage : python simulateur/etude_premieres_balles_salle.py /tmp/sackmann . [--lignes cache.json.gz]
"""
import datetime as dt
import gzip
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import recalage_stats as RS  # noqa: E402
import tournois_en_salle as TS  # noqa: E402

COUPURE = '2023-01-01'
MIN_CAS_SALLE, PRIOR, REDUCTION = 1000, 300.0, 0.5
SORTIE = os.path.join(ICI, 'rapport_premieres_balles_salle.json')


def _moy(v):
    return sum(v) / len(v) if v else None


def apprendre(appr, c, stat):
    """{'salle': δ, 'plein_air': δ} — biais moyen de chaque groupe sur l'apprentissage, réduit par n / (n + 300)."""
    out = {}
    for nom, drapeau in (('salle', True), ('plein_air', False)):
        v = [r['reel'] - r['moy'] for r in appr if r['c'] == c and r['k'] == stat and r['salle'] is drapeau]
        out[nom] = round(_moy(v) * len(v) / (len(v) + PRIOR), 3) if v else 0.0
    return out


def juger_case(rows, c, stat):
    R = [r for r in rows if r['c'] == c and r['k'] == stat and r['salle'] is not None]
    appr, juge = [r for r in R if r['jour'] < COUPURE], [r for r in R if r['jour'] >= COUPURE]
    d = apprendre(appr, c, stat)
    corr = lambda r: r['reel'] - r['moy'] - (d['salle'] if r['salle'] else d['plein_air'])
    brut = lambda r: r['reel'] - r['moy']

    def bilan(L, f):
        s, a = [f(r) for r in L if r['salle']], [f(r) for r in L if not r['salle']]
        return {'cas_en_salle': len(s), 'biais_en_salle': round(_moy(s), 3) if s else None,
                'cas_plein_air': len(a), 'biais_plein_air': round(_moy(a), 3) if a else None,
                'ecart_moyen': round(_moy([abs(x) for x in s + a]), 4) if s or a else None}
    avant, apres = bilan(juge, brut), bilan(juge, corr)
    raisons = []
    if avant['cas_en_salle'] < MIN_CAS_SALLE:
        raisons.append(f"moins de {MIN_CAS_SALLE} cas en salle jugés")
    if avant['biais_en_salle'] is None or abs(apres['biais_en_salle']) > abs(avant['biais_en_salle']) * (1 - REDUCTION):
        raisons.append("le biais en salle ne baisse pas de moitié")
    if avant['ecart_moyen'] is None or apres['ecart_moyen'] > avant['ecart_moyen']:
        raisons.append("l'écart moyen monte")
    mois = {}
    for r in juge:
        mois.setdefault(int(r['jour'][5:7]), []).append((brut(r), corr(r)))
    return {'decalages': d, 'apprentissage_2019_2022': bilan(appr, brut), 'jugement_avant': avant, 'jugement_apres': apres,
            'biais_par_mois_2023': {str(m): {'cas': len(v), 'avant': round(_moy([x[0] for x in v]), 2), 'apres': round(_moy([x[1] for x in v]), 2)}
                                    for m, v in sorted(mois.items()) if len(v) >= 200},
            'retenu': not raisons, 'raisons': raisons}


def etudier(rows):
    for r in rows:
        r['salle'] = TS.en_salle(r['c'], r.get('tournoi'), r.get('surface'))
    return {c: {stat: juger_case(rows, c, stat) for stat in RS.STATS} for c in TS.CIRCUITS}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 and not argv[2].startswith('--') else '.')
    cache = argv[argv.index('--lignes') + 1] if '--lignes' in argv else None
    if cache and os.path.exists(cache):
        with gzip.open(cache, 'rt', encoding='utf-8') as f:
            rows = json.load(f)
    else:
        import etude_statistiques_annoncees as ES
        rows = ES.lignes(archive, racine)
        if cache:
            with gzip.open(cache, 'wt', encoding='utf-8') as f:
                json.dump(rows, f)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("décalages « en salle » et « plein air » appris sur 2019–2022, jugés une fois sur 2023 → juin 2026 : retenu si le "
                     "biais en salle baisse d'au moins moitié et si l'écart moyen ne monte pas, sur au moins 1 000 cas en salle"),
           'table': {'fichier': 'simulateur/tournois_en_salle.py', 'tournois_en_salle': {c: sorted(TS.SALLE[c]) for c in TS.CIRCUITS},
                     'tournois_ecartes': {c: list(TS.INCERTAINS[c]) for c in TS.CIRCUITS}},
           'circuits': etudier(rows)}
    doc['retenus'] = [f'{c}|{k}' for c, v in doc['circuits'].items() for k, x in v.items() if x['retenu']]
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, v in doc['circuits'].items():
        for k, x in v.items():
            a, b = x['jugement_avant'], x['jugement_apres']
            print(f"{c} {k:15s} décalages {x['decalages']} | appr. salle {x['apprentissage_2019_2022']['biais_en_salle']} air {x['apprentissage_2019_2022']['biais_plein_air']} | "
                  f"jugé : salle {a['biais_en_salle']} → {b['biais_en_salle']} ({a['cas_en_salle']} cas), plein air {a['biais_plein_air']} → {b['biais_plein_air']}, "
                  f"écart {a['ecart_moyen']} → {b['ecart_moyen']} | {'RETENU' if x['retenu'] else 'non : ' + ' ; '.join(x['raisons'])}")
    print('par mois, ATP 1res balles :', doc['circuits']['ATP']['premiere_pct']['biais_par_mois_2023'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
