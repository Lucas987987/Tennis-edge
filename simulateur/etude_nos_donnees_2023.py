#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_nos_donnees_2023.py — paquet 531 (28/11/2026). Nos feuilles peuvent-elles remplacer l'archive Sackmann
depuis 2023 ? (l'archive est sous licence non commerciale ; nos feuilles anciennes, collectées par
collecte_feuilles_anciennes.py, couvrent l'ATP et la WTA depuis 2023 et le Challenger depuis 2024.)

RÈGLE ÉCRITE LE 28/11/2026, AVANT TOUT CALCUL — elle ne bouge plus une fois l'étude lancée :
  Deux historiques, même moteur, mêmes réglages :
    A (en place)  : Sackmann jusqu'à sa fin, nos feuilles ensuite (ce que fait l'algo aujourd'hui).
    B (candidat)  : Sackmann AVANT le 01/01/2023 (Challenger : avant le 01/01/2024), puis nos feuilles seules
                    (feuilles anciennes + feuilles du jour). Ce que nos feuilles ne couvrent pas (ITF) reste
                    Sackmann dans les deux.
  Comparaison des DONNÉES seulement : une ligne Sackmann retrouvée dans nos feuilles (même paire de joueurs,
  feuille datée entre le début du tournoi et +16 jours) prend la date réelle du match ; une ligne non retrouvée
  prend la fin du tournoi (jamais un résultat connu avant d'être joué).
  Matchs jugés : présents dans les deux sources, même vainqueur, ATP / WTA / Challenger (circuit de la feuille),
  chaque joueur avec au moins 5 matchs dans A ET dans B ; notes d'avant le jour du match.
  Deux composantes : l'Elo résultats (réglages de production, simulateur/elo_etat.json) et l'Elo au service et au
  retour (elo_service_retour.py ; η appris pour chaque source sur la période d'apprentissage).
  Apprentissage : du 01/07/2023 (Challenger : 01/07/2024, six mois de rodage) au 31/12/2024.
  Jugement : du 01/01/2025 au 31/05/2026.
  Mesure : log loss du vainqueur, circuit par circuit.
  Décision (non-infériorité : le changement vient de la licence, pas d'un gain attendu) : B remplace A si, pour les
  deux composantes et chaque circuit avec au moins 1 000 matchs jugés, B n'est pas pire de plus de 0,001 sur le
  jugement ET sur l'apprentissage. Si B est meilleur d'au moins 0,001 sur les deux périodes, c'est noté comme un gain.
  Sinon on garde A, et le rapport dit où B perd. Un circuit sous 1 000 matchs jugés ne décide rien.
Aucune cote n'entre ici. Seuls des comptes et des log loss sont affichés.

Usage : python simulateur/etude_nos_donnees_2023.py /tmp/sackmann [racine]
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

import donnees  # noqa: E402
import elo as E  # noqa: E402
import elo_service_retour as ESR  # noqa: E402
import feuilles as FE  # noqa: E402

D = dt.date
DEBUT_B = {'ATP': D(2023, 1, 1), 'WTA': D(2023, 1, 1), 'CH': D(2024, 1, 1)}
DEBUT_2023 = D(2023, 1, 1)
APPRENTISSAGE = {'ATP': D(2023, 7, 1), 'WTA': D(2023, 7, 1), 'CH': D(2024, 7, 1)}
FIN_APPRENTISSAGE = D(2025, 1, 1)
JUGEMENT = (D(2025, 1, 1), D(2026, 6, 1))
CIRCUITS = ('ATP', 'WTA', 'CH')
SEUIL, N_MIN, CONNU_MIN, FENETRE = 0.001, 1000, 5, 16
ETAS = (0.001, 0.0015, 0.002, 0.003, 0.004)
BAS = ('CH', 'ITF', 'ITFH')
SORTIE = os.path.join(ICI, 'rapport_nos_donnees_2023.json')


def periode(c, d):
    """'apprentissage', 'jugement' ou None pour un match du circuit c joué le jour d."""
    if c not in CIRCUITS:
        return None
    if APPRENTISSAGE[c] <= d < FIN_APPRENTISSAGE:
        return 'apprentissage'
    if JUGEMENT[0] <= d < JUGEMENT[1]:
        return 'jugement'
    return None


def grand_chelem_feuille(r):
    """Tableau final d'un Grand Chelem (2 000 points, hors qualifications) — la feuille n'a pas le niveau Sackmann."""
    return r.get('points_tournoi') == 2000 and 'qualif' not in str(r.get('tournoi') or '').lower()


def feuilles_toutes(racine):
    """Nos feuilles (anciennes + du jour, une feuille du jour l'emporte), forfaits écartés comme en production."""
    P = FE.points(racine)
    out, vus = [], set()
    for r, ancienne in [(r, False) for r in FE.lire(racine)] + [(r, True) for r in FE.lire_archive(racine)]:
        if r.get('id') is not None and r['id'] in vus:
            continue
        if 'walkover' in str((r.get('statut') or {}).get('texte') or '').lower():
            continue
        m = FE.en_match(r, (r.get('jeux') if ancienne else None) or P.get(r.get('id')))
        if not m or not m['nom_g'] or not m['nom_p']:
            continue
        vus.add(r.get('id'))
        m['gc'] = grand_chelem_feuille(r)
        m['ancienne'] = ancienne
        out.append(m)
    out.sort(key=lambda m: (m['date'], m.get('tour', 0), m['id'] or 0))
    return out


def alias_communs(racine, S, F):
    """Alias de production (elo_etat.json) + liens stricts (E.unifier) des noms des feuilles vers les noms Sackmann :
    les mêmes pour A et B, pour qu'un joueur reste un seul joueur quelle que soit la source."""
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    connus = {}
    for m in S:
        for n in (m['nom_g'], m['nom_p']):
            if n:
                connus.setdefault(E.cle(n), n)
    nouveaux = {n for m in F for n in (m['nom_g'], m['nom_p']) if n}
    for k, v in E.unifier(connus, nouveaux).items():
        alias.setdefault(k, v)
    return alias


def apparier(S, F, cle):
    """Relie chaque ligne Sackmann depuis 2023 à sa feuille : {i Sackmann: j feuille}."""
    index = collections.defaultdict(list)
    for j, f in enumerate(F):
        index[frozenset((cle(f['nom_g']), cle(f['nom_p'])))].append(j)
    pris, lien = set(), {}
    for i, s in enumerate(S):
        if s['date'] < DEBUT_2023 - dt.timedelta(days=FENETRE):
            continue
        cands = [j for j in index.get(frozenset((cle(s['nom_g']), cle(s['nom_p']))), ())
                 if j not in pris and s['date'] <= F[j]['date'] <= s['date'] + dt.timedelta(days=FENETRE)]
        if cands:
            j = min(cands, key=lambda j: F[j]['date'])
            pris.add(j)
            lien[i] = j
    return lien


def _evt(d, m, g, p, gc, ordre):
    stats = m['stats'] if (m.get('stats') and m.get('complet') and not m.get('abandon')) else None
    part = E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None
    return (d, ordre, g, p, m['circuit'], m['surface'], gc, part, stats)


def sources(S, F, lien, cle):
    """(A, B) : listes d'événements (jour, ordre, gagnant, perdant, circuit, surface, grand chelem, part des jeux,
    stats service) triées par jour."""
    fin_sack = max(s['date'] for s in S) if S else D(2000, 1, 1)
    vers_feuille = set(lien.values())
    A, B = [], []
    for i, s in enumerate(S):
        g, p = cle(s['nom_g']), cle(s['nom_p'])
        if not g or not p or g == p:
            continue
        gc = s.get('niveau') == 'G'
        if s['date'] < DEBUT_2023:
            e = _evt(s['date'], s, g, p, gc, (s.get('tour', 0), s.get('num', 0)))
            A.append(e)
            B.append(e)
            continue
        if i in lien:
            A.append(_evt(F[lien[i]]['date'], s, g, p, gc, (s.get('tour', 0), s.get('num', 0))))
            continue                                     # B : la feuille prend sa place
        d = s.get('fin') or s['date']
        A.append(_evt(d, s, g, p, gc, (s.get('tour', 0), s.get('num', 0))))
        debut = DEBUT_B.get(s['circuit'])
        if debut is None or s['date'] < debut:           # ITF, ou Challenger 2023 : nos feuilles n'y sont pas
            B.append(_evt(d, s, g, p, gc, (s.get('tour', 0), s.get('num', 0))))
    for j, f in enumerate(F):
        g, p = cle(f['nom_g']), cle(f['nom_p'])
        if not g or not p or g == p:
            continue
        e = _evt(f['date'], f, g, p, f.get('gc', False), (f.get('tour', 0), f.get('id') or 0))
        if f['date'] > fin_sack and j not in vers_feuille:   # déjà dans A par sa ligne Sackmann
            A.append(e)
        debut = DEBUT_B.get(f['circuit'])
        if (debut is not None and f['date'] >= debut) or j in vers_feuille or f['date'] > fin_sack:
            B.append(e)
    A.sort(key=lambda e: (e[0], e[1]))
    B.sort(key=lambda e: (e[0], e[1]))
    return A, B


def requetes(S, F, lien, cle):
    """Matchs jugés : présents dans les deux sources, même vainqueur, dans une des deux périodes.
    [(id, jour, gagnant, perdant, circuit, surface, sets gagnants, période)], désaccords de vainqueur."""
    out, desaccords = [], 0
    for i, j in lien.items():
        f, s = F[j], S[i]
        per = periode(f['circuit'], f['date'])
        if per is None:
            continue
        g, p = cle(f['nom_g']), cle(f['nom_p'])
        if not g or not p or g == p:
            continue
        if cle(s['nom_g']) != g:
            desaccords += 1
            continue
        sg = 3 if (f.get('bo') or s.get('bo')) == 5 else 2
        out.append((j, f['date'], g, p, f['circuit'], f['surface'], sg, per))
    out.sort(key=lambda q: q[1])
    return out, desaccords


def rejouer(evts, Q, faire, maj, connu):
    """Notes d'avant chaque jour : les matchs du jour q sont appliqués après les requêtes du jour q.
    faire(q) → probabilité du vainqueur ; renvoie {id: (p, matchs gagnant, matchs perdant)}."""
    out, i = {}, 0
    for q in Q:
        while i < len(evts) and evts[i][0] < q[1]:
            maj(evts[i])
            i += 1
        out[q[0]] = (faire(q), connu(q[2]), connu(q[3]))
    return out


def rejouer_elo(evts, Q, racine):
    el, bas = E.de_production(racine)

    def maj(e):
        d, _, g, p, c, s, gc, part, _ = e
        if bas and c in BAS:
            for k in (g, p):
                el.presenter(k, E.depart_du_niveau(c, bas))
        el.maj(g, p, s, gc, part)
    return rejouer(evts, Q, lambda q: el.proba(q[2], q[3], q[5]), maj, el.matchs)


def rejouer_sr(evts, Q, eta):
    el = ESR.EloSR(eta)

    def maj(e):
        if e[8]:
            el.maj(e[2], e[3], e[4], e[5], e[8])
    return rejouer(evts, Q, lambda q: el.proba(q[2], q[3], q[4], q[5], q[6]), maj, el.connu)


def _ll(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p)


def comparer(Q, ra, rb):
    """{période: {circuit: {n, ll_A, ll_B, ecart (B − A), erreur_type}}} sur les matchs connus des deux côtés."""
    acc = collections.defaultdict(list)
    for q in Q:
        a, b = ra.get(q[0]), rb.get(q[0])
        if not a or not b or min(a[1], a[2], b[1], b[2]) < CONNU_MIN:
            continue
        acc[(q[7], q[4])].append((_ll(a[0]), _ll(b[0])))
    out = {}
    for (per, c), L in sorted(acc.items()):
        n = len(L)
        la, lb = sum(x for x, _ in L) / n, sum(y for _, y in L) / n
        d = [y - x for x, y in L]
        md = sum(d) / n
        et = math.sqrt(sum((x - md) ** 2 for x in d) / max(n - 1, 1) / n) if n > 1 else None
        out.setdefault(per, {})[c] = {'n': n, 'll_A': round(la, 5), 'll_B': round(lb, 5), 'ecart': round(lb - la, 5),
                                      'erreur_type': round(et, 5) if et is not None else None}
    return out


def ll_global(Q, r, per):
    L = [_ll(r[q[0]][0]) for q in Q if q[7] == per and q[0] in r and min(r[q[0]][1], r[q[0]][2]) >= CONNU_MIN]
    return sum(L) / len(L) if L else float('inf')


def decider(comp):
    """Applique la règle de l'en-tête à {composante: comparer(...)}."""
    detail, decisifs, perd, gagne = {}, 0, [], []
    for nom, cp in comp.items():
        for c in CIRCUITS:
            j, a = (cp.get('jugement') or {}).get(c), (cp.get('apprentissage') or {}).get(c)
            if not j or j['n'] < N_MIN or not a:
                detail[f'{nom} {c}'] = 'pas assez de matchs jugés'
                continue
            decisifs += 1
            if j['ecart'] > SEUIL or a['ecart'] > SEUIL:
                perd.append(f'{nom} {c}')
                detail[f'{nom} {c}'] = 'B pire'
            elif j['ecart'] <= -SEUIL and a['ecart'] <= -SEUIL:
                gagne.append(f'{nom} {c}')
                detail[f'{nom} {c}'] = 'B meilleur'
            else:
                detail[f'{nom} {c}'] = 'équivalent'
    if not decisifs:
        verdict = 'pas assez de matchs : rien ne change'
    elif perd:
        verdict = 'garder Sackmann (B pire : ' + ', '.join(perd) + ')'
    else:
        verdict = 'remplacer Sackmann par nos feuilles depuis 2023' + (' (gain : ' + ', '.join(gagne) + ')' if gagne else '')
    return verdict, detail


def couverture(S, F, lien):
    """Comptes par circuit et année depuis 2023 : lignes Sackmann, retrouvées, feuilles, feuilles en plus, stats."""
    cpt = collections.defaultdict(collections.Counter)
    for i, s in enumerate(S):
        if s['date'] >= DEBUT_2023:
            k = f"{s['circuit']} {s['date'].year}"
            cpt[k]['sackmann'] += 1
            cpt[k]['sackmann_retrouvees'] += i in lien
            cpt[k]['sackmann_avec_stats'] += bool(s.get('stats'))
    lies = set(lien.values())
    for j, f in enumerate(F):
        if f['date'] >= DEBUT_2023:
            k = f"{f['circuit']} {f['date'].year}"
            cpt[k]['feuilles'] += 1
            cpt[k]['feuilles_absentes_de_sackmann'] += j not in lies
            cpt[k]['feuilles_avec_stats'] += bool(f.get('stats'))
    return {k: dict(v) for k, v in sorted(cpt.items())}


def collecte_finie(racine):
    """(jours collectés, jours attendus) des feuilles anciennes (historique/archive_feuilles/etat.json)."""
    attendus = (D(2026, 5, 31) - DEBUT_2023).days + 1
    try:
        with open(os.path.join(racine, 'historique', 'archive_feuilles', 'etat.json'), encoding='utf-8') as f:
            jours = (json.load(f).get('jours') or {})
    except (OSError, ValueError):
        jours = {}
    return sum(1 for j in jours if DEBUT_2023.isoformat() <= j <= '2026-05-31'), attendus


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    archive = args[0] if args else '/tmp/sackmann'
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    faits, attendus = collecte_finie(racine)
    if faits < attendus and '--forcer' not in argv:
        print(f'Collecte des feuilles anciennes pas finie : {faits}/{attendus} jours. '
              "L'étude ne se juge qu'une fois, sur la collecte complète : relance-la quand elle est finie.")
        return 0
    S = donnees.charger(archive, 2016)
    F = feuilles_toutes(racine)
    print(f'Sackmann : {len(S)} matchs · nos feuilles : {len(F)} '
          f'(dont {sum(1 for f in F if f["ancienne"])} anciennes)', flush=True)
    if not S or not F:
        print('::error::archive ou feuilles absentes')
        return 1
    alias = alias_communs(racine, S, F)
    cle = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    lien = apparier(S, F, cle)
    cov = couverture(S, F, lien)
    print('Couverture depuis 2023 (Sackmann / retrouvées dans nos feuilles / feuilles / feuilles en plus) :')
    for k, v in cov.items():
        print(f"  {k:9s} {v.get('sackmann', 0):6d} / {v.get('sackmann_retrouvees', 0):6d} / "
              f"{v.get('feuilles', 0):6d} / {v.get('feuilles_absentes_de_sackmann', 0):6d}")
    A, B = sources(S, F, lien, cle)
    Q, desaccords = requetes(S, F, lien, cle)
    print(f'Historique A : {len(A)} · B : {len(B)} · matchs à juger : {len(Q)} · vainqueurs en désaccord : {desaccords}',
          flush=True)

    comp = {'Elo résultats': comparer(Q, rejouer_elo(A, Q, racine), rejouer_elo(B, Q, racine))}
    choix = {}
    meilleurs = {}
    for nom, ev in (('A', A), ('B', B)):
        res = {eta: rejouer_sr(ev, Q, eta) for eta in ETAS}
        eta = min(ETAS, key=lambda e: ll_global(Q, res[e], 'apprentissage'))
        choix[nom], meilleurs[nom] = eta, res[eta]
        print(f'η appris pour {nom} : {eta}', flush=True)
    comp['Elo service / retour'] = comparer(Q, meilleurs['A'], meilleurs['B'])

    verdict, detail = decider(comp)
    for nom, cp in comp.items():
        print(f'— {nom} (log loss A → B, écart B − A)')
        for per in ('apprentissage', 'jugement'):
            for c, x in (cp.get(per) or {}).items():
                print(f"  {per:13s} {c:3s} n={x['n']:6d}  {x['ll_A']:.4f} → {x['ll_B']:.4f}  ({x['ecart']:+.4f} ± {x['erreur_type'] or 0:.4f})")
    print('Verdict :', verdict)
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': 531,
           'regle': 'non-infériorité : B ne doit pas être pire de plus de 0,001 sur les deux périodes, circuit par circuit, '
                    'pour les deux composantes (≥ 1 000 matchs jugés)',
           'apprentissage': {c: [APPRENTISSAGE[c].isoformat(), FIN_APPRENTISSAGE.isoformat()] for c in CIRCUITS},
           'jugement': [JUGEMENT[0].isoformat(), JUGEMENT[1].isoformat()],
           'sackmann_jusqu_au': max(s['date'] for s in S).isoformat(),
           'couverture': cov, 'matchs_a_juger': len(Q), 'vainqueurs_en_desaccord': desaccords,
           'eta_appris': choix, 'resultats': comp, 'detail': detail, 'verdict': verdict}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
