"""Garde-fous communs champion–challenger, exécutés après les études hebdomadaires.

- périodes de jugement disjointes pour l'apprentissage continu ;
- décisions stabilisées et traçables ;
- au plus une nouvelle promotion par semaine, toutes règles confondues ;
- retour à l'entrée champion précédente pour toute promotion excédentaire.

Ce module ne calcule pas de pronostic et ne lit aucune donnée de marché.
"""
import argparse
import datetime as dt
import hashlib
import json
import os

CLES_EXCLUES = {'apprentissage_continu_suivi'}


def _regles(choix):
    return {k: v for k, v in choix.items() if k not in CLES_EXCLUES and isinstance(v, dict) and 'adopte' in v}


def _empreinte(choix):
    brut = json.dumps(_regles(choix), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(brut).hexdigest()


def _audit_periodes(choix, precedent=None):
    suivi = choix.get('apprentissage_continu_suivi') or {}
    continu = choix.get('combinaison_continue') or {}
    precedent = (((precedent or {}).get('choix') or {}).get('combinaison_continue') or {}).get('jugement') or {}
    courant = continu.get('jugement') or {}
    problemes = []
    if suivi.get('juge_jusqua') and courant.get('jusqua') and courant['jusqua'] < suivi['juge_jusqua']:
        problemes.append('La période courante recule avant la période déjà jugée.')
    nouveau_verdict = courant.get('jusqua') and courant.get('jusqua') != precedent.get('jusqua')
    if nouveau_verdict and precedent.get('jusqua') and courant.get('depuis') and courant['depuis'] <= precedent['jusqua']:
        problemes.append('Chevauchement des périodes de jugement.')
    if nouveau_verdict and precedent and (courant.get('n') or 0) < 30:
        problemes.append('Moins de 30 nouveaux matchs dans le jugement.')
    return {'juge_jusqua': suivi.get('juge_jusqua'), 'jugement_courant': courant,
            'minimum_nouveaux_matchs': 30, 'n_nouveaux': courant.get('n'),
            'ok': not problemes, 'problemes': problemes}


def appliquer(choix, stabilite, precedent, semaine=None):
    """Renvoie (choix, stabilite, rapport) ; ne modifie pas les entrées déjà championnes."""
    semaine = semaine or dt.datetime.now(dt.timezone.utc).date().isocalendar()[:2]
    semaine = f'{semaine[0]}-W{semaine[1]:02d}' if isinstance(semaine, tuple) else str(semaine)
    regles = _regles(choix)
    ancien = _regles(precedent.get('choix') or {})
    initialisation = not precedent
    nouvelles = [] if initialisation else [k for k, v in regles.items() if v.get('adopte') and not (ancien.get(k) or {}).get('adopte')]
    retraits = []
    if len(nouvelles) > 1:
        # Le gain est mesuré contre le champion ; à égalité, ordre stable et reproductible.
        nouvelles.sort(key=lambda k: (-float((stabilite.get(k) or {}).get('gain') or 0.0), k))
        for k in nouvelles[1:]:
            if k in ancien:
                choix[k] = ancien[k]
            else:
                choix.pop(k, None)
            if k in stabilite:
                stabilite[k]['adopte'] = False
                stabilite[k]['serie'] = stabilite[k]['serie_avant'] = 0
            retraits.append(k)
    periodes = _audit_periodes(choix, precedent)
    non_tracees = [k for k, v in _regles(choix).items() if v.get('adopte') and 'adopte_brut' in v and not v.get('stabilite')]
    rapport = {
        'semaine': semaine, 'initialisation': initialisation,
        'promotions_demande_es': nouvelles, 'promotions_retenues': nouvelles[:1],
        'promotions_differees': retraits,
        'regle_promotion': 'Au plus une nouvelle règle adoptée par semaine ; priorité au plus grand gain de log loss.',
        'periodes': periodes, 'decisions_sans_trace_stabilite': non_tracees,
        'champion_avant': precedent.get('empreinte'), 'champion_apres': _empreinte(choix),
        'statut': 'ok' if periodes['ok'] and not non_tracees else 'a_verifier',
    }
    return choix, stabilite, rapport


def main(racine='.'):
    dossier = os.path.join(racine, 'simulateur')
    cp = os.path.join(dossier, 'choix_simulation.json')
    sp = os.path.join(dossier, 'stabilite.json')
    ep = os.path.join(dossier, 'gouvernance_etat.json')
    try:
        choix = json.load(open(cp, encoding='utf-8'))
    except (OSError, ValueError):
        choix = {}
    try:
        stabilite = json.load(open(sp, encoding='utf-8'))
    except (OSError, ValueError):
        stabilite = {}
    try:
        precedent = json.load(open(ep, encoding='utf-8'))
    except (OSError, ValueError):
        precedent = {}
    choix, stabilite, rapport = appliquer(choix, stabilite, precedent)
    json.dump(choix, open(cp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(stabilite, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    etat = {'empreinte': rapport['champion_apres'], 'choix': {k: v for k, v in choix.items() if k in _regles(choix)},
            'semaine': rapport['semaine']}
    json.dump(etat, open(ep, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    rapport['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat()
    path = os.path.join(dossier, 'rapport_gouvernance.json')
    json.dump(rapport, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Gouvernance :', rapport['statut'], '· promotions différées', rapport['promotions_differees'], flush=True)
    return rapport


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
