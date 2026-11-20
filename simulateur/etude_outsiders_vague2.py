#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_outsiders_vague2.py — « REPÉRER LES OUTSIDERS QUI GAGNENT », DEUXIÈME VAGUE (20/11/2026, paquet 304, décision
de Lucas : « On lance la deuxième vague »). Suite de etude_outsiders_gagnants.py (paquet 273), dont deux situations
sont en place en Challenger depuis le paquet 274 (favori fatigué, outsider mieux classé).

Question : dans quelles autres situations, connues AVANT le match, l'outsider gagne-t-il plus souvent qu'annoncé ?
Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match. BASE = ce que l'algo annonce aujourd'hui : Elo de production + les trois signaux solides (changement de surface,
retour d'absence, âge ; β appris sur 2018–2022 comme au paquet 273) + EN CHALLENGER les deux décalages déjà en place
(simulateur/outsiders_ch.json, mêmes définitions que pronostics_du_jour.py). Une situation n'est donc jugée que sur ce
qu'elle ajoute à l'algo actuel. Matchs jugés : ATP, WTA, Challenger, sans abandon ni compétition par équipes.
Outsider = le joueur que la base donne entre 15 et 45 %.

TROIS SITUATIONS NOUVELLES (vues de l'outsider, toutes connues avant le match) :
  1. favori_charge        — le favori a joué au moins 8 matchs (tous circuits de l'archive, qualifications comprises)
                            dans les 21 jours avant ce match, sur au moins 2 tournois, et l'outsider au moins 3 de moins ;
  2. dynamiques_opposees  — sur les 60 derniers jours, la note Elo générale du favori a baissé d'au moins 30 points et
                            celle de l'outsider a monté d'au moins 30 points (les deux joueurs déjà notés 60 jours avant) ;
  3. favori_enchaine      — le favori a atteint au moins les demi-finales d'un autre tournoi commencé dans les 14 jours
                            précédents, et joue ici son premier match.

RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup), situation par situation
et CIRCUIT PAR CIRCUIT : un décalage (logit) vers l'outsider est appris sur 2018–2022 sur les matchs concernés, puis
jugé une seule fois sur 2023 → juin 2026 sur les matchs concernés. RETENU si : au moins 1 000 matchs concernés jugés ;
gain de log loss ≥ 0,001 ; gain ≥ 2 erreurs types ; et l'outsider concerné gagne plus qu'annoncé sur les DEUX périodes.
Un résultat retenu n'entre dans l'algo que par un paquet à part, avec sa règle de retrait. Rapport public :
simulateur/rapport_outsiders_vague2.json (aucun nom de joueur). Descriptif tant que rien n'est mis en place.
Usage : python simulateur/etude_outsiders_vague2.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys
from collections import deque

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402
import etude_age as EA  # noqa: E402
import etude_changement_surface as ECS  # noqa: E402
import etude_retour_absence as ERA  # noqa: E402
import etude_signaux_combines as ESC  # noqa: E402
import etude_outsiders as EO  # noqa: E402
import etude_outsiders_gagnants as EOG  # noqa: E402

DEBUT, COUPURE, FIN = EO.DEBUT, EO.COUPURE, EO.FIN
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
OUTSIDER = (0.15, 0.45)
SITUATIONS = ('favori_charge', 'dynamiques_opposees', 'favori_enchaine')
CHARGE_JOURS, CHARGE_MIN, CHARGE_ECART = 21, 8, 3
DYN_JOURS, DYN_POINTS = 60, 30.0
ENCHAINE_JOURS, DEMI = 14, 9                        # tour 9 = demi-finale (donnees.ORDRE_TOURS)
SORTIE = os.path.join(ICI, 'rapport_outsiders_vague2.json')
_lg, _sg = EOG._lg, EOG._sg


def decalages_ch(racine):
    """Les deux décalages Challenger en place (paquet 274), sauf ceux retirés."""
    try:
        with open(os.path.join(racine, 'simulateur', 'outsiders_ch.json'), encoding='utf-8') as f:
            S = json.load(f).get('signaux') or {}
    except (OSError, ValueError):
        return {}
    return {k: float(v['beta']) for k, v in S.items() if not v.get('retire') and v.get('beta') is not None}


def note_il_y_a(hist, d, jours):
    """Note du joueur à la date d − jours (dernière note connue à cette date), sinon None."""
    limite = d - dt.timedelta(days=jours)
    avant = None
    for dd, n in hist:
        if dd <= limite:
            avant = n
        else:
            break
    return avant


def lignes(archive, racine):
    """Une ligne par match jugé, vue du VAINQUEUR, avec les situations vues du vainqueur et du perdant."""
    M = DN.charger(archive, 2012)
    X = EOG.extras(archive)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    dernier = {}            # joueur → (tournoi_id, match long ?)
    joues = {}              # joueur → deque[(date de début du tournoi, tournoi_id)]
    notes = {}              # joueur → [(date, note générale après le match)] sur ~120 jours
    parcours = {}           # joueur → {tournoi_id: (date de début, meilleur tour atteint)}
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d, tid = m['circuit'], m['surface'], m['date'], m.get('tournoi_id')
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in ('ATP', 'WTA', 'CH') and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            z = _lg(el.proba(g, p, s))
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            ex = X.get((str(tid or ''), m.get('num') or 0, m.get('nom_g') or ''))

            def vue(j, rang):
                dj = dernier.get(j)
                recents = [(dd, t) for dd, t in joues.get(j, ()) if 0 <= (d - dd).days <= CHARGE_JOURS]
                n_avant = note_il_y_a(notes.get(j, []), d, DYN_JOURS)
                premier_ici = not dj or dj[0] != tid
                enchaine = any(t != tid and 1 <= (d - dd).days <= ENCHAINE_JOURS and tour >= DEMI
                               for t, (dd, tour) in parcours.get(j, {}).items())
                return {'long': bool(dj and dj[0] == tid and dj[1]),
                        'court': bool(not dj or dj[0] != tid or not dj[1]),
                        'rang': rang,
                        'charge': len(recents), 'tournois': len({t for _, t in recents}),
                        'dyn': None if n_avant is None else el.note(j) - n_avant,
                        'enchaine': enchaine and premier_ici}
            vg = vue(g, ex[2] if ex else None)
            vp = vue(p, ex[3] if ex else None)
            rows.append({'c': c, 'd': d, 'z': z,
                         'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1], xg[0], xg[1]),
                         'vg': vg, 'vp': vp})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        long_match = len(m.get('sets') or []) >= (5 if m.get('bo') == 5 else 3)
        tour = m.get('tour') or 0
        for j in (g, p):
            dernier[j] = (tid, long_match)
            q = joues.setdefault(j, deque(maxlen=40))
            q.append((d, tid))
            pj = parcours.setdefault(j, {})
            pj[tid] = (d, max(tour, pj.get(tid, (d, 0))[1]))
            if len(pj) > 12:
                for t in sorted(pj, key=lambda t: pj[t][0])[:len(pj) - 12]:
                    del pj[t]
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
        for j in (g, p):
            h = notes.setdefault(j, [])
            h.append((d, el.note(j)))
            while h and (d - h[0][0]).days > DYN_JOURS + 60:
                h.pop(0)
    return rows


def outsider(r):
    """(o, f, p de l'outsider, signe) : signe +1 si l'outsider est le vainqueur ; None hors 15–45 %."""
    pw = _sg(r['zb'])
    if pw > 0.5:
        o, f, p_out, signe = r['vp'], r['vg'], 1 - pw, -1.0
    else:
        o, f, p_out, signe = r['vg'], r['vp'], pw, 1.0
    if not (OUTSIDER[0] <= p_out <= OUTSIDER[1]):
        return None
    return o, f, p_out, signe


def poser_ch_en_place(rows, D):
    """En Challenger, ajoute à la base les décalages du paquet 274 (vers l'outsider), comme pronostics_du_jour.py."""
    n = {'favori_fatigue': 0, 'outsider_mieux_classe': 0}
    for r in rows:
        if r['c'] != 'CH':
            continue
        x = outsider(r)
        if not x:
            continue
        o, f, _, signe = x
        add = 0.0
        if 'favori_fatigue' in D and f['long'] and o['court']:
            add += D['favori_fatigue']
            n['favori_fatigue'] += 1
        if 'outsider_mieux_classe' in D and o['rang'] and f['rang'] and o['rang'] < f['rang']:
            add += D['outsider_mieux_classe']
            n['outsider_mieux_classe'] += 1
        r['zb'] += signe * add
    return n


def situation(nom, o, f):
    if nom == 'favori_charge':
        return f['charge'] >= CHARGE_MIN and f['tournois'] >= 2 and o['charge'] <= f['charge'] - CHARGE_ECART
    if nom == 'dynamiques_opposees':
        return f['dyn'] is not None and o['dyn'] is not None and f['dyn'] <= -DYN_POINTS and o['dyn'] >= DYN_POINTS
    if nom == 'favori_enchaine':
        return f['enchaine']
    return False


def cas(r, nom):
    x = outsider(r)
    if not x or not situation(nom, x[0], x[1]):
        return None
    _, _, p_out, signe = x
    return signe, p_out, 1 if signe > 0 else 0


def juger(rows, c, nom):
    A, J = [], []
    for r in rows:
        if r['c'] != c:
            continue
        x = cas(r, nom)
        if x:
            (A if r['d'] < COUPURE else J).append((r['zb'], x))
    if len(A) < 50:
        return {'matchs_2018_2022': len(A), 'matchs_2023': len(J), 'retenu': False, 'raisons': ['trop peu de cas']}
    beta = ESC.apprendre([(z, (x[0],)) for z, x in A], k=1)[0]
    f_ = lambda z, x: z + beta * x[0]  # noqa: E731
    appr = EO.bilan([z for z, _ in A], [f_(z, x) for z, x in A])
    juge = EO.bilan([z for z, _ in J], [f_(z, x) for z, x in J]) if J else {'matchs': 0}
    taux = lambda L: {'annonce_pct': round(100 * sum(x[1] for _, x in L) / len(L), 1),  # noqa: E731
                      'reel_pct': round(100 * sum(x[2] for _, x in L) / len(L), 1)} if L else {}
    oa, oj = taux(A), taux(J)
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f'moins de {MIN_JUGES} matchs jugés')
    if juge.get('gain', -1) < MARGE:
        raisons.append(f'gain sous {MARGE}')
    if (juge.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f'gain sous {MIN_ERREURS_TYPES:g} erreurs types')
    if not (oa and oj and oa['reel_pct'] > oa['annonce_pct'] and oj['reel_pct'] > oj['annonce_pct']):
        raisons.append("l'outsider ne gagne pas plus qu'annoncé sur les deux périodes")
    return {'decalage_appris': round(beta, 4), 'outsider_2018_2022': oa, 'outsider_2023': oj,
            '2018–2022': appr, '2023 → juin 2026': juge, 'retenu': not raisons, 'raisons': raisons}


def regle():
    return (__doc__.split('RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup),')[1]
            .split('Usage')[0].replace('\n', ' ').replace('  ', ' ').strip())


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows = lignes(archive, racine)
    betas = EO.poser_la_base(rows)
    D = decalages_ch(racine)
    n_ch = poser_ch_en_place(rows, D)
    res = {nom: {c: juger(rows, c, nom) for c in ('ATP', 'WTA', 'CH')} for nom in SITUATIONS}
    retenus = [f'{nom} · {c}' for nom, v in res.items() for c, r in v.items() if r.get('retenu')]
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 304,
           'regle': regle(),
           'situations_definies': {'favori_charge': f'favori ≥ {CHARGE_MIN} matchs sur {CHARGE_JOURS} jours, sur au moins 2 '
                                                    f'tournois ; outsider au moins {CHARGE_ECART} de moins',
                                   'dynamiques_opposees': f'sur {DYN_JOURS} jours : favori −{DYN_POINTS:g} points d\'Elo '
                                                          f'ou plus, outsider +{DYN_POINTS:g} ou plus',
                                   'favori_enchaine': f'favori demi-finaliste ou mieux d\'un autre tournoi commencé dans '
                                                      f'les {ENCHAINE_JOURS} jours, premier match ici'},
           'base': {'elo': 'réglé comme la production', 'signaux': 'surface, absence, âge', 'betas_2018_2022': betas,
                    'challenger_en_place': {k: round(v, 4) for k, v in D.items()},
                    'challenger_cas_corriges': n_ch},
           'situations': res, 'retenus': retenus,
           'conclusion': ('retenus : ' + ', '.join(retenus)) if retenus else 'aucune situation ne passe la règle',
           'descriptif': 'le % de victoire ne change pas'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for nom, v in res.items():
        for c, r in v.items():
            j, oa, oj = r.get('2023 → juin 2026') or {}, r.get('outsider_2018_2022') or {}, r.get('outsider_2023') or {}
            print(f"{nom:20s} {c:3s} β={r.get('decalage_appris')} n18={r.get('2018–2022', {}).get('matchs', r.get('matchs_2018_2022'))} "
                  f"n23={j.get('matchs', r.get('matchs_2023'))} gain={j.get('gain')} et={j.get('erreurs_types')} "
                  f"out18 {oa.get('reel_pct')}/{oa.get('annonce_pct')} out23 {oj.get('reel_pct')}/{oj.get('annonce_pct')} "
                  f"{'RETENU' if r.get('retenu') else ', '.join(r.get('raisons', []))}")
    print(doc['conclusion'])


if __name__ == '__main__':
    main(sys.argv)
