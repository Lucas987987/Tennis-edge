#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_regle_hebdomadaire.py — la règle « deux semaines de suite » contre une règle cumulée (12/11/2026, audit, paquet 234)

LE DÉFAUT (audit, section 4). Chaque lundi, fantomes_circuits.py rejuge chaque signal sur la seule semaine écoulée :
il entre après deux semaines gagnantes de suite (≥ 30 matchs, gain ≥ 0,001), il sort après deux semaines perdantes.
Or l'écart type du gain par match est d'environ 0,095 : sur 30 matchs l'erreur type vaut 0,017, dix-sept fois le
seuil. La règle réagit donc surtout au bruit.

RÈGLE ÉCRITE À L'AUDIT (rapport_audit.json, constat « regle_hebdomadaire », paquet 227) :
  rejouer semaine par semaine, sur l'archive 2023 →, la règle en place et une règle cumulée (retrait si le gain depuis
  l'adoption est négatif de 2 erreurs types sur au moins 300 matchs ; entrée à +2 erreurs types sur des semaines qui
  ne se chevauchent pas), avec un signal connu bon (retour d'absence) et un signal tiré au hasard ; est gardée celle
  qui fait le moins d'erreurs sur les deux signaux.
PRÉCISIONS ÉCRITES LE 12/11/2026, AVANT DE LANCER L'ÉTUDE :
  - données : les matchs jugés de etude_signaux_reappris.py (Elo de production, 2023 → juin 2026), une semaine =
    lundi → dimanche ; pour chaque match concerné par le retour d'absence, le gain propre du signal (log loss sans
    lui − avec lui, les autres signaux en place, β appris sur 2018–2022) ;
  - signal au hasard : sur les MÊMES matchs, un décalage de la même taille mais de signe tiré à pile ou face (il ne
    porte aucune information) ; 300 tirages ;
  - signal bon : l'histoire réelle, plus 300 histoires où les semaines sont retirées au sort avec remise ;
  - chaque règle est rejouée dans les deux positions de départ : signal en place, signal en attente ;
  - ERREUR d'une règle = part des semaines passées dans le MAUVAIS état (signal bon : hors de l'algo ; signal au
    hasard : dans l'algo), moyenne sur les trois circuits, les deux signaux et les deux positions de départ ;
  - règle cumulée, précisément : en place → retiré dès que, depuis l'adoption, sur ≥ 300 matchs, gain + 2 erreurs
    types < 0 ; en attente → adopté dès que, depuis le début du suivi (ou le dernier retrait), sur ≥ 300 matchs,
    gain − 2 erreurs types > 0 ; les compteurs repartent de zéro à chaque changement d'état ;
  - est gardée la règle dont l'erreur est la plus basse ; à égalité, celle en place.

Usage : python simulateur/etude_regle_hebdomadaire.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_outsiders as EO  # noqa: E402
import etude_signaux_reappris as ER  # noqa: E402

MIN_SEMAINE, MARGE, SEMAINES = 30, 0.001, 2                    # la règle en place (fantomes_circuits.py, stabilite.py)
CUMUL_MIN, CUMUL_ET = 300, 2.0                                 # la règle cumulée
TIRAGES, GRAINE = 300, 20261112
SIGNAL_BON = 'retour_absence'
SORTIE = os.path.join(ICI, 'rapport_regle_hebdomadaire.json')


