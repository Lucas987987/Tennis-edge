#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controle_fuites.py — aucun pronostic d'un match À VENIR dans ce qui part au dépôt public (24/11/2026, paquet 416,
Lucas : « vérifier qu'aucun pronostic à venir ne reste visible »).

Audit du 24/11 (copie publique de main, 58 matchs à venir) : trois fuites trouvées.
  • simulateur/journal_pronostics/*_v1.jsonl (lignes et statistiques prévues) : en clair → filtrés depuis le paquet 414 ;
  • matchs RETARDÉS : le journal, les passages et les fiches étaient filtrés sur le début PLANIFIÉ, déjà passé, alors
    que le match n'avait pas commencé (jusqu'à 4 h plus tard) → filtrés sur le début annoncé par le site (paquet 416) ;
  • Tennis_Edge_Lab/live/pronostics_marche.json (probabilité tirée des cotes, matchs à venir) commité par « Courbes
    live + alertes » → sorti du dépôt, envoyé seulement au site privé du Lab sur R2 (paquet 416).

Règle du contrôle : un objet JSON qui désigne un match à venir (clé « uid » ou clé de dictionnaire = uid d'un match
dont le début annoncé n'est pas passé, hors match du jour offert) ET qui porte un champ de pronostic est une fuite.
Les matchs à venir viennent de la copie publique d'algo/donnees.json (qui garde l'affiche de chaque match).
Sortie : les NOMS des fichiers en cause seulement, jamais leur contenu (journaux Actions publics).

Usage : python scripts/controle_fuites.py [racine] [fichier …]   (sans fichier : ceux prêts à être commités)
Code retour : 0 aucun souci, 1 au moins une fuite (les fichiers en cause sont listés, un par ligne).
"""
import datetime as dt
import gzip
import json
import os
import subprocess
import sys

CHAMPS = frozenset(('p_home', 'p_affiche', 'p_simulation', 'p_elo', 'combinaison', 'simulation', 'stats', 'sets',
                    'lignes', 'lignes_algo', 'feuille_prevue', 'feuille_plus', 'scenarios', 'cotes_justes', 'detail',
                    'premier', 'dernier', 'pin',
                    # journaux figés des styles (styles_global_v1…) : % du champion, du contrôle, du challenger
                    'champion', 'controle', 'challenger', 'styles_global', 'variables', 'pronostic_fige'))
EXTENSIONS = ('.json', '.jsonl', '.json.gz', '.jsonl.gz')


def matchs_a_venir(racine, maintenant=None):
    """{uid} des matchs dont le début annoncé (copie publique du site) n'est pas passé, hors match du jour offert."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M')
    try:
        with open(os.path.join(racine, 'algo', 'donnees.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return set()
    offert = (doc.get('match_du_jour') or {}).get('uid')
    out = set()
    for m in doc.get('matchs') or []:
        d = str(m.get('debut_utc') or m.get('debut') or '')[:16]
        if m.get('uid') and m['uid'] != offert and d > maintenant:
            out.add(m['uid'])
    return out


def _fuit(x, futurs, prof=0):
    if prof > 40:
        return False
    if isinstance(x, dict):
        if x.get('uid') in futurs and CHAMPS & set(x):
            return True
        for k, v in x.items():
            if k in futurs and isinstance(v, dict) and (CHAMPS & set(v) or any(isinstance(w, (int, float)) for w in v.values())):
                return True
            if isinstance(v, (dict, list)) and _fuit(v, futurs, prof + 1):
                return True
        return False
    if isinstance(x, list):
        return any(_fuit(v, futurs, prof + 1) for v in x)
    return False


def lire(chemin):
    with open(chemin, 'rb') as f:
        data = f.read()
    if chemin.endswith('.gz'):
        data = gzip.decompress(data)
    return data.decode('utf-8', 'replace')


def fuite_dans(chemin, futurs, offert=None):
    """True si le fichier porte le pronostic d'un match à venir."""
    if not futurs or not chemin.endswith(EXTENSIONS):
        return False
    try:
        texte = lire(chemin)
    except (OSError, EOFError, ValueError):
        return False
    if not any(u in texte for u in futurs):                     # tri rapide : aucun uid à venir cité
        return False
    if '.jsonl' in chemin:
        for l in texte.splitlines():
            if not l.strip() or not any(u in l for u in futurs):
                continue
            try:
                if _fuit(json.loads(l), futurs):
                    return True
            except ValueError:
                continue
        return False
    try:
        return _fuit(json.loads(texte), futurs)
    except ValueError:
        return False


def fichiers_prets(racine):
    r = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=AM'], capture_output=True, text=True, cwd=racine)
    return [x for x in r.stdout.split() if x]


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    fichiers = argv[2:] or fichiers_prets(racine)
    futurs = matchs_a_venir(racine)
    en_cause = [f for f in fichiers if fuite_dans(os.path.join(racine, f), futurs)]
    for f in en_cause:
        print(f)
    print(f"Contrôle des fuites : {len(fichiers)} fichier(s) vérifié(s), {len(futurs)} match(s) à venir, "
          f"{len(en_cause)} fichier(s) en cause.", file=sys.stderr)
    return 1 if en_cause else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
