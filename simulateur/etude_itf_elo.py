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
1re semaine (28/10/2026, archive jusqu'au 02/06/2026 + 76 183 matchs ITF) : Challenger −0,0145 (22 530 matchs),
ATP + WTA −0,0042, joueurs peu vus −0,035 → candidat 1/2.
DÉCISION DE LUCAS LE 28/10/2026 : mise en production sans attendre la 2e semaine (backtest_pronostic.py, étape 5,
et collecte quotidienne). La règle devient la SORTIE : l'étude continue chaque lundi et retire l'ITF de l'Elo de
production s'il fait moins bien deux semaines de suite (« adopte » = false dans etude_itf_elo.json). Descriptif en plus (jamais dans la règle) : Challenger dont un joueur avait moins de
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
CLE_STABILITE = 'elo_itf_production'      # 28/10/2026 : en place par décision de Lucas ; sort après 2 semaines moins bien


def feuilles_apres(racine, depuis):
    """Résultats des feuilles TennisApi après `depuis`, forfaits écartés — même règle que
    backtest_pronostic.resultats_feuilles, sans importer ce module (il dépend de fichiers du Lab absents du run :
    1er run du 28/10 en échec sur Tennis_Edge_Lab/books.py)."""
    import feuilles as FE
    out = []
    for r in FE.lire(racine):
        if 'walkover' in str((r.get('statut') or {}).get('texte') or '').lower():
            continue
        m = FE.en_match(r)
        if m and m['date'] > depuis and m['nom_g'] and m['nom_p']:
            out.append(m)
    out.sort(key=lambda m: m['date'])
    return out


def sexe_de_circuit(c):
    return 'F' if c in ('WTA', 'ITF') else 'H'


def lier_itf(M, connus, itf_rows, deja):
    """28/10/2026 — alias des noms venus SEULEMENT des résultats ITF, par elo.unifier_strict (audit : des fusions à tort
    avec la règle souple) : même sexe, même ordre des mots, même premier et dernier mot, nom de famille rare si le nom
    court n'a que deux mots. Utilisé par l'étude ET par l'Elo de production (backtest_pronostic)."""
    import elo as E
    sexe_connus = {}
    for m in M:
        for n in (m['nom_g'], m['nom_p']):
            sexe_connus.setdefault(E.cle(n), sexe_de_circuit(m['circuit']))
    sx = {}
    for m in itf_rows:
        sx[m['nom_g']] = sx[m['nom_p']] = sexe_de_circuit(m['circuit'])
    noms = ({m['nom_g'] for m in itf_rows} | {m['nom_p'] for m in itf_rows}) - set(deja)
    return E.unifier_strict(connus, noms, sexe_connus, sx)


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
    femme = 'women' in str(r.get('categorie') or '').lower()
    return {'date': j, 'fin': j, 'circuit': 'ITF' if femme else 'ITFH', 'surface': surface_de(r.get('surface')), 'nom_g': g['nom'],
            'nom_p': p['nom'], 'sets': sets, 'complet': complet, 'niveau': '', 'tour': 0, 'num': 0, 'id': r.get('id'),
            'source': 'itf', 'gagnant': E.cle(g['nom']), 'perdant': E.cle(p['nom'])}


def flux(M, F, I):
    """Archive + feuilles après l'archive (+ ITF si I) dans l'ordre ; ITF déjà présent dans les feuilles écarté."""
    fin = max(m['date'] for m in M)
    F = [m for m in F if m['date'] > fin]
    ids = {m.get('id') for m in F if m.get('id')}
    # ITF féminin : déjà dans l'archive jusqu'à sa fin → seulement après (l'ITF masculin n'y est jamais)
    I = [m for m in (I or []) if m.get('id') not in ids and not (m['circuit'] == 'ITF' and m['date'] <= fin)]
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


def couverture(racine, aujourd_hui, dossier=None, debut=None):
    import resultats_itf as RI
    dossier, debut = dossier or RI.DOSSIER_HOMMES, debut or DEBUT_ITF
    try:
        with open(os.path.join(racine, dossier, 'etat.json'), encoding='utf-8') as f:
            jours = json.load(f).get('jours') or {}
    except (OSError, ValueError):
        jours = {}
    attendus = (aujourd_hui - debut).days
    faits = sum(1 for j in jours if debut.isoformat() <= j < aujourd_hui.isoformat())
    return round(faits / attendus, 4) if attendus > 0 else 0.0


def etude(M, F, I_brut):
    """Cœur testable : renvoie le rapport (sans la décision stabilisée)."""
    import elo as E
    I = [m for m in (match_itf(r) for r in I_brut) if m]
    connus = {}
    for m in M:
        connus.setdefault(E.cle(m['nom_g']), m['nom_g'])
        connus.setdefault(E.cle(m['nom_p']), m['nom_p'])
    base_noms = {n for m in F for n in (m['nom_g'], m['nom_p'])}
    alias = E.unifier(connus, base_noms)
    alias.update(lier_itf(M, connus, I, base_noms))      # même règle stricte que la production pour les noms ITF
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


# ------------------------------------------------------------------ ITF FEMMES (28/10/2026)
# RÈGLE FIXÉE LE 28/10/2026, AVANT TOUT RÉSULTAT : base = l'Elo de production (archive + feuilles + ITF hommes) ;
# on ajoute les résultats ITF femmes APRÈS la fin de l'archive (02/06/2026 : avant, ils y sont déjà). Matchs jugés :
# WTA joués après la fin de l'archive (là où l'information manquait). Verdict de la semaine : log loss WTA −0,001 au
# moins, ATP + Challenger pas plus de +0,0005 ; adoption DEUX semaines de suite (série « elo_itf_femmes ») ; rien n'est
# jugé sous 95 % des jours collectés depuis le 25/05/2026. Adopté seulement : l'Elo de production les ajoute.
DEBUT_ITF_FEMMES = dt.date(2026, 5, 25)
CLE_FEMMES = 'elo_itf_femmes'


def etude_femmes(M, F, I_hommes_brut, I_femmes_brut):
    import elo as E
    Ih = [m for m in (match_itf(r) for r in I_hommes_brut) if m]
    If = [m for m in (match_itf(r) for r in I_femmes_brut) if m]
    fin = max(m['date'] for m in M)
    connus = {}
    for m in M:
        connus.setdefault(E.cle(m['nom_g']), m['nom_g'])
        connus.setdefault(E.cle(m['nom_p']), m['nom_p'])
    base_noms = {n for m in F for n in (m['nom_g'], m['nom_p'])}
    alias = E.unifier(connus, base_noms)
    alias.update(lier_itf(M, connus, Ih + If, base_noms))
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))
    T0, T1 = flux(M, F, Ih), flux(M, F, Ih + If)
    cle_m = lambda m: (m['date'].isoformat(), cle_c(m['nom_g']), cle_c(m['nom_p']), m['circuit'])
    juge = lambda m: cle_m(m) if (m['date'] > fin and m['circuit'] in ('ATP', 'WTA', 'CH')
                                  and m.get('source') != 'itf') else None
    sans, avec = rejouer(T0, cle_c, juge), rejouer(T1, cle_c, juge)
    rap = {'matchs_itf_femmes': sum(1 for m in If if m['date'] > fin),
           'wta': comparer(sans, avec, lambda k: k[3] == 'WTA'),
           'atp_challenger': comparer(sans, avec, lambda k: k[3] in ('ATP', 'CH')),
           'descriptif': {'wta_peu_vues': comparer(sans, avec, lambda k: k[3] == 'WTA', lambda k: sans[k][1] < PEU_VUS)}}
    gw, ga = rap['wta']['gain'], rap['atp_challenger']['gain']
    rap['verdict_semaine'] = bool(gw is not None and gw >= MARGE and (ga is None or ga >= -TOLERANCE))
    return rap


