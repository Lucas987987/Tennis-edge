#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vitrine.py — les données du site public de l'algorithme (23/10/2026) : algo/donnees.json.

Le site public (algo/index.html, en français et en anglais) montre :
  — chaque match des prochaines heures en entier : % de victoire, cote juste (1 / %), sets, scores
    probables, feuille prévue et scénario représentatif rejouable point par point ;
  — le MATCH DU JOUR, toujours choisi séparément par sa règle fixe, sans influencer les autres simulations ;
  — le BILAN PUBLIC : tous les matchs pronostiqués depuis le début du journal, sans tri, pertes comprises ;
  — la CALIBRATION : ce que l'algo annonçait contre ce qui s'est passé (en direct, et rejoué hors échantillon).

Préversion Plus : le détail complet (sets, scores, feuille, simulation) est publié pour TOUS les matchs afin
de tester le catalogue et les parcours. Si une offre payante est activée plus tard, les éléments réservés
devront être déplacés vers un service à accès contrôlé : un simple masquage visuel ne protégerait pas ce JSON.

Rien d'autre ne sort : ni cote de bookmaker, ni signal d'alerte, ni canal privé. L'algo est une source
indépendante : il ne regarde pas le marché, le site non plus.

Règle du MATCH DU JOUR (fixée le 23/10/2026, avant toute publication) : parmi les matchs du jour (heure de
Paris) pas encore commencés au premier passage, ATP et WTA d'abord (Challenger seulement s'il n'y a rien
d'autre) ; l'affiche la plus forte = la plus grande somme des Elo des deux joueurs. Une fois choisi, le match
du jour ne change plus de la journée. La confiance de l'algo n'entre JAMAIS dans le choix : sinon le bilan
serait trié.

Règle du BILAN (fixée le 23/10/2026) : chaque match ATP, WTA et Challenger du journal depuis le 21/10/2026
(début du journal, premier pronostic jamais modifié), jugé sur le DERNIER pronostic affiché avant le début du
match (à défaut, le premier). Abandons et forfaits exclus (ils ne jugent pas un pronostic).
Usage : python simulateur/vitrine.py [racine]
"""
import datetime as dt
import gzip
import json
import math
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join('algo', 'donnees.json')
DEBUT_BILAN = '2026-10-21'
CIRCUITS = ('ATP', 'WTA', 'CH')
VERSIONS = ('combinaison', 'simulation', 'stats')
BACS = [i / 10 for i in range(11)]
PARIS = dt.timezone(dt.timedelta(hours=2))          # remplacé par zoneinfo si disponible


def _paris():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo('Europe/Paris')
    except Exception:  # noqa: BLE001
        return PARIS


# joueur pas encore connu (« vainqueur du quart 1 ») : pas de pronostic public
PROVISOIRE = re.compile(r'^(?:W|L)(?:QF|SF|F|R\d+|Q)\d*$|^(?:TBD|TBA|Qualifier)$', re.I)


def connu(m):
    return not (PROVISOIRE.match(str(m.get('home') or '').strip()) or PROVISOIRE.match(str(m.get('away') or '').strip()))


def _lire(chemin, defaut=None):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def version(m):
    """Version affichée d'un pronostic : Simulation + Elo, sinon simulation, sinon Elo."""
    for k in VERSIONS:
        v = m.get(k)
        if isinstance(v, dict) and v.get('p_home') is not None:
            return k, v
    return None, None


def cote(p):
    return round(1 / p, 2) if p and p > 0.001 else None


def _utc(s):
    d = dt.datetime.fromisoformat(str(s))
    return d.replace(tzinfo=dt.timezone.utc) if d.tzinfo is None else d


def jour_paris(s):
    return _utc(s).astimezone(_paris()).date().isoformat()


def elo_de(etat, cle):
    j = ((etat or {}).get('joueurs') or {}).get(cle) or {}
    return float(j.get('elo') or 1200.0)


