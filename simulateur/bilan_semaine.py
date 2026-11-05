#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bilan_semaine.py — le bilan de la SEMAINE écoulée (lundi → dimanche), pour la carte du lundi (05/11/2026, demande de
Lucas). Lit tous les bilans après match (simulateur/journal_pronostics/apres_match/*.json.gz : pronostic figé avant
le match contre résultat réel) et écrit algo/semaine.json, lu par la page en mode ?semaine=1 (capturée par
scripts/video_simulation.py --semaine). Rien n'est trié : TOUS les matchs ATP, WTA et Challenger jugés de la semaine.
Aucune cote. Usage : python simulateur/bilan_semaine.py [racine]   (BILAN_JOUR=AAAA-MM-JJ pour une autre date)
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
CIRCUITS = ('ATP', 'WTA', 'CH')
SORTIE = os.path.join('algo', 'semaine.json')


def semaine(aujourdhui):
    lundi = aujourdhui - dt.timedelta(days=aujourdhui.weekday())
    return lundi - dt.timedelta(days=7), lundi - dt.timedelta(days=1)


def lire(racine, debut, fin):
    out = []
    for chemin in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', 'apres_match', '*.json.gz'))):
        if not (debut.isoformat() <= os.path.basename(chemin)[:10] <= fin.isoformat()):
            continue
        try:
            out.extend(json.load(gzip.open(chemin, 'rt', encoding='utf-8')).values())
        except (OSError, ValueError):
            continue
    return [b for b in out if b.get('circuit') in CIRCUITS and (b.get('ecarts') or {}).get('vainqueur_juste') is not None
            and isinstance((b.get('prevu') or {}).get('p_home'), (int, float))
            and debut.isoformat() <= str(b.get('debut'))[:10] <= fin.isoformat()]


def calculer(B, debut, fin):
    pf = lambda b: max(b['prevu']['p_home'], 1 - b['prevu']['p_home'])
    juste = lambda b: bool(b['ecarts']['vainqueur_juste'])
    def bloc(L):
        n = len(L)
        return {'matchs': n, 'justes_pct': round(100 * sum(map(juste, L)) / n, 1) if n else None,
                'annonce_pct': round(100 * sum(map(pf, L)) / n, 1) if n else None}
    circuits = {c: bloc([b for b in B if b['circuit'] == c]) for c in CIRCUITS}
    fav70 = bloc([b for b in B if pf(b) >= .70])
    rates = sorted([b for b in B if not juste(b)], key=pf, reverse=True)[:2]
    exacts = [b for b in B if b['ecarts'].get('score_rang') == 1]
    video = [b for b in B if ((b['prevu'].get('scenario') or {}).get('score') or '').strip()
             and b['prevu']['scenario']['score'].strip() == str((b.get('reel') or {}).get('score') or '').strip()]
    court = lambda n: str(n or '').split(' ')[-1]
    resume = lambda b: {'match': f"{court(b['home'])} – {court(b['away'])}", 'circuit': b['circuit'],
                        'favori': court(b['home'] if b['prevu']['p_home'] >= .5 else b['away']),
                        'p': round(100 * pf(b)), 'score': (b.get('reel') or {}).get('score')}
    return {'debut': debut.isoformat(), 'fin': fin.isoformat(), 'tous': bloc(B), 'circuits': circuits,
            'favoris_70': fav70, 'pires_rates': [resume(b) for b in rates],
            'scores_exacts': len(exacts), 'scores_exacts_exemples': [resume(b) for b in exacts[:3]],
            'videos_exactes': [resume(b) for b in video[:3]]}


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    jour = dt.date.fromisoformat(os.environ['BILAN_JOUR']) if os.environ.get('BILAN_JOUR') else dt.date.today()
    debut, fin = semaine(jour)
    doc = calculer(lire(racine, debut, fin), debut, fin)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: doc[k] for k in ('debut', 'fin', 'tous', 'circuits', 'favoris_70')}, ensure_ascii=False))
    return 0 if doc['tous']['matchs'] else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
