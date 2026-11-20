#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_pente_niveau.py — LE MÊME ÉCART D'ELO VAUT-IL LA MÊME CHOSE EN HAUT ET EN BAS DU TABLEAU ?
(20/11/2026, paquet 301, étude de fiabilité)

QUESTION. L'Elo ne regarde que l'ÉCART entre les deux joueurs : 100 points d'écart donnent le même % entre deux
joueurs du top 20 qu'entre deux joueurs classés au-delà de la 300e place. Or les joueurs du haut sont plus réguliers
d'un match à l'autre (moins de jours « sans »), et leur niveau est mieux connu ; en bas, le niveau varie plus et
l'outsider gagne peut-être plus souvent qu'annoncé. Si c'est vrai, nos % sont trop prudents en haut et trop sûrs en
bas (ou l'inverse), et la note de fiabilité ne le voit pas. Ce n'est pas encore étudié : le balayage du paquet 236
a regardé le niveau du TOURNOI, la surface, la saison, le tour et l'expérience du joueur le moins vu, jamais le
niveau des DEUX joueurs ; le paquet 289 a regardé le style du duel (service / retour), rejeté.

INDICE DU NIVEAU DU MATCH (connu avant le match, symétrique : il ne dit rien du vainqueur).
    u = ( ½ (Elo_A + Elo_B) − R_c ) / 200
Elo = note de production sur la surface du match, juste avant le match ; R_c = médiane de ½ (Elo_A + Elo_B) sur les
matchs 2018–2022 du circuit (fixée sur la période d'apprentissage seulement). u > 0 : match du haut du circuit.

CORRECTION ÉTUDIÉE, une par circuit : z' = z · (1 + β · u), z = logit du % de BASE (Elo de production mis à jour
après chaque match + les trois signaux solides, comme etude_outsiders.py et etude_pente_service.py). β appris par
maximum de vraisemblance. β > 0 = l'écart compte plus en haut du circuit (nos % y sont trop prudents).

RÈGLE ÉCRITE AVANT TOUT RÉSULTAT (20/11/2026), CIRCUIT PAR CIRCUIT (ATP, WTA, Challenger analysés séparément) :
  1. β et R_c sont appris sur 2018–2022 SEULEMENT ;
  2. jugés UNE SEULE FOIS sur 2023 → juin 2026 (matchs jugés : sans abandon, sans compétition par équipes ; ITF
     jamais jugée, ses résultats ne servent qu'à l'Elo) ;
  3. le signal est RETENU sur un circuit seulement si, sur la période jugée :
       a. au moins 1 000 matchs jugés,
       b. gain de log loss ≥ 0,001 par match par rapport à la base,
       c. même sens sur les deux périodes : β réappris sur 2023 → juin 2026 de même signe que β appris sur
          2018–2022, et gain positif sur 2018–2022 ;
  4. publiés à côté, sans décider : erreur type du gain (et « ≥ 2 erreurs types »), Brier, constat par quintile de u
     (favori réel contre annoncé) sur les deux périodes ;
  5. rien n'entre en production par ce paquet : un circuit retenu est PROPOSÉ à Lucas pour un paquet suivant, avec
     la règle de retrait cumulée habituelle (300 matchs, 2 erreurs types) ; un circuit non retenu est écarté et la
     piste n'est pas rejouée.
Les pronostics en direct ne servent qu'à confirmer, jamais à décider ; rien n'est jugé sur une centaine de matchs.

Rapport public : simulateur/rapport_pente_niveau.json — comptes et moyennes seulement, aucun nom de joueur. L'entrée
du journal (paquet 301) est écrite par cette étude avec ses résultats.

Usage : python simulateur/etude_pente_niveau.py /tmp/sackmann .
        python simulateur/etude_pente_niveau.py --journal-depuis-rapport simulateur/rapport_pente_niveau.json
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_pente_service as EPS  # noqa: E402  (outils communs : β, bilan, quintiles, journal)

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
ECHELLE = 200.0
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
SORTIE = os.path.join(ICI, 'rapport_pente_niveau.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_301.json')
PAQUET = 301


def mediane(v):
    s = sorted(v)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


# ------------------------------------------------------------------ rejeu de l'archive (dépôt complet nécessaire)
def lignes(archive, racine):
    """Une ligne par match jugé, vue du VAINQUEUR : circuit, date, z de l'Elo de production, variables des trois
    signaux solides (comme etude_outsiders.lignes) et 'niv' = ½ (Elo_A + Elo_B) sur la surface, avant le match."""
    import donnees as DN
    import elo as E
    import etude_age as EA
    import etude_changement_surface as ECS
    import etude_retour_absence as ERA
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d = m['circuit'], m['surface'], m['date']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in CIRCUITS and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            pr = min(max(el.proba(g, p, s), 1e-6), 1 - 1e-6)
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            rows.append({'c': c, 'd': d, 'z': math.log(pr / (1 - pr)),
                         'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1], xg[0], xg[1]),
                         'niv': 0.5 * (el.note(g, s) + el.note(p, s))})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows


def poser_indice(rows):
    """R_c appris sur 2018–2022 seulement ; écrit r['x'] = u. Renvoie {circuit: R_c}."""
    refs = {}
    for c in CIRCUITS:
        refs[c] = mediane([r['niv'] for r in rows if r['c'] == c and r['d'] < COUPURE])
        for r in rows:
            if r['c'] == c:
                r['x'] = (r['niv'] - refs[c]) / ECHELLE
    return refs


# ------------------------------------------------------------------ jugement (données factices possibles)
def juger_circuit(rows, c):
    A = [r for r in rows if r['c'] == c and r['d'] < COUPURE]
    J = [r for r in rows if r['c'] == c and r['d'] >= COUPURE]
    ZA, XA = [r['zb'] for r in A], [r['x'] for r in A]
    ZJ, XJ = [r['zb'] for r in J], [r['x'] for r in J]
    beta = EPS.apprendre_beta(ZA, XA) if A else 0.0
    beta_j = EPS.apprendre_beta(ZJ, XJ) if J else 0.0
    appr = EPS.bilan(ZA, [EPS.corriger(z, x, beta) for z, x in zip(ZA, XA)])
    juge = EPS.bilan(ZJ, [EPS.corriger(z, x, beta) for z, x in zip(ZJ, XJ)])
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append("moins de 1 000 matchs jugés")
    if juge.get('gain', -1.0) < MARGE:
        raisons.append("gain sous 0,001")
    if not (beta * beta_j > 0 and appr.get('gain', -1.0) > 0):
        raisons.append("pas le même sens sur les deux périodes")
    bornes = EPS.quintiles(XA)
    return {'circuit': NOM_CIRCUIT[c],
            'beta_appris_2018_2022': round(beta, 3), 'beta_reappris_2023_juin_2026': round(beta_j, 3),
            'bornes_quintiles_points_elo': [round(ECHELLE * b, 1) for b in bornes],
            '2018–2022': appr, '2023 → juin 2026': juge,
            'constat_par_quintile': {'2018–2022': EPS.constat(ZA, XA, bornes),
                                     '2023 → juin 2026': EPS.constat(ZJ, XJ, bornes)},
            'retenu': not raisons, 'raisons': raisons,
            'passe_deux_erreurs_types': (juge.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES}


def etudier(rows):
    return {c: juger_circuit(rows, c) for c in CIRCUITS}


REGLE = ("Circuit par circuit (ATP, WTA, Challenger). Correction z' = z·(1 + β·u), u = (½(Elo_A + Elo_B) − R_c)/200, "
         "niveau moyen des deux joueurs connu avant le match, R_c = médiane 2018–2022 du circuit. β appris sur 2018–2022, "
         "jugé une fois sur 2023 → juin 2026. Retenu si : ≥ 1 000 matchs jugés, gain de log loss ≥ 0,001, même sens sur "
         "les deux périodes (β réappris de même signe, gain positif sur 2018–2022). Erreur type, Brier et constat par "
         "quintile publiés sans décider. Rien en production par ce paquet.")


def phrase_resultats(res):
    fr = EPS.fr
    morceaux = []
    for c in CIRCUITS:
        v = res[c]
        j = v['2023 → juin 2026']
        if not j.get('matchs'):
            morceaux.append(f"{v['circuit']} : aucun match jugé")
            continue
        q = v['constat_par_quintile']['2023 → juin 2026']
        bas_, haut = (q[0] if q and q[0].get('matchs') else None), (q[-1] if q and q[-1].get('matchs') else None)
        detail = ''
        if bas_ and haut:
            detail = (f" ; matchs du bas (quintile 1) : favori {fr(bas_['favori_reel_pct'])} % réels pour "
                      f"{fr(bas_['favori_annonce_pct'])} % annoncés ; matchs du haut (quintile 5) : "
                      f"{fr(haut['favori_reel_pct'])} % pour {fr(haut['favori_annonce_pct'])} %")
        morceaux.append(f"{v['circuit']} : β {fr(v['beta_appris_2018_2022'])} (réappris {fr(v['beta_reappris_2023_juin_2026'])}), "
                        f"{j['matchs']} matchs jugés, gain {fr(j['gain'])} ± {fr(j['erreur_type'])}, Brier {fr(j['brier_base'])} → "
                        f"{fr(j['brier'])}{detail} — {'RETENU' if v['retenu'] else 'non retenu (' + ', '.join(v['raisons']) + ')'}")
    return ' ; '.join(morceaux) + '.'


def entree_journal(res, gabarit):
    retenus = [res[c]['circuit'] for c in CIRCUITS if res[c]['retenu']]
    fin = (f" Retenu sur : {', '.join(retenus)}. Proposé à Lucas pour un paquet suivant (règle de retrait cumulée) ; "
           f"rien n'est changé dans l'algo par ce paquet." if retenus else
           " Aucun circuit retenu : un écart d'Elo vaut la même chose en haut et en bas du circuit ; la piste est close "
           "et ne sera pas rejouée.")
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + ' RÉSULTAT : ' + phrase_resultats(res) + fin + ' Le % de victoire ne change pas.',
            'garde_fou': gabarit['garde_fou']}


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            EPS.ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    import etude_outsiders as EO
    rows = lignes(archive, racine)
    betas = EO.poser_la_base(rows)
    refs = poser_indice(rows)
    res = etudier(rows)
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        gabarit = json.load(f)
    entree = entree_journal(res, gabarit)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'paquet': PAQUET, 'regle': REGLE,
           'indice': ("u = (½(Elo_A + Elo_B) − R_c) / 200 ; Elo de production sur la surface du match, avant le match ; "
                      "R_c = médiane 2018–2022 du circuit"),
           'reference_elo_2018_2022': {NOM_CIRCUIT[c]: round(v, 1) for c, v in refs.items()},
           'elo': "réglé comme la production (elo.de_production), mis à jour après chaque match ; compétitions par équipes exclues",
           'base': {'signaux': ['changement_surface', 'retour_absence_court', 'retour_absence_long', 'age_vieux', 'age_jeune'],
                    'betas_2018_2022': betas},
           'circuits': res, 'en_production': False, 'entree_journal': entree}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    EPS.ajouter_au_journal(JOURNAL, entree)
    for c in CIRCUITS:
        v = res[c]
        print(v['circuit'], '| β', v['beta_appris_2018_2022'], '/', v['beta_reappris_2023_juin_2026'], '| jugé',
              v['2023 → juin 2026'], '| retenu :', v['retenu'], v['raisons'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
