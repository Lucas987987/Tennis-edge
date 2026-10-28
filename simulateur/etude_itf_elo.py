#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_itf_elo.py — les RÉSULTATS ITF hommes améliorent-ils l'Elo des joueurs Challenger ? (28/10/2026)

Contexte : quand le moins documenté des deux joueurs a 500 à 1 500 balles effectives, l'algo trouve 47 % des
vainqueurs pour 70 % de confiance (55 matchs jugés depuis le 21/10). Ces joueurs jouent surtout en ITF, absent de
l'archive masculine ; la sonde du 28/10 a montré que ces matchs n'ont presque jamais de feuille. Leurs résultats
(vainqueur, score) existent : scripts/resultats_itf.py les collecte depuis juin 2024 dans resultats_itf/.
ITF = DONNÉE seulement : jamais pronostiqué, jamais parié (décision de Lucas, 28/10/2026).

Méthode : l'Elo de production (options en place : surface 0,3, welo « norme », incertitude 5 ; départ 1 200 pour
un joueur qui débute en Challenger ou ITF) est rejoué deux fois dans l'ordre des dates, sur l'archive Sackmann puis
nos feuilles TennisApi — SANS puis AVEC les résultats ITF hommes. Mêmes noms de joueurs dans les deux passages.
Chaque match jugé est prédit AVANT d'être compté (aucune information du futur). Un match ITF déjà présent dans nos
feuilles (même identifiant) n'est pas compté deux fois ; les forfaits sont écartés.

RÈGLE FIXÉE LE 28/10/2026, AVANT TOUT RÉSULTAT :
  — matchs jugés : ATP, WTA et Challenger joués du 1er janvier 2025 à aujourd'hui (6 mois de résultats ITF avant) ;
  — verdict de la semaine : la log loss du vainqueur sur les matchs CHALLENGER baisse d'au moins 0,001 avec l'ITF,
    ET celle des matchs ATP + WTA ne monte pas de plus de 0,0005 ;
  — adoption : ce verdict DEUX semaines de suite (stabilite.py ; état gardé dans le rapport) ;
  — rien n'est jugé si la collecte couvre moins de 95 % des jours depuis le 1er juin 2024.
Une fois adopté seulement : les résultats ITF hommes entrent dans l'Elo de production, avec leur collecte
quotidienne (livraison séparée). Descriptif en plus (jamais dans la règle) : Challenger dont un joueur avait moins de
40 matchs dans l'Elo sans ITF ; Challenger dont un joueur a des résultats ITF.

Usage : python simulateur/etude_itf_elo.py <archive Sackmann> [racine]
Sortie : simulateur/etude_itf_elo.json (descriptif, aucune cote) + résumé dans le journal.
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))

OPTIONS = {'poids_surface': 0.3, 'welo': 'norme', 'incertitude': 5.0}     # options de l'Elo en place (elo_etat.json)
DEPART_BAS, BAS = 1200.0, ('CH', 'ITF', 'ITFH')
DEBUT_JUGE = dt.date(2025, 1, 1)
DEBUT_ITF = dt.date(2024, 6, 1)
MARGE, TOLERANCE = 0.001, 0.0005
COUVERTURE_MIN = 0.95
PEU_VUS = 40
SORTIE = os.path.join('simulateur', 'etude_itf_elo.json')
CLE_STABILITE = 'elo_resultats_itf'


def match_itf(r):
    """Fiche resultats_itf -> match (format donnees) ; None si forfait, inachevé ou incomplet."""
    import elo as E
    from feuilles import surface_de
    if r.get('vainqueur') not in (1, 2) or not r.get('jour'):
        return None
    if 'walkover' in str((r.get('statut') or {}).get('texte') or '').lower():
        return None
    h, a = r.get('home') or {}, r.get('away') or {}
    if not h.get('nom') or not a.get('nom'):
        return None
    g, p = (h, a) if r['vainqueur'] == 1 else (a, h)
    sh, sa = (r.get('score_home') or {}).get('sets') or [], (r.get('score_away') or {}).get('sets') or []
    sets = list(zip(sh, sa)) if r['vainqueur'] == 1 else list(zip(sa, sh))
    complet = str((r.get('statut') or {}).get('texte') or '').lower() in ('ended', 'finished', 'terminé')
    j = dt.date.fromisoformat(r['jour'])
    return {'date': j, 'fin': j, 'circuit': 'ITFH', 'surface': surface_de(r.get('surface')), 'nom_g': g['nom'],
            'nom_p': p['nom'], 'sets': sets, 'complet': complet, 'niveau': '', 'tour': 0, 'num': 0, 'id': r.get('id'),
            'source': 'itf', 'gagnant': E.cle(g['nom']), 'perdant': E.cle(p['nom'])}


def flux(M, F, I):
    """Archive + feuilles après l'archive (+ ITF si I) dans l'ordre ; ITF déjà présent dans les feuilles écarté."""
    fin = max(m['date'] for m in M)
    F = [m for m in F if m['date'] > fin]
    ids = {m.get('id') for m in F if m.get('id')}
    I = [m for m in (I or []) if m.get('id') not in ids]
    rang = {'archive': 0, 'tennisapi': 1, 'itf': 2}
    tout = [dict(m, source=m.get('source') or 'archive') for m in M] + F + I
    tout.sort(key=lambda m: (m['date'], rang.get(m['source'], 1), m.get('tour', 0), m.get('num', 0)))
    return tout


