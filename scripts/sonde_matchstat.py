#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_matchstat.py — l'historique de Matchstat (« Tennis API - ATP WTA ITF », RapidAPI) peut-il remplacer
l'archive Sackmann ? (22/11/2026, paquet 331, demande de Lucas après l'annonce de Matchstat.)

POURQUOI : l'algo apprend sur l'archive de Jeff Sackmann, sous licence CC BY-NC-SA 4.0 (usage NON commercial).
Avant une offre payante, il faut une source utilisable commercialement. Matchstat annonce des statistiques de
match depuis 2003 et du point par point depuis 2010. Cette sonde répond, avec très peu de requêtes :
  1. les statistiques de service et de retour d'un match passé sont-elles données, et par quel chemin ?
     (dans les résultats d'un tournoi = 1 requête par tournoi ; ou match par match = 1 requête par match) ;
  2. concordent-elles avec Sackmann pour les mêmes matchs (aces, doubles fautes, points au service) ?
  3. le point par point est-il disponible avec la formule actuelle ?
  4. combien de requêtes faudrait-il pour récupérer 2018–2025 (ATP, Challengers, WTA, WTA 125),
     comparé à ce que permet la formule (en-têtes x-ratelimit) ?

RÈGLES : budget de requêtes fixe (12 par défaut), arrêt si le quota restant passe sous la réserve (30) pour ne
jamais priver fetch_results_fast.py, aucune nouvelle tentative, la clé n'est jamais écrite. Les données ne sont
pas gardées : seulement des extraits courts et les comptes dans sonde_matchstat.json (artefact, non commité).
Rien ici ne touche l'algo, le site ni les pronostics.

Usage : python scripts/sonde_matchstat.py [--budget 12] [--sackmann /tmp/sackmann] [--chemins "/tennis/v2/{tour}/…"]
Les chemins donnés à --chemins (séparés par des virgules) acceptent {tour} {tid} {p1} {p2} {mid} et sont essayés
sur le premier match de chaque échantillon (utile si la documentation donne le chemin exact du point par point).
"""
import argparse
import collections
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sonde_stats import Client, matchs_de, stats_trouvees, liens, ident, texte, structure  # noqa: E402

HOTE = 'tennis-api-atp-wta-itf.p.rapidapi.com'
SORTIE = 'sonde_matchstat.json'
RESERVE = 30
# Échantillons : (circuit, jour, ce qu'on cherche). Un jour de semaine ordinaire, des années de l'apprentissage
# et du jugement, Challengers en premier (72 % de nos pronostics jugés).
ECHANTILLONS = (('atp', '2019-05-08', 'challenger'), ('atp', '2023-08-02', 'principal'), ('wta', '2024-03-13', 'principal'))
# Chemins candidats pour la feuille d'un match (le premier qui répond avec des statistiques est retenu)
STATS_CANDIDATS = ('/tennis/v2/{tour}/h2h/match-stats/{tid}/{p1}/{p2}',)
MOTS_PBP = re.compile(r'point.?by.?point|pbp|points?_?log|point_?history', re.I)
CORRESP = {  # statistique Sackmann -> mots possibles chez Matchstat
    'ace': re.compile(r'^aces?$|aces', re.I),
    'df': re.compile(r'double', re.I),
    'svpt': re.compile(r'(service|serve).?points?(?!.*won)|svpt|total.?serv', re.I),
}


def norm(s):
    s = unicodedata.normalize('NFD', str(s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c)).replace('-', ' ')
    return re.sub(r'[^a-z ]', ' ', s).split()


def nom_famille(s):
    m = norm(s)
    return m[-1] if m else ''


def joueurs(m):
    """(id1, nom1, id2, nom2) quelle que soit la forme : player1 {id, name} ou player1Id / player1Name…"""
    out = []
    for i in ('1', '2'):
        p = m.get('player' + i) or m.get('p' + i) or {}
        pid = (p.get('id') if isinstance(p, dict) else None) or m.get(f'player{i}Id') or m.get(f'player{i}_id')
        nom = (p.get('name') if isinstance(p, dict) else p if isinstance(p, str) else None) or m.get(f'player{i}Name') or ''
        out += [pid, nom]
    return tuple(out)


def tournoi_de(m):
    t = m.get('tournament') if isinstance(m.get('tournament'), dict) else {}
    return t.get('id') or m.get('tournamentId') or m.get('tournament_id'), (t.get('name') or m.get('tournamentName') or '')


def remplir(modele, tour, tid, m):
    p1, _, p2, _ = joueurs(m)
    return (modele.replace('{tour}', tour).replace('{tid}', str(tid or '')).replace('{p1}', str(p1 or ''))
            .replace('{p2}', str(p2 or '')).replace('{mid}', str(ident(m) or '')))


def quota(c):
    for r in reversed(c.journal):
        q = r.get('quota') or {}
        if q.get('x-ratelimit-requests-remaining') is not None:
            try:
                return int(q['x-ratelimit-requests-remaining']), q.get('x-ratelimit-requests-limit')
            except ValueError:
                pass
    return None, None


def peut(c):
    r, _ = quota(c)
    return c.n < c.max and (r is None or r > RESERVE)


def valeurs_stats(stats):
    """{'ace': (a, b) …} à partir des statistiques repérées (premier objet nommé qui correspond)."""
    out = {}
    for s in stats:
        for cle, mot in CORRESP.items():
            if cle in out or not mot.search(str(s['stat'])):
                continue
            nums = [v for v in s['valeurs'].values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if len(nums) >= 2:
                out[cle] = (nums[0], nums[1])
    return out


# ------------------------------------------------------------------ Sackmann (comparaison et volumes)
def charger_sackmann(dossier, annees=range(2018, 2026)):
    lignes = []
    if not dossier or not os.path.isdir(dossier):
        return lignes
    for f in glob.glob(os.path.join(dossier, '**', '*_matches_*20*.csv'), recursive=True):
        a = re.search(r'(20\d\d)\.csv$', f)
        if not a or int(a.group(1)) not in annees:
            continue
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for r in csv.DictReader(fh):
                r['_fichier'] = os.path.basename(f)
                lignes.append(r)
    return lignes


def volumes(lignes):
    """Matchs et tournois 2018–2025 par niveau suivi (ITF hommes et femmes exclus : pas de pronostic)."""
    v = collections.defaultdict(lambda: {'matchs': 0, 'tournois': set(), 'avec_stats': 0})
    for r in lignes:
        f, niv = r['_fichier'], r.get('tourney_level', '')
        if f.startswith('atp_matches_qual_chall'):
            if niv != 'C':
                continue
            k = 'Challengers'
        elif f.startswith('atp_matches_'):
            k = 'ATP'
        elif f.startswith('wta_matches_qual_itf'):
            if niv != 'C':
                continue
            k = 'WTA 125'
        elif f.startswith('wta_matches_'):
            k = 'WTA'
        else:
            continue
        v[k]['matchs'] += 1
        v[k]['tournois'].add(r.get('tourney_id'))
        v[k]['avec_stats'] += bool(r.get('w_svpt'))
    return {k: {'matchs': x['matchs'], 'tournois': len(x['tournois']), 'avec_stats_sackmann': x['avec_stats']} for k, x in v.items()}


def chercher_sackmann(lignes, nom1, nom2, annee):
    a, b = nom_famille(nom1), nom_famille(nom2)
    for r in lignes:
        if not r.get('tourney_date', '').startswith(str(annee)):
            continue
        w, l = nom_famille(r.get('winner_name')), nom_famille(r.get('loser_name'))
        if {w, l} == {a, b} and a:
            return r, (w == a)
    return None, None


def comparer(vals, ligne, j1_gagnant):
    if not ligne or not vals:
        return None
    out = {}
    for cle, (x1, x2) in vals.items():
        s1 = ligne.get(('w_' if j1_gagnant else 'l_') + cle)
        s2 = ligne.get(('l_' if j1_gagnant else 'w_') + cle)
        if s1 not in (None, '') and s2 not in (None, ''):
            out[cle] = {'matchstat': [x1, x2], 'sackmann': [int(float(s1)), int(float(s2))],
                        'egal': [x1, x2] == [int(float(s1)), int(float(s2))]}
    return out


# ------------------------------------------------------------------ la sonde
def sonder(cle, budget=12, sackmann=None, chemins=(), ouvrir=None, echantillons=ECHANTILLONS):
    c = Client(HOTE, cle, ouvrir, max_req=budget)
    S = charger_sackmann(sackmann)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'budget': budget,
           'reserve_quota': RESERVE, 'echantillons': [], 'chemin_stats': None, 'stats_dans_resultats_tournoi': False,
           'point_par_point': None}
    for tour, jour, quoi in echantillons:
        if not peut(c):
            break
        e = {'circuit': tour, 'jour': jour, 'cherche': quoi}
        rep['echantillons'].append(e)
        fin = (dt.date.fromisoformat(jour) + dt.timedelta(days=1)).isoformat()
        code, doc = c.get(f"/tennis/v2/{tour}/fixtures/{jour}/{fin}?include=tournament&filter=PlayerGroup:singles&pageSize=100&pageNo=1")
        e['matchs_du_jour'] = len(matchs_de(doc)) if code == 200 else 0
        e['code_liste'] = code
        M = matchs_de(doc) if code == 200 else []
        if quoi == 'challenger':
            M = [m for m in M if re.search(r'challenger', tournoi_de(m)[1] + ' ' + texte(m), re.I)] or M
        else:
            M = [m for m in M if not re.search(r'challenger|\bitf\b|\bw\d{2,3}\b|\bm\d{2}\b', tournoi_de(m)[1], re.I)] or M
        if not M:
            continue
        m = M[0]
        tid, tnom = tournoi_de(m)
        e['tournoi'] = tnom
        e['stats_dans_la_liste'] = len(stats_trouvees(m))
        # 1) résultats du tournoi : les statistiques y sont-elles ?
        R = []
        if tid and peut(c):
            code, doc = c.get(f"/tennis/v2/{tour}/tournament/results/{tid}")
            R = [x for x in matchs_de(doc)] if code == 200 else []
            e['resultats_tournoi'] = {'code': code, 'matchs': len(R), 'stats': len(stats_trouvees(R[:3]))}
            if e['resultats_tournoi']['stats']:
                rep['stats_dans_resultats_tournoi'] = True
        cible = next((x for x in R if joueurs(x)[0] and joueurs(x)[2]), m)
        p1, n1, p2, n2 = joueurs(cible)
        e['match'] = f"{n1} – {n2}"
        stats = stats_trouvees(cible) if e.get('resultats_tournoi', {}).get('stats') else []
        # 2) sinon la feuille de match : chemins fournis par l'API, puis candidats connus, puis --chemins
        essais = [x for x in liens(cible) if re.search(r'stat', x, re.I)]
        essais += [remplir(x, tour, tid, cible) for x in STATS_CANDIDATS]
        e['essais_stats'] = []
        for ch in dict.fromkeys(essais):
            if stats or not peut(c):
                break
            code, d2 = c.get(ch)
            st = stats_trouvees(d2) if code == 200 else []
            e['essais_stats'].append({'chemin': re.sub(r'\d{3,}', '…', ch), 'code': code, 'stats': len(st)})
            if st:
                stats = st
                rep['chemin_stats'] = rep['chemin_stats'] or re.sub(r'/\d+', '/{id}', ch)
        e['statistiques'] = [s['stat'] for s in stats][:25]
        vals = valeurs_stats(stats)
        ligne, j1g = chercher_sackmann(S, n1, n2, jour[:4])
        e['comparaison_sackmann'] = comparer(vals, ligne, j1g) if ligne else ('match absent de Sackmann' if S else 'Sackmann non chargé')
        # 3) point par point : liens fournis par l'API, puis --chemins
        pbp = [x for x in liens(cible) if MOTS_PBP.search(x)] + [remplir(x, tour, tid, cible) for x in chemins]
        for ch in dict.fromkeys(pbp):
            if not peut(c):
                break
            code, d3 = c.get(ch)
            n = len(matchs_de(d3)) if code == 200 else 0
            e.setdefault('essais_pbp', []).append({'chemin': re.sub(r'\d{3,}', '…', ch), 'code': code, 'elements': n,
                                                   'structure': json.dumps(structure(d3), ensure_ascii=False)[:400]})
            if code == 200 and n > 10:
                rep['point_par_point'] = re.sub(r'/\d+', '/{id}', ch)
    reste, limite = quota(c)
    rep['quota'] = {'restant': reste, 'limite': limite, 'requetes_faites': c.n}
    vol = volumes(S)
    rep['volumes_2018_2025'] = vol
    par = 'tournois' if rep['stats_dans_resultats_tournoi'] else 'matchs'
    rep['requetes_pour_tout_recuperer'] = {'unite': par, 'total': sum(x[par] for x in vol.values()) if vol else None}
    rep['requetes'] = [{k: v for k, v in r.items() if k != 'structure'} for r in c.journal]
    rep['conclusion'] = conclure(rep)
    return rep


def conclure(rep):
    L = []
    if rep['stats_dans_resultats_tournoi']:
        L.append("Statistiques de match données dans les résultats d'un tournoi : 1 requête par tournoi.")
    elif rep['chemin_stats']:
        L.append(f"Statistiques de match données match par match ({rep['chemin_stats']}) : 1 requête par match.")
    else:
        L.append("Aucune statistique de match obtenue avec cette formule et ces chemins.")
    comp = [x for e in rep['echantillons'] for x in ((e.get('comparaison_sackmann') or {}).values()
                                                    if isinstance(e.get('comparaison_sackmann'), dict) else [])]
    if comp:
        L.append(f"Concordance avec Sackmann : {sum(x['egal'] for x in comp)}/{len(comp)} statistiques identiques.")
    L.append("Point par point : " + (f"disponible ({rep['point_par_point']})." if rep['point_par_point'] else
                                     "non obtenu (donner le chemin exact de la documentation dans « chemins »)."))
    t, q = rep['requetes_pour_tout_recuperer'], rep['quota']
    if t['total']:
        L.append(f"Pour récupérer 2018–2025 : environ {t['total']:,} requêtes ({t['unite']}).".replace(',', ' '))
    if q.get('limite'):
        L.append(f"Formule actuelle : {q['limite']} requêtes par période, {q['restant']} restantes.")
    return L


def main(argv):
    a = argparse.ArgumentParser()
    a.add_argument('--budget', type=int, default=12)
    a.add_argument('--sackmann', default='')
    a.add_argument('--chemins', default='')
    o = a.parse_args(argv[1:])
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    chemins = [x.strip() for x in o.chemins.split(',') if x.strip().startswith('/')][:3]
    rep = sonder(cle, max(1, min(o.budget, 40)), o.sackmann, chemins)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print('===== Sonde Matchstat =====')
    for e in rep['echantillons']:
        print(f"\n[{e['circuit']} {e['jour']} · {e['cherche']}] {e.get('tournoi', '?')} · {e.get('match', '?')}")
        print(f"  liste du jour : {e.get('code_liste')} ({e.get('matchs_du_jour', 0)} matchs) · résultats du tournoi : {e.get('resultats_tournoi')}")
        for x in e.get('essais_stats', []):
            print(f"  feuille : {x['chemin']} -> {x['code']} ({x['stats']} statistiques)")
        print(f"  statistiques : {', '.join(map(str, e.get('statistiques', []))) or 'aucune'}")
        print(f"  Sackmann : {json.dumps(e.get('comparaison_sackmann'), ensure_ascii=False)}")
        for x in e.get('essais_pbp', []):
            print(f"  point par point : {x['chemin']} -> {x['code']} ({x['elements']} éléments) {x['structure'][:200]}")
    print('\n===== Volumes 2018–2025 (Sackmann) =====')
    for k, v in rep['volumes_2018_2025'].items():
        print(f"  {k} : {v['matchs']} matchs, {v['tournois']} tournois, {v['avec_stats_sackmann']} avec statistiques chez Sackmann")
    print('\n===== Conclusion =====')
    for x in rep['conclusion']:
        print('  ' + x)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
