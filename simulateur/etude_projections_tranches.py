#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_projections_tranches.py — 24/11/2026 (paquet 421, Lucas : « est-ce qu'on peut le faire avec les autres projections
du match ? Est-ce que c'est mettre notre modèle en valeur ? » puis « lance l'étude »).

QUESTION
  Pour chaque projection affichée sur une fiche (1er set, sets secs, au moins un set, match au set décisif, au moins un
  tie-break, écart de jeux du favori, total de jeux), quand l'algo annonce X %, est-ce que ça arrive X % du temps ?
  Et fait-il mieux qu'une annonce naïve (la fréquence moyenne de l'événement sur le circuit) ?

RÈGLE (écrite avant de regarder les résultats ; étude DESCRIPTIVE : rien ne change dans l'algo ni sur le site)
  1. Données : nos propres projections FIGÉES AVANT LE MATCH, jamais recalculées :
       • simulateur/journal_pronostics/lignes_algo_v1.jsonl (une ligne par match, la première, figée avant le début) ;
       • simulateur/journal_pronostics/AAAA-MM-JJ.jsonl.gz : le PREMIER passage avant le début (répartition des sets,
         % de victoire) ;
     jugées sur le score réel de Tennis_Edge_Lab/live/pronostics_resultats.json. Matchs interrompus, scores invalides
     et circuits hors ATP / WTA / Challenger exclus. Aucune cote, aucun nom de joueur dans le rapport.
  2. Chaque projection est lue du côté que l'algo juge le plus probable (« l'algo dit oui » si p ≥ 50 %, « non »
     sinon) : confiance = max(p, 1 − p), « bon » = ce côté est arrivé. Tranches de 5 points : 50–55 … 95–100.
  3. Une tranche (ligne × circuit) n'est JUGÉE qu'à partir de 100 matchs (« on ne juge rien sur 100 matchs »). Elle
     « tient » si l'écart réalisé − annoncé reste dans ± 2 erreurs types binomiales (√(p(1−p)/n)) ; sinon « trop
     confiant » (réalisé plus bas) ou « trop prudent » (réalisé plus haut).
  4. Une projection entière (ligne × circuit, ≥ 100 matchs) « met le modèle en valeur » si les deux conditions sont
     réunies : (a) son Brier bat le Brier naïf (fréquence de l'événement sur le circuit et la période, calculée sur
     les mêmes matchs, donc avantageuse pour le naïf) ; (b) au moins 2/3 des tranches jugées « tiennent ». Sinon :
     « à corriger avant affichage » (a raté) ou « annonce à recaler » (b raté).
  5. Le résultat est un avis pour l'affichage. Toute correction de l'algo passerait par son étude propre et la règle
     2018–2022 / 2023 → juin 2026.
Usage : python simulateur/etude_projections_tranches.py [racine] [--sortie chemin]
"""
import glob
import gzip
import json
import math
import os
import sys

CIRCUITS = ('ATP', 'WTA', 'CH')
MIN_JUGE = 100
SORTIE = os.path.join('simulateur', 'rapport_projections_tranches.json')
LIBELLES = {
    'vainqueur': 'Vainqueur du match (favori de l’algo)',
    'set1_favori': 'Le favori gagne le 1er set',
    'sets_secs_favori': 'Le favori gagne sans perdre de set (l’autre côté : l’outsider gagne au moins un set)',
    'set_decisif': 'Match au set décisif',
    'tie_break': 'Au moins un tie-break',
}


def _lire_jsonl(chemin):
    out = []
    try:
        ouvrir = gzip.open if chemin.endswith('.gz') else open
        with ouvrir(chemin, 'rt', encoding='utf-8') as f:
            for l in f:
                l = l.strip()
                if l:
                    try:
                        out.append(json.loads(l))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def scores_reels(racine):
    """{uid: (circuit, [(a, b), …])} pour les matchs joués jusqu'au bout, score lisible."""
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for m in doc.get('matchs') or []:
        reel = m.get('reel') or {}
        if m.get('circuit') not in CIRCUITS or reel.get('interrompu') or reel.get('score_invalide'):
            continue
        if reel.get('gagnant') not in ('home', 'away') or not reel.get('score'):
            continue
        try:
            sets = [tuple(int(v.split('(')[0]) for v in s.split('-')) for s in str(reel['score']).split()]
        except ValueError:
            continue
        if not sets or any(len(s) != 2 for s in sets):
            continue
        gh = sum(1 for a, b in sets if a > b)
        if (gh > len(sets) - gh) != (reel['gagnant'] == 'home'):
            continue                                            # score incohérent avec le vainqueur : écarté
        out[m['uid']] = (m['circuit'], sets)
    return out


