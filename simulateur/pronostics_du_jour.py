#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pronostics_du_jour.py — pronostic de chaque match à venir, deux versions côte à côte (21/10/2026).

  « stats seules »   : force Elo (elo_etat.json, refait chaque run depuis tous
                        les résultats) + style service/retour de chaque joueur
                        (notes_joueurs.json) + forme du jour, dans le moteur ;
  « stats + marché » : même moteur, niveau pris à la cote Pinnacle (marge
                        retirée) quand Pinnacle cote le match.
Pour chaque match : probabilité de victoire, 2-0 / 2-1 / 1-2 / 0-2 (ou en 5
sets), les 3 scores complets les plus probables set par set dans l'ordre réel
(ex. « 4-6 6-3 6-4 »), victoire après la perte du 1er set, set 1, total de jeux
moyen, au moins un tie-break.

JOURNAL : le PREMIER pronostic de chaque match est écrit une fois dans
simulateur/pronostics_log.jsonl et jamais modifié ; le bilan (taux de
vainqueurs devinés des deux versions, sur les matchs joués) se calcule sur ce
journal — un vrai suivi en direct, sans retouche.

MATCH SIMULÉ (22/10/2026) : chaque version est aussi jouée 5 000 fois point
par point (match_simule.py) avec le profil de service des deux joueurs
(profils_service.json : % de 1re balle, aces, doubles fautes, points gagnés
derrière la 1re et la 2e balle, qualité de retour), au niveau de la version.
On en tire la feuille de stats prévue (moyenne et fourchette à 80 %) et un
match type, set par set avec les breaks.

