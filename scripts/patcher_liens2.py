#!/usr/bin/env python3
"""patcher_liens2.py — les trois scripts d'alerte que le premier patcher a manqués.

    python scripts/patcher_liens2.py --dry
    python scripts/patcher_liens2.py

CE QUI A ÉTÉ MANQUÉ, ET POURQUOI
---------------------------------
patcher_liens.py cherchait la chaîne f"<b>{joueur}</b> vs {adv}", la forme
des sept scripts d'hypothèses. Trois autres envoient des alertes avec des
noms de joueurs, dans une forme différente, et sont restés en texte simple :

    canal_public.py:312       📊 ÉVOLUTION DE COTE · {_home} vs {_away}
    steam_alert.py:571        🎯 MISER · {_home} vs {_away}
    early_open_signal.py:182  <b>{home}</b> vs <b>{away}</b>

Les deux premiers sont ceux qui portent le trafic : canal_public publie sur
le canal à abonnés, steam_alert envoie les alertes MISER.

DEUX TRAITEMENTS, PARCE QUE DEUX FORMATS
-----------------------------------------
canal_public et steam_alert n'envoient AUCUN parse_mode à l'API Telegram :
leurs messages sont du texte brut. Un <a href> y apparaîtrait littéralement,
balises comprises. On y ajoute donc une URL EN CLAIR sur sa propre ligne —
Telegram la rend cliquable d'elle-même, et sans confirmation puisqu'il n'y a
rien à masquer. C'est `ligne_texte()`.

early_open_signal envoie en HTML, comme les sept : il reçoit un lien masqué
sur les deux noms, par `duo_html()`, exactement comme eux.

OÙ LA LIGNE EST INSÉRÉE
------------------------
Après le nom du tournoi, avant le reste du message. Le lecteur voit donc
l'en-tête, puis le lien, puis les chiffres. Mettre l'URL en fin de message
l'aurait noyée sous huit lignes de données.

canal_public passe déjà `disable_web_page_preview: true` : l'URL n'ouvrira
pas de carte d'aperçu et le message reste compact.

SANS FICHES_BASE
----------------
`ligne_texte()` et `duo_html()` rendent exactement ce qu'ils rendaient
avant, au caractère près. Le patch est donc sans effet tant que la variable
n'est pas réglée — elle l'est déjà dans courbes_alertes.yml.
"""

import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))

# Point d'ancrage de l'import, PAR FICHIER : steam_alert.py n'a pas de
# sys.path.insert — il n'en a pas besoin, Python met le dossier du script
# en tête de sys.path quand on lance `python scripts/steam_alert.py`.
# L'ancrer sur une ligne qui n'existe pas l'aurait laissé de côté en
# silence, ce qui est exactement la panne qu'on est en train de réparer.
ANCRES = {
    'canal_public.py':
        'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))',
    'early_open_signal.py':
        'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))',
    'steam_alert.py':
        'import curves_common as cc',
}
IMPORT = 'import lien_joueur                   # noqa: E402 — liens vers les fiches'

# (fichier, texte à trouver, texte de remplacement)
EDITS = [
    ('canal_public.py',
     """        msg = (f"📊 ÉVOLUTION DE COTE · {g['_home']} vs {g['_away']}"
               + (f" ({g['_tour']})" if g['_tour'] else "") + "\\n\"""",
     """        msg = (f"📊 ÉVOLUTION DE COTE · {g['_home']} vs {g['_away']}"
               + (f" ({g['_tour']})" if g['_tour'] else "")
               + lien_joueur.ligne_texte(g['_home'], g['_away']) + "\\n\""""),

    ('steam_alert.py',
     """        msg = (f"🎯 MISER{_MKT_LABEL.get(MARKET, '')} · {bk['_home']} vs {bk['_away']}"
               + (f" ({bk['_tour']})" if bk['_tour'] else "") + "\\n\"""",
     """        msg = (f"🎯 MISER{_MKT_LABEL.get(MARKET, '')} · {bk['_home']} vs {bk['_away']}"
               + (f" ({bk['_tour']})" if bk['_tour'] else "")
               + lien_joueur.ligne_texte(bk['_home'], bk['_away']) + "\\n\""""),

    ('early_open_signal.py',
     '''        f"<b>{home}</b> vs <b>{away}</b>\\n"''',
     '''        f"{lien_joueur.duo_html(home, away)}\\n"'''),
]


def patcher(nom, avant, apres, sec):
    chemin = os.path.join(ICI, nom)
    if not os.path.exists(chemin):
        return 'absent'
    src = open(chemin, encoding='utf-8').read()
    faits = []

    ancre = ANCRES[nom]
    if 'import lien_joueur' in src:
        faits.append('import déjà là')
    elif src.count(ancre) != 1:
        return f'ANCRE IMPORT trouvée {src.count(ancre)} fois — non modifié'
    else:
        src = src.replace(ancre, ancre + '\n' + IMPORT, 1)
        faits.append('import ajouté')

    n = src.count(avant)
    if n == 0:
        faits.append('ligne déjà patchée' if 'lien_joueur.' in src
                     else 'LIGNE MESSAGE INTROUVABLE')
    elif n > 1:
        return f'LIGNE MESSAGE TROUVÉE {n} FOIS — non modifié'
    else:
        src = src.replace(avant, apres, 1)
        faits.append('lien ajouté au message')

    try:
        compile(src, chemin, 'exec')
    except SyntaxError as e:
        return f'SYNTAXE CASSÉE ligne {e.lineno} — NON ÉCRIT ({e.msg})'

    if not sec:
        open(chemin, 'w', encoding='utf-8').write(src)
    return ' · '.join(faits)


def main():
    sec = '--dry' in sys.argv
    if not os.path.exists(os.path.join(ICI, 'lien_joueur.py')):
        print('scripts/lien_joueur.py absent.')
        return 1
    ko = 0
    for nom, avant, apres in EDITS:
        r = patcher(nom, avant, apres, sec)
        print(f'{nom:24} {r}')
        if 'INTROUVABLE' in r or 'CASSÉE' in r or r == 'absent':
            ko += 1
    if sec:
        print('\n(simulation, rien écrit)')
        return 0
    if ko:
        print(f'\n{ko} fichier(s) à voir.')
        return 1

    # On importe les trois : compiler ne prouve pas qu'ils démarrent.
    sys.path.insert(0, ICI)
    for nom, _, _ in EDITS:
        mod = nom[:-3]
        try:
            __import__(mod)
            print(f'  {mod:24} import OK')
        except Exception as e:
            print(f'  {mod:24} IMPORT KO : {type(e).__name__} {e}')
            ko += 1
    print('\nPatch appliqué.' if not ko else '\nÀ VÉRIFIER avant de commiter.')
    return 1 if ko else 0


if __name__ == '__main__':
    raise SystemExit(main())
