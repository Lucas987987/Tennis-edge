#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tableau_adoptions.py — chaque lundi, UN message pour tout ce qui a été adopté DIRECTEMENT, sans période de fantôme
(05/11/2026, demande de Lucas) : signaux combinés et parcours dans le tournoi (fantomes_circuits.json), tie-breaks du
Challenger (idem), recalage des statistiques annoncées (recalage_stats.json, cases directes). Pour chacun, par circuit :
gain réel de la semaine jugée et depuis le début, état — ✅ en place · ⚠️ une semaine pire (retiré à la deuxième) ·
❌ retiré. Ne décide rien : les règles de retrait restent dans fantomes_circuits.py et recalage_stats.py, qui tournent
AVANT dans le même workflow. Usage : python simulateur/tableau_adoptions.py . [--telegram]
"""
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
NOMS = {'changement_surface': 'changement de surface', 'retour_absence': "retour d'absence", 'age': 'âge',
        'favori_outsider': 'profil favori / outsider', 'parcours_tournoi': 'parcours dans le tournoi',
        'tiebreak': 'tie-breaks (ligne)', 'documentation_faible': 'matchs peu documentés (< 500 balles)', 'montee_petits_tournois': 'montée des petits tournois'}
STATS = {'premiere_pct': '% de 1res balles', 'aces': 'aces', 'doubles_fautes': 'doubles fautes', 'breaks': 'breaks'}


def _lire(racine, nom):
    try:
        with open(os.path.join(racine, 'simulateur', nom), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def lignes(racine):
    import fantomes_circuits as FC
    fc, rs = _lire(racine, 'fantomes_circuits.json'), _lire(racine, 'recalage_stats.json')
    dec, sem = fc.get('decisions') or {}, fc.get('semaine') or {}
    out = []
    for sgn, c in sorted(FC.directs(racine)):
        cle = f'{sgn}|{c}'
        d, v = dec.get(cle) or {}, sem.get(cle) or {}
        if d.get('retire'):
            etat = '❌ retiré'
        elif (d.get('stabilite') or '').startswith('1/2') or (v.get('matchs_semaine', 0) >= FC.MIN_MATCHS
                                                                 and (v.get('gain_semaine') or 0) <= -FC.MARGE):
            etat = '⚠️ une semaine pire'
        else:
            etat = '✅ en place'
        out.append({'quoi': NOMS.get(sgn, sgn), 'circuit': c, 'etat': etat,
                    'detail': (f"semaine {v.get('matchs_semaine', 0)} m. ({v.get('gain_semaine')}), depuis le début "
                               f"{v.get('matchs_total', 0)} m. ({v.get('gain_total')})") if v else 'pas encore de match jugé'})
    import recalage_stats as RS
    di = rs.get('direct') or {}
    for c, k in RS.CASES_DIRECTES:
        x = di.get(f'{c}|{k}') or {}
        etat = '❌ retiré' if x.get('retire') else '⚠️ une semaine pire' if x.get('semaines_pires') else '✅ en place'
        det = (f"écart moyen semaine : sans {x['ecart_sans']} → avec {x['ecart_avec']} ({x.get('cas_semaine')} cas)"
               if x.get('ecart_avec') is not None else (x.get('note') or 'pas encore jugé'))
        out.append({'quoi': f"recalage {STATS.get(k, k)}", 'circuit': c, 'etat': etat, 'detail': det})
    return out


def message(L):
    T = ['<b>Adoptions directes — état de la semaine</b> (gain = log loss sans − avec ; positif = mieux)']
    for x in L:
        T.append(f"{x['etat']} · {x['circuit']} · {x['quoi']} — {x['detail']}")
    if not L:
        T.append('Aucune adoption directe en place.')
    return '\n'.join(T)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    txt = message(lignes(racine))
    print(txt.replace('<b>', '').replace('</b>', ''))
    if '--telegram' in argv:
        import urllib.parse
        import urllib.request
        tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
        if tok and chat:
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
