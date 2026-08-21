#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_json_state.py — Résout les conflits git sur les fichiers JSON d'état.

LE PROBLÈME
capture_closing tourne toutes les 5 à 10 minutes. Quand deux exécutions se
chevauchent — ou qu'un autre workflow pousse entre le checkout et le push —
git tombe en conflit sur les fichiers JSON réécrits en entier :
    CONFLICT (content): Merge conflict in closing_lines.json
    CONFLICT (content): Merge conflict in capture_state.json
    CONFLICT (content): Merge conflict in matches_oddspapi.json
Le merge échoue, le push est rejeté, et TOUT le run est perdu — y compris les
partitions live qui, elles, s'étaient fusionnées sans problème grâce au pilote
« union » du .gitattributes.

POURQUOI « union » NE PEUT PAS SERVIR ICI
Ces fichiers ne sont pas des journaux append-only : ce sont des documents JSON.
Concaténer deux versions produirait du JSON invalide. Le pilote union est le bon
choix pour parts/*.jsonl, il est destructeur pour un objet JSON.

POURQUOI « -X ours » NON PLUS
closing_lines.json est un ACCUMULATEUR : les entrées s'ajoutent au fil des
captures et se complètent (fixture_id, niveau, sport_key ajoutés après coup).
Prendre systématiquement notre version effacerait les matchs ajoutés par
l'exécution concurrente — un match terminé entre les deux serait perdu
définitivement, car les runs suivants ne le réintroduiraient pas.

CE QUE FAIT CE SCRIPT
Il récupère les DEUX versions depuis l'index git (:2 = la nôtre, :3 = la leur)
et fusionne les dictionnaires clé par clé :
  • clé présente d'un seul côté  -> conservée ;
  • clé des deux côtés, valeurs = dicts -> fusion récursive ;
  • sinon -> la NÔTRE l'emporte, car elle vient de la capture la plus récente.
Aucune donnée n'est perdue, et le résultat reste du JSON valide.

Un fichier qu'il ne sait pas fusionner (listes, types incompatibles) est laissé
en conflit et signalé : mieux vaut un run rouge qu'une résolution silencieuse
et fausse.

Usage : appelé après un `git merge` en conflit, avant de retenter le commit.
Sortie : 0 si tous les conflits JSON sont résolus, 1 sinon.
"""
import json
import subprocess
import sys


def git(*args):
    return subprocess.run(['git'] + list(args), capture_output=True, text=True)


def version(etape, chemin):
    """Contenu d'un côté du conflit. :1 = ancêtre, :2 = nous, :3 = eux."""
    r = subprocess.run(['git', 'show', f':{etape}:{chemin}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def fusion(nous, eux):
    """Union des deux dictionnaires. En cas d'égalité de clé, NOUS l'emportons
    (capture la plus récente), mais uniquement après tentative de fusion
    récursive : on ne remplace jamais un sous-dictionnaire en bloc."""
    if isinstance(nous, dict) and isinstance(eux, dict):
        out = dict(eux)
        for k, v in nous.items():
            out[k] = fusion(v, eux[k]) if k in eux else v
        return out
    return nous


def main():
    r = git('diff', '--name-only', '--diff-filter=U')
    conflits = [x for x in r.stdout.split('\n') if x.strip()]
    if not conflits:
        print('Aucun conflit à résoudre.')
        return 0

    print(f'{len(conflits)} fichier(s) en conflit :')
    resolus, restants = [], []
    for chemin in conflits:
        if not chemin.endswith('.json'):
            restants.append(chemin)
            print(f'  ⏭️  {chemin} — pas un JSON, laissé en conflit')
            continue
        nous, eux = version(2, chemin), version(3, chemin)
        if nous is None or eux is None:
            restants.append(chemin)
            print(f'  ❌ {chemin} — version illisible, laissé en conflit')
            continue
        if not isinstance(nous, dict) or not isinstance(eux, dict):
            restants.append(chemin)
            print(f'  ❌ {chemin} — pas un objet JSON, fusion refusée')
            continue
        m = fusion(nous, eux)
        ajoutees = len(set(m) - set(nous))
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False)
        git('add', '--', chemin)
        resolus.append(chemin)
        print(f'  ✅ {chemin} — {len(nous)} + {len(eux)} clés -> {len(m)} '
              f'({ajoutees} récupérée(s) de l\'autre exécution)')

    if restants:
        print(f'\n❌ {len(restants)} conflit(s) non résolu(s) : {restants}')
        print('   Résolution silencieuse refusée — mieux vaut un run rouge.')
        return 1
    print(f'\n✅ {len(resolus)} conflit(s) JSON fusionné(s) sans perte.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
