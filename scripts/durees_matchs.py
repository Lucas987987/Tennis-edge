#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
durees_matchs.py — la durée des matchs déjà collectés (23/10/2026, corrigé le 28/10/2026).

PANNE CORRIGÉE le 28/10/2026 : la première version lisait la durée dans la LISTE des matchs du jour, qui ne contient
pas le champ « time » ; elle a marqué tous les jours comme traités sans trouver une seule durée (duree_min vide dans
les 9 764 feuilles). Désormais : une requête de DÉTAIL par match (/api/tennis/event/{id}), seulement pour les matchs
terminés avec feuille, ATP / WTA / Challenger, sans durée, 3 tentatives au plus (« duree_essai »).
Les plus récents d'abord. La durée d'un match fini ne change plus : la relire après coup ne fait entrer aucune
information du futur.
Quota TennisApi : ~15 000 requêtes par jour, ~470 consommées par la collecte habituelle ; ce rattrapage prend 800
requêtes par passage (2 passages par jour) avec une réserve de 6 000 : ~6 jours pour les feuilles passées.
Diagnostic : si 20 détails reviennent sans durée, le format de la réponse est affiché (clés seulement) et on s'arrête.
Usage : python scripts/durees_matchs.py [budget]
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402


class FormatInconnu(Exception):
    pass


def candidats(recs):
    return [r for r in recs.values()
            if r.get('stats') and not r.get('duree_min') and (r.get('duree_essai') or 0) < FM.DUREE_ESSAIS_MAX
            and 'itf' not in FM.norm(r.get('categorie'))]


def completer_jour(c, jour, compteur):
    """Nombre de durées trouvées pour ce jour (None : rien à faire) ; lève FM.QuotaAtteint ou FormatInconnu."""
    recs = FM.lire_jour(jour, FM.DOSSIER)
    a_faire = candidats(recs) if recs else []
    if not a_faire:
        return None
    n = 0
    try:
        for r in a_faire:
            code, doc = c.get(f"/api/tennis/event/{r['id']}")
            r['duree_essai'] = (r.get('duree_essai') or 0) + 1
            if code != 200:
                continue
            m = FM.duree_minutes(doc)
            compteur['essais'] += 1
            if m:
                r['duree_min'] = m
                n += 1
                compteur['trouves'] += 1
            elif compteur['trouves'] == 0 and compteur['essais'] >= 20:
                ev = (doc or {}).get('event') or doc or {}
                for x in a_faire:                         # format à corriger : rien n'est « consommé »
                    if not x.get('duree_min'):
                        x['duree_essai'] = max((x.get('duree_essai') or 1) - 1, 0)
                raise FormatInconnu(f"aucune durée dans 20 détails ; clés : {sorted(ev)[:40]} ; "
                                    f"time : {sorted((ev.get('time') or {}))}")
    finally:
        FM.ecrire_jour(jour, recs, FM.DOSSIER)
    return n


def main(argv):
    budget = int(argv[1]) if len(argv) > 1 else 800
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('RAPIDAPI_KEY absent : rien à faire.')
        return 0
    c = FM.Client(cle, budget=budget, reserve=int(os.environ.get('DUREES_RESERVE', '6000')))
    jours = sorted(os.path.basename(p)[:10] for p in glob.glob(os.path.join(FM.DOSSIER, '20*.jsonl.gz')))
    faits, compteur = 0, {'essais': 0, 'trouves': 0}
    try:
        for j in reversed(jours):                       # les plus récents d'abord
            n = completer_jour(c, j, compteur)
            if n is not None:
                faits += 1
    except FM.QuotaAtteint as e:
        print(f"::warning::Arrêt : {e} (le prochain passage reprendra)")
    except FormatInconnu as e:
        print(f"::warning::Durées : {e}")
    print(f"Durées des matchs : {faits} jour(s) traités, {compteur['trouves']} durée(s) trouvée(s) sur "
          f"{compteur['essais']} détail(s) · {c.n} requêtes")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
