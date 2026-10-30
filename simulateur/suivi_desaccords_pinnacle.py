#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suivi_desaccords_pinnacle.py — quand notre algo s'écarte de Pinnacle, qui a raison ? (30/10/2026, demande de Lucas)

DESCRIPTIF, CANAL PRIVÉ. Rien ne change dans l'algo : les cotes ne servent qu'à comparer, a posteriori.
Pronostics hors échantillon (simulateur/pronostics_hors_echantillon.jsonl.gz : p_algo, vainqueur) reliés à la ligne
Pinnacle du même match (closing_lines : 1er relevé = ouverture, dernier = clôture ; marge retirée). Pour chaque match :
écart = |p_algo − p_clôture| ; « côté de l'algo » = le joueur que l'algo met plus haut que Pinnacle.

Par circuit et par tranche d'écart (0–3, 3–6, 6–10, 10+ points) :
  — le côté de l'algo gagne-t-il plus souvent que Pinnacle ne le disait (réel contre prévu, erreur de mesure) ;
  — log loss de l'algo et de la clôture Pinnacle ;
  — Pinnacle a-t-il bougé vers l'algo ou contre lui entre ouverture et clôture (approche de la CLV) ;
  — rendement du côté de l'algo à la cote juste de clôture (indicatif : cote impossible à obtenir).
Profil suivi à part (30/10/2026, cas Rune – Vacherot) : ATP, écart 6–10 points, algo plus haut que Pinnacle sur
l'OUTSIDER de Pinnacle — 65 matchs au 30/10 : gagne 27,7 % pour 34,1 % donnés par Pinnacle.

Rien avant 30 matchs dans une case. Le rapport reste hors du dépôt (SUIVI_DESACCORDS_SORTIE) : Telegram privé.
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
TRANCHES = ((0.0, 0.03), (0.03, 0.06), (0.06, 0.10), (0.10, 1.01))
CIRCUITS = ('ATP', 'WTA', 'CH')
MIN_N = 30


def _p(pt):
    try:
        a, b = 1 / float(pt['home']), 1 / float(pt['away'])
        return a / (a + b)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def relier(pronos, fiches, closing, cle):
    """[{jour, c, y, pa, po, pc}] : chaque pronostic hors échantillon relié à la ligne Pinnacle du même match."""
    idx = {}
    for v in closing.values():
        H = v.get('history') or []
        if len(H) >= 2 and v.get('home') and v.get('away'):
            idx[(v.get('date'), frozenset((cle(v['home']), cle(v['away']))))] = v
    par_id = {r.get('id'): r for r in fiches}
    out = []
    for x in pronos:
        r = par_id.get(x.get('id'))
        if not r or x.get('p_algo') is None or x.get('gagnant') not in ('home', 'away'):
            continue
        h, a = (cle((r.get(c) or {}).get('nom') or '') for c in ('home', 'away'))
        v = idx.get((x.get('jour'), frozenset((h, a))))
        if not v:
            continue
        po, pc = _p(v['history'][0]), _p(v['history'][-1])
        if po is None or pc is None:
            continue
        if cle(v['home']) != h:
            po, pc = 1 - po, 1 - pc
        out.append({'jour': x['jour'], 'c': x.get('circuit'), 'y': int(x['gagnant'] == 'home'),
                    'pa': float(x['p_algo']), 'po': po, 'pc': pc})
    return out


def _ll(p, y):
    q = p if y else 1 - p
    return -math.log(min(max(q, 1e-9), 1 - 1e-9))


def resumer(R):
    if not R:
        return None
    n = len(R)
    cote_algo = lambda r: r['pa'] > r['pc']                       # l'algo préfère le joueur 1 (home)
    gagne = sum(1 for r in R if (r['y'] == 1) == cote_algo(r))
    prevu = sum((r['pc'] if cote_algo(r) else 1 - r['pc']) for r in R)
    vers = sum(1 for r in R if (r['pc'] - r['po']) * (r['pa'] - r['po']) > 0)
    contre = sum(1 for r in R if (r['pc'] - r['po']) * (r['pa'] - r['po']) < 0)
    rend = sum((1 / (r['pc'] if cote_algo(r) else 1 - r['pc']) if (r['y'] == 1) == cote_algo(r) else 0) - 1 for r in R) / n
    q = prevu / n
    return {'matchs': n, 'cote_algo_gagne_pct': round(100 * gagne / n, 1), 'pinnacle_donnait_pct': round(100 * q, 1),
            'ecart_pts': round(100 * (gagne - prevu) / n, 1), 'erreur_pts': round(100 * math.sqrt(q * (1 - q) / n), 1),
            'log_loss_algo': round(sum(_ll(r['pa'], r['y']) for r in R) / n, 4),
            'log_loss_pinnacle': round(sum(_ll(r['pc'], r['y']) for r in R) / n, 4),
            'pinnacle_vers_algo': vers, 'pinnacle_contre_algo': contre,
            'rendement_cloture_juste_pct': round(100 * rend, 1), 'conclusion_possible': n >= MIN_N}


