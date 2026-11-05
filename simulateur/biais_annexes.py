#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
biais_annexes.py — où nos prévisions annexes se trompent, circuit par circuit, recalculé chaque semaine sur nos
6 dernières semaines (05/11/2026, demande de Lucas : « une information sur la fiche des matchs pour prendre en compte
les erreurs potentielles »). Rien n'est corrigé ici : on SIGNALE (simulateur/biais_annexes.json, lu par vitrine.py →
bloc « Points de vigilance » de chaque fiche). Les corrections passent par leurs études (recalage_stats.py, etc.).

Statistiques par joueur (fiches jugées, pronostics_resultats.json : prévu, fourchette 80 %, réel) — signalée sur un
circuit si au moins 200 valeurs ET (part dans la fourchette < 75 % ou > 85 %, OU biais moyen à au moins 2 erreurs
types de zéro et d'au moins 0,3 en valeur absolue — points pour les %, unités pour les compteurs).
Lignes (bilans après match : tie-break, set décisif, 1er set du joueur cité en premier, totaux de jeux, handicaps)
— signalée si au moins 80 matchs, écart réel − prévu d'au moins 3 points et z ≥ 2.
Usage : python simulateur/biais_annexes.py . [--telegram]
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
SEMAINES = 6
MIN_STAT, MIN_LIGNE = 200, 80
SORTIE = os.path.join('simulateur', 'biais_annexes.json')
STATS = ('aces', 'doubles_fautes', 'breaks', 'premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct', 'jeux')
# 05/11/2026 : « 1er set du joueur cité en premier » retiré : sur 4 698 fiches, ce joueur gagne le 1er set 51,3 % du temps
# (et le match 52,1 %) ; l'écart vu sur nos 443 matchs suivait leur part de victoires (53 %) — du hasard d'échantillon.
# Ce qui compte vraiment pour le 1er set, c'est le PREMIER SERVEUR (57,0 % des 1ers sets), inconnu avant le match.
LIGNES = ('tie_break', 'set_decisif', 'total_plus_18.5', 'total_plus_19.5', 'total_plus_20.5',
          'total_plus_21.5', 'total_plus_22.5', 'total_plus_23.5', 'handicap_favori_1.5', 'handicap_favori_2.5',
          'handicap_favori_3.5', 'handicap_favori_4.5', 'handicap_favori_5.5')


def stats_circuit(M):
    out = {}
    for st in STATS:
        v = [x for m in M for x in ((m['diagnostic']['stats'].get(st) or {}).get('home'),
                                    (m['diagnostic']['stats'].get(st) or {}).get('away'))
             if x and x.get('reel') is not None and x.get('prevu') is not None]
        n = len(v)
        if n < MIN_STAT:
            continue
        e = [x['reel'] - x['prevu'] for x in v]
        b = sum(e) / n
        se = math.sqrt(sum((y - b) ** 2 for y in e) / max(1, n - 1) / n)
        cov = 100 * sum(bool(x.get('dans')) for x in v) / n
        signal = cov < 75 or cov > 85 or (abs(b) >= 0.3 and abs(b) >= 2 * se)
        out[st] = {'valeurs': n, 'dans_fourchette_pct': round(cov, 1), 'biais': round(b, 2), 'signal': bool(signal),
                   'sens': ('sous-estimé' if b > 0 else 'surestimé') if abs(b) >= 0.3 and abs(b) >= 2 * se else None,
                   'fourchette': 'trop étroite' if cov < 75 else 'trop large' if cov > 85 else None}
    return out


def lignes_circuit(B):
    out = {}
    for k in LIGNES:
        v = [(b['ecarts']['lignes'][k]) for b in B if ((b.get('ecarts') or {}).get('lignes') or {}).get(k)]
        v = [x for x in v if x and x[0] is not None]
        n = len(v)
        if n < MIN_LIGNE:
            continue
        pm, r = sum(x[0] for x in v) / n, sum(bool(x[1]) for x in v) / n
        z = (r - pm) / math.sqrt(max(pm * (1 - pm), 1e-6) / n)
        out[k] = {'matchs': n, 'prevu_pct': round(100 * pm, 1), 'reel_pct': round(100 * r, 1), 'z': round(z, 2),
                  'signal': bool(abs(r - pm) >= 0.03 and abs(z) >= 2)}
    return out


def calculer(racine, aujourdhui):
    debut = (aujourdhui - dt.timedelta(weeks=SEMAINES)).isoformat()
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    M = [m for m in doc.get('matchs') or [] if m.get('diagnostic') and (m['diagnostic'].get('stats'))
         and str(m.get('debut'))[:10] >= debut and not (m.get('reel') or {}).get('interrompu')]
    B = []
    for chemin in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', 'apres_match', '*.json.gz'))):
        if os.path.basename(chemin)[:10] < debut:
            continue
        try:
            B.extend(json.load(gzip.open(chemin, 'rt', encoding='utf-8')).values())
        except (OSError, ValueError):
            continue
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        out[c] = {'stats': stats_circuit([m for m in M if m.get('circuit') == c]),
                  'lignes': lignes_circuit([b for b in B if b.get('circuit') == c])}
    out['tous'] = {'stats': {}, 'lignes': lignes_circuit(B)}      # lignes : repli tous circuits confondus
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'depuis': debut,
            'matchs_stats': len(M), 'matchs_lignes': len(B),
            'regle': ("stat signalée : ≥ 200 valeurs et part dans la fourchette 80 % hors 75–85 %, ou biais net (≥ 0,3 et "
                      "≥ 2 erreurs types) ; ligne signalée : ≥ 80 matchs, |réel − prévu| ≥ 3 points et |z| ≥ 2"),
            'circuits': out}


