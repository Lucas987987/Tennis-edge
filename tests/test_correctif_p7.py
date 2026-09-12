#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_correctif_p7.py — Tests du correctif de segmentation (12/09/2026).

Les tests FONCTIONNELS tournent sur le vrai moves_detail_hist.csv : c'est là
que le bug vivait, et un cas synthétique n'aurait rien prouvé -- la fonction
`segment_circuit` ne se trompait pas sur les libellés qu'on lui imaginait,
elle se trompait sur ceux que le fournisseur envoie vraiment.

Env :  SCRIPTS (défaut ./scripts) · STATIQUES_SEULEMENT=1
"""
import csv
import os
import sys

SCRIPTS = os.path.abspath(os.environ.get('SCRIPTS', 'scripts'))
RACINE = os.path.dirname(SCRIPTS) or '.'
sys.path.insert(0, SCRIPTS)

echecs, oks = [], []


def verifie(nom, cond, detail=''):
    if cond:
        oks.append(nom)
        print(f"  ✅ {nom}")
    else:
        echecs.append(nom)
        print(f"  ❌ {nom}" + (f" — {detail}" if detail else ''))


def t1_classification():
    print("\nT1 — les Grands Chelems ne tombent plus dans 'autre'")
    import pistes_common as pc
    cas = [
        ('US Open Men Singles', 'Grand Chelem'),
        ('US Open Women Singles', 'Grand Chelem'),
        ('Wimbledon Men Singles', 'Grand Chelem'),
        ('French Open Men Singles', 'Grand Chelem'),
        ('Australian Open Women Singles', 'Grand Chelem'),
        # non-régression : ce qui marchait doit continuer
        ('ATP Challenger Cassis', 'Challenger'),
        ('ATP Cincinnati', 'ATP'),
        ('WTA Cincinnati', 'WTA'),
        ('WTA Bad Homburg Women Singles', 'WTA'),
        ('Berlin', 'autre'),
    ]
    for libelle, attendu in cas:
        obtenu = pc.segment_circuit(libelle)
        verifie(f"{libelle!r} -> {attendu}", obtenu == attendu,
                f"obtenu : {obtenu!r}")
    verifie("un Challenger n'est jamais reclassé Grand Chelem",
            pc.segment_circuit('ATP Challenger US Open Cup') == 'Challenger',
            "l'ordre des tests a changé")


def t2_bucket_autre_visible():
    print("\nT2 — le fourre-tout 'autre' est rendu visible")
    import pistes_common as pc
    verifie("libelles_non_classes existe", hasattr(pc, 'libelles_non_classes'))
    if not hasattr(pc, 'libelles_non_classes'):
        return
    faux = [{'tour': 'Zzz Open'}, {'tour': 'Zzz Open'}, {'tour': 'ATP Halle'}]
    res = pc.libelles_non_classes(faux)
    verifie("remonte le libellé inconnu avec son effectif",
            res and res[0] == ('Zzz Open', 2), f"obtenu : {res}")
    src = open(os.path.join(SCRIPTS, 'segments_study.py'), encoding='utf-8').read()
    verifie("segments_study.py affiche le contenu de 'autre'",
            'libelles_non_classes' in src,
            "sans cet affichage, le prochain libellé inconnu dormira "
            "encore trois semaines")
    verifie("segments_study.py boucle sur le segment Grand Chelem",
            "'Grand Chelem'" in src)


def t3_donnees_reelles():
    print("\nT3 — sur le vrai moves_detail_hist.csv")
    chemin = os.path.join(RACINE, 'moves_detail_hist.csv')
    if not os.path.exists(chemin):
        verifie("moves_detail_hist.csv présent", False, chemin)
        return
    import pistes_common as pc
    tours = [r['tour'] for r in csv.DictReader(open(chemin, encoding='utf-8'))]
    n = len(tours)
    seg = [pc.segment_circuit(t) for t in tours]
    n_autre = sum(1 for s in seg if s == 'autre')
    n_gc = sum(1 for s in seg if s == 'Grand Chelem')
    print(f"     n={n} | Grand Chelem={n_gc} | autre={n_autre} "
          f"({100 * n_autre / max(n, 1):.1f}%)")
    verifie("'autre' retombe sous 5% de la population",
            n_autre / max(n, 1) < 0.05,
            f"{n_autre}/{n} — un libellé courant échappe encore au classement")
    verifie("le segment Grand Chelem est peuplé (n>=30)", n_gc >= 30,
            f"n={n_gc}")
    # le protocole gelé le 25/08 ne doit pas bouger
    n_ch = sum(1 for s in seg if s == 'Challenger')
    verifie("la population Challenger est inchangée par le correctif",
            n_ch == sum(1 for t in tours
                        if 'Challenger' in (t or '') or (t or '').startswith('CH')),
            "la règle gelée a été touchée — cela exigerait un nouveau gel")


def main():
    print(f"Scripts testés : {SCRIPTS}")
    t1_classification()
    t2_bucket_autre_visible()
    if os.environ.get('STATIQUES_SEULEMENT') != '1':
        t3_donnees_reelles()
    print(f"\n{len(oks)} test(s) OK · {len(echecs)} échec(s)")
    for e in echecs:
        print(f"  - {e}")
    return 1 if echecs else 0


if __name__ == '__main__':
    sys.exit(main())
