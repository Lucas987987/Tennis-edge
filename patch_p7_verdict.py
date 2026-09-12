#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_p7_verdict.py — Inscrit le constat P7 du 12/09/2026 dans
frozen_pistes.json.

À lancer depuis la racine du dépôt :  python3 patch_p7_verdict.py
Option --dry-run pour voir le résultat sans écrire.

POURQUOI UN SCRIPT ET PAS UNE ÉDITION À LA MAIN
frozen_pistes.json est le registre qui empêche de réécrire une hypothèse
après avoir vu les données. Une édition manuelle sur téléphone, dans un JSON
sans schéma, est exactement le geste qui abîme ce registre sans que rien ne
le signale. Le script relit le fichier, vérifie qu'il patche bien la clé
attendue, conserve tout le reste à l'identique, et refuse d'écrire si quoi
que ce soit ne correspond pas.
"""
import json
import os
import sys

CHEMIN = 'frozen_pistes.json'
CLE = 'P7_segments'

STATUT = (
    "CONSTAT 12/09/2026 (metrique du protocole : clv_book_pct). "
    "Correctif prealable : les Grands Chelems n'ont aucun prefixe ATP/WTA "
    "et tombaient tous dans 'autre' (167 moves sur 180 apres le 26/08) ; "
    "segment 'Grand Chelem' ajoute, regle Challenger et temoin global "
    "INCHANGES, donc le protocole gele le 25/08 n'est pas modifie. "
    "| Historique complet (n=1296, temoin 67.1%) : ATP 69.9% [65;74] n=399 ; "
    "WTA 65.3% [61;70] n=401 ; Challenger 59.8% [53;66] n=199 ; "
    "Grand Chelem 70.6% [65;76] n=269 ; autre 28 (Berlin seul, circuit "
    "indeterminable depuis le libelle). "
    "| HORS ECHANTILLON, post-gel >=26/08 (n=353, temoin 67.4%) : "
    "Challenger 60.1% [53;67] n=173 ; Grand Chelem 73.1% [66;79] n=167 ; "
    "ATP n=9 et WTA n=4, sous le seuil. "
    "| LECTURE : l'hypothese pre-specifiee disait Challengers moins "
    "efficients donc CLV SUPERIEUR au temoin. On observe l'inverse dans les "
    "deux fenetres -- direction contredite. Mais la separation n'est PAS "
    "franche hors echantillon : la borne haute du Challenger (67) touche le "
    "temoin (67.4). Le critere gele (IC95 separe du temoin a n>=30) n'est "
    "donc pas rempli proprement. Statut : DIRECTION CONTREDITE, separation "
    "limite, pas de verdict. Aucun segment ne se separe du temoin. "
    "| SUITE : laisser courir sans reoptimiser. Si le Challenger confirme "
    "sous le temoin sur une fenetre supplementaire, la piste devient "
    "'Challengers PLUS efficients', qui est une hypothese NOUVELLE et exige "
    "son propre gel date -- elle ne peut pas heriter du gel du 25/08, dont "
    "elle est la negation."
)


def main():
    dry = '--dry-run' in sys.argv
    if not os.path.exists(CHEMIN):
        print(f"❌ {CHEMIN} introuvable — lancer depuis la racine du depot.")
        return 1
    with open(CHEMIN, encoding='utf-8') as f:
        data = json.load(f)

    pistes = data.get('pistes')
    if not isinstance(pistes, dict) or CLE not in pistes:
        print(f"❌ cle '{CLE}' absente de frozen_pistes.json — structure "
              f"inattendue, rien n'est ecrit.")
        return 1

    ancien = pistes[CLE].get('statut_gel', '')
    if 'CONSTAT 12/09/2026' in ancien:
        print("ℹ️ le constat du 12/09 est deja inscrit — rien a faire.")
        return 0

    # le test gele ne bouge pas : seul le statut est mis a jour
    avant_test = pistes[CLE].get('test')
    pistes[CLE]['statut_gel_precedent'] = ancien
    pistes[CLE]['statut_gel'] = STATUT

    if pistes[CLE].get('test') != avant_test:
        print("❌ le champ 'test' a change — abandon.")
        return 1

    print(f"--- ancien statut ---\n{ancien}\n")
    print(f"--- nouveau statut ---\n{STATUT}\n")
    if dry:
        print("(--dry-run : rien n'a ete ecrit)")
        return 0

    tmp = CHEMIN + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(tmp, CHEMIN)          # ecriture atomique
    print(f"✅ {CHEMIN} mis a jour ({CLE}).")
    print("   L'ancien statut est conserve sous 'statut_gel_precedent'.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
