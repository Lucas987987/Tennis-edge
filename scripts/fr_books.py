#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fr_books.py — Résout dynamiquement la liste CAPTURE_BOOKS avec garde-fou France.

Pourquoi : capture_closing demandait 4 books en dur. L'API oddspapi renvoie TOUS
les books dans le MÊME appel (quota par requête, pas par book), donc on peut en
capturer beaucoup plus sans coût supplémentaire — à condition de ne garder que
les books réellement pariables en France.

Garde-fou : on lit le catalogue /bookmakers (1 requête, 1 fois par run) et on ne
retient que les books dont availableCountries contient 'fr' ET qui sont actifs.
Pinnacle (et autres sharps de référence) sont TOUJOURS inclus même s'ils ne sont
pas pariables en FR : ils servent de "fair" de référence, pas de support de pari.

Usage dans capture_closing.py :
    import fr_books
    CAPTURE_BOOKS = fr_books.resolve(os.environ.get('CAPTURE_BOOKS', FALLBACK))
  - CAPTURE_BOOKS=auto      -> liste FR dynamique (1 appel /bookmakers)
  - CAPTURE_BOOKS=pin,uni.. -> valeur telle quelle (comportement actuel inchangé)

Env optionnels :
    CAPTURE_BOOKS_ALWAYS  (def: 'pinnacle')   books toujours inclus, en tête
    CAPTURE_BOOKS_MAX     (def: '25')          plafond de sécurité sur la taille
    CAPTURE_BOOKS_UNKNOWN (def: '0')           1 = inclure aussi les books au drapeau FR inconnu
"""
import os

try:
    import oddspapi_v5 as ov
except Exception:                       # import résilient (tests, autre contexte)
    ov = None

FALLBACK = 'pinnacle,unibet,bwin,betsson'   # repli sûr = comportement historique
ALWAYS   = tuple(s.strip().lower() for s in
                 os.environ.get('CAPTURE_BOOKS_ALWAYS', 'pinnacle').split(',') if s.strip())
MAX_BOOKS = int(os.environ.get('CAPTURE_BOOKS_MAX', '25'))
INCLUDE_UNKNOWN = os.environ.get('CAPTURE_BOOKS_UNKNOWN', '0') == '1'


def _is_fr(b):
    """True si pariable FR, False si exclu FR, None si inconnu (book global)."""
    ac = b.get('availableCountries')
    if isinstance(ac, list):
        return 'fr' in [str(x).lower() for x in ac]
    return None


def fr_bettable_books(catalogue=None):
    """Construit la chaîne 'slug1,slug2,...' : sharps de référence + books FR actifs.
    Repli sur FALLBACK si le catalogue est vide/indisponible (jamais de pipeline cassé)."""
    if catalogue is None:
        if ov is None:
            return FALLBACK
        try:
            catalogue = ov.get_bookmakers('all')
        except Exception as e:
            print(f"  ⚠️ fr_books: catalogue indisponible ({e}) — repli {FALLBACK}")
            return FALLBACK

    fr = []
    for b in catalogue or []:
        slug = (b.get('slug') or '').lower()
        if not slug or b.get('active') is False:
            continue
        infr = _is_fr(b)
        if infr is True or (INCLUDE_UNKNOWN and infr is None):
            fr.append(slug)

    ordered = []
    for s in list(ALWAYS) + sorted(set(fr)):     # sharps d'abord, puis FR triés
        if s and s not in ordered:
            ordered.append(s)

    if len(ordered) <= len(ALWAYS):              # rien de FR détecté -> repli sûr
        return FALLBACK
    return ','.join(ordered[:MAX_BOOKS])


def resolve(env_value):
    """Point d'entrée pour capture_closing : 'auto'/'' -> liste FR dynamique, sinon brut."""
    v = (env_value or '').strip()
    if v.lower() in ('', 'auto', 'fr'):
        return fr_bettable_books()
    return v


if __name__ == '__main__':
    # Test manuel : nécessite RAPIDAPI_KEY pour interroger le vrai catalogue.
    print("CAPTURE_BOOKS auto =>", resolve('auto'))
