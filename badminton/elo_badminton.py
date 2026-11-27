#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo_badminton.py — LECTURE DES RÉSULTATS DU BADMINTON pour l'Elo (27/11/2026, Lucas : première étape du badminton).

Lecture des résultats collectés (historique/badminton/AAAA/AAAA-MM-JJ.jsonl.gz) et mise au format attendu par l'Elo du
tennis de table (tennis_de_table/elo_tt.py : rejouer, log_loss, pente — repris tels quels, rien n'est recopié).

Un camp = une entité : le joueur en simple, la PAIRE en double (l'identifiant de la paire, pas ses deux joueurs).

Matchs gardés : terminés normalement (statut « finished », sans abandon, forfait ni annulation), vainqueur connu
(g = 1 ou 2), un seul exemplaire par identifiant de match, deux camps de même nature (deux joueurs ou deux paires),
2 ou 3 manches régulières à 21 (21 avec 2 points d'écart, prolongations jusqu'à 30–29), et un vainqueur cohérent avec
les manches (il en a gagné 2, l'autre moins). Tout ce qui est écarté est compté, motif par motif.

Épreuve (simple messieurs, simple dames, double messieurs, double dames, double mixte), lue dans cet ordre :
  1. « nom »        le nom du tournoi le dit (MS, WS, MD, WD, XD, Men, Women, Mixed ; Thomas Cup = messieurs,
                    Uber Cup = dames) ; simple ou double vient des camps eux-mêmes (une paire s'écrit « A / B ») ;
  2. « joueurs »    le nom ne dit pas le sexe (« Singles », « Doubles » ou rien) : l'épreuve des AUTRES matchs des mêmes
                    joueurs ou paires, de proche en proche (une entité ne joue qu'une épreuve) ;
  3. « convention » toujours rien : messieurs, la convention du fournisseur (non marqué = messieurs), comptée à part.
L'épreuve ne sert qu'à ranger les résultats ; elle n'entre pas dans l'Elo.
"""
import collections
import glob
import gzip
import json
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(ICI), 'tennis_de_table'))
import elo_tt as ET  # noqa: E402

DOSSIER = os.path.join('historique', 'badminton')
EPREUVES = ['simple messieurs', 'simple dames', 'double messieurs', 'double dames', 'double mixte']
# Séries locales quotidiennes, hors circuits BWF (constat de lecture des noms de tournoi, avant tout essai).
HORS_CIRCUIT = ('armenia infinity cup',)
_SIGLE = re.compile(r'(?<![A-Za-z])(MS|WS|MD|WD|XD)(?![A-Za-z])')

rejouer, log_loss, pente, proba = ET.rejouer, ET.log_loss, ET.pente, ET.proba


def manche_reguliere(x, y):
    """Une manche à 21 terminée : 21 avec au moins 2 points d'écart, ou prolongation (2 d'écart, plafond 30–29)."""
    haut, bas = max(x, y), min(x, y)
    return (haut == 21 and bas <= 19) or (22 <= haut <= 30 and haut - bas == 2) or (haut == 30 and bas == 29)


def sexe_du_nom(tournoi):
    """'M', 'D' (dames), 'X' (mixte) ou None si le nom du tournoi ne le dit pas."""
    t = str(tournoi or '')
    bas = t.lower()
    s = _SIGLE.search(t)
    if (s and s.group(1) == 'XD') or 'mixed' in bas:
        return 'X'
    if s:
        return 'D' if s.group(1)[0] == 'W' else 'M'
    if 'women' in bas or 'uber cup' in bas:
        return 'D'
    if re.search(r'(?<![a-z])men(?![a-z])', bas) or 'thomas cup' in bas:
        return 'M'
    return None


def hors_circuit(tournoi):
    return str(tournoi or '').strip().lower().startswith(HORS_CIRCUIT)


def _nom_epreuve(double, sexe):
    if sexe == 'X':
        return 'double mixte' if double else None      # « mixte » en simple : illisible
    return ('double ' if double else 'simple ') + ('dames' if sexe == 'D' else 'messieurs')


def ligne_lue(r, jour=None):
    """Une ligne de l'historique → (dict du match, None) si elle est gardée, sinon (None, motif de l'écart)."""
    if r.get('statut') != 'finished':
        return None, 'non_termine'
    if r.get('detail'):
        return None, 'abandon_forfait'
    if r.get('g') not in (1, 2):
        return None, 'sans_vainqueur'
    h, a = (r.get('h') or [None, ''])[:2], (r.get('a') or [None, ''])[:2]
    if not h[0] or not a[0] or h[0] == a[0]:
        return None, 'camps_illisibles'
    dh, da = '/' in str(h[1]), '/' in str(a[1])
    if dh != da:
        return None, 'camps_dissemblables'
    M = r.get('manches') or []
    if len(M) not in (2, 3):
        return None, 'manches_absentes' if not M else 'nombre_de_manches'
    try:
        M = [(int(x), int(y)) for x, y in M]
    except (TypeError, ValueError):
        return None, 'manches_illisibles'
    if not all(manche_reguliere(x, y) for x, y in M):
        return None, 'manches_non_a_21'
    mh, ma = sum(1 for x, y in M if x > y), sum(1 for x, y in M if y > x)
    if max(mh, ma) != 2 or mh == ma or (r['g'] == 1) != (mh > ma):
        return None, 'vainqueur_incoherent'
    ph, pa = sum(x for x, _ in M), sum(y for _, y in M)
    noms = (tuple(x.strip() for x in str(h[1]).split('/')), tuple(x.strip() for x in str(a[1]).split('/'))) if dh else None
    if noms and (len(noms[0]) != 2 or len(noms[1]) != 2 or not all(noms[0] + noms[1])):
        noms = None                                    # paire illisible : reste une entité (étape 2, joueurs du double)
    return {'id': r.get('id'), 't': int(r.get('t') or 0), 'jour': jour, 'h': h[0], 'a': a[0], 'noms': noms,
            'y': 1 if r['g'] == 1 else 0, 'part': ph / (ph + pa), 'double': dh,
            'sexe': sexe_du_nom(r.get('tournoi')), 'hors': hors_circuit(r.get('tournoi'))}, None


def ranger_epreuves(L):
    """Donne à chaque match gardé son épreuve et la façon dont elle a été lue (« nom », « joueurs », « convention »)."""
    connu = collections.defaultdict(collections.Counter)      # entité → épreuves lues dans les noms de tournoi
    for m in L:
        m['epreuve'] = _nom_epreuve(m['double'], m['sexe']) if m['sexe'] else None
        m['lue_par'] = 'nom' if m['epreuve'] else None
        if m['epreuve']:
            connu[m['h']][m['epreuve']] += 1
            connu[m['a']][m['epreuve']] += 1
    for _ in range(10):                                        # de proche en proche
        trouves = []
        for m in L:
            if m['epreuve']:
                continue
            voix = connu.get(m['h'], collections.Counter()) + connu.get(m['a'], collections.Counter())
            voix = [(n, e) for e, n in voix.items() if e.startswith('double') == m['double']]
            if voix:
                trouves.append((m, sorted(voix, key=lambda v: (-v[0], v[1]))[0][1]))
        if not trouves:
            break
        for m, e in trouves:
            m['epreuve'], m['lue_par'] = e, 'joueurs'
            connu[m['h']][e] += 1
            connu[m['a']][e] += 1
    for m in L:
        if not m['epreuve']:
            m['epreuve'], m['lue_par'] = _nom_epreuve(m['double'], 'M'), 'convention'
    return L


def lire(racine='.', dossier=DOSSIER):
    """Lit tout l'historique. Renvoie (M, comptes) :
    M = [(t, jour, épreuve, id_h, id_a, y, part_points_h, hors_circuit, lue_par, noms)] trié par début (y = 1 si h
        gagne ; les 7 premières cases sont celles qu'attend elo_tt.rejouer ; noms = ((j1, j2), (j3, j4)), les deux
        joueurs de chaque paire en double, None en simple — étape 2 ; aucun nom n'est jamais écrit dans un rapport) ;
    comptes = lignes lues, matchs gardés, écarts par motif, façon de lire l'épreuve."""
    L, vus, ecarts, lues = [], set(), collections.Counter(), 0
    for p in sorted(glob.glob(os.path.join(racine, dossier, '20*', '20*.jsonl.gz'))):
        jour = os.path.basename(p)[:10]
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                lignes = [l for l in f if l.strip()]
        except OSError:
            ecarts['fichier_illisible'] += 1
            continue
        for l in lignes:
            lues += 1
            try:
                r = json.loads(l)
            except ValueError:
                ecarts['ligne_illisible'] += 1
                continue
            m, motif = ligne_lue(r, jour)
            if m is None:
                ecarts[motif] += 1
            elif m['id'] is not None and m['id'] in vus:
                ecarts['doublon'] += 1                         # déjà gardé une fois (même identifiant de match)
            else:
                vus.add(m['id'])
                L.append(m)
    ranger_epreuves(L)
    M = [(m['t'], m['jour'], m['epreuve'], m['h'], m['a'], m['y'], m['part'], m['hors'], m['lue_par'], m['noms']) for m in L]
    M.sort(key=lambda x: (x[0], str(x[3]), str(x[4])))
    comptes = {'lignes_lues': lues, 'matchs_gardes': len(M), 'matchs_ecartes': sum(ecarts.values()),
               'ecartes_par_motif': dict(sorted(ecarts.items())),
               'epreuve_lue_par': dict(sorted(collections.Counter(m[8] for m in M).items())),
               'hors_circuit': sum(1 for m in M if m[7])}
    return M, comptes


def matchs(racine='.', dossier=DOSSIER):
    return lire(racine, dossier)[0]
