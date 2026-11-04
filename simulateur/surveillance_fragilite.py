#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
surveillance_fragilite.py — chaque semaine (run « Pronostic » du lundi), la fragilité est revérifiée sur NOS pronostics
figés jugés après match (Tennis_Edge_Lab/live/pronostics_resultats.json), 6 dernières semaines (04/11/2026, Lucas).

Mesure d'un groupe : la PENTE d'étalonnage a (réel ~ σ(a · logit p affiché)) ; 1 = nos % se réalisent tels quels.

1. FAVORIS OPPOSÉS (Elo et simulation désignent des favoris différents) — « fragile » d'office depuis le 04/11.
   Justifiée une semaine si, avec au moins 100 matchs dans le groupe, sa pente est inférieure d'au moins 0,10 à celle
   du reste. LEVÉE après deux semaines de suite NON justifiées (avec ≥ 100 matchs) ; une semaine trop pauvre ne
   compte ni pour ni contre. Rétablie après deux semaines justifiées de suite.
2. AUTRES CRITÈRES (connus avant le match, lisibles dans nos fiches) : même favori mais écart Elo / simulation ≥ 10
   points ; un joueur à moins de 30 matchs ; à moins de 60 matchs ; match serré (favori < 58 %) ; gros favori
   (≥ 80 %). Même règle : ENTRE dans la note (fragile d'office) après deux semaines justifiées de suite, SORT après
   deux semaines non justifiées.
3. NOTE V3 : sur les matchs notés en v3, le tiers des notes hautes doit avoir une pente plus proche de 1 ET une erreur
   d'étalonnage plus petite que le tiers bas (au moins 150 matchs) ; sinon ALERTE (Telegram privé) — rien n'est changé
   automatiquement.
Les décisions vont dans simulateur/surveillance_fragilite.json, lu par fiabilite.py.
Usage : python simulateur/surveillance_fragilite.py . [--telegram]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SEMAINES, MIN_N, MIN_V3, ECART = 6, 100, 150, 0.10
SORTIE = os.path.join('simulateur', 'surveillance_fragilite.json')
CRITERES = {
    'favoris_opposes': ("Elo et simulation désignent des favoris différents",
                        lambda r: r['pe'] is not None and r['ps'] is not None and (r['pe'] >= .5) != (r['ps'] >= .5)),
    'ecart_modeles_10': ("même favori, écart Elo / simulation ≥ 10 points",
                         lambda r: r['pe'] is not None and r['ps'] is not None and (r['pe'] >= .5) == (r['ps'] >= .5)
                         and abs(r['pe'] - r['ps']) >= .10),
    'experience_30': ("un joueur à moins de 30 matchs", lambda r: r['xp'] is not None and r['xp'] < 30),
    'experience_60': ("un joueur à moins de 60 matchs", lambda r: r['xp'] is not None and r['xp'] < 60),
    'match_serre': ("match serré (favori < 58 %)", lambda r: max(r['p'], 1 - r['p']) < .58),
    'gros_favori': ("gros favori (≥ 80 %)", lambda r: max(r['p'], 1 - r['p']) >= .80),
}
ACTIF_AU_DEPART = {'favoris_opposes'}         # décision de Lucas du 04/11/2026


def _c(p):
    return min(max(float(p), 1e-6), 1 - 1e-6)


def _lg(p):
    p = _c(p)
    return math.log(p / (1 - p))


def pente(R):
    a = 1.0
    for _ in range(60):
        g = h = 0.0
        for r in R:
            z = _lg(r['p']) if r['y'] else -_lg(r['p'])
            q = 1 / (1 + math.exp(-a * z))
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 0:
            break
        d = g / h
        a -= d
        if abs(d) < 1e-9:
            break
    return a


def erreur_etalonnage(R):
    tot, n = 0.0, 0
    for lo in range(0, 100, 10):
        b = [r for r in R if lo <= 100 * r['p'] < lo + 10]
        if b:
            tot += abs(sum(r['y'] for r in b) - sum(r['p'] for r in b))
            n += len(b)
    return tot / max(1, n)


def lignes(racine, aujourdhui):
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    debut = (aujourdhui - dt.timedelta(weeks=SEMAINES)).isoformat()
    out = []
    for m in doc.get('matchs') or []:
        reel = m.get('reel') or {}
        p = m.get('p_affiche')
        if p is None or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu'):
            continue
        jour = str(m.get('debut') or '')[:10]
        if not jour or jour < debut or jour >= aujourdhui.isoformat():
            continue
        pr = m.get('premier') or {}
        mj = [x for x in (m.get('matchs_joues') or []) if x is not None]
        f_ = m.get('fiabilite') or {}
        out.append({'c': m.get('circuit'), 'p': _c(p), 'y': int(reel['gagnant'] == 'home'),
                    'pe': (pr.get('stats') or {}).get('p_home'), 'ps': (pr.get('simulation') or {}).get('p_home'),
                    'xp': min(mj) if len(mj) == 2 else None, 'note_v3': f_.get('note_v3')})
    return out


def verdict(R, f):
    A = [r for r in R if f(r)]
    B = [r for r in R if not f(r)]
    if len(A) < MIN_N or len(B) < MIN_N:
        return {'matchs': len(A), 'assez': False}
    a, b = pente(A), pente(B)
    return {'matchs': len(A), 'assez': True, 'pente_groupe': round(a, 3), 'pente_reste': round(b, 3),
            'justifie': bool(a <= b - ECART),
            'reussite_groupe_pct': round(100 * sum((r['p'] >= .5) == (r['y'] == 1) for r in A) / len(A), 1)}


def decider(ancien, v, actif_defaut):
    """Hystérésis : deux semaines de suite pour entrer comme pour sortir ; semaine sans assez de matchs neutre."""
    e = dict(ancien or {'actif': actif_defaut, 'serie': 0})
    if not v.get('assez'):
        e['note'] = 'trop peu de matchs : inchangé'
        return e
    contre = (not v['justifie']) if e['actif'] else v['justifie']
    e['serie'] = e.get('serie', 0) + 1 if contre else 0
    if e['serie'] >= 2:
        e['actif'], e['serie'] = not e['actif'], 0
        e['note'] = 'levé : deux semaines non justifiées' if not e['actif'] else 'entré : deux semaines justifiées'
    else:
        e['note'] = (f"{'actif' if e['actif'] else 'inactif'}" + (f" ; {e['serie']}/2 vers le changement" if contre else ''))
    return e


def controle_v3(R):
    N = sorted([r for r in R if r['note_v3'] is not None], key=lambda r: r['note_v3'])
    if len(N) < MIN_V3:
        return {'matchs': len(N), 'assez': False, 'alerte': False}
    k = len(N) // 3
    bas, haut = N[:k], N[2 * k:]
    pb, ph = pente(bas), pente(haut)
    eb, eh = erreur_etalonnage(bas), erreur_etalonnage(haut)
    tient = abs(1 - ph) < abs(1 - pb) and eh < eb
    return {'matchs': len(N), 'assez': True, 'tiers_bas': {'pente': round(pb, 3), 'erreur_pts': round(100 * eb, 2)},
            'tiers_haut': {'pente': round(ph, 3), 'erreur_pts': round(100 * eh, 2)}, 'tient': bool(tient), 'alerte': not tient}


def actifs(racine):
    """Critères de fragilité en vigueur (lu par fiabilite.py). Sans fichier : la décision de départ."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            doc = json.load(f)
        return {k for k, e in (doc.get('decisions') or {}).items() if e.get('actif')}
    except (OSError, ValueError):
        return set(ACTIF_AU_DEPART)


def message(doc):
    L = ['<b>Fragilité — vérification de la semaine</b> (6 dernières semaines)']
    for k, e in doc['decisions'].items():
        v = doc['semaine'][k]
        det = (f"pente {v['pente_groupe']} contre {v['pente_reste']} (reste), {v['matchs']} matchs, "
               f"{v['reussite_groupe_pct']} % de bons vainqueurs") if v.get('assez') else f"{v['matchs']} matchs : trop peu"
        L.append(f"{'🔴' if e['actif'] else '⚪'} {CRITERES[k][0]} — {e['note']} — {det}")
    v3 = doc['note_v3']
    if v3.get('assez'):
        L.append(f"{'⚠️ ALERTE ' if v3['alerte'] else '✅ '}note v3 : tiers haut pente {v3['tiers_haut']['pente']} / "
                 f"{v3['tiers_haut']['erreur_pts']} pt, tiers bas pente {v3['tiers_bas']['pente']} / {v3['tiers_bas']['erreur_pts']} pt")
    else:
        L.append(f"note v3 : {v3['matchs']} matchs notés, contrôle à partir de {MIN_V3}")
    return '\n'.join(L)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    aujourdhui = dt.date.fromisoformat(os.environ['FRAGILITE_JOUR']) if os.environ.get('FRAGILITE_JOUR') else dt.date.today()
    R = lignes(racine, aujourdhui)
    chemin = os.path.join(racine, SORTIE)
    try:
        ancien = json.load(open(chemin, encoding='utf-8'))
    except (OSError, ValueError):
        ancien = {}
    sem = {k: verdict(R, f) for k, (_, f) in CRITERES.items()}
    if ancien.get('jour') == aujourdhui.isoformat():          # relancé le même jour : pas de double comptage
        dec = ancien.get('decisions') or {}
    else:
        dec = {k: decider((ancien.get('decisions') or {}).get(k), sem[k], k in ACTIF_AU_DEPART) for k in CRITERES}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'jour': aujourdhui.isoformat(),
           'regle': ("groupe justifié si pente ≤ reste − 0,10 avec ≥ 100 matchs (6 semaines) ; deux semaines de suite pour "
                     "entrer comme pour sortir ; semaine trop pauvre : inchangé"),
           'matchs': len(R), 'semaine': sem, 'decisions': dec, 'note_v3': controle_v3(R)}
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    txt = message(doc)
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
