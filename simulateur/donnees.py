#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
donnees.py — matchs au format Sackmann (statistiques de service) et jointure
avec tennis-data (clôture Pinnacle).

Source : archive publique des CSV de Jeff Sackmann (ses dépôts GitHub ont été
supprimés en 2026) : github.com/Aneeshers/tennis-sackmann-archive, instantané de
juin 2026, licence CC BY-NC-SA 4.0 (usage non commercial, attribution à Jeff
Sackmann). Le workflow « Simulateur » la clone ; rien n'est versionné ici.

Fichiers lus (n'importe où sous le dossier donné) :
  atp_matches_AAAA.csv            -> circuit ATP
  atp_matches_qual_chall_AAAA.csv -> CH (Challengers + qualifications)
  wta_matches_AAAA.csv            -> WTA
  wta_matches_qual_itf_AAAA.csv   -> ITF
"""
import csv
import datetime as dt
import glob
import gzip
import os
import re
import unicodedata

SURFACES = {'hard': 'Hard', 'clay': 'Clay', 'grass': 'Grass', 'carpet': 'Hard'}
# Ordre des tours dans un tournoi (rejouer les matchs dans l'ordre où ils ont eu lieu).
ORDRE_TOURS = {'Q1': 0, 'Q2': 1, 'Q3': 2, 'Q4': 3, 'ER': 4, 'R128': 4, 'R64': 5, 'R32': 6, 'RR': 6, 'R16': 7,
               'QF': 8, 'SF': 9, 'BR': 9, 'F': 10}


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z ]+', ' ', s.replace('-', ' ').replace("'", ' ')).split()


def _int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def score_sets(score):
    """'6-4 3-6 7-6(5)' -> ([(6,4),(3,6),(7,6)], complet). RET/W/O/DEF -> incomplet."""
    s = str(score or '').strip()
    complet = bool(s) and not re.search(r'RET|W/O|DEF|ABD|ABN|unfinished|Walkover|Def', s, re.I)
    sets = []
    for m in re.finditer(r'(\d+)-(\d+)(?:\(\d+\))?', s):
        sets.append((int(m.group(1)), int(m.group(2))))
    return sets, complet


def _circuit(nom):
    b = os.path.basename(nom)
    if b.startswith('atp_matches_qual_chall_'):
        return 'CH'
    if b.startswith('wta_matches_qual_itf_'):
        return 'ITF'
    if re.match(r'atp_matches_\d{4}\.csv', b):
        return 'ATP'
    if re.match(r'wta_matches_\d{4}\.csv', b):
        return 'WTA'
    return None


def fichiers(racine, annee_min=2018):
    out = []
    for f in glob.glob(os.path.join(racine, '**', '*_matches_*.csv'), recursive=True):
        c = _circuit(f)
        m = re.search(r'(\d{4})\.csv$', f)
        if c and m and int(m.group(1)) >= annee_min:
            out.append((f, c))
    return sorted(out)


def charger(racine, annee_min=2018):
    """Liste de matchs : dict(date, fin, circuit, surface, bo, gagnant, perdant, noms, stats, sets, complet)."""
    out = []
    for f, c in fichiers(racine, annee_min):
        tour = 'wta' if c in ('WTA', 'ITF') else 'atp'
        with open(f, encoding='utf-8', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh):
                d = str(r.get('tourney_date') or '')
                if len(d) != 8 or not r.get('winner_id') or not r.get('loser_id'):
                    continue
                try:
                    debut = dt.date(int(d[:4]), int(d[4:6]), int(d[6:]))
                except ValueError:
                    continue
                niveau = r.get('tourney_level') or ''
                fin = debut + dt.timedelta(days=15 if niveau == 'G' else 8)
                st = {}
                for p in ('w', 'l'):
                    n = _int(r.get(f'{p}_svpt'))
                    k1, k2 = _int(r.get(f'{p}_1stWon')), _int(r.get(f'{p}_2ndWon'))
                    if n and n >= 20 and k1 is not None and k2 is not None and 0 <= k1 + k2 <= n:
                        st[p] = (n, k1 + k2)
                sets, complet = score_sets(r.get('score'))
                out.append({
                    'date': debut, 'fin': fin, 'circuit': c,
                    'surface': SURFACES.get(str(r.get('surface') or '').lower(), 'Hard'),
                    'bo': _int(r.get('best_of')) or 3,
                    'gagnant': f"{tour}:{r['winner_id']}", 'perdant': f"{tour}:{r['loser_id']}",
                    'nom_g': r.get('winner_name') or '', 'nom_p': r.get('loser_name') or '',
                    'stats': st if len(st) == 2 else None, 'sets': sets, 'complet': complet,
                    'tournoi': r.get('tourney_name') or '',
                    'tour': ORDRE_TOURS.get(str(r.get('round') or '').upper(), 6),
                    'niveau': niveau,
                    'num': _int(r.get('match_num')) or 0,
                })
    out.sort(key=lambda m: (m['date'], m['tour'], m['num']))
    return out


# ------------------------------------------------------------------ tennis-data
def cles_sackmann(nom):
    """Clés (nom de famille, initiale) possibles : « Juan Martin del Potro » ->
    (del potro, j), (martin del potro, j), (potro, j)."""
    t = norm(nom)
    if len(t) < 2:
        return set()
    return {(' '.join(t[k:]), t[0][0]) for k in range(1, len(t))}


def cles_sackmann_etendues(nom):
    """Comme cles_sackmann, plus souple (22/10/2026) : nom de famille = n'importe quelle
    suite de mots après le prénom (« Mpetshi » pour Giovanni Mpetshi Perricard), initiale
    de n'importe quel prénom (« D. » pour Adolfo Daniel Vallejo). Renvoie
    {(nom de famille, initiale)} et les prénoms, pour départager « Xin. » et « Xiy. »."""
    t = norm(nom)
    out = set()
    for ordre in (t, t[::-1]):            # « Xinyu Wang » comme « Wang Xinyu »
        for k in range(1, len(ordre)):
            prenoms = ordre[:k]
            for j in range(k + 1, len(ordre) + 1):
                for p in prenoms:
                    out.add((' '.join(ordre[k:j]), p[0]))
    return out, t


def cle_td_prefixe(nom):
    """« Wang Xin. » -> ('wang', 'xin') ; « Fernandez L.A. » -> ('fernandez', 'l')."""
    brut = str(nom or '').strip()
    parts = brut.split()
    if len(parts) < 2:
        return None
    ini = parts[-1]
    if '.' not in ini and len(ini) > 3:
        return None
    nom_famille = ' '.join(norm(' '.join(parts[:-1])))
    pref = norm(ini.split('.')[0])
    if not nom_famille or not pref:
        return None
    return (nom_famille, pref[0])


def cle_td(nom):
    """« Del Potro J.M. » -> (del potro, j) ; « Bublik A. » -> (bublik, a)."""
    brut = str(nom or '').strip()
    parts = brut.split()
    if len(parts) < 2:
        return None
    ini = parts[-1]
    if '.' not in ini and len(ini) > 2:
        return None
    nom_famille = ' '.join(norm(' '.join(parts[:-1])))
    lettres = norm(ini.replace('.', ' '))
    if not nom_famille or not lettres:
        return None
    return (nom_famille, lettres[0][0])


def charger_td(chemin, depuis='2018-01-01'):
    """Clôtures Pinnacle tennis-data : date, circuit, vainqueur, perdant, psw, psl, tournoi, surface."""
    out = []
    op = gzip.open if chemin.endswith('.gz') else open
    with op(chemin, 'rt', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r['date'] < depuis:
                continue
            try:
                psw, psl = float(r['psw']), float(r['psl'])
            except (TypeError, ValueError):
                continue
            if psw <= 1 or psl <= 1:
                continue
            out.append({'date': dt.date.fromisoformat(r['date']), 'circuit': r['circuit'],
                        'vainqueur': r['vainqueur'], 'perdant': r['perdant'], 'psw': psw, 'psl': psl,
                        'tournoi': r.get('tournoi') or '',
                        'surface': SURFACES.get(str(r.get('surface') or '').lower(), 'Hard')})
    return out


def joindre(td, matchs, fenetre=16):
    """Associe chaque match tennis-data à son match Sackmann (même paire, date du
    match dans [début du tournoi ; début + fenêtre]). Retourne [(td, sackmann)]."""
    index = {}
    for i, m in enumerate(matchs):
        if m['circuit'] not in ('ATP', 'WTA'):
            continue
        for kg in cles_sackmann(m['nom_g']):
            for kp in cles_sackmann(m['nom_p']):
                index.setdefault((kg, kp), []).append(i)
    paires, pris = [], set()
    for t in td:
        kg, kp = cle_td(t['vainqueur']), cle_td(t['perdant'])
        if not kg or not kp:
            continue
        cands = [i for i in index.get((kg, kp), [])
                 if i not in pris and matchs[i]['date'] <= t['date'] <= matchs[i]['date'] + dt.timedelta(days=fenetre)]
        if len(cands) == 1:
            pris.add(cands[0])
            paires.append((t, matchs[cands[0]]))
    return paires
