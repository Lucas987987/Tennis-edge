#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coffre.py — le COFFRE PRIVÉ du projet (23/10/2026) : des fichiers qui ne doivent plus être lisibles dans le dépôt
public, rangés dans R2 (privé) sous le préfixe « prive/ ».

Pourquoi : le dépôt est public (les workflows y sont gratuits). Tout fichier commité se lit par n'importe qui.
Les canaux H18, H19 et H20 sont privés (« ne pas diffuser ») : leurs journaux et leurs états, les verdicts du Lab
qui en sortent et le pronostic complet du jour ne doivent plus être commités ni publiés sur GitHub Pages.

Fonctionnement, dans chaque workflow qui lit ou écrit ces fichiers :
  pull    : rapatrie depuis R2 la version du coffre (sinon garde la copie locale — premier passage) ;
  push    : renvoie au coffre les fichiers modifiés (écriture conditionnelle ; deux runs qui se croisent sur un
            journal .jsonl : les lignes des deux sont gardées) ;
  retirer : sort du suivi git les fichiers que le coffre détient À L'IDENTIQUE (git rm --cached) ; le .gitignore
            les empêche d'y revenir. Rien n'est retiré si R2 est indisponible : jamais de perte.
Le site public n'en reçoit rien ; Lucas les lit dans le Lab par le worker « algo » (/prive/…, clé privée).

