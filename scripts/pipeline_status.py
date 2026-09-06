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
import os, sys, json, glob, re, datetime, subprocess

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
    # AJOUTÉ LE 04/09/2026 : canal_public_log.jsonl n'était surveillé par
    # RIEN, alors que c'est la SEULE trace de ce que reçoivent réellement les
    # abonnés du canal Telegram -- et la source dont paper_journal_canal.py
    # tire le track record aligné sur la publication. Quand son producteur
    # (scripts/canal_public.py) a disparu du dépôt, le canal a cessé de
    # publier sans qu'aucun run ne devienne rouge : `|| true` avalait
    # l'erreur, ce fichier se figeait, et personne ne regardait sa date.
    # 'externe' : écrit par capture_closing (toutes les 5-10 min), pas par
    # le steam pipeline -- même traitement que resultats_derived.json.
    ('canal_public_log.jsonl',    'Journal du canal public',            100, 'externe'),
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


def _age_heures(iso):
    """Âge en heures d'un horodatage ISO, ou None s'il est absent/illisible.
    AJOUTÉ LE 04/09/2026 : le calcul était copié-collé trois fois dans main()
    et il en fallait une quatrième pour derniere_mesure_reussie_le."""
    if not iso:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def _age_interne_h(path):
    """Âge en heures d'après l'horodatage ÉCRIT DANS le fichier, ou None.

    CORRIGÉ LE 04/09/2026 AU SOIR : cette fonction ne savait lire qu'un objet
    JSON. Le premier livrable 'externe' au format JSONL ajouté à ARTIFACTS
    (canal_public_log.jsonl) tombait donc systématiquement en « FIGÉ
    (fraîcheur inconnue) » -- donc bloquant sous --strict EN PERMANENCE, y
    compris une fois son producteur restauré. Une surveillance qui ne peut
    jamais passer au vert n'est pas une surveillance stricte, c'est une
    alarme cassée : au bout de trois jours on cesse de la lire, et on
    retombe exactement sur le mode de panne que --strict combat.
    Pour un .jsonl on lit la DERNIÈRE ligne : c'est l'événement le plus
    récent, donc la vraie fraîcheur du flux.
    """
    d = None
    try:
        if path.endswith('.jsonl'):
            derniere = None
            with open(path, encoding='utf-8') as f:
                for ligne in f:
                    if ligne.strip():
                        derniere = ligne
            d = json.loads(derniere) if derniere else None
        else:
            d = json.load(open(path, encoding='utf-8'))
    except (ValueError, OSError):
        return None
    if not isinstance(d, dict):
        return None
    # 't' : convention des journaux de ce dépôt (canal_public_log.jsonl).
    for champ in ('generated_at', 'updated', 'run_termine', 'ts', 't'):
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


def scripts_manquants():
    """Tout `scripts/X.py` cité par un workflow existe-t-il vraiment ?

    AJOUTÉ LE 04/09/2026. `capture_closing.yml` appelait
    `scripts/canal_public.py`, absent du dépôt, derrière un `|| true` : le
    canal public a cessé de publier en silence, et avec lui le track record
    qui lui est aligné. Aucun mécanisme du dépôt ne pouvait le voir.

    Pourquoi ceci BLOQUE --strict alors que l'alerte Polymarket, elle, en a
    été retirée le même jour : ce n'est pas le résultat d'exécution d'un
    autre workflow, c'est un défaut STRUCTUREL du dépôt, vérifiable sans
    rien lancer et réparable par la personne qui lit le rapport.
    """
    refs = set()
    for f in sorted(glob.glob('.github/workflows/*.yml')):
        try:
            txt = open(f, encoding='utf-8').read()
        except OSError:
            continue
        # Appels directs : `python scripts/foo.py`
        refs |= set(re.findall(r'scripts/([A-Za-z_0-9]+\.py)', txt))
        # Appels INDIRECTS : polymarket_studies.yml lance ses études par
        #   for s in a b c d; do ... python scripts/${s}.py ... done
        # La regex ci-dessus ne voit que « scripts/${s}.py » et rate les
        # quatre noms réels : le contrôle aurait eu un angle mort exactement
        # là où le dépôt utilise une indirection. On résout la boucle.
        for var, noms in re.findall(r'for\s+([A-Za-z_]\w*)\s+in\s+([^;\n]+?)\s*;\s*do',
                                    txt):
            if ('scripts/${%s}.py' % var) not in txt and \
               ('scripts/$%s.py' % var) not in txt:
                continue
            for n in noms.split():
                # on écarte les globs et substitutions : seuls les noms
                # littéraux sont vérifiables
                if re.fullmatch(r'[A-Za-z_][\w-]*', n):
                    refs.add(n + '.py')
    return sorted(r for r in refs if not os.path.exists(os.path.join('scripts', r)))


