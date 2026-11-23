#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""site_leger.py — version légère des données pour les visiteurs du site (21/11/2026, paquet 328, Lucas : « vitesse »).

algo/donnees.json reste le fichier complet (vidéos, cartes, contrôles de la chaîne, fiches figées le lisent). Pour le
visiteur, au moment de publier le site (workflow pages.yml) :
  site.json      — ce que la page affiche en arrivant, sans les champs qu'elle ne lit jamais (distribution complète des
                   scores exacts, feuilles « brutes », horodatages internes…) ;
  site_plus.json — les blocs du bas de page (bilan détaillé, étalonnage, journal des changements, validation de la
                   fiabilité), chargés juste après le premier affichage.
  site_libre.json — 23/11/2026 (paquet 377) : ce que reçoit un visiteur SANS accès Plus (le worker choisit) : le match du
                   jour complet (le match offert), les autres matchs réduits à l'affiche (joueurs, tournoi, heure),
                   sans aucun pourcentage ni détail ; les bilans des matchs passés restent publics.
La page lit site.json et, s'il manque, donnees.json : rien ne casse si ce script n'a pas tourné.
Usage : python scripts/site_leger.py algo/donnees.json <dossier de sortie>
"""
import gzip
import json
import os
import sys

INUTILES_MATCH = ('distribution_scores', 'distribution_reste', 'feuille_prevue_brute', 'feuille_fourchette_brute',
                  'horodatage', 'scores_simules', 'scores_source', 'salle_appliquee', 'commence_garde', 'salle_brut')
INUTILES_HAUT = ('qualite_horodatages', 'styles_descriptifs_source', 'bilan_lignes')
PLUS = ('bilan', 'journal_changements', 'validation_fiabilite')
# 23/11/2026 (paquet 380, Lucas) : sections internes (journal des changements, suivi de la fiabilité, données de service,
# calibration) — jamais dans les fichiers des visiteurs ni des abonnés ; site_admin.json, servi au seul administrateur
INTERNES = ('journal_changements', 'validation_fiabilite', 'desaccords', 'qualite_donnees', 'rejoue')
# 377 : champs d'un match réservé gardés dans la version libre (l'affiche seulement)
AFFICHE = ('uid', 'debut', 'debut_utc', 'tournoi', 'circuit', 'surface', 'meilleur_des', 'home', 'away', 'pays', 'en_salle')


def libre(site):
    """Version sans accès Plus : le match du jour complet, les autres matchs à l'affiche seulement (« verrou »)."""
    offert = ((site.get('match_du_jour') or {}).get('uid'))
    out = dict(site)
    out['matchs'] = [m if m.get('uid') == offert else dict({k: m[k] for k in AFFICHE if k in m}, verrou=True)
                     for m in site.get('matchs') or []]
    out['acces'] = 'libre'
    return out


def decouper(doc):
    site = {k: v for k, v in doc.items() if k not in INUTILES_HAUT and k not in PLUS and k not in INTERNES}
    site['matchs'] = [{k: v for k, v in m.items() if k not in INUTILES_MATCH} for m in doc.get('matchs') or []]
    site['_plus'] = 'site_plus.json'
    plus = {k: doc[k] for k in PLUS if k in doc and k not in INTERNES}
    if isinstance(plus.get('bilan'), dict) and 'calibration' in plus['bilan']:
        plus['bilan'] = {k: v for k, v in plus['bilan'].items() if k != 'calibration'}
    return site, plus


def interne(doc):
    """380 : ce que seul l'administrateur voit (sections internes du bas de page)."""
    out = {k: doc[k] for k in INTERNES if k in doc}
    out['bilan_calibration'] = (doc.get('bilan') or {}).get('calibration') or []
    return out


def main(argv):
    src, dossier = argv[1], argv[2]
    with open(src, encoding='utf-8') as f:
        doc = json.load(f)
    site, plus = decouper(doc)
    os.makedirs(dossier, exist_ok=True)
    for nom, d in (('site.json', site), ('site_plus.json', plus), ('site_libre.json', libre(site)),
                   ('site_admin.json', interne(doc))):
        b = json.dumps(d, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        with open(os.path.join(dossier, nom), 'wb') as f:
            f.write(b)
        print(f"{nom} : {len(b) / 1e3:.0f} Ko ({len(gzip.compress(b)) / 1e3:.0f} Ko compressé)")
    b = open(src, 'rb').read()
    print(f"donnees.json : {len(b) / 1e3:.0f} Ko ({len(gzip.compress(b)) / 1e3:.0f} Ko compressé)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
