#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthèse lisible des apprentissages et décisions de la semaine.

Lecture seule des rapports existants : ce module n'entraîne rien, ne promeut
aucun challenger et ne modifie pas le champion. Les populations restent séparées
et une mesure absente n'est jamais remplacée par zéro.
"""
import argparse
import datetime as dt
import json
import os

SCHEMA = 'recap_apprentissage_v1'
FICHIERS = {
    'facteurs': 'facteurs.json',
    'choix': 'choix_simulation.json',
    'stabilite': 'stabilite.json',
    'evaluation': 'rapport_evaluation_sorties.json',
    'recalibrage': 'rapport_recalibrage.json',
    'derive': 'rapport_surveillance_derive.json',
    'gouvernance': 'rapport_gouvernance.json',
}
NOMS_GROUPES = {
    'forme_fatigue': 'Forme et fatigue',
    'vitesse_court': 'Vitesse du court',
    'morphologie': 'Morphologie',
    'points_importants': 'Points importants',
    'styles': 'Styles',
    'face_a_face': 'Face-à-face',
    'conditions': 'Conditions',
    'contexte_tournoi': 'Contexte du tournoi',
    'charting': 'Match Charting',
    'blessure': 'Blessure',
    'pression': 'Pression',
    'duree': 'Durée',
    'matchup': 'Matchup',
    'adversaires_communs': 'Adversaires communs',
}
NOMS_RECALIBRAGE = {
    'logistique': 'Régression logistique',
    'contraction_hierarchique': 'Contraction hiérarchique',
    'isotone': 'Isotone',
}


def _nombre(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _arrondi(v, n=6):
    v = _nombre(v)
    return round(v, n) if v is not None else None


def _metrique(doc, *cles):
    for cle in cles:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(cle)
    return doc


def _source(donnees, nom):
    doc = donnees.get(nom)
    return {'disponible': isinstance(doc, dict),
            'genere_le': doc.get('genere_le') if isinstance(doc, dict) else None}


def _facteurs(doc):
    doc = doc or {}
    groupes = doc.get('groupes') or {}
    adoptes = sorted(k for k, v in groupes.items() if isinstance(v, dict) and v.get('adopte') is True)
    non_adoptes = []
    for nom, v in sorted(groupes.items()):
        if not isinstance(v, dict) or v.get('adopte') is True:
            continue
        non_adoptes.append({'nom': nom, 'libelle': NOMS_GROUPES.get(nom, nom),
                            'adopte_brut': v.get('adopte_brut'),
                            'statut': v.get('stabilite') or 'non adopté'})
    ensemble = doc.get('ensemble_sur_le_jugement') or {}
    base, avec = ensemble.get('base') or {}, ensemble.get('avec') or {}
    ll_base, ll_avec = _nombre(base.get('log_loss')), _nombre(avec.get('log_loss'))
    ex_base, ex_avec = _nombre(base.get('reussite_pct')), _nombre(avec.get('reussite_pct'))
    return {
        'apprentissage_n': doc.get('apprentissage'), 'jugement_n': doc.get('jugement'),
        'fenetres': doc.get('fenetres') or {}, 'adoptes': adoptes,
        'non_adoptes': non_adoptes,
        'candidats_en_attente': [x['nom'] for x in non_adoptes if x['adopte_brut'] is True],
        'avant_apres_jugement': {
            'log_loss_avant': _arrondi(ll_base), 'log_loss_apres': _arrondi(ll_avec),
            'gain_log_loss': _arrondi(ll_base - ll_avec) if ll_base is not None and ll_avec is not None else None,
            'exactitude_avant_pct': _arrondi(ex_base, 3), 'exactitude_apres_pct': _arrondi(ex_avec, 3),
            'gain_exactitude_points': _arrondi(ex_avec - ex_base, 3) if ex_base is not None and ex_avec is not None else None,
        },
        'population': 'évaluation des facteurs, distincte des seuls pronostics directs récents',
    }


def _continu(doc):
    c = (doc or {}).get('combinaison_continue') or {}
    jugement = c.get('jugement') or {}
    return {
        'n': c.get('n'), 'minimum_n': c.get('min'), 'adopte': c.get('adopte'),
        'raison': c.get('raison'), 'poids': c.get('poids'),
        'poids_appris': c.get('poids_appris'), 'jugement': jugement,
        'statut': ('adopte' if c.get('adopte') is True else
                   'accumulation' if _nombre(c.get('n')) is not None and _nombre(c.get('n')) < (_nombre(c.get('min')) or 0)
                   else 'non_adopte' if c.get('adopte') is False else 'indisponible'),
        'population': 'premiers pronostics figés avec simulation et Elo, résultats ultérieurs',
    }


def _evaluation(doc):
    globale = (doc or {}).get('global') or {}
    combinaison = globale.get('combinaison') or {}
    victoire = combinaison.get('victoire') or {}
    return {
        'matchs': combinaison.get('matchs'),
        'log_loss': _metrique(victoire, 'log_loss', 'valeur'),
        'brier': _metrique(victoire, 'brier', 'valeur'),
        'exactitude': _metrique(victoire, 'exact', 'valeur'),
        'score_exact': _metrique(combinaison, 'scores', 'exact', 'valeur'),
        'jeux_mae': _metrique(combinaison, 'jeux', 'mae', 'valeur'),
        'population': 'pronostics récents évalués ; ne pas confondre avec le jugement des facteurs',
    }


def _decisions_recalibrage(bloc):
    bloc = bloc or {}
    return [{'nom': nom, 'libelle': NOMS_RECALIBRAGE.get(nom, nom),
             'adopte': d.get('adopte'), 'statut': d.get('statut'),
             'gain_log_loss_pondere': _arrondi(d.get('gain_log_loss_pondere')),
             'fenetres_positives': d.get('fenetres_positives'), 'fenetres': d.get('fenetres')}
            for nom, d in sorted((bloc.get('decisions') or {}).items()) if isinstance(d, dict)]


def _recalibrage(doc):
    doc = doc or {}
    direct, rejoue = doc.get('direct') or {}, doc.get('rejoue') or {}
    return {
        'direct': {'n': direct.get('n'), 'semaines': direct.get('semaines'),
                   'decisions': _decisions_recalibrage(direct),
                   'champion_actif_modifie': direct.get('champion_actif_modifie')},
        'rejoue': {'n': rejoue.get('n'), 'semaines': rejoue.get('semaines'),
                   'decisions': _decisions_recalibrage(rejoue)},
        'populations_separees': doc.get('populations_separees'),
    }


def _alertes_derive(doc):
    alertes = []
    for nom, bloc in ((doc or {}).get('fenetres') or {}).items():
        for alerte in bloc.get('alertes') or []:
            alertes.append(f'{nom}:{alerte}')
    for nom, bloc in ((doc or {}).get('groupes_12_semaines') or {}).items():
        if nom == 'global':
            continue
        for alerte in bloc.get('alertes') or []:
            alertes.append(f'{nom}:{alerte}')
    return sorted(set(alertes))


def _champion(doc):
    doc = doc or {}
    avant, apres = doc.get('champion_avant'), doc.get('champion_apres')
    return {
        'statut_gouvernance': doc.get('statut'),
        'initialisation': doc.get('initialisation'),
        'empreinte_avant': avant, 'empreinte_apres': apres,
        'modifie_cette_semaine': (avant != apres) if avant and apres else None,
        'promotions_demande_es': doc.get('promotions_demande_es') or [],
        'promotions_retenues': doc.get('promotions_retenues') or [],
        'promotions_differees': doc.get('promotions_differees') or [],
        'periodes': doc.get('periodes') or {},
        'decisions_sans_trace_stabilite': doc.get('decisions_sans_trace_stabilite') or [],
    }


def construire(donnees, genere_le=None):
    """Construit la synthèse sans modifier les dictionnaires sources."""
    gouvernance = donnees.get('gouvernance') or {}
    derive = donnees.get('derive') or {}
    semaine = gouvernance.get('semaine')
    if not semaine:
        iso = dt.datetime.now(dt.timezone.utc).date().isocalendar()
        semaine = f'{iso.year}-W{iso.week:02d}'
    sources = {nom: _source(donnees, nom) for nom in FICHIERS}
    manquantes = sorted(nom for nom, s in sources.items() if not s['disponible'])
    champion = _champion(gouvernance)
    alertes = _alertes_derive(derive)
    if champion['statut_gouvernance'] == 'a_verifier':
        statut = 'a_verifier'
    elif alertes or str(derive.get('statut') or '').startswith('alerte'):
        statut = 'alerte'
    elif manquantes:
        statut = 'partiel'
    else:
        statut = 'ok'
    return {
        'schema': SCHEMA, 'semaine': semaine,
        'genere_le': genere_le or dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'statut': statut, 'lecture_seule': True, 'modifie_apprentissage': False,
        'marche_utilise': False, 'sources': sources, 'sources_manquantes': manquantes,
        'facteurs': _facteurs(donnees.get('facteurs')),
        'apprentissage_continu': _continu(donnees.get('choix')),
        'performance_recente': _evaluation(donnees.get('evaluation')),
        'recalibrage': _recalibrage(donnees.get('recalibrage')),
        'derive': {'statut': derive.get('statut'), 'n': derive.get('n'),
                   'date_de_reference': derive.get('date_de_reference'), 'alertes': alertes},
        'champion': champion,
        'avertissement': ('Synthèse descriptive des rapports existants. Les populations ne sont pas agrégées ; '
                          'aucune adoption nouvelle et aucune promesse de taux de réussite ou de ROI.'),
    }


def _fmt(v, suffixe=''):
    return f'{v}{suffixe}' if v is not None else '—'


def _bool(v):
    return 'oui' if v is True else 'non' if v is False else '—'


def _noms(noms):
    return ', '.join(NOMS_GROUPES.get(n, n) for n in noms) if noms else 'Aucun'


def markdown(recap):
    f, c = recap['facteurs'], recap['apprentissage_continu']
    p, r, d, ch = recap['performance_recente'], recap['recalibrage'], recap['derive'], recap['champion']
    av = f['avant_apres_jugement']
    lignes = [
        f"# Récapitulatif de l’apprentissage — {recap['semaine']}", '',
        f"Généré le {recap['genere_le']} · état **{recap['statut']}**.", '',
        '> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; '
        'aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.', '',
        '## En bref', '',
        f"- **Facteurs adoptés** : {_noms(f['adoptes'])}.",
        f"- **Candidats encore en attente** : {_noms(f['candidats_en_attente'])}.",
        f"- **Apprentissage sur nos propres pronostics** : {c['statut']} — "
        f"{_fmt(c['n'])}/{_fmt(c['minimum_n'])} matchs documentés ; {c.get('raison') or 'décision indisponible'}",
        f"- **Pronostics récents évalués** : {_fmt(p['matchs'])} matchs ; exactitude de la combinaison "
        f"{_fmt(round(100 * p['exactitude'], 2) if p['exactitude'] is not None else None, ' %')}.",
        f"- **Dérive** : {d['statut'] or 'indisponible'} ; {len(d['alertes'])} alerte(s).",
        f"- **Champion modifié cette semaine** : {_bool(ch['modifie_cette_semaine'])}"
        f"{' (initialisation du suivi)' if ch['initialisation'] else ''}.", '',
        '## Facteurs : apprentissage et jugement', '',
        f"Effectifs : **{_fmt(f['apprentissage_n'])}** matchs d’apprentissage et "
        f"**{_fmt(f['jugement_n'])}** matchs de jugement.", '',
        '| Mesure sur le jugement | Avant | Après | Variation favorable |',
        '|---|---:|---:|---:|',
        f"| Log loss | {_fmt(av['log_loss_avant'])} | {_fmt(av['log_loss_apres'])} | {_fmt(av['gain_log_loss'])} |",
        f"| Exactitude | {_fmt(av['exactitude_avant_pct'], ' %')} | {_fmt(av['exactitude_apres_pct'], ' %')} | "
        f"{_fmt(av['gain_exactitude_points'], ' point(s)')} |", '',
        'La log loss est plus faible quand elle est meilleure. Ce avant/après appartient au jugement des facteurs ; '
        'il n’est pas mélangé avec les pronostics récents ci-dessous.', '',
        '### Groupes non adoptés ou en accumulation', '',
        '| Groupe | Candidat brut | Statut |', '|---|---|---|',
    ]
    if f['non_adoptes']:
        for g in f['non_adoptes']:
            lignes.append(f"| {g['libelle']} | {_bool(g['adopte_brut'])} | {g['statut']} |")
    else:
        lignes.append('| Aucun | — | — |')
    lignes += [
        '', '## Performance des pronostics récents', '',
        '| Matchs | Log loss | Brier | Exactitude | Score exact | Erreur moyenne de jeux |',
        '|---:|---:|---:|---:|---:|---:|',
        f"| {_fmt(p['matchs'])} | {_fmt(p['log_loss'])} | {_fmt(p['brier'])} | "
        f"{_fmt(round(100 * p['exactitude'], 2) if p['exactitude'] is not None else None, ' %')} | "
        f"{_fmt(round(100 * p['score_exact'], 2) if p['score_exact'] is not None else None, ' %')} | {_fmt(p['jeux_mae'])} |",
        '', '## Recalibrage : décisions séparées', '',
        f"Direct : **{_fmt(r['direct']['n'])}** pronostics sur **{_fmt(r['direct']['semaines'])}** semaine(s). "
        f"Rejoué : **{_fmt(r['rejoue']['n'])}** pronostics sur **{_fmt(r['rejoue']['semaines'])}** semaine(s). "
        'Les deux populations ne sont jamais agrégées.', '',
        '| Population | Méthode | Statut | Gain pondéré de log loss | Fenêtres positives | Adopté |',
        '|---|---|---|---:|---:|---|',
    ]
    for population in ('direct', 'rejoue'):
        decisions = r[population]['decisions']
        if not decisions:
            lignes.append(f'| {population} | Aucune décision disponible | — | — | — | — |')
        for x in decisions:
            lignes.append(f"| {population} | {x['libelle']} | {x['statut'] or '—'} | "
                          f"{_fmt(x['gain_log_loss_pondere'])} | {_fmt(x['fenetres_positives'])}/{_fmt(x['fenetres'])} | "
                          f"{_bool(x['adopte'])} |")
    lignes += [
        '', '## Gouvernance, dérive et champion', '',
        f"- **Gouvernance** : {ch['statut_gouvernance'] or 'indisponible'}.",
        f"- **Promotions retenues** : {', '.join(ch['promotions_retenues']) or 'aucune'}.",
        f"- **Promotions différées** : {', '.join(ch['promotions_differees']) or 'aucune'}.",
        f"- **Dérive** : {d['statut'] or 'indisponible'}, sur {_fmt(d['n'])} matchs ; "
        f"alertes : {', '.join(d['alertes']) or 'aucune'}.",
        f"- **Empreinte du champion** : `{ch['empreinte_apres'] or 'indisponible'}`.",
        f"- **Sources manquantes** : {', '.join(recap['sources_manquantes']) or 'aucune'}.", '',
        'Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective '
        'supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.', '',
    ]
    return '\n'.join(lignes)


def _charger(racine):
    out = {}
    for nom, fichier in FICHIERS.items():
        try:
            with open(os.path.join(racine, 'simulateur', fichier), encoding='utf-8') as fh:
                value = json.load(fh)
            out[nom] = value if isinstance(value, dict) else None
        except (OSError, ValueError):
            out[nom] = None
    return out


def main(racine='.'):
    recap = construire(_charger(racine))
    dossier = os.path.join(racine, 'simulateur')
    os.makedirs(dossier, exist_ok=True)
    with open(os.path.join(dossier, 'recap_apprentissage.json'), 'w', encoding='utf-8') as fh:
        json.dump(recap, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(dossier, 'recap_apprentissage.md'), 'w', encoding='utf-8') as fh:
        fh.write(markdown(recap))
    print('Récapitulatif apprentissage :', recap['statut'], '·', recap['semaine'], flush=True)
    return recap


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
