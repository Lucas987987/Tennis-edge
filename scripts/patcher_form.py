#!/usr/bin/env python3
"""patcher_form.py — remet player_form.py en production.

    python scripts/patcher_form.py --dry
    python scripts/patcher_form.py

LE DÉFAUT
---------
player_form.json est lu par build_profiles.py — c'est lui qui donne « Sur
ses 10 derniers » sur chaque fiche. Mais player_form.py n'est lancé par
AUCUN workflow : `grep -rl player_form.py .github/workflows/` ne rend rien.

Le fichier porte sa propre date de fabrication : 2026-10-05. Il a donc été
produit à la main, une fois, et plus jamais depuis. Constaté le 08/10 : une
fiche annonçait « dernier match : hier » pour un match du 04/10.

POURQUOI PAS UN WORKFLOW À PART
-------------------------------
player_profiles.yml tourne déjà tous les jours à 6 h 20 et sa première
action est de lancer build_profiles.py, qui LIT player_form.json. Mettre la
régénération ailleurs, c'est accepter que les deux fichiers soient d'âges
différents, et créer exactement le genre de décalage silencieux qui a coûté
la journée du 08/10 — move_audit jugeant sur 3 books pendant que les
détecteurs en utilisaient 7.

Un producteur et son consommateur dans le même job, dans cet ordre : il n'y
a pas de désynchronisation possible.

CE QUE L'ÉTAPE FAIT
-------------------
1. curves_parts.py rebuild — player_form lit book_curves_live.jsonl pour
   ses résidus de marché. Le fichier plat n'est plus commité, il se
   reconstruit depuis parts/live_*. Sans lui le script tourne quand même
   (la lecture des courbes est en try/except) mais perd cette section.
2. player_form.py.

`|| true` sur les deux : une panne ici ne doit pas empêcher les fiches de
se construire. Elles se dégradent — « Sur ses 10 derniers » disparaît —
elles ne tombent pas.

ET LE COMMIT
------------
player_form.json est ajouté à la ligne `git add` de l'étape Commit. Sans
ça le fichier serait régénéré sur le runner et perdu avec lui, ce qui est
pire que l'état actuel : on croirait l'avoir réparé.
"""

import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
WF = os.path.join(ICI, '..', '.github', 'workflows', 'player_profiles.yml')

# On insère AVANT le commentaire qui précède « Construire les fiches », pas
# entre lui et son étape : il dit « build_profiles ne lit QUE des fichiers
# plats, pas de restore_curves a prevoir », ce qui reste vrai de
# build_profiles et deviendrait faux s'il semblait décrire la nouvelle étape.
ANCRE = """      # build_profiles ne lit QUE des fichiers plats a la racine : ni
      # partitions, ni releases. Pas de restore_curves a prevoir.
      - name: Construire les fiches
        run: python scripts/build_profiles.py"""

ETAPE = """      # AJOUTÉ LE 08/10/2026. player_form.py n'était lancé par aucun
      # workflow : player_form.json datait du 05/10 et une fiche annonçait
      # « dernier match : hier » pour un match du 04/10.
      #
      # Ici et pas ailleurs : build_profiles.py LIT ce fichier à l'étape
      # suivante. Producteur et consommateur dans le même job, dans cet
      # ordre — aucun décalage d'âge possible entre les deux.
      #
      # rebuild d'abord : les courbes plates ne sont plus commitées, et
      # player_form les lit pour ses résidus de marché. Sans elles il tourne
      # quand même, en perdant cette seule section.
      - name: Forme et fatigue des joueurs
        run: |
          python scripts/curves_parts.py rebuild || true
          python scripts/player_form.py || true

"""


def main():
    sec = '--dry' in sys.argv
    if not os.path.exists(WF):
        print(f'{WF} introuvable.')
        return 1
    src = open(WF, encoding='utf-8').read()
    faits = []

    if 'player_form.py' in src:
        faits.append('étape déjà présente')
    elif ANCRE not in src:
        print('ANCRE INTROUVABLE — le workflow a changé, rien modifié.')
        return 1
    else:
        src = src.replace(ANCRE, ETAPE + ANCRE, 1)
        faits.append('étape ajoutée avant « Construire les fiches »')

    # Le commit ne porte que players_profile.json : sans cette ligne, le
    # player_form.json régénéré mourrait avec le runner.
    AV = '          git add players_profile.json'
    AP = '          git add players_profile.json player_form.json'
    if AP in src:
        faits.append('commit déjà élargi')
    elif AV in src:
        src = src.replace(AV, AP, 1)
        faits.append('player_form.json ajouté au commit')
    else:
        faits.append('LIGNE git add INTROUVABLE — à vérifier à la main')

    # Garde-fou : un YAML cassé ferait échouer le workflow au démarrage,
    # sans run, et les fiches cesseraient d'être produites.
    try:
        import yaml
        d = yaml.safe_load(src)
        noms = [s.get('name') for j in d['jobs'].values() for s in j['steps']]
        assert 'Forme et fatigue des joueurs' in noms, 'etape absente apres patch'
        assert noms.index('Forme et fatigue des joueurs') \
            < noms.index('Construire les fiches'), 'ordre inverse'
        faits.append('YAML valide, ordre vérifié')
    except ImportError:
        faits.append('PyYAML absent — validation sautée')
    except Exception as e:
        print(f'YAML CASSÉ ({e}) — NON ÉCRIT.')
        return 1

    print(' · '.join(faits))
    if sec:
        print('\n(simulation, rien écrit)')
    else:
        open(WF, 'w', encoding='utf-8').write(src)
        print('\nÉcrit. Le prochain run de 6 h 20 régénérera player_form.json.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