def choisir_match_du_jour(matchs, etat, maintenant, precedent=None):
    """Règle fixe (voir l'en-tête). precedent : le choix déjà publié (gardé toute la journée)."""
    jour = maintenant.astimezone(_paris()).date().isoformat()
    if precedent and precedent.get('jour') == jour and any(m['uid'] == precedent.get('uid') for m in matchs):
        return precedent
    du_jour = [m for m in matchs if jour_paris(m['debut']) == jour and _utc(m['debut']) > maintenant
               and m.get('circuit') in CIRCUITS and version(m)[1]]
    if not du_jour:
        return None
    principal = [m for m in du_jour if m['circuit'] in ('ATP', 'WTA')]
    pool = principal or du_jour
    cles = lambda m: (m.get('cles') or [None, None])
    m = max(pool, key=lambda x: (elo_de(etat, cles(x)[0]) + elo_de(etat, cles(x)[1]), x['uid']))
    return {'jour': jour, 'uid': m['uid'],
            'elo': [round(elo_de(etat, cles(m)[0])), round(elo_de(etat, cles(m)[1]))]}


def _feuille_prevue(v):
    f = ((v.get('match_simule') or {}).get('feuille')) or []
    out = []
    for j in f[:2]:
        out.append({k: round((j.get(k) or {}).get('moy'), 1) for k in
                    ('aces', 'doubles_fautes', 'breaks', 'premiere_pct', 'jeux_service_gagnes_pct')
                    if isinstance(j.get(k), dict) and j[k].get('moy') is not None})
    return out or None


def _feuille_fourchette(v):
    """29/10/2026 — fourchette 80 % (10e–90e centile des simulations) de chaque statistique annoncée, par joueur :
    sert à mesurer après le match si ce qui est annoncé tient (apres_match.py)."""
    f = ((v.get('match_simule') or {}).get('feuille')) or []
    out = []
    for j in f[:2]:
        out.append({k: [j[k]['p10'], j[k]['p90']] for k in ('aces', 'doubles_fautes', 'breaks', 'premiere_pct')
                    if isinstance(j.get(k), dict) and j[k].get('p10') is not None and j[k].get('p90') is not None})
    return out if len(out) == 2 and any(out) else None


def _scores_public(v):
    """Classement exact en priorité ; les fréquences simulées restent séparées."""
    exact = v.get('scores_exact') or {}
    sim = v.get('match_simule') or {}
    return (exact.get('scores') or v.get('scores_probables') or sim.get('scores') or [])[:3]


def ligne_match(m, complet):
    k, v = version(m)
    p = float(v['p_home'])
    out = {'uid': m['uid'], 'debut': m['debut'], 'debut_utc': m.get('debut_utc'),
           'horodatage': m.get('horodatage'), 'tournoi': m.get('tournoi'), 'circuit': m.get('circuit'),
           'surface': m.get('surface'), 'meilleur_des': m.get('meilleur_des', 3),
           'home': m['home'], 'away': m['away'], 'p_home': round(p, 3), 'version': k,
           'fiabilite': m.get('fiabilite'), 'cotes_justes': [cote(p), cote(1 - p)]}
    if m.get('controle'):
        out['controle'] = m['controle']             # 29/10/2026 : modèle fantôme (Elo d'avant les changements)
    cb_ = m.get('combinaison') or {}
    if cb_.get('p_elo') is not None and cb_.get('p_simulation') is not None:
        # 29/10/2026 : les deux modèles avant mélange — suivi de leurs désaccords après le match (apres_match.py)
        out['modeles'] = {'p_elo': round(float(cb_['p_elo']), 4), 'p_simulation': round(float(cb_['p_simulation']), 4)}
    if m.get('activite'):
        out['activite'] = m['activite']             # 29/10/2026 : activité récente des deux joueurs (activite.py)
    if m.get('echanges'):
        out['echanges'] = m['echanges']             # 30/10/2026 : longueur des échanges (echanges_joueur.py)
    if m.get('forme_service'):
        out['forme_service'] = m['forme_service']   # 29/10/2026 : service / retour du moment (forme_service.py)
    if not complet:
        out['simulation_disponible'] = False
        return out
    d = m.get('direct') or {}
    sim = v.get('match_simule') or {}
    exact = v.get('scores_exact') or {}
    out.update({
        'simulation_disponible': bool(d.get('a') and d.get('b') and sim.get('match_type')),
        'sets': v.get('sets'),
        'scores_probables': _scores_public(v),
        'scores_source': 'exact' if exact else 'repli_ancien_format',
        'distribution_scores': exact.get('distribution'),
        'scores_simules': (sim.get('scores') or [])[:3],
        'jeux_moyen': v.get('jeux_moyen'),
        'tiebreak': v.get('tiebreak'),
        'set1_home': v.get('set1_home'),
        'feuille_prevue': _feuille_prevue(v),
        'feuille_fourchette': _feuille_fourchette(v),
        'simulation': ({'a': round(d['a'], 4), 'b': round(d['b'], 4),
                        'sets_gagnants': int(d.get('sets_gagnants') or (3 if m.get('meilleur_des') == 5 else 2)),
                        'tb_final': int(d.get('tb_final') or 7), 'n': int(sim.get('n') or 0),
                        'version': k, 'scenario': sim.get('match_type'),
                        'stabilite_score': sim.get('stabilite_score')}
                       if d.get('a') and d.get('b') else None),
    })
    return out


