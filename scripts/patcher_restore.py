#!/usr/bin/env python3
"""patcher_restore.py — insère restore_curves dans les workflows qui lisent
l'historique sans le restaurer.

POURQUOI UN PATCHEUR ET NON DES FICHIERS PRÊTS
----------------------------------------------
Deux fois en septembre, j'ai livré des .yml pré-corrigés construits à
partir d'un instantané du dépôt — et deux fois ils ont écrasé une
correction posée entre-temps :

  * le 24/09 restore_curves est ajouté à steam_pipeline ; trois
    livraisons suivantes partent du dépôt d'origine et le suppriment.
    moves_detail_hist.csv tombe de 1 748 à 302 lignes.
  * le 03/10 le retry renforcé remplace la boucle ENTIÈRE de 20
    workflows, y compris l'appel à merge_json_state qu'elle contenait.
    fetch_clv échoue deux jours.

Ce script lit le fichier RÉEL, n'ajoute que ce qui manque, et ne touche à
rien d'autre. Relancé, il ne fait rien.

ORDRE D'INSERTION
-----------------
L'étape est placée avant la PREMIÈRE étape qui lance un script lecteur.
Placée après, elle ne servirait à rien : le script aurait déjà reconstruit
ses données sur un historique tronqué — sans lever d'erreur, ce qui est
précisément le défaut qu'on corrige.

Usage :
    python patcher_restore.py            # simulation
    python patcher_restore.py POSER      # écrit
"""

import glob
import os
import re
import sys

try:
    import yaml
except ImportError:
    print("❌ PyYAML requis : pip install pyyaml")
    sys.exit(1)

RACINE = os.getcwd()
WF = os.path.join(RACINE, '.github', 'workflows')
SCRIPTS = os.path.join(RACINE, 'scripts')

MARQUEURS = ('hist_partitions', 'iter_hist_lines', 'hist_book_',
             'hist_set1_', 'hist_set2_')

# Ces scripts touchent les partitions sans avoir besoin qu'elles soient
# restaurées : ils les suppriment, compressent ou déplacent. Exiger la
# restauration avant eux rapatrierait 160 Mo pour rien — et purge_data
# effacerait ce que restore_curves vient de ramener.
GESTIONNAIRES = {
    'purge_data', 'cleanup_duplicate_partitions', 'compress_hist_partitions',
    'migrate_hist_partitions', 'archive_curves', 'restore_curves',
    'curves_parts', 'scan_coherence', 'patcher_restore',
}

COMMENTAIRE = [
    "# RESTAURATION DES PARTITIONS ARCHIVEES.",
    "#",
    "# Ce workflow lance un script dont le resultat depend de",
    "# l'historique COMPLET. Depuis que archive_curves sort les",
    "# partitions de plus de 28 jours vers les releases curves-2026-*,",
    "# elles ne sont plus dans le depot : sans cette etape, le job",
    "# travaille sur un historique tronque SANS lever d'erreur.",
    "#",
    "# Constate le 02/10 sur book_index : 1 251 matchs au lieu de 1 863,",
    "# et une reactivite devenue negative partout. Les chiffres",
    "# changeaient sans que rien ne le signale.",
    "#",
    "# `|| true` : une panne de release ne doit pas bloquer le job.",
    "# restore_curves interroge l'index ET les releases directement.",
]


def lecteurs():
    """Scripts dont le resultat depend d'un historique complet."""
    out = set()
    for p in glob.glob(os.path.join(SCRIPTS, '*.py')):
        nom = os.path.basename(p)[:-3]
        if nom in GESTIONNAIRES:
            continue
        try:
            s = open(p, encoding='utf-8').read()
        except OSError:
            continue
        if any(m in s for m in MARQUEURS):
            out.add(nom)
    return out


def patcher(chemin, lect):
    s = open(chemin, encoding='utf-8').read()
    if 'restore_curves' in s:
        return None, "deja present"

    lances = set(re.findall(r'scripts/([a-z_0-9]+)\.py', s))
    concernes = lances & lect
    if not concernes:
        return None, None

    lignes = s.split('\n')
    debuts = [i for i, l in enumerate(lignes) if re.match(r'^(\s+)- name:', l)]
    if not debuts:
        return None, "aucune etape nommee"

    # Premiere etape dont le corps lance un script lecteur.
    cible = None
    for k, i in enumerate(debuts):
        fin = debuts[k + 1] if k + 1 < len(debuts) else len(lignes)
        corps = '\n'.join(lignes[i:fin])
        if any(f'scripts/{n}.py' in corps for n in concernes):
            cible = i
            break
    if cible is None:
        cible = debuts[0]

    ind = re.match(r'^(\s+)- name:', lignes[cible]).group(1)
    bloc = [f'{ind}{l}' if l else '' for l in COMMENTAIRE]
    bloc += [
        f'{ind}- name: Restaurer les partitions de courbes archivees',
        f'{ind}  env:',
        f'{ind}    GH_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}',
        f'{ind}  run: python scripts/restore_curves.py || true',
        '',
    ]
    neuf = '\n'.join(lignes[:cible] + bloc + lignes[cible:])

    try:
        yaml.safe_load(neuf)
    except Exception as e:
        return None, f"YAML casse : {str(e)[:60]}"

    # Verification du PLACEMENT sur le YAML charge, pas sur le texte :
    # une etape inseree au mauvais niveau d'indentation passerait le
    # parse mais se retrouverait hors du bloc steps.
    d = yaml.safe_load(neuf)
    job = list(d['jobs'].values())[0]
    noms = [st.get('name', '') for st in job['steps']]
    idx = [k for k, n in enumerate(noms) if 'Restaurer les partitions' in n]
    if not idx:
        return None, "etape inseree HORS du bloc steps"
    pos = idx[0]
    usage = None
    for k, st in enumerate(job['steps']):
        r = str(st.get('run', ''))
        if any(f'scripts/{n}.py' in r for n in concernes):
            usage = k
            break
    if usage is not None and pos > usage:
        return None, f"inseree APRES l'usage (etape {pos+1} > {usage+1})"

    return neuf, f"OK — etape {pos+1}/{len(noms)}, usage etape {usage+1 if usage is not None else '?'}"


def main():
    poser = len(sys.argv) > 1 and sys.argv[1] == 'POSER'
    lect = lecteurs()
    print(f"{len(lect)} script(s) dependant de l'historique complet :")
    print(f"  {', '.join(sorted(lect))}\n")

    faits, riens = [], 0
    for p in sorted(glob.glob(os.path.join(WF, '*.yml'))):
        neuf, msg = patcher(p, lect)
        nom = os.path.basename(p)
        if msg is None:
            riens += 1
            continue
        if neuf is None:
            if msg != "deja present":
                print(f"  ⚠️ {nom} : {msg}")
            continue
        print(f"  {'✅' if poser else '→ '} {nom} : {msg}")
        if poser:
            open(p, 'w', encoding='utf-8').write(neuf)
        faits.append(nom)

    print()
    if not faits:
        print("Rien a patcher.")
        return 0
    if not poser:
        print(f"SIMULATION — {len(faits)} fichier(s) a modifier.")
        print("Pour appliquer : python scripts/patcher_restore.py POSER")
    else:
        print(f"{len(faits)} fichier(s) modifie(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
