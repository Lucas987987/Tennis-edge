#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lignes_algo.py — « stats annexes » CALCULÉES PAR L'ALGO (28/10/2026), et duel service ↔ retour.

1. Lignes de paris tirées de la distribution EXACTE des scores du match (distribution_exacte.py, déjà publiée par
   la vitrine) : total de jeux au-dessus de 18,5 à 23,5 (34,5 à 39,5 au meilleur des 5), handicap de jeux du favori
   (−1,5 à −5,5), au moins un tie-break, match en 3 sets (5 au meilleur des 5), 1er set. Contrairement aux bilans
   bruts d'un joueur, ce sont des probabilités propres à CE match, sans aucune cote. Vérifiées le 28/10 sur
   2 468 matchs jamais vus (README). Chaque probabilité est figée dans un journal avant le match
   (simulateur/journal_pronostics/lignes_algo_v1.jsonl) et jugée sur le score réel (bilan_lignes()).
2. Duel service ↔ retour : indice 0–100 = rang centile du joueur, sur la surface du match, parmi les joueurs de
   son circuit ayant au moins 200 balles (Tennis_Edge_Lab/live/joueurs_service.json.gz, déjà public).
Aucune entrée du modèle : affichage et suivi seulement.
"""
import bisect
import datetime as dt
import gzip
import json
import os

LIGNES_TOTAL = {3: (18.5, 19.5, 20.5, 21.5, 22.5, 23.5), 5: (32.5, 34.5, 36.5, 38.5, 40.5)}
LIGNES_HANDICAP = (1.5, 2.5, 3.5, 4.5, 5.5)
MIN_BALLES_DUEL = 200
JOURNAL = os.path.join('simulateur', 'journal_pronostics', 'lignes_algo_v1.jsonl')


def _tb(sc):
    return any(max(a, b) == 7 and min(a, b) == 6 for a, b in sc)


def lignes(distribution, p_home, meilleur_des=3):
    """{ligne: probabilité} depuis [{'score': [[a, b], …], 'probabilite': p}] (scores vus de home)."""
    D = [(tuple(tuple(s) for s in e['score']), e['probabilite']) for e in distribution or []]
    tot = sum(p for _, p in D)
    if not D or tot <= 0:
        return None
    fav = 1 if p_home >= 0.5 else -1                       # +1 : home favori
    out = {'favori': 'home' if fav == 1 else 'away', 'meilleur_des': meilleur_des}
    for k in LIGNES_TOTAL.get(meilleur_des, ()):
        out[f'total_plus_{k}'] = round(sum(p for sc, p in D if sum(a + b for a, b in sc) > k) / tot, 4)
    for k in LIGNES_HANDICAP:
        out[f'handicap_favori_{k}'] = round(sum(p for sc, p in D if fav * sum(a - b for a, b in sc) > k) / tot, 4)
    out['tie_break'] = round(sum(p for sc, p in D if _tb(sc)) / tot, 4)
    out['set_decisif'] = round(sum(p for sc, p in D if len(sc) == 2 * (meilleur_des // 2) + 1) / tot, 4)
    out['set1_home'] = round(sum(p for sc, p in D if sc[0][0] > sc[0][1]) / tot, 4)
    out['jeux_moyen'] = round(sum(p * sum(a + b for a, b in sc) for sc, p in D) / tot, 1)
    return out


def resultat(sets, m):
    """{ligne: 0/1} pour toutes les lignes figées m (sortie de lignes())."""
    if not sets or not m:
        return {}
    fav = 1 if m['favori'] == 'home' else -1
    bo = m.get('meilleur_des', 3)
    out = {}
    for k in m:
        if k.startswith('total_plus_'):
            out[k] = int(sum(a + b for a, b in sets) > float(k[len('total_plus_'):]))
        elif k.startswith('handicap_favori_'):
            out[k] = int(fav * sum(a - b for a, b in sets) > float(k[len('handicap_favori_'):]))
    out['tie_break'] = int(_tb(sets))
    out['set_decisif'] = int(len(sets) == 2 * (bo // 2) + 1)
    out['set1_home'] = int(sets[0][0] > sets[0][1])
    return out


# ------------------------------------------------------------------ journal figé et bilan
def journaliser(lignes, racine, maintenant=None):
    """Ajoute une ligne par uid (la PREMIÈRE seulement : jamais réécrite) pour les matchs pas encore commencés."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    chemin = os.path.join(racine, JOURNAL)
    vus = set()
    try:
        with open(chemin, encoding='utf-8') as f:
            vus = {json.loads(l)['uid'] for l in f if l.strip()}
    except (OSError, ValueError):
        pass
    nouv = []
    for x in lignes:
        m = x.get('lignes_algo')
        if not m or x['uid'] in vus:
            continue
        try:
            debut = dt.datetime.fromisoformat(str(x.get('debut_utc') or '').replace('Z', '+00:00'))
        except ValueError:
            continue
        if debut.tzinfo is None:
            debut = debut.replace(tzinfo=dt.timezone.utc)
        if debut <= maintenant:
            continue                                        # seulement AVANT le début du match
        nouv.append({'uid': x['uid'], 'fige_le': maintenant.isoformat(timespec='seconds'), 'debut': debut.isoformat(),
                     'circuit': x.get('circuit'), 'home': x.get('home'), 'away': x.get('away'), 'lignes': m})
    if nouv:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, 'a', encoding='utf-8') as f:
            for r in nouv:
                f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    return len(nouv)


