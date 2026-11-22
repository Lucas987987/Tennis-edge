#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controle_prive.py — CONTRÔLE DE LA BASCULE PRIVÉE (22/11/2026, paquet 353, Lucas : « Contrôle de la bascule privée »).

Les fichiers de cotes et les journaux privés vivent au coffre R2 (scripts/coffre.py, scripts/cotes_privees.py,
scripts/etat_chaud.py). Ce contrôle vérifie, une fois par jour, sans rien modifier :
  1. AU COFFRE  : chaque fichier privé y a une copie (non vide) ;
  2. FRAIS      : les fichiers qui ont un rédacteur régulier ont été envoyés récemment (seuil par fichier) ;
  3. HORS GIT   : en mode ETAT_CHAUD=prive, plus aucun n'est suivi par git (dépôt public) ;
  4. SITE PRIVÉ : les copies de l'onglet Direct du Lab sont présentes et fraîches.

Ne modifie rien. Le journal d'Actions (public) n'affiche que des nombres et des NOMS DE FICHIERS (déjà
écrits dans le code public), jamais un contenu. Le rapport complet part au coffre (prive/controle_prive.json).
CODE DE SORTIE : en mode « prive », 1 si un problème est trouvé (le run devient rouge) ; dans les autres modes, les
problèmes sont des avertissements (le coffre se remplit au fil des passages des rédacteurs) et le code reste 0.
Usage : python scripts/controle_prive.py
"""
import datetime as dt
import json
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

# Âge maximal (heures) d'une copie au coffre, pour les fichiers qui ont un rédacteur régulier. Les autres (journaux qui
# ne grandissent que s'il y a un signal, rapports lancés à la main, fichiers figés) ne sont contrôlés qu'en présence.
FRAICHEUR_H = {
    'closing_lines.json': 12, 'matches_oddspapi.json': 12, 'live_odds.json': 12,          # capture (5–10 min)
    'moves_detail.csv': 30, 'moves_detail_hist.csv': 30, 'suivi_direct/resultats.json': 30,  # steam_pipeline (1/jour)
    'resultats_oddspapi.json': 30,                                                         # settlement (2/jour)
    'kalshi_lead_obs.jsonl': 30,                                                           # polymarket_studies
    'courbes_absences.json': 30,                                                           # fetch_book_curves
    'value_candidates.jsonl': 30,                                                          # value_journal
    'direct_matchs.json': 12,                                                              # courbes_alertes
}
FRAICHEUR_SITE_H = {'direct_matchs.json': 12, 'live_odds.json': 12}


def mode():
    m = str(os.environ.get('ETAT_CHAUD', 'double')).strip().lower()
    return m if m in ('off', 'double', 'on', 'prive') else 'double'


def inventaire():
    """[(fichier, clé R2, famille)] — tout ce qui doit vivre au coffre."""
    import coffre as C
    import cotes_privees as CP
    import etat_chaud as EC
    out, vus = [], set()
    for f in CP.CHAUDS:
        out.append((f, EC.PREFIXE + f, 'chauds'))
        vus.add(f)
    for g in CP.GROUPES_ENTIERS:
        for f in C.GROUPES[g]:
            if f not in vus:
                out.append((f, C.cle(f), g))
                vus.add(f)
    for g, L in sorted(C.GROUPES.items()):
        if g in ('tous',) or g in CP.GROUPES_ENTIERS:
            continue
        for f in L:
            if f.endswith('/*') or f in vus:
                continue
            out.append((f, C.cle(f), g))
            vus.add(f)
    mois = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
    f = f'closing_lines/closing_lines_{mois}.jsonl'
    out.append((f, C.cle(f), 'archives'))
    return out


def _tete(r2, cle):
    """(taille, âge en heures ou None) ou None si absent."""
    try:
        h = r2.client.head_object(Bucket=r2.bucket, Key=cle)
    except Exception:  # noqa: BLE001
        return None
    t = h.get('LastModified')
    age = None
    if t is not None:
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        age = (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600
    return int(h.get('ContentLength') or 0), age


def suivis(chemins):
    r = subprocess.run(['git', 'ls-files', '--', *chemins], capture_output=True, text=True)
    return set(r.stdout.split()) if r.returncode == 0 else set()


def controler(r2, m, inv=None):
    import cotes_privees as CP
    inv = inventaire() if inv is None else inv
    dans_git = suivis([f for f, _, _ in inv])
    lignes, problemes, avert = [], [], []
    for f, cle, fam in inv:
        t = _tete(r2, cle)
        L = {'fichier': f, 'famille': fam, 'au_coffre': bool(t and t[0] > 0),
             'octets': t[0] if t else 0, 'age_h': round(t[1], 1) if t and t[1] is not None else None,
             'dans_git': f in dans_git}
        seuil = FRAICHEUR_H.get(f)
        if not L['au_coffre'] and (seuil is not None or L['dans_git']):
            L['etat'] = 'absent du coffre'
        elif not L['au_coffre']:
            L['etat'] = 'jamais créé'          # journal optionnel ou fichier pas encore produit : pas une panne
        elif seuil is not None and L['age_h'] is not None and L['age_h'] > seuil:
            L['etat'] = f'périmé (> {seuil} h)'
        elif m == 'prive' and L['dans_git']:
            L['etat'] = 'encore dans le dépôt public'
        else:
            L['etat'] = 'ok'
        lignes.append(L)
        if L['etat'] not in ('ok', 'jamais créé'):
            # hors « prive », tout est avertissement (le coffre se remplit au passage de chaque rédacteur) ; en « prive »,
            # un fichier sans rédacteur régulier (rapport lancé à la main, fichier figé) encore dans git attend le
            # prochain passage de son workflow : avertissement aussi
            grave = m == 'prive' and (seuil is not None or L['etat'] != 'encore dans le dépôt public')
            (problemes if grave else avert).append(L)
    site = []
    for n in CP.SITE_DIRECT:
        t = _tete(r2, CP.PREFIXE_SITE_DIRECT + n)
        S = {'fichier': n, 'present': bool(t and t[0] > 0), 'age_h': round(t[1], 1) if t and t[1] is not None else None}
        seuil = FRAICHEUR_SITE_H.get(n)
        S['etat'] = ('absent' if not S['present'] else
                     (f'périmé (> {seuil} h)' if seuil and S['age_h'] is not None and S['age_h'] > seuil else 'ok'))
        site.append(S)
        if S['etat'] != 'ok':
            (problemes if m == 'prive' else avert).append({'fichier': 'site privé du Lab : ' + n, 'etat': S['etat']})
    return {'genere_le': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), 'paquet': 353,
            'mode': m, 'fichiers': lignes, 'site_direct': site,
            'resume': {'fichiers': len(lignes), 'au_coffre': sum(L['au_coffre'] for L in lignes),
                       'jamais_crees': sum(L['etat'] == 'jamais créé' for L in lignes),
                       'encore_dans_git': sum(L['dans_git'] for L in lignes),
                       'problemes': len(problemes), 'avertissements': len(avert)},
            'problemes': [{'fichier': p['fichier'], 'etat': p['etat']} for p in problemes],
            'avertissements': [{'fichier': p['fichier'], 'etat': p['etat']} for p in avert]}


def main(argv):
    m = mode()
    import r2_io
    r2 = r2_io.client(quiet=True)
    if r2 is None:
        print('Contrôle privé : R2 absent, rien à contrôler.')
        return 0
    doc = controler(r2, m)
    try:
        r2.put('prive/controle_prive.json', json.dumps(doc, ensure_ascii=False, indent=1).encode('utf-8'),
               content_type='application/json')
    except Exception:  # noqa: BLE001
        print('::warning::rapport non envoyé au coffre')
    r = doc['resume']
    print(f"Contrôle de la bascule privée (mode {m}) : {r['fichiers']} fichiers · {r['au_coffre']} au coffre · "
          f"{r['encore_dans_git']} encore dans git · {r['jamais_crees']} jamais créé(s) · {r['problemes']} problème(s) · {r['avertissements']} avertissement(s)")
    for p in doc['problemes']:
        print(f"::error::{p['fichier']} : {p['etat']}")
    for p in doc['avertissements']:
        print(f"::warning::{p['fichier']} : {p['etat']}")
    return 1 if doc['problemes'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
