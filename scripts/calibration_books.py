#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibration_books.py — Les bookmakers sont-ils bien calibrés sur le tennis ?

RÉÉCRIT LE 25/08/2026. L'original (étude du 24/08, voir calibration_books.md)
a été détruit par une corruption d'upload : 12 542 octets, tous nuls, et aucune
version saine dans l'historique git — le fichier est arrivé corrompu dès son
premier commit. Reconstruit à partir du rapport publié, avec les mêmes
conventions que le reste du projet.

DEUX MESURES, DEUX QUESTIONS
1. Calibration par tranches : quand une cote implique p %, le joueur gagne-t-il
   vraiment p % du temps ? Probabilités DÉVIGÉES (Shin, la méthode validée du
   projet) — sinon on mesure surtout la marge de l'opérateur. Chaque match
   contribue DEUX entrées (une par côté), les tranches sont donc symétriques
   par construction (mêmes n en 15-30 et 70-85, etc.) : c'est un contrôle de
   cohérence gratuit, pas un bug.
2. Score de Brier par opérateur, sur ÉCHANTILLON COMMUN : uniquement les
   matchs où TOUS les opérateurs retenus cotent — sinon on comparerait des
   books sur des univers de matchs différents (le biais de sélection classique
   de ce projet). 0,25 = pile ou face ; plus bas est meilleur.

Probabilité mesurée = CLOSING (dernier point de courbe), le prix le mieux
informé — aucune valeur en cours de vie du match n'est utilisée (look-ahead).

Entrées : parts/hist_book_*.jsonl (une ligne par match×book),
          resultats_derived.json via results_join.ResultIndex.
Sortie  : calibration_books.md (racine, commité, lisible depuis GitHub).
Env     : MIN_COUVERTURE (déf 0.85) part minimale de l'échantillon commun
          qu'un book doit coter pour entrer dans le tableau Brier ;
          OUT_MD (déf calibration_books.md).
