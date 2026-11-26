#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suivi_pente_sous_500.py — FANTÔME « PENTE SOUS 500 POINTS » EN CHALLENGER, suivi sur nos matchs publiés (26/11/2026,
paquet 466, accord de Lucas). Le % affiché ne change pas.

Origine : étude 465 (simulateur/etude_pente_melange.py). En Challenger, quand le joueur le moins vu a moins de 500 points
de service au jour du match, nos % du rejeu restent trop timides MÊME APRÈS la pente 1,11 en place (paquet 453) :
pente 1,174 apprise sur 01/2025 → 05/2026, gain jugé sur 06–12/2024 +0,0070 ± 0,0019 (1 018 matchs), mais le sens
inverse ne tient pas (pente 1,40 apprise sur 2024, −0,0010 ± 0,0034 sur 2025–2026) : non retenue. Le rejeu n'a ni les
couches du lundi ni les autres corrections : seule la vérification sur nos matchs PUBLIÉS peut trancher.

Ce suivi : pour chaque Challenger terminé, sans abandon, dont le joueur le moins vu avait moins de 500 points au moment
du pronostic (balles_min, enregistré depuis le paquet 368), log loss du % publié contre le même étiré :
p' = σ(PENTE_EN_PLUS · logit p), soit environ 1,30 au total avec la pente 1,11 déjà en place.

RÈGLE FIXÉE AVANT TOUT RÉSULTAT (26/11/2026) — le candidat est PROPOSÉ à Lucas (jamais appliqué automatiquement) si :
  au moins MIN_MATCHS (1 000) matchs concernés ; gain de log loss ≥ MARGE (0,001) par match ; gain − 2 erreurs types
  > 0 ; gain > 0 sur chacune des deux moitiés chronologiques.
En plus, à titre descriptif : la pente de nos % publiés par circuit et par tranche de documentation (moins de 500,
500–1 500, 1 500–3 000, 3 000 et plus), avec la documentation comptée au jour du match.

Sortie : simulateur/suivi_pente_sous_500.json (comptes et moyennes, aucun nom). Telegram privé avec --telegram.
Usage : python simulateur/suivi_pente_sous_500.py [racine] [--telegram]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

PENTE_EN_PLUS = 1.174
SEUIL = 500
MIN_MATCHS, MARGE = 1000, 0.001
TRANCHES = ((0, 500, 'moins de 500'), (500, 1500, '500 à 1 500'), (1500, 3000, '1 500 à 3 000'),
            (3000, 10 ** 12, '3 000 et plus'))
CIRCUITS = ('ATP', 'WTA', 'CH')
SORTIE = os.path.join('simulateur', 'suivi_pente_sous_500.json')
MIN_PENTE = 30


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(u):
    return 1 / (1 + math.exp(-u)) if u >= 0 else math.exp(u) / (1 + math.exp(u))


def _ll(p, y):
    q = p if y else 1 - p
    return -math.log(min(max(q, 1e-12), 1.0))


