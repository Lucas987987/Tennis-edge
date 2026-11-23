#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_envoi.py — envoi Telegram sûr pour les rapports du simulateur (23/11/2026, paquet 375).

Le 23/11, le message ROI (4 501 caractères) a été refusé par Telegram (limite 4 096 → HTTP 400) et l'étape a fait
sauter la publication du run hebdomadaire. Ici : message coupé entre deux lignes (≤ 4 000 caractères), « < », « > »,
« & » hors balises échappés en HTML (comme bilan_algo.texte_telegram), et un envoi raté ne fait qu'un avertissement
(le code HTTP seul : le journal des runs est public, jamais l'adresse ni le jeton).
"""
import os
import re

LIMITE = 4000
_BALISE = re.compile(r'(</?(?:b|i|u|s|code|pre)>|<a href="[^"<>]*">|</a>|&(?:lt|gt|amp|quot|#\d+);)')


def echapper(texte):
    parts = _BALISE.split(texte or '')
    return ''.join(m if i % 2 else m.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                   for i, m in enumerate(parts))


def morceaux(texte, limite=LIMITE):
    """Coupe entre deux lignes, chaque morceau ≤ limite (une ligne trop longue est coupée net) ; rien n'est perdu."""
    out, cur = [], None
    for ligne in (texte or '').split('\n'):
        while len(ligne) > limite:
            if cur is not None:
                out.append(cur)
                cur = None
            out.append(ligne[:limite])
            ligne = ligne[limite:]
        if cur is None:
            cur = ligne
        elif len(cur) + 1 + len(ligne) > limite:
            out.append(cur)
            cur = ligne
        else:
            cur = cur + '\n' + ligne
    if cur is not None and cur.strip():
        out.append(cur)
    return out


def envoyer(texte, html=False, timeout=20, apercu=False, tok=None, chat=None):
    """Envoie `texte` en un ou plusieurs messages ; renvoie le nombre de messages envoyés (0 sans configuration)."""
    import urllib.parse
    import urllib.request
    tok = tok or os.environ.get('TELEGRAM_TOKEN')
    chat = chat or os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        print('Telegram non configuré : message non envoyé.')
        return 0
    n = 0
    for i, m in enumerate(morceaux(echapper(texte) if html else texte)):
        champs = {'chat_id': chat, 'text': m}
        if html:
            champs['parse_mode'] = 'HTML'
        if not apercu:
            champs['disable_web_page_preview'] = 'true'
        try:
            urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage',
                                   data=urllib.parse.urlencode(champs).encode(), timeout=timeout).read()
            n += 1
        except Exception as e_:  # noqa: BLE001
            print(f"::warning::Telegram : message {i + 1} non envoyé ({getattr(e_, 'code', type(e_).__name__)})")
    return n
