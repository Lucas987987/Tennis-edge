#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_infos_tennis.py — 26/11/2026 : quelles informations le fournisseur de TennisApi donne-t-il
que nous n'utilisons PAS encore ? Et le badminton ?

LECTURE SEULE. Passe par AllSportsApi (allsportsapi2.p.rapidapi.com, formule gratuite, 100
requêtes par jour), même auteur et mêmes réponses que TennisApi : le quota du tennis n'est
PAS touché. Rien n'est écrit dans le dépôt ; le journal ne montre que des codes HTTP, des
tailles, des noms de champs et des comptes (jamais la clé, jamais de cote).

Ce que nous utilisons déjà (pas re-sondé) : calendrier, matchs par catégorie, détail du match,
statistiques, point par point, joueur, classements, tournoi (infos, saisons, tours, tableau).

A. Tennis, un match ATP ou Challenger terminé hier : on essaie les chemins que nous n'appelons
   pas (face-à-face, votes, forme avant le match, séries, dynamique du match, faits marquants…),
   puis ceux du joueur (performances, statistiques de l'année, historique de classement…),
   puis ceux du tournoi. Un 404 veut dire « absent ou autre nom » : on note et on passe.
   Les cotes ne sont jamais appelées.
B. Badminton : même sonde que le tennis de table (sonde_tennis_de_table.sonder).

AU PLUS 50 requêtes en tout, jamais de nouvelle tentative.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sonde_tennis_de_table as TT  # noqa: E402

MAX_REQ = 50
MAX_TENNIS = 36
CIRCUITS = ('atp', 'challenger', 'wta')

CHEMINS_MATCH = ('h2h', 'h2h/events', 'votes', 'pregame-form', 'team-streaks', 'streaks', 'tennis-power',
                 'power', 'graph', 'incidents', 'highlights', 'win-probability')
CHEMINS_JOUEUR = ('team/{id}/performance', 'team/{id}/year-statistics/{an}', 'team/{id}/rankings',
                  'team/{id}/ranking-history', 'team/{id}/tournaments', 'player/{id}/statistics/seasons',
                  'team/{id}/events/last/0', 'team/{id}/near-events')
CHEMINS_TOURNOI = ('tournament/{ut}/season/{sid}/statistics', 'tournament/{ut}/media',
                   'tournament/{ut}/featured-events')
INTERDITS = ('odds',)


def forme(doc):
    """Résumé lisible et sans contenu : champs du premier niveau et taille des listes."""
    if isinstance(doc, dict):
        out = []
        for k, v in list(doc.items())[:8]:
            out.append(f"{k}[{len(v)}]" if isinstance(v, list) else k)
        return ', '.join(out)
    if isinstance(doc, list):
        return f"liste de {len(doc)}"
    return '-'


def champs(doc, prof=0, out=None):
    """Tous les noms de champs, sans les valeurs (pour voir ce qu'un objet contient)."""
    out = set() if out is None else out
    if prof > 3:
        return out
    if isinstance(doc, dict):
        for k, v in doc.items():
            out.add(k)
            champs(v, prof + 1, out)
    elif isinstance(doc, list):
        for v in doc[:3]:
            champs(v, prof + 1, out)
    return out


def essayer(c, chemin, journal, connus=None):
    assert not any(m in chemin for m in INTERDITS)
    code, doc = c.get(f"/api/tennis/{chemin}")
    nouveaux = ''
    if code == 200 and connus is not None:
        n = sorted(champs(doc) - connus)
        nouveaux = f" · champs : {', '.join(n[:25])}" if n else ''
    journal(f"   {chemin.split('/', 2)[-1] if chemin.startswith('event/') else chemin} : HTTP {code}"
            + (f" · {forme(doc)}" if code == 200 else '') + nouveaux)
    return code, doc


def match_du_jour(c, hier, journal):
    code, idx = c.get(f"/api/tennis/calendar/{hier.day}/{hier.month}/{hier.year}/categories")
    L = TT.ligues(idx) if code == 200 else []
    journal(f"A. Tennis {hier} : HTTP {code}, {TT.total(L)} matchs dans {len(L)} catégories "
            f"({', '.join(f'{n} {k}' for n, _, k in L[:6])})")
    for voulu in CIRCUITS:
        cat = next(((n, i) for n, i, k in L if k and n.lower() == voulu), None)
        if not cat:
            continue
        code, doc = c.get(f"/api/tennis/category/{cat[1]}/events/{hier.day}/{hier.month}/{hier.year}")
        for e in TT.termines(doc):
            h, a = e.get('homeTeam') or {}, e.get('awayTeam') or {}
            if not h.get('subTeams') and not a.get('subTeams') and h.get('id'):
                journal(f"   match choisi : {cat[0]}, terminé, {len(TT.termines(doc))} matchs terminés dans la catégorie")
                return e
    return None


def sonder_tennis(c, hier, journal):
    e = match_du_jour(c, hier, journal)
    if not e:
        journal("   aucun match ATP, Challenger ou WTA terminé : arrêt du volet tennis")
        return {}
    connus = champs(e)
    res = {'match': {}, 'joueur': {}, 'tournoi': {}}
    journal("   — chemins du match")
    for ch in CHEMINS_MATCH:
        if c.n >= MAX_TENNIS:
            break
        res['match'][ch] = essayer(c, f"event/{e['id']}/{ch}", journal, connus)[0]
    jid = (e.get('homeTeam') or {}).get('id')
    journal("   — chemins du joueur")
    for ch in CHEMINS_JOUEUR:
        if c.n >= MAX_TENNIS:
            break
        res['joueur'][ch] = essayer(c, ch.format(id=jid, an=hier.year), journal, set())[0]
    t = e.get('tournament') or {}
    ut, sid = (t.get('uniqueTournament') or {}).get('id'), (e.get('season') or {}).get('id')
    if ut:
        journal("   — chemins du tournoi")
        for ch in CHEMINS_TOURNOI:
            if c.n >= MAX_TENNIS or ('{sid}' in ch and not sid):
                continue
            res['tournoi'][ch] = essayer(c, ch.format(ut=ut, sid=sid), journal, set())[0]
    return res


def sonder(cle, aujourdhui=None, ouvrir=None, journal=print):
    hier = (aujourdhui or dt.date.today()) - dt.timedelta(days=1)
    c = TT.Client(cle, ouvrir, max_req=MAX_TENNIS)
    tennis = sonder_tennis(c, hier, journal)
    dispo = [k for v in tennis.values() for k, code in v.items() if code == 200]
    journal(f"   bilan tennis : {len(dispo)} chemins répondent ({', '.join(dispo)}) — {c.n} requêtes, "
            f"quota restant {c.reste}")
    journal("B. Badminton")
    bad = TT.sonder(cle, aujourdhui, ouvrir, journal, noms=('badminton',))
    return {'tennis': tennis, 'badminton': bad, 'requetes_tennis': c.n}


def main():
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('sonde_infos_tennis : RAPIDAPI_KEY absente')
        return 0
    sonder(cle)
    return 0


if __name__ == '__main__':
    sys.exit(main())