def lignes(doc):
    """Matchs terminés, sans abandon, avec % publié et documentation au jour du match, dans l'ordre chronologique."""
    out = []
    for m in (doc or {}).get('matchs') or []:
        reel = m.get('reel') or {}
        if (m.get('circuit') not in CIRCUITS or m.get('p_affiche') is None or m.get('balles_min') is None
                or reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away')):
            continue
        out.append({'c': m['circuit'], 'p': float(m['p_affiche']), 'y': int(reel['gagnant'] == 'home'),
                    'b': int(m['balles_min']), 'd': str(m.get('debut') or '')})
    out.sort(key=lambda r: r['d'])
    return out


def pente(L):
    """Pente d'étalonnage a (σ(a · logit p)) et son erreur type, ou (None, None)."""
    Z = [(_lg(r['p']) if r['y'] else -_lg(r['p'])) for r in L]
    if len(Z) < MIN_PENTE:
        return None, None
    a = 1.0
    for _ in range(60):
        g = h = 0.0
        for z in Z:
            q = _sg(a * z)
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 1e-12:
            return None, None
        d = max(min(g / h, 2.0), -2.0)
        a -= d
        if abs(d) < 1e-9:
            break
    h = sum(_sg(a * z) * (1 - _sg(a * z)) * z * z for z in Z)
    return round(a, 3), (round(1 / math.sqrt(h), 3) if h > 0 else None)


def gains(L, k=PENTE_EN_PLUS):
    return [_ll(r['p'], r['y']) - _ll(_sg(k * _lg(r['p'])), r['y']) for r in L]


def _moy_et(G):
    n = len(G)
    if not n:
        return None, None
    m = sum(G) / n
    v = sum((g - m) ** 2 for g in G) / (n - 1) if n > 1 else 0.0
    return round(m, 5), round(math.sqrt(v / n), 5)


def candidat(L):
    C = [r for r in L if r['c'] == 'CH' and r['b'] < SEUIL]
    G = gains(C)
    g, et = _moy_et(G)
    h = len(G) // 2
    g1, _ = _moy_et(G[:h])
    g2, _ = _moy_et(G[h:])
    ok = bool(len(G) >= MIN_MATCHS and g is not None and g >= MARGE and et is not None and g - 2 * et > 0
              and g1 is not None and g2 is not None and g1 > 0 and g2 > 0)
    a, a_et = pente(C)
    return {'matchs': len(G), 'pente_en_plus': PENTE_EN_PLUS, 'gain_log_loss': g, 'erreur_type': et,
            'gain_1re_moitie': g1, 'gain_2de_moitie': g2, 'pente_du_publie': a, 'pente_erreur_type': a_et,
            'a_proposer': ok,
            'regle': (f"proposé à Lucas (jamais appliqué automatiquement) si ≥ {MIN_MATCHS} matchs, gain ≥ {MARGE}, "
                      "gain − 2 erreurs types > 0 et gain > 0 sur les deux moitiés")}


def par_tranche(L):
    out = {}
    for c in CIRCUITS:
        out[c] = {}
        for lo, hi, nom in TRANCHES:
            G = [r for r in L if r['c'] == c and lo <= r['b'] < hi]
            a, et = pente(G)
            out[c][nom] = {'matchs': len(G), 'pente_du_publie': a, 'erreur_type': et,
                           'favori_annonce_pct': round(100 * sum(max(r['p'], 1 - r['p']) for r in G) / len(G), 1) if G else None,
                           'favori_gagnant_pct': round(100 * sum((r['p'] >= .5) == (r['y'] == 1) for r in G) / len(G), 1) if G else None}
    return out


def message(doc):
    c = doc['candidat']
    t = doc['par_tranche'].get('CH') or {}
    lig = ' ; '.join(f"{k} {v['matchs']} m. pente {v['pente_du_publie']}" for k, v in t.items() if v['matchs'])
    return (f"📐 Pente sous 500 points (Challenger, fantôme, paquet 466) — {c['matchs']} matchs, gain {c['gain_log_loss']} "
            f"± {c['erreur_type']} (moitiés {c['gain_1re_moitie']} / {c['gain_2de_moitie']}) — "
            + ("À PROPOSER à Lucas" if c['a_proposer'] else f"suivi (règle : {MIN_MATCHS} matchs)")
            + (f"\nNos % publiés en Challenger par tranche : {lig}" if lig else ''))


def main(argv):
    racine = argv[1] if len(argv) > 1 and not argv[1].startswith('--') else '.'
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            src = json.load(f)
    except (OSError, ValueError):
        print('pronostics_resultats.json absent')
        return 0
    L = lignes(src)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs_lus': len(L),
           'definition': ("% publié contre le même étiré (σ(1,174 · logit p)) sur les Challengers dont le joueur le moins "
                          "vu avait moins de 500 points de service au moment du pronostic. Le % affiché ne change pas."),
           'candidat': candidat(L), 'par_tranche': par_tranche(L)}
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
    c = doc['candidat']
    print(len(L), 'matchs lus ;', c['matchs'], 'concernés ; gain', c['gain_log_loss'], '; à proposer', c['a_proposer'])
    if '--telegram' in argv:
        try:
            import telegram_envoi as TE
            TE.envoyer(message(doc))
        except Exception as e:  # noqa: BLE001 — le message ne doit jamais faire échouer le suivi
            print('telegram :', type(e).__name__)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