def rejouer(tout, cle_c, juge):
    """{indice du match jugé: (p du vainqueur, matchs min. des deux joueurs avant)} — prédiction AVANT la mise à jour."""
    import elo as E
    e = E.Elo(**OPTIONS)
    out = {}
    for m in tout:
        g, p = cle_c(m['nom_g']), cle_c(m['nom_p'])
        if not g or not p or g == p:
            continue
        if m['circuit'] in BAS:
            e.presenter(g, DEPART_BAS)
            e.presenter(p, DEPART_BAS)
        k = juge(m)
        if k is not None:
            out[k] = (e.proba(g, p, m['surface']), min(e.matchs(g), e.matchs(p)))
        e.maj(g, p, m['surface'], m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    return out


def _ll(L):
    return round(-sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L), 6) if L else None


def comparer(sans, avec, circuits, filtre=None):
    ks = [k for k in sans if k in avec and circuits(k) and (filtre is None or filtre(k))]
    a, b = _ll([sans[k][0] for k in ks]), _ll([avec[k][0] for k in ks])
    return {'n': len(ks), 'log_loss_sans': a, 'log_loss_avec': b,
            'gain': round(a - b, 6) if a is not None and b is not None else None,
            'vainqueurs_sans_pct': round(100 * sum(sans[k][0] > .5 for k in ks) / len(ks), 1) if ks else None,
            'vainqueurs_avec_pct': round(100 * sum(avec[k][0] > .5 for k in ks) / len(ks), 1) if ks else None}


def couverture(racine, aujourd_hui):
    import resultats_itf as RI
    try:
        with open(os.path.join(racine, RI.DOSSIER, 'etat.json'), encoding='utf-8') as f:
            jours = json.load(f).get('jours') or {}
    except (OSError, ValueError):
        jours = {}
    attendus = (aujourd_hui - DEBUT_ITF).days
    faits = sum(1 for j in jours if DEBUT_ITF.isoformat() <= j < aujourd_hui.isoformat())
    return round(faits / attendus, 4) if attendus > 0 else 0.0


def etude(M, F, I_brut):
    """Cœur testable : renvoie le rapport (sans la décision stabilisée)."""
    import elo as E
    I = [m for m in (match_itf(r) for r in I_brut) if m]
    connus = {}
    for m in M:
        connus.setdefault(E.cle(m['nom_g']), m['nom_g'])
        connus.setdefault(E.cle(m['nom_p']), m['nom_p'])
    alias = E.unifier(connus, {n for m in F + I for n in (m['nom_g'], m['nom_p'])})
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))
    T0, T1 = flux(M, F, None), flux(M, F, I)
    cle_m = lambda m: (m['date'].isoformat(), cle_c(m['nom_g']), cle_c(m['nom_p']), m['circuit'])
    juge = lambda m: cle_m(m) if (m['date'] >= DEBUT_JUGE and m['circuit'] in ('ATP', 'WTA', 'CH')
                                  and m.get('source') != 'itf') else None
    sans, avec = rejouer(T0, cle_c, juge), rejouer(T1, cle_c, juge)
    joueurs_itf = {cle_c(n) for m in I for n in (m['nom_g'], m['nom_p'])}
    ch = lambda k: k[3] == 'CH'
    rap = {'matchs_itf': len(I), 'joueurs_itf': len(joueurs_itf),
           'challenger': comparer(sans, avec, ch),
           'atp_wta': comparer(sans, avec, lambda k: k[3] in ('ATP', 'WTA')),
           'descriptif': {
               'challenger_peu_vus': comparer(sans, avec, ch, lambda k: sans[k][1] < PEU_VUS),
               'challenger_avec_joueur_itf': comparer(sans, avec, ch, lambda k: k[1] in joueurs_itf or k[2] in joueurs_itf)}}
    gc, ga = rap['challenger']['gain'], rap['atp_wta']['gain']
    rap['verdict_semaine'] = bool(gc is not None and gc >= MARGE and (ga is None or ga >= -TOLERANCE))
    return rap


def main(argv):
    import donnees
    import resultats_itf as RI
    import stabilite as ST
    args = argv[1:]
    if not args:
        print('Usage : python simulateur/etude_itf_elo.py <archive Sackmann> [racine]')
        return 2
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    auj = dt.datetime.now(dt.timezone.utc).date()
    chemin = os.path.join(racine, SORTIE)
    try:
        with open(chemin, encoding='utf-8') as f:
            precedent = json.load(f)
    except (OSError, ValueError):
        precedent = {}
    cv = couverture(racine, auj)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'couverture_itf': cv,
           'regle': ("Challenger : log loss −0,001 au moins avec l'ITF, ATP + WTA : pas plus de +0,0005 ; deux semaines "
                     "de suite ; matchs jugés depuis le 01/01/2025 ; rien n'est jugé sous 95 % de jours collectés "
                     "(fixée le 28/10/2026, avant tout résultat)")}
    etat = dict(precedent.get('stabilite') or {})
    if cv < COUVERTURE_MIN:
        doc['statut'] = f"collecte incomplète ({100 * cv:.1f} % des jours) : rien n'est jugé"
        doc['stabilite'] = etat
        doc['adopte'] = bool((etat.get(CLE_STABILITE) or {}).get('adopte'))
    else:
        M = donnees.charger(args[0], 2016)
        import backtest_pronostic as BP                       # feuilles après l'archive, forfaits écartés (comme l'Elo)
        rap = etude(M, BP.resultats_feuilles(racine, max(m['date'] for m in M)), RI.lire_tout(racine))
        adopte, note = ST.decider(etat, CLE_STABILITE, False, rap['verdict_semaine'],
                                  rap['challenger']['log_loss_avec'], rap['challenger']['log_loss_sans'])
        doc.update(rap, statut=note, adopte=adopte, stabilite=etat)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in doc.items() if k != 'stabilite'}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
