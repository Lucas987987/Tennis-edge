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
  — six attributs (1 à 99), tirés des PROFILS AJUSTÉS de la simulation en production (profils_service.json,
    bloc « ajuste » : ajustement.py, choix_simulation.json = « ajustees »), sur le circuit et la surface du match :
      SER  points gagnés au service face à un relanceur moyen (« __moyen__ »), centile
      RET  points gagnés au retour face à un serveur moyen, centile
      ACE  aces par 1re balle dans le court face à un relanceur moyen, centile
      PRÉ  % de 1res balles, centile
      2E   sûreté de la 2e balle : centile inversé des doubles fautes par 2e balle (moins = mieux)
      FOR  forme : 50 + 200 × (victoires − victoires attendues) / matchs, sur les 40 derniers matchs
           (infos_avant_match.py, attendues = chances Elo d'avant chaque match), bornée à 1–99 ;
    les taux bruts des feuilles ne sont PAS utilisés : un joueur qui joue surtout des Challengers y paraît
    meilleur relanceur qu'il ne l'est (contrôle du 07/11 : Dzumhur, Brunold, Montes-de la Torre au-delà du
    94e centile ATP au retour brut). Les centiles sont pris parmi les joueurs actifs du groupe (fiches
    service / retour, Tennis_Edge_Lab/live/joueurs_service.json.gz) connus de l'ajustement ;
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
INVERSES = ('df',)                                             # moins = mieux
MOYEN = '__moyen__'                                            # adversaire moyen (ajustement.py)
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


def _p_service(c):
    return c['f'] * c['w1'] + (1 - c['f']) * (1 - c['d']) * c['w2j']


class Cartes:
    def __init__(self, service_doc, etat, infos=None, classement=None, ajuste=None):
        """ajuste : objet ajustement (Ajuste / AjusteDeux), celui de la simulation."""
        self.S = (service_doc or {}).get('joueurs') or {}
        self.A = ajuste
        self.E = (etat or {}).get('joueurs') or {}
        self.poids = float(((etat or {}).get('options') or {}).get('poids_surface') or 0.3)
        self.infos = infos or {}
        self.rangs = classement or {}
        self._ref, self._cache = {}, {}

    def valeurs(self, k, circuit, surface):
        """{'ser', 'ret', 'ace', 'pre', 'df'} du profil ajusté, ou None si le joueur est inconnu de l'ajustement."""
        if self.A is None or not self.A.connu(k):
            return None
        cle = (k, circuit, surface)
        if cle not in self._cache:
            import match_simule as MS
            sv = MS.borner(self.A.taux(k, MOYEN, circuit, surface))
            rt = MS.borner(self.A.taux(MOYEN, k, circuit, surface))
            self._cache[cle] = {'ser': _p_service(sv), 'ret': 1 - _p_service(rt), 'ace': sv['a'], 'pre': sv['f'], 'df': sv['d']}
        return self._cache[cle]

    def reference(self, groupe, circuit, surface):
        cle = (groupe, circuit, surface)
        if cle not in self._ref:
            R = {a: [] for a in ('ser', 'ret', 'ace', 'pre', 'df')}
            for k, f in self.S.items():
                if GROUPES.get(f.get('circuit')) != groupe:
                    continue
                v = self.valeurs(k, circuit, surface)
                if v:
                    for a in R:
                        R[a].append(v[a])
            for a in R:
                R[a].sort()
            self._ref[cle] = R
        return self._ref[cle]

    def carte(self, cle, nom, circuit, surface, jour=None, reussite=None):
        e = self.E.get(cle)
        groupe = GROUPES.get(circuit)
        if not e or not groupe:
            return None
        out = {'nom': nom}
        n_ = note_elo(elo_match(e, surface, self.poids))
        if n_ is not None:
            out['note'] = n_
        surf = {s_: note_elo(elo_match(e, s_, self.poids)) for s_ in SURFACES
                if (e.get('surfaces') or {}).get(s_) is not None}
        if surf:
            out['surfaces'] = surf
        at = {}
        v = self.valeurs(cle, circuit, surface)
        if v:
            R = self.reference(groupe, circuit, surface)
            for a, x in v.items():
                c_ = centile(R[a], x)
                if c_ is not None:
                    at[a] = _borne(100 - c_ if a in INVERSES else c_)
        r = reussite or {}
        if (r.get('matchs') or 0) >= FORME_MIN_MATCHS and r.get('ecart') is not None:
            at['for'] = _borne(50 + FORME_PENTE * float(r['ecart']) / r['matchs'])
        if len(at) == len(ATTRIBUTS):
            out['attributs'] = at
            out['valeurs'] = {a: round(100 * x, 1) for a, x in v.items()}
            if (self.S.get(cle) or {}).get('balles'):
                out['balles'] = self.S[cle]['balles']
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
    ajuste = None
    prof = _lire_json(os.path.join(racine, 'simulateur', 'profils_service.json'), {}) or {}
    if prof.get('ajuste'):
        import ajustement as AJ
        ajuste = AJ.importer(prof['ajuste'])
    return Cartes(service, etat, infos, {k: v['rang'] for k, v in rangs.items()}, ajuste)


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
