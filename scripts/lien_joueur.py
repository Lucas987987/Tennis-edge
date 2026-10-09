#!/usr/bin/env python3
"""lien_joueur.py — transforme un nom de joueur en lien vers sa fiche.

À IMPORTER depuis les scripts d'alerte. Aucun appel réseau, aucune table
de correspondance : le lien se calcule à partir du nom seul.

    import lien_joueur
    ...
    lien_joueur.duo_html(joueur, adv)   # remplace f"<b>{joueur}</b> vs {adv}"

L'ADRESSE DU WORKER A UNE VALEUR PAR DÉFAUT DEPUIS LE 09/10/2026
----------------------------------------------------------------
Elle n'en avait pas, volontairement, tant que l'adresse n'était pas
connue : une adresse devinée aurait produit des liens morts sans que
rien ne le signale. L'adresse est désormais connue et vérifiée :

    https://joueurs.tennis-edge.workers.dev

Et l'absence de défaut a produit, elle aussi, la panne silencieuse
qu'elle devait éviter. La variable n'était réglée que dans
courbes_alertes.yml ; or odds_movement.py est lancé par
capture_closing.py, dans capture_closing.yml. Les alertes « Mouvement
de cote » sont donc parties avec des noms non cliquables, sans erreur.
Une adresse par défaut ici couvre tous les workflows d'un coup, y
compris ceux qu'on ajoutera.

    FICHES_BASE absente  -> adresse par défaut
    FICHES_BASE=""       -> aucun lien, texte d'avant au caractère près
    FICHES_BASE=<autre>  -> cette adresse

Si l'adresse change un jour (nouveau sous-domaine, nom de domaine),
c'est ici qu'on la change — et dans courbes_alertes.yml, qui la fixe
encore explicitement.

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


DEFAUT = 'https://joueurs.tennis-edge.workers.dev'


def _base():
    """Lue à chaque appel, pas au chargement : un test peut ainsi régler
    la variable après l'import.

    Absente -> DEFAUT. Vide -> pas de lien (moyen de couper sans toucher
    au code). La distinction entre « absente » et « vide » est voulue."""
    v = os.environ.get('FICHES_BASE')
    if v is None:
        v = DEFAUT
    return v.strip().rstrip('/')


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
    """La ligne « X vs Y » des alertes Telegram.

    LES DEUX NOMS MÈNENT À LA MÊME PAGE : leur COMPARAISON.

    La première version envoyait chaque nom vers sa fiche solo. Mais une
    alerte parle d'un match, pas d'un joueur : la question qu'on se pose en
    la lisant est « que valent ces deux-là l'un contre l'autre », et c'est
    la page de comparaison qui y répond — les deux prix sur la même
    échelle, le face-à-face, et un lien vers chaque fiche complète pour qui
    veut aller plus loin. Quel que soit le nom touché, on arrive au bon
    endroit du premier coup.

    LIEN MASQUÉ ASSUMÉ. Telegram affiche « Ouvrir ce lien ? » avant
    d'ouvrir, parce que le texte visible diffère de l'URL. C'est sa
    protection contre l'hameçonnage et elle ne se désactive pas côté bot.
    L'éviter imposerait d'écrire l'adresse en clair dans chaque alerte :
    un clic de confirmation est un meilleur marché qu'une ligne d'URL.

    Pour X, voir ligne_x() : là-bas l'URL nue est la seule forme possible.

    Sans FICHES_BASE, rend exactement la chaîne d'avant, au caractère près.
    """
    a = html.escape(str(joueur), quote=False)
    b = html.escape(str(adv), quote=False)
    u = lien_duo(joueur, adv)
    if not u:
        return f'<b>{a}</b> vs {b}'
    return f'<a href="{u}"><b>{a}</b></a> vs <a href="{u}">{b}</a>'

def ligne_texte(joueur, adv=None):
    """Le lien pour un message SANS parse_mode, prêt à concaténer.

    canal_public.py et steam_alert.py envoient en texte brut : ils ne
    passent aucun parse_mode à l'API Telegram. Un <a href> y apparaîtrait
    littéralement, balises comprises. Seule une URL écrite en clair y
    devient cliquable — et elle s'ouvre sans confirmation, puisqu'il n'y
    a rien à masquer.

    Rend une chaîne COMMENÇANT par un saut de ligne, pour se coller à la
    fin d'une ligne existante sans la réécrire. Vide si FICHES_BASE n'est
    pas réglée : le message part alors exactement comme avant.
    """
    u = lien_duo(joueur, adv) if adv else lien(joueur)
    return f'\n{u}' if u else ''


def ligne_x(joueur, adv=None):
    """La même information pour un post sur X, où le HTML n'existe pas.

    X ne connaît pas le lien masqué : une URL devient cliquable parce
    qu'elle est écrite. On la met donc en clair, sur sa propre ligne, et
    X l'affiche en carte si la page porte ses balises Open Graph — ce que
    worker-joueurs.js fait pour la fiche comme pour la comparaison.

    Rend une chaîne vide si FICHES_BASE n'est pas réglée : mieux vaut un
    post sans lien qu'un post avec un lien mort.
    """
    u = lien_duo(joueur, adv) if adv else lien(joueur)
    return u or ''

def ligne_x_masquee(joueur, adv=None):
    """L'adresse de la fiche EN SPOILER, pour un message HTML recopié vers X.

    AJOUTÉ LE 09/10/2026. Deux contraintes qui se contredisent :
      - dans Telegram, pas d'adresse visible (seuls les noms sont cliquables) ;
      - sur X, un nom ne peut PAS être un lien : seule une adresse écrite en
        entier devient cliquable. Un lien masqué sur un nom redevient du texte
        simple au copier-coller.

    Le spoiler (<tg-spoiler>) les concilie : Telegram l'affiche flouté, sans
    adresse lisible, et le copier-coller en reprend le texte en clair. Placée
    en DERNIÈRE ligne, l'adresse est aussi celle dont X tire la carte
    d'aperçu — le titre et la description viennent des balises og: de la page.

    Vide sans FICHES_BASE (même règle que les autres fonctions).
    """
    u = lien_duo(joueur, adv) if adv else lien(joueur)
    return f'\n<tg-spoiler>{html.escape(u)}</tg-spoiler>' if u else ''


def ligne_fiches(a, b=None, prefixe='Fiches'):
    """Une ligne à part, pour un message qui n'est pas en HTML (X)."""
    u = lien_duo(a, b) if b else lien(a)
    return f'{prefixe} : {u}' if u else ''


if __name__ == '__main__':
    for a, b in (('Mattia Bellucci', 'bellucci mattia'),
                 ('Félix Auger-Aliassime', 'auger aliassime felix'),
                 ('Aryna Sabalenka', 'sabalenka aryna')):
        assert slug(a) == slug(b), (a, b, slug(a), slug(b))

    os.environ['FICHES_BASE'] = ''
    nu = duo_html('Aryna Sabalenka', 'Linda Noskova')
    assert nu == '<b>Aryna Sabalenka</b> vs Linda Noskova', nu
    print('FICHES_BASE vide :', nu)

    os.environ.pop('FICHES_BASE', None)
    defaut = duo_html('Aryna Sabalenka', 'Linda Noskova')
    assert DEFAUT + '/j/' in defaut, defaut
    print('sans FICHES_BASE :', defaut)

    os.environ['FICHES_BASE'] = 'https://exemple.workers.dev/'
    print('avec FICHES_BASE :', duo_html('Aryna Sabalenka', 'Linda Noskova'))
    print('nom piégé        :', duo_html('A & B', 'C <D>'))
    print('spoiler pour X   :', repr(ligne_x_masquee('Elmer Moller', 'Tiago Pereira')))
