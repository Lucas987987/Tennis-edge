#!/usr/bin/env python3
"""patcher_gel_forme.py — gèle l'hypothèse « le marché surcote la forme ».

    python scripts/patcher_gel_forme.py --dry
    python scripts/patcher_gel_forme.py

Ajoute un bloc de constantes à validation_report.py. N'ajoute AUCUN
watcher : le verdict se mesurera avec player_form.py, qui recalcule déjà
ces résidus à chaque run. Ce patch fige le protocole, pas le calcul.

CE QUI EST GELÉ
---------------
Population : tous les matchs disputés APRÈS la date de gel pour lesquels
on dispose d'un prix Pinnacle pré-match ET d'un écart de forme supérieur
à 0,20 en valeur absolue.

Prédiction : le côté EN MEILLEURE FORME réalise un résidu NÉGATIF —
il gagne moins souvent que son prix ne l'annonce.

Verdict : à n = 400, pas avant.

POURQUOI 400 ET PAS 100
-----------------------
C'est le point qui a failli être manqué. Le seuil maison de 100 aurait
garanti un verdict non concluant, quel que soit le résultat.

Effet observé in-sample : -5,57 points, écart-type tel que l'IC95 à
n=100 vaut +-9,2 points. Un effet de 5,6 ne peut pas sortir d'un
intervalle de 9,2 : le test serait perdu d'avance.

    n=100   IC95 +-9,2 pts   ne conclut pas
    n=200   IC95 +-6,5 pts   ne conclut pas
    n=300   IC95 +-5,3 pts   limite
    n=400   IC95 +-4,6 pts   conclut

Au rythme mesuré de 124 matchs par mois dans cette population, n=400
tombe vers la mi-janvier 2027.

CE QUI REND CETTE HYPOTHÈSE PLUS SOLIDE QU'ELLE N'EN A L'AIR
------------------------------------------------------------
player_form.py n'a signalé qu'UNE tranche significative sur trois, et son
propre test de permutation rappelle que 5 % des tirages aléatoires en
produisent autant. Lu ainsi, c'est du bruit.

Mais les tranches ne sont pas indépendantes. « A en meilleure forme » et
« A en moins bonne forme » décrivent le MÊME phénomène vu des deux côtés,
puisque A et B sont home et away, étiquettes arbitraires. Or les deux
pointent dans le même sens :

    A meilleure    n=280   residu -6,7  IC95 [-12,2 ; -1,2]
    A moins bonne  n=216   residu +4,1  IC95 [ -2,2 ; +10,4]

Le côté le mieux en forme sous-performe dans les deux cas. Mises en
commun, les deux tranches donnent -5,57 points sur n=496, IC95 approché
[-9,71 ; -1,42].

C'est une réplication interne, pas une tranche isolée. Elle ne remplace
pas une validation hors échantillon — d'où ce gel.

CE QUE CE N'EST PAS
-------------------
Pas un signal à jouer. Le résidu se mesure contre la CLÔTURE Pinnacle :
il dit que le marché se trompe, pas qu'on peut encaisser l'écart. Reste
à savoir si un opérateur accessible offre ce prix, et avec quelle marge.

Pas non plus une hypothèse sur la population des alertes. Les 20 autres
portent sur des mouvements détectés ; celle-ci porte sur tous les matchs
cotés. Deux populations différentes — à ne pas agréger dans un Holm
commun sans y réfléchir.
"""

import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
CIBLE = os.path.join(ICI, 'validation_report.py')

ANCRE = """FREEZE_DATE_H16B = '2026-09-27'
# H16-B = H16 privée des ultra-favoris. Le SEUL seuil ajouté est 1,30.
H16B_PIN_OPEN_MIN = 1.30"""

