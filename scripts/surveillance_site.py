# -*- coding: utf-8 -*-
"""Surveillance de gamesetalgo.com (25/11/2026, paquet 435, avant l'ouverture du site).

Toutes les 10 minutes (workflow surveillance_site.yml) : la page d'accueil répond et contient « Game Set Algo », et le
worker répond sur /live/termines (lu dans R2, jamais d'appel TennisApi ; /site.json n'est pas lu pour ne pas
compter de fausses visites). Chaque vérification est retentée une fois après 20 s (petites coupures ignorées).

Telegram privé : UN message quand le site tombe (le run précédent était bon), UN quand il revient — pas toutes les
10 minutes. Le run finit en échec tant que le site est en panne : c'est ce qui sert d'état d'un run à l'autre.
Journal public des Actions : seulement les codes HTTP et les durées, jamais de secret.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

SITE = 'https://gamesetalgo.com'
VERIFS = [
    ('accueil', SITE + '/', lambda corps: 'Game Set Algo' in corps),
    ('worker', SITE + '/live/termines', lambda corps: isinstance(json.loads(corps), dict)),
]
ENTETES = {'User-Agent': 'GameSetAlgo-surveillance/1.0', 'Accept': 'text/html,application/json'}


def lire(url, delai=20):
    req = urllib.request.Request(url, headers=ENTETES)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            return r.status, r.read().decode('utf-8', 'replace'), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, '', time.time() - t0
    except Exception as e:  # réseau, délai dépassé
        return 0, type(e).__name__, time.time() - t0


def verifier(lecteur=lire, pause=time.sleep):
    """→ liste des problèmes (vide si tout va bien)."""
    pbs = []
    for nom, url, test in VERIFS:
        for essai in (1, 2):
            code, corps, duree = lecteur(url)
            try:
                bon = code == 200 and test(corps)
            except Exception:
                bon = False
            print(f'{nom} : HTTP {code} en {duree:.1f} s' + ('' if bon else ' — KO'))
            if bon:
                break
            if essai == 1:
                pause(20)
        else:
            pbs.append(f'{nom} : HTTP {code}' if code else f'{nom} : {corps or "pas de réponse"}')
    return pbs


def run_precedent_en_echec():
    """Conclusion du dernier run TERMINÉ de ce workflow (le run en cours n'est pas terminé)."""
    depot, jeton = os.environ.get('GITHUB_REPOSITORY'), os.environ.get('GITHUB_TOKEN')
    if not depot or not jeton:
        return None
    url = f'https://api.github.com/repos/{depot}/actions/workflows/surveillance_site.yml/runs?status=completed&per_page=1'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {jeton}', 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            runs = json.load(r).get('workflow_runs') or []
        return runs[0].get('conclusion') == 'failure' if runs else False
    except Exception:
        return None


def message(pbs, avant_ko):
    """Texte Telegram à envoyer, ou None (pas de changement d'état)."""
    if pbs and avant_ko is not True:
        return '🔴 gamesetalgo.com ne répond plus correctement\n' + '\n'.join('• ' + p for p in pbs)
    if not pbs and avant_ko is True:
        return '🟢 gamesetalgo.com répond de nouveau normalement.'
    return None


def telegram(texte):
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        print('Telegram non configuré : message non envoyé.')
        return False
    data = json.dumps({'chat_id': chat, 'text': texte, 'disable_web_page_preview': True}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendMessage', data=data,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print('Telegram : envoyé' if r.status == 200 else f'Telegram : HTTP {r.status}')
            return r.status == 200
    except Exception as e:
        print('Telegram : échec (' + type(e).__name__ + ')')
        return False


def main():
    pbs = verifier()
    texte = message(pbs, run_precedent_en_echec())
    if texte:
        telegram(texte)
    print('Site : en panne' if pbs else 'Site : OK')
    return 1 if pbs else 0


if __name__ == '__main__':
    sys.exit(main())
