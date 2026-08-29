#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_status.py — Rend l'état du pipeline LISIBLE DEPUIS LE REPO.

POURQUOI CE SCRIPT
Toutes les pannes de ce projet ont la même signature : rien ne plante, tout est
vide, et il faut ouvrir les logs GitHub Actions pour s'en apercevoir — souvent
des jours plus tard.
  - 14/08 : push bloqué 5 jours (>100 Mo), avalé par "git push || true"
  - 15/08 : commit écarté en silence par "git pull --rebase" après commit
  - 15/08 : "git add" en bloc qui échoue si UN fichier manque
  - 16/08 : book_curves_live.jsonl absent -> sorties vides, aucun code d'erreur
  - 16/08 : resultats.json à "count": 0 depuis des semaines
Le point commun n'est pas la cause, c'est l'INVISIBILITÉ. Ce script inverse le
défaut : après chaque run, l'état de chaque livrable est écrit dans un fichier
COMMITÉ, donc consultable depuis GitHub sans ouvrir un seul log.

VERDICTS
  ✅ OK      — présent, non vide, écrit pendant ce run
  ⏳ FIGÉ    — présent mais pas réécrit pendant ce run (le script n'a rien produit)
  ⚠️ VIDE    — présent mais réduit à son en-tête / 0 entrée
  ❌ ABSENT  — pas produit du tout

SORTIES : pipeline_status.json (machine) + pipeline_status.md (lisible sur GitHub)

Env : RUN_STARTED (ISO 8601, injecté par le workflow — sert à distinguer
      "réécrit pendant ce run" de "figé depuis un run précédent"), OUT_JSON, OUT_MD.
"""
import os, sys, json, glob, datetime

OUT_JSON = os.environ.get('OUT_JSON', 'pipeline_status.json')
OUT_MD   = os.environ.get('OUT_MD', 'pipeline_status.md')

# (chemin, libellé, seuil d'octets sous lequel on considère le fichier vide
#  [, 'externe' si le fichier est produit par un AUTRE workflow])
# 'externe' — CORRIGÉ LE 25/08/2026 : resultats_derived.json est produit par
# results_bridge.py dans capture_closing (toutes les 5-10 min), PAS par le
# steam pipeline. Le juger sur « écrit pendant CE run » produisait un
# ❌/⏳ permanent — une fausse alerte qui polluait le monitoring, soit
# précisément le mode de panne que ce script existe pour éviter. Un livrable
# externe est jugé sur présence + taille + fraîcheur < 24 h, rien d'autre.
ARTIFACTS = [
    ('set_results.json',          'Résultats match + set',              200),
    ('resultats_derived.json',    'Pont résultats (études)',            200, 'externe'),
    ('paper_trades_match.jsonl',  'Journal forward — match',             50),
    ('paper_trades_set1.jsonl',   'Journal forward — set 1',             50),
    # 'optionnel' : peut être légitimement vide (peu d'alertes set 2) —
    # --strict ne doit pas rendre le pipeline rouge en permanence pour ça.
    ('paper_trades_set2.jsonl',   'Journal forward — set 2',              0, 'optionnel'),
    ('moves_detail.csv',          'Audit des moves (live)',             200),
    ('moves_detail_hist.csv',     'Audit des moves (historique)',       200),
    ('canal_clv_detail.csv',      'CLV réalisé du canal public',        100),
    ('book_curves_live.jsonl',    'Courbes live reconstruites',        1000),
]


def _run_started():
    s = os.environ.get('RUN_STARTED', '')
    try:
        return datetime.datetime.fromisoformat(s.replace('Z', ''))
    except Exception:
        # Repli : tout fichier touché dans la dernière heure compte comme "ce run"
        return datetime.datetime.utcnow() - datetime.timedelta(hours=1)


def _lines(path):
    try:
        if path.endswith('.json'):
            d = json.load(open(path, encoding='utf-8'))
            if isinstance(d, dict):
                return len(d.get('results', d))
            return len(d)
        with open(path, encoding='utf-8', errors='replace') as f:
            return sum(1 for l in f if l.strip())
    except Exception:
        return None


def _age_interne_h(path):
    """Âge en heures d'après l'horodatage ÉCRIT DANS le fichier, ou None."""
    try:
        d = json.load(open(path, encoding='utf-8'))
    except (ValueError, OSError):
        return None
    if not isinstance(d, dict):
        return None
    for champ in ('generated_at', 'updated', 'run_termine', 'ts'):
        v = d.get(champ)
        if not v:
            continue
        try:
            t = datetime.datetime.fromisoformat(str(v).replace('Z', ''))
            return (datetime.datetime.utcnow() - t).total_seconds() / 3600
        except ValueError:
            continue
    return None


def inspect(started):
    rows = []
    for art in ARTIFACTS:
        path, label, min_bytes = art[0], art[1], art[2]
        drapeaux = set(art[3:])
        externe = 'externe' in drapeaux
        r = {'fichier': path, 'libellé': label,
             'optionnel': 'optionnel' in drapeaux, 'externe': externe}
        if not os.path.exists(path):
            r.update(verdict='❌ ABSENT', octets=0, lignes=0, ecrit_ce_run=False)
            rows.append(r); continue
        size = os.path.getsize(path)
        mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(path))
        fresh = mtime >= started
        n = _lines(path)
        if size <= min_bytes or not n:
            verdict = '⚠️ VIDE'
        elif externe:
            # Produit ailleurs : « pas réécrit pendant CE run » est NORMAL.
            # CORRIGÉ LE 25/08/2026 : le mtime d'un fichier fraîchement
            # checkouté est l'heure du checkout — un test d'âge sur mtime est
            # donc TOUJOURS vrai en CI, et une panne du producteur (ex :
            # results_bridge cassé par un checkout sparse) resterait ✅ pour
            # toujours. On lit la fraîcheur DANS le fichier (generated_at /
            # updated), la seule horloge qui survit au checkout. Sans champ
            # lisible, on l'avoue : verdict dégradé, jamais un faux ✅.
            age_h = _age_interne_h(path)
            if age_h is None:
                verdict = '⏳ FIGÉ (fraîcheur inconnue)'
            else:
                verdict = '✅ OK' if age_h <= 24 else '⏳ FIGÉ'
        elif not fresh:
            verdict = '⏳ FIGÉ'
        else:
            verdict = '✅ OK'
        r.update(verdict=verdict, octets=size, lignes=n, ecrit_ce_run=fresh,
                 modifie=mtime.isoformat(timespec='seconds'))
        rows.append(r)
    return rows


def partitions_health():
    """Surveille la trajectoire de taille du repo : c'est ce qui a bloqué tous
    les push pendant 5 jours en août. Une partition >90 Mo est en zone rouge
    (mur dur GitHub : 100 Mo par fichier)."""
    out = {'total_mo': 0.0, 'zone_rouge': [], 'n_partitions': 0}
    # 25/08/2026 : les .gz n'étaient pas comptés — le total affiché (663 Mo
    # de .jsonl) masquait la vraie trajectoire du dépôt. On compte TOUT.
    for p in sorted(glob.glob('parts/*.jsonl') + glob.glob('parts/*.jsonl.gz')):
        mo = os.path.getsize(p) / 1e6
        out['total_mo'] += mo
        out['n_partitions'] += 1
        if mo >= 90:
            out['zone_rouge'].append({'fichier': p, 'mo': round(mo, 1)})
    out['total_mo'] = round(out['total_mo'], 1)
    return out


def main():
    started = _run_started()
    rows = inspect(started)
    parts = partitions_health()
    ko = [r for r in rows if r['verdict'] != '✅ OK']

    # AJOUTÉ LE 27/08/2026 (audit v3 §S) : le compte d'écarts Q3 (fraîcheur
    # des clôtures, capture_quality.py) rejoint le fichier committé et
    # lisible depuis GitHub, plutôt qu'un simple echo dans un log de run.
    q3 = None
    try:
        q3 = json.load(open('q3_status.json', encoding='utf-8'))
    except (OSError, ValueError):
        pass

    # AJOUTÉ LE 28/08/2026 (audit v6 §AE, même motif que Q3 ci-dessus) :
    # clv_vs_median_report.json rendu visible ici -- sinon le rapport de
    # décomposition prime/dérive (la réponse au §E) risque de rester non lu
    # exactement comme Q3 l'a été deux mois et demi.
    clv_median = None
    try:
        clv_median = json.load(open('clv_vs_median_report.json', encoding='utf-8'))
    except (OSError, ValueError):
        pass

    # AJOUTÉ LE 28/08/2026 (audit v7 §AJ) : polymarket_studies.yml commite
    # son rapport dès que `test -s` passe -- un rapport avec 5 échecs sur 5
    # le passait sans que rien ne le signale. Même motif Q3/CLV.
    pm_studies = None
    try:
        pm_studies = json.load(open('polymarket_studies_status.json', encoding='utf-8'))
    except (OSError, ValueError):
        pass
    # AJOUTÉ LE 28/08/2026 (audit v8 §AO) : ce statut est écrit par un AUTRE
    # workflow (polymarket_studies.yml, 04h20 UTC), pas celui-ci -- s'il
    # s'arrête de tourner, ce fichier reste sur disque tel quel et
    # afficherait indéfiniment le dernier statut connu comme s'il était
    # frais. Le concept existe déjà dans ce script pour les livrables
    # "externe" (fraîcheur inconnue = casse silencieuse en soi) ; appliqué
    # ici à la main faute de pouvoir facilement transformer pm_studies en
    # entrée de `rows`. Seuil 36h : le cycle normal est ~20h entre les deux
    # workflows, marge pour un jour manqué sans fausse alerte.
    if pm_studies and pm_studies.get('genere_le'):
        try:
            genere = datetime.datetime.fromisoformat(
                pm_studies['genere_le'].replace('Z', '+00:00'))
            age_h = (datetime.datetime.now(datetime.timezone.utc) - genere).total_seconds() / 3600
            pm_studies['age_heures'] = round(age_h, 1)
            pm_studies['fraicheur_inconnue_ou_perimee'] = age_h > 36
        except (ValueError, TypeError):
            pm_studies['fraicheur_inconnue_ou_perimee'] = True
    elif pm_studies:
        pm_studies['fraicheur_inconnue_ou_perimee'] = True   # pas de genere_le -> ancien format, méfiance

    payload = {
        'run_termine': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'run_demarre': started.isoformat(timespec='seconds'),
        'verdict_global': 'OK' if not ko else f'{len(ko)} livrable(s) à vérifier',
        'livrables': rows,
        'partitions': parts,
        'q3_qualite_cloture': q3,
        'clv_vs_median': clv_median,
        'polymarket_studies': pm_studies,
    }
    json.dump(payload, open(OUT_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    L = []
    L.append('# État du dernier run — Steam Pipeline\n')
    L.append(f"Run démarré `{payload['run_demarre']}` · terminé `{payload['run_termine']}` (UTC)\n")
    L.append(f"**Verdict : {payload['verdict_global']}**\n")
    L.append('| Livrable | Fichier | Lignes | Octets | État |')
    L.append('|---|---|---:|---:|---|')
    for r in rows:
        L.append(f"| {r['libellé']} | `{r['fichier']}` | {r.get('lignes') or 0} | "
                 f"{r.get('octets') or 0} | {r['verdict']} |")
    L.append('')
    L.append(f"**Partitions** : {parts['n_partitions']} fichiers, {parts['total_mo']} Mo au total.")
    if parts['zone_rouge']:
        L.append('')
        L.append('> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :')
        for z in parts['zone_rouge']:
            L.append(f"> - `{z['fichier']}` : {z['mo']} Mo")
    # AJOUTÉ LE 28/08/2026 (audit v8 §AP, le correctif au meilleur rapport
    # effort/valeur des huit passes selon l'audit lui-même) : q3, clv_median
    # et pm_studies étaient chargés dans `payload` (le JSON) mais JAMAIS
    # ajoutés à `L` (le Markdown) -- l'alerte remontait jusqu'au fichier
    # committé et s'arrêtait UNE case avant le fichier que Lucas regarde
    # réellement sur GitHub. Quatre correctifs différents (§S, §AE, §AJ)
    # avaient fait remonter une alerte d'un log vers un JSON ; aucun n'avait
    # fait le dernier pas jusqu'au .md. Défensif sur les clés (.get partout)
    # : un JSON d'un format antérieur ne doit jamais faire planter ce script.
    L.append('')
    if q3:
        etat = '⚠️' if q3.get('alerte') else '✅'
        pct = q3.get('pct_ecarts')
        L.append(f"{etat} **Qualité de clôture (Q3)** : "
                 f"{pct if pct is not None else '?'} % d'écarts > 3 % "
                 f"({q3.get('ecarts_gt_3pct', '?')}/{q3.get('n_total', '?')}), "
                 f"seuil {q3.get('seuil_pct', '?')} %")
    if clv_median and clv_median.get('verdict') == 'calcule':
        L.append(f"**CLV décomposé** : prime {clv_median.get('prime_selection_pct', 0):+.2f} % · "
                 f"dérive {clv_median.get('derive_marche_pct', 0):+.2f} % · "
                 f"part de la sélection {clv_median.get('part_prime_pct', '?')} % "
                 f"(n={clv_median.get('n_exploitables', '?')})")
    if pm_studies:
        if pm_studies.get('fraicheur_inconnue_ou_perimee'):
            L.append(f"⏳ **Études Polymarket** : statut périmé ou sans date "
                     f"(âge {pm_studies.get('age_heures', '?')}h) -- le "
                     f"producteur (polymarket_studies.yml) tourne-t-il encore ?")
        else:
            etat = '⚠️' if pm_studies.get('alerte') else '✅'
            # AJOUTÉ LE 28/08/2026 (audit v9 §AR) : n_avertissements affiché
            # à part, JAMAIS bloquant -- ce sont les "historique tronqué"
            # émis en fonctionnement normal dès que l'archivage a joué son
            # rôle (parts/ARCHIVE_INDEX.json non vide, désormais le cas en
            # permanence). Seul n_echecs (❌) compte pour l'état ✅/⚠️ et
            # pour --strict plus bas.
            n_av = pm_studies.get('n_avertissements')
            av_txt = f" · {n_av} avertissement(s) (info)" if n_av else ''
            L.append(f"{etat} **Études Polymarket** : {pm_studies.get('n_echecs', '?')} échec(s)"
                     f"{av_txt} (il y a {pm_studies.get('age_heures', '?')}h)")
    L.append('')
    L.append('Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit '
             '(le script n\'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.')
    open(OUT_MD, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    # AJOUTÉ LE 28/08/2026 (audit v9 §AS) : pipeline_status.json/.md ont
    # disparu du dépôt entre deux runs (transitoire, très probablement des
    # commandes de nettoyage locales, pas un bug du pipeline -- ils sont
    # déjà dans le git add de steam_pipeline.yml). Pas de mécanisme
    # inter-run construit ce soir (hors scope, priorité la plus basse de
    # la passe) -- juste une vérification immédiate que ce run a bien écrit
    # quelque chose de non vide, pour ne pas committer silencieusement un
    # fichier tronqué si l'écriture elle-même échouait à moitié.
    for _f in (OUT_JSON, OUT_MD):
        if not os.path.exists(_f) or os.path.getsize(_f) == 0:
            print(f"⚠️ {_f} : écriture de ce run absente ou vide -- à vérifier.")

    print(f"PIPELINE STATUS -> {OUT_JSON} + {OUT_MD}")
    for r in rows:
        print(f"  {r['verdict']:<10} {r['fichier']:<28} {r.get('lignes') or 0} lignes")
    print(f"  partitions : {parts['n_partitions']} fichiers, {parts['total_mo']} Mo")
    for z in parts['zone_rouge']:
        print(f"  ⛔ ZONE ROUGE : {z['fichier']} = {z['mo']} Mo (mur GitHub 100 Mo)")

    # MODE --strict (25/08/2026) — le verrou qui manquait.
    # 166 « || true » rendaient tous les jobs verts quoi qu'il arrive : le
    # pire mode de panne de ce projet (voir l'en-tête). Placé en DERNIÈRE
    # étape d'un workflow, APRÈS le commit/push (les données sont donc déjà
    # persistées), ce mode rend le run ROUGE si un livrable critique est
    # ABSENT ou VIDE. FIGÉ est toléré : un script peut légitimement n'avoir
    # rien produit de neuf pendant un run donné.
    if '--strict' in sys.argv:
        # La ligne de partage n'est PAS « ABSENT/VIDE vs FIGÉ », c'est
        # « interne vs externe » (audit du 25/08 après-midi) :
        #   interne + FIGÉ  = normal, le script n'a rien produit CE run ;
        #   externe + FIGÉ  = le PRODUCTEUR est mort — la fraîcheur interne
        #                     est le SEUL signal dont on dispose sur lui, et
        #                     c'était précisément celui que strict ignorait.
        # « FIGÉ (fraîcheur inconnue) » compte aussi : ne plus pouvoir lire
        # l'horodatage d'un externe est en soi une casse silencieuse.
        def _ko(r):
            if r.get('optionnel'):
                return False
            if r['verdict'].startswith(('❌', '⚠️')):
                return True
            return bool(r.get('externe')) and r['verdict'].startswith('⏳')
        ko_dur = [r for r in rows if _ko(r)]
        # AJOUTÉ LE 28/08/2026 (audit v8 §AP) : q3['alerte'] et
        # pm_studies['alerte'] existaient précisément pour signaler un
        # problème et n'étaient lus par AUCUN script ni workflow -- écrits
        # trois fois, lus zéro fois. --strict est le seul mécanisme du
        # dépôt qui rend un run rouge ; il ne regardait jusqu'ici que la
        # présence/fraîcheur des fichiers, jamais leur contenu.
        alertes_contenu = []
        if q3 and q3.get('alerte'):
            alertes_contenu.append(f"Q3 : {q3.get('pct_ecarts', '?')}% d'écarts "
                                   f"(seuil {q3.get('seuil_pct', '?')}%)")
        if pm_studies and pm_studies.get('fraicheur_inconnue_ou_perimee'):
            alertes_contenu.append("Polymarket : statut périmé ou sans date -- "
                                   "le producteur tourne-t-il encore ?")
        elif pm_studies and pm_studies.get('alerte'):
            alertes_contenu.append(f"Polymarket : {pm_studies.get('n_echecs', '?')} échec(s)")
        if ko_dur or alertes_contenu:
            print(f"\n🔒 STRICT : {len(ko_dur)} livrable(s) critique(s) en défaut, "
                 f"{len(alertes_contenu)} alerte(s) de contenu -> exit 1")
            for r in ko_dur:
                print(f"   {r['verdict']} {r['fichier']}")
            for a in alertes_contenu:
                print(f"   ⚠️ {a}")
            sys.exit(1)
        print("\n🔒 STRICT : tous les livrables critiques sont présents, non vides, et leurs producteurs externes sont vivants.")


if __name__ == '__main__':
    main()
