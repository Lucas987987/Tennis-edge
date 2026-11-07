#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cartes_joueurs.py — carte d'identité de chaque joueur du match, pour le site (07/11/2026, paquet 216).

DESCRIPTIF SEULEMENT : la carte ne change pas le %. Elle range le joueur parmi les joueurs actifs de SON
groupe de référence, avec les données déjà utilisées par l'algo. Groupes : hommes = joueurs actifs dont le
circuit principal est l'ATP ou le Challenger (une seule échelle, comme une note FIFA : le niveau du circuit
compte) ; femmes = joueuses actives dont le circuit principal est la WTA.

  — note (40 à 99) : niveau Elo du joueur sur la surface du match (même mélange que l'algo :
    (1 − poids_surface) × Elo général + poids_surface × Elo surface), sur une échelle FIXE commune à tous :
    note = 99 − (2400 − Elo) / 22, arrondie et bornée (repères au 07/11 : n° 1 mondiaux ≈ 92–97,
    100e ATP ≈ 69, 300e ≈ 59) ; un point de note = 22 points d'Elo ;
  — six attributs (1 à 99) :
      SER  Elo au service (elo_service_retour.py : ajusté à la force des relanceurs affrontés), centile
      RET  Elo au retour (ajusté à la force des serveurs affrontés), centile
      ACE  aces par 1re balle dans le court, centile (profil tous terrains, fiches_service.py)
      PRÉ  % de 1res balles, centile (même profil)
      2E   sûreté de la 2e balle : centile inversé des doubles fautes par 2e balle (moins = mieux)
      FOR  forme : 50 + 200 × (victoires − victoires attendues) / matchs, sur les 40 derniers matchs
           (infos_avant_match.py, attendues = chances Elo d'avant chaque match), bornée à 1–99 ;
    les centiles bruts (points gagnés au service ou au retour) ne sont PAS utilisés pour SER et RET : un joueur
    qui joue surtout des Challengers y paraît meilleur relanceur qu'il ne l'est (contrôle du 07/11 : Dzumhur,
    Brunold, Montes-de la Torre au-delà du 94e centile ATP au retour brut) ;
  — niveau par surface (dur, terre, gazon) : même échelle, Elo mélangé avec chaque surface ;
  — identité (TennisApi) : classement du jour, pays, âge, taille, main.

Sans profil documenté (moins de 300 balles de service), les attributs sont absents et la carte le dit.
Seuils fixes, choisis avant d'afficher la moindre carte ; aucune donnée de cotes n'entre ici.
"""
import bisect
import datetime as dt
import glob
import gzip
import json
import os

ATTRIBUTS = ('ser', 'ret', 'ace', 'pre', 'df', 'for')
SOURCE = {'ace': 'a', 'pre': 'f', 'df': 'd'}                  # profil tous terrains (fiches_service.py)
INVERSES = ('df',)                                             # moins = mieux
FORME_PENTE, FORME_MIN_MATCHS = 200.0, 10
SURFACES = ('Hard', 'Clay', 'Grass')
ELO_HAUT, ELO_PAR_POINT, NOTE_MIN, NOTE_MAX = 2400.0, 22.0, 40, 99
MIN_REFERENCE = 20                  # en dessous, pas de centile (référence trop mince)
GROUPES = {'ATP': 'hommes', 'CH': 'hommes', 'WTA': 'femmes'}


def _lire_json(chemin, defaut=None):
    try:
        if chemin.endswith('.gz'):
            with gzip.open(chemin, 'rt', encoding='utf-8') as f:
                return json.load(f)
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def centile(ref, x):
    """Centile de x dans la liste triée ref (0–100, ex aequo comptés pour moitié)."""
    if x is None or len(ref) < MIN_REFERENCE:
        return None
    bas, haut = bisect.bisect_left(ref, x), bisect.bisect_right(ref, x)
    return 100.0 * (bas + 0.5 * (haut - bas)) / len(ref)


def _borne(c):
    return None if c is None else max(1, min(99, int(round(c))))


def note_elo(elo):
    if elo is None:
        return None
    return int(max(NOTE_MIN, min(NOTE_MAX, round(NOTE_MAX - (ELO_HAUT - elo) / ELO_PAR_POINT))))


def elo_match(j, surface, poids):
    if not j:
        return None
    g = float(j.get('elo') or 0) or None
    if g is None:
        return None
    s = (j.get('surfaces') or {}).get(surface)
    return g if s is None else (1 - poids) * g + poids * float(s)


class Cartes:
    def __init__(self, service_doc, etat, infos=None, classement=None, sr=None):
        self.S = (service_doc or {}).get('joueurs') or {}
        self.SR = (sr or {}).get('joueurs') or {}
        self.E = (etat or {}).get('joueurs') or {}
        self.poids = float(((etat or {}).get('options') or {}).get('poids_surface') or 0.3)
        self.infos = infos or {}
        self.rangs = classement or {}
        self.ref = {}
        for k, f in self.S.items():
            c = GROUPES.get(f.get('circuit'))
            if not c:
                continue
            j = ((f.get('surfaces') or {}).get('all') or {}).get('joueur') or {}
            for a, src in SOURCE.items():
                if j.get(src) is not None:
                    self.ref.setdefault((c, a), []).append(j[src])
            n = self.SR.get(k)
            if n:
                self.ref.setdefault((c, 'ser'), []).append(n[0])
                self.ref.setdefault((c, 'ret'), []).append(n[1])
        for k in self.ref:
            self.ref[k].sort()

    def carte(self, cle, nom, circuit, surface, jour=None, reussite=None):
        e, f = self.E.get(cle), self.S.get(cle)
        if not e and not f:
            return None
        out = {'nom': nom}
        circuit = GROUPES.get(circuit)
        n_ = note_elo(elo_match(e, surface, self.poids))
        if n_ is not None:
            out['note'] = n_
        surf = {s_: note_elo(elo_match(e, s_, self.poids)) for s_ in SURFACES
                if e and (e.get('surfaces') or {}).get(s_) is not None}
        if surf:
            out['surfaces'] = surf
        j = (((f or {}).get('surfaces') or {}).get('all') or {}).get('joueur') or {}
        at = {}
        sr = self.SR.get(cle)
        if sr:
            for i, a in ((0, 'ser'), (1, 'ret')):
                v = _borne(centile(self.ref.get((circuit, a)) or [], sr[i]))
                if v is not None:
                    at[a] = v
        for a, src in SOURCE.items():
            c_ = centile(self.ref.get((circuit, a)) or [], j.get(src))
            if c_ is not None:
                at[a] = _borne(100 - c_ if a in INVERSES else c_)
        r = reussite or {}
        if (r.get('matchs') or 0) >= FORME_MIN_MATCHS and r.get('ecart') is not None:
            at['for'] = _borne(50 + FORME_PENTE * float(r['ecart']) / r['matchs'])
        if len(at) == len(ATTRIBUTS):
            out['attributs'] = at
            out['balles'] = f.get('balles')
            out['valeurs'] = {'ace': round(100 * j['a'], 1), 'pre': round(100 * j['f'], 1), 'df': round(100 * j['d'], 1),
                              'ser': round(100 * j['serv'], 1), 'ret': round(100 * j['ret'], 1)}
            if r:
                out['valeurs']['for'] = [r.get('victoires'), r.get('attendu'), r.get('matchs')]
        rang = self.rangs.get(cle)
        if rang:
            out['rang'] = rang
        i = self.infos.get(cle) or {}
        if i.get('taille_cm'):
            out['taille_cm'] = i['taille_cm']
        if i.get('main') in ('droite', 'gauche'):
            out['main'] = i['main']
        if i.get('naissance') and jour:
            try:
                n = dt.date.fromisoformat(i['naissance'][:10])
                out['age'] = jour.year - n.year - ((jour.month, jour.day) < (n.month, n.day))
            except ValueError:
                pass
        if i.get('pays'):
            out['pays'] = i['pays']
        return out


def charger(racine, etat):
    import elo as E
    service = _lire_json(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'joueurs_service.json.gz'), {})
    infos = {}
    brut = _lire_json(os.path.join(racine, 'feuilles', 'joueurs.json'), {}) or {}
    for v in sorted((v for v in brut.values() if isinstance(v, dict) and v.get('nom')), key=lambda v: v.get('maj') or ''):
        infos[E.cle(v['nom'])] = v
    rangs = {}
    fichiers = sorted(glob.glob(os.path.join(racine, 'feuilles', 'classements', '*.json')))
    if fichiers:
        doc = _lire_json(fichiers[-1], {}) or {}
        for circ in ('ATP', 'WTA'):
            for k, v in (doc.get(circ) or {}).items():
                if isinstance(v, list) and v:
                    rangs[k] = {'circuit': circ, 'rang': v[0]}
    sr = _lire_json(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'elo_service_retour.json'), {})
    return Cartes(service, etat, infos, {k: v['rang'] for k, v in rangs.items()}, sr)


def ajouter_cartes(lignes, racine, etat):
    """ligne['cartes'] = {descriptif_seulement, circuit, joueurs: [carte home, carte away]} si les deux existent."""
    import elo as E
    C = charger(racine, etat)
    for x in lignes:
        try:
            jour = dt.date.fromisoformat(str(x.get('debut'))[:10])
        except ValueError:
            jour = None
        av = x.get('avant_match') or {}
        cs = [C.carte(E.cle(x.get(c) or ''), x.get(c), x.get('circuit'), x.get('surface'), jour,
                      (av.get(c) or {}).get('reussite')) for c in ('home', 'away')]
        if all(cs) and all('note' in c for c in cs):
            x['cartes'] = {'descriptif_seulement': True, 'groupe': GROUPES.get(x.get('circuit')), 'surface': x.get('surface'),
                           'joueurs': cs}