def ajouter_styles_descriptifs(lignes, document):
    """Ajoute seulement un descriptif par UID ; ne recalcule aucune sortie du modèle."""
    styles = (document or {}).get('matchs') or {}
    for ligne in lignes:
        bloc = styles.get(ligne.get('uid'))
        if bloc and bloc.get('descriptif_seulement') is True and len(bloc.get('joueurs') or []) == 2:
            # Les résidus du challenger restent hors du document public.
            ligne['styles_descriptifs'] = {'descriptif_seulement': True, 'joueurs': bloc['joueurs']}
    return lignes


def ajouter_rythme(lignes, document, alias=None):
    """28/10/2026 — durée prévue et profils de rythme / longueur / régularité (profil_rythme.py). Descriptif."""
    import elo as E
    import profil_rythme as PR
    profils = (document or {}).get('joueurs') or {}
    bases = (document or {}).get('bases_log_secondes_par_point') or {}
    refs = (document or {}).get('references_circuit') or {}
    if not profils or not bases:
        return lignes
    alias = alias or {}
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    champs = ('matchs', 'points_par_match', 'jeux_par_match', 'minutes_par_match', 'tiebreak_pct', 'trois_sets_pct',
              'rythme_pct')
    for ligne in lignes:
        joueurs = []
        for nom in (ligne.get('home'), ligne.get('away')):
            pf = profils.get(cle_c(nom))
            joueurs.append(dict({k: pf.get(k) for k in champs},
                                regularite=(pf.get('regularite') or {}).get('niveau'),
                                regularite_centile=(pf.get('regularite') or {}).get('centile')) if pf else None)
        prev = PR.prevision(ligne, profils, bases, cle_c)
        if prev or any(joueurs):
            ligne['rythme'] = {'descriptif_seulement': True, 'prevision': prev, 'joueurs': joueurs,
                               'reference': refs.get(ligne.get('circuit'))}     # repère du circuit (phrases du site)
    return lignes


def bilan_lignes(racine, resultats):
    """28/10/2026 : lignes figées avant le match (lignes_algo.journaliser) contre les scores réels."""
    import lignes_algo as MD
    scores = {}
    for m in (resultats or {}).get('matchs') or []:
        reel = m.get('reel') or {}
        if reel.get('interrompu') or reel.get('score_invalide') or not reel.get('score'):
            continue
        try:
            sets = [tuple(int(v.split('(')[0]) for v in s_.split('-')) for s_ in str(reel['score']).split()]
        except ValueError:
            continue
        scores[m['uid']] = sets
    return MD.bilan_lignes(racine, scores)


def _juge(m):
    """(p_home, gagnant) du pronostic jugé : dernier avant le match, sinon premier."""
    for bloc in ('dernier', 'premier'):
        b = m.get(bloc) or {}
        for k in VERSIONS:
            v = b.get(k)
            if isinstance(v, dict) and v.get('p_home') is not None and v.get('vainqueur_juste') is not None:
                return float(v['p_home']), k
    return None, None


def _mesures(points):
    """points : [(p annoncée pour le vainqueur RÉEL… non : p_home, y_home)]."""
    n = len(points)
    if not n:
        return None
    eps = 1e-6
    brier = sum((p - y) ** 2 for p, y in points) / n
    ll = -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in points) / n
    ok = sum(1 for p, y in points if (p > 0.5) == (y == 1))
    return {'n': n, 'vainqueurs': ok, 'pct': round(100 * ok / n, 1), 'brier': round(brier, 4),
            'log_loss': round(ll, 4)}


