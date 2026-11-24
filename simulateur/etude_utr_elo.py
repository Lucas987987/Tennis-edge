#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_utr_elo.py — les RÉSULTATS du circuit UTR Pro Tennis Tour améliorent-ils l'Elo ? (24/11/2026, paquet 400,
Lucas : « 1 et 2 »)

Contexte : la sonde du 24/11 (scripts/sonde_outsiders_inconnus.py) sur 81 outsiders peu documentés : 458 de leurs matchs
depuis juin 2024 sont sur le circuit UTR (surtout États-Unis et Australie), que notre classement ignore. Les joueurs à
qui il manque le plus de matchs en viennent presque tous. scripts/resultats_itf.py (ITF_CIRCUIT=UTR) collecte ces
résultats (vainqueur, score) depuis le 01/06/2024 dans resultats_utr/. UTR = DONNÉE seulement : jamais pronostiqué,
jamais parié (même règle que l'ITF).

Méthode (celle de l'étude ITF du 28/10, etude_itf_elo.py) : l'Elo de production est rejoué deux fois dans l'ordre des
dates, archive Sackmann + feuilles TennisApi + résultats ITF hommes (la production d'aujourd'hui), SANS puis AVEC les
résultats UTR. Un joueur qui débute en UTR part au niveau des ITF hommes. Chaque match jugé est prédit AVANT d'être
compté ; un match déjà dans nos feuilles ou nos résultats ITF (même identifiant) n'est pas compté deux fois.

RÈGLE FIXÉE LE 24/11/2026, AVANT TOUT RÉSULTAT :
  — matchs jugés : ATP et Challenger joués du 1er janvier 2025 à aujourd'hui (7 mois de résultats UTR avant) ;
  — verdict de la semaine : la log loss du vainqueur sur les matchs CHALLENGER baisse d'au moins 0,001 avec l'UTR, ET
    celle des matchs ATP ne monte pas de plus de 0,0005 ;
  — adoption : ce verdict DEUX semaines de suite (stabilite.py, série « elo_utr ») ; adopté, il est proposé à Lucas
    (un paquet à part l'ajoute à l'Elo de production) ;
  — rien n'est jugé si la collecte couvre moins de 95 % des jours depuis le 01/06/2024.
Descriptif en plus (jamais dans la règle) : Challenger dont un joueur a des résultats UTR ; Challenger dont un joueur
avait moins de 40 matchs dans l'Elo sans UTR.
Usage : python simulateur/etude_utr_elo.py <archive Sackmann> [racine]
Sortie : simulateur/etude_utr_elo.json (aucune cote).
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))

import etude_itf_elo as EI  # noqa: E402

DEBUT_UTR = dt.date(2024, 6, 1)
SORTIE = os.path.join('simulateur', 'etude_utr_elo.json')
CLE_STABILITE = 'elo_utr'


def match_utr(r):
    """Fiche resultats_utr -> match ; traité au niveau des ITF hommes (départ, circuit « ITFH »), source « itf »
    (jamais jugé, jamais compté deux fois)."""
    m = EI.match_itf(r)
    if m:
        m['circuit'] = 'ITFH'
        m['source'] = 'itf'
    return m


def etude(M, F, I_itf_brut, I_utr_brut):
    import elo as E
    Ih = [m for m in (EI.match_itf(r) for r in I_itf_brut) if m and m['circuit'] == 'ITFH']
    ids = {m.get('id') for m in Ih if m.get('id')}
    Iu = [m for m in (match_utr(r) for r in I_utr_brut) if m and m.get('id') not in ids]
    connus = {}
    for m in M:
        connus.setdefault(E.cle(m['nom_g']), m['nom_g'])
        connus.setdefault(E.cle(m['nom_p']), m['nom_p'])
    base_noms = {n for m in F for n in (m['nom_g'], m['nom_p'])}
    alias = E.unifier(connus, base_noms)
    alias.update(EI.lier_itf(M, connus, Ih + Iu, base_noms))     # même règle stricte que la production
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))  # noqa: E731
    T0, T1 = EI.flux(M, F, Ih), EI.flux(M, F, Ih + Iu)
    cle_m = lambda m: (m['date'].isoformat(), cle_c(m['nom_g']), cle_c(m['nom_p']), m['circuit'])  # noqa: E731
    juge = lambda m: cle_m(m) if (m['date'] >= EI.DEBUT_JUGE and m['circuit'] in ('ATP', 'CH')  # noqa: E731
                                  and m.get('source') != 'itf') else None
    sans, avec = EI.rejouer(T0, cle_c, juge), EI.rejouer(T1, cle_c, juge)
    joueurs_utr = {cle_c(n) for m in Iu for n in (m['nom_g'], m['nom_p'])}
    ch = lambda k: k[3] == 'CH'  # noqa: E731
    rap = {'matchs_utr': len(Iu), 'joueurs_utr': len(joueurs_utr),
           'challenger': EI.comparer(sans, avec, ch),
           'atp': EI.comparer(sans, avec, lambda k: k[3] == 'ATP'),
           'descriptif': {
               'challenger_avec_joueur_utr': EI.comparer(sans, avec, ch, lambda k: k[1] in joueurs_utr or k[2] in joueurs_utr),
               'challenger_peu_vus': EI.comparer(sans, avec, ch, lambda k: sans[k][1] < EI.PEU_VUS)}}
    gc, ga = rap['challenger']['gain'], rap['atp']['gain']
    rap['verdict_semaine'] = bool(gc is not None and gc >= EI.MARGE and (ga is None or ga >= -EI.TOLERANCE))
    return rap


def main(argv):
    import donnees
    import resultats_itf as RI
    import stabilite as ST
    args = argv[1:]
    if not args:
        print('Usage : python simulateur/etude_utr_elo.py <archive Sackmann> [racine]')
        return 2
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    auj = dt.datetime.now(dt.timezone.utc).date()
    chemin = os.path.join(racine, SORTIE)
    try:
        with open(chemin, encoding='utf-8') as f:
            precedent = json.load(f)
    except (OSError, ValueError):
        precedent = {}
    cv = EI.couverture(racine, auj, RI.DOSSIER_UTR, DEBUT_UTR)
    etat = dict(precedent.get('stabilite') or {})
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'couverture_utr': cv,
           'regle': ("Challenger : log loss −0,001 au moins avec l'UTR, ATP : pas plus de +0,0005 ; deux semaines de "
                     "suite ; matchs jugés depuis le 01/01/2025 ; rien n'est jugé sous 95 % de jours collectés "
                     "(fixée le 24/11/2026, avant tout résultat)")}
    if cv < EI.COUVERTURE_MIN:
        doc.update(statut=f"collecte incomplète ({100 * cv:.1f} % des jours) : rien n'est jugé", adopte=False)
    else:
        M = donnees.charger(args[0], 2016)
        rap = etude(M, EI.feuilles_apres(racine, max(m['date'] for m in M)), RI.lire_tout(racine),
                    RI.lire_tout(racine, RI.DOSSIER_UTR))
        adopte, note = ST.decider(etat, CLE_STABILITE, False, rap['verdict_semaine'],
                                  rap['challenger']['log_loss_avec'], rap['challenger']['log_loss_sans'])
        doc.update(rap, statut=note, adopte=adopte)
    doc['stabilite'] = etat
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"Étude UTR : couverture {100 * cv:.1f} % · {doc.get('statut')}")
    for k in ('challenger', 'atp'):
        if doc.get(k):
            x = doc[k]
            print(f"  {k} : {x['n']} matchs, log loss {x['log_loss_sans']} → {x['log_loss_avec']} (gain {x['gain']})")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
