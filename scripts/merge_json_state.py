#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_json_state.py — Résout les conflits git sur les fichiers JSON d'état.

LE PROBLÈME
capture_closing tourne toutes les 8 à 20 minutes. Quand deux exécutions se
chevauchent — ou qu'un autre workflow pousse entre le checkout et le push —
git tombe en conflit sur les fichiers JSON réécrits en entier :
    CONFLICT (content): Merge conflict in closing_lines.json
    CONFLICT (content): Merge conflict in live_odds.json
Le merge échoue, le push est rejeté, et TOUT le run est perdu — y compris les
partitions live qui, elles, s'étaient fusionnées sans problème grâce au pilote
« union » du .gitattributes.

POURQUOI « union » NE PEUT PAS SERVIR ICI
Ces fichiers ne sont pas des journaux append-only : ce sont des documents JSON.
Concaténer deux versions produirait du JSON invalide.

POURQUOI « -X ours » NON PLUS
closing_lines.json est un ACCUMULATEUR : les entrées s'ajoutent au fil des
captures et se complètent. Prendre systématiquement notre version effacerait
les matchs ajoutés par l'exécution concurrente.

DEUX FORMES À TRAITER — la leçon du 22/08/2026
La première version ne savait fusionner que les OBJETS. Or live_odds.json et
matches_oddspapi.json sont des LISTES de matchs. Elles étaient donc refusées,
le run échouait quand même, et le correctif ne servait à rien dans la moitié
des cas :
    ❌ live_odds.json — pas un objet JSON, fusion refusée
    ❌ matches_oddspapi.json — pas un objet JSON, fusion refusée
Les listes sont désormais fusionnées par IDENTIFIANT d'élément (id,
fixture_id, uid...), avec la même règle : union des deux côtés, le nôtre
l'emporte en cas d'égalité car il vient de la capture la plus récente.

CE QU'IL REFUSE TOUJOURS
Une liste dont les éléments n'ont pas d'identifiant exploitable : fusionner à
l'aveugle produirait des doublons ou des pertes silencieuses. Mieux vaut un
run rouge qu'une résolution fausse.

Usage : appelé après un `git merge` en conflit, avant de retenter le commit.
Sortie : 0 si tous les conflits JSON sont résolus, 1 sinon.
"""
import json
import subprocess
import sys

# Champs testés, dans l'ordre, pour identifier un élément de liste.
CLES_ID = ('id', 'fixture_id', 'uid', 'match_id', 'ticker', 'key', 'slug')


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


def _cle(element):
    """Identifiant d'un élément de liste, ou None si indéterminable."""
    if not isinstance(element, dict):
        return None
    for k in CLES_ID:
        v = element.get(k)
        if v:
            return f'{k}={v}'
    # Repli : un match est identifié par ses joueurs et son horaire.
    h = element.get('home_team') or element.get('home')
    a = element.get('away_team') or element.get('away')
    t = element.get('commence_time') or element.get('start_time')
    if h and a:
        return f'pair={h}|{a}|{str(t)[:10]}'
    return None


def fusion(nous, eux):
    """Union des deux versions.

    Objets : union des clés, fusion récursive des sous-objets, NOUS l'emportons
    en cas d'égalité (capture la plus récente).
    Listes  : union par identifiant d'élément, même règle de priorité. L'ordre
    d'origine du côté « nous » est préservé, les éléments propres à « eux »
    sont ajoutés à la suite.
    Renvoie None si la fusion est impossible — jamais un résultat approximatif.
    """
    if isinstance(nous, dict) and isinstance(eux, dict):
        out = dict(eux)
        for k, v in nous.items():
            if k in eux:
                m = fusion(v, eux[k])
                out[k] = v if m is None else m
            else:
                out[k] = v
        return out

    if isinstance(nous, list) and isinstance(eux, list):
        idx_nous = [(_cle(x), x) for x in nous]
        idx_eux = [(_cle(x), x) for x in eux]
        # Sans identifiant sur AUCUN élément, on ne sait pas fusionner.
        if any(k is None for k, _ in idx_nous + idx_eux):
            return None
        vus = {}
        ordre = []
        for k, x in idx_nous:
            vus[k] = x
            ordre.append(k)
        for k, x in idx_eux:
            if k in vus:
                m = fusion(vus[k], x)
                if m is not None:
                    vus[k] = m
            else:
                vus[k] = x
                ordre.append(k)
        return [vus[k] for k in ordre]

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
        m = fusion(nous, eux)
        if m is None:
            restants.append(chemin)
            print(f'  ❌ {chemin} — éléments sans identifiant, fusion refusée')
            continue
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False)
        git('add', '--', chemin)
        resolus.append(chemin)
        if isinstance(m, dict):
            gagnees = len(set(m) - set(nous))
            print(f'  ✅ {chemin} — objet · {len(nous)} + {len(eux)} clés '
                  f'-> {len(m)} ({gagnees} récupérée(s) de l\'autre exécution)')
        else:
            gagnees = len(m) - len(nous)
            print(f'  ✅ {chemin} — liste · {len(nous)} + {len(eux)} éléments '
                  f'-> {len(m)} ({gagnees} récupéré(s) de l\'autre exécution)')

    if restants:
        print(f'\n❌ {len(restants)} conflit(s) non résolu(s) : {restants}')
        print('   Résolution silencieuse refusée — mieux vaut un run rouge.')
        return 1
    print(f'\n✅ {len(resolus)} conflit(s) JSON fusionné(s) sans perte.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
