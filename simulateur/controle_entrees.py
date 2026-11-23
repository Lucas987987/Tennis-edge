#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controle_entrees.py — matchs écartés et identités des joueurs, contrôlés à chaque pronostic (23/11/2026, paquet 371).

Deux questions de Lucas (23/11) :
  1. combien de matchs à venir n'ont PAS de pronostic, et pourquoi (identité ambiguë, surface inconnue, doublon) ?
  2. les joueurs réunis par simulateur/identites.py (paquet 369) ont-ils bien UN seul classement ?

Lecture seule de Tennis_Edge_Lab/live/pronostics.json, simulateur/elo_etat.json et simulateur/alias_observes.json.
Sortie : simulateur/rapport_entrees.json (noms de joueurs et de tournois, aucun chiffre de cote), avec l'historique
des 60 derniers jours. Rien ici ne change un pronostic.

Statut « alerte » si un joueur réuni a encore deux classements, ou si un doublon a été écarté alors que les deux
noms gardaient deux classements différents (le lien est alors appris en direct, voir identites.noter_observes).
"""
import collections
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402

SORTIE = os.path.join('simulateur', 'rapport_entrees.json')
JOURS_HISTORIQUE = 60


def _lire(racine, chemin, defaut=None):
    try:
        with open(os.path.join(racine, chemin), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def fusions(etat):
    """Chaque lien d'identité : l'alias ne doit plus avoir de classement à lui, la cible doit en avoir un."""
    joueurs, alias = etat.get('joueurs') or {}, etat.get('alias') or {}
    deux, sans_cible = [], []
    for x in etat.get('identites') or []:
        ka, kg = E.cle(x.get('alias')), E.cle(x.get('garde'))
        cible = alias.get(ka, ka)
        if ka in joueurs and ka != cible:
            deux.append({'alias': x.get('alias'), 'garde': x.get('garde')})
        elif alias.get(kg, kg) not in joueurs:
            sans_cible.append({'alias': x.get('alias'), 'garde': x.get('garde')})
    return {'n': len(etat.get('identites') or []), 'deux_classements': deux, 'cible_sans_classement': sans_cible}


def sans_historique(doc, etat):
    """Joueurs pronostiqués sans aucun match au classement ; « suspect » si un joueur connu porte le même nom de
    famille (écriture différente possible, à vérifier)."""
    par_nom = collections.defaultdict(list)
    for k, v in (etat.get('joueurs') or {}).items():
        t = E.mots(v.get('nom') or '')
        if t and (v.get('matchs') or 0) > 0:
            par_nom[t[-1]].append(v.get('nom'))
    out = []
    for m in doc.get('matchs') or []:
        mj = m.get('matchs_joues') or [None, None]
        for i, n in enumerate((m.get('home'), m.get('away'))):
            if i < len(mj) and mj[i] == 0:
                t = E.mots(n or '')
                proches = sorted(par_nom.get(t[-1], [])) if t else []
                out.append({'nom': n, 'tournoi': m.get('tournoi'), 'meme_nom_de_famille': proches[:5]})
    return out


def controler(racine):
    doc = _lire(racine, os.path.join('Tennis_Edge_Lab', 'live', 'pronostics.json'), {}) or {}
    etat = _lire(racine, os.path.join('simulateur', 'elo_etat.json'), {}) or {}
    obs = _lire(racine, os.path.join('simulateur', 'alias_observes.json'), {}) or {}
    rejets = doc.get('rejets_entrees') or []
    par_raison = collections.Counter(r.get('raison') for r in rejets)
    doublons = [r for r in rejets if r.get('raison') == 'doublon_meme_match']
    F = fusions(etat)
    SH = sans_historique(doc, etat)
    jour = (doc.get('genere_le') or dt.datetime.utcnow().isoformat())[:10]
    alerte = bool(F['deux_classements']) or any(not r.get('meme_classement', True) for r in doublons)
    rap = {
        'genere_le': dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'pronostics_du': doc.get('genere_le'),
        'statut': 'alerte' if alerte else 'ok',
        'matchs_pronostiques': len(doc.get('matchs') or []),
        'rejets_par_raison': dict(par_raison),
        'rejets': [{k: r.get(k) for k in ('home', 'away', 'tournoi', 'raison', 'noms_ambigus', 'garde',
                                          'meme_classement') if r.get(k) is not None} for r in rejets],
        'surfaces_inconnues': sorted({r.get('tournoi') or '' for r in rejets if r.get('raison') == 'surface_inconnue'}),
        'fusions': F,
        'alias_observes': {'n': len(obs), 'conflits': sorted(x.get('nom') for x in obs.values() if x.get('conflit'))},
        'sans_historique': {'n': len(SH), 'suspects': [x for x in SH if x['meme_nom_de_famille']], 'liste': SH},
        'regle': "lecture seule ; alerte si un joueur réuni garde deux classements ou si un doublon écarté avait deux "
                 "classements différents (lien alors appris en direct)",
    }
    ancien = _lire(racine, SORTIE, {}) or {}
    H = [h for h in (ancien.get('historique') or []) if h.get('jour') != jour]
    H.append({'jour': jour, 'matchs': rap['matchs_pronostiques'], 'rejets': dict(par_raison),
              'sans_historique': len(SH), 'deux_classements': len(F['deux_classements'])})
    H = sorted(H, key=lambda h: h['jour'])[-JOURS_HISTORIQUE:]
    rap['historique'] = H
    return rap


def main(argv):
    racine = next((a for a in argv[1:] if not a.startswith('--')), os.path.join(ICI, '..'))
    rap = controler(racine)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print(f"Entrées : {rap['matchs_pronostiques']} matchs pronostiqués · écartés {sum(rap['rejets_par_raison'].values())} "
          f"{rap['rejets_par_raison']} · sans historique {rap['sans_historique']['n']} "
          f"(dont {len(rap['sans_historique']['suspects'])} à vérifier) · fusions {rap['fusions']['n']}, "
          f"encore doubles {len(rap['fusions']['deux_classements'])} · statut {rap['statut']}")
    if rap['statut'] == 'alerte':
        print("::warning::contrôle des entrées : voir simulateur/rapport_entrees.json")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
