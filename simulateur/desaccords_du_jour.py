#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
desaccords_du_jour.py — chaque matin, la liste PRIVÉE des matchs du jour où l'algo contredit Pinnacle (05/11/2026,
demande de Lucas : des sujets de posts comme Fils – Fritz). LOUPE seulement : les cotes ne sont jamais une entrée de
l'algo et n'apparaissent pas sur le site ; la liste part sur le Telegram privé (TELEGRAM_CHAT_ID) et nulle part ailleurs.

Retenu : match ATP, WTA ou Challenger du jour (heure de Paris), pas commencé, avec une cote Pinnacle (marge retirée),
et soit des favoris opposés (l'algo et Pinnacle ne désignent pas le même favori), soit au moins 10 points d'écart.
Le type de match de l'algo (fiable / standard / fragile) est rappelé : un désaccord sur un match fragile est d'abord
un match très ouvert, pas un avantage. Rien n'est conclu ici : le suivi « qui a raison » est suivi_desaccords_pinnacle.py.
Envoi une seule fois par jour (repère dans le coffre R2, créé seulement s'il n'existe pas), à partir de 7 h à Paris.
Usage : python simulateur/desaccords_du_jour.py . [--telegram]
"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
PARIS = ZoneInfo('Europe/Paris')
ECART_MIN = 0.10
HEURE_MIN = 7


def p_pinnacle(c):
    try:
        a, b = 1 / float(c[0]), 1 / float(c[1])
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError, IndexError):
        return None


def type_match(m, p):
    f = m.get('fiabilite') or {}
    pe, ps = (m.get('stats') or {}).get('p_home'), (m.get('simulation') or {}).get('p_home')
    if f.get('fragile_criteres') or (pe is not None and ps is not None and (pe >= .5) != (ps >= .5)):
        return 'fragile'
    if pe is not None and ps is not None and abs(pe - ps) < .10 and max(p, 1 - p) >= .70:
        return 'fiable'
    return 'standard'


def _utc(s):
    d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def index_pinnacle(closing):
    """{(jour, clé joueur A, clé joueur B) triées: (cle_home, p_home Pinnacle sans marge)} — dernier relevé."""
    import elo as E
    out = {}
    for v in (closing or {}).values():
        h = (v or {}).get('history') or []
        if not h or not v.get('home') or not v.get('away'):
            continue
        q = p_pinnacle((h[-1].get('home'), h[-1].get('away')))
        if q is None:
            continue
        a, b = E.cle(v['home']), E.cle(v['away'])
        jour = str(v.get('commence_time') or v.get('date') or '')[:10]
        out[(jour, *sorted((a, b)))] = (a, q)
    return out


def p_du_match(m, idx):
    """P(home) Pinnacle sans marge : relevés closing_lines (même jour ou veille en UTC), sinon pin_cotes du programme."""
    import elo as E
    h, a = E.cle(m['home']), E.cle(m['away'])
    try:
        j = _utc(m.get('debut_utc') or m.get('debut')).date()
    except ValueError:
        j = None
    for jour in ([j, j - dt.timedelta(days=1), j + dt.timedelta(days=1)] if j else []):
        x = idx.get((jour.isoformat(), *sorted((h, a))))
        if x:
            return x[1] if x[0] == h else 1 - x[1]
    return p_pinnacle(m.get('pin_cotes'))


def lister(doc, maintenant, closing=None):
    jour = maintenant.astimezone(PARIS).date()
    idx = index_pinnacle(closing)
    out = []
    for m in doc.get('matchs') or []:
        p = (m.get('combinaison') or m.get('simulation') or m.get('stats') or {}).get('p_home')
        q = p_du_match(m, idx)
        if p is None or q is None or m.get('circuit') not in ('ATP', 'WTA', 'CH'):
            continue
        try:
            debut = _utc(m.get('debut_utc') or m.get('debut'))
        except ValueError:
            continue
        if debut.astimezone(PARIS).date() != jour or debut <= maintenant:
            continue
        oppose = (p >= .5) != (q >= .5)
        if not (oppose or abs(p - q) >= ECART_MIN):
            continue
        out.append({'heure': debut.astimezone(PARIS).strftime('%H:%M'), 'circuit': m['circuit'], 'tournoi': m.get('tournoi'),
                    'home': m['home'], 'away': m['away'], 'p_algo': p, 'p_pin': q, 'oppose': oppose,
                    'type': type_match(m, p)})
    return sorted(out, key=lambda x: (x['heure'], x['home']))


