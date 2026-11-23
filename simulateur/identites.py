#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
identites.py — un joueur écrit de deux façons = un seul classement (23/11/2026, paquet 369).

Constat (Lucas, 23/11) : « Gianluca Cadenasso – Melios Efstathiou » et « Gianluca Cadenasso – Menelaos Efstathiou »
affichés deux fois, avec deux % différents. C'est le MÊME joueur (Chypre, né le 02/03/1999, 183 cm) : Melios est le
diminutif de Menelaos, et l'archive Sackmann lui donne même deux identifiants (144949 jusqu'en 2024, 213713 depuis
2025). Il avait donc deux classements : 15 matchs sous un nom, 127 sous l'autre. E.unifier ne pouvait pas les relier
(un seul mot en commun).

Ceci est une correction de DONNÉES (le principe « un joueur = un classement » est en service depuis le 22/10), pas un
changement de modèle : aucun réglage, aucune mesure de réussite n'intervient.

Règle, écrite avant de regarder la liste produite :
  deux noms (deux clés E.cle différentes) sont le même joueur si
    1. même nom de famille (dernier mot), même pays (le plus fréquent) ;
    2. dates de naissance à 45 jours au plus (Sackmann donne l'âge au dixième d'année ; TennisApi la date) ;
    3. prénoms compatibles : même prénom une fois les espaces retirés (« Seong Chan » / « Seongchan »), ou initiale
       du prénom long (« R. » / « Ricardo »), ou orthographes proches (SequenceMatcher ≥ 0,75 : « Aleksandr » /
       « Alexander », « Khumoun » / « Khumoyun ») — OU paire de la liste MANUELS (diminutifs vérifiés à la main) ;
    4. tailles compatibles (5 cm au plus) quand les deux sont connues ;
    5. jamais deux noms vus dans le MÊME tournoi de l'archive (les jumeaux Pliskova, Kichenok, Sabanov… sont deux
       joueuses ou joueurs) ;
    6. un SEUL candidat possible de chaque côté — sinon on ne relie pas.