Entrées : matches_oddspapi.json (matchs à venir), simulateur/elo_etat.json,
simulateur/notes_joueurs.json, simulateur/profils_service.json, set_results.json (résultats).
Sorties : Tennis_Edge_Lab/live/pronostics.json, Tennis_Edge_Lab/live/pronostics_bilan.json,
simulateur/pronostics_log.jsonl. 0 requête API.
"""
import datetime as dt
import importlib.util
import json
import math
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as MS  # noqa: E402
import modele as M  # noqa: E402
import nos_resultats as NR  # noqa: E402
import profils_service as PS  # noqa: E402

SIGMA = 0.15
SIMULATIONS = int(os.environ.get('SIMULATIONS', '5000'))
BALLES_CONNU = 500          # profil « connu » : au moins 500 balles de service (pondérées) dans l'archive
HORIZON_H = 36
LOG = 'simulateur/pronostics_log.jsonl'
SORTIE = 'Tennis_Edge_Lab/live/pronostics.json'
BILAN = 'Tennis_Edge_Lab/live/pronostics_bilan.json'


def _books(racine):
    sp = importlib.util.spec_from_file_location('tennis_edge_pj_books', os.path.join(racine, 'Tennis_Edge_Lab', 'books.py'))
    b = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(b)
    return b


def circuit(t):
    t = str(t or '').lower()
    if 'wta' in t or 'women' in t:
        return 'WTA'
    if 'itf' in t:
        return 'ITF'
    if 'challenger' in t:
        return 'CH'
    return 'ATP'


def sig(z):
    return 1 / (1 + math.exp(-z))


class Styles:
    """Service / retour de chaque joueur (notes Sackmann ajustées aux adversaires)."""

    def __init__(self, chemin):
        try:
            doc = json.load(open(chemin, encoding='utf-8'))
        except (OSError, ValueError):
            doc = {}
        self.mu = {}
        for k, v in (doc.get('mu') or {}).items():
            c, _, s = k.partition(' ')
            self.mu[(c, s)] = v
        self.j = {}
        for v in (doc.get('joueurs') or {}).values():
            k = E.cle(v.get('nom'))
            if k and (k not in self.j or v.get('points', 0) > self.j[k][2]):
                self.j[k] = (v.get('service', 0.0), v.get('retour', 0.0), v.get('points', 0))

    def mu_de(self, c, s):
        if (c, s) in self.mu:
            return self.mu[(c, s)]
        v = [x for (cc, _), x in self.mu.items() if cc == c]
        return sum(v) / len(v) if v else 0.5

    def service(self, a, b, c, s):
        """P(A gagne un point sur son service contre B), avant ancrage au niveau."""
        sa, ra = (self.j.get(a) or (0.0, 0.0, 0))[:2]
        sb, rb = (self.j.get(b) or (0.0, 0.0, 0))[:2]
        mu = self.mu_de(c, s)
        return sig(mu + sa - rb), sig(mu + sb - ra)

    def connu(self, a):
        return a in self.j


def pronostic(p_home, c, sg, pa0, pb0):
    """Distribution complète, niveau ancré sur p_home, style (pa0, pb0).

    Scores : les 3 scores COMPLETS les plus probables, set par set et dans l'ordre
    réel (modele.scores_complets : rien n'est supposé — le vainqueur peut perdre le
    1er set). Il y a ~1 500 scores possibles : même le premier dépasse rarement 4 %."""
    a, b = M.ancrer_forme(pa0, pb0, min(max(p_home, 0.01), 0.99), sg, SIGMA, iterations=20)
    r = M.match_forme(a, b, sg, SIGMA)
    sc = M.scores_complets(a, b, sg, SIGMA, top=3)
    return {'p_home': round(r['victoire'], 4),
            'sets': {k: round(v, 4) for k, v in r['sets'].items()},
            'scores_probables': [[s_, round(p_, 4)] for s_, p_ in sc['scores']],
            'remontee': {'home': round(sc['remontee_A'], 4), 'away': round(sc['remontee_B'], 4)},
            'set1_home': round(r['set1'], 4),
            'jeux_moyen': round(M.moyenne(r['total_jeux']), 1),
            'tiebreak': round(r['tiebreak'], 3)}


def charger_profils(racine):
    try:
        with open(os.path.join(racine, 'simulateur', 'profils_service.json'), encoding='utf-8') as f:
            return PS.Profils.importer(json.load(f))
    except (OSError, ValueError, KeyError):
        return None


def match_simule(P, h, a, c, s, sg, p_home, cle):
    """Le match joué SIMULATIONS fois au niveau p_home, avec les profils de service des deux joueurs."""
    ph, nh = P.profil(h, c, s, P.jour_export)
    pa, na = P.profil(a, c, s, P.jour_export)
    mu = P.moyenne(c, s)
    r = MS.simuler(MS.composantes(ph, pa, mu), MS.composantes(pa, ph, mu), p_home, sg, SIMULATIONS, SIGMA, cle=cle)
    r['profil_connu'] = [nh >= BALLES_CONNU, na >= BALLES_CONNU]
    return r


def matchs_a_venir(racine, maintenant):
    try:
        L = json.load(open(os.path.join(racine, 'matches_oddspapi.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    L = L if isinstance(L, list) else list(L.values())
    out = []
    for m in L:
        try:
            debut = dt.datetime.fromisoformat(str(m['commence_time']).replace('Z', '+00:00')).replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        if not (maintenant < debut <= maintenant + dt.timedelta(hours=HORIZON_H)):
            continue
        h, a = m.get('home_team'), m.get('away_team')
        if not h or not a:
            continue
        pin = None
        for bk in m.get('bookmakers') or []:
            if bk.get('key') != 'pinnacle':
                continue
            for mk in bk.get('markets') or []:
                if mk.get('key') == 'h2h':
                    px = {o.get('name'): o.get('price') for o in mk.get('outcomes') or []}
                    if px.get(h) and px.get(a):
                        pin = (float(px[h]), float(px[a]))
        out.append({'debut': debut, 'home': h, 'away': a, 'tournoi': m.get('sport_title') or '', 'pin': pin})
    out.sort(key=lambda x: x['debut'])
    return out


def construire(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.utcnow()
    books = _books(racine)
    etat = json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8'))
    elo = E.Elo.importer(etat['joueurs'])
    surf = etat.get('surfaces_tournois') or {}
    S = Styles(os.path.join(racine, 'simulateur', 'notes_joueurs.json'))
    PR = charger_profils(racine)
    venir = matchs_a_venir(racine, maintenant)
    # Un joueur = un classement : alias du dernier calcul, puis noms nouveaux reliés au joueur connu.
    alias = dict(etat.get('alias') or {})
    alias.update(E.unifier({k: v.get('nom', k) for k, v in etat['joueurs'].items()},
                           [n for x in venir for n in (x['home'], x['away'])]))
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))
    out = []
    for x in venir:
        h, a = cle_c(x['home']), cle_c(x['away'])
        c = circuit(x['tournoi'])
        if etat.get('depart_bas') and c in ('CH', 'ITF'):
            elo.presenter(h, etat['depart_bas'])
            elo.presenter(a, etat['depart_bas'])
        s = NR.surface_de(x['tournoi'], surf)
        sg = 3 if NR.cinq_sets(x['tournoi']) else 2
        pa0, pb0 = S.service(h, a, c, s)
        stats = pronostic(elo.proba(h, a, s), c, sg, pa0, pb0)
        marche = None
        if x['pin'] and min(x['pin']) > 1:
            k = books.power_exponent(*x['pin'])
            ph = (1 / x['pin'][0]) ** k if k else (1 / x['pin'][0]) / (1 / x['pin'][0] + 1 / x['pin'][1])
            marche = pronostic(ph, c, sg, pa0, pb0)
        uid = f"{x['debut'].date()}_{NR.slug(x['home'])}_{NR.slug(x['away'])}"
        if PR is not None:
            for nom_v, v in (('stats', stats), ('marche', marche)):
                if v:
                    v['match_simule'] = match_simule(PR, h, a, c, s, sg, v['p_home'], f"{uid}|{nom_v}")
        out.append({'uid': uid,
                    'debut': x['debut'].isoformat(timespec='minutes'), 'tournoi': x['tournoi'], 'circuit': c,
                    'surface': s, 'meilleur_des': 2 * sg - 1, 'home': x['home'], 'away': x['away'],
                    'matchs_joues': [elo.matchs(h), elo.matchs(a)], 'style_connu': [S.connu(h), S.connu(a)],
                    'stats': stats, 'marche': marche})
    return {'genere_le': maintenant.isoformat(timespec='seconds') + 'Z', 'elo_au': etat.get('dernier_match'),
            'horizon_h': HORIZON_H, 'sigma': SIGMA, 'simulations': SIMULATIONS if PR is not None else 0,
            'profils_au': PR.jour_export.isoformat() if PR is not None else None, 'matchs': out}


SUIVI_STATS = ('aces', 'doubles_fautes', 'premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct', 'breaks', 'jeux')


def feuille_prevue(m):
    """Feuille simulée gardée au journal (version marché si Pinnacle cote, sinon stats seules) :
    {stat: [[moy, p10, p90] home, [..] away]} + total de jeux."""
    v = m['marche'] if m.get('marche') and m['marche'].get('match_simule') else m['stats']
    S = (v or {}).get('match_simule')
    if not S:
        return None
    out = {'version': 'marche' if v is m.get('marche') else 'stats'}
    for k in SUIVI_STATS:
        a, b = S['feuille'][0].get(k), S['feuille'][1].get(k)
        if a and b:
            out[k] = [[a['moy'], a['p10'], a['p90']], [b['moy'], b['p10'], b['p90']]]
    if S.get('jeux'):
        out['total_jeux'] = [S['jeux']['moy'], S['jeux']['p10'], S['jeux']['p90']]
    return out


def suivi_feuilles(racine, lignes):
    """Match simulé contre la vraie feuille (feuilles/ collectées) : par statistique, prévu moyen,
    réel moyen, écart moyen absolu et part des réels dans la fourchette à 80 % (bornes incluses)."""
    avec = [r for r in lignes if r.get('feuille')]
    if not avec:
        return {'n': 0}
    jours = sorted(r['debut'][:10] for r in avec)
    debut = (dt.date.fromisoformat(jours[0]) - dt.timedelta(days=1)).isoformat()
    idx = FE.Index(FE.lire(racine, depuis=debut))
    acc = {k: [] for k in SUIVI_STATS + ('total_jeux',)}
    n = 0
    for r in avec:
        fi, inv = idx.trouver(r['debut'][:10], r['home'], r['away'])
        if not fi or str((fi.get('statut') or {}).get('texte') or '').lower() != 'ended':
            continue
        reel = FE.feuille_reelle(fi, inv)
        if not reel:
            continue
        (fh, fa), tot = reel
        n += 1
        for k in SUIVI_STATS:
            if k in r['feuille']:
                for i, f in ((0, fh), (1, fa)):
                    moy, lo, hi = r['feuille'][k][i]
                    acc[k].append((moy, lo, hi, f[k]))
        if 'total_jeux' in r['feuille']:
            moy, lo, hi = r['feuille']['total_jeux']
            acc['total_jeux'].append((moy, lo, hi, tot))
    out = {'n': n, 'stats': {}}
    for k, L in acc.items():
        if L:
            out['stats'][k] = {'n': len(L), 'prevu': round(sum(x[0] for x in L) / len(L), 2),
                               'reel': round(sum(x[3] for x in L) / len(L), 2),
                               'ecart_moyen': round(sum(abs(x[0] - x[3]) for x in L) / len(L), 2),
                               'dans_fourchette_pct': round(100 * sum(x[1] <= x[3] <= x[2] for x in L) / len(L), 1)}
    return out


def journaliser(racine, doc):
    chemin = os.path.join(racine, LOG)
    deja = set()
    try:
        with open(chemin, encoding='utf-8') as f:
            for l in f:
                try:
                    deja.add(json.loads(l)['uid'])
                except (ValueError, KeyError):
                    continue
    except OSError:
        pass
    n = 0
    with open(chemin, 'a', encoding='utf-8') as f:
        for m in doc['matchs']:
            if m['uid'] in deja:
                continue
            f.write(json.dumps({'uid': m['uid'], 'pronostique_le': doc['genere_le'], 'debut': m['debut'],
                                'home': m['home'], 'away': m['away'], 'tournoi': m['tournoi'], 'circuit': m['circuit'],
                                'stats': {'p_home': m['stats']['p_home'], 'sets': m['stats']['sets']},
                                'marche': ({'p_home': m['marche']['p_home'], 'sets': m['marche']['sets']} if m['marche'] else None),
                                'feuille': feuille_prevue(m)},
                               ensure_ascii=False) + '\n')
            n += 1
    return n


def bilan(racine, maintenant=None):
    """Taux de vainqueurs devinés sur le journal (matchs joués, résultat connu)."""
    maintenant = maintenant or dt.datetime.utcnow()
    try:
        sr = json.load(open(os.path.join(racine, 'set_results.json'), encoding='utf-8'))
    except (OSError, ValueError):
        sr = {}
    vus, L, journal = set(), [], []
    try:
        lignes = open(os.path.join(racine, LOG), encoding='utf-8').read().splitlines()
    except OSError:
        lignes = []
    for l in lignes:
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r['uid'] in vus:
            continue
        vus.add(r['uid'])
        journal.append(r)
        d0 = dt.date.fromisoformat(r['debut'][:10])
        res, sens = NR.resultat(sr, d0, r['home'], r['away'])
        if not res:
            continue
        o = (lambda v: v) if sens == 1 else (lambda v: {'home': 'away', 'away': 'home'}.get(v))
        g, s1, s2 = o(res.get('match')), o(res.get('set1')), o(res.get('set2'))
        sets = None
        if s1 in ('home', 'away') and s2 in ('home', 'away') and not (s1 == s2 and g != s1) and len(r['stats']['sets']) == 4:
            sets = ('2-0' if g == 'home' else '0-2') if s1 == s2 else ('2-1' if g == 'home' else '1-2')
        L.append(dict(r, gagnant=g, sets_reel=sets))

    def bloc(items, cle):
        it = [x for x in items if x.get(cle)]
        n = len(it)
        if not n:
            return {'n': 0}
        ok = sum(1.0 if (x[cle]['p_home'] > 0.5) == (x['gagnant'] == 'home') and x[cle]['p_home'] != 0.5 else
                 (0.5 if x[cle]['p_home'] == 0.5 else 0.0) for x in it)
        s = [x for x in it if x['sets_reel']]
        sj = sum(max(x[cle]['sets'], key=x[cle]['sets'].get) == x['sets_reel'] for x in s)
        return {'n': n, 'reussite_pct': round(100 * ok / n, 1),
                'score_sets_juste_pct': round(100 * sj / len(s), 1) if s else None, 'n_sets': len(s)}
    depuis7 = (maintenant - dt.timedelta(days=7)).date().isoformat()
    doc = {'genere_le': maintenant.isoformat(timespec='seconds') + 'Z', 'pronostiques': len(vus), 'joues_avec_resultat': len(L),
           'tous': {'stats_seules': bloc(L, 'stats'), 'stats_plus_marche': bloc(L, 'marche')},
           '7_derniers_jours': {'stats_seules': bloc([x for x in L if x['debut'] >= depuis7], 'stats'),
                                'stats_plus_marche': bloc([x for x in L if x['debut'] >= depuis7], 'marche')},
           'derniers': [{'debut': x['debut'], 'home': x['home'], 'away': x['away'], 'gagnant': x['gagnant'],
                         'stats': x['stats']['p_home'], 'marche': (x['marche'] or {}).get('p_home')}
                        for x in sorted(L, key=lambda x: x['debut'])[-30:]],
           'match_simule_contre_feuille': suivi_feuilles(racine, journal)}
    return doc


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    doc = construire(racine)
    os.makedirs(os.path.join(racine, 'Tennis_Edge_Lab', 'live'), exist_ok=True)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    n = journaliser(racine, doc)
    b = bilan(racine)
    with open(os.path.join(racine, BILAN), 'w', encoding='utf-8') as f:
        json.dump(b, f, ensure_ascii=False, indent=1)
    t = b['tous']
    print(f"Pronostics : {len(doc['matchs'])} matchs dans les {HORIZON_H} h ({n} nouveaux au journal) · "
          f"bilan sur {b['joues_avec_resultat']} matchs joués : stats {t['stats_seules'].get('reussite_pct')} % · "
          f"marché {t['stats_plus_marche'].get('reussite_pct')} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
