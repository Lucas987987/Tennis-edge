#!/usr/bin/env python3
"""patcher_liens.py — rend les noms de joueurs cliquables dans les alertes.

    python scripts/patcher_liens.py          # applique
    python scripts/patcher_liens.py --dry    # montre sans rien écrire

Modifie sur place les sept scripts qui nomment deux joueurs :

    h13_signal  h15_signal  h16_signal  h16b_signal  h17_signal
    h18_signal  zone_signal

DEUX MODIFICATIONS PAR FICHIER, PAS UNE DE PLUS
-----------------------------------------------
1. `import lien_joueur` ajouté juste après le `sys.path.insert(...)` qui
   existe déjà dans les sept — donc l'import marche quel que soit le
   répertoire courant du runner.

2. `f"<b>{joueur}</b> vs {adv}"` devient `f"{lien_joueur.duo_html(joueur, adv)}"`.

Rien d'autre n'est touché : ni `envoyer()`, ni `_suivi()`, ni les textes
de gel. Le script est idempotent — relancé, il ne fait rien.

CE QUI SE PASSE SI ON OUBLIE FICHES_BASE
-----------------------------------------
Rien. `duo_html()` rend alors exactement la même chaîne qu'aujourd'hui,
au caractère près. Les alertes partent comme avant, simplement sans lien.
C'est le seul comportement acceptable : un lien par défaut vers une
adresse devinée aurait produit des 404 dans chaque alerte, sans rien
dans les logs pour le signaler.

L'ORDRE À SUIVRE
----------------
1. ajouter `scripts/lien_joueur.py` ;
2. lancer ce patcher avec `--dry`, lire la sortie ;
3. le lancer pour de bon ;
4. seulement ensuite, régler FICHES_BASE dans le workflow des alertes.

Entre 3 et 4, les alertes tournent inchangées : rien ne presse.
"""

import os
import re
import sys

CIBLES = ['h13_signal.py', 'h15_signal.py', 'h16_signal.py',
          'h16b_signal.py', 'h17_signal.py', 'h18_signal.py',
          'zone_signal.py']

ANCRE = 'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))'
IMPORT = ('import lien_joueur                   # noqa: E402 — liens vers '
          'les fiches\n')

# Les sept écrivent la même chose à un espace et un \n près. On capture ce
# qui entoure pour réécrire sans toucher à l'indentation ni au \n final.
MOTIF = re.compile(r'f"<b>\{joueur\}</b> vs \{adv\}(\\n)?"')

# Un seul appel remplace la ligne : tout le HTML est dans lien_joueur, donc
# rien à changer ici le jour où l'adresse du worker change, et aucun
# guillemet imbriqué dans le code généré. Une version précédente écrivait
# le `<a href>` directement et cassait les sept fichiers sur un `\'` de
# raw-string ; la fonction supprime le problème au lieu de le contourner.
def _remplacement(m):
    fin = m.group(1) or ''
    return 'f"{lien_joueur.duo_html(joueur, adv)}' + fin + '"'


def patcher(chemin, sec):
    src = open(chemin, encoding='utf-8').read()
    faits = []

    if 'import lien_joueur' in src:
        faits.append('import déjà là')
    elif ANCRE not in src:
        return f'ANCRE INTROUVABLE — non modifié'
    else:
        src = src.replace(ANCRE, ANCRE + '\n' + IMPORT.rstrip(), 1)
        faits.append('import ajouté')

    n = len(MOTIF.findall(src))
    if n == 0:
        faits.append('ligne joueurs déjà patchée' if 'lien_joueur.duo_html'
                     in src else 'LIGNE JOUEURS INTROUVABLE')
    else:
        src = MOTIF.sub(_remplacement, src)
        faits.append(f'{n} ligne(s) joueurs liée(s)')

    # Garde-fou : un fichier qui ne compile plus n'est pas écrit.
    try:
        compile(src, chemin, 'exec')
    except SyntaxError as e:
        return f'SYNTAXE CASSÉE ligne {e.lineno} — NON ÉCRIT ({e.msg})'

    if not sec:
        open(chemin, 'w', encoding='utf-8').write(src)
    return ', '.join(faits)


def main():
    sec = '--dry' in sys.argv
    ici = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(ici, 'lien_joueur.py')):
        print('scripts/lien_joueur.py absent — à ajouter avant de patcher.')
        return 1
    ko = 0
    for f in CIBLES:
        p = os.path.join(ici, f)
        if not os.path.exists(p):
            print(f'{f:18} absent')
            ko += 1
            continue
        r = patcher(p, sec)
        print(f'{f:18} {r}')
        if r.isupper() or 'INTROUVABLE' in r or 'CASSÉE' in r:
            ko += 1
    print('\n(simulation, rien écrit)' if sec
          else '\nPatch appliqué.' if not ko else f'\n{ko} fichier(s) à voir.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
