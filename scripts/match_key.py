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
  1. clé naturelle = { joueurs normalisés } + JOURNÉE (pas l'heure -- corrigé
     le 27/08/2026, ce docstring n'avait pas suivi le changement documenté
     dans natural_key() : commence_time varie jusqu'à 4h selon la source,
     une clé à l'heure près faisait changer 27 uid d'identifiant)
     (insensible à l'ordre home/away, aux accents, à la casse, au tournoi)
  2. fusion par `fixture_id` via union-find : deux enregistrements partageant
     un fixture_id sont le même match, même si horaire ou noms diffèrent
  3. fusion de PROXIMITÉ, à tournoi identique : mêmes joueurs, même tournoi,
     horaires distants de moins de PROXI_H (36 h) -> même match.

POURQUOI L'ÉTAPE 3
L'horaire annoncé d'un match bouge entre les sources. Deux motifs constatés :
  • correction de quelques minutes de part et d'autre de MINUIT
    (2026-08-12 23:40 puis 2026-08-13 00:10 = 30 min d'écart, deux dates) ;
  • horaire PROVISOIRE 14:00 repris tel quel deux jours de suite, avant que
    l'heure réelle n'arrive.
53 paires apparaissaient ainsi sur des jours consécutifs, TOUTES dans le même
tournoi. Sans l'étape 3, ce sont autant de matchs comptés deux fois.
Au tennis, deux joueurs ne peuvent pas se rencontrer deux fois en moins de 36 h
dans le MÊME tournoi : la fusion est donc sûre.

GARDE-FOU : jamais de fusion entre TOURNOIS DIFFÉRENTS, et jamais si les deux
côtés portent des fixture_id connus et DISJOINTS (preuve de deux vraies
rencontres). Deux rencontres espacées de plus de 36 h restent distinctes —
vérifié : 69 paires se rencontrent à plusieurs dates, correctement séparées.

Usage :
    import match_key as mk
    idx = mk.build_index(records)        # records = dicts de courbes
    cle = idx.key_of(uid)                # -> identifiant canonique stable
"""
import re, unicodedata, collections


def _toks(s):
    # CORRIGÉ LE 27/08/2026, deux fois le même jour.
    # v1 (audit 1, §4.3.2) : seuil abaissé à 3 -> 2 lettres, pour que les
    # noms courts (Wu, Li, Xu, An) ne s'effondrent plus en ensemble vide.
    # v2 (découvert en écrivant le test de non-régression de l'audit v2
    # §G) : le commentaire ci-dessus disait qu'une initiale isolée
    # "n'identifie rien", mais c'est FAUX quand elle sert à DISTINGUER --
    # "A. Zverev" et "M. Zverev" réduisaient tous deux à {zverev}
    # STRICTEMENT IDENTIQUE, donc fusionnaient dès l'égalité de base
    # (avant même la moindre étape de proximité). Garder l'initiale ajoute
    # de l'info, ne peut jamais en retirer -- le risque en sens inverse
    # (deux tokens à 1 lettre qui matcheraient à tort) n'existe pas : un
    # ensemble AVEC initiale est un sur-ensemble strict de la version sans,
    # donc au pire aussi précis, jamais moins. Seuil : aucun (>=1).
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    toks = frozenset(t for t in re.split(r'[^a-z]+', s) if len(t) >= 1)
    if toks:
        return toks
    # Filet : même à 1 lettre, un nom pourrait ne rien produire (chiffres,
    # caractères hors a-z après normalisation). Mieux vaut une clé moins
    # discriminante que silencieusement vide.
    brut = re.sub(r'[^a-z]', '', s)
    return frozenset({brut}) if brut else frozenset()


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


PROXI_H = 36.0      # au-delà, deux rencontres des mêmes joueurs sont distinctes


def _ts(s):
    import datetime
    try:
        return datetime.datetime.fromisoformat(
            str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def _joueurs_compatibles(n1, n2):
    """n1, n2 : nat[0], un frozenset de 1 ou 2 frozensets de tokens (un par
    joueur). True si chaque joueur de n1 correspond -- par inclusion ou
    égalité, DANS UN SENS OU L'AUTRE -- à un joueur DISTINCT de n2.
    Appariement BIPARTITE explicite (pas une comparaison de la paire comme
    un bloc, qui échoue systématiquement -- voir le commentaire à l'appel)."""
    l1, l2 = list(n1), list(n2)
    if len(l1) != len(l2) or not l1:
        return False

    def couvre(a, b):
        return bool(a) and bool(b) and (a <= b or b <= a)

    if len(l1) == 1:
        return couvre(l1[0], l2[0])
    if len(l1) == 2:
        a1, a2 = l1
        b1, b2 = l2
        return ((couvre(a1, b1) and couvre(a2, b2)) or
                (couvre(a1, b2) and couvre(a2, b1)))
    return False   # cas dégénéré (>2 "joueurs"), on n'y touche pas


def build_index(records):
    """records : itérable de dicts ayant uid, home/home_team, away/away_team,
    commence_time et éventuellement fixture_id."""
    uf = _UF()
    uid_nat = {}
    nat_rows = []

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
        nat_rows.append((nat, (r.get('tournament') or '').strip().lower(),
                         _ts(r.get('commence_time')), uid, fx))

    # ── Étape 3 : fusion de proximité, à tournoi identique ────────────────
    # clé de regroupement volontairement STRICTE : mêmes joueurs ET même tournoi.
    prox = collections.defaultdict(list)
    for nat, tour, when, uid, fx in nat_rows:
        if when is None:
            continue
        prox[(nat[0], tour)].append((when, uid, fx))
    for key, items in prox.items():
        items.sort(key=lambda x: (x[0], str(x[1])))
        for i in range(len(items) - 1):
            (t1, u1, f1), (t2, u2, f2) = items[i], items[i + 1]
            if abs((t2 - t1).total_seconds()) / 3600.0 > PROXI_H:
                continue
            if f1 and f2 and f1 != f2:
                continue        # deux fixture_id connus et différents = 2 matchs
            uf.union(('uid', u1), ('uid', u2))

    # ── Étape 4 : RETIRÉE LE 27/08/2026 (audit v2 §G). Une version de fusion
    # par inclusion d'ensembles vivait ici (prénoms abrégés), corrigée le
    # jour même d'un bug de comparaison plate -- mais l'audit a montré que
    # ses garde-fous (tournoi + fenêtre 36h) n'empêchent PAS de fusionner
    # deux HOMONYMES réels : « A. Zverev » et « M. Zverev » (Alexander et
    # Mischa, deux joueurs distincts) contre le même adversaire, même
    # tournoi, même jour -> fusionnés à tort (vérifié : True). Et le
    # bénéfice mesuré sur clv_history.jsonl était NUL (1405 matchs
    # canoniques identiques avec ou sans cette étape, 0 fusion
    # supplémentaire). Risque réel, gain nul sur les données actuelles :
    # retirée plutôt que rapiécée une troisième fois sous pression -- le
    # même empressement qui l'a produite la première fois.
    # Piste pour une VRAIE réintroduction, si le besoin se confirme un jour :
    # exiger que le token en plus (le prénom) ne soit pas déjà un nom de
    # famille présent ailleurs dans l'index (distinguerait Zverev de
    # Griekspoor), ou refuser l'inclusion quand le côté court n'a qu'un
    # seul token. Non implémenté ce soir -- demande un index de fréquence
    # des noms qui n'existe pas encore, pas une correction de trois lignes.

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