Le nom qui a le plus de matchs garde la clé ; l'autre devient un alias.
"""
import collections
import csv
import datetime as dt
import difflib
import json
import os
import statistics
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402

ECART_NAISSANCE_J = 45
ECART_TAILLE_CM = 5
PROCHE = 0.75

# Diminutifs ou transcriptions qu'aucune règle d'orthographe ne relie ; la règle 1-2-4-5 reste exigée.
MANUELS = [
    ('Melios Efstathiou', 'Menelaos Efstathiou'),       # CYP, né le 02/03/1999 — signalé par Lucas le 23/11/2026
    ('Caty Mcnally', 'Catherine McNally'),
    ('J J Wolf', 'Jeffrey John Wolf'),
    ('Nikita Mashtakov', 'Mykyta Mashtakov'),
]


def _prenoms(nom):
    t = E.mots(nom)
    return t[:-1]


def prenoms_compatibles(a, b):
    pa, pb = _prenoms(a), _prenoms(b)
    if not pa or not pb:
        return False
    ja, jb = ''.join(pa), ''.join(pb)
    if ja == jb:
        return True
    if (len(pa[0]) == 1 or len(pb[0]) == 1) and pa[0][0] == pb[0][0]:
        return True
    if pa[0][0] != pb[0][0] and not (set(pa) & set(pb)):
        return False
    return difflib.SequenceMatcher(None, ja, jb).ratio() >= PROCHE


class Fiches:
    """Par clé E.cle : nom, pays, naissances estimées (jour ordinal), tailles, nombre de matchs, tournois vus."""

    def __init__(self):
        self.f = {}

    def voir(self, nom, pays=None, naissance=None, taille=None, tournoi=None):
        k = E.cle(nom)
        if not k:
            return
        x = self.f.setdefault(k, {'nom': nom, 'pays': collections.Counter(), 'naiss': [], 'taille': [], 'n': 0,
                                  'tournois': set()})
        x['n'] += 1
        if pays:
            x['pays'][pays] += 1
        if naissance:
            x['naiss'].append(naissance)
        if taille:
            x['taille'].append(float(taille))
        if tournoi:
            x['tournois'].add(tournoi)


def fiches_sackmann(F, dossier, annee_min=2016):
    import donnees
    for chemin, _c in donnees.fichiers(dossier, annee_min):
        with open(chemin, encoding='utf-8', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh):
                try:
                    j = dt.datetime.strptime(r.get('tourney_date') or '', '%Y%m%d').date().toordinal()
                except ValueError:
                    continue
                for s in ('winner', 'loser'):
                    n = r.get(s + '_name')
                    if not n:
                        continue
                    try:
                        nb = j - float(r.get(s + '_age')) * 365.25
                    except (TypeError, ValueError):
                        nb = None
                    try:
                        ht = float(r.get(s + '_ht'))
                    except (TypeError, ValueError):
                        ht = None
                    F.voir(n, r.get(s + '_ioc'), nb, ht, tournoi=r.get('tourney_id'))


def fiches_feuilles(F, racine):
    """Noms des feuilles TennisApi, avec la fiche joueur (feuilles/joueurs.json : naissance, pays, taille)."""
    import feuilles as FE
    try:
        with open(os.path.join(racine, 'feuilles', 'joueurs.json'), encoding='utf-8') as f:
            J = json.load(f)
    except (OSError, ValueError):
        J = {}
    for r in FE.lire(racine):
        for c in ('home', 'away'):
            p = r.get(c) or {}
            if not p.get('nom'):
                continue
            fi = J.get(str(p.get('id'))) or {}
            try:
                nb = dt.date.fromisoformat(fi['naissance']).toordinal() if fi.get('naissance') else None
            except ValueError:
                nb = None
            F.voir(p['nom'], fi.get('pays') or p.get('pays'), nb, fi.get('taille_cm'))


def _resume(x):
    return {'nom': x['nom'], 'n': x['n'], 'pays': x['pays'].most_common(1)[0][0] if x['pays'] else None,
            'naissance': statistics.median(x['naiss']) if x['naiss'] else None,
            'taille': statistics.median(x['taille']) if x['taille'] else None}


def meme_joueur(a, b, manuel=False):
    """a, b : fiches brutes. Règles 1, 2, 4, 5 toujours ; règle 3 sauf paire manuelle."""
    ra, rb = _resume(a), _resume(b)
    ta, tb = E.mots(a['nom']), E.mots(b['nom'])
    if not ta or not tb or ta[-1] != tb[-1]:
        return False
    if not ra['pays'] or ra['pays'] != rb['pays']:
        return False
    if ra['naissance'] is None or rb['naissance'] is None or abs(ra['naissance'] - rb['naissance']) > ECART_NAISSANCE_J:
        return False
    if ra['taille'] is not None and rb['taille'] is not None and abs(ra['taille'] - rb['taille']) > ECART_TAILLE_CM:
        return False
    if a['tournois'] & b['tournois']:
        return False
    return manuel or prenoms_compatibles(a['nom'], b['nom'])


def liens(F):
    """{clé de l'alias: clé gardée} et le détail, selon la règle de l'en-tête."""
    fi = F.f
    manuels = {frozenset((E.cle(x), E.cle(y))) for x, y in MANUELS}
    groupes = collections.defaultdict(list)
    for k, x in fi.items():
        t = E.mots(x['nom'])
        if t:
            groupes[t[-1]].append(k)
    cand = collections.defaultdict(set)
    for ks in groupes.values():
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                a, b = ks[i], ks[j]
                if meme_joueur(fi[a], fi[b], manuel=frozenset((a, b)) in manuels):
                    cand[a].add(b)
                    cand[b].add(a)
    alias, detail = {}, []
    for a in sorted(cand):
        if len(cand[a]) != 1:
            continue
        b = next(iter(cand[a]))
        if len(cand[b]) != 1 or a > b:
            continue
        garde, autre = (a, b) if (fi[a]['n'], a) >= (fi[b]['n'], b) else (b, a)
        alias[autre] = garde
        detail.append({'alias': fi[autre]['nom'], 'garde': fi[garde]['nom'],
                       'matchs': [fi[autre]['n'], fi[garde]['n']]})
    return alias, detail


def resoudre(alias):
    """Suit les chaînes (a → b → c devient a → c) ; une boucle est coupée."""
    out = {}
    for k in alias:
        v, vus = alias[k], {k}
        while v in alias and v not in vus:
            vus.add(v)
            v = alias[v]
        if v != k:
            out[k] = v
    return out


CHEMIN_OBSERVES = os.path.join('simulateur', 'alias_observes.json')


def charger_observes(racine):
    try:
        with open(os.path.join(racine, CHEMIN_OBSERVES), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def noter_observes(racine, rejets, quand):
    """23/11/2026 (paquet 371) — un même match listé deux fois (même tournoi, même heure, même adversaire) avec deux
    écritures d'un joueur : les deux noms sont le même joueur (un joueur ne joue pas deux simples à la même heure).
    « Aaron Funk – Tugra Duran » et « Aaron Funk – Cemil Tugra Duran » (Ankara, 22/11). Le nom le moins documenté
    pointe vers l'autre ; le lien sert au classement suivant (appliquer). Renvoie le nombre de liens nouveaux."""
    d = charger_observes(racine)
    nouveaux, change = 0, False
    for r in rejets or ():
        if r.get('raison') != 'doublon_meme_match' or r.get('meme_classement') or not r.get('garde'):
            continue
        ec, ga = [r['home'], r['away']], list(r['garde'])
        communs = {E.cle(n) for n in ec} & {E.cle(n) for n in ga}
        a = [n for n in ec if E.cle(n) not in communs]
        b = [n for n in ga if E.cle(n) not in communs]
        if len(a) != 1 or len(b) != 1 or E.cle(a[0]) == E.cle(b[0]):
            continue
        k = E.cle(a[0])
        x = d.get(k)
        if x is None:
            d[k] = {'nom': a[0], 'vers': b[0], 'tournoi': r.get('tournoi'), 'premier': quand, 'dernier': quand, 'vu': 1}
            nouveaux += 1
            change = True
        elif E.cle(x.get('vers')) == E.cle(b[0]):
            x['dernier'], x['vu'] = quand, int(x.get('vu') or 0) + 1
            change = True
        elif not x.get('conflit'):
            x['conflit'] = True          # deux cibles différentes : le lien n'est plus appliqué
            change = True
    if not change:
        return 0
    os.makedirs(os.path.join(racine, 'simulateur'), exist_ok=True)
    with open(os.path.join(racine, CHEMIN_OBSERVES), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    return nouveaux


def liens_identifiant(racine):
    """23/11/2026 (paquet 396) — MÊME IDENTIFIANT TennisApi = même joueur. « Zach Viiala » (27 matchs ITF) et
    « Zachary Viiala » (le nom du Challenger de Champaign) ont le même identifiant TennisApi (387395) mais avaient deux
    classements : il a été annoncé battu à 99 % le 16/11 avec un seul match documenté. Les feuilles de match et les
    résultats ITF (hommes et femmes) donnent l'identifiant TennisApi de chaque joueur ; deux écritures sous le même
    identifiant sont reliées, le nom le plus vu garde la clé. Correction de données : aucun réglage.
    Renvoie ({clé alias: clé gardée}, détail)."""
    import glob
    import gzip
    vus = collections.defaultdict(collections.Counter)
    fichiers = (glob.glob(os.path.join(racine, 'feuilles', '*.jsonl.gz'))
                + glob.glob(os.path.join(racine, 'resultats_itf', '*.jsonl.gz'))
                + glob.glob(os.path.join(racine, 'resultats_itf_femmes', '*.jsonl.gz')))
    for f in fichiers:
        try:
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                for l in fh:
                    try:
                        r = json.loads(l)
                    except ValueError:
                        continue
                    for c in ('home', 'away'):
                        j = r.get(c)
                        if isinstance(j, dict) and j.get('id') and j.get('nom'):
                            vus[j['id']][j['nom']] += 1
        except (OSError, EOFError):
            continue
    lid, detail = {}, []
    for i, noms in vus.items():
        cles = collections.Counter()
        for n, v in noms.items():
            cles[E.cle(n)] += v
        if len(cles) < 2:
            continue
        garde = max(cles, key=lambda k: (cles[k], k))
        nom_garde = max((n for n in noms if E.cle(n) == garde), key=lambda n: noms[n])
        for k in cles:
            if k != garde:
                lid[k] = garde
                detail.append({'alias': max((n for n in noms if E.cle(n) == k), key=lambda n: noms[n]), 'garde': nom_garde,
                               'source': 'meme_identifiant_tennisapi', 'matchs': [cles[k], cles[garde]]})
    return lid, detail


def contredit(F, k1, k2):
    """Vrai si les fiches disent deux joueurs différents (pays, naissance ou taille incompatibles)."""
    a, b = F.f.get(k1), F.f.get(k2)
    if not a or not b:
        return False
    ra, rb = _resume(a), _resume(b)
    if ra['pays'] and rb['pays'] and ra['pays'] != rb['pays']:
        return True
    if ra['naissance'] is not None and rb['naissance'] is not None and \
            abs(ra['naissance'] - rb['naissance']) > ECART_NAISSANCE_J:
        return True
    return ra['taille'] is not None and rb['taille'] is not None and abs(ra['taille'] - rb['taille']) > ECART_TAILLE_CM


def appliquer(alias, dossier, racine):
    """Ajoute à `alias` (E.unifier, lier_itf) les liens d'identité ; renvoie (alias résolu, détail)."""
    F = Fiches()
    try:
        fiches_sackmann(F, dossier)
        fiches_feuilles(F, racine)
    except Exception as e_:  # noqa: BLE001 — sans fiches, les alias existants restent tels quels
        print(f"::warning::identités non vérifiées : {type(e_).__name__}")
        return dict(alias), []
    lid, detail = liens(F)
    # liens vus en direct (même match listé deux fois), sauf si les fiches les contredisent
    for k, x in charger_observes(racine).items():
        if x.get('conflit') or k in lid:
            continue
        v = E.cle(x.get('vers'))
        v = alias.get(v, lid.get(v, v))
        if v and v != k and not contredit(F, k, v):
            lid[k] = v
            detail.append({'alias': x.get('nom'), 'garde': x.get('vers'), 'source': 'vu_en_direct'})
    # 396 : même identifiant TennisApi (feuilles et résultats ITF) : preuve directe, appliquée en dernier
    try:
        lii, det_i = liens_identifiant(racine)
    except Exception as e_:  # noqa: BLE001
        print(f"::warning::liens par identifiant non calculés : {type(e_).__name__}")
        lii, det_i = {}, []
    for k, v in lii.items():
        if k not in lid:
            lid[k] = lid.get(v, v)
            detail.append(next(d for d in det_i if E.cle(d['alias']) == k))
    tout = dict(alias)
    for k, v in lid.items():
        tout.setdefault(k, v)
        # un nom déjà relié à l'alias suit le joueur gardé
    for k, v in list(tout.items()):
        if v in lid:
            tout[k] = lid[v]
    return resoudre(tout), detail
