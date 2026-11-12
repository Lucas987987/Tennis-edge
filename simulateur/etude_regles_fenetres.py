#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_regles_fenetres.py — les règles du lundi jugées sur 42 jours glissants (12/11/2026, audit, paquet 241)

LE DÉFAUT (audit, section 4). Les poids du mélange et les réglages de la simulation (backtest_match_simule.py,
entrainement_progressif.py) sont rejugés chaque lundi sur les 42 DERNIERS JOURS : six semaines dont cinq déjà vues la
semaine d'avant. La décision passe par stabilite.decider : entrer si le gain dépasse 0,001 deux semaines de suite,
sortir s'il est sous −0,001 deux semaines de suite. Deux semaines de fenêtres qui se chevauchent à 5/6 ne sont pas
deux confirmations : c'est presque la même mesure. Et 0,001 est très petit devant le bruit d'une fenêtre.

RÈGLE ÉCRITE AU PAQUET 234 (rapport_audit.json, « regles_hebdomadaires_des_poids_et_des_facteurs ») :
  même étude que pour les signaux : la règle en place contre une règle cumulée, un réglage connu bon et un réglage au
  hasard, part des semaines dans le mauvais état ; est gardée celle qui fait le moins d'erreurs.
PRÉCISIONS ÉCRITES LE 12/11/2026, AVANT DE LANCER L'ÉTUDE :
  - données : les matchs jugés de etude_signaux_reappris.py (Elo de production, 2023 → juin 2026), semaine = lundi ;
  - réglage connu bon : la configuration des signaux en place sur le circuit contre l'Elo seul — un réglage qui
    touche TOUS les matchs, comme un poids du mélange ; gain par match = log loss sans − avec ;
  - réglage au hasard : sur les mêmes matchs, un décalage de même taille et de signe tiré au sort ; 300 tirages ;
    signal bon : l'histoire réelle plus 300 histoires où les semaines sont tirées au sort avec remise ;
  - règles comparées, chacune depuis les deux positions de départ (en place, en attente) :
      « en place »   : gain moyen sur les 42 derniers jours, stabilite.decider à l'identique (0,001, deux semaines) ;
      « cumulée »    : depuis le dernier changement, ≥ 300 matchs, ± 2 erreurs types (fantomes_circuits.py, paquet 234) ;
      « fenêtre 2σ » : les 42 derniers jours, ± 2 erreurs types de la fenêtre, deux semaines de suite (ce que les flux
                       actuels peuvent calculer sans garder d'historique) ;
  - erreur = part des semaines dans le mauvais état, moyenne des trois circuits, des deux signaux et des deux départs ;
    est gardée la règle d'erreur la plus basse ; à égalité, celle en place.
  Rien ne change le % de victoire dans ce paquet par lui-même : il change QUAND un réglage entre ou sort.

Usage : python simulateur/etude_regles_fenetres.py /tmp/sackmann . [--lignes cache.json.gz]
"""
import collections
import datetime as dt
import gzip
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_outsiders as EO  # noqa: E402
import etude_regle_hebdomadaire as RH  # noqa: E402
import etude_signaux_reappris as ER  # noqa: E402
import stabilite as ST  # noqa: E402

FENETRE_SEMAINES, TIRAGES, GRAINE = 6, 300, 20261112
SORTIE = os.path.join(ICI, 'rapport_regles_fenetres.json')


def _fenetre(semaines, i):
    return [x for S in semaines[max(0, i - FENETRE_SEMAINES + 1): i + 1] for x in S]


def regle_en_place(semaines, en_place):
    """stabilite.decider à l'identique, sur le gain moyen des 42 derniers jours."""
    etat, out = {}, []
    for i in range(len(semaines)):
        F = _fenetre(semaines, i)
        g = sum(F) / len(F) if F else 0.0
        ok, _ = ST.decider(etat, 'r', en_place, g > 0, ll_nouveau=-g, ll_actuel=0.0, semaine=f's{i}')
        out.append(ok)
    return out


def regle_fenetre_2se(semaines, en_place, seuil=2.0):
    """Entrer : gain de la fenêtre au-dessus de 2 erreurs types, deux semaines de suite ; sortir : en dessous de −2."""
    etat, serie, out = bool(en_place), 0, []
    for i in range(len(semaines)):
        F = _fenetre(semaines, i)
        if len(F) >= 30:
            m = sum(F) / len(F)
            se = math.sqrt(max(sum(x * x for x in F) / len(F) - m * m, 0.0) / len(F))
            change = (m - seuil * se > 0) if not etat else (m + seuil * se < 0)
            serie = serie + 1 if change else 0
            if serie >= ST.SEMAINES:
                etat, serie = not etat, 0
        out.append(etat)
    return out


REGLES = {'en_place': regle_en_place, 'cumulee': RH.regle_cumulee, 'fenetre_2se': regle_fenetre_2se}


def semaines_du_circuit(R, b):
    W = collections.defaultdict(list)
    for r in R:
        if r['d'] < ER.COUPURE:
            continue
        avec, sans = ER._zc(r, b), r['z']
        W[r['d'] - dt.timedelta(days=r['d'].weekday())].append((EO.ll(sans) - EO.ll(avec), abs(avec - sans), avec))
    return [W[k] for k in sorted(W)]


def etudier_circuit(sem, rnd):
    bon = [[g for g, _, _ in S] for S in sem]
    n = sum(len(S) for S in bon)
    out = {'semaines': len(sem), 'matchs': n, 'matchs_par_semaine': round(n / max(1, len(sem)), 1),
           'gain_du_reglage_bon': round(sum(sum(S) for S in bon) / max(1, n), 5)}
    H_bon = [bon] + [[bon[rnd.randrange(len(bon))] for _ in bon] for _ in range(TIRAGES)]
    H_has = [RH._hasard(sem, rnd) for _ in range(TIRAGES)]
    for nom, f in REGLES.items():
        r = {}
        for depart in (True, False):
            cle = 'depart_en_place' if depart else 'depart_en_attente'
            Eb = [f(h, depart) for h in H_bon]
            Eh = [f(h, depart) for h in H_has]
            r[cle] = {'reglage_bon_hors_algo': round(sum(RH._part_mauvais(e, True) for e in Eb[1:]) / TIRAGES, 3),
                      'reglage_bon_histoire_reelle': round(RH._part_mauvais(Eb[0], True), 3),
                      'reglage_au_hasard_dans_l_algo': round(sum(RH._part_mauvais(e, False) for e in Eh) / TIRAGES, 3),
                      'changements_par_an_reglage_au_hasard': round(sum(sum(1 for a, b in zip([depart] + e, e) if a != b) for e in Eh) / TIRAGES
                                                                    / max(1, len(sem)) * 52, 2)}
        r['erreur'] = round(sum(r[c]['reglage_bon_hors_algo'] + r[c]['reglage_au_hasard_dans_l_algo']
                                for c in ('depart_en_place', 'depart_en_attente')) / 4, 4)
        out[nom] = r
    return out


def main(argv):
    import donnees as DN
    import elo as E
    import etude_age as EA
    archive, racine = argv[1], (argv[2] if len(argv) > 2 and not argv[2].startswith('--') else '.')
    etat = ER._json(racine, 'elo_etat.json')
    alias = dict(E.migrer_etat(etat).get('alias') or {}) if etat else {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    rows = ER.lignes(DN.charger(archive, 2012), racine, EA.naissances(archive, k), k)
    Rp = ER._json(racine, 'rapport_signaux_reappris.json').get('circuits') or {}
    rnd = random.Random(GRAINE)
    circuits = {}
    for c in ER.CIRCUITS:
        v = Rp.get(c) or {}
        betas = v.get('betas') if v.get('adopte') else v.get('betas_en_place')
        b = [(betas or {}).get(n, 0.0) for n in ER.NOMS]
        circuits[c] = etudier_circuit(semaines_du_circuit([r for r in rows if r['c'] == c], b), rnd)
    erreurs = {nom: round(sum(v[nom]['erreur'] for v in circuits.values()) / len(circuits), 4) for nom in REGLES}
    gardee = min(erreurs, key=lambda n: (erreurs[n], n != 'en_place'))
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("règle en place (42 jours glissants, 0,001, deux semaines), règle cumulée (≥ 300 matchs, 2 erreurs types) et "
                     "fenêtre à 2 erreurs types rejouées semaine par semaine sur 2023 → juin 2026, avec un réglage connu bon et un "
                     "réglage au hasard de même taille ; erreur = part des semaines dans le mauvais état ; est gardée la plus basse"),
           'tirages': TIRAGES, 'circuits': circuits, 'erreur_par_regle': erreurs, 'regle_gardee': gardee}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, v in circuits.items():
        print(f"== {c} : {v['semaines']} semaines, {v['matchs_par_semaine']} matchs par semaine, gain du réglage bon {v['gain_du_reglage_bon']}")
        for nom in REGLES:
            for dep in ('depart_en_place', 'depart_en_attente'):
                x = v[nom][dep]
                print(f"   {nom:12s} {dep:18s} | bon hors algo {x['reglage_bon_hors_algo']} (réel {x['reglage_bon_histoire_reelle']}) | hasard dans l'algo "
                      f"{x['reglage_au_hasard_dans_l_algo']} | changements/an au hasard {x['changements_par_an_reglage_au_hasard']}")
            print(f"   {nom:12s} erreur {v[nom]['erreur']}")
    print('ERREUR PAR RÈGLE :', erreurs, '→ gardée :', gardee)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