def calibration(points, n_min=20):
    """Vu des DEUX joueurs : chaque match compte deux fois (p et 1 − p)."""
    deux = []
    for p, y in points:
        deux += [(p, y), (1 - p, 1 - y)]
    out = []
    for lo, hi in zip(BACS, BACS[1:]):
        s = [(p, y) for p, y in deux if lo <= p < hi or (hi == 1.0 and p == 1.0)]
        if len(s) >= n_min:
            out.append({'de': lo, 'a': hi, 'n': len(s), 'prevu': round(100 * sum(p for p, _ in s) / len(s), 1),
                        'reel': round(100 * sum(y for _, y in s) / len(s), 1)})
    return out


def bilan(resultats, debut=DEBUT_BILAN, seulement=None):
    lignes, points, par_c, par_jour = [], [], {}, {}
    for m in (resultats or {}).get('matchs') or []:
        if m.get('circuit') not in CIRCUITS or str(m.get('debut'))[:10] < debut or not connu(m):
            continue
        if seulement and not seulement(m):
            continue
        reel = m.get('reel') or {}
        if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        p, k = _juge(m)
        if p is None:
            continue
        y = 1 if reel['gagnant'] == 'home' else 0
        points.append((p, y))
        par_c.setdefault(m['circuit'], []).append((p, y))
        par_jour.setdefault(jour_paris(m['debut']), []).append((p, y))
        lignes.append({'uid': m.get('uid'), 'debut': m['debut'], 'tournoi': m.get('tournoi'), 'circuit': m['circuit'],
                       'home': m['home'], 'away': m['away'], 'p_home': round(p, 3),
                       'gagnant': reel['gagnant'], 'score': reel.get('score'), 'juste': (p > 0.5) == (y == 1),
                       'fiabilite': m.get('fiabilite')})
    lignes.sort(key=lambda x: x['debut'], reverse=True)
    par_circuit = {}
    for c, v in par_c.items():
        jours_c = {}
        for x in lignes:
            if x['circuit'] == c:
                y = 1 if x['gagnant'] == 'home' else 0
                jours_c.setdefault(jour_paris(x['debut']), []).append((x['p_home'], y))
        par_circuit[c] = dict(_mesures(v), courbe=_courbe(jours_c),
                              derniers=[x for x in lignes if x['circuit'] == c][:40])
    return {'depuis': debut, 'global': _mesures(points), 'par_circuit': par_circuit,
            'calibration': calibration(points), 'courbe': _courbe(par_jour), 'derniers': lignes[:40]}


COURBE_N_MIN = 10        # la courbe démarre quand 10 matchs sont jugés (avant : un pourcentage sur 3 matchs)


def _courbe(par_jour):
    """Taux de vainqueurs trouvés cumulé jour après jour (Europe/Paris)."""
    cumul, out = [], []
    for j in sorted(par_jour):
        cumul += par_jour[j]
        if len(cumul) >= COURBE_N_MIN:
            mm = _mesures(cumul)
            out.append({'jour': j, 'n': mm['n'], 'pct': mm['pct']})
    return out


def rejoue(racine):
    """Calibration rejouée hors échantillon (entrainement_progressif.py : chaque semaine prédite avec un modèle
    entraîné sur les semaines d'avant). Version Simulation + Elo."""
    p = os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz')
    points, jours = [], []
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for l in f:
                r = json.loads(l)
                if r.get('circuit') in CIRCUITS and r.get('p_algo') is not None:
                    points.append((float(r['p_algo']), 1 if r['gagnant'] == 'home' else 0))
                    jours.append(r['jour'])
    except (OSError, ValueError):
        return None
    if not points:
        return None
    return {'du': min(jours), 'au': max(jours), 'global': _mesures(points), 'calibration': calibration(points)}


NIVEAUX_FIABILITE = ('fragile', 'prudent', 'correct', 'solide')


