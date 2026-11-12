#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_anciennes_etudes.py — les études d'avant l'audit rejouées avec l'Elo de la production (12/11/2026, paquet 247)

LE DÉFAUT (audit, section 2, « elo_des_etudes »). 18 études d'avant l'audit rejouaient l'archive avec un Elo SANS
RÉGLAGE (pas les options de elo_etat.json, départ 1200 en Challenger et en ITF) et, pour la plupart, FIGÉ pendant tout
le tournoi (mis à jour au changement de date, et la date de l'archive est celle du début du tournoi). Sur 2016–2022,
l'Elo figé coûtait 0,002 à 0,004 de log loss ; un signal appris contre lui peut mesurer surtout ce défaut (le
« parcours dans le tournoi » mesurait les victoires que l'Elo figé n'avait pas encore comptées). Le paquet 233 a
rejugé les sept β du combiné ; les autres verdicts n'avaient jamais été rejoués.

LE REJEU. Chaque étude est relancée TELLE QUELLE (mêmes variables, même règle, même découpage des périodes), avec
deux changements seulement :
  1. son Elo sans réglage est réglé comme la production (elo.options_production) et le départ 1200 des joueurs vus d'abord
     en Challenger ou en ITF devient le départ en place ;
  2. l'archive lui est donnée avec la date du match décalée d'un jour par tour (Q1 = jour du début, … finale = jour
     10, bornée à la fin du tournoi) : l'étude met son Elo à jour au changement de date, il n'est donc plus figé
     pendant le tournoi (un joueur ne joue qu'un match par tour). Les dates restent dans la semaine du tournoi.
Les rapports d'origine ne sont pas touchés : les nouveaux sont écrits à part, puis comparés verdict par verdict.

RÈGLE ÉCRITE LE 12/11/2026, AVANT DE LANCER LE REJEU :
  - chaque étude garde SA règle (écrite avant, apprentissage puis jugement sur une période jamais vue) ;
  - un verdict qui ne change pas : rien à faire ;
  - un verdict POSITIF qui devient négatif : ce que l'étude a mis en production est listé pour retrait, sauf si le
    paquet 233 l'a déjà rejugé sur l'Elo de production (âge, retour d'absence, changement de surface, favori /
    outsider, parcours dans le tournoi : c'est la décision du 233 qui compte) ;
  - un verdict NÉGATIF qui devient positif : rien n'entre en production ; la piste est portée au fantôme, comme le
    prévoit la règle de l'étude ;
  - Challenger : l'archive n'a pas les résultats ITF hommes que le classement de production utilise (deux études ont
    changé de sens à cause de cela, paquets 229 et 230) : un verdict Challenger qui change est « non concluant ».
NON REJOUÉES ICI, avec la raison : la loupe descriptive privée (pas de verdict) ; etude_prior_elo
(l'Elo n'y sert que de point de départ des profils ; non retenue ; à rejouer si la piste est reprise) ;
etude_5_derniers_styles et etude_statistiques_styles (recherche, rien en production, l'Elo y est déjà mis à jour après
chaque match) ; etude_live_reevaluation (tourne en production : corrigée dans le code, voir ce paquet).

Usage : python simulateur/etude_anciennes_etudes.py /tmp/sackmann . [--seulement=etude_age,etude_cpi]
"""
import contextlib
import datetime as dt
import importlib
import json
import os
import shutil
import sys
import tempfile
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SORTIE = os.path.join(ICI, 'rapport_anciennes_etudes.json')
DEJA_REJUGE_233 = {'etude_age', 'etude_retour_absence', 'etude_changement_surface', 'etude_signaux_combines'}
ETUDES = ('etude_classement_serie', 'etude_pistes_saison', 'etude_pistes_tournoi', 'etude_profils_contexte',
          'etude_bilans_contexte', 'etude_set_decisif', 'etude_tiebreaks_joueurs', 'etude_cpi', 'etude_duels_styles',
          'etude_age', 'etude_retour_absence', 'etude_changement_surface', 'etude_signaux_combines')
CLES_VERDICT = ('retenue', 'retenu', 'positif', 'positive', 'adoptee', 'adopte', 'retenus')
NON_REJOUEES = {
    'loupe_descriptive_privee': "loupe descriptive privée, pas de verdict",
    'etude_prior_elo': "l'Elo n'y sert que de point de départ des profils ; non retenue ; à rejouer si la piste est reprise",
    'etude_5_derniers_styles': "recherche, rien en production ; Elo déjà mis à jour après chaque match",
    'etude_statistiques_styles': "recherche, rien en production ; Elo déjà mis à jour après chaque match",
    'etude_live_reevaluation': "tourne en production (suivi du % en direct) : corrigée dans le code au paquet 247"}


def decaler(M):
    import donnees as DN
    return DN.decaler_par_tour(M)


@contextlib.contextmanager
def elo_de_production(racine):
    """Pendant le bloc : le constructeur elo.Elo rend un Elo réglé comme la production (départ en place au lieu de 1200) et
    donnees.charger rend l'archive décalée par tour."""
    import donnees as DN
    import elo as E
    options, bas = E.options_production(racine)
    Base, charger = E.Elo, DN.charger

    class EloProduction(Base):
        def __init__(self, *a, **k):
            super().__init__(*a, **dict(options, **k))

        def presenter(self, j, valeur):
            return super().presenter(j, bas if (bas and valeur == 1200.0) else valeur)

    E.Elo = EloProduction
    DN.charger = lambda *a, **k: decaler(charger(*a, **k))
    try:
        yield
    finally:
        E.Elo, DN.charger = Base, charger


def verdicts(x, chemin=''):
    """{chemin: valeur} de tous les verdicts d'un rapport."""
    out = {}
    if isinstance(x, dict):
        for k, v in x.items():
            p = f"{chemin}/{k}" if chemin else str(k)
            if k in CLES_VERDICT and isinstance(v, (bool, list)):
                out[p] = sorted(v) if isinstance(v, list) else v
            elif isinstance(v, (dict, list)):
                out.update(verdicts(v, p))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            if isinstance(v, (dict, list)):
                out.update(verdicts(v, f"{chemin}[{i}]"))
    return out


def rapport_de(nom):
    mod = importlib.import_module(nom)
    s = getattr(mod, 'SORTIE', None)
    return s or os.path.join(ICI, {'etude_cpi': 'rapport_cpi.json'}.get(nom, f"rapport_{nom[6:]}.json"))


def lancer(nom, archive, racine, dossier):
    """Relance l'étude avec l'Elo de production ; renvoie (ancien rapport, nouveau rapport, minutes)."""
    chemin = rapport_de(nom)
    sauve = os.path.join(dossier, os.path.basename(chemin) + '.origine')
    shutil.copyfile(chemin, sauve)
    t0 = time.time()
    try:
        with elo_de_production(racine):
            mod = importlib.import_module(nom)
            if nom in ('etude_cpi', 'etude_duels_styles'):
                mod.main(archive, racine)
            else:
                mod.main([nom, archive, racine])
        nouveau = json.load(open(chemin, encoding='utf-8'))
    finally:
        shutil.copyfile(chemin, os.path.join(dossier, os.path.basename(chemin) + '.production'))
        shutil.copyfile(sauve, chemin)                     # le rapport d'origine est remis tel quel
    return json.load(open(sauve, encoding='utf-8')), nouveau, round((time.time() - t0) / 60, 1)


def comparer(nom, ancien, nouveau):
    a, n = verdicts(ancien), verdicts(nouveau)
    changes = []
    for k in sorted(set(a) | set(n)):
        if a.get(k) != n.get(k):
            ch = 'CH' in k.split('/')
            sens = ('devenu positif' if n.get(k) is True and a.get(k) is False else
                    'devenu négatif' if a.get(k) is True and n.get(k) is False else 'liste changée')
            sous = '/seule/' in k or k.startswith('comparaison_sans_role')
            suite = ('non concluant (Challenger : résultats ITF hommes absents de l\'archive)' if ch else
                     'sous-verdict ou comparaison descriptive : seul le verdict final de l\'étude compte' if sous else
                     'décision du paquet 233' if nom in DEJA_REJUGE_233 else
                     'à retirer de la production si elle y est' if sens == 'devenu négatif' else
                     'porté au fantôme' if sens == 'devenu positif' else 'à examiner')
            changes.append({'verdict': k, 'avant': a.get(k), 'avec_l_elo_de_production': n.get(k), 'sens': sens, 'suite': suite})
    return {'verdicts': len(set(a) | set(n)), 'positifs_avant': sum(1 for v in a.values() if v is True),
            'positifs_apres': sum(1 for v in n.values() if v is True), 'changements': changes}


def main(argv):
    args = [x for x in argv[1:] if not x.startswith('--')]
    opt = {x.split('=')[0]: x.split('=', 1)[1] for x in argv[1:] if x.startswith('--') and '=' in x}
    archive, racine = (args + ['/tmp/sackmann', os.path.join(ICI, '..')])[:2]
    noms = opt['--seulement'].split(',') if opt.get('--seulement') else ETUDES
    dossier = opt.get('--dossier') or tempfile.mkdtemp(prefix='anciennes_')
    os.makedirs(dossier, exist_ok=True)
    try:
        doc = json.load(open(SORTIE, encoding='utf-8')) if opt.get('--seulement') and os.path.exists(SORTIE) else {}
    except ValueError:
        doc = {}
    doc.update({'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 247, 'statut': 'etude',
                'regle': ("chaque étude relancée telle quelle, avec l'Elo réglé comme la production et mis à jour à chaque tour ; "
                          "elle garde sa propre règle ; un positif devenu négatif est listé pour retrait (sauf décision du "
                          "paquet 233), un négatif devenu positif est porté au fantôme ; Challenger non concluant"),
                'non_rejouees': NON_REJOUEES})
    E_ = doc.setdefault('etudes', {})
    for nom in noms:
        print(f"== {nom}", flush=True)
        try:
            ancien, nouveau, mn = lancer(nom, archive, racine, dossier)
            E_[nom] = dict(comparer(nom, ancien, nouveau), minutes=mn)
        except Exception as e:  # noqa: BLE001 — une étude en échec n'arrête pas les autres
            E_[nom] = {'erreur': f"{type(e).__name__}: {e}"}
        print(json.dumps(E_[nom], ensure_ascii=False)[:1500], flush=True)
        with open(SORTIE, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
    doc['resume'] = {n: ({'changements': len(v['changements']), 'positifs': f"{v['positifs_avant']} → {v['positifs_apres']}"}
                         if 'changements' in v else v) for n, v in E_.items()}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
