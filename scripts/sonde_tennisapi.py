#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_tennisapi.py — SONDE de deux pistes TennisApi (06/11/2026, demande de Lucas) :
  1. LE LIEU EXACT de chaque match (ville, stade, coordonnées ?) dans le détail /api/tennis/event/{id} — aujourd'hui
     lieux_tournois.py devine le lieu d'après le NOM du tournoi ;
  2. LE TABLEAU du tournoi (pour le mode tournoi) : saisons, puis « cuptrees » (tableau à élimination directe).
Pour UN match récent par circuit (ATP, WTA, Challenger) des feuilles : ~6 requêtes par circuit, 20 au plus.
Rien n'est modifié dans le pipeline : la réponse (raccourcie, sans clé) est écrite dans sondes/tennisapi_AAAA-MM-JJ.json
pour être lue à la main. Usage : python scripts/sonde_tennisapi.py [--tableau]
06/11/2026 (paquet 208) : --tableau = 2e sonde, sur le tableau (autre identifiant de tournoi, tours, matchs par tour).
"""
import datetime as dt
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sondes')
CIRCUITS = {'ATP': 'ATP', 'WTA': 'WTA', 'Challenger': 'CH'}


def raccourcir(x, prof=0, max_liste=3, max_prof=6):
    """Copie lisible : listes coupées à 3 éléments (avec leur longueur), chaînes à 200 caractères."""
    if prof > max_prof:
        return '…'
    if isinstance(x, dict):
        return {k: raccourcir(v, prof + 1, max_liste, max_prof) for k, v in x.items()}
    if isinstance(x, list):
        out = [raccourcir(v, prof + 1, max_liste, max_prof) for v in x[:max_liste]]
        if len(x) > max_liste:
            out.append(f'… {len(x)} éléments au total')
        return out
    if isinstance(x, str) and len(x) > 200:
        return x[:200] + '…'
    return x


def chercher_cles(x, mots, chemin='', out=None):
    """Chemins de toutes les clés dont le nom contient un des mots (venue, city, stadium, coordinates…)."""
    out = [] if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            c = f'{chemin}.{k}' if chemin else k
            if any(m in k.lower() for m in mots):
                out.append([c, raccourcir(v, max_prof=2)])
            chercher_cles(v, mots, c, out)
    elif isinstance(x, list) and x:
        chercher_cles(x[0], mots, chemin + '[0]', out)
    return out


def matchs_recents():
    """Un match terminé récent par circuit, depuis les feuilles (plus récent d'abord)."""
    vus = {}
    for p in sorted(glob.glob(os.path.join(FM.DOSSIER, '20*.jsonl.gz')), reverse=True)[:5]:
        for r in FM.lire_jour(os.path.basename(p)[:10]).values():
            cat = str(r.get('categorie') or '')
            c = CIRCUITS.get(cat)
            if c and c not in vus and r.get('tournoi_id') and FM.est_simple({'homeTeam': {'name': r['home'].get('nom')},
                                                                              'awayTeam': {'name': r['away'].get('nom')}}):
                vus[c] = r
        if len(vus) == len(CIRCUITS):
            break
    return vus


def sonde_tableau(c, doc):
    """06/11/2026 (paquet 208) — 2e sonde : où est le TABLEAU ? « cuptrees » répondait 404 avec l'identifiant du
    tournoi « unique ». On essaie l'autre identifiant (event.tournament.id), les tours, et les matchs par tour."""
    for circ, r in matchs_recents().items():
        if circ == 'WTA':
            continue
        bloc = {'match': f"{r['home'].get('nom')} – {r['away'].get('nom')} ({r.get('tournoi')}, {r.get('jour')})",
                'requetes': []}

        def essai(chemin, garder=True):
            try:
                code, d = c.get(chemin)
            except FM.QuotaAtteint as e:
                bloc['requetes'].append({'chemin': chemin, 'http': f'arrêt : {e}'})
                return None
            bloc['requetes'].append({'chemin': chemin, 'http': code,
                                     'cles': sorted(d.keys()) if isinstance(d, dict) else None,
                                     'reponse': raccourcir(d) if garder and d else None})
            print(f"{circ} · HTTP {code} · {chemin}", flush=True)
            return d

        ev = (essai(f"/api/tennis/event/{r['id']}", garder=False) or {}).get('event') or {}
        tid = (ev.get('tournament') or {}).get('id')
        utid = ((ev.get('tournament') or {}).get('uniqueTournament') or {}).get('id') or r.get('tournoi_id')
        sid = (ev.get('season') or {}).get('id')
        rnd = (ev.get('roundInfo') or {})
        bloc.update(tournament_id=tid, unique_id=utid, season_id=sid, round=rnd)
        if tid and sid:
            essai(f"/api/tennis/tournament/{tid}/season/{sid}/cuptrees")
        if utid and sid:
            essai(f"/api/tennis/tournament/{utid}/season/{sid}/rounds")
            if rnd.get('round') is not None:
                essai(f"/api/tennis/tournament/{utid}/season/{sid}/events/round/{rnd['round']}")
            essai(f"/api/tennis/tournament/{utid}/season/{sid}/events/next/0")
            essai(f"/api/tennis/tournament/{utid}/season/{sid}/events/last/0")
        doc['tableau'][circ] = bloc


def main():
    if '--tableau' in sys.argv:
        cle = os.environ.get('RAPIDAPI_KEY', '').strip()
        if not cle:
            print('RAPIDAPI_KEY absent : rien à faire.')
            return 0
        c = FM.Client(cle, budget=16)
        doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'tableau': {}}
        sonde_tableau(c, doc)
        doc['requetes'], doc['quota_restant'] = c.n, c.restant
        os.makedirs(SORTIE, exist_ok=True)
        chemin = os.path.join(SORTIE, f"tennisapi_tableau_{dt.date.today().isoformat()}.json")
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print(f"{c.n} requêtes · {chemin}")
        return 0
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('RAPIDAPI_KEY absent : rien à faire.')
        return 0
    c = FM.Client(cle, budget=20)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'circuits': {}}
    for circ, r in matchs_recents().items():
        bloc = {'match': f"{r['home'].get('nom')} – {r['away'].get('nom')} ({r.get('tournoi')}, {r.get('jour')})",
                'event_id': r['id'], 'tournoi_id': r.get('tournoi_id'), 'requetes': []}

        def essai(chemin, mots=None, garder=False):
            try:
                code, d = c.get(chemin)
            except FM.QuotaAtteint as e:
                bloc['requetes'].append({'chemin': chemin, 'http': f'arrêt : {e}'})
                return None
            x = {'chemin': chemin, 'http': code, 'cles': sorted(d.keys()) if isinstance(d, dict) else None}
            if mots and d:
                x['trouve'] = chercher_cles(d, mots)
            if garder and d:
                x['reponse'] = raccourcir(d)
            bloc['requetes'].append(x)
            print(f"{circ} · HTTP {code} · {chemin}", flush=True)
            return d

        ev = essai(f"/api/tennis/event/{r['id']}", ['venue', 'city', 'stadium', 'coordinat', 'latitude', 'longitude',
                                                      'country', 'season', 'uniquetournament', 'indoor', 'ground'])
        ut = (((ev or {}).get('event') or {}).get('tournament') or {}).get('uniqueTournament') or {}
        utid = ut.get('id') or r.get('tournoi_id')
        sid = (((ev or {}).get('event') or {}).get('season') or {}).get('id')
        if not sid:
            se = essai(f"/api/tennis/tournament/{utid}/seasons", garder=True)
            ss = (se or {}).get('seasons') or []
            sid = ss[0].get('id') if ss else None
        essai(f"/api/tennis/tournament/{utid}/info", ['venue', 'city', 'stadium', 'coordinat', 'ground', 'indoor', 'draw'],
              garder=True)
        if sid:
            essai(f"/api/tennis/tournament/{utid}/season/{sid}/cuptrees", garder=True)
            essai(f"/api/tennis/tournament/{utid}/season/{sid}/info", garder=True)
        bloc['season_id'] = sid
        doc['circuits'][circ] = bloc
    doc['requetes'] = c.n
    doc['quota_restant'] = c.restant
    os.makedirs(SORTIE, exist_ok=True)
    chemin = os.path.join(SORTIE, f"tennisapi_{dt.date.today().isoformat()}.json")
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"{c.n} requêtes · {chemin}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