def perte_attendue(p):
    """Log loss MOYENNE attendue si la probabilité annoncée p est juste (entropie) : un match à 55 % « coûte »
    naturellement plus qu'un match à 85 %."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(p * math.log(p) + (1 - p) * math.log(1 - p))


def par_niveau_fiabilite(matchs, cle='niveau'):
    """29/10/2026 — par niveau de fiabilité : vainqueurs trouvés, confiance annoncée et PERTE EXCÉDENTAIRE (log loss
    réelle − log loss attendue vu les probabilités annoncées). Comparer les niveaux sur le taux de vainqueurs trompe :
    les notes hautes vont souvent à des matchs serrés. Perte excédentaire ≈ 0 : l'annonce tient ; > 0 : plus d'erreur
    que prévu. Descriptif ; la règle de jugement de la note reste celle de rapport_validation_fiabilite.json."""
    par = {}
    for m in matchs:
        reel = m.get('reel') or {}
        niv = (m.get('fiabilite') or {}).get(cle)
        if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away') or niv not in NIVEAUX_FIABILITE:
            continue
        p, _ = _juge(m)
        if p is None:
            continue
        y = 1 if reel['gagnant'] == 'home' else 0
        q = min(max(p if y else 1 - p, 1e-6), 1 - 1e-6)
        par.setdefault(niv, []).append((max(p, 1 - p), (p >= .5) == (y == 1), -math.log(q), perte_attendue(p)))
    out = {}
    for niv in NIVEAUX_FIABILITE:
        L = par.get(niv) or []
        if L:
            n = len(L)
            out[niv] = {'n': n, 'vainqueurs_pct': round(100 * sum(x[1] for x in L) / n, 1),
                        'confiance_pct': round(100 * sum(x[0] for x in L) / n, 1),
                        'perte_excedentaire': round(sum(x[2] - x[3] for x in L) / n, 4),
                        'conclusion_possible': n >= 30}
    return out


def validation_fiabilite(resultats):
    """Cohorte strictement prospective de la fiabilité circuit.

    Une note recalculée sur un match déjà journalisé ne le fait pas entrer dans
    cette cohorte : la date du premier enregistrement doit elle aussi suivre
    l'activation. Les probabilités et le bilan historique restent inchangés.
    """
    sys.path.insert(0, ICI)
    from fiabilite import ACTIVE_LE, VERSION_FIABILITE

    def eligible(m):
        f = m.get('fiabilite') or {}
        return (f.get('version_fiabilite') == VERSION_FIABILITE
                and str(m.get('pronostique_le') or '')[:10] >= ACTIVE_LE)

    out = bilan(resultats, debut=ACTIVE_LE, seulement=eligible)
    out['par_niveau'] = par_niveau_fiabilite([m for m in resultats.get('matchs') or [] if eligible(m)])
    # 29/10/2026 : note v2 (sans la calibration) en fantôme, jugée seulement à partir du 30/10
    from fiabilite import ACTIVE_V2_LE, VERSION_V2
    out['v2'] = {'version': VERSION_V2, 'depuis': ACTIVE_V2_LE, 'par_niveau': par_niveau_fiabilite(
        [m for m in resultats.get('matchs') or [] if (m.get('fiabilite') or {}).get('version_v2') == VERSION_V2
         and str(m.get('pronostique_le') or '')[:10] >= ACTIVE_V2_LE], 'niveau_v2')}
    out.update({'version': VERSION_FIABILITE, 'depuis': ACTIVE_LE,
                'regle': "Premiers pronostics enregistrés après activation, portant la version circuit_v1 ; aucun ancien match recalculé."})
    return out


def qualite_donnees(racine, resultats=None):
    from qualite_donnees import auditer, couverture_pronostiques
    doc = _lire(os.path.join(racine, 'simulateur', 'profils_service.json'), {}) or {}
    out = auditer(doc)
    if out is not None:
        try:                                    # 29/10/2026 : joueurs actifs (30 derniers jours), le chiffre de tête
            from qualite_donnees import actifs
            out['actifs'] = actifs(doc, racine)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::joueurs actifs non calculés : {type(e).__name__}: {e}")
    if out is not None and resultats:
        # 28/10/2026 : couverture des joueurs réellement pronostiqués (mêmes matchs que le tableau des scores)
        matchs = [m for m in resultats.get('matchs') or [] if m.get('circuit') in CIRCUITS
                  and str(m.get('debut'))[:10] >= DEBUT_BILAN and connu(m)]

        def juge(m):
            reel = m.get('reel') or {}
            if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
                return None
            p, _ = _juge(m)
            return None if p is None else (p, 1 if reel['gagnant'] == 'home' else 0)
        out['pronostiques'] = couverture_pronostiques(doc, matchs, juge)
    return out


STATS_TEST = ('aces', 'doubles_fautes', 'premiere_pct', 'breaks', 'gagnes_1re_pct', 'gagnes_2e_pct', 'jeux', 'total_jeux')


def fiabilite_stats(racine, analyse=None):
    """29/10/2026 — ce qui est annoncé contre ce qui se passe : en direct (nos matchs, apres_match.analyser) par circuit,
    et le test sur matchs passés (rapport_match_simule.json, version ancrée sur l'Elo, la plus proche de la production).
    Même règle de fiabilité pour les deux (apres_match.fiabilite_stat)."""
    import apres_match as AM
    g = (analyse or {}).get('groupes') or {}
    direct = {k: {'matchs': v.get('matchs'), 'stats': v.get('stats') or {}, 'lignes': v.get('lignes') or {}}
              for k, v in g.items() if isinstance(v, dict)}
    test = None
    R = _lire(os.path.join(racine, 'simulateur', 'rapport_match_simule.json'), {}) or {}
    V = (R.get('versions') or {}).get('stats_seules') or {}
    if V:
        test = {'periode': R.get('periode'), 'matchs': R.get('matchs_simules'), 'stats': {}}
        for k in STATS_TEST:
            x = V.get(k) or {}
            if x.get('couverture_80_pct') is None:
                continue
            n = int(x.get('n') or 0)
            dans, sous, dessus = x['couverture_80_pct'], x.get('sous_p10_pct') or 0.0, x.get('au_dessus_p90_pct') or 0.0
            pos = [0] * round(n * dans / 100) + [-1] * round(n * sous / 100) + [1] * round(n * dessus / 100)
            fi = AM.fiabilite_stat(pos, [])['fiabilite'] if pos else 'rien'
            test['stats'][k] = {'n': n, 'dans_fourchette_pct': dans, 'sous_pct': sous, 'dessus_pct': dessus,
                                'erreur_moyenne': x.get('mae'), 'gain_vs_naif_pct': x.get('gain_vs_naif_pct'),
                                'correlation': x.get('correlation'), 'fiabilite': fi}
    return {'en_direct': direct, 'test': test}


def desaccords(racine, analyse=None):
    """29/10/2026 — quand l'Elo et la simulation ne désignent pas le même vainqueur : qui avait raison ? En direct (nos
    matchs, apres_match) par circuit, et la référence sur les pronostics hors échantillon (entraînement semaine après
    semaine, depuis juin). Descriptif : ce sont les arbres, jugés chaque semaine, qui apprennent quoi en faire."""
    g = (analyse or {}).get('groupes') or {}
    direct = {k: v['desaccord'] for k, v in g.items() if isinstance(v, dict) and v.get('desaccord')}
    ref = {}
    try:
        with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
            X = [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        X = []
    for c in ('TOUS',) + CIRCUITS:
        L = [x for x in X if x.get('p_algo') is not None and (c == 'TOUS' or x.get('circuit') == c)]
        D_ = [x for x in L if (x['p_elo'] >= .5) != (x['p_sim'] >= .5)]
        if not D_:
            continue
        juste = lambda p, x: (p >= .5) == (x['gagnant'] == 'home')
        A_ = [x for x in L if (x['p_elo'] >= .5) == (x['p_sim'] >= .5)]
        ref[c] = {'matchs': len(L), 'desaccords': len(D_), 'part_pct': round(100 * len(D_) / len(L), 1),
                  'elo_pct': round(100 * sum(juste(x['p_elo'], x) for x in D_) / len(D_), 1),
                  'simulation_pct': round(100 * sum(juste(x['p_sim'], x) for x in D_) / len(D_), 1),
                  'affiche_pct': round(100 * sum(juste(x['p_algo'], x) for x in D_) / len(D_), 1),
                  'accord_pct': round(100 * sum(juste(x['p_algo'], x) for x in A_) / len(A_), 1) if A_ else None}
    return {'en_direct': direct, 'reference': ref} if (direct or ref) else None


def journal_changements(racine, analyse=None):
    """29/10/2026 — journal des changements du modèle (simulateur/journal_changements.json) + comparaison en direct du
    modèle fantôme (Elo en place contre Elo d'avant les changements, sur les mêmes matchs réels)."""
    doc = _lire(os.path.join(racine, 'simulateur', 'journal_changements.json'), {}) or {}
    if not doc:
        return None
    g = ((analyse or {}).get('groupes') or {})
    doc['fantome'] = {k: v['fantome'] for k, v in g.items() if isinstance(v, dict) and v.get('fantome')}
    # 29/10/2026 : un fantôme par changement (ITF hommes + femmes ensemble, ITF femmes seules, σ du Challenger)
    T = g.get('TOUS') or {}
    doc['fantomes'] = [dict(T[k], cle=k) for k in ('fantome', 'fantome_itf_femmes', 'fantome_sigma', 'fantome_forme_service') if T.get(k)]
    return doc


ABANDON_J = 90


def ajouter_abandons(lignes, racine, maintenant=None):
    """ligne['abandon_recent'] = [jours depuis le dernier abandon de home, de away] (≤ 90 jours, sinon None)."""
    import elo as E
    import feuilles as FE
    dern = {}
    for r in FE.lire(racine):
        txt = str((r.get('statut') or {}).get('texte') or '').lower()
        if 'retired' not in txt or r.get('vainqueur') not in (1, 2) or not r.get('jour'):
            continue
        perdant = r['away'] if r['vainqueur'] == 1 else r['home']
        k = E.cle(perdant.get('nom'))
        dern[k] = max(dern.get(k, ''), r['jour'])
    for x in lignes:
        try:
            j0 = _utc(x.get('debut_utc') or x['debut']).date()
        except (KeyError, TypeError, ValueError):
            continue
        v = []
        for n in (x.get('home'), x.get('away')):
            d = dern.get(E.cle(n))
            jours = (j0 - dt.date.fromisoformat(d)).days if d else None
            v.append(jours if jours is not None and 0 < jours <= ABANDON_J else None)
        if any(v):
            x['abandon_recent'] = v


def construire(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    pron = _lire(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics.json'), {}) or {}
    etat = _lire(os.path.join(racine, 'simulateur', 'elo_etat.json'), {})
    sys.path.insert(0, ICI)
    import elo as E
    etat = E.migrer_etat(etat)
    precedent = (_lire(os.path.join(racine, SORTIE), {}) or {}).get('match_du_jour')
    matchs = [m for m in pron.get('matchs') or [] if m.get('circuit') in CIRCUITS and version(m)[1] and connu(m)]
    mdj = choisir_match_du_jour(matchs, etat, maintenant, precedent)
    a_venir = sorted((m for m in matchs if _utc(m['debut']) > maintenant - dt.timedelta(hours=3)),
                     key=lambda m: (m['debut'], m['uid']))
    lignes = [ligne_match(m, complet=True) for m in a_venir]
    # Bloc descriptif calculé hors du moteur de probabilité : simple fusion par UID.
    styles_doc = _lire(os.path.join(racine, 'simulateur', 'styles_descriptifs.json'), {}) or {}
    styles = styles_doc.get('matchs') or {}
    ajouter_styles_descriptifs(lignes, styles_doc)
    rythme_doc = _lire(os.path.join(racine, 'simulateur', 'profil_rythme.json'), {}) or {}
    try:
        import elo as E
        alias = dict(E.migrer_etat(etat).get('alias') or {})
    except Exception:
        alias = {}
    ajouter_rythme(lignes, rythme_doc, alias)
    # 28/10/2026 — lignes de paris calculées par l'algo (distribution exacte) et duel service ↔ retour
    import lignes_algo as MD
    duel = MD.Duel.charger(racine)
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    for ligne in lignes:
        mk = MD.lignes(ligne.get('distribution_scores'), ligne.get('p_home', 0.5), ligne.get('meilleur_des') or 3)
        if mk:
            ligne['lignes_algo'] = mk
        du = duel.match(cle_c(ligne.get('home')), cle_c(ligne.get('away')), ligne.get('circuit'), ligne.get('surface'))
        if du:
            ligne['duel'] = du
    try:
        MD.journaliser(lignes, racine, maintenant)
    except OSError as e:
        print(f'::warning::journal des lignes non écrit : {e}')
    # 28/10/2026 — documentation des joueurs (balles de service effectives, comme la production)
    try:
        from qualite_donnees import balles_par_nom
        b_de = balles_par_nom(_lire(os.path.join(racine, 'simulateur', 'profils_service.json'), {}) or {},
                              [n for x in lignes for n in (x.get('home'), x.get('away'))])
        for ligne in lignes:
            ligne['documentation'] = [b_de(ligne.get('home')), b_de(ligne.get('away'))]
    except Exception as e:  # noqa: BLE001
        print(f'::warning::documentation des joueurs non calculée : {type(e).__name__}: {e}')
    resultats = _lire(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), {})
    # 28/10/2026 — fiches figées (premier et dernier pronostic avant le match), évolution, bilans après match
    apres, analyse_am = {}, None
    # 29/10/2026 — abandon récent (≤ 90 jours) : 3,1 % d'abandon au match suivant contre 1,5 % (19 502 joueurs-matchs)
    try:
        ajouter_abandons(lignes, racine)
    except Exception as e:  # noqa: BLE001
        print(f'::warning::abandons récents non calculés : {type(e).__name__}: {e}')
    try:
        import apres_match as AM
        facteurs_doc = _lire(os.path.join(racine, 'simulateur', 'facteurs.json'), {}) or {}
        version_m = AM.version_modele(etat, facteurs_doc)
        fiches = AM.figer(lignes, racine, maintenant, version_m)
        for ligne in lignes:
            ev = AM.evolution(fiches.get(ligne['uid']), ligne, version_m)
            if ev:
                ligne['evolution'] = ev
        B = AM.bilans(racine, resultats)
        apres = AM.pour_le_site(B, jours=3, maintenant=maintenant)
        analyse_am = AM.analyser(B)
        with open(os.path.join(racine, AM.SORTIE_ANALYSE), 'w', encoding='utf-8') as f:
            json.dump(analyse_am, f, ensure_ascii=False, indent=1)
    except Exception as e:  # noqa: BLE001
        print(f'::warning::après-match non calculé : {type(e).__name__}: {e}')
    return {'genere_le': maintenant.isoformat(timespec='seconds'), 'pronostics_du': pron.get('genere_le'),
            'simulations': pron.get('simulations') or 20000, 'match_du_jour': mdj,
            'qualite_horodatages': pron.get('qualite_horodatages'),
            'styles_descriptifs_source': ({'archive_jusqu_au': styles_doc.get('archive_jusqu_au'),
                                           'feuilles_recentes': styles_doc.get('feuilles_recentes'),
                                           'regle': styles_doc.get('regle')} if styles else None),
            'matchs': lignes, 'bilan': bilan(resultats), 'apres_match': apres,
            'journal_changements': journal_changements(racine, analyse_am),
            'bilan_lignes': bilan_lignes(racine, resultats),
            'fiabilite_stats': fiabilite_stats(racine, analyse_am),
            'desaccords': desaccords(racine, analyse_am),
            'validation_fiabilite': validation_fiabilite(resultats),
            'qualite_donnees': qualite_donnees(racine, resultats),
            'rejoue': rejoue(racine)}


DISTRIBUTION_P_MIN = 0.001


def compacter(doc, p_min=DISTRIBUTION_P_MIN):
    """29/10/2026 — la distribution exacte compte ~1 470 scores par match (6,6 Mo sur 7,6 Mo pour le fichier) ; le site
    n'en lit aucune ligne. Tout ce qui s'en sert (lignes de l'algo, rythme, fiches figées) tourne AVANT, sur la
    distribution complète. On publie les scores à 0,1 % et plus, plus la masse restante (« distribution_reste ») :
    la somme publiée reste exactement 1 (contrôlée par validation_vitrine)."""
    for m in doc.get('matchs') or []:
        D_ = m.get('distribution_scores')
        if not D_:
            continue
        garde = [r for r in D_ if float(r['probabilite']) >= p_min] or D_[:1]
        m['distribution_scores'] = garde
        m['distribution_reste'] = round(1.0 - sum(float(r['probabilite']) for r in garde), 12)
    return doc


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    doc = construire(racine)
    from validation_vitrine import valider
    valider(doc, int(os.environ.get('SIMULATIONS', '20000')))
    compacter(doc)
    valider(doc, int(os.environ.get('SIMULATIONS', '20000')))
    os.makedirs(os.path.join(racine, 'algo'), exist_ok=True)
    destination = os.path.join(racine, SORTIE)
    temporaire = destination + '.tmp'
    with open(temporaire, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(temporaire, destination)
    b = (doc['bilan'] or {}).get('global') or {}
    print(f"Site public : {len(doc['matchs'])} matchs · match du jour {(doc['match_du_jour'] or {}).get('uid')} · "
          f"bilan {b.get('vainqueurs')}/{b.get('n')} ({b.get('pct')} %)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