def itf_femmes_adoptees(racine):
    """Vrai seulement si l'étude a ADOPTÉ les résultats ITF femmes (deux semaines de suite)."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            return bool((json.load(f).get('femmes') or {}).get('adopte'))
    except (OSError, ValueError):
        return False


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
        doc['adopte'] = bool((etat.get(CLE_STABILITE) or {}).get('adopte', True))
    else:
        M = donnees.charger(args[0], 2016)
        rap = etude(M, feuilles_apres(racine, max(m['date'] for m in M)), RI.lire_tout(racine))
        adopte, note = ST.decider(etat, CLE_STABILITE, True, rap['verdict_semaine'],
                                  rap['challenger']['log_loss_avec'], rap['challenger']['log_loss_sans'])
        doc.update(rap, statut=note, adopte=adopte, stabilite=etat)
    # --- ITF femmes : jugées à part, adoption seulement deux semaines de suite
    cvf = couverture(racine, auj, RI.DOSSIER_FEMMES, DEBUT_ITF_FEMMES)
    fem = {'couverture': cvf, 'regle': ("WTA après la fin de l'archive : log loss −0,001 au moins avec l'ITF femmes, "
                                        "ATP + Challenger pas plus de +0,0005 ; deux semaines de suite (fixée le 28/10/2026)")}
    if cvf < COUVERTURE_MIN:
        fem['statut'] = f"collecte incomplète ({100 * cvf:.1f} % des jours) : rien n'est jugé"
        fem['adopte'] = bool((etat.get(CLE_FEMMES) or {}).get('adopte', False))
    else:
        if 'M' not in locals():
            M = donnees.charger(args[0], 2016)
        rf = etude_femmes(M, feuilles_apres(racine, max(m['date'] for m in M)), RI.lire_tout(racine),
                          RI.lire_tout(racine, RI.DOSSIER_FEMMES))
        ok, note = ST.decider(etat, CLE_FEMMES, False, rf['verdict_semaine'],
                              rf['wta']['log_loss_avec'], rf['wta']['log_loss_sans'])
        fem.update(rf, statut=note, adopte=ok)
    doc['femmes'] = fem
    doc['stabilite'] = etat
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in doc.items() if k != 'stabilite'}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
