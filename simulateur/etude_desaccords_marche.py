#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Étude externe des désaccords algorithme–marché et des signaux H13/H14.

Les probabilités indépendantes restent inchangées. Le marché sert seulement de
référence externe sur les mêmes premiers pronostics figés. H13/H14 sont étudiés
comme des règles de sélection corrélées, jamais comme des variables du modèle.

Sortie privée, agrégée : simulateur/rapport_etude_desaccords_marche.json
Usage : python simulateur/etude_desaccords_marche.py . [--archive /tmp/sackmann]
"""
import argparse
import collections
import datetime as dt
import glob
import gzip
import json
import math
import os
import random
import re
import sys
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.abspath(os.path.join(ICI, '..'))
LAB = os.path.join(RACINE, 'Tennis_Edge_Lab')
sys.path.insert(0, ICI)
sys.path.insert(0, LAB)
import ablation as AB  # noqa: E402
import styles_joueurs as ST  # noqa: E402

# Les dépendances du Lab sont importées dans les fonctions d'audit qui les
# utilisent réellement. Les tests du modèle indépendant peuvent ainsi fonctionner
# avec le checkout allégé, sans charger aucune brique de marché.

COUPURE_DIRECT = dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc)
COUPURE_STYLES = dt.date(2025, 1, 1)
SEUILS_DESACCORD = (.03, .05, .10)
MIN_PERIODE = 30
RESULTATS = os.path.join('Tennis_Edge_Lab', 'live', 'pronostics_resultats.json')
SORTIE = os.path.join('simulateur', 'rapport_etude_desaccords_marche.json')


def _ts(valeur):
    try:
        t = dt.datetime.fromisoformat(str(valeur).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def _periode(t):
    return 'decouverte' if t < COUPURE_DIRECT else 'confirmation'


def _norm(nom):
    txt = unicodedata.normalize('NFKD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    return ''.join(re.findall(r'[a-z0-9]+', txt))


def _p(x):
    return min(max(float(x), 1e-6), 1-1e-6)


def proba_sans_marge(cote_home, cote_away):
    """Dé-margination puissance du référentiel du Lab, sans réinjection au modèle."""
    try:
        ch, ca = float(cote_home), float(cote_away)
    except (TypeError, ValueError):
        return None
    if ch <= 1 or ca <= 1:
        return None
    a, b = 1/ch, 1/ca
    def f(k):
        return a**k + b**k - 1
    lo, hi = 1e-6, 1.0
    while f(hi) > 0:
        hi *= 2
        if hi > 1e6:
            break
    if f(lo) < 0 or f(hi) > 0:
        return a/(a+b)
    for _ in range(200):
        mid = (lo+hi)/2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi-lo < 1e-12:
            break
    k = (lo+hi)/2
    return _p(a**k)


def _cotes(m):
    c = m.get('pin_cotes')
    if isinstance(c, dict):
        c = c.get('pinnacle')
    if not isinstance(c, (list, tuple)) or len(c) < 2:
        return None
    return c[0], c[1]


def observations_marche(doc):
    """Cotes enregistrées avec le premier pronostic, jamais une clôture future."""
    source = {m.get('uid'): m for m in (doc or {}).get('matchs') or []}
    out, rejets = [], collections.Counter()
    for r in AB.observations(doc):
        m = source[r['uid']]
        cotes, pronostique, debut = _cotes(m), _ts(m.get('pronostique_le')), _ts(m.get('debut'))
        if cotes is None:
            rejets['cotes_au_pronostic_absentes'] += 1
            continue
        pm = proba_sans_marge(*cotes)
        if pm is None or pronostique is None or debut is None or pronostique >= debut:
            rejets['alignement_ou_cotes_invalides'] += 1
            continue
        ligne = dict(r, marche=pm, pronostique_le=pronostique,
                     periode=_periode(pronostique), desaccord=r['pipeline_complet']-pm)
        out.append(ligne)
    return out, dict(rejets)


def _score(rows, cle):
    if not rows:
        return {'n': 0}
    ll = sum(-(r['y']*math.log(r[cle])+(1-r['y'])*math.log(1-r[cle])) for r in rows)/len(rows)
    brier = sum((r[cle]-r['y'])**2 for r in rows)/len(rows)
    exact = sum((r[cle] > .5) == bool(r['y']) for r in rows)/len(rows)
    return {'n': len(rows), 'log_loss': round(ll, 6), 'brier': round(brier, 6),
            'reussite_pct': round(100*exact, 2)}


def _gains(rows, autre='marche', reference='pipeline_complet'):
    if not rows:
        return {'log_loss': None, 'brier': None}
    a, b = _score(rows, autre), _score(rows, reference)
    return {'log_loss': round(a['log_loss']-b['log_loss'], 6),
            'brier': round(a['brier']-b['brier'], 6),
            'sens': 'positif = algorithme indépendant meilleur'}


def _ic_gains(rows, repetitions, graine=20261027):
    semaines = sorted({r['semaine'] for r in rows})
    if len(semaines) < 2 or repetitions <= 0:
        return {'log_loss': None, 'brier': None}
    groupes = {s: [r for r in rows if r['semaine'] == s] for s in semaines}
    rnd, vals = random.Random(graine), {'log_loss': [], 'brier': []}
    for _ in range(repetitions):
        echantillon = [r for s in (rnd.choice(semaines) for _ in semaines) for r in groupes[s]]
        g = _gains(echantillon)
        for k in vals:
            vals[k].append(g[k])
    out = {}
    for k, values in vals.items():
        values.sort()
        out[k] = {'bas': round(values[int(.025*(len(values)-1))], 6),
                  'haut': round(values[int(.975*(len(values)-1))], 6)}
    return out


def _bloc_marche(rows, bootstrap=0):
    return {
        'n': len(rows), 'semaines': len({r['semaine'] for r in rows}),
        'algorithme': _score(rows, 'pipeline_complet'), 'marche': _score(rows, 'marche'),
        'gains_algorithme': _gains(rows),
        'ic95_bootstrap_semaine': _ic_gains(rows, bootstrap),
        'desaccord_absolu_moyen_pts': round(100*sum(abs(r['desaccord']) for r in rows)/len(rows), 3) if rows else None,
        'favoris_differents': sum((r['pipeline_complet'] > .5) != (r['marche'] > .5) for r in rows),
        'lecture': 'exploratoire' if len(rows) < MIN_PERIODE else 'descriptif, sans activation',
    }


def analyser_marche(doc, bootstrap=2000):
    rows, rejets = observations_marche(doc)
    groupes = {'global': rows}
    for periode in ('decouverte', 'confirmation'):
        groupes[periode] = [r for r in rows if r['periode'] == periode]
    for seuil in SEUILS_DESACCORD:
        groupes[f'desaccord_absolu>={seuil:.2f}'] = [r for r in rows if abs(r['desaccord']) >= seuil]
    groupes['favoris_differents'] = [r for r in rows if (r['pipeline_complet'] > .5) != (r['marche'] > .5)]
    return {
        'n_pronostics_regles': len(AB.observations(doc)), 'n_avec_marche_au_pronostic': len(rows),
        'rejets': rejets, 'coupure_decouverte_confirmation': COUPURE_DIRECT.isoformat(),
        'source_marche': 'pin_cotes du premier pronostic figé ; dé-margination puissance ; aucune clôture future',
        'population': 'exactement les mêmes matchs pour algorithme et marché dans chaque bloc',
        'seuils_fixes_sans_optimisation': list(SEUILS_DESACCORD),
        'resultats': {nom: _bloc_marche(g, bootstrap if nom == 'global' else 0) for nom, g in groupes.items()},
        'avertissement': 'Deux semaines ISO seulement : les intervalles sont exploratoires ; aucun filtre n’est activé.',
    }


def lire_jsonl(chemin):
    out = []
    try:
        with open(chemin, encoding='utf-8') as f:
            for ligne in f:
                if not ligne.strip():
                    continue
                try:
                    row = json.loads(ligne)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _signaux_h14(doc, signaux):
    source = {m.get('uid'): m for m in (doc or {}).get('matchs') or []}
    observations = {r['uid']: r for r in AB.observations(doc)}
    out, rejets, vus = [], collections.Counter(), set()
    for s in signaux:
        uid, side = s.get('uid'), s.get('side')
        if not uid or uid in vus:
            rejets['doublon_journal'] += 1
            continue
        vus.add(uid)
        m, r = source.get(uid), observations.get(uid)
        if not m or not r or side not in ('home', 'away'):
            rejets['resultat_ou_pronostic_inutilisable'] += 1
            continue
        pronostique, detecte, debut = _ts(m.get('pronostique_le')), _ts(s.get('detecte_le')), _ts(m.get('debut'))
        if not pronostique or not detecte or not debut or not pronostique <= detecte < debut:
            rejets['pronostic_non_disponible_ou_signal_hors_fenetre'] += 1
            continue
        joueur_attendu = m.get(side)
        if _norm(joueur_attendu) != _norm(s.get('joueur')):
            rejets['identite_side_incoherente'] += 1
            continue
        try:
            pin_decision = float(s.get('pin_decision'))
        except (TypeError, ValueError):
            pin_decision = 0.0
        if pin_decision <= 1:
            rejets['pin_decision_invalide'] += 1
            continue
        favori = 'home' if r['pipeline_complet'] >= .5 else 'away'
        out.append(dict(r, side_h14=side, detecte_le=detecte, periode=_periode(detecte),
                        veto=favori != side, h14_gagne=int((m.get('reel') or {}).get('gagnant') == side),
                        doublon_h13=bool(s.get('doublon') == 'h13' or (s.get('doublon_ref') or {}).get('canal') == 'h13'),
                        envoye=bool(s.get('envoye')), regle_hash=s.get('regle_hash'), gele_le=s.get('gele_le')))
    return out, dict(rejets)


def _bloc_veto(rows):
    retenus = [r for r in rows if not r['veto']]
    vetes = [r for r in rows if r['veto']]
    def contenu(g):
        return {'n': len(g), 'algorithme': AB._public(AB.mesures(g, 'pipeline_complet')),
                'h14_reussite_pct': round(100*sum(r['h14_gagne'] for r in g)/len(g), 2) if g else None,
                'doublons_h13': sum(r['doublon_h13'] for r in g)}
    return {
        'tous': contenu(rows), 'conserves_apres_veto': contenu(retenus), 'ecartes_par_veto': contenu(vetes),
        'comparabilite': 'populations différentes : blocs descriptifs, pas un gain apparié',
    }


def analyser_veto(doc, signaux):
    rows, rejets = _signaux_h14(doc, signaux)
    return {
        'statut_h14': 'NON VALIDÉE — étude privée, ne pas diffuser',
        'n_signaux_journal': len(signaux), 'n_testables_apres_pronostic': len(rows), 'rejets': rejets,
        'regle_testee': 'écarter le signal H14 si le premier algorithme figé favorise l’autre joueur',
        'alignement': 'pronostique_le <= detecte_le < debut ; side et identité du joueur vérifiés',
        'coupure_decouverte_confirmation': COUPURE_DIRECT.isoformat(),
        'versions_gelees': sorted({str(r['gele_le']) for r in rows if r['gele_le']}),
        'regles_hash': sorted({str(r['regle_hash']) for r in rows if r['regle_hash']}),
        'resultats': {
            'global': _bloc_veto(rows),
            'decouverte': _bloc_veto([r for r in rows if r['periode'] == 'decouverte']),
            'confirmation': _bloc_veto([r for r in rows if r['periode'] == 'confirmation']),
            'sensibilite_hors_doublons_h13': _bloc_veto([r for r in rows if not r['doublon_h13']]),
        },
        'activation': False,
        'verdict': 'échantillon insuffisant ; veto non activé' if len(rows) < MIN_PERIODE else 'résultat descriptif ; veto non activé sans confirmation appariée',
        'note_marche': 'pin_decision contrôle seulement la validité du signal externe ; il ne modifie aucune probabilité indépendante.',
    }


def _premiers_par_uid(rows):
    out = {}
    for r in rows:
        uid, t = r.get('uid'), _ts(r.get('detecte_le'))
        if not uid or not t:
            continue
        if uid not in out or t < out[uid][0]:
            out[uid] = (t, r)
    return out


def _chevauchement_bloc(h13, h14):
    u13, u14 = set(h13), set(h14)
    both = u13 & u14
    memes = sum(_norm(h13[u][1].get('joueur')) == _norm(h14[u][1].get('joueur')) for u in both)
    union = u13 | u14
    return {
        'h13': len(u13), 'h14': len(u14), 'intersection': len(both), 'union': len(union),
        'jaccard_pct': round(100*len(both)/len(union), 2) if union else None,
        'h14_parmi_h13_pct': round(100*len(both)/len(u13), 2) if u13 else None,
        'h13_parmi_h14_pct': round(100*len(both)/len(u14), 2) if u14 else None,
        'meme_joueur_dans_intersection': memes,
        'meme_joueur_pct': round(100*memes/len(both), 2) if both else None,
        'h14_marques_doublon_h13': sum(bool(h14[u][1].get('doublon') == 'h13') for u in u14),
    }


def analyser_chevauchement(h13_rows, h14_rows):
    h13_all, h14_all = _premiers_par_uid(h13_rows), _premiers_par_uid(h14_rows)
    if not h13_all or not h14_all:
        return {'n': 0, 'verdict': 'journaux insuffisants'}
    debut = max(min(t for t, _ in h13_all.values()), min(t for t, _ in h14_all.values()))
    fin = min(max(t for t, _ in h13_all.values()), max(t for t, _ in h14_all.values()))
    if debut > fin:
        return {'n': 0, 'periode_commune': None, 'verdict': 'aucune période de surveillance commune'}
    h13 = {u: (t, r) for u, (t, r) in h13_all.items() if debut <= t <= fin}
    h14 = {u: (t, r) for u, (t, r) in h14_all.items() if debut <= t <= fin}
    h13_env = {u: v for u, v in h13.items() if v[1].get('envoye')}
    h14_env = {u: v for u, v in h14.items() if v[1].get('envoye')}
    return {
        'periode_commune': {'debut': debut.isoformat(), 'fin': fin.isoformat()},
        'unite': 'un premier signal par UID ; recouvrement du joueur par nom normalisé',
        'toutes_detections': _chevauchement_bloc(h13, h14),
        'signaux_envoyes_seulement': _chevauchement_bloc(h13_env, h14_env),
        'dependance': 'H13 et H14 sont des signaux potentiellement redondants, jamais deux confirmations indépendantes.',
        'limite': 'Pas de coefficient de corrélation sur tous les matchs : l’univers commun réellement surveillé n’est pas journalisé.',
    }


def _audit_vide():
    return {'fichiers': 0, 'matchs': 0, 'courbes': 0, 'points_valides': 0,
            'points_uniques': 0, 'doublons_stricts': 0}


def _audit_resultat(compteurs, fichiers):
    return {'fichiers': fichiers, 'matchs': compteurs['matchs'], 'courbes': compteurs['courbes'],
            'points_valides': compteurs['points_valides'], 'points_uniques': compteurs['points_uniques'],
            'doublons_stricts': compteurs['duplicate_quote_points_removed']}


def _auditer_clv(racine):
    import clv_source
    import courbes_cotes
    compteurs = collections.Counter()
    chemin = os.path.join(racine, 'clv_history.jsonl')
    fichiers = clv_source.files(chemin)
    if not fichiers:
        return _audit_vide()
    with clv_source.open_text(chemin) as stream:
        for ligne in stream:
            if not ligne.strip():
                continue
            try:
                record = json.loads(ligne)
            except ValueError:
                continue
            start = _ts(record.get('commence_time'))
            if not start:
                continue
            compteurs['matchs'] += 1
            for side in ('home', 'away'):
                points = []
                for point in record.get(f'{side}_curve') or []:
                    if not isinstance(point, (list, tuple)) or len(point) < 2:
                        continue
                    t = _ts(point[0])
                    try:
                        cote = float(point[1])
                    except (TypeError, ValueError):
                        continue
                    if t and t < start and cote > 1:
                        points.append((t, cote))
                points.sort()
                avant = len(points)
                points = courbes_cotes.dedupliquer(points, compteurs)
                compteurs['courbes'] += 1
                compteurs['points_valides'] += avant
                compteurs['points_uniques'] += len(points)
    return _audit_resultat(compteurs, len(fichiers))


def _auditer_partitions(racine):
    import bookmakers_sets_v5 as cotes_engine
    compteurs = collections.Counter()
    chemins = sorted(p for p in glob.glob(os.path.join(racine, 'parts', 'hist_book_*.jsonl*'))
                     if p.endswith('.jsonl') or p.endswith('.jsonl.gz'))
    for chemin in chemins:
        opener = gzip.open if chemin.endswith('.gz') else open
        try:
            with opener(chemin, 'rt', encoding='utf-8') as stream:
                for ligne in stream:
                    if not ligne.strip():
                        continue
                    try:
                        record = json.loads(ligne)
                    except ValueError:
                        continue
                    start = cotes_engine.parse_time(record.get('commence_time'))
                    if not start:
                        continue
                    compteurs['matchs'] += 1
                    for side in ('home', 'away'):
                        avant = compteurs['duplicate_quote_points_removed']
                        points = cotes_engine._curve_points(record.get(f'{side}_curve'), start, compteurs)
                        retires = compteurs['duplicate_quote_points_removed'] - avant
                        compteurs['courbes'] += 1
                        compteurs['points_valides'] += len(points) + retires
                        compteurs['points_uniques'] += len(points)
        except (OSError, EOFError):
            continue
    return _audit_resultat(compteurs, len(chemins))


def auditer_deduplication(racine):
    """Audit CLV + partitions bookmakers, sans réécrire les historiques."""
    try:
        clv = _auditer_clv(racine)
    except OSError:
        clv = _audit_vide()
    parts = _auditer_partitions(racine)
    total = {k: clv.get(k, 0) + parts.get(k, 0) for k in _audit_vide()}
    total.update({
        'clv_history': clv, 'partitions_hist_book': parts,
        'regle': 'même horodatage et même cote seulement ; aucun historique brut réécrit',
        'portee': 'lectures du Lab ; producteur Telegram absent du checkout, non déclaré corrigé',
    })
    return total


def etude_styles(racine, archive=None, maximum=2000, bootstrap=2000):
    if not archive:
        try:
            with open(os.path.join(racine, 'simulateur', 'rapport_styles_joueurs.json'), encoding='utf-8') as f:
                doc = json.load(f)
            if doc.get('controle_incremental'):
                return doc['controle_incremental']
        except (OSError, ValueError):
            pass
        return {'n': 0, 'activation': False,
                'verdict': 'archive Sackmann absente : contrôle incrémental non exécuté, aucune donnée fabriquée'}
    import donnees
    import profils_robustes as PR
    M = donnees.charger(archive, 2021)
    choisis = PR.selection(M, dt.date(2024, 1, 1), maximum)
    try:
        with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
            reglage = (json.load(f).get('profils_hierarchiques') or {})
        actif = reglage if reglage.get('adopte') else {}
    except (OSError, ValueError):
        actif = {}
    out = ST.evaluer_controle(M, choisis, COUPURE_STYLES,
                              demi_vie=actif.get('demi_vie', ST.PS.DEMI_VIE),
                              prior_mult=actif.get('prior_mult', 1.0), bootstrap=bootstrap)
    out['source'] = 'archive Sackmann, CC BY-NC-SA 4.0, usage non commercial ; profils libérés après fin du tournoi'
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('racine', nargs='?', default=RACINE)
    ap.add_argument('--archive', help='archive Sackmann facultative pour le contrôle incrémental des styles')
    ap.add_argument('--max-styles', type=int, default=2000)
    ap.add_argument('--bootstrap', type=int, default=2000)
    ap.add_argument('--sans-audit-doublons', action='store_true')
    ap.add_argument('--sortie', help='chemin JSON facultatif ; ne pas choisir un fichier public du Lab')
    args = ap.parse_args(argv)
    racine = os.path.abspath(args.racine)
    try:
        with open(os.path.join(racine, RESULTATS), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    h13 = lire_jsonl(os.path.join(racine, 'h13_signal_log.jsonl'))
    h14 = lire_jsonl(os.path.join(racine, 'h14_signal_log.jsonl'))
    rapport = {
        'schema': 1,
        'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'visibilite': 'PRIVÉ — H14 NON VALIDÉE, ne pas diffuser ; aucune publication automatique',
        'separation': 'Le marché et H13–H20 sont des évaluations externes ; aucune entrée du modèle indépendant.',
        'population_directe': 'premiers pronostics figés et résultats ultérieurs ; aucun résultat ajouté manuellement',
        'desaccords_algorithme_marche': analyser_marche(doc, max(0, args.bootstrap)),
        'veto_h14': analyser_veto(doc, h14),
        'chevauchement_h13_h14': analyser_chevauchement(h13, h14),
        'styles_incrementaux': etude_styles(racine, args.archive, max(1, args.max_styles), max(0, args.bootstrap)),
        'deduplication_cotes': ({'verdict': 'audit sauté à la demande'} if args.sans_audit_doublons
                                else auditer_deduplication(racine)),
        'activation': {'modele_modifie': False, 'veto_active': False, 'regles_gelees_modifiees': False},
    }
    sortie = args.sortie or os.path.join(racine, SORTIE)
    if not os.path.isabs(sortie):
        sortie = os.path.join(racine, sortie)
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    with open(sortie, 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    marche = rapport['desaccords_algorithme_marche']
    veto = rapport['veto_h14']
    both = rapport['chevauchement_h13_h14'].get('toutes_detections', {}).get('intersection', 0)
    styles = rapport['styles_incrementaux']
    doublons = rapport['deduplication_cotes'].get('doublons_stricts', 'sauté')
    print(f"Désaccords : {marche['n_avec_marche_au_pronostic']} matchs avec cote au pronostic")
    print(f"Veto H14 : {veto['n_testables_apres_pronostic']} signaux testables · chevauchements H13–H14 : {both}")
    print(f"Styles : {styles.get('n', 0)} matchs · doublons stricts de cotes : {doublons}")
    print(f"Rapport privé agrégé : {sortie}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
