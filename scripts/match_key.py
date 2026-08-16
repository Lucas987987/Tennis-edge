#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_key.py — Identifiant CANONIQUE de match, unique quelle que soit la source.

PROBLÈME RÉSOLU (16/08/2026)
Deux conventions d'uid coexistent dans les courbes :
  • ancienne, par tournoi : atp_montreal_matteo_arnaldi_vs_tallon_griekspoor
  • actuelle, par date    : 2026-08-07_tallon_griekspoor_matteo_arnaldi
La bascule s'est faite le 10/08/2026, mais du 11/06 au 09/08 LES DEUX ont été
écrites. Résultat : 162 matchs présents sous deux uid distincts, donc comptés
DEUX FOIS par toute analyse qui déduplique sur l'uid.
Symptôme qui l'a révélé : Tallon Griekspoor apparaissait deux fois à cote 5,77
avec le même gain, et pesait à lui seul 48 % du cumul de sa tranche de cotes.

Pourquoi une simple comparaison de chaînes ne suffit pas : dans 2634 cas sur
2700, le premier joueur de l'uid « tournoi » n'est PAS le `home` de
l'enregistrement. L'ordre des noms dans l'identifiant ne suit pas home/away.

MÉTHODE
  1. clé naturelle = { joueurs normalisés } + horaire à l'heure près
     (insensible à l'ordre home/away, aux accents, à la casse, au tournoi)
  2. fusion par `fixture_id` via union-find : deux enregistrements partageant
     un fixture_id sont le même match, même si horaire ou noms diffèrent
     (report d'horaire, orthographe alternative...)

PRUDENCE DÉLIBÉRÉE : sans fixture_id commun, deux horaires de JOURS différents
restent deux matchs distincts. Un report de match non couvert par un fixture_id
sera donc compté deux fois — on préfère surcompter que fusionner à tort deux
rencontres réelles entre les mêmes joueurs.

Usage :
    import match_key as mk
    idx = mk.build_index(records)        # records = dicts de courbes
    cle = idx.key_of(uid)                # -> identifiant canonique stable
"""
import re, unicodedata, collections


def _toks(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return frozenset(t for t in re.split(r'[^a-z]+', s) if len(t) >= 3)


def natural_key(home, away, commence):
    """Clé insensible à l'ordre des joueurs, à la JOURNÉE près.

    Pourquoi la journée et non l'heure : pour un même uid, commence_time varie
    d'une source à l'autre, jusqu'à 4 heures d'écart (mélange UTC / heure
    locale selon les enregistrements). Une clé à l'heure près n'était donc PAS
    stable — 27 uid changeaient d'identifiant selon l'ordre de lecture, ce qui
    aurait cassé le gel du registre entre deux runs.
    Deux rencontres entre les mêmes joueurs le même jour n'existent pas en
    pratique, la journée est donc une granularité sûre.
    """
    pair = frozenset({_toks(home), _toks(away)})
    return (pair, str(commence or '')[:10])      # YYYY-MM-DD


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _label(nat):
    """Chaîne DÉTERMINISTE et lisible depuis une clé naturelle.

    Indispensable : repr(frozenset) n'a PAS d'ordre garanti d'une exécution à
    l'autre. Utiliser ce repr comme identifiant stocké (registre gelé, CSV)
    produirait des clés différentes au run suivant pour le MÊME match. On trie
    donc explicitement, à tous les niveaux.
    """
    pair, when = nat
    joueurs = sorted('-'.join(sorted(p)) for p in pair)
    return f"{joueurs[0]}_vs_{joueurs[1]}@{when}" if len(joueurs) > 1 else f"{joueurs[0]}@{when}"


class Index:
    def __init__(self, uid2canon, groups, labels):
        self._m = uid2canon
        self.groups = groups          # canon -> set(uid)
        self._labels = labels         # canon -> chaîne stable

    def key_of(self, uid):
        """Identifiant canonique STABLE et lisible ; repli sur l'uid si inconnu."""
        c = self._m.get(uid)
        if c is None:
            return uid
        return self._labels.get(c, uid)

    @property
    def n_merged(self):
        return sum(len(v) - 1 for v in self.groups.values() if len(v) > 1)

    def report(self):
        dup = {k: v for k, v in self.groups.items() if len(v) > 1}
        return (f"{len(self._m)} uid -> {len(self.groups)} matchs canoniques "
                f"({len(dup)} groupes fusionnés, {self.n_merged} uid en doublon)")


def build_index(records):
    """records : itérable de dicts ayant uid, home/home_team, away/away_team,
    commence_time et éventuellement fixture_id."""
    uf = _UF()
    uid_nat = {}
    fx_seen = collections.defaultdict(set)

    for r in records:
        uid = r.get('uid')
        if not uid:
            continue
        home = r.get('home_team') or r.get('home') or ''
        away = r.get('away_team') or r.get('away') or ''
        nat = natural_key(home, away, r.get('commence_time'))
        # Un même uid peut apparaître avec des commence_time différents : on
        # retient la plus petite clé, choix stable quel que soit l'ordre de
        # lecture. Toutes les variantes sont malgré tout unies entre elles.
        prev = uid_nat.get(uid)
        if prev is None or _label(nat) < _label(prev):
            uid_nat[uid] = nat
        uf.union(('nat', nat), ('uid', uid))
        fx = r.get('fixture_id')
        if fx:
            uf.union(('fx', fx), ('uid', uid))
            fx_seen[fx].add(uid)

    groups = collections.defaultdict(set)
    uid2canon = {}
    for uid in uid_nat:
        root = uf.find(('uid', uid))
        uid2canon[uid] = root
        groups[root].add(uid)

    # Un groupe peut réunir plusieurs clés naturelles (fusion par fixture_id).
    # On retient DÉTERMINISTIQUEMENT la plus petite, pour que le libellé du
    # match ne dépende ni de l'ordre de lecture ni du hachage.
    labels = {}
    for root, uids in groups.items():
        labels[root] = min(_label(uid_nat[u]) for u in uids)
    return Index(uid2canon, dict(groups), labels)
