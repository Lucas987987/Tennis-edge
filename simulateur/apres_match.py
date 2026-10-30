#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apres_match.py — ce que l'algo AVAIT DIT, contre ce qui S'EST PASSÉ, match par match (28/10/2026).

1. FICHES FIGÉES (figer) : à chaque passage de la vitrine, pour chaque match pas encore commencé, on garde
   — le PREMIER pronostic affiché (heure, probabilité, version du modèle) : jamais réécrit ;
   — le DERNIER pronostic affiché avant le début (probabilité, sets, scores, feuille prévue, durée prévue, lignes de
     l'algo, fiabilité, documentation des joueurs, version du modèle) : remplacé à chaque passage jusqu'au début,
     puis plus jamais (c'est celui que juge le tableau des scores).
   Stockage : simulateur/journal_pronostics/fiches/AAAA-MM-JJ.json.gz {uid: {premier, dernier}} (jour du début : un
   fichier n'est plus réécrit une fois ses matchs commencés — le dépôt ne grossit pas à chaque passage).

2. APRÈS-MATCH (bilans) : dès que le résultat est connu (Tennis_Edge_Lab/live/pronostics_resultats.json : vainqueur,
   score, feuille réelle ; feuilles/ : durée), un bilan par match — prévu, réel, écarts :
   vainqueur (juste, log loss), sets, score réel (rang parmi les scores prévus, probabilité donnée), durée (écart,
   dans la fourchette 8 sur 10 ou non), chaque ligne de l'algo (probabilité, arrivée ou non), feuille de match
   (aces, doubles fautes, % 1re balle, breaks — prévu moins réel, par joueur).
   Stockage permanent : simulateur/journal_pronostics/apres_match/AAAA-MM-JJ.json.gz {uid: bilan} (jour du début).

3. ANALYSE POUR L'ALGO (analyser) : tous les bilans, par circuit — biais de la feuille prévue (prévu − réel),
   calibration des sets et des lignes, part des scores réels parmi les 3 plus probables, erreur sur la durée et
   couverture de la fourchette (elle devrait contenir 80 % des matchs). Sortie : simulateur/analyse_apres_match.json.
   DESCRIPTIF : aucune entrée du modèle. Une piste qui en sort devient un candidat jugé par la règle habituelle
   (fixée avant résultat, marge 0,001, deux semaines de suite, aucun circuit dégradé).

Aucune cote, aucune donnée de marché : uniquement nos pronostics et les résultats.
"""
import datetime as dt
import glob
import gzip
import json
import math
import os

ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_FICHES = os.path.join('simulateur', 'journal_pronostics', 'fiches')
DOSSIER_BILANS = os.path.join('simulateur', 'journal_pronostics', 'apres_match')
SORTIE_ANALYSE = os.path.join('simulateur', 'analyse_apres_match.json')
SCORES_GARDES = 300           # scores gardés dans la fiche : tous ceux d'au moins 0,1 % (~140 par match)
SCORE_P_MIN = 0.001
STATS_FEUILLE = ('aces', 'doubles_fautes', 'premiere_pct', 'breaks')
CIRCUITS = ('ATP', 'WTA', 'CH')


# ------------------------------------------------------------------ outils
def _utc(s):
    d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _lire_gz(chemin):
    try:
        with gzip.open(chemin, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ecrire_gz(chemin, doc):
    """Réécrit seulement si le contenu change (mtime gzip fixé à 0 : pas de faux changement dans git)."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    brut = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if os.path.exists(chemin):
        try:
            with gzip.open(chemin, 'rt', encoding='utf-8') as f:
                if f.read() == brut:
                    return False
        except OSError:
            pass
    with open(chemin + '.tmp', 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as g:
            g.write(brut.encode('utf-8'))
    os.replace(chemin + '.tmp', chemin)
    return True


def score_txt(score):
    return ' '.join(f"{a}-{b}" for a, b in score)


def version_modele(etat_elo, facteurs_doc):
    """Ce qui définit le modèle à un instant : variante de l'Elo et facteurs adoptés (pour expliquer un changement)."""
    return {'elo': (etat_elo or {}).get('variante'),
            'facteurs': sorted((facteurs_doc or {}).get('adoptes') or [])}


def raisons_changement(v0, v1):
    """Différences lisibles entre deux versions du modèle, ou []."""
    out = []
    if not v0 or not v1:
        return out
    e0, e1 = set(str(v0.get('elo') or '').split('+')), set(str(v1.get('elo') or '').split('+'))
    for x in sorted(e1 - e0):
        out.append({'itf': 'résultats ITF ajoutés au classement', 'feuilles': 'résultats des feuilles ajoutés au classement',
                    'elo_ameliore': 'classement Elo amélioré'}.get(x, f"classement : {x} ajouté"))
    for x in sorted(e0 - e1):
        out.append(f"classement : {x} retiré")
    f0, f1 = set(v0.get('facteurs') or []), set(v1.get('facteurs') or [])
    out += [f"facteur adopté : {x}" for x in sorted(f1 - f0)] + [f"facteur retiré : {x}" for x in sorted(f0 - f1)]
    return out


# ------------------------------------------------------------------ 1. fiches figées
def fiche(ligne, maintenant, version):
    """Ce qu'on garde d'une ligne de la vitrine (dernier pronostic affiché)."""
    dist = sorted(ligne.get('distribution_scores') or [], key=lambda d: -d['probabilite'])
    r = ligne.get('rythme') or {}
    pv = r.get('prevision') or {}
    fb = ligne.get('fiabilite') or {}
    return {'fige_le': maintenant.isoformat(timespec='seconds'), 'p_home': ligne.get('p_home'),
            'version': ligne.get('version'), 'modele': version,
            'fiabilite': {'note': fb.get('note'), 'niveau': fb.get('niveau')},
            'sets': ligne.get('sets'),
            'scores': [[score_txt(d['score']), round(d['probabilite'], 5)] for d in dist[:SCORES_GARDES]
                       if d['probabilite'] >= SCORE_P_MIN],
            'jeux_moyen': ligne.get('jeux_moyen'), 'tiebreak': ligne.get('tiebreak'), 'set1_home': ligne.get('set1_home'),
            'feuille': ligne.get('feuille_prevue'), 'fourchette': ligne.get('feuille_fourchette'),
            'duree': ({k: pv.get(k) for k in ('minutes', 'minutes_p10', 'minutes_p90', 'points')} if pv else None),
            'lignes': ligne.get('lignes_algo'), 'documentation': ligne.get('documentation'),
            'controle': ligne.get('controle'), 'modeles': ligne.get('modeles')}


def figer(lignes, racine, maintenant, version):
    """Met à jour les fiches des matchs pas encore commencés. Renvoie {uid: {premier, dernier}} des matchs vus."""
    par_mois, vus = {}, {}
    for x in lignes:
        try:
            debut = _utc(x.get('debut_utc') or x.get('debut'))
        except (TypeError, ValueError):
            continue
        mois = debut.strftime('%Y-%m-%d')                       # fichier du JOUR du début
        if mois not in par_mois:
            par_mois[mois] = _lire_gz(os.path.join(racine, DOSSIER_FICHES, f"{mois}.json.gz"))
        doc = par_mois[mois]
        e = doc.get(x['uid'])
        if debut > maintenant:
            f = fiche(x, maintenant, version)
            if e is None:
                e = doc[x['uid']] = {'debut': debut.isoformat(), 'circuit': x.get('circuit'), 'surface': x.get('surface'),
                                     'meilleur_des': x.get('meilleur_des'), 'home': x.get('home'), 'away': x.get('away'),
                                     'premier': {k: f[k] for k in ('fige_le', 'p_home', 'version', 'modele')}}
            e['dernier'] = f                                   # jusqu'au début seulement
        if e is not None:
            vus[x['uid']] = e
    for mois, doc in par_mois.items():
        _ecrire_gz(os.path.join(racine, DOSSIER_FICHES, f"{mois}.json.gz"), doc)
    return vus


def toutes_les_fiches(racine):
    out = {}
    for p in sorted(glob.glob(os.path.join(racine, DOSSIER_FICHES, '20*.json.gz'))):
        out.update(_lire_gz(p))
    return out


# ------------------------------------------------------------------ 2. bilans après match
def _sets(score):
    """'6-4 3-6 7-6' (vu de home) -> [(6,4), (3,6), (7,6)] ou None."""
    try:
        out = [tuple(int(v) for v in s.split('-')[:2]) for s in str(score).split()]
        return out if out and all(len(s) == 2 for s in out) else None
    except ValueError:
        return None


def ll_forme(masses, sets):
    """(−log P σ en place, −log P σ d'avant) de la forme réelle (camp × tie-break × 3 sets × jeux), sachant le
    vainqueur (le même pour les deux σ par ancrage) ; None si le vainqueur n'a aucune masse."""
    camp = 0 if sets[-1][0] > sets[-1][1] else 1
    o = (camp, any(max(a, b) == 7 and min(a, b) == 6 for a, b in sets), len(sets) >= 3, sum(a + b for a, b in sets))
    out = []
    for i in (4, 5):
        cote = sum(r[i] for r in masses if r[0] == camp)
        if not cote:
            return None
        v = next((r[i] for r in masses if (r[0], r[1], r[2], r[3]) == o), 0.0)
        out.append(round(-math.log(max(v / cote, 1e-6)), 5))
    return tuple(out)


def bilan_match(uid, f, reel, duree_reelle=None):
    """Bilan d'un match : prévu, réel, écarts. f : fiche figée ; reel : 'reel' de pronostics_resultats."""
    d = f.get('dernier') or {}
    if not d or (reel or {}).get('gagnant') not in ('home', 'away') or reel.get('interrompu'):
        return None
    sets = _sets(reel.get('score'))
    y = 1 if reel['gagnant'] == 'home' else 0
    p = d.get('p_home')
    out = {'uid': uid, 'debut': f.get('debut'), 'circuit': f.get('circuit'), 'surface': f.get('surface'),
           'home': f.get('home'), 'away': f.get('away'), 'fige_le': d.get('fige_le'),
           'prevu': {'p_home': p, 'sets': d.get('sets'), 'scores': (d.get('scores') or [])[:3],
                     'feuille': d.get('feuille'), 'duree': d.get('duree'), 'fiabilite': d.get('fiabilite')},
           'reel': {'gagnant': reel['gagnant'], 'score': reel.get('score'), 'sets': reel.get('sets'),
                    'feuille': reel.get('feuille'), 'minutes': duree_reelle},
           'ecarts': {}}
    E = out['ecarts']
    if isinstance(p, (int, float)):
        q = min(max(p if y else 1 - p, 1e-6), 1 - 1e-6)
        E['vainqueur_juste'] = (p > 0.5) == (y == 1)
        E['log_loss'] = round(-math.log(q), 5)
        E['p_vainqueur'] = round(q, 4)
    if sets:
        txt = score_txt(sets)
        jeux = sum(a + b for a, b in sets)
        tb = any(max(a, b) == 7 and min(a, b) == 6 for a, b in sets)
        out['reel'].update({'jeux': jeux, 'tie_break': tb, 'nb_sets': len(sets)})
        sc = d.get('scores') or []
        rang = next((i + 1 for i, (s, _) in enumerate(sc) if s == txt), None)
        E['score_rang'] = rang                                 # None : score à moins de 0,1 % (hors des scores gardés)
        E['score_proba'] = next((pp for s, pp in sc if s == txt), None)
        E['score_dans_top3'] = bool(rang and rang <= 3)
        st = d.get('sets') or {}
        cle = f"{sum(a > b for a, b in sets)}-{sum(b > a for a, b in sets)}"
        if st.get(cle) is not None:
            E['sets_proba'] = st.get(cle)
        lig = d.get('lignes') or {}
        res = {}
        for k, v in lig.items():
            if not isinstance(v, (int, float)):
                continue
            if k.startswith('total_plus_'):
                res[k] = [v, jeux > float(k[11:])]
            elif k.startswith('handicap_favori_') and lig.get('favori') in ('home', 'away'):
                m = sum(a - b for a, b in sets) * (1 if lig['favori'] == 'home' else -1)
                res[k] = [v, m > float(k[16:])]
            elif k == 'tie_break':
                res[k] = [v, tb]
            elif k == 'set_decisif':
                res[k] = [v, len(sets) == (5 if (f.get('meilleur_des') or 3) == 5 else 3)]
            elif k == 'set1_home':
                res[k] = [v, sets[0][0] > sets[0][1]]
        if res:
            E['lignes'] = res
    mo = d.get('modeles') or {}
    if mo.get('p_elo') is not None and mo.get('p_simulation') is not None and isinstance(p, (int, float)):
        # 29/10/2026 : l'Elo et la simulation désignaient-ils le même vainqueur ? Qui avait raison ?
        ju = lambda q: (q >= .5) == (y == 1)
        E['modeles'] = {'desaccord': (mo['p_elo'] >= .5) != (mo['p_simulation'] >= .5), 'elo_juste': ju(mo['p_elo']),
                        'simulation_juste': ju(mo['p_simulation']), 'affiche_juste': ju(p),
                        'ecart': round(abs(mo['p_elo'] - mo['p_simulation']), 4)}
    ct = d.get('controle') or {}
    if ct.get('p_elo') is not None and ct.get('p_elo_reference') is not None:
        lp = lambda q: round(-math.log(min(max(q if y else 1 - q, 1e-6), 1 - 1e-6)), 5)
        E['fantome'] = {'ll_elo': lp(ct['p_elo']), 'll_reference': lp(ct['p_elo_reference']), 'reference': ct.get('reference')}
    if ct.get('p_elo') is not None and ct.get('p_elo_sans_itf_femmes') is not None:     # 29/10/2026 : ITF femmes à part
        lp = lambda q: round(-math.log(min(max(q if y else 1 - q, 1e-6), 1 - 1e-6)), 5)
        E['fantome_itf_femmes'] = {'ll_elo': lp(ct['p_elo']), 'll_reference': lp(ct['p_elo_sans_itf_femmes'])}
    fo = ct.get('forme') or {}
    if fo.get('masses') and sets:           # 29/10/2026 : forme du jour (σ) en place contre l'ancienne, forme réelle
        ll_f = ll_forme(fo['masses'], sets)
        if ll_f:
            E['fantome_sigma'] = {'ll_elo': ll_f[0], 'll_reference': ll_f[1], 'sigma': fo.get('sigma'),
                                  'sigma_reference': fo.get('sigma_reference')}
    ent = ct.get('entree') or {}
    if ent.get('p_home') is not None and isinstance(p, (int, float)):
        # 30/10/2026 : pronostic affiché contre le même corrigé du statut d'entrée (invité en Challenger, qualifié en ATP)
        lp = lambda q: round(-math.log(min(max(q if y else 1 - q, 1e-6), 1 - 1e-6)), 5)
        E['fantome_entree'] = {'ll_elo': lp(p), 'll_reference': lp(ent['p_home'])}
    fsv = ct.get('forme_service') or {}
    if fsv.get('p_home') is not None and isinstance(p, (int, float)):
        # 29/10/2026 : pronostic affiché contre le même AVEC le service / retour du moment (forme_service.py)
        lp = lambda q: round(-math.log(min(max(q if y else 1 - q, 1e-6), 1 - 1e-6)), 5)
        E['fantome_forme_service'] = {'ll_elo': lp(p), 'll_reference': lp(fsv['p_home'])}
    du = d.get('duree') or {}
    if duree_reelle and du.get('minutes'):
        E['duree_ecart_min'] = round(du['minutes'] - duree_reelle)
        if du.get('minutes_p10') and du.get('minutes_p90'):
            E['duree_dans_fourchette'] = du['minutes_p10'] <= duree_reelle <= du['minutes_p90']
    fp, fr = d.get('feuille'), reel.get('feuille')
    if fp and fr and len(fp) == 2 and len(fr) == 2:
        E['feuille'] = [{k: round(fp[i][k] - fr[i][k], 2) for k in STATS_FEUILLE
                         if isinstance(fp[i].get(k), (int, float)) and isinstance(fr[i].get(k), (int, float))}
                        for i in (0, 1)]
    fq = d.get('fourchette')
    if fq and fr and len(fq) == 2 and len(fr) == 2:     # 29/10/2026 : le réel tombe-t-il dans la fourchette 80 % ?
        E['fourchette'] = [{k: (-1 if fr[i][k] < fq[i][k][0] else 1 if fr[i][k] > fq[i][k][1] else 0)
                            for k in STATS_FEUILLE if isinstance(fr[i].get(k), (int, float)) and fq[i].get(k)}
                           for i in (0, 1)]
    return out


def durees_reelles(racine):
    """{(jour, frozenset clés) : minutes} depuis les feuilles (détail du match)."""
    try:
        import feuilles as FE
        import elo as E
    except ImportError:
        return {}
    out = {}
    for r in FE.lire(racine):
        if r.get('duree_min') and r.get('jour'):
            out[(r['jour'], frozenset((E.cle(r['home'].get('nom')), E.cle(r['away'].get('nom')))))] = r['duree_min']
    return out


def duree_de(durees, f):
    import elo as E
    try:
        j0 = _utc(f['debut']).date()
    except (KeyError, ValueError, TypeError):
        return None
    paire = frozenset((E.cle(f.get('home')), E.cle(f.get('away'))))
    for k in (0, -1, 1):
        v = durees.get(((j0 + dt.timedelta(days=k)).isoformat(), paire))
        if v:
            return v
    return None


def bilans(racine, resultats, fiches=None):
    """Bilans de tous les matchs figés dont le résultat est connu ; écrits par mois (permanent). Renvoie {uid: bilan}."""
    fiches = fiches if fiches is not None else toutes_les_fiches(racine)
    reels = {m['uid']: m.get('reel') for m in (resultats or {}).get('matchs') or [] if m.get('uid')}
    durees = durees_reelles(racine)
    out, par_mois = {}, {}
    for uid, f in fiches.items():
        b = bilan_match(uid, f, reels.get(uid), duree_de(durees, f))
        if b:
            out[uid] = b
            par_mois.setdefault(str(f.get('debut'))[:10], {})[uid] = b
    for mois, doc in par_mois.items():
        _ecrire_gz(os.path.join(racine, DOSSIER_BILANS, f"{mois}.json.gz"), doc)
    return out


# ------------------------------------------------------------------ 3. analyse pour l'algo
def _moy(L):
    return round(sum(L) / len(L), 4) if L else None


# ------------------------------------------------------------------ 29/10/2026 : réussite et fiabilité de ce qui est annoncé
# RÈGLE FIXÉE AVANT DE VOIR LES CHIFFRES (29/10/2026, 10 h 40) — descriptive, rien n'est réglé dessus :
#  statistiques (aces, doubles fautes, 1re balle, breaks, par joueur) : « réussite » = part des cas où le réel tombe
#    dans la fourchette 80 % annoncée. Moins de 30 cas : rien à conclure. Fiable si 70 à 90 % ET ni « au-dessous » ni
#    « au-dessus » ne dépasse 15 % ; sinon : trop étroite (< 70 %), trop large (> 90 %), ou penche d'un côté (biais).
#  événements (tie-break, set décisif, total de jeux, handicap, 1er set) : « réussite » = l'issue donnée à plus de
#    50 % est arrivée ; fiabilité = écart entre le % annoncé et le % arrivé, fiable à 5 points ou moins.
N_FIABLE = 30


def fiabilite_stat(pos, ecarts):
    """pos : [-1 sous, 0 dedans, 1 au-dessus] ; ecarts : prévu − réel."""
    n = len(pos)
    out = {'n': n or len(ecarts), 'erreur_moyenne': _moy([abs(x) for x in ecarts]), 'biais': _moy(ecarts)}
    if not n:
        return dict(out, fiabilite='rien')
    dans, sous, dessus = (100.0 * sum(1 for x in pos if x == v) / n for v in (0, -1, 1))
    out.update(dans_fourchette_pct=round(dans, 1), sous_pct=round(sous, 1), dessus_pct=round(dessus, 1), cible_pct=80)
    if n < N_FIABLE:
        out['fiabilite'] = 'rien'
    elif dans < 70:
        out['fiabilite'] = 'trop_etroite'
    elif dans > 90:
        out['fiabilite'] = 'trop_large'
    elif max(sous, dessus) > 15:
        out['fiabilite'] = 'penche_haut' if sous > 15 else 'penche_bas'
    else:
        out['fiabilite'] = 'fiable'
    return out


def fiabilite_ligne(v):
    """v : [(probabilité annoncée, arrivé)]."""
    n = len(v)
    prevu, reel = 100 * sum(p for p, _ in v) / n, 100 * sum(ok for _, ok in v) / n
    reussite = 100 * sum((p >= .5) == bool(ok) for p, ok in v) / n
    brier = sum((p - ok) ** 2 for p, ok in v) / n
    base = reel / 100
    brier_naif = sum((base - ok) ** 2 for _, ok in v) / n
    ecart = prevu - reel
    fi = 'rien' if n < N_FIABLE else 'fiable' if abs(ecart) <= 5 else ('surestime' if ecart > 0 else 'sous_estime')
    return {'n': n, 'prevu_pct': round(prevu, 1), 'reel_pct': round(reel, 1), 'reussite_pct': round(reussite, 1),
            'ecart_pts': round(ecart, 1), 'brier': round(brier, 4), 'brier_naif': round(brier_naif, 4), 'fiabilite': fi}


N_PISTE = 30          # au moins 30 matchs pour signaler une piste
Z_PISTE = 2.0         # écart d'au moins 2 erreurs-types


def _ecart_type(L):
    if len(L) < 2:
        return None
    m = sum(L) / len(L)
    return math.sqrt(sum((x - m) ** 2 for x in L) / (len(L) - 1))


def pistes(B):
    """28/10/2026 — biais NETS de l'analyse après match (≥ 30 matchs, écart ≥ 2 erreurs-types), par circuit.
    Avec des dizaines d'indicateurs, quelques-uns passent ce seuil par hasard : une piste n'est qu'une QUESTION. Elle ne
    devient un candidat (jugé par la règle habituelle, fixée avant résultat) que si elle revient semaine après semaine."""
    out = []
    groupes = {'TOUS': list(B.values())}
    for c in CIRCUITS:
        groupes[c] = [b for b in B.values() if b.get('circuit') == c]
    for g, L in groupes.items():
        E = [b['ecarts'] for b in L]
        fe = {}
        for e in E:
            for j in e.get('feuille') or []:
                for k, v in j.items():
                    fe.setdefault(k, []).append(v)
        for k, v in fe.items():
            sd = _ecart_type(v)
            if len(v) >= N_PISTE and sd:
                m = sum(v) / len(v)
                if abs(m) >= Z_PISTE * sd / math.sqrt(len(v)):
                    out.append({'groupe': g, 'type': 'feuille', 'stat': k, 'n': len(v), 'biais_prevu_moins_reel': round(m, 3),
                                'z': round(m / (sd / math.sqrt(len(v))), 1)})
        lig = {}
        for e in E:
            for k, (p, ok) in (e.get('lignes') or {}).items():
                lig.setdefault(k, []).append((p, ok))
        for k, v in lig.items():
            n = len(v)
            if n < N_PISTE:
                continue
            pm, rm = sum(p for p, _ in v) / n, sum(ok for _, ok in v) / n
            se = math.sqrt(max(sum(p * (1 - p) for p, _ in v), 1e-9)) / n
            if abs(rm - pm) >= Z_PISTE * se:
                out.append({'groupe': g, 'type': 'ligne', 'stat': k, 'n': n, 'prevu_pct': round(100 * pm, 1),
                            'reel_pct': round(100 * rm, 1), 'z': round((rm - pm) / se, 1)})
        V = [(e['p_vainqueur'], e['vainqueur_juste']) for e in E if 'p_vainqueur' in e]
        if len(V) >= N_PISTE:
            n = len(V)
            conf = sum(max(p, 1 - p) for p, _ in V) / n
            hit = sum(ok for _, ok in V) / n
            se = math.sqrt(sum(max(p, 1 - p) * (1 - max(p, 1 - p)) for p, _ in V)) / n
            if abs(hit - conf) >= Z_PISTE * se:
                out.append({'groupe': g, 'type': 'vainqueur', 'stat': 'confiance', 'n': n, 'prevu_pct': round(100 * conf, 1),
                            'reel_pct': round(100 * hit, 1), 'z': round((hit - conf) / se, 1)})
        D = [e['duree_ecart_min'] for e in E if 'duree_ecart_min' in e]
        sd = _ecart_type(D)
        if len(D) >= N_PISTE and sd:
            m = sum(D) / len(D)
            if abs(m) >= Z_PISTE * sd / math.sqrt(len(D)):
                out.append({'groupe': g, 'type': 'duree', 'stat': 'biais_min', 'n': len(D), 'biais_prevu_moins_reel': round(m, 1),
                            'z': round(m / (sd / math.sqrt(len(D))), 1)})
        C = [e['duree_dans_fourchette'] for e in E if 'duree_dans_fourchette' in e]
        if len(C) >= N_PISTE:
            n, cov = len(C), sum(C) / len(C)
            se = math.sqrt(0.8 * 0.2 / n)
            if abs(cov - 0.8) >= Z_PISTE * se:
                out.append({'groupe': g, 'type': 'duree', 'stat': 'fourchette_80', 'n': n, 'prevu_pct': 80.0,
                            'reel_pct': round(100 * cov, 1), 'z': round((cov - 0.8) / se, 1)})
    out.sort(key=lambda x: -abs(x['z']))
    return out


def message_pistes(doc):
    """Texte Telegram (canal privé) : les pistes de la semaine, ou « rien de net »."""
    P = doc.get('pistes') or []
    T = doc.get('groupes', {}).get('TOUS') or {}
    L = ["<b>🔬 Après-match : ce que l'algo prévoit mal</b>",
         f"<i>{T.get('matchs', 0)} matchs jugés · seuil : 30 matchs et 2 erreurs-types · une piste = une question, pas une preuve</i>"]
    if not P:
        L.append("Rien de net cette semaine.")
    for p in P[:12]:
        if 'biais_prevu_moins_reel' in p:
            L.append(f"• {p['groupe']} · {p['type']} {p['stat']} : prévu − réel = {p['biais_prevu_moins_reel']} (n={p['n']}, z={p['z']})")
        else:
            L.append(f"• {p['groupe']} · {p['type']} {p['stat']} : prévu {p['prevu_pct']} % / réel {p['reel_pct']} % (n={p['n']}, z={p['z']})")
    lig = []                        # 29/10/2026 : désaccords Elo / simulation, chaque semaine
    for g in ('TOUS', 'ATP', 'WTA', 'CH'):
        dsc = (doc.get('groupes', {}).get(g) or {}).get('desaccord') or {}
        if dsc.get('desaccords'):
            lig.append(f"• {g} : {dsc['desaccords']} désaccords sur {dsc['matchs']} · Elo juste {dsc['elo_pct']} % · "
                       f"simulation {dsc['simulation_pct']} % · affiché {dsc['affiche_pct']} % (accord : {dsc['accord_pct']} %)"
                       + ('' if dsc.get('conclusion_possible') else ' · moins de 30 : rien à conclure'))
    if lig:
        L.append("\n<b>Elo et simulation en désaccord sur le vainqueur</b>")
        L += lig
    L.append("\n<i>Descriptif : rien n'entre dans le modèle sans le test habituel (fixé avant résultat, deux semaines de suite).</i>")
    return '\n'.join(L)


def analyser(B):
    """Synthèse descriptive de tous les bilans, par circuit (et tous)."""
    groupes = {'TOUS': list(B.values())}
    for c in CIRCUITS:
        groupes[c] = [b for b in B.values() if b.get('circuit') == c]
    out = {}
    for g, L in groupes.items():
        if not L:
            continue
        E = [b['ecarts'] for b in L]
        r = {'matchs': len(L),
             'vainqueurs_pct': _moy([100.0 * e['vainqueur_juste'] for e in E if 'vainqueur_juste' in e]),
             'log_loss': _moy([e['log_loss'] for e in E if 'log_loss' in e]),
             'score_dans_top3_pct': _moy([100.0 * e['score_dans_top3'] for e in E if 'score_dans_top3' in e]),
             'proba_moyenne_du_score_reel': _moy([e['score_proba'] or 0.0 for e in E if 'score_rang' in e]),
             'proba_moyenne_des_sets_reels': _moy([e['sets_proba'] for e in E if 'sets_proba' in e])}
        de = [e['duree_ecart_min'] for e in E if 'duree_ecart_min' in e]
        if de:
            r['duree'] = {'matchs': len(de), 'erreur_moyenne_min': _moy([abs(x) for x in de]),
                          'biais_min': _moy(de), 'dans_fourchette_pct': _moy(
                              [100.0 * e['duree_dans_fourchette'] for e in E if 'duree_dans_fourchette' in e]),
                          'attendu_fourchette_pct': 80}
        lig = {}
        for e in E:
            for k, (p, ok) in (e.get('lignes') or {}).items():
                lig.setdefault(k, []).append((p, ok))
        r['lignes'] = {k: fiabilite_ligne(v) for k, v in sorted(lig.items())}
        fe = {}
        for e in E:
            for j in e.get('feuille') or []:
                for k, v in j.items():
                    fe.setdefault(k, []).append(v)
        r['feuille_biais_prevu_moins_reel'] = {k: {'n': len(v), 'biais': _moy(v), 'erreur_moyenne': _moy([abs(x) for x in v])}
                                                for k, v in fe.items()}
        fq = {}
        for e in E:
            for j in e.get('fourchette') or []:
                for k, v in j.items():
                    fq.setdefault(k, []).append(v)
        r['stats'] = {k: fiabilite_stat(fq.get(k) or [], fe.get(k) or []) for k in STATS_FEUILLE if fq.get(k) or fe.get(k)}
        mo = [e['modeles'] for e in E if 'modeles' in e]
        if mo:                      # 29/10/2026 : désaccords Elo / simulation — qui avait raison ?
            dd, aa = [x for x in mo if x['desaccord']], [x for x in mo if not x['desaccord']]
            pct = lambda L, k: round(100 * sum(x[k] for x in L) / len(L), 1) if L else None
            r['desaccord'] = {'matchs': len(mo), 'desaccords': len(dd), 'elo_pct': pct(dd, 'elo_juste'),
                              'simulation_pct': pct(dd, 'simulation_juste'), 'affiche_pct': pct(dd, 'affiche_juste'),
                              'accord_pct': pct(aa, 'affiche_juste'), 'conclusion_possible': len(dd) >= 30}
        # 29/10/2026 : chaque changement contre son modèle fantôme, sur les mêmes matchs réels
        for cle_f in ('fantome', 'fantome_itf_femmes', 'fantome_sigma', 'fantome_forme_service', 'fantome_entree'):
            fa = [e[cle_f] for e in E if cle_f in e]
            if fa:
                a_, b_ = _moy([x['ll_elo'] for x in fa]), _moy([x['ll_reference'] for x in fa])
                r[cle_f] = {'matchs': len(fa), 'log_loss_elo_en_place': a_, 'log_loss_elo_reference': b_,
                            'gain': round(b_ - a_, 5), 'conclusion_possible': len(fa) >= 30}
        r['conclusion_possible'] = len(L) >= 30
        out[g] = r
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'pistes': pistes(B),
            'definition': ("Dernier pronostic affiché avant le match contre le résultat. Descriptif : aucune entrée du "
                           "modèle ; une piste devient un candidat jugé par la règle habituelle (fixée avant résultat)."),
            'groupes': out}


def pour_le_site(B, jours=4, maintenant=None):
    """Bilans compacts des matchs commencés depuis `jours` jours (fiches après match du site)."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    lim = maintenant - dt.timedelta(days=jours)
    out = {}
    for uid, b in B.items():
        try:
            if _utc(b['debut']) < lim:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        out[uid] = b
    return out


def evolution(f, ligne, version_actuelle):
    """Premier pronostic affiché -> pronostic actuel (et pourquoi, si le modèle a changé)."""
    pr = (f or {}).get('premier') or {}
    if pr.get('p_home') is None or ligne.get('p_home') is None:
        return None
    return {'premier_p_home': pr['p_home'], 'premier_le': pr.get('fige_le'),
            'ecart_pts': round(100 * (ligne['p_home'] - pr['p_home']), 1),
            'raisons': raisons_changement(pr.get('modele'), version_actuelle)}


def main(argv):
    """python simulateur/apres_match.py [racine] [--telegram] : affiche (ou envoie au Telegram privé) les pistes."""
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    try:
        with open(os.path.join(racine, SORTIE_ANALYSE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        print('Analyse après match absente : rien à envoyer.')
        return 0
    txt = message_pistes(doc)
    if '--telegram' in argv:
        import urllib.parse
        import urllib.request
        tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
        if tok and chat:
            try:
                data = urllib.parse.urlencode({'chat_id': chat, 'text': txt, 'parse_mode': 'HTML'}).encode()
                urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20).read()
                print('Pistes après match : envoyées sur le Telegram privé.')
            except Exception as e:  # noqa: BLE001
                print(f'::warning::Telegram impossible ({type(e).__name__})')
        return 0
    print(txt)
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