def premiers_passages(racine):
    """{uid: passage} : le PREMIER passage du journal quotidien enregistré avant le début du match."""
    out = {}
    for ch in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '20*.jsonl.gz'))):
        for r in _lire_jsonl(ch):
            uid, pas, deb = r.get('uid'), str(r.get('passage') or ''), str(r.get('debut_utc') or '')
            if not uid or uid in out or not pas or not deb:
                continue
            if pas.replace('Z', '+00:00')[:19] >= deb.replace('Z', '+00:00')[:19]:
                continue
            out[uid] = r
    return out


def evenements(racine):
    """Liste de (ligne, circuit, p_oui, y) — p_oui : probabilité annoncée que l'événement arrive, y : 0/1."""
    reels = scores_reels(racine)
    lignes = {}
    for r in _lire_jsonl(os.path.join(racine, 'simulateur', 'journal_pronostics', 'lignes_algo_v1.jsonl')):
        lignes.setdefault(r.get('uid'), r)                     # la première seulement
    passages = premiers_passages(racine)
    E = []
    for uid, (circ, sets) in reels.items():
        bo = 5 if max(sum(1 for a, b in sets if a > b), sum(1 for a, b in sets if b > a)) == 3 else 3
        jeux = sum(a + b for a, b in sets)
        ecart_home = sum(a - b for a, b in sets)
        home_gagne = sum(1 for a, b in sets if a > b) > len(sets) / 2
        P = passages.get(uid)
        comb = (P or {}).get('combinaison') or {}
        if isinstance(comb.get('p_home'), (int, float)):
            ph = float(comb['p_home'])
            fav_home = ph >= 0.5
            E.append(('vainqueur', circ, max(ph, 1 - ph), int(home_gagne == fav_home)))
            S = comb.get('sets') or {}
            if S:
                gag = (P.get('meilleur_des') or bo) // 2 + 1
                cle = f'{gag}-0' if fav_home else f'0-{gag}'
                if isinstance(S.get(cle), (int, float)):
                    secs = int(all((a > b) == fav_home for a, b in sets))
                    E.append(('sets_secs_favori', circ, float(S[cle]), secs))
        L = (lignes.get(uid) or {}).get('lignes') or {}
        if not L:
            continue
        fav = 1 if L.get('favori') == 'home' else -1
        mbo = L.get('meilleur_des', 3)
        for k, p in L.items():
            if not isinstance(p, (int, float)) or k in ('meilleur_des', 'jeux_moyen') or k.endswith('_brut'):
                continue
            if k.startswith('total_plus_'):
                y = int(jeux > float(k[len('total_plus_'):]))
                nom = f'{k}' + ('_bo5' if mbo == 5 else '')
            elif k.startswith('handicap_favori_'):
                y = int(fav * ecart_home > float(k[len('handicap_favori_'):]))
                nom = k + ('_bo5' if mbo == 5 else '')
            elif k == 'tie_break':
                y, nom = int(any(max(a, b) == 7 and min(a, b) == 6 for a, b in sets)), 'tie_break'
            elif k == 'set_decisif':
                y, nom = int(len(sets) == 2 * (mbo // 2) + 1), 'set_decisif'
            elif k == 'set1_home':
                # vu du favori de la ligne : P(favori gagne le 1er set)
                p = p if fav == 1 else 1 - p
                y, nom = int((sets[0][0] > sets[0][1]) == (fav == 1)), 'set1_favori'
            else:
                continue
            E.append((nom, circ, float(p), y))
    return E


def _tranche(c):
    i = min(int((c - 0.5) * 20 + 1e-9), 9)          # 0,70 tombe bien dans 70–75
    return f'{50 + 5 * i}-{55 + 5 * i}'


def juger(points):
    """points : [(p_oui, y)] → mesures, tranches et avis (règle de l'en-tête)."""
    n = len(points)
    if not n:
        return None
    base = sum(y for _, y in points) / n
    brier = sum((p - y) ** 2 for p, y in points) / n
    naif = sum((base - y) ** 2 for _, y in points) / n
    out = {'n': n, 'annonce_pct': round(100 * sum(p for p, _ in points) / n, 1), 'arrive_pct': round(100 * base, 1),
           'brier': round(brier, 4), 'brier_naif': round(naif, 4),
           'gain_vs_naif_pct': round(100 * (1 - brier / naif), 1) if naif > 0 else None}
    T = {}
    for p, y in points:
        c = max(p, 1 - p)
        T.setdefault(_tranche(c), []).append((c, int((p >= 0.5) == (y == 1))))
    tr, jugees, tiennent = {}, 0, 0
    for k in sorted(T, key=lambda s: int(s.split('-')[0])):
        L = T[k]
        m = len(L)
        a = sum(c for c, _ in L) / m
        r = sum(b for _, b in L) / m
        e = {'n': m, 'annonce_pct': round(100 * a, 1), 'bon_pct': round(100 * r, 1)}
        if m >= MIN_JUGE:
            se = math.sqrt(max(a * (1 - a), 1e-9) / m)
            e['verdict'] = 'tient' if abs(r - a) <= 2 * se else ('trop confiant' if r < a else 'trop prudent')
            jugees += 1
            tiennent += e['verdict'] == 'tient'
        else:
            e['verdict'] = 'trop tôt'
        tr[k] = e
    out['tranches'] = tr
    out['tranches_jugees'] = jugees
    out['tranches_qui_tiennent'] = tiennent
    if n < MIN_JUGE or not jugees:
        out['avis'] = 'trop tôt'
    elif brier >= naif:
        out['avis'] = 'à corriger avant affichage'
    elif tiennent * 3 < jugees * 2:
        out['avis'] = 'annonce à recaler'
    else:
        out['avis'] = 'met le modèle en valeur'
    return out


def etudier(racine):
    E = evenements(racine)
    par = {}
    for nom, circ, p, y in E:
        for c in ('TOUS', circ):
            par.setdefault(nom, {}).setdefault(c, []).append((p, y))
    projections = {}
    for nom in sorted(par, key=_ordre):
        projections[nom] = {'libelle': _libelle(nom),
                            'par_circuit': {c: juger(par[nom][c]) for c in ('TOUS',) + CIRCUITS if par[nom].get(c)}}
    return {'etude': 'projections_tranches', 'paquet': 421, 'min_juge': MIN_JUGE,
            'regle': "Projections figées avant le match, lues du côté jugé le plus probable ; tranches de 5 points jugées "
                     "à partir de 100 matchs (± 2 erreurs types) ; « met le modèle en valeur » = Brier meilleur que le "
                     "naïf et au moins 2/3 des tranches jugées qui tiennent. Descriptif : rien ne change dans l'algo.",
            'matchs_juges': sum(1 for nom, *_ in E if nom == 'vainqueur'),
            'projections': projections}


def _ordre(nom):
    rang = ['vainqueur', 'set1_favori', 'sets_secs_favori', 'set_decisif', 'tie_break']
    if nom in rang:
        return (rang.index(nom), 0.0)
    if nom.startswith('handicap_favori_'):
        return (10 + nom.endswith('_bo5'), float(nom.split('_')[2]))
    return (20 + nom.endswith('_bo5'), float(nom.split('_')[2]))


def _libelle(nom):
    if nom in LIBELLES:
        return LIBELLES[nom]
    bo = ' (au meilleur des 5)' if nom.endswith('_bo5') else ''
    k = nom.replace('_bo5', '').split('_')[-1].replace('.', ',')
    if nom.startswith('handicap_favori_'):
        return f'Le favori gagne de plus de {k} jeux{bo}'
    return f'Plus de {k} jeux dans le match{bo}'


def main(argv):
    racine, sortie = '.', None
    args = list(argv[1:])
    if '--sortie' in args:
        i = args.index('--sortie')
        sortie = args[i + 1]
        del args[i:i + 2]
    if args:
        racine = args[0]
    R = etudier(racine)
    chemin = sortie or os.path.join(racine, SORTIE)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f"Matchs jugés : {R['matchs_juges']} · projections : {len(R['projections'])}")
    for nom, v in R['projections'].items():
        t = v['par_circuit'].get('TOUS') or {}
        ligne = [f"{v['libelle']} : {t.get('n', 0)} matchs, annoncé {t.get('annonce_pct')} % → arrivé {t.get('arrive_pct')} %, "
                 f"gain sur le naïf {t.get('gain_vs_naif_pct')} % — {t.get('avis')}"]
        for c in CIRCUITS:
            x = v['par_circuit'].get(c)
            if x:
                ligne.append(f"    {c} : {x['n']} matchs, {x['annonce_pct']} → {x['arrive_pct']} %, {x['avis']}")
        print('\n'.join(ligne))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
