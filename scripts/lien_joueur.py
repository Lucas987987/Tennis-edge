#!/usr/bin/env python3
"""lien_joueur.py — transforme un nom de joueur en lien vers sa fiche.

À IMPORTER depuis les scripts d'alerte (Telegram, X). Aucun appel réseau,
aucune table de correspondance : le lien se calcule à partir du nom seul.

    from lien_joueur import ligne_fiches, lien, slug

    msg += "\\n" + ligne_fiches(steame, opp)

POURQUOI LES TOKENS SONT TRIÉS
------------------------------
Le slug doit être identique des deux côtés — ici, dans worker-joueurs.js,
et dans la clé de players_profile.json. Les trois sources de noms du dépôt
n'écrivent pas dans le même ordre :

    moves_detail_hist  « Mattia Bellucci »
    player_form        « bellucci mattia »

Trier les tokens absorbe l'inversion. Sans le tri, un lien sur deux
pointait dans le vide, et c'est exactement le genre de panne qu'on ne voit
pas : le message part, le lien existe, il tombe sur « joueur inconnu ».

La contrepartie est que le slug ne se lit pas comme un nom
(`bellucci-mattia`, pas `mattia-bellucci`). C'est le prix d'un lien qui
marche à tous les coups, et personne ne lit les URL d'une alerte.

UNE SEULE LIGNE, PAS UN LIEN PAR NOM
------------------------------------
L'alerte nomme deux joueurs. Plutôt que deux liens dans le texte — qui
coûtent des caractères sur X et alourdissent Telegram — on ajoute une
ligne qui pointe vers leur COMPARAISON. La page porte les deux fiches, le
face-à-face, et un lien vers chaque fiche complète. Un lien au lieu de
deux, et il en dit plus que les deux.
"""

import os
import re
import unicodedata

# Domaine du worker public. À régler une fois dans les variables
# d'environnement du workflow, pas dans chaque script.
BASE = os.environ.get('FICHES_BASE',
                      'https://tennis-edge-index.antoine-galopinpro.workers.dev')


def slug(nom):
    """Tokens du nom : sans accent, minuscules, TRIÉS, joints par un tiret.

    Doit rester l'image exacte de slug() dans worker-joueurs.js et de
    cle() dans build_profiles.py. Les trois changent ensemble ou aucune.
    """
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode()
    toks = [t for t in re.split(r'[^A-Za-z]+', s.lower()) if len(t) > 1]
    return '-'.join(sorted(toks))


def lien(nom):
    """Lien vers la fiche d'un joueur."""
    s = slug(nom)
    return f'{BASE}/j/{s}' if s else BASE + '/j'


def lien_duo(a, b):
    """Lien vers la comparaison de deux joueurs, sur la même échelle."""
    sa, sb = slug(a), slug(b)
    if not sa:
        return lien(b)
    if not sb:
        return lien(a)
    return f'{BASE}/j/{sa}/{sb}'


def ligne_fiches(a, b=None, prefixe='Fiches'):
    """La ligne à coller en bas d'une alerte.

    Telegram et X affichent tous deux le lien nu correctement ; pas de
    balisage, donc rien à échapper et aucun risque d'erreur de parse_mode.
    """
    return f'{prefixe} : {lien_duo(a, b) if b else lien(a)}'


if __name__ == '__main__':
    # Vérification croisée : les deux ordres doivent donner le même slug.
    for a, b in (('Mattia Bellucci', 'bellucci mattia'),
                 ('Félix Auger-Aliassime', 'auger aliassime felix'),
                 ('Aryna Sabalenka', 'sabalenka aryna')):
        assert slug(a) == slug(b), (a, b, slug(a), slug(b))
    print(slug('Mattia Bellucci'))
    print(ligne_fiches('Aryna Sabalenka', 'Linda Noskova'))
