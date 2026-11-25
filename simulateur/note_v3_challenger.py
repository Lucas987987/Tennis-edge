#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REMPLACÉ LE 25/11/2026 PAR simulateur/note_par_match.py (paquet 451) : la note Challenger par classe (paquet 450) n'a
jamais tourné ; simulateur/note_v3_challenger.json est marqué « retire ». Gardé pour mémoire ; plus lancé le lundi.

note_v3_challenger.py — GARDE-FOU DE LA NOTE DE FIABILITÉ CHALLENGER RÉAPPRISE (25/11/2026, paquet 450).

En place depuis le 25/11/2026 (décision de Lucas) : en Challenger, la note v3 prend les pentes réapprises sur le rejeu
comme en production (simulateur/note_v3_challenger.json, etude_note_v3_challenger.py). L'ancienne note reste calculée à
côté (fiabilite : note_v3_ancienne, niveau_ancien).

RÈGLE DE RETRAIT (écrite avant la mise en place), chaque lundi : sur nos matchs Challenger terminés notés depuis
l'activation (sans abandon), dès 200 matchs, on compare les deux notes — la nouvelle (fiabilite.note, .niveau) et
l'ancienne (fiabilite.note_ancienne, .niveau_ancien), mêmes critères « fragile », même plafond — sur ce que la note
PROMET (« plus elle est proche de 100, plus nos % sont la réalité ») : pour chaque niveau d'au moins 20 matchs, la note
réelle du niveau, 100 · min(a, 1/a) avec a sa pente d'étalonnage, contre la note moyenne annoncée à ses matchs ; écart
absolu, moyenne pondérée par les matchs du niveau. Si l'écart de la nouvelle dépasse celui de l'ancienne, « retire »
passe à true : l'ancienne note revient au passage suivant. Rien d'autre ne change.

Usage : python simulateur/note_v3_challenger.py . [--telegram]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

FICHIER = os.path.join('simulateur', 'note_v3_challenger.json')
MIN_MATCHS, MIN_NIVEAU = 200, 20
NIVEAUX = ('fragile', 'prudent', 'correct', 'solide')


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def pente(Z):
    a = 1.0
    for _ in range(60):
        g = h = 0.0
        for z in Z:
            q = 1 / (1 + math.exp(-max(min(a * z, 30), -30)))
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 1e-12:
            break
        d = max(min(g / h, 2.0), -2.0)
        a -= d
        if abs(d) < 1e-9:
            break
    return a


def lignes(doc, depuis):
    out = []
    for m in doc.get('matchs') or []:
        fi, reel = m.get('fiabilite') or {}, m.get('reel') or {}
        if (m.get('circuit') != 'CH' or not fi.get('niveau_ancien') or m.get('p_affiche') is None
                or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu')
                or str(m.get('debut') or '')[:10] < depuis):
            continue
        z = _lg(m['p_affiche'])
        if fi.get('note') is None or fi.get('note_ancienne') is None:
            continue
        out.append({'z': z if reel['gagnant'] == 'home' else -z, 'nouveau': fi.get('niveau'), 'ancien': fi['niveau_ancien'],
                    'note_nouveau': float(fi['note']), 'note_ancien': float(fi['note_ancienne'])})
    return out


def ecart(L, cle):
    """Écart entre la note annoncée et la note réelle de chaque niveau (niveaux d'au moins MIN_NIVEAU matchs), moyenne
    pondérée par les matchs. Note réelle d'un niveau = 100 · min(a, 1/a), a = pente d'étalonnage de ses matchs."""
    par, tot, n = {}, 0.0, 0
    for nv in NIVEAUX:
        G = [r for r in L if r[cle] == nv]
        if len(G) >= MIN_NIVEAU:
            a = pente([r['z'] for r in G])
            reelle = 100 * min(a, 1 / a) if a > 0 else 0.0
            annoncee = sum(r['note_' + cle] for r in G) / len(G)
            par[nv] = {'matchs': len(G), 'pente': round(a, 3), 'note_reelle': round(reelle, 1),
                       'note_annoncee': round(annoncee, 1)}
            tot += len(G) * abs(reelle - annoncee)
            n += len(G)
        elif G:
            par[nv] = {'matchs': len(G), 'pente': None}
    return (round(tot / n, 2) if n else None), par


def verifier(racine, aujourdhui=None):
    chemin = os.path.join(racine, FICHIER)
    with open(chemin, encoding='utf-8') as f:
        dec = json.load(f)
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    L = lignes(doc, dec.get('active_le') or '9999')
    e_new, p_new = ecart(L, 'nouveau')
    e_old, p_old = ecart(L, 'ancien')
    ctl = {'jour': (aujourdhui or dt.date.today()).isoformat(), 'matchs': len(L), 'assez': len(L) >= MIN_MATCHS,
           'ecart_nouvelle': e_new, 'ecart_ancienne': e_old, 'niveaux_nouvelle': p_new, 'niveaux_ancienne': p_old}
    if dec.get('retire'):
        ctl['verdict'] = 'déjà retirée'
    elif not ctl['assez'] or e_new is None or e_old is None:
        ctl['verdict'] = f"pas encore jugée (moins de {MIN_MATCHS} matchs)"
    elif e_new > e_old:
        dec['retire'] = True
        dec['retiree_le'] = ctl['jour']
        ctl['verdict'] = 'RETIRÉE : les niveaux de la nouvelle note sont plus loin de la réalité que ceux de l\'ancienne'
    else:
        ctl['verdict'] = 'gardée'
    dec['dernier_controle'] = ctl
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write(json.dumps(dec, ensure_ascii=False, indent=1) + '\n')
    return ctl


def message(ctl):
    return (f"🎯 Note de fiabilité Challenger (paquet 450) — {ctl['matchs']} matchs ; écart note annoncée / note réelle : "
            f"nouvelle {ctl['ecart_nouvelle']}, ancienne {ctl['ecart_ancienne']} — {ctl['verdict']}")


def main(argv):
    racine = argv[1] if len(argv) > 1 and not argv[1].startswith('--') else '.'
    ctl = verifier(racine)
    print(ctl['matchs'], 'matchs ;', ctl['verdict'])
    if '--telegram' in argv:
        try:
            import telegram_envoi as TE
            TE.envoyer(message(ctl))
        except Exception as e:  # noqa: BLE001 — le message ne doit jamais faire échouer le contrôle
            print('telegram :', type(e).__name__)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
