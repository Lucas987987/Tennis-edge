#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tournois_infos.py — fiche de chaque tournoi des feuilles (TennisApi) — 06/11/2026, paquet 208.

Sonde du 06/11/2026 (sondes/tennisapi_2026-11-06.json) : la saison d'un tournoi donne la VILLE et le PAYS HÔTES, le
nombre de joueurs du tableau et la DOTATION totale ; la fiche du tournoi donne les points du vainqueur.
Pour chaque tournoi (ATP, WTA, Challenger, compétitions par équipes ; pas d'ITF) et chaque ANNÉE pas encore connus :
  /api/tennis/tournament/{id}/seasons            → la saison de l'année du match ;
  /api/tennis/tournament/{id}/season/{saison}/info → ville, pays, joueurs, dotation, devise ;
  /api/tennis/tournament/{id}/info               → points du vainqueur (une fois par tournoi).
Trois requêtes par tournoi nouveau, une seule fois (≈ 700 la première fois pour tout l'historique, puis quelques-unes
par semaine). Garde-fous de feuilles_match.py (budget, réserve de quota).
Sortie : feuilles/tournois_infos.json {id: {annee: {saison, ville, pays, joueurs, dotation, devise, dotation_usd},
                                             'points': n, 'nom': …}}
Lu par lieux_tournois.py (le lieu hôte passe AVANT le nom du tournoi) et par facteurs.py (groupe « dotation »).
Usage : python scripts/tournois_infos.py [budget]
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

FICHIER = os.path.join(FM.DOSSIER, 'tournois_infos.json')
ESSAIS_MAX = 2
# Conversion approximative en dollars (seul l'ordre de grandeur compte : la variable est un logarithme).
EN_USD = {'$': 1.0, 'USD': 1.0, '€': 1.08, 'EUR': 1.08, '£': 1.27, 'GBP': 1.27, 'A$': 0.66, 'AUD': 0.66,
          'C$': 0.73, 'CAD': 0.73, 'CHF': 1.13, '¥': 0.0067, 'JPY': 0.0067, 'CNY': 0.14, 'R$': 0.18}


def lire(chemin=FICHIER):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ecrire(doc, chemin=FICHIER):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, sort_keys=True, indent=0)
    os.replace(chemin + '.tmp', chemin)


def dotation_usd(valeur, devise):
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    taux = EN_USD.get(str(devise or '').strip())
    return round(v * taux) if taux and v > 0 else None


def fiche_saison(doc):
    """Champs utiles de /season/{id}/info (format vu par la sonde du 06/11/2026)."""
    i = (doc or {}).get('info') or {}
    if not i:
        return None
    brut = i.get('totalPrizeMoneyRaw') or {}
    val = brut.get('value', i.get('totalPrizeMoney'))
    dev = brut.get('currency', i.get('totalPrizeMoneyCurrency'))
    pays = i.get('hostCountries') or []
    return {'ville': i.get('hostCity') or ((i.get('hostCities') or [None])[0]),
            'pays': pays[0] if pays else None, 'joueurs': i.get('numberOfCompetitors'),
            'dotation': val, 'devise': dev, 'dotation_usd': dotation_usd(val, dev)}


def saison_de_l_annee(doc, annee):
    for s in (doc or {}).get('seasons') or []:
        if str(s.get('year')) == str(annee) or str(annee) in str(s.get('name') or ''):
            return s.get('id')
    return None


def tournois_des_feuilles():
    """{id: {'nom', 'annees': set}} — sans l'ITF."""
    out = {}
    for p in sorted(glob.glob(os.path.join(FM.DOSSIER, '20*.jsonl.gz'))):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    r = json.loads(l)
                    i = r.get('tournoi_id')
                    if not i or 'itf' in FM.norm(r.get('categorie')) or not r.get('jour'):
                        continue
                    e = out.setdefault(str(i), {'nom': r.get('tournoi_unique') or r.get('tournoi'), 'annees': set()})
                    e['annees'].add(r['jour'][:4])
        except (OSError, ValueError, EOFError):
            continue
    return out


def main(argv):
    budget = int(argv[1]) if len(argv) > 1 and argv[1] else 300
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('RAPIDAPI_KEY absent : rien à faire.')
        return 0
    c = FM.Client(cle, budget=budget)
    doc = lire()
    vus = tournois_des_feuilles()
    n_new = 0
    # les tournois les plus récents d'abord (ceux qui comptent pour les pronostics du jour)
    try:
        for i, e in sorted(vus.items(), key=lambda kv: max(kv[1]['annees']), reverse=True):
            d = doc.setdefault(i, {'nom': e['nom']})
            for an in sorted(e['annees'], reverse=True):
                x = d.get(an) or {}
                if x.get('ville') or x.get('dotation_usd') or x.get('essais', 0) >= ESSAIS_MAX:
                    continue
                code, se = c.get(f"/api/tennis/tournament/{i}/seasons")
                sid = saison_de_l_annee(se, an) if code == 200 else None
                f = None
                if sid:
                    code, si = c.get(f"/api/tennis/tournament/{i}/season/{sid}/info")
                    f = fiche_saison(si) if code == 200 else None
                d[an] = dict(f or {}, saison=sid, essais=x.get('essais', 0) + (0 if f else 1))
                n_new += 1
            if 'points' not in d:
                code, ti = c.get(f"/api/tennis/tournament/{i}/info")
                m = (ti or {}).get('meta') or {}
                d['points'] = ((m.get('uniqueTournament') or {}).get('tennisPoints')) if code == 200 else None
    except FM.QuotaAtteint as e:
        print(f'Arrêt : {e}')
    finally:
        ecrire(doc)
    avec = sum(1 for d in doc.values() for k, v in d.items() if k.isdigit() and isinstance(v, dict) and v.get('dotation_usd'))
    print(f"{len(doc)} tournois · {n_new} saisons demandées · {avec} saisons avec dotation · {c.n} requêtes")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