Limite assumée : l'historique git (versions passées de ces fichiers) reste lisible — le réécrire demanderait un
push forcé, exclu sur ce dépôt.
22/11/2026 (paquet 334, Lucas : « basculer un maximum de choses en privé ») — groupe « suivi » : les journaux de suivi
(paper_trades_*), le CLV du canal et le rapport CLV contre la médiane. Ces fichiers sont RÉÉCRITS (positions qui se
ferment, lignes recalculées), pas seulement prolongés : l'union de lignes les abîmerait. Pour ce groupe (PROTEGES) :
  pull  garde une copie de base (.coffre_base/) et son ETag ;
  push  n'écrit que si le coffre n'a pas bougé depuis le pull (If-Match) ; s'il a bougé, fusion à trois voies
        (git merge-file : base, la nôtre, celle du coffre), comme le faisait git entre deux workflows ; en cas de
        conflit réel, la version du coffre est gardée et un avertissement est affiché (rien n'est écrasé) ;
        un fichier qui n'a PAS été rapatrié dans ce run n'est jamais envoyé par-dessus le coffre ;
  rendre remet la version git des fichiers encore suivis (avant les opérations git d'un workflow qui n'a fait que lire).
22/11/2026 (paquet 338, Lucas : cotes et cotes de clôture en privé, étape 1) — groupe « lab_sorties » : ce que le
calcul quotidien du Lab écrit (CLV Pinnacle par book, stabilité, propositions, explorateur, registre, croisements,
cache des cotes avant signal) ; groupe « lab_donnees » : l'instantané du Lab (data.js), reconstruit par pages.yml.
Un seul rédacteur par fichier (lab_quotidien, ou pages) : envoi simple. Un motif « dossier/* » couvre un dossier
entier (registre mensuel) ; ses fichiers ont une clé à part, prive/<dossier>/<nom>, pour qu'un index.json ne
remplace jamais un autre index.json du coffre.
Usage : python scripts/coffre.py pull|push|retirer|rendre [--groupe …] [--si-present]
"""
import argparse
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_io  # noqa: E402

PREFIXE = 'prive/'
GROUPES = {
    # écrits par courbes_alertes.yml (canaux privés)
    'signaux': ['h18_signal_log.jsonl', 'h18_signal_state.json', 'h19_signal_log.jsonl', 'h19_signal_state.json',
                'h20_signal_log.jsonl', 'h20_signal_state.json'],
    # écrits par lab_quotidien.yml (verdicts des canaux privés)
    'lab': ['Tennis_Edge_Lab/live/valeur.json', 'Tennis_Edge_Lab/live/h20.json',
            # 22/11/2026 (paquet 335) : « le prix tient-il après l'alerte ? » (CLV du canal par circuit) — privé
            'Tennis_Edge_Lab/live/delai_alertes.json'],
    # écrit par pronostics_quotidien.yml (pronostic complet du jour : réservé)
    'pronostics': ['Tennis_Edge_Lab/live/pronostics.json'],
}
# entrées du Lab quotidien : seul le journal H19 est relu (verdict de H19) ; le journal H18 n'est PAS rapatrié
# dans le Lab, sans quoi l'explorateur et data.json (publiés) le republieraient
GROUPES['lab_entrees'] = ['h19_signal_log.jsonl']
# 28/10/2026 : rapport ROI (règles R1/R2) — interne, jamais dans le dépôt public ; écrit par pronostic.yml
GROUPES['roi'] = ['simulateur/rapport_roi_algo.json', 'simulateur/rapport_desaccords.json']
# 22/11/2026 (paquet 334) : journaux de suivi et CLV — écrits par courbes_alertes.yml (paper_trades_*) et
# steam_pipeline.yml (paper_trades_*, canal_clv_*, clv_vs_median_report) ; lus par le Lab, pages.yml, lab_quotidien,
# suivi_une_par_match, video_resume, polymarket_studies, freeze_thresholds
GROUPES['suivi'] = ['paper_trades_match.jsonl', 'paper_trades_set1.jsonl', 'paper_trades_set2.jsonl',
                    'paper_trades_canal.jsonl', 'paper_canal_report.json', 'canal_clv_detail.csv', 'canal_clv_exclus.csv',
                    'canal_clv_detail_avant_correction_2026-09-13.csv', 'clv_vs_median_report.json']
PROTEGES = {'suivi', 'lab_sorties', 'lab_donnees'}   # 338 : un fichier non rapatrié n'écrase jamais le coffre
BASE = '.coffre_base'
GROUPES['tous'] = [f for k in ('signaux', 'lab', 'pronostics') for f in GROUPES[k]]
# 335 : ce que pages.yml rapatrie pour le Lab (servi ensuite seulement derrière la connexion)
GROUPES['lab_site'] = ['Tennis_Edge_Lab/live/delai_alertes.json']
# 338 : sorties du calcul quotidien du Lab (lab_quotidien.yml les écrit ; pages.yml et lab_gel.yml les lisent)
_LIVE = 'Tennis_Edge_Lab/live/'
GROUPES['lab_sorties'] = [_LIVE + n for n in (
    'bookmakers_sets.json', 'bookmakers_sets_audit.json', 'candidate_watch_v62_prospective.json',
    'history_stability.json', 'propositions_v66.json', 'propositions_v66_populations.json.gz', 'gel_v66_prospective.json',
    'gel_explorateur_prospective.json', 'profils_hypotheses.json', 'reconciliation_hypotheses.json',
    'worker_hypotheses_capture.json', 'explorateur_alertes.json.gz', 'explorateur_histo.json.gz',
    'explorateur_matchs.json.gz', 'explorateur_detections.json.gz', 'lectures_profils.json', 'croisements.json')] + [
    'Tennis_Edge_Lab/cache/parts_features.json', 'Tennis_Edge_Lab/cache/parts_features_public.json.gz',
    _LIVE + 'registre/*']
# 338 : instantané du Lab, reconstruit à chaque déploiement (pages.yml) ; la version précédente sert au contrôle
# « plus de 40 % des observations ont disparu »
GROUPES['lab_donnees'] = ['Tennis_Edge_Lab/data.js']
# 22/11/2026 (paquet 345, cotes en privé, étape 2) — journaux et états des canaux d'alertes (canal public, MISER, H13 à
# H17, zone) : écrits par courbes_alertes.yml ; lus par steam_pipeline (verdicts en direct), lab_quotidien, pages
# (instantané du Lab) et pronostic (recherche externe)
GROUPES['canaux'] = ['canal_public_log.jsonl', 'canal_public_state.json', 'miser_signal_log.jsonl',
                     'h13_signal_log.jsonl', 'h13_signal_state.json', 'h14_signal_log.jsonl', 'h14_signal_state.json',
                     'h15_signal_log.jsonl', 'h15_signal_state.json', 'h16_signal_log.jsonl', 'h16_signal_state.json',
                     'h16b_signal_log.jsonl', 'h16b_signal_state.json', 'h17_signal_log.jsonl', 'h17_signal_state.json',
                     'zone_signal_log.jsonl', 'zone_signal_state.json']
# 345 — verdicts (CLV contre la clôture) : écrits par steam_pipeline (suivi_direct.py, validation_report.py) et par
# courbes_alertes (steam_alert.py : suivi_canaux.json ; validation_report.py : verdicts_geles.json) ; lus par le Lab,
# les scripts d'alertes (bilan en direct) et l'observateur externe
GROUPES['verdicts'] = ['verdicts_direct.json', 'suivi_canaux.json', 'verdicts_geles.json']
PROTEGES |= {'canaux', 'verdicts'}   # deux rédacteurs possibles, et des états à ne jamais écraser par une copie périmée
# servis au Lab par le worker « algo » (nom de fichier seul, sans dossier)
SERVIS = sorted({os.path.basename(f) for f in GROUPES['tous']})


DOSSIERS = {_LIVE + 'registre': 'registre'}     # dossier entier au coffre → sous-préfixe propre


def cle(chemin):
    d = os.path.dirname(chemin)
    if d in DOSSIERS:
        return PREFIXE + DOSSIERS[d] + '/' + os.path.basename(chemin)
    return PREFIXE + os.path.basename(chemin)


def _nom_base(f):
    """Nom de la copie de base (.coffre_base/) : tiré de la clé, pour que deux index.json ne se confondent pas."""
    return cle(f)[len(PREFIXE):].replace('/', '__')


def developper(fichiers, r2=None):
    """Remplace « dossier/* » par ses fichiers : ceux du coffre (si r2 est donné) et ceux présents en local."""
    import glob
    out = []
    for f in fichiers:
        if not f.endswith('/*'):
            out.append(f)
            continue
        d = f[:-2]
        noms = {os.path.basename(p) for p in glob.glob(os.path.join(d, '*')) if os.path.isfile(p)}
        if r2 is not None and d in DOSSIERS:
            pre = PREFIXE + DOSSIERS[d] + '/'
            try:
                noms |= {k[len(pre):] for k, _ in r2.list(pre) if k[len(pre):] and '/' not in k[len(pre):]}
            except Exception as e:                       # liste indisponible : les fichiers locaux seulement
                print(f"  coffre : liste de {pre} indisponible ({type(e).__name__})")
        out += [os.path.join(d, n) for n in sorted(noms)]
    return out


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _lire(chemin):
    try:
        with open(chemin, 'rb') as f:
            return f.read()
    except OSError:
        return None


def union_jsonl(distant, local):
    """Lignes du coffre, puis celles du local qu'il n'a pas (ordre gardé)."""
    vues = set(distant.splitlines())
    ajout = [l for l in local.splitlines() if l.strip() and l not in vues]
    base = distant if distant.endswith(b'\n') or not distant else distant + b'\n'
    return base + b''.join(l + b'\n' for l in ajout)


def pull(fichiers, r2):
    for f in fichiers:
        got = r2.get_with_etag(cle(f))
        if got is None:
            print(f"  coffre : {f} absent — copie locale gardée{' (absente aussi)' if _lire(f) is None else ''}")
            continue
        if _lire(f) != got[0]:
            os.makedirs(os.path.dirname(f) or '.', exist_ok=True)
            r2_io._write_atomic(f, got[0])
        print(f"  coffre → {f} ({len(got[0])} octets)")


def _etats(base=BASE):
    try:
        import json
        with open(os.path.join(base, 'etags.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ecrire_etats(etats, base=BASE):
    import json
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, 'etags.json'), 'w', encoding='utf-8') as f:
        json.dump(etats, f, ensure_ascii=False, indent=1, sort_keys=True)


def pull_protege(fichiers, r2, base=BASE):
    """Comme pull, en gardant la base (contenu + ETag) pour la fusion du push."""
    etats = _etats(base)
    for f in fichiers:
        got = r2.get_with_etag(cle(f))
        if got is None:
            etats[f] = {'etag': None}
            print(f"  coffre : {f} absent — copie locale gardée{' (absente aussi)' if _lire(f) is None else ''}")
            continue
        if _lire(f) != got[0]:
            os.makedirs(os.path.dirname(f) or '.', exist_ok=True)
            r2_io._write_atomic(f, got[0])
        os.makedirs(base, exist_ok=True)
        r2_io._write_atomic(os.path.join(base, _nom_base(f)), got[0])
        etats[f] = {'etag': got[1]}
        print(f"  coffre → {f} ({len(got[0])} octets)")
    _ecrire_etats(etats, base)


def fusion3(notre, base, leur):
    """Fusion à trois voies (git merge-file). (octets fusionnés, True) ou (None, False) en cas de conflit."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        chemins = []
        for nom, b in (('notre', notre), ('base', base), ('leur', leur)):
            p = os.path.join(d, nom)
            with open(p, 'wb') as fh:
                fh.write(b)
            chemins.append(p)
        r = subprocess.run(['git', 'merge-file', '-p', *chemins], capture_output=True)
        if r.returncode != 0:
            return None, False
        return r.stdout, True


def push_protege(fichiers, r2, base=BASE):
    etats, echecs = _etats(base), 0
    for f in fichiers:
        data = _lire(f)
        if data is None:
            continue
        if f not in etats:
            if r2.get_with_etag(cle(f)) is None:
                try:
                    r2.put(cle(f), data, create_only=True, content_type='application/json')
                    print(f"  {f} → coffre (création, {len(data)} octets)")
                except r2_io.PreconditionFailed:
                    print(f"::warning::{f} : créé entre-temps par un autre run — non envoyé")
            else:
                print(f"  {f} : pas rapatrié dans ce run — jamais envoyé par-dessus le coffre")
            continue
        etag = etats[f].get('etag')
        b = _lire(os.path.join(base, _nom_base(f))) if etag else b''
        if etag and data == b:
            continue                                     # rien de changé dans ce run
        for _ in range(5):
            try:
                if etag:
                    r2.put(cle(f), data, if_match=etag, content_type='application/json')
                else:
                    r2.put(cle(f), data, create_only=True, content_type='application/json')
                r2_io._write_atomic(f, data)
                print(f"  {f} → coffre ({len(data)} octets)")
                break
            except r2_io.PreconditionFailed:
                got = r2.get_with_etag(cle(f))
                if got is None:
                    etag, b = None, b''
                    continue
                fus, ok = fusion3(data, b or b'', got[0])
                if not ok:
                    echecs += 1
                    print(f"::warning::{f} : modifié en même temps par un autre run, fusion impossible — la version du "
                          f"coffre est gardée, celle de ce run est perdue pour ce fichier")
                    break
                data, b, etag = fus, got[0], got[1]
        else:
            echecs += 1
            print(f"::warning::{f} : envoi au coffre impossible (conflits répétés) — reste local")
    return echecs


def rendre(fichiers):
    """Remet la version git des fichiers encore suivis (un workflow qui n'a fait que lire, avant ses opérations git)."""
    suivis = subprocess.run(['git', 'ls-files', '--', *fichiers], capture_output=True, text=True).stdout.split()
    if suivis:
        subprocess.run(['git', 'checkout', '--', *suivis], check=False)
        print(f"  coffre : {len(suivis)} fichier(s) remis dans leur version git (lecture seule)")


def push(fichiers, r2):
    echecs = 0
    for f in fichiers:
        data = _lire(f)
        if data is None:
            continue
        for _ in range(4):
            got = r2.get_with_etag(cle(f))
            if got is not None and got[0] == data:
                break
            cible = data
            if got is not None and f.endswith('.jsonl'):
                cible = union_jsonl(got[0], data)
                if cible == got[0]:
                    break
            try:
                r2.put(cle(f), cible, create_only=got is None, if_match=got[1] if got else None,
                       content_type='application/json')
                if cible != data:
                    r2_io._write_atomic(f, cible)
                print(f"  {f} → coffre ({len(cible)} octets)")
                break
            except r2_io.PreconditionFailed:
                continue
        else:
            echecs += 1
            print(f"::warning::{f} : envoi au coffre impossible (conflits répétés) — reste local")
    return echecs


def retirer(fichiers, r2, si_present=False):
    """git rm --cached des fichiers suivis que le coffre détient à l'identique.
    28/10/2026 — si_present : retire aussi un fichier suivi dont le coffre détient une AUTRE version (le coffre
    est la source à jour ; la copie git est une ancienne version figée). Jamais si le coffre n'en a aucune."""
    suivis = set(subprocess.run(['git', 'ls-files', '--', *fichiers], capture_output=True, text=True).stdout.split())
    for f in sorted(suivis):
        data, got = _lire(f), r2.get_with_etag(cle(f))
        if si_present and got is not None and got[0]:
            subprocess.run(['git', 'rm', '--cached', '--quiet', '--', f], check=False)
            print(f"  {f} : retiré du dépôt (le coffre en a une version, {len(got[0])} octets)")
            continue
        if data is None or got is None or _sha(got[0]) != _sha(data):
            print(f"  {f} : gardé dans git (le coffre n'en a pas une copie identique)")
            continue
        subprocess.run(['git', 'rm', '--cached', '--quiet', '--', f], check=False)
        print(f"  {f} : retiré du dépôt (gardé au coffre)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['pull', 'push', 'retirer', 'rendre'])
    ap.add_argument('--groupe', default='tous', choices=sorted(GROUPES))
    ap.add_argument('--si-present', action='store_true',
                    help="retirer : aussi quand le coffre a une autre version (copie git figée et périmée)")
    a = ap.parse_args(argv)
    fichiers = GROUPES[a.groupe]
    if a.action == 'rendre':
        rendre(developper(fichiers))
        return 0
    r2 = r2_io.client()
    if r2 is None:
        print('coffre : R2 indisponible — rien à faire (les fichiers restent tels quels).')
        return 0
    fichiers = developper(fichiers, r2)
    if a.action == 'pull':
        (pull_protege if a.groupe in PROTEGES else pull)(fichiers, r2)
        return 0
    if a.action == 'push':
        return 1 if (push_protege if a.groupe in PROTEGES else push)(fichiers, r2) else 0
    retirer(fichiers, r2, si_present=a.si_present)
    return 0


if __name__ == '__main__':
    sys.exit(main())
