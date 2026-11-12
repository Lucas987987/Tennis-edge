#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stabilite.py — une règle d'adoption qui ne bascule pas au hasard (23/10/2026, décidé AVANT les prochains
verdicts, pour toutes les règles du modèle).

Constat : chaque lundi, une dizaine de règles sont rejugées sur des fenêtres qui se chevauchent. Le 23/10, les
arbres ont été adoptés pour 0,0001 de log loss ; le face-à-face était déjà entré puis sorti d'une fenêtre à
l'autre. À ce rythme, des réglages entrent et sortent par simple hasard.

La règle, identique partout :
  — ENTRER : faire mieux que l'actuel d'au moins MARGE (0,001 de log loss du vainqueur), DEUX semaines de suite ;
  — SORTIR : faire moins bien que l'alternative d'au moins MARGE, deux semaines de suite ;
  — entre les deux, rien ne change (hystérésis) : un réglage en place le reste, un réglage absent le reste.
Une règle sans mesure en log loss (groupes de facteurs : vraisemblance des points) n'a que la confirmation
sur deux semaines. Plusieurs passages dans la même semaine (lancement à la main) comptent pour un : le
dernier verdict de la semaine remplace le précédent.

Point de départ : ce qui est en place aujourd'hui (le choix précédent) — rien ne bouge à l'installation.
État : simulateur/stabilite.json {règle: {adopte, semaine, serie_avant, serie, gain}}.
"""
import datetime as dt
import json
import os

ICI = os.path.dirname(os.path.abspath(__file__))
FICHIER = os.path.join(ICI, 'stabilite.json')
MARGE = 0.001
SEMAINES = 2
# 12/11/2026 (audit, paquet 241, etude_regles_fenetres.py) — RÈGLE CUMULÉE pour les règles jugées sur 42 jours glissants
# qui fournissent le détail par match (« paires » : jour, log loss sans, log loss avec). Deux semaines de fenêtres qui
# se chevauchent à 5/6 ne sont pas deux confirmations. Rejouée sur 2023 → juin 2026, la règle en place passait 12,7 %
# des semaines dans le mauvais état, la règle cumulée 9,4 %. Avec des paires : chaque match n'est compté qu'UNE fois
# (le jour où il entre dans la fenêtre) ; ENTRER si, depuis le dernier changement, sur au moins CUMUL_MIN matchs, le
# gain est positif de plus de CUMUL_ET erreurs types ; SORTIR s'il est négatif de plus de CUMUL_ET erreurs types ;
# compteurs remis à zéro à chaque changement. Sans paires : la règle d'avant, inchangée.
CUMUL_MIN, CUMUL_ET = 300, 2.0


def semaine_iso(d=None):
    d = d or dt.datetime.now(dt.timezone.utc).date()
    a, s, _ = d.isocalendar()
    return f"{a}-W{s:02d}"


def lire(chemin=FICHIER):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ecrire(etat, chemin=FICHIER):
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)


def sans_paires(x):
    """Copie sans aucune clé « paires » (le détail par match ne s'enregistre jamais)."""
    if isinstance(x, dict):
        return {k: sans_paires(v) for k, v in x.items() if k != 'paires'}
    if isinstance(x, list):
        return [sans_paires(v) for v in x]
    return x


def decider_cumule(etat, cle, en_place, paires):
    """Règle cumulée (paquet 241). paires : [(jour ISO, log loss sans, log loss avec)] des matchs jugés cette semaine
    (une fenêtre glissante : seuls les jours après le dernier vu sont ajoutés). Renvoie (adopté, note)."""
    import math
    e = etat.get(cle)
    if e is None:
        e = {'adopte': bool(en_place)}
    c = e.get('cumul') or {'vu': None, 'n': 0, 's': 0.0, 's2': 0.0}
    vu = c.get('vu')
    nouveaux = [(j, l0, l1) for j, l0, l1 in paires or () if vu is None or str(j) > vu]
    for j, l0, l1 in nouveaux:
        d = float(l0) - float(l1)
        c['n'] += 1
        c['s'] += d
        c['s2'] += d * d
    if nouveaux:
        c['vu'] = max(str(j) for j, _, _ in nouveaux)
    n = c['n']
    m = c['s'] / n if n else 0.0
    se = math.sqrt(max(c['s2'] / n - m * m, 0.0) / n) if n else 0.0
    if n >= CUMUL_MIN and e['adopte'] and m + CUMUL_ET * se < 0:
        e['adopte'], note = False, f"sorti : gain {m:+.4f} ± {se:.4f} sur {n} matchs, négatif de plus de {CUMUL_ET:g} erreurs types"
        c.update(n=0, s=0.0, s2=0.0)
    elif n >= CUMUL_MIN and not e['adopte'] and m - CUMUL_ET * se > 0:
        e['adopte'], note = True, f"adopté : gain {m:+.4f} ± {se:.4f} sur {n} matchs, positif de plus de {CUMUL_ET:g} erreurs types"
        c.update(n=0, s=0.0, s2=0.0)
    else:
        note = (f"{'en place' if e['adopte'] else 'pas adopté'} (cumul : {n} matchs"
                + (f", gain {m:+.4f} ± {se:.4f}" if n else '') + f" ; il en faut {CUMUL_MIN} et {CUMUL_ET:g} erreurs types)")
    e['cumul'] = c
    e['regle'] = 'cumulee'
    e['gain'] = round(m, 5) if n else None
    etat[cle] = e
    return e['adopte'], note


def decider(etat, cle, en_place, brut, ll_nouveau=None, ll_actuel=None, semaine=None, paires=None):
    """Décision stabilisée de la règle `cle`.
    en_place : adopté aujourd'hui (choix précédent) — point de départ si la règle est inconnue ;
    brut     : verdict de la règle seule cette semaine ;
    ll_nouveau / ll_actuel : log loss du vainqueur avec et sans le réglage (facultatifs ; sans eux, pas de marge).
    Renvoie (adopté, note lisible)."""
    if paires is not None:                                 # 12/11/2026 (paquet 241) : règle cumulée
        return decider_cumule(etat, cle, en_place, paires)
    semaine = semaine or semaine_iso()
    e = etat.get(cle)
    if e is None:
        e = {'adopte': bool(en_place), 'semaine': None, 'serie_avant': 0, 'serie': 0}
    if e.get('semaine') != semaine:                        # nouvelle semaine : la série acquise devient la base
        e['serie_avant'] = e.get('serie', 0)
        e['semaine'] = semaine
    gain = (ll_actuel - ll_nouveau) if (ll_nouveau is not None and ll_actuel is not None) else None
    if e['adopte']:
        echoue = (not brut) and (gain is None or gain <= -MARGE)
        e['serie'] = e['serie_avant'] + 1 if echoue else 0
        if e['serie'] >= SEMAINES:
            e['adopte'], e['serie'], e['serie_avant'] = False, 0, 0
            note = f"sorti : moins bien {SEMAINES} semaines de suite"
        else:
            note = (f"en place ; à confirmer pour sortir ({e['serie']}/{SEMAINES})" if echoue else "en place")
    else:
        candidat = bool(brut) and (gain is None or gain >= MARGE)
        e['serie'] = e['serie_avant'] + 1 if candidat else 0
        if e['serie'] >= SEMAINES:
            e['adopte'], e['serie'], e['serie_avant'] = True, 0, 0
            note = f"adopté : mieux {SEMAINES} semaines de suite"
        elif candidat:
            note = f"candidat ({e['serie']}/{SEMAINES}) : adopté s'il fait encore mieux la semaine prochaine"
        elif brut and gain is not None:
            note = f"écart trop faible ({gain:+.4f} < {MARGE}) : pas adopté"
        else:
            note = "pas adopté"
    e['gain'] = round(gain, 5) if gain is not None else None
    etat[cle] = e
    return e['adopte'], note


def appliquer(etat, cle, ancien, nouveau, params=(), semaine=None):
    """Entrée de choix_simulation.json stabilisée. ancien : l'entrée en place (ou None) ; nouveau : le verdict de
    la semaine ({'adopte', 'raison', 'll': {'avec', 'sans'}, réglages…}) ; params : les clés qui portent le
    réglage. Gardé en place par l'hystérésis alors que la semaine dit non : on garde les ANCIENS réglages."""
    nouveau = dict(nouveau or {})
    paires = nouveau.pop('paires', None)                   # 12/11/2026 : détail par match, jamais enregistré
    ancien = ancien or {}
    ll = nouveau.get('ll') or {}
    ok, note = decider(etat, cle, bool(ancien.get('adopte')), bool(nouveau.get('adopte')), ll.get('avec'), ll.get('sans'), semaine,
                       paires=paires)
    out = dict(nouveau, adopte_brut=bool(nouveau.get('adopte')), adopte=ok, stabilite=note)
    if ok and not nouveau.get('adopte'):
        for k in params:
            if ancien.get(k) is not None:
                out[k] = ancien[k]
    out['raison'] = f"{nouveau.get('raison') or ''} — {note}".strip(' —')
    return out
