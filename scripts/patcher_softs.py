#!/usr/bin/env python3
"""patcher_softs.py — ferme la dernière fuite de la liste des books d'entrée.

    python scripts/patcher_softs.py --dry    # montre sans rien écrire
    python scripts/patcher_softs.py          # applique

LE DÉFAUT
---------
validation_report.py définit H14_SOFTS, sept books, et son commentaire
l'annonce comme « source de vérité UNIQUE, partagée par move_audit.py […]
et par h13_signal.py ».

Six scripts l'importent : h15, h16, h16b, h17, h18, zone.
Deux ne l'importent pas — précisément les deux que le commentaire nomme :

    move_audit.py:37   SOFTS = os.environ.get('SOFTS', 'unibet,bwin,betsson')
    h13_signal.py:72   idem

Et `SOFTS` n'apparaît dans aucun workflow. Les deux retombent donc sur le
défaut à trois books. Mesuré sur moves_detail_hist.csv : 1 776 lignes de
juin à octobre, pas un seul bet365, 888sport, betway ni leovegas.

CE QUE ÇA PRODUISAIT
--------------------
Six détecteurs envoient des alertes en prenant le meilleur prix parmi
sept books. move_audit, qui produit moves_detail_hist.csv — la population
sur laquelle tout est jugé — mesure le meilleur prix parmi trois.

Le juge et les détecteurs regardaient deux populations différentes, sans
qu'aucune erreur ne se déclenche. C'est mot pour mot ce que le commentaire
du 09/09 redoutait, arrivé dans l'autre sens.

Biais conservateur : moins de books, moins bon prix d'entrée, donc le CLV
et le ROI publiés SOUS-ESTIMENT ce que les alertes offraient. Mesures du
dépôt : 3 books CLV +3,7 % / ROI +2,0 % ; 7 books +4,3 % / +2,7 %.

LE CORRECTIF
------------
Celui déjà appliqué à la bande de cote le 06/09 : supprimer la variable
d'environnement, importer la constante. Une liste lue dans l'environnement
finit toujours par diverger de la liste gelée ; une constante importée,
non. Après ce patch, `SOFTS` n'est plus réglable de l'extérieur, et c'est
le but.

CE QUE LE PATCH NE FAIT PAS
---------------------------
Il ne reconstruit pas moves_detail_hist.csv. Le fichier reste sur trois
books jusqu'à ce que move_audit soit rejoué sur l'historique :

    CURVES=book_curves.jsonl OUT=moves_detail_hist.csv python scripts/move_audit.py

Cette reconstruction CHANGE LA POPULATION JUGÉE de toutes les hypothèses
qui lisent ce fichier. À dater et à annoncer, pas à faire en silence.
"""

import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))

# Le bloc à remplacer, à la mise en page près : move_audit l'écrit sur une
# ligne, h13_signal sur deux. Un seul motif couvre les deux.
MOTIF = re.compile(
    r"SOFTS\s*=\s*\[b\.strip\(\)\s*for b in os\.environ\.get\(\s*\n?\s*"
    r"'SOFTS',\s*'unibet,bwin,betsson'\)\.split\(','\)\s*if b\.strip\(\)\]")

NOUVEAU = (
    "# BOOKS D'ENTRÉE : importés de validation_report, jamais relus dans\n"
    "# l'environnement. La variable SOFTS n'était posée dans aucun workflow :\n"
    "# ce script retombait sur trois books pendant que six détecteurs en\n"
    "# utilisaient sept. Une constante importée ne peut pas diverger.\n"
    "SOFTS = list(_vr.H14_SOFTS)")

ANCRE_PATH = 'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))'
IMPORT_VR = 'import validation_report as _vr'

# Les docstrings annoncent encore SOFTS comme variable d'environnement. Les
# laisser, c'est garder dans le fichier le mode d'emploi de la panne qu'on
# vient de fermer : la prochaine personne poserait SOFTS=... et ne
# comprendrait pas pourquoi rien ne change.
DOCS = [
    ('  SHARP (pinnacle), SOFTS (unibet,bwin,betsson), THR',
     '  SHARP (pinnacle), THR'),
    ('Env : CURVES (déf. book_curves_live.jsonl), SHARP, SOFTS, THR, MIN_LEAD,',
     'Env : CURVES (déf. book_curves_live.jsonl), SHARP, THR, MIN_LEAD,'),
    ('  - entrée : meilleur prix parmi SOFTS sur le côté steamé',
     '  - entrée : meilleur prix parmi _vr.H14_SOFTS sur le côté steamé'),
]