def regle_en_place(semaines, en_place):
    """Rejoue fantomes_circuits.main + stabilite.decider. semaines : [[gain propre de chaque match concerné]].
    Renvoie l'état (True = dans l'algo) APRÈS chaque semaine. Un signal « direct » ne sort que sur deux semaines
    jugées (≥ 30 matchs) perdantes de suite ; une fois sorti (ou parti en attente) il suit la règle des fantômes :
    il entre après deux semaines gagnantes de suite, il ressort après deux semaines non gagnantes."""
    direct, etat, serie, tot_n, tot_s, out = bool(en_place), bool(en_place), 0, 0, 0.0, []
    for S in semaines:
        tot_n += len(S)
        tot_s += sum(S)
        gs = sum(S) / len(S) if S else None
        if direct:
            if len(S) >= MIN_SEMAINE:
                serie = serie + 1 if gs <= -MARGE else 0
                if serie >= SEMAINES:
                    etat, direct, serie = False, False, 0
        else:
            gagnante = len(S) >= MIN_SEMAINE and gs >= MARGE and tot_n and tot_s / tot_n >= MARGE
            if etat:
                serie = serie + 1 if not gagnante else 0
                if serie >= SEMAINES:
                    etat, serie = False, 0
            else:
                serie = serie + 1 if gagnante else 0
                if serie >= SEMAINES:
                    etat, serie = True, 0
        out.append(etat)
    return out


def regle_cumulee(semaines, en_place):
    etat, n, s, s2, out = bool(en_place), 0, 0.0, 0.0, []
    for S in semaines:
        n += len(S)
        s += sum(S)
        s2 += sum(x * x for x in S)
        if n >= CUMUL_MIN:
            m = s / n
            et = math.sqrt(max(s2 / n - m * m, 0.0) / n)
            if (etat and m + CUMUL_ET * et < 0) or (not etat and m - CUMUL_ET * et > 0):
                etat, n, s, s2 = not etat, 0, 0.0, 0.0
        out.append(etat)
    return out


REGLES = {'en_place': regle_en_place, 'cumulee': regle_cumulee}


def series(rows, betas):
    """{lundi: [(gain propre du signal bon, taille du décalage)]} pour les matchs jugés concernés."""
    b = [betas.get(n, 0.0) for n in ER.NOMS]
    idx = ER.SIGNAUX[SIGNAL_BON]
    b0 = [0.0 if i in idx else v for i, v in enumerate(b)]
    W = collections.defaultdict(list)
    for r in rows:
        if r['d'] < ER.COUPURE or not any(r['x'][i] for i in idx):
            continue
        avec, sans = ER._zc(r, b), ER._zc(r, b0)
        W[r['d'] - dt.timedelta(days=r['d'].weekday())].append((EO.ll(sans) - EO.ll(avec), abs(avec - sans), avec))
    return [W[k] for k in sorted(W)]


def _hasard(sem, rnd):
    """Le signal au hasard : même taille de décalage, signe tiré au sort, ajouté au pronostic complet."""
    return [[EO.ll(z) - EO.ll(z + (t if rnd.random() < 0.5 else -t)) for _, t, z in S] for S in sem]


def _part_mauvais(etats, bon):
    return sum(1 for e in etats if e != bon) / max(1, len(etats))


def etudier_circuit(sem, rnd):
    bon = [[g for g, _, _ in S] for S in sem]
    out = {'semaines': len(sem), 'matchs_concernes': sum(len(S) for S in sem),
           'matchs_par_semaine': round(sum(len(S) for S in sem) / max(1, len(sem)), 1),
           'semaines_d_au_moins_30_matchs': sum(1 for S in sem if len(S) >= MIN_SEMAINE),
           'gain_propre_du_signal_bon': round(sum(sum(S) for S in bon) / max(1, sum(len(S) for S in bon)), 5)}
    histoires_bon = [bon] + [[bon[rnd.randrange(len(bon))] for _ in bon] for _ in range(TIRAGES)]
    histoires_hasard = [_hasard(sem, rnd) for _ in range(TIRAGES)]
    for nom, f in REGLES.items():
        r = {}
        for depart in (True, False):
            cle = 'depart_en_place' if depart else 'depart_en_attente'
            E_bon = [f(h, depart) for h in histoires_bon]
            E_has = [f(h, depart) for h in histoires_hasard]
            r[cle] = {'signal_bon': {'histoire_reelle_part_hors_algo': round(_part_mauvais(E_bon[0], True), 3),
                                     'part_hors_algo': round(sum(_part_mauvais(e, True) for e in E_bon[1:]) / TIRAGES, 3),
                                     'hors_algo_a_la_fin_pct': round(100 * sum(1 for e in E_bon[1:] if not e[-1]) / TIRAGES, 1),
                                     'change_d_etat_au_moins_une_fois_pct': round(100 * sum(1 for e in E_bon[1:] if any(x != depart for x in e)) / TIRAGES, 1)},
                      'signal_au_hasard': {'part_dans_l_algo': round(sum(_part_mauvais(e, False) for e in E_has) / TIRAGES, 3),
                                           'dans_l_algo_a_la_fin_pct': round(100 * sum(1 for e in E_has if e[-1]) / TIRAGES, 1),
                                           'change_d_etat_au_moins_une_fois_pct': round(100 * sum(1 for e in E_has if any(x != depart for x in e)) / TIRAGES, 1)}}
        r['erreur'] = round(sum(r[c]['signal_bon']['part_hors_algo'] + r[c]['signal_au_hasard']['part_dans_l_algo']
                                for c in ('depart_en_place', 'depart_en_attente')) / 4, 4)
        out[nom] = r
    return out


