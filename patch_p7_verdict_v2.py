#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_p7_verdict_v2.py — Met à jour le constat P7 avec les chiffres
mesurés APRÈS la régénération du CSV causal (13/09/2026).

POURQUOI UNE SECONDE VERSION
Le constat inscrit le 12/09 reposait sur `moves_detail_hist.csv` tel qu'il
existait alors : ampleur rétrospective, Grands Chelems dans 'autre'. Depuis,
`move_audit.py` a régénéré le fichier avec la colonne causale et le segment
Grand Chelem est en place. La population passe de n=1296 à n=1348, le témoin
de 67,1 % à 66,7 %, et le Challenger de 59,8 % [53 ; 66] à 58 % [52 ; 64].

Conséquence : ce qui était une séparation LIMITE (la borne haute touchait le
témoin) est maintenant une séparation FRANCHE. Le constat du 12/09 était
prudent à raison, il est aujourd'hui dépassé.

L'ancien statut n'est pas effacé : il rejoint `historique_statuts`. Un
registre d'hypothèses qui n'affiche que sa dernière version ne vaut rien ;
c'est la SUITE des constats qui montre comment la mesure s'est affinée.

À lancer depuis la racine du dépôt. --dry-run pour prévisualiser.
"""
import json
import os
import sys

CHEMIN = 'frozen_pistes.json'
CLE = 'P7_segments'
MARQUEUR = 'CONSTAT 13/09/2026'

STATUT = (
    "CONSTAT 13/09/2026 (metrique du protocole : clv_book_pct ; remplace le "
    "constat du 12/09, voir historique_statuts). "
    "Mesure faite sur moves_detail_hist.csv REGENERE avec la colonne "
    "d'ampleur causale et le segment Grand Chelem en place. "
    "| Temoin global 66.7% de CLV>0 (n=1348) : "
    "ATP 70% [65;74] n=399 med +4.7% ; WTA 66% [61;70] n=409 med +4.2% ; "
    "Challenger 58% [52;64] n=240 med +2.7% ; "
    "Grand Chelem 71% [65;76] n=272 med +4.6% ; "
    "autre 28 (Berlin seul, n<30, circuit indeterminable depuis le libelle). "
    "| LECTURE : l'hypothese gelee le 25/08 predisait que les circuits "
    "peripheriques, moins efficients, donneraient un CLV SUPERIEUR au temoin. "
    "Le Challenger sort a 58% [52;64] contre un temoin a 66.7%, n=240 : le "
    "temoin est HORS de l'intervalle, la separation est franche et la "
    "direction est l'INVERSE de celle predite. Le 12/09 la separation etait "
    "limite (borne haute 66 contre temoin 67.1) ; la regeneration du CSV l'a "
    "rendue nette. Aucun autre segment ne se separe du temoin. "
    "| STATUT : HYPOTHESE CONTREDITE. Le critere gele (IC95 separe du temoin "
    "a n>=30) est rempli, mais dans le sens oppose a la prediction. "
    "| RESERVE IMPORTANTE : la population couvre tout l'historique, "
    "majoritairement ANTERIEUR au gel du 25/08 -- elle est donc largement "
    "in-sample. Le protocole exige un verdict sur donnees posterieures au "
    "gel. Ce constat ferme la direction predite ; il ne vaut pas validation "
    "de la direction inverse. "
    "| SUITE : 'Challengers PLUS efficients que le temoin' est une hypothese "
    "NOUVELLE, negation de celle gelee le 25/08. Elle ne peut pas heriter de "
    "ce gel. Si elle doit etre testee, elle exige son propre gel date et une "
    "fenetre de donnees posterieure a ce gel. Ne rien reoptimiser d'ici la."
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
        print(f"❌ cle '{CLE}' absente — structure inattendue, rien n'est ecrit.")
        return 1

    p = pistes[CLE]
    if MARQUEUR in p.get('statut_gel', ''):
        print("ℹ️ le constat du 13/09 est deja inscrit — rien a faire.")
        return 0

    avant_test = p.get('test')

    # empile l'historique plutot que de l'ecraser
    hist = p.get('historique_statuts')
    if not isinstance(hist, list):
        hist = []
    if p.get('statut_gel'):
        hist.append(p['statut_gel'])
    if p.get('statut_gel_precedent'):
        hist.append(p.pop('statut_gel_precedent'))
    p['historique_statuts'] = hist
    p['statut_gel'] = STATUT

    if p.get('test') != avant_test:
        print("❌ le champ 'test' a change — abandon.")
        return 1

    print(f"--- nouveau statut ---\n{STATUT}\n")
    print(f"--- historique conserve : {len(hist)} constat(s) anterieur(s) ---")
    for i, h in enumerate(hist, 1):
        print(f"  [{i}] {h[:110]}...")
    if dry:
        print("\n(--dry-run : rien n'a ete ecrit)")
        return 0

    tmp = CHEMIN + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(tmp, CHEMIN)          # ecriture atomique
    print(f"\n✅ {CHEMIN} mis a jour ({CLE}).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
