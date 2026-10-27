#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trajectoires descriptives des joueurs, avec effectifs et surfaces.

Les périodes sont strictement antérieures à la date de référence. Les taux bruts
et leurs variations restent descriptifs : ils ne sont ni des probabilités de
victoire ni des variables automatiquement ajoutées au modèle.
"""
import argparse
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo as E  # noqa: E402

SORTIE = os.path.join('simulateur', 'evolution_statistiques_joueurs.json')
SEUILS = {
    'premiere_balle_pct': 100,
    'aces_par_premiere_pct': 100,
    'points_premiere_pct': 100,
    'doubles_fautes_par_seconde_pct': 50,
    'points_seconde_pct': 50,
    'points_retour_premiere_pct': 100,
    'points_retour_seconde_pct': 50,
    'balles_break_sauvees_pct': 10,
    'balles_break_converties_pct': 10,
    'tiebreaks_gagnes_pct': 5,
    'sets_decisifs_gagnes_pct': 5,
}


def _documentation(n, nom):
    seuil = SEUILS[nom]
    if n < seuil:
        return 'insuffisante'
    if n < 3 * seuil:
        return 'intermediaire'
    return 'large'


def _ligne(numerateur, denominateur, nom):
    if denominateur <= 0:
        return {'n': 0, 'taux_pct': None, 'documentation': 'absente'}
    return {'n': round(denominateur, 3), 'numerateur': round(numerateur, 3),
            'taux_pct': round(100 * numerateur / denominateur, 2),
            'documentation': _documentation(denominateur, nom)}


def _sommes_propres(propre, adverse):
    sv, in1, w1, w2, ace, df = propre[:6]
    osv, oin1, ow1, ow2, _, odf = adverse[:6]
    sec, osec = sv - in1, osv - oin1
    bpf, bps = propre[6], propre[7]
    obpf, obps = adverse[6], adverse[7]
    return {
        'premiere_balle_pct': (in1, sv),
        'aces_par_premiere_pct': (ace, in1),
        'points_premiere_pct': (w1, in1),
        'doubles_fautes_par_seconde_pct': (df, sec),
        'points_seconde_pct': (w2, sec - df),
        'points_retour_premiere_pct': (oin1 - ow1, oin1),
        'points_retour_seconde_pct': (osec - odf - ow2, osec - odf),
        'balles_break_sauvees_pct': (bps, bpf),
        'balles_break_converties_pct': (obpf - obps, obpf),
    }


def _evenement(m, joueur, propre, adverse):
    sets = m.get('sets') or []
    bo = m.get('bo') or 3
    tie_n = tie_v = 0
    for sg, sp in sets:
        if (sg, sp) in ((7, 6), (6, 7)):
            tie_n += 1
            tie_v += int((joueur == m['gagnant'] and sg > sp) or
                         (joueur == m['perdant'] and sp > sg))
    dec_n = int(len(sets) == bo)
    dec_v = int(dec_n and joueur == m['gagnant'])
    stats = _sommes_propres(propre, adverse)
    stats['tiebreaks_gagnes_pct'] = (tie_v, tie_n)
    stats['sets_decisifs_gagnes_pct'] = (dec_v, dec_n)
    return {'date': m['date'], 'surface': m['surface'], 'circuit': m['circuit'], 'stats': stats}


def evenements(M, cibles):
    """Conserve uniquement les matchs complets et antérieurement observables."""
    out = {j: [] for j in cibles}
    noms = {}
    for m in sorted(M, key=lambda x: (x['date'], x.get('tour', 0), x.get('num', 0))):
        if not m.get('complet') or m.get('abandon') or not m.get('detail'):
            continue
        g, p = m['gagnant'], m['perdant']
        if g in out:
            out[g].append(_evenement(m, g, m['detail']['w'], m['detail']['l']))
            noms[g] = m.get('nom_g') or g
        if p in out:
            out[p].append(_evenement(m, p, m['detail']['l'], m['detail']['w']))
            noms[p] = m.get('nom_p') or p
    return out, noms


def agreger(lignes, debut, fin, surface=None):
    total = {nom: [0.0, 0.0] for nom in SEUILS}
    matchs = 0
    for ligne in lignes:
        if not debut <= ligne['date'] < fin:
            continue
        if surface is not None and ligne['surface'] != surface:
            continue
        matchs += 1
        for nom, (num, den) in ligne['stats'].items():
            total[nom][0] += num
            total[nom][1] += den
    return {'matchs': matchs,
            'statistiques': {nom: _ligne(num, den, nom) for nom, (num, den) in total.items()}}


def comparaison(lignes, reference, fenetre, surface=None):
    recent_debut = reference - dt.timedelta(days=fenetre)
    ancien_debut = reference - dt.timedelta(days=2 * fenetre)
    recent = agreger(lignes, recent_debut, reference, surface)
    ancien = agreger(lignes, ancien_debut, recent_debut, surface)
    variations = {}
    for nom in SEUILS:
        a, b = ancien['statistiques'][nom], recent['statistiques'][nom]
        documente = (a['taux_pct'] is not None and b['taux_pct'] is not None
                     and a['documentation'] != 'insuffisante' and b['documentation'] != 'insuffisante')
        variations[nom] = {
            'variation_points': round(b['taux_pct'] - a['taux_pct'], 2) if documente else None,
            'statut': 'comparaison_documentee' if documente else 'sous_documentee',
        }
    return {'periode_precedente': ancien, 'periode_recente': recent, 'variations': variations}


def _cibles_actives(M, reference, maximum, jours=365):
    comptes = {}
    noms = {}
    debut = reference - dt.timedelta(days=jours)
    for m in M:
        if not debut <= m['date'] < reference or not m.get('detail') or not m.get('complet') or m.get('abandon'):
            continue
        for j, nom in ((m['gagnant'], m.get('nom_g')), (m['perdant'], m.get('nom_p'))):
            comptes[j] = comptes.get(j, 0) + 1
            noms[j] = nom or j
    choisis = sorted(comptes, key=lambda j: (-comptes[j], noms.get(j, j)))[:maximum]
    return set(choisis)


def construire(M, reference=None, joueurs=(), maximum_joueurs=20, fenetre_jours=180,
               points_trajectoire=6, pas_jours=90):
    reference = reference or (max(m['date'] for m in M) + dt.timedelta(days=1))
    M = [m for m in M if m['date'] < reference]
    if joueurs:
        recherches = {E.cle(nom) for nom in joueurs}
        cibles = set(recherches)
        # L’archive utilise des identifiants stables (par exemple wta:211279),
        # tandis que l’utilisateur recherche un nom affiché. On résout les deux.
        for m in M:
            if E.cle(m.get('nom_g') or '') in recherches:
                cibles.add(m['gagnant'])
            if E.cle(m.get('nom_p') or '') in recherches:
                cibles.add(m['perdant'])
    else:
        cibles = _cibles_actives(M, reference, maximum_joueurs)
    historique, noms = evenements(M, cibles)
    out = {
        'schema': 'evolution_statistiques_joueurs_v1',
        'reference_pre_match': reference.isoformat(),
        'fenetre_jours': fenetre_jours,
        'descriptif_seulement': True,
        'champion_actif_modifie': False,
        'marche_utilise': False,
        'definitions': {
            'periode_recente': f'{fenetre_jours} jours avant la référence, date de référence exclue',
            'periode_precedente': f'{fenetre_jours} jours immédiatement antérieurs',
            'variation': 'taux récent moins taux précédent, en points de pourcentage',
            'documentation': 'effectif du dénominateur propre à chaque statistique',
            'limites': 'taux bruts non ajustés à la force adverse ; aucune causalité ni probabilité de victoire',
        },
        'joueurs': {},
    }
    for joueur in sorted(cibles):
        lignes = historique.get(joueur) or []
        if not lignes:
            continue
        bloc = {
            'nom': noms.get(joueur, joueur),
            'global': comparaison(lignes, reference, fenetre_jours),
            'par_surface': {},
            'trajectoire_globale': [],
        }
        for surface in ('Hard', 'Clay', 'Grass'):
            if any(x['surface'] == surface for x in lignes):
                bloc['par_surface'][surface] = comparaison(lignes, reference, fenetre_jours, surface)
        for k in range(points_trajectoire - 1, -1, -1):
            fin = reference - dt.timedelta(days=k * pas_jours)
            point = agreger(lignes, fin - dt.timedelta(days=fenetre_jours), fin)
            bloc['trajectoire_globale'].append({'fin_periode_exclue': fin.isoformat(), **point})
        out['joueurs'][joueur] = bloc
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--reference', help='date pré-match ISO ; par défaut lendemain du dernier match de l’archive')
    ap.add_argument('--joueurs', nargs='*', default=[])
    ap.add_argument('--maximum-joueurs', type=int, default=20)
    ap.add_argument('--fenetre-jours', type=int, default=180)
    ap.add_argument('--points-trajectoire', type=int, default=6)
    ap.add_argument('--pas-jours', type=int, default=90)
    args = ap.parse_args(argv)
    M = donnees.charger(args.archive, 2021)
    if not M:
        raise SystemExit('Aucun match Sackmann lisible.')
    reference = dt.date.fromisoformat(args.reference) if args.reference else None
    out = construire(M, reference, args.joueurs, args.maximum_joueurs, args.fenetre_jours,
                     args.points_trajectoire, args.pas_jours)
    out['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    out['source'] = 'Archive Jeff Sackmann, CC BY-NC-SA 4.0, usage non commercial et attribution requis'
    chemin = os.path.join(args.racine, SORTIE)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({'schema': out['schema'], 'reference': out['reference_pre_match'],
                      'joueurs': len(out['joueurs']), 'sortie': SORTIE,
                      'descriptif_seulement': True}, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