BLOC = '''
# ── 21e HYPOTHÈSE — LE MARCHÉ SURCOTE LA FORME RÉCENTE ──────────────────
#
# GELÉE LE 08/10/2026, sur le rapport de player_form.py du même jour.
#
# ÉNONCÉ. Sur les matchs où les deux joueurs diffèrent de plus de 20 points
# de taux de victoire sur leurs 10 derniers matchs, le côté EN MEILLEURE
# FORME gagne MOINS souvent que son prix Pinnacle pré-match ne l'annonce.
#
# OBSERVÉ IN-SAMPLE (juin-octobre 2026, 496 matchs) :
#     A meilleure    n=280   residu -6,7 pts  IC95 [-12,2 ; -1,2]
#     A moins bonne  n=216   residu +4,1 pts  IC95 [ -2,2 ; +10,4]
#     mis en commun  n=496   residu -5,57 pts IC95 [-9,71 ; -1,42] (approché)
#
# Les deux tranches pointent dans le même sens — A et B étant home et away,
# étiquettes arbitraires, elles décrivent le même phénomène vu des deux
# côtés. C'est une réplication interne, pas une tranche isolée sur trois.
#
# RÉSERVE. player_form.py avertit que 5 % des tirages ALÉATOIRES produisent
# au moins une tranche significative. La mise en commun réduit ce risque
# sans l'annuler : l'énoncé reste à valider hors échantillon.
#
# CE N'EST PAS UN SIGNAL À JOUER. Le résidu se mesure contre la CLÔTURE
# Pinnacle : il dit que le marché se trompe, pas qu'on peut encaisser
# l'écart. La question de l'exécution vient après, si le verdict est
# positif.
#
# POPULATION DISJOINTE DES 20 AUTRES. Celles-ci portent sur des mouvements
# DÉTECTÉS ; celle-ci sur tous les matchs cotés. Ne pas agréger dans un
# Holm commun sans y réfléchir.
FREEZE_DATE_FORME = '2026-10-08'
FORME_ECART_MIN = 0.20          # |taux_A - taux_B| sur 10 matchs
FORME_N_CIBLE = 400             # verdict à ce n, pas avant

# POURQUOI 400 ET PAS LE SEUIL MAISON DE 100.
# À n=100 l'IC95 vaut +-9,2 points. Un effet de 5,6 points ne peut pas en
# sortir : le verdict serait non concluant par construction, quel que soit
# le résultat réel. Geler à 100 aurait été se condamner d'avance.
#     n=100  +-9,2   n=200  +-6,5   n=300  +-5,3   n=400  +-4,6
# Au rythme mesuré de 124 matchs/mois dans cette population, n=400 tombe
# vers la mi-janvier 2027.
'''


def main():
    sec = '--dry' in sys.argv
    if not os.path.exists(CIBLE):
        print('validation_report.py introuvable.')
        return 1
    src = open(CIBLE, encoding='utf-8').read()

    if 'FREEZE_DATE_FORME' in src:
        print('déjà gelée — rien fait.')
        return 0
    if src.count(ANCRE) != 1:
        print(f'ANCRE trouvée {src.count(ANCRE)} fois (attendu 1) — rien fait.')
        return 1

    src = src.replace(ANCRE, ANCRE + BLOC, 1)

    try:
        compile(src, CIBLE, 'exec')
    except SyntaxError as e:
        print(f'SYNTAXE CASSÉE ligne {e.lineno} — NON ÉCRIT ({e.msg})')
        return 1

    if sec:
        print('gel prêt à être écrit  ·  (simulation, rien écrit)')
        return 0

    open(CIBLE, 'w', encoding='utf-8').write(src)

    # On relit par import : compiler ne prouve pas que les constantes
    # existent et valent ce qu'on croit.
    sys.path.insert(0, ICI)
    import validation_report as vr
    print(f'gelée le {vr.FREEZE_DATE_FORME}  ·  '
          f'écart min {vr.FORME_ECART_MIN}  ·  verdict à n={vr.FORME_N_CIBLE}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