def message(L, maintenant):
    court = lambda n: str(n).split(' ')[-1]
    jour = maintenant.astimezone(PARIS).strftime('%d/%m')
    if not L:
        return f"<b>🔎 Désaccords algo / Pinnacle — {jour}</b>\nAucun match du jour avec des favoris opposés ou 10 points d'écart."
    T = [f"<b>🔎 Désaccords algo / Pinnacle — {jour}</b> ({len(L)} matchs, cotes = loupe privée)"]
    ic = {'fiable': '🟢', 'standard': '⚪', 'fragile': '🟠'}
    for x in L:
        fa = x['home'] if x['p_algo'] >= .5 else x['away']
        fp = x['home'] if x['p_pin'] >= .5 else x['away']
        pa, pp = max(x['p_algo'], 1 - x['p_algo']), max(x['p_pin'], 1 - x['p_pin'])
        quoi = 'favoris opposés' if x['oppose'] else f"écart {round(100 * abs(x['p_algo'] - x['p_pin']))} pts"
        T.append(f"{ic[x['type']]} {x['heure']} {x['circuit']} · {court(x['home'])} – {court(x['away'])} : "
                 f"algo {court(fa)} {round(100 * pa)} % · Pinnacle {court(fp)} {round(100 * pp)} % ({quoi}, match {x['type']})")
    T.append("🟠 fragile = l'algo lui-même hésite : un match ouvert, pas un avantage. Rien n'est validé avant 30 matchs (CLV).")
    return '\n'.join(T)


def deja_envoye(jour):
    """True si l'envoi du jour a déjà eu lieu ; sinon pose le repère (création seule) et renvoie False."""
    try:
        sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
        import r2_io
        r2 = r2_io.client(quiet=True)
        if r2 is None:
            return None
        try:
            r2.put(f'prive/desaccords_du_jour/{jour}', b'1', create_only=True, content_type='text/plain')
            return False
        except Exception:  # noqa: BLE001 — repère déjà là (ou refus) : déjà envoyé
            return True
    except Exception:  # noqa: BLE001
        return None


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    maintenant = dt.datetime.now(dt.timezone.utc)
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics.json'), encoding='utf-8') as f:
        doc = json.load(f)
    try:                                   # cotes Pinnacle relevées (état chaud) : loupe seulement
        with open(os.path.join(racine, 'closing_lines.json'), encoding='utf-8') as f:
            closing = json.load(f)
    except (OSError, ValueError):
        closing = {}
    txt = message(lister(doc, maintenant, closing), maintenant)
    print(txt.replace('<b>', '').replace('</b>', ''))
    if '--telegram' not in argv:
        return 0
    heure = maintenant.astimezone(PARIS).hour
    if heure < HEURE_MIN and '--forcer' not in argv:
        print('Avant 7 h à Paris : pas d\'envoi.')
        return 0
    deja = deja_envoye(maintenant.astimezone(PARIS).date().isoformat()) if '--forcer' not in argv else False
    if deja or (deja is None and heure != 8):
        print('Désaccords du jour déjà envoyés (ou coffre indisponible hors de 8 h) : pas de doublon.')
        return 0
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if tok and chat:
        import urllib.parse
        import urllib.request
        try:
            from bilan_algo import texte_telegram
            for m in texte_telegram(txt):
                data = urllib.parse.urlencode({'chat_id': chat, 'text': m, 'parse_mode': 'HTML'}).encode()
                urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20).read()
        except Exception as e:  # noqa: BLE001
            print(f'::warning::Telegram impossible ({type(e).__name__})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