def outsider_soutenu(r):
    """L'algo met plus haut que Pinnacle le joueur que Pinnacle donne perdant."""
    return (r['pa'] > r['pc'] and r['pc'] < 0.5) or (r['pa'] < r['pc'] and r['pc'] > 0.5)


def etudier(rows, depuis_semaines=None, maintenant=None):
    if depuis_semaines:
        lim = ((maintenant or dt.date.today()) - dt.timedelta(weeks=depuis_semaines)).isoformat()
        rows = [r for r in rows if r['jour'] >= lim]
    out = {}
    for c in ('TOUS',) + CIRCUITS:
        Rc = [r for r in rows if c == 'TOUS' or r['c'] == c]
        out[c] = {f"{int(100 * lo)}-{int(100 * hi) if hi < 1 else '+'}": resumer([r for r in Rc if lo <= abs(r['pa'] - r['pc']) < hi])
                  for lo, hi in TRANCHES}
    out['profil_atp_outsider_6_10'] = resumer([r for r in rows if r['c'] == 'ATP' and 0.06 <= abs(r['pa'] - r['pc']) < 0.10
                                                and outsider_soutenu(r)])
    return out


def message(doc):
    L = ['<b>Désaccords algo / Pinnacle</b> (descriptif, rien ne change dans l’algo)',
         f"{doc['sources']['matchs']} matchs reliés · réel du côté de l’algo contre ce que donnait Pinnacle"]
    for c in ('ATP', 'WTA', 'CH'):
        L.append(f'\n<b>{c}</b>')
        for t, r in doc['total'][c].items():
            if not r:
                continue
            L.append(f"{t} pts : {r['matchs']} m · {r['cote_algo_gagne_pct']} % / {r['pinnacle_donnait_pct']} % "
                     f"({r['ecart_pts']:+.1f} ± {r['erreur_pts']}) · Pinnacle vers nous {r['pinnacle_vers_algo']}, "
                     f"contre {r['pinnacle_contre_algo']}" + ('' if r['conclusion_possible'] else ' · &lt; 30'))
    p = doc['total'].get('profil_atp_outsider_6_10')
    if p:
        L.append(f"\n<b>Profil ATP, outsider soutenu, 6–10 pts</b> : {p['matchs']} m · {p['cote_algo_gagne_pct']} % "
                 f"/ {p['pinnacle_donnait_pct']} % ({p['ecart_pts']:+.1f} ± {p['erreur_pts']})")
    r4 = (doc.get('quatre_semaines') or {}).get('TOUS') or {}
    gros = r4.get('10-+')
    if gros:
        L.append(f"4 dernières semaines, écart 10+ pts (tous) : {gros['matchs']} m · {gros['ecart_pts']:+.1f} pts")
    return '\n'.join(L)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    import elo as E
    import feuilles as FE
    import closing_store as CS
    try:
        with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
            pronos = [json.loads(l) for l in f if l.strip()]
    except OSError:
        pronos = []
    closing = CS.load_all(os.path.join(racine, 'closing_lines.json'), max_age_days=None)
    rows = relier(pronos, FE.lire(racine), closing, E.cle)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'sources': {'pronostics': len(pronos), 'matchs': len(rows)},
           'total': etudier(rows), 'quatre_semaines': etudier(rows, 4)}
    sortie = os.environ.get('SUIVI_DESACCORDS_SORTIE') or os.path.join(racine, 'simulateur', 'suivi_desaccords_pinnacle.json')
    with open(sortie, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(message(doc).replace('<b>', '').replace('</b>', '').replace('&lt;', '<'))
    if '--telegram' in argv:
        import urllib.parse
        import urllib.request
        tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
        if tok and chat:
            try:
                data = urllib.parse.urlencode({'chat_id': chat, 'text': message(doc), 'parse_mode': 'HTML'}).encode()
                urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20).read()
                print('Désaccords algo / Pinnacle : envoyés sur le Telegram privé.')
            except Exception as e:  # noqa: BLE001
                print(f'::warning::Telegram impossible ({type(e).__name__})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