def bilan_lignes(racine, scores_reels):
    """Calibration et Brier par ligne sur les matchs journalisés et joués. scores_reels : {uid: [(h, a), …]}."""
    try:
        with open(os.path.join(racine, JOURNAL), encoding='utf-8') as f:
            J = [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        return {'n': 0}
    acc = {}
    n = 0
    for r in J:
        sets = scores_reels.get(r['uid'])
        if not sets:
            continue
        n += 1
        for k, y in resultat(sets, r['lignes']).items():
            p = r['lignes'].get(k)
            if p is None:
                continue
            a = acc.setdefault(k, [0, 0.0, 0.0, 0.0])
            a[0] += 1
            a[1] += p
            a[2] += y
            a[3] += (p - y) ** 2
    out = {'n': n, 'lignes': {}}
    for k, (m, sp, sy, sb) in sorted(acc.items()):
        taux = sy / m
        out['lignes'][k] = {'n': m, 'prevu_pct': round(100 * sp / m, 1), 'reel_pct': round(100 * taux, 1),
                             'brier': round(sb / m, 4), 'conclusion_possible': m >= 30}
    return out


# ------------------------------------------------------------------ duel service ↔ retour
class Duel:
    def __init__(self, doc):
        self.J = (doc or {}).get('joueurs') or {}
        self.moy = (doc or {}).get('moyennes') or {}
        self.ref = {}
        for j, e in self.J.items():
            for s, v in (e.get('surfaces') or {}).items():
                if (v.get('balles') or 0) >= MIN_BALLES_DUEL and v.get('joueur'):
                    for cote in ('serv', 'ret'):
                        self.ref.setdefault((e.get('circuit'), s, cote), []).append(v['joueur'][cote])
        for k in self.ref:
            self.ref[k].sort()

    @classmethod
    def charger(cls, racine):
        try:
            with gzip.open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'joueurs_service.json.gz'), 'rt',
                           encoding='utf-8') as f:
                return cls(json.load(f))
        except (OSError, ValueError):
            return cls({})

    def joueur(self, cle, circuit, surface):
        e = self.J.get(cle)
        v = ((e or {}).get('surfaces') or {}).get(surface) or {}
        if not e or (v.get('balles') or 0) < MIN_BALLES_DUEL or not v.get('joueur'):
            return None
        out = {'balles': v['balles']}
        for cote in ('serv', 'ret'):
            R = self.ref.get((circuit, surface, cote)) or []
            x = v['joueur'][cote]
            out[cote + '_pct'] = round(100 * x, 1)
            out[cote + '_indice'] = round(100 * bisect.bisect_left(R, x) / len(R)) if R else None
        return out

    def match(self, h, a, circuit, surface):
        jh, ja = self.joueur(h, circuit, surface), self.joueur(a, circuit, surface)
        if not jh or not ja:
            return None
        return {'descriptif_seulement': True, 'joueurs': [jh, ja], 'circuit': circuit, 'surface': surface,
                'moyenne': {k: round(100 * v, 1) for k, v in ((self.moy.get(circuit) or {}).get(surface) or {}).items()
                            if k in ('serv', 'ret')},
                'duels': [{'service': 0, 'ecart': (jh['serv_indice'] or 0) - (ja['ret_indice'] or 0)},
                          {'service': 1, 'ecart': (ja['serv_indice'] or 0) - (jh['ret_indice'] or 0)}]}