def closing_health(jours=7):
    """Quelle proportion des matchs a un closing EXPLOITABLE ?

    AJOUTÉ LE 06/09/2026. C'est la métrique la plus structurante du projet, et
    elle n'était rapportée NULLE PART — ni ici, ni dans health_check, ni dans
    validation_report.

    Pourquoi elle compte plus que les autres : le CLV est le juge UNIQUE du
    dispositif, et `closing_reliable` en est le filtre d'entrée. La docstring
    de capture_closing.py le dit sans détour — « sinon le match est marqué
    closing_reliable=False et doit être EXCLU du CLV ». Un match sans closing
    fiable ne compte pour rien : ni validation, ni réfutation. Ce taux est
    donc le dénominateur de tout ce que le projet sait de lui-même.

    Mesuré le 05/09/2026 sur les 1 479 matchs de closing_lines.json :
        closing présent            85,3 %
        pinnacle_t7 (T-3 à T-7)    54,2 %
        pinnacle_t3 (T-0 à T-3)    43,5 %
    Et sur le dernier point capté avant le coup d'envoi, 31,2 % des matchs
    étaient au-delà de T-35, donc hors fenêtre fiable : près d'un tiers du
    volume perdu pour une raison purement mécanique — la cadence de capture.

    C'est précisément ce qui a motivé le passage de 5 à 3 minutes (découpe de
    capture_closing le 05/09). Sans ce compteur, l'effet de cette découpe
    n'était mesurable qu'en exportant le dépôt et en recalculant à la main.
    Une optimisation dont on ne peut pas lire le résultat n'est pas une
    optimisation, c'est un pari.

    FENÊTRE GLISSANTE de `jours` jours sur commence_time, et non le cumul
    historique : le cumul dilue tout changement de cadence dans des mois
    d'anciennes données. C'est la lecture récente qui doit réagir.

    Retourne un dict, ou None si closing_lines.json est illisible.
    """
    try:
        cl = json.load(open('closing_lines.json', encoding='utf-8'))
    except (OSError, ValueError):
        return None
    items = cl.values() if isinstance(cl, dict) else cl

    limite = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=jours))
    n = t3 = t7 = clos = 0
    for m in items:
        if not isinstance(m, dict):
            continue
        ct = m.get('commence_time')
        if not ct:
            continue
        try:
            t = datetime.datetime.fromisoformat(str(ct).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        # Matchs à venir exclus : leur closing n'existe pas encore, les
        # compter écraserait le taux et ferait clignoter l'alerte chaque
        # matin sans qu'il y ait quoi que ce soit à corriger.
        if t > datetime.datetime.now(datetime.timezone.utc) or t < limite:
            continue
        n += 1
        if m.get('closing'):
            clos += 1
        if m.get('pinnacle_t7'):
            t7 += 1
        if m.get('pinnacle_t3'):
            t3 += 1
    if not n:
        return None
    return {'jours': jours, 'n': n,
            'closing_pct': round(100.0 * clos / n, 1),
            't7_pct': round(100.0 * t7 / n, 1),
            't3_pct': round(100.0 * t3 / n, 1)}


CLOSING_CHUTE_PTS = 20.0     # points de pourcentage sous la référence 30 j
CLOSING_N_MIN = 50           # sous ce volume, la fenêtre 7 j est trop bruitée


def closing_degrade(recent, reference):
    """La capture s'est-elle dégradée récemment ?

    SEUIL RELATIF et non absolu : la référence dépend du calendrier (un
    Grand Chelem n'a pas le même profil horaire qu'une semaine de
    Challengers) et de la cadence de capture, qui vient de passer de 5 à
    3 min. Un seuil fixe serait à re-régler à chaque changement — donc
    jamais re-réglé, donc faux. On compare la fenêtre 7 j à la référence
    30 j : le dispositif se calibre sur lui-même.

    Vérifié sur les données du 04/09 : 34,9 % sur 7 j contre 80,8 % sur
    30 j, soit 45,9 points de chute. La fenêtre courte contenait la panne
    de quota du 30/08 au 03/09 — cinq jours sans capture, que RIEN n'avait
    signalé à l'époque. Ce contrôle l'aurait rendue impossible à manquer.

    Retourne (True, message) ou (False, None).
    """
    if not recent or not reference:
        return (False, None)
    if recent['n'] < CLOSING_N_MIN:
        return (False, None)          # trop peu de matchs : on ne conclut pas
    chute = reference['closing_pct'] - recent['closing_pct']
    if chute < CLOSING_CHUTE_PTS:
        return (False, None)
    return (True,
            f"Closings exploitables : {recent['closing_pct']:.0f} % sur 7 j "
            f"contre {reference['closing_pct']:.0f} % sur 30 j "
            f"({chute:.0f} pts de chute, n={recent['n']}) -- la capture ne "
            f"suit plus, le CLV perd sa matière première.")


def _checkout_partiel():
    """Ce run tourne-t-il sous sparse-checkout ? AJOUTÉ LE 04/09/2026.

    steam_pipeline.yml restreint désormais son checkout (pm_ticks/kx_ticks
    laissés au vestiaire). Sans ce drapeau, partitions_health() compterait
    ce qu'il voit -- une fraction -- et l'afficherait comme le total : le
    compteur qui surveille la trajectoire du dépôt deviendrait une source de
    FAUSSE RÉASSURANCE, exactement ce que la sentinelle de taille vient de
    subir. Une vue partielle doit se déclarer partielle."""
    try:
        r = subprocess.run(['git', 'config', '--get', 'core.sparseCheckout'],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip().lower() == 'true'
    except (OSError, subprocess.SubprocessError):
        return False


def partitions_health():
    """Surveille la trajectoire de taille du repo : c'est ce qui a bloqué tous
    les push pendant 5 jours en août. Une partition >90 Mo est en zone rouge
    (mur dur GitHub : 100 Mo par fichier)."""
    out = {'total_mo': 0.0, 'zone_rouge': [], 'n_partitions': 0,
           'vue_partielle': _checkout_partiel()}
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
    manquants = scripts_manquants()
    clos7, clos30 = closing_health(7), closing_health(30)
    clos_ko, clos_msg = closing_degrade(clos7, clos30)
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

    # AJOUTÉ LE 30/08/2026 (validation externe, point 1) : repo_sentinel.py
    # mesure la taille du dépôt tous les jours (health_check.yml, 7h37 UTC)
    # depuis le 29/08, mais son verdict -- y compris un dépassement de seuil
    # -- ne vivait que dans un log de run, derrière un `|| true`. "L'alerte
    # la plus urgente du projet" (l'historique git grossit de ~0,15 Go/jour
    # vers un mur GitHub à ~5 Go) était aussi la moins visible. Même motif
    # de fraîcheur que pm_studies : écrit par un AUTRE workflow, seuil 36h
    # (le cycle normal est ~16-17h entre les deux crons).
    repo_size = None
    try:
        repo_size = json.load(open('repo_size_status.json', encoding='utf-8'))
    except (OSError, ValueError):
        pass
    if repo_size and repo_size.get('genere_le'):
        try:
            genere = datetime.datetime.fromisoformat(
                repo_size['genere_le'].replace('Z', '+00:00'))
            age_h = (datetime.datetime.now(datetime.timezone.utc) - genere).total_seconds() / 3600
            repo_size['age_heures'] = round(age_h, 1)
            repo_size['fraicheur_inconnue_ou_perimee'] = age_h > 36
        except (ValueError, TypeError):
            repo_size['fraicheur_inconnue_ou_perimee'] = True
    elif repo_size:
        repo_size['fraicheur_inconnue_ou_perimee'] = True

    payload = {
        'scripts_manquants': manquants,
        'closing_7j': clos7,
        'closing_30j': clos30,
        'run_termine': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'run_demarre': started.isoformat(timespec='seconds'),
        'verdict_global': 'OK' if not ko else f'{len(ko)} livrable(s) à vérifier',
        'livrables': rows,
        'partitions': parts,
        'q3_qualite_cloture': q3,
        'clv_vs_median': clv_median,
        'polymarket_studies': pm_studies,
        'repo_size': repo_size,
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
    if clos7 and clos30:
        L.append('')
        L.append(f"**Closings exploitables** : {clos7['closing_pct']:.0f} % "
                 f"sur 7 jours (fenêtre t3 : {clos7['t3_pct']:.0f} %, "
                 f"n={clos7['n']}) — référence 30 jours "
                 f"{clos30['closing_pct']:.0f} % (t3 {clos30['t3_pct']:.0f} %). "
                 f"C'est le dénominateur du CLV : un match sans closing "
                 f"fiable ne valide ni ne réfute rien.")
    if manquants:
        L.append('')
        L.append('> ⛔ **Script(s) appelé(s) par un workflow et ABSENT(S) du dépôt** — '
                 'l\'appel échoue derrière un `|| true`, sans run rouge :')
        for m in manquants:
            L.append(f'> - `scripts/{m}`')
    if parts.get('vue_partielle'):
        L.append(f"**Partitions** : {parts['n_partitions']} fichiers, "
                 f"{parts['total_mo']} Mo — ⚠️ **vue partielle** "
                 f"(sparse-checkout : pm_ticks/kx_ticks absents de ce run). "
                 f"La taille réelle du dépôt est celle de la sentinelle "
                 f"ci-dessous, pas celle-ci.")
    else:
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
    # AJOUTÉ LE 30/08/2026 (validation externe, point 1) : "l'alerte la plus
    # urgente du projet" rendue visible ici plutôt que dans un log de run.
    if repo_size:
        if repo_size.get('fraicheur_inconnue_ou_perimee'):
            L.append(f"⏳ **Taille du dépôt** : statut périmé ou sans date "
                     f"(âge {repo_size.get('age_heures', '?')}h) -- le "
                     f"producteur (health_check.yml) tourne-t-il encore ?")
        elif repo_size.get('zone') == 'alarme':
            L.append(f"🔴 **Taille du dépôt** : {repo_size.get('taille_go', '?')} Go "
                     f"-- SEUIL FRANCHI (alarme {repo_size.get('seuil_alarme_go', '?')} Go, "
                     f"zone GitHub ~5 Go) -- {repo_size.get('message', '')}")
        elif repo_size.get('zone') == 'vigilance':
            L.append(f"🟠 **Taille du dépôt** : {repo_size.get('taille_go', '?')} Go "
                     f"-- zone de vigilance, marge {repo_size.get('marge_go', '?')} Go "
                     f"avant le seuil de {repo_size.get('seuil_alarme_go', '?')} Go")
        elif repo_size.get('zone') == 'indisponible':
            L.append(f"⚠️ **Taille du dépôt** : mesure indisponible ce run "
                     f"({repo_size.get('message', '')})")
        else:
            L.append(f"✅ **Taille du dépôt** : {repo_size.get('taille_go', '?')} Go "
                     f"(marge {repo_size.get('marge_go', '?')} Go)")
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
    for _m in manquants:
        print(f"  ⛔ SCRIPT MANQUANT : scripts/{_m} est appelé par un workflow "
              f"et n'existe pas dans le dépôt.")
    if clos7 and clos30:
        print(f"  closings   : {clos7['closing_pct']:.0f} % sur 7 j "
              f"(t3 {clos7['t3_pct']:.0f} %, n={clos7['n']}) · "
              f"référence 30 j {clos30['closing_pct']:.0f} % "
              f"(t3 {clos30['t3_pct']:.0f} %, n={clos30['n']})")
    _vp = ' (VUE PARTIELLE — sparse-checkout)' if parts.get('vue_partielle') else ''
    print(f"  partitions : {parts['n_partitions']} fichiers, {parts['total_mo']} Mo{_vp}")
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
        if clos_ko:
            alertes_contenu.append(clos_msg)
        for m in manquants:
            alertes_contenu.append(
                f"Script manquant : scripts/{m} est appelé par un workflow et "
                f"n'existe pas -- l'appel échoue derrière un `|| true`.")
        if q3 and q3.get('alerte'):
            alertes_contenu.append(f"Q3 : {q3.get('pct_ecarts', '?')}% d'écarts "
                                   f"(seuil {q3.get('seuil_pct', '?')}%)")
        # DÉCOUPLÉ LE 04/09/2026 (panne du run 91710599493). Le run avait ses
        # 10 livrables ✅ et son push réussi ; il est mort sur « Polymarket :
        # 1 échec(s) », importé d'un AUTRE workflow. Les quatre scripts de
        # cette boucle sont des ÉTUDES EXPLORATOIRES, pas des livrables de
        # production : steam_pipeline ne les produit pas, ne les contrôle pas
        # et ne peut pas les réparer. Leur verrou vit maintenant dans
        # polymarket_studies.yml, là où quelqu'un peut agir.
        # La fraîcheur, elle, RESTE bloquante : un producteur externe mort est
        # exactement ce que --strict a été écrit pour attraper (audit 25/08).
        # L'état ✅/⚠️ des études reste affiché dans le Markdown, non bloquant.
        if pm_studies and pm_studies.get('fraicheur_inconnue_ou_perimee'):
            alertes_contenu.append("Polymarket : statut périmé ou sans date -- "
                                   "le producteur tourne-t-il encore ?")
        # AJOUTÉ LE 30/08/2026 (validation externe, point 1) : la zone
        # ALARME (dépôt au-dessus du seuil, mur GitHub ~5 Go tout proche)
        # bloque --strict -- une taille de dépôt hors contrôle est une
        # urgence au moins aussi réelle que les autres alertes de contenu
        # ci-dessus. La zone VIGILANCE, elle, ne bloque PAS (même logique
        # que Q3/CLV : signaler tôt sans rendre le run rouge trop tôt).
        if repo_size and repo_size.get('fraicheur_inconnue_ou_perimee'):
            alertes_contenu.append("Taille du dépôt : statut périmé ou sans date -- "
                                   "le producteur (health_check.yml) tourne-t-il encore ?")
        elif repo_size and repo_size.get('zone') == 'alarme':
            alertes_contenu.append(f"Taille du dépôt : {repo_size.get('taille_go', '?')} Go, "
                                   f"seuil franchi ({repo_size.get('seuil_alarme_go', '?')} Go)")
        # AJOUTÉ LE 04/09/2026 (audit) : zone 'indisponible' = `gh api` a
        # échoué, taille_go vaut null, RIEN n'a été mesuré. Le fichier étant
        # tout de même réécrit chaque jour, fraicheur_inconnue_ou_perimee est
        # FAUX et zone != 'alarme' : la sentinelle était donc silencieusement
        # muette depuis le 03/09 12h13 (secrets.GH_TOKEN inexistant), avec
        # 3,48 Go mesurés le 29/08 pour une alarme à 4,0 Go et le mur GitHub
        # vers 5 Go. Une sentinelle qui ne peut pas mesurer est une sentinelle
        # EN PANNE, pas une sentinelle rassurante -- même raisonnement que
        # « externe + FIGÉ » plus haut.
        elif repo_size and repo_size.get('zone') == 'indisponible':
            # Une indisponibilité PASSAGÈRE de `gh` ne doit pas rendre le run
            # rouge (repo_sentinel a raison sur ce point : « je n'ai pas pu
            # mesurer » n'est pas « le dépôt est trop gros », et un rouge
            # quotidien cesse d'être un signal). Ce qui doit bloquer, c'est
            # une CÉCITÉ DURABLE : plus aucune mesure réussie depuis 72 h.
            # Le 04/09 : dernière valeur réelle le 29/08 (3,48 Go pour une
            # alarme à 4,0 et le mur GitHub vers 5), zone 'indisponible' en
            # continu depuis, et rien ne l'attrapait -- `genere_le` restait
            # frais parce que le fichier, lui, était bien réécrit chaque jour.
            #
            # CORRIGÉ LE 04/09/2026 AU SOIR : la première version traitait un
            # champ ABSENT comme « jamais mesuré » et bloquait. Or le champ
            # vient d'être introduit : tout repo_size_status.json écrit par
            # la version PRÉCÉDENTE de repo_sentinel.py en est dépourvu, sans
            # que cela dise quoi que ce soit sur la surveillance. Résultat
            # constaté sur le run de 18h43 : steam_pipeline rouge à cause du
            # correctif censé le rendre fiable, sur un fichier de 12h14
            # parfaitement normal pour son époque. Un contrôle qui déclenche
            # sur sa propre migration est un faux positif, exactement ce que
            # `|| true` produisait en négatif.
            # Règle : champ absent = ANCIEN FORMAT, on ne bloque que si le
            # fichier lui-même n'a pas été réécrit depuis 72 h -- auquel cas
            # le producteur n'a pas tourné avec le nouveau code en trois
            # jours, et c'est un vrai problème. Dès que repo_sentinel repasse,
            # le champ apparaît et la règle des 72 h s'applique normalement.
            _dm = repo_size.get('derniere_mesure_reussie_le')
            _age_dm = _age_heures(_dm) if _dm else None
            _ancien_format = _dm is None
            _age_fichier = _age_heures(repo_size.get('genere_le'))
            if _ancien_format:
                _aveugle = _age_fichier is None or _age_fichier > 72
                _depuis = ('date de génération illisible' if _age_fichier is None
                           else f'{_age_fichier:.0f} h (format antérieur au '
                                f'suivi des mesures réussies)')
            else:
                _aveugle = _age_dm > 72
                _depuis = f'{_age_dm:.0f} h'
            if _aveugle:
                alertes_contenu.append(
                    f"Taille du dépôt : AUCUNE mesure réussie depuis "
                    f"{_depuis} ({repo_size.get('message', 'cause inconnue')}) "
                    f"-- la sentinelle est aveugle, pas rassurante.")
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
