#!/usr/bin/env python3
"""lien_joueur.py — transforme un nom de joueur en lien vers sa fiche.

À IMPORTER depuis les scripts d'alerte. Aucun appel réseau, aucune table
de correspondance : le lien se calcule à partir du nom seul.

    import lien_joueur
    ...
    lien_joueur.duo_html(joueur, adv)   # remplace f"<b>{joueur}</b> vs {adv}"

L'ADRESSE DU WORKER N'A PAS DE VALEUR PAR DÉFAUT, ET C'EST VOULU
----------------------------------------------------------------
FICHES_BASE non renseignée → duo_html() rend exactement le texte
d'avant, sans lien. Pas d'URL inventée, pas de 404 dans une alerte.

Une mauvaise adresse par défaut serait la pire des pannes : le message
part, le lien est là, il ne mène nulle part, et rien dans les logs ne le
signale. Mieux vaut un message identique à celui d'hier.

Pour activer les liens, une seule ligne au niveau `env:` du workflow qui
lance les alertes :

    env:
      FICHES_BASE: https://<le-worker>.workers.dev

POURQUOI LES TOKENS SONT TRIÉS
------------------------------
Le slug doit être identique ici, dans worker-joueurs.js, et dans la clé
de players_profile.json. Les sources de noms du dépôt n'écrivent pas dans
le même ordre :

    moves_detail_hist  « Mattia Bellucci »
    player_form        « bellucci mattia »

Trier les tokens absorbe l'inversion. Sans le tri, un lien sur deux
pointait dans le vide — vérifié sur les 1 030 fiches, zéro écart avec
le tri, et c'est le genre de panne qu'on ne voit pas.

La contrepartie est que le slug ne se lit pas comme un nom
(`bellucci-mattia`). Personne ne lit l'URL d'une alerte.

LE HTML
-------
Les sept scripts envoient en `parse_mode: HTML`, où `<a href>` est admis :
le nom lui-même devient le lien. Pas un caractère de plus dans le message
visible, et c'est le geste attendu — on clique sur le nom.

Les noms sont échappés ici (`&`, `<`, `>`). Ils ne l'étaient pas dans la
version précédente de la ligne : un joueur dont le nom contient une
esperluette faisait répondre 400 à Telegram et l'alerte ne partait pas.
Le cas ne s'est pas produit, mais il coûtait une alerte entière.
"""

import html
import os
import re
import unicodedata


def _base():
    """Lue à chaque appel, pas au chargement : un test peut ainsi régler
    la variable après l'import, et un workflow qui l'oublie ne fige pas
    une valeur vide dans un module importé tôt."""
    return (os.environ.get('FICHES_BASE') or '').rstrip('/')


def slug(nom):
    """Tokens du nom : sans accent, minuscules, TRIÉS, joints par un tiret.

    Doit rester l'image exacte de slug() dans worker-joueurs.js et de
    cle() dans build_profiles.py. Les trois changent ensemble ou aucune.
    """
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode()
    toks = [t for t in re.split(r'[^A-Za-z]+', s.lower()) if len(t) > 1]
    return '-'.join(sorted(toks))


def lien(nom):
    """Lien vers la fiche d'un joueur, ou None si rien n'est configuré."""
    b, s = _base(), slug(nom)
    return f'{b}/j/{s}' if b and s else None


def lien_duo(a, b):
    """Lien vers la comparaison de deux joueurs, sur la même échelle."""
    base, sa, sb = _base(), slug(a), slug(b)
    if not base:
        return None
    if sa and sb:
        return f'{base}/j/{sa}/{sb}'
    return f'{base}/j/{sa or sb}' if (sa or sb) else None


def nom_html(nom, gras=False):
    """Le nom, cliquable s'il y a une base, en texte sinon."""
    t = html.escape(str(nom), quote=False)
    if gras:
        t = f'<b>{t}</b>'
    u = lien(nom)
    return f'<a href="{u}">{t}</a>' if u else t


def duo_html(joueur, adv):
    """La ligne « X vs Y » des alertes, les deux noms cliquables.

    Remplace exactement f"<b>{joueur}</b> vs {adv}" et rend la même chose
    au caractère près quand FICHES_BASE n'est pas réglée.
    """
    return f'{nom_html(joueur, gras=True)} vs {nom_html(adv)}'


def ligne_fiches(a, b=None, prefixe='Fiches'):
    """Une ligne à part, pour un message qui n'est pas en HTML (X)."""
    u = lien_duo(a, b) if b else lien(a)
    return f'{prefixe} : {u}' if u else ''


if __name__ == '__main__':
    for a, b in (('Mattia Bellucci', 'bellucci mattia'),
                 ('Félix Auger-Aliassime', 'auger aliassime felix'),
                 ('Aryna Sabalenka', 'sabalenka aryna')):
        assert slug(a) == slug(b), (a, b, slug(a), slug(b))

    os.environ.pop('FICHES_BASE', None)
    nu = duo_html('Aryna Sabalenka', 'Linda Noskova')
    assert nu == '<b>Aryna Sabalenka</b> vs Linda Noskova', nu
    print('sans FICHES_BASE :', nu)

    os.environ['FICHES_BASE'] = 'https://exemple.workers.dev/'
    print('avec FICHES_BASE :', duo_html('Aryna Sabalenka', 'Linda Noskova'))
    print('nom piégé        :', duo_html('A & B', 'C <D>'))