def vigilance(doc, circuit, matchs_joues=None, tour=None):
    """Liste de points de vigilance pour un match (codes + chiffres ; le site écrit les phrases en FR / EN)."""
    C = (doc or {}).get('circuits') or {}
    c = C.get(circuit) or {}
    out = []
    for st, v in (c.get('stats') or {}).items():
        # sur la fiche : seulement ce qui peut surprendre — un biais d'au moins 0,5 ou une fourchette trop étroite
        if v.get('signal') and ((v.get('sens') and abs(v['biais']) >= 0.5) or v.get('fourchette') == 'trop étroite'):
            out.append({'type': 'stat', 'cle': st, 'sens': v.get('sens'), 'biais': v['biais'],
                        'fourchette': v.get('fourchette'), 'dans_pct': v['dans_fourchette_pct']})
    vus = set()
    for portee, bloc in ((circuit, c), ('tous', C.get('tous') or {})):
        for k, v in (bloc.get('lignes') or {}).items():
            if v.get('signal') and k not in vus:
                vus.add(k)
                out.append({'type': 'ligne', 'cle': k, 'prevu': v['prevu_pct'], 'reel': v['reel_pct'],
                            'portee': 'circuit' if portee == circuit else 'tous'})
    mj = [x for x in (matchs_joues or []) if x is not None]
    if len(mj) == 2 and min(mj) < 100:
        out.append({'type': 'experience'})            # fourchettes du service moins sûres (69–70 % au lieu de 78–81 %)
    return out


def message(doc):
    L = [f"<b>Prévisions annexes — biais des 6 dernières semaines</b> ({doc['matchs_stats']} matchs, {doc['matchs_lignes']} pour les lignes)"]
    for c, v in doc['circuits'].items():
        s = [f"{k} {x['biais']:+} ({x['dans_fourchette_pct']} % dans la fourchette)" for k, x in (v.get('stats') or {}).items() if x['signal']]
        l_ = [f"{k} {x['prevu_pct']} → {x['reel_pct']} %" for k, x in v['lignes'].items() if x['signal']]
        L.append(f"{c} : " + ('; '.join(s + l_) if s or l_ else 'rien à signaler'))
    return '\n'.join(L)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    aujourdhui = dt.date.fromisoformat(os.environ['BIAIS_JOUR']) if os.environ.get('BIAIS_JOUR') else dt.date.today()
    doc = calculer(racine, aujourdhui)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
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
