#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meilleurs_prix.py — les meilleurs prix du moment pour le côté alerté (21/10/2026).

Étude « délai alerte -> pari » du Lab : le book signalé corrige souvent vite
(H17 : +2,8 % de CLV au prix du message, +0,5 % cinq minutes plus tard sur ce
book), alors que le meilleur AUTRE book tenait encore +5,8 %. Chaque alerte
affiche donc les 3 meilleurs prix disponibles, tous books confondus.

Règles :
  * cote NETTE de commission (bourses : books.effective_odds du Lab) pour le tri ;
  * cote fraîche seulement : dernier point vieux d'au plus AGE_MAX_MIN minutes ;
  * Pinnacle (référence) et flux « données seules » (sbobet, 4casters…) exclus ;
  * bet365 / bet365.fr comptés une fois (le meilleur des deux) ;
  * meilleur book français (ANJ) ajouté s'il n'est pas déjà dans le top.

N'influence AUCUNE règle gelée : affichage seulement. 0 requête API.

Entrée : g = {book: {'h': [(t, cote)], 'a': [(t, cote)]}, ...} — t en datetime
(naïf UTC) ou en secondes epoch, comme dans les h*_signal.py et steam_alert.py.
"""
import datetime as _dt
import importlib.util
import os

AGE_MAX_MIN = float(os.environ.get('PRIX_AGE_MAX_MIN', '30'))
_LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Tennis_Edge_Lab', 'books.py')
_spec = importlib.util.spec_from_file_location('tennis_edge_mp_books', _LAB)
books = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(books)


def _ts(t):
    if isinstance(t, _dt.datetime):
        if t.tzinfo is None:
            t = t.replace(tzinfo=_dt.timezone.utc)
        return t.timestamp()
    return float(t)


def classement(g, side, maintenant=None, age_max_min=AGE_MAX_MIN):
    """[{book, cote, nette, age_min, fr}] trié par cote nette décroissante, un par book canonique."""
    side = {'home': 'h', 'away': 'a'}.get(side, side)
    now = _ts(maintenant) if maintenant is not None else _dt.datetime.now(_dt.timezone.utc).timestamp()
    par_canon = {}
    for b, s in g.items():
        if str(b).startswith('_') or not isinstance(s, dict):
            continue
        f = books.flags(b)
        if not f['jouable'] or f['reference_sharp']:
            continue
        serie = [p for p in (s.get(side) or []) if _ts(p[0]) <= now]
        if not serie:
            continue
        t, cote = serie[-1]
        age = (now - _ts(t)) / 60
        if age > age_max_min or not cote or cote <= 1:
            continue
        it = {'book': f['book'], 'cote': float(cote), 'nette': books.effective_odds(b, float(cote)),
              'age_min': round(age, 1), 'fr': f['jouable_fr']}
        k = books.canonical(b)
        if k not in par_canon or it['nette'] > par_canon[k]['nette']:
            par_canon[k] = it
    return sorted(par_canon.values(), key=lambda x: (-x['nette'], x['book']))


def _fmt(it):
    net = f" (net {it['nette']:.2f})" if abs(it['nette'] - it['cote']) > 1e-9 else ''
    return f"{it['book']} {it['cote']:.2f}{net}"


def ligne(g, side, maintenant=None, n=3):
    """Texte prêt à insérer (sans HTML) ; '' si aucun prix frais."""
    cl = classement(g, side, maintenant)
    if not cl:
        return ''
    top = cl[:n]
    txt = "💶 Meilleurs prix : " + " · ".join(_fmt(x) for x in top)
    if not any(x['fr'] for x in top):
        fr = next((x for x in cl if x['fr']), None)
        if fr:
            txt += f"\n🇫🇷 Meilleur français : {_fmt(fr)}"
    return txt