Aucune dépendance externe.
"""
import datetime
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import results_join as rj

OUT_MD = os.environ.get('OUT_MD', 'calibration_books.md')
MIN_COUVERTURE = float(os.environ.get('MIN_COUVERTURE', '0.85'))

# Tranches du rapport : symétriques autour de 50 %.
TRANCHES = [(0.00, 0.15), (0.15, 0.30), (0.30, 0.45), (0.45, 0.55),
            (0.55, 0.70), (0.70, 0.85), (0.85, 1.00)]


def shin_ph(oh, oa):
    """Probabilité dévigée (Shin) du côté home — identique à validation_report."""
    ih, ia = 1 / oh, 1 / oa
    ssum = ih + ia
    if ssum <= 1:
        return ih / ssum
    z = 0.02
    for _ in range(50):
        ph = (math.sqrt(z * z + 4 * (1 - z) * ih * ih / ssum) - z) / (2 * (1 - z))
        pa = (math.sqrt(z * z + 4 * (1 - z) * ia * ia / ssum) - z) / (2 * (1 - z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z = min(max(z + (t - 1), 0.0), 0.3)
    return ph / (ph + pa)


def closing(curve, commence_time):
    """Dernière cote valide AVANT le coup d'envoi.

    LE piège de ce projet (déjà corrigé une fois sur la mesure des courbes
    Pinnacle) : le dernier point d'une courbe est souvent IN-PLAY, la cote
    s'y est déjà effondrée vers l'issue connue. Le prendre donne une
    « calibration » miraculeuse (98 % de réussite en tranche 70-85 %) qui ne
    mesure que le look-ahead. On coupe strictement à commence_time.
    """
    coupure = str(commence_time or '').replace('Z', '')[:19]
    if not coupure:
        return None
    for pt in reversed(curve or []):
        try:
            if str(pt[0])[:19] > coupure:
                continue                      # point in-play : interdit
            o = float(pt[1])
            if o > 1:
                return o
        except (TypeError, ValueError, IndexError):
            continue
    return None


def _ouvrir(path):
    """Ouvre une partition, compressée ou non — les semaines passées sont en
    .gz (cleanup_partitions), seule la semaine courante est en clair."""
    if path.endswith('.gz'):
        import gzip
        return gzip.open(path, 'rt', encoding='utf-8', errors='replace')
    return open(path, encoding='utf-8', errors='replace')


def charger():
    """-> {cle_match: {'home','away','ct','books': {book: p_home_devig}}}
    avec le vainqueur résolu ; les matchs sans résultat sont écartés."""
    idx = rj.ResultIndex()
    matchs = {}
    n_lignes = 0
    # Étape 4 (16/10/2026) : historique figé servi par R2 (R2_HIST_MATERIALIZE=1).
    try:
        import r2_io
        r2_io.materialize_hist('book')
    except Exception:                           # noqa: BLE001
        pass
    fichiers = sorted(glob.glob('parts/hist_book_*.jsonl')
                      + glob.glob('parts/hist_book_*.jsonl.gz'))
    for f in fichiers:
        with _ouvrir(f) as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    r = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                n_lignes += 1
                h, a, bk = r.get('home'), r.get('away'), r.get('book')
                ct = r.get('commence_time')
                if not h or not a or not bk:
                    continue
                oh = closing(r.get('home_curve'), ct)
                oa = closing(r.get('away_curve'), ct)
                if not oh or not oa:
                    continue
                cle = (rj.paire(h, a), str(ct or '')[:10])
                m = matchs.setdefault(cle, {'home': h, 'away': a,
                                            'ct': ct, 'books': {}})
                # Doublon (match revu dans une partition plus récente) : on
                # garde la DERNIÈRE version lue = la plus proche du closing.
                m['books'][bk] = shin_ph(oh, oa)

    denoues = {}
    for cle, m in matchs.items():
        w = idx.winner(m['home'], m['away'], m['ct'])
        if w not in ('home', 'away'):
            continue
        m['gagnant_home'] = 1 if w == 'home' else 0
        denoues[cle] = m
    print(f"  {n_lignes} lignes match×book lues, {len(matchs)} matchs, "
          f"{len(denoues)} dénoués ({idx.ambigus} ambigus écartés)")
    return denoues


def table_calibration(matchs):
    """Tranches sur la MOYENNE des probabilités dévigées des books du match
    (les books sont indiscernables en qualité prédictive : la moyenne est un
    estimateur plus stable que n'importe quel book seul). Deux entrées par
    match : (p_home, issue_home) et (1-p_home, 1-issue_home)."""
    entrees = []
    for m in matchs.values():
        if not m['books']:
            continue
        p = sum(m['books'].values()) / len(m['books'])
        y = m['gagnant_home']
        entrees.append((p, y))
        entrees.append((1 - p, 1 - y))
    lignes = []
    for lo, hi in TRANCHES:
        sel = [(p, y) for p, y in entrees if lo <= p < hi] if hi < 1 else \
              [(p, y) for p, y in entrees if lo <= p <= hi]
        if not sel:
            lignes.append((lo, hi, None, None, 0))
            continue
        obs = sum(y for _, y in sel) / len(sel)
        ann = sum(p for p, _ in sel) / len(sel)
        lignes.append((lo, hi, obs, obs - ann, len(sel)))
    return lignes, len(entrees) // 2


def table_brier(matchs):
    """Brier par opérateur sur l'échantillon COMMUN.
    1. books candidats = présents sur >= MIN_COUVERTURE des matchs dénoués ;
    2. échantillon commun = matchs où TOUS les candidats cotent ;
    3. Brier par entrée-côté (2 par match), même n pour tous par construction."""
    total = len(matchs)
    couverture = {}
    for m in matchs.values():
        for bk in m['books']:
            couverture[bk] = couverture.get(bk, 0) + 1
    candidats = sorted(bk for bk, n in couverture.items()
                       if n >= MIN_COUVERTURE * total)
    commun = [m for m in matchs.values()
              if all(bk in m['books'] for bk in candidats)]
    scores = []
    for bk in candidats:
        s, n = 0.0, 0
        for m in commun:
            p, y = m['books'][bk], m['gagnant_home']
            s += (p - y) ** 2 + ((1 - p) - (1 - y)) ** 2
            n += 2
        if n:
            scores.append((bk, s / n, n))
    scores.sort(key=lambda x: x[1])
    return scores, len(commun)


def rendre(cal, n_matchs, briers, n_commun):
    jour = datetime.date.today().isoformat()
    L = []
    L.append('# Les bookmakers sont-ils bien calibrés sur le tennis ?\n')
    L.append(f'*Mesuré sur {n_matchs} matchs dénoués. Mise à jour du {jour}.*\n')
    L.append('Quand une cote implique 30 % de chances, le joueur gagne-t-il '
             'vraiment 30 % du temps ? Les probabilités ci-dessous sont '
             '**dévigées** : la marge de l\'opérateur est retirée, sinon on '
             'mesurerait surtout ce qu\'il prélève.\n')
    L.append('| Probabilité annoncée | Observé | Écart | n |')
    L.append('|---|---:|---:|---:|')
    for lo, hi, obs, ecart, n in cal:
        lab = f'{lo * 100:.0f} – {hi * 100:.0f} %'
        if obs is None:
            L.append(f'| {lab} | — | — | 0 |')
        else:
            L.append(f'| {lab} | {obs * 100:.1f} % | {ecart * 100:+.1f} pts | {n} |')
    L.append('')
    L.append('## Qualité prédictive par opérateur\n')
    L.append('| Opérateur | Score de Brier | n |')
    L.append('|---|---:|---:|')
    for bk, b, n in briers:
        L.append(f'| {bk} | {b:.4f} | {n} |')
    L.append('')
    L.append('Le **score de Brier** mesure la qualité d\'une prédiction '
             'probabiliste : 0,25 correspond à un pile ou face, plus bas est '
             'meilleur. Il ne dépend d\'aucun découpage en tranches. '
             f'Échantillon commun : {n_commun} matchs cotés par tous les '
             'opérateurs listés.\n')
    L.append('---\n')
    L.append('Un écart de calibration n\'est pas exploitable tel quel : la '
             'marge de l\'opérateur l\'absorbe. C\'est une information sur la '
             'qualité de ce que vous achetez, pas sur un rendement.\n')
    L.append('18+ · Jouer comporte des risques · joueurs-info-service.fr')
    return '\n'.join(L) + '\n'


def main():
    print('Calibration des bookmakers (closing dévigé Shin)')
    matchs = charger()
    if len(matchs) < 30:
        print(f'  n={len(matchs)} matchs dénoués — trop tôt pour publier (seuil 30).')
        return
    cal, n_matchs = table_calibration(matchs)
    briers, n_commun = table_brier(matchs)
    open(OUT_MD, 'w', encoding='utf-8').write(rendre(cal, n_matchs, briers, n_commun))
    print(f'  -> {OUT_MD} : {n_matchs} matchs, tableau Brier sur {n_commun} '
          f'communs, {len(briers)} opérateurs.')
    for lo, hi, obs, ecart, n in cal:
        if obs is not None:
            print(f'     {lo*100:3.0f}-{hi*100:3.0f}% : observé {obs*100:5.1f}% '
                  f'({ecart*100:+.1f} pts, n={n})')


if __name__ == '__main__':
    main()
