# -*- coding: utf-8 -*-
"""IndexNow (25/11/2026, paquet 444) : à chaque publication, signaler à Bing (et Yandex, Seznam, Naver…) les pages
du site nouvelles ou modifiées, pour qu'elles soient indexées en quelques heures au lieu de quelques jours.
Google n'utilise pas IndexNow : pour lui, le plan du site (sitemap.xml) suffit.

  · la liste vient de publier_r2.py (--urls-indexnow) : seulement les pages HTML publiques réellement envoyées ;
  · la clé n'est pas un secret (le protocole la publie) : le worker la sert à https://gamesetalgo.com/<CLE>.txt ;
  · 10 000 adresses au plus par envoi ; un échec ne bloque jamais la publication.
Journal public des Actions : seulement des nombres et des codes HTTP.

Usage : python scripts/indexnow.py <fichier d'adresses>
"""
import json
import re
import sys
import urllib.request

CLE = '46bbd636fd3b0fc7e291244e36a79d7b'
HOTE = 'gamesetalgo.com'
SITE = 'https://' + HOTE
LOT = 10000
_PAGES = re.compile(r'^algo/(?:(en)/)?(?:(match|joueur|tournoi|bilan)/([^/]+)\.html|(matchs|joueurs|tournois|bilans)\.html)$')


def url_de(rel):
    """Chemin relatif de _site → adresse publique, ou None si ce n'est pas une page à signaler."""
    rel = rel.replace('\\', '/').lstrip('/')
    if rel == 'algo/index.html':
        return SITE + '/'
    if rel in ('algo/apropos.html', 'algo/methode.html'):
        return SITE + '/' + rel[len('algo/'):]
    m = _PAGES.match(rel)
    if not m:
        return None
    en, quoi, nom, index = m.groups()
    chemin = f"/{quoi}/{nom}" if quoi else f"/{index}"
    return SITE + ('/en' if en else '') + chemin


def envoyer(urls, poster=None):
    """→ liste des codes HTTP (un par lot)."""
    urls = sorted(set(u for u in urls if u))
    codes = []
    for i in range(0, len(urls), LOT):
        corps = json.dumps({'host': HOTE, 'key': CLE, 'keyLocation': f'{SITE}/{CLE}.txt', 'urlList': urls[i:i + LOT]}).encode()
        if poster:
            codes.append(poster(corps))
            continue
        req = urllib.request.Request('https://api.indexnow.org/indexnow', data=corps,
                                     headers={'Content-Type': 'application/json; charset=utf-8'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                codes.append(r.status)
        except urllib.error.HTTPError as e:
            codes.append(e.code)
        except Exception:
            codes.append(0)
    return codes


def main(argv):
    try:
        with open(argv[1], encoding='utf-8') as f:
            urls = [x.strip() for x in f if x.strip()]
    except (OSError, IndexError):
        print('IndexNow : aucune liste, rien à signaler.')
        return 0
    if not urls:
        print('IndexNow : aucune page nouvelle ou modifiée.')
        return 0
    codes = envoyer(urls)
    print(f"IndexNow : {len(set(urls))} adresse(s) signalée(s) · réponses {codes}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
