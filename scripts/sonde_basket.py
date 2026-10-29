#!/usr/bin/env python3
"""sonde_basket.py — 29/10/2026 : peut-on faire pour le basket (EuroLeague, Betclic Élite) ce qu'on fait au tennis ?

LECTURE SEULE, rien n'est écrit dans le dépôt. Trois questions :
  1. OddsPapi cote-t-il l'EuroLeague et la Betclic Élite ? (2 requêtes au plus : /sports puis /tournaments du basket)
  2. Les données publiques de l'EuroLeague sont-elles accessibles depuis GitHub ? (feuille de match et action par
     action d'un match de 2025-26, résultats d'une saison)
  3. Le site de la LNB répond-il ? (accessibilité seulement)
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
MOTS = ('euro', 'france', 'french', 'lnb', 'elite', 'élite', 'pro a', 'betclic', 'eurocup')
UA = {'User-Agent': 'Mozilla/5.0 (sonde lecture seule)'}


def http(url, n=200000):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(n).decode('utf-8', 'replace')
    except Exception as e:  # noqa: BLE001
        return f'{type(e).__name__}: {e}', ''


def cotes():
    out = {}
    try:
        import oddspapi_v5 as ov
    except Exception as e:  # noqa: BLE001
        return {'erreur': f'import oddspapi_v5 : {e}'}
    sports = ov.get_sports() or []
    basket = [s for s in sports if 'basket' in json.dumps(s).lower()]
    out['sports_basket'] = basket[:5]
    sid = next((s.get('sportId') or s.get('id') for s in basket if isinstance(s, dict)), 11)
    tours = ov.get_tournaments(sid) or []
    out['basket_sport_id'] = sid
    out['tournois_total'] = len(tours)
    out['tournois_retenus'] = [t for t in tours if isinstance(t, dict) and any(m in json.dumps(t, ensure_ascii=False).lower() for m in MOTS)][:40]
    out['requetes'] = ov.REQUETES_RESEAU
    out['quota'] = ov.QUOTA
    return out


def euroleague():
    out = {}
    for nom, url in (('feuille_de_match', 'https://live.euroleague.net/api/Boxscore?gamecode=1&seasoncode=E2025'),
                     ('action_par_action', 'https://live.euroleague.net/api/PlayByPlay?gamecode=1&seasoncode=E2025'),
                     ('tirs', 'https://live.euroleague.net/api/Points?gamecode=1&seasoncode=E2025'),
                     ('resultats_saison', 'https://api-live.euroleague.net/v1/results?seasonCode=E2024')):
        st, txt = http(url)
        d = {'statut': st, 'octets': len(txt), 'debut': txt[:300]}
        try:
            j = json.loads(txt)
            d['cles'] = list(j.keys())[:15] if isinstance(j, dict) else f'liste de {len(j)}'
            if nom == 'action_par_action':
                d['actions'] = sum(len(v) for k, v in j.items() if isinstance(v, list))
            if nom == 'tirs':
                d['tirs'] = len(j.get('Rows') or [])
        except ValueError:
            if nom == 'resultats_saison':
                d['matchs'] = txt.count('<game>')
        out[nom] = d
    return out


def lnb():
    out = {}
    for nom, url in (('site', 'https://www.lnb.fr/'), ('elite', 'https://www.lnb.fr/elite/')):
        st, txt = http(url, 400000)
        out[nom] = {'statut': st, 'octets': len(txt),
                    'api_dans_la_page': sorted({m for m in ('api', 'graphql', 'json', 'sportradar', 'genius', 'fiba') if m in txt.lower()})}
    return out


def main():
    rapport = {'euroleague': euroleague(), 'lnb': lnb(), 'cotes': cotes()}
    print(json.dumps(rapport, ensure_ascii=False, indent=1)[:60000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