def main(argv):
    import donnees as DN
    import elo as E
    import etude_age as EA
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    etat = ER._json(racine, 'elo_etat.json')
    alias = dict(E.migrer_etat(etat).get('alias') or {}) if etat else {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    rows = ER.lignes(DN.charger(archive, 2012), racine, EA.naissances(archive, k), k)
    rnd = random.Random(GRAINE)
    circuits = {}
    for c in ER.CIRCUITS:
        R = [r for r in rows if r['c'] == c]
        betas = ER.juger_circuit(R, [0.0] * 7)['betas']         # β appris sur 2018–2022, signaux gardés
        betas.update({n: v for n, v in zip(ER.NOMS, ER.ESC.apprendre([(r['z'], r['x']) for r in R if r['d'] < ER.COUPURE], k=7))
                      if n.startswith('retour_absence') and n not in betas})
        circuits[c] = etudier_circuit(series(R, betas), rnd)
    erreurs = {nom: round(sum(v[nom]['erreur'] for v in circuits.values()) / len(circuits), 4) for nom in REGLES}
    gardee = 'cumulee' if erreurs['cumulee'] < erreurs['en_place'] else 'en_place'
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("la règle en place (deux semaines de suite, ≥ 30 matchs, seuil 0,001) et la règle cumulée (≥ 300 matchs, "
                     "2 erreurs types, compteurs remis à zéro à chaque changement d'état) rejouées semaine par semaine sur "
                     "2023 → juin 2026, avec le retour d'absence (signal bon) et un signal au hasard de même taille ; erreur = "
                     "part des semaines passées dans le mauvais état ; est gardée la règle dont l'erreur est la plus basse"),
           'tirages': TIRAGES, 'circuits': circuits, 'erreur_par_regle': erreurs, 'regle_gardee': gardee}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, v in circuits.items():
        print(f"== {c} : {v['semaines']} semaines, {v['matchs_par_semaine']} matchs concernés par semaine ({v['semaines_d_au_moins_30_matchs']} semaines ≥ 30), "
              f"gain propre du signal bon {v['gain_propre_du_signal_bon']}")
        for nom in REGLES:
            for dep in ('depart_en_place', 'depart_en_attente'):
                b, h = v[nom][dep]['signal_bon'], v[nom][dep]['signal_au_hasard']
                print(f"   {nom:9s} {dep:18s} | bon : hors algo {b['part_hors_algo']} des semaines (réel {b['histoire_reelle_part_hors_algo']}), hors à la fin {b['hors_algo_a_la_fin_pct']} % "
                      f"| hasard : dans l'algo {h['part_dans_l_algo']} des semaines, dedans à la fin {h['dans_l_algo_a_la_fin_pct']} %")
            print(f"   {nom:9s} erreur {v[nom]['erreur']}")
    print('ERREUR PAR RÈGLE :', erreurs, '→ gardée :', gardee)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