def patcher(nom, sec):
    chemin = os.path.join(ICI, nom)
    if not os.path.exists(chemin):
        return 'absent'
    src = open(chemin, encoding='utf-8').read()
    faits = []

    if 'list(_vr.H14_SOFTS)' in src:
        return 'déjà patché'

    n = len(MOTIF.findall(src))
    if n != 1:
        return f'MOTIF SOFTS TROUVÉ {n} FOIS (attendu 1) — non modifié'

    pos_softs = MOTIF.search(src).start()
    pos_import = src.find(IMPORT_VR)

    # _vr doit être importé AVANT la ligne qu'on écrit, sinon NameError au
    # chargement. Trois cas, et h13_signal est le piège : il importe _vr,
    # mais huit lignes APRÈS l'endroit où SOFTS est défini.
    if pos_import == -1:
        if ANCRE_PATH not in src:
            return 'NI IMPORT _vr NI sys.path — non modifié'
        src = src.replace(
            ANCRE_PATH,
            ANCRE_PATH + '\n' + IMPORT_VR
            + '      # noqa: E402 — constantes gelées', 1)
        faits.append('import _vr ajouté')
    elif pos_import > pos_softs:
        # On retire l'import tardif et on le remonte sous sys.path : garder
        # les deux marcherait (ré-import = non-opération) mais laisserait un
        # F811 et, surtout, deux endroits où chercher la vérité.
        ligne = [l for l in src.split('\n')
                 if l.startswith(IMPORT_VR)][0]
        src = src.replace('\n' + ligne, '', 1)
        src = src.replace(
            ANCRE_PATH, ANCRE_PATH + '\n' + ligne, 1)
        faits.append('import _vr remonté avant SOFTS')
    else:
        faits.append('import _vr déjà en place')

    src = MOTIF.sub(lambda m: NOUVEAU, src, count=1)
    faits.append('SOFTS importé de H14_SOFTS')

    nd = 0
    for avant, apres in DOCS:
        if avant in src:
            src = src.replace(avant, apres, 1)
            nd += 1
    if nd:
        faits.append(f'{nd} mention(s) obsolète(s) corrigée(s)')

    try:
        compile(src, chemin, 'exec')
    except SyntaxError as e:
        return f'SYNTAXE CASSÉE ligne {e.lineno} — NON ÉCRIT ({e.msg})'

    if not sec:
        open(chemin, 'w', encoding='utf-8').write(src)
    return ', '.join(faits)


def verifier():
    """Charge les deux modules et compare leur SOFTS à la constante gelée.

    Le patch n'est utile que s'il produit la MÊME liste que les six autres
    scripts. Compiler ne le prouve pas ; importer, si.
    """
    sys.path.insert(0, ICI)
    import validation_report as vr
    attendu = list(vr.H14_SOFTS)
    ok = True
    for nom in ('move_audit', 'h13_signal'):
        try:
            m = __import__(nom)
            got = list(getattr(m, 'SOFTS', []))
            bon = got == attendu
            ok = ok and bon
            print(f'  {nom:14} {len(got)} books {"=" if bon else "≠"} H14_SOFTS'
                  f'  {got if not bon else ""}')
        except Exception as e:
            ok = False
            print(f'  {nom:14} IMPORT IMPOSSIBLE : {type(e).__name__} {e}')
    print(f'  attendu : {attendu}')
    return ok


def main():
    sec = '--dry' in sys.argv
    ko = 0
    for nom in ('move_audit.py', 'h13_signal.py'):
        r = patcher(nom, sec)
        print(f'{nom:18} {r}')
        if 'NON MODIFIÉ' in r.upper() or 'CASSÉE' in r or r == 'absent':
            ko += 1

    if sec:
        print('\n(simulation, rien écrit)')
        return 0
    if ko:
        print(f'\n{ko} fichier(s) à voir — rien d\'autre fait.')
        return 1

    print('\nVérification par import :')
    if not verifier():
        print('\nÉCHEC : les deux scripts ne voient pas la même liste que '
              'les six autres. Ne pas commiter.')
        return 1
    print('\nPatch appliqué et vérifié.')
    print('\nmoves_detail_hist.csv reste sur 3 books tant que move_audit '
          'n\'est pas rejoué sur l\'historique.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
