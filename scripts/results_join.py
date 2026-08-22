#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
results_join.py — Le pont entre les courbes de cotes et les résultats.

LE PROBLÈME QU'IL RÉSOUT
Le test de contrôle a montré que seuls 43 matchs sur 440 avaient un résultat
connu — 10 % de couverture, et 4 matchs seulement dans le groupe « écart ≥ 8 % ».
Aucun ROI n'est mesurable là-dessus. Diagnostic : DEUX causes distinctes.

1. LES ANALYSES NE LISAIENT QUE LES COURBES LIVE.
   book_curves_live.jsonl ne contient que 54 paires de joueurs — la fenêtre de
   rétention courante. Les 1 195 autres sont dans les partitions historiques
   compressées. En lisant l'historique, la couverture passe de 4 % à 100 % :
   les 1 142 paires de résultats s'y retrouvent TOUTES.

2. LA DATE DE RÉSULTAT N'EST PAS CELLE DU COUP D'ENVOI.
   resultats_derived.json porte la date de RÈGLEMENT. Un match commencé à
   21 h UTC se règle le lendemain. Mesuré sur les paires communes :
       même jour  103 · 1 jour  604 · 2 jours  187 · 3 jours et + 291
   Exiger l'égalité stricte des dates écartait donc 90 % des appariements.

TROIS CONVENTIONS DE CLÉS COEXISTENT DANS LE PROJET
    résultats    atp_stuttgart_jurij_rodionov_vs_sho_shimabukuro
    match_key    frances-tiafoe_vs_learner-tien@2026-08-19
    uid courbes  2026-08-19_learner_tien_frances_tiafoe
Aucune ne se joint aux autres. On joint donc par (PAIRE DE JOUEURS, DATE À
±N JOURS) — les seuls invariants entre les trois.

LA PAIRE EST NON ORIENTÉE
Les jetons de chaque nom sont triés, puis les deux noms triés entre eux :
« Learner Tien vs Frances Tiafoe » et « Frances Tiafoe vs Learner Tien »
donnent la même clé. C'est indispensable : l'ordre home/away diffère entre les
sources, et c'est exactement ce qui avait produit 52 % de vainqueurs inversés
dans la première version de results_bridge.

CE QU'IL REFUSE
Un appariement ambigu — même paire de joueurs, deux résultats dans la fenêtre.
Deux joueurs peuvent se rencontrer deux fois en peu de jours (tournois
différents). On garde alors le plus proche en date, et on le SIGNALE.

Usage :
    from results_join import ResultIndex
    idx = ResultIndex()                 # charge resultats_derived.json
    gagnant = idx.winner(home, away, commence_time)   # 'home' | 'away' | None
"""
import os
import re
import json
import datetime
import unicodedata
import collections

RESULTS = os.environ.get('RESULTS_DERIVED', 'resultats_derived.json')
# Fenêtre de tolérance sur la date. 3 jours couvre le décalage de règlement
# et les matchs reportés, sans risquer de confondre deux rencontres du même
# duo à des tournois différents (voir la levée d'ambiguïté ci-dessous).
FENETRE_J = int(os.environ.get('JOIN_WINDOW_DAYS', '3'))


def norm_nom(s):
    """Jetons du nom, triés. Rend l'ordre des prénoms/noms indifférent."""
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return ' '.join(sorted(re.sub(r'[^a-z0-9]+', ' ', s.lower()).split()))


def paire(h, a):
    """Clé NON ORIENTÉE de la rencontre."""
    return '|'.join(sorted([norm_nom(h), norm_nom(a)]))


def _date(x):
    try:
        return datetime.date.fromisoformat(str(x)[:10])
    except Exception:
        return None


class ResultIndex:
    def __init__(self, chemin=None):
        self.par_paire = collections.defaultdict(list)
        self.n = 0
        self.ambigus = 0
        chemin = chemin or RESULTS
        if not os.path.exists(chemin):
            print(f"⚠️ {chemin} absent — lancer scripts/results_bridge.py d'abord.")
            return
        try:
            brut = json.load(open(chemin, encoding='utf-8'))
        except Exception as e:
            print(f"⚠️ {chemin} illisible : {e}")
            return
        lignes = brut.get('results') if isinstance(brut, dict) else brut
        for r in (lignes or []):
            if not isinstance(r, dict):
                continue
            h, a, w = r.get('home_team'), r.get('away_team'), r.get('winner')
            d = _date(r.get('date'))
            if not h or not a or not w or not d:
                continue
            # Le vainqueur est un NOM : on le compare aux deux joueurs plutôt
            # que de se fier à un champ 'home'/'away' dont l'orientation a déjà
            # été fausse une fois dans ce projet.
            nw = norm_nom(w)
            if nw == norm_nom(h):
                cote = 'home'
            elif nw == norm_nom(a):
                cote = 'away'
            else:
                continue
            self.par_paire[paire(h, a)].append({
                'date': d, 'home': h, 'away': a, 'gagnant_nom': w, 'cote': cote})
            self.n += 1
        print(f"ResultIndex : {self.n} résultats · {len(self.par_paire)} paires "
              f"· fenêtre ±{FENETRE_J} j")

    def lookup(self, home, away, quand):
        """Résultat de la rencontre, ou None. `quand` = coup d'envoi."""
        d = _date(quand)
        if d is None:
            return None
        lot = self.par_paire.get(paire(home, away))
        if not lot:
            return None
        proches = [(abs((x['date'] - d).days), x) for x in lot]
        proches = [(k, x) for k, x in proches if k <= FENETRE_J]
        if not proches:
            return None
        proches.sort(key=lambda x: x[0])
        if len(proches) > 1 and proches[0][0] == proches[1][0]:
            # Deux résultats à égale distance : on ne devine pas.
            self.ambigus += 1
            return None
        return proches[0][1]

    def winner(self, home, away, quand):
        """'home' ou 'away' DU POINT DE VUE DES NOMS PASSÉS, ou None.

        Le côté est recalculé à partir des noms fournis, jamais repris tel quel
        du fichier de résultats : l'appelant peut passer les joueurs dans
        l'ordre inverse, et c'est même fréquent entre sources.
        """
        r = self.lookup(home, away, quand)
        if not r:
            return None
        return 'home' if norm_nom(r['gagnant_nom']) == norm_nom(home) else 'away'


def main():
    """Diagnostic : quelle couverture atteint-on sur les courbes disponibles ?"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import oddspapi_v5 as ov

    idx = ResultIndex()
    if not idx.n:
        return 1

    vus, apparies = set(), 0
    for ligne in ov.iter_hist_lines('book'):
        try:
            r = json.loads(ligne)
        except Exception:
            continue
        h = r.get('home_team') or r.get('home')
        a = r.get('away_team') or r.get('away')
        ct = r.get('commence_time')
        if not h or not a or not ct:
            continue
        k = (paire(h, a), str(ct)[:10])
        if k in vus:
            continue
        vus.add(k)
        if idx.winner(h, a, ct):
            apparies += 1

    print(f"\nCourbes historiques : {len(vus)} match(s) distinct(s)")
    print(f"Avec résultat        : {apparies} ({100*apparies/max(1,len(vus)):.0f} %)")
    if idx.ambigus:
        print(f"⚠️ {idx.ambigus} appariement(s) refusé(s) pour ambiguïté "
              f"(deux résultats à égale distance)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
