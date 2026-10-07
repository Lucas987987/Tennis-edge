#!/usr/bin/env python3
"""scan_coherence.py — vérifie les invariants que RIEN d'autre ne vérifie.

Pourquoi ce script existe
-------------------------
Tous les incidents de la semaine du 29/09 au 07/10 étaient détectables,
et aucun garde-fou ne les cherchait :

  * `restore_curves` absent de SEPT workflows qui lisent l'historique —
    trouvé à la main, après que book_index soit tombé de 1 863 à 1 251
    matchs sans qu'aucune erreur ne soit levée ;
  * `merge_json_state` supprimé de 20 workflows par un correctif de retry —
    détecté après DEUX JOURS d'échecs de fetch_clv ;
  * une précédence shell `A || B && C || D` qui faisait échouer le cas
    nominal — détectée après l'échec ;
  * un look-ahead sur `mag_cote_pct` signalé à chaque run pendant TROIS
    SEMAINES sans que personne ne lise le message.

Les outils existants surveillent la FRAÎCHEUR des fichiers. Aucun ne
surveille la COHÉRENCE du dispositif.

Ce que ce script NE fait pas
----------------------------
Il ne vérifie pas que les données sont bonnes — validation_report et
audit_qa s'en chargent. Il vérifie que le dispositif de mesure est
intact : les gels, les seuils, les dépendances entre workflows.

Priorité au premier bloc : si un seuil gelé change sans qu'on le voie,
VINGT hypothèses deviennent silencieusement invalides. C'est le genre de
chose qui arrive en modifiant un fichier pour autre chose.

Sortie : 0 si tout va bien, 1 si une anomalie CRITIQUE est trouvée.
Les avertissements n'échouent pas le run — ils seraient ignorés.
"""

import ast
import glob
import json
import os
import re
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(RACINE, '.github', 'workflows')
SCRIPTS = os.path.join(RACINE, 'scripts')
EMPREINTE = os.path.join(RACINE, 'coherence_empreinte.json')

critiques, alertes = [], []


def crit(m):
    critiques.append(m)
    print(f"  ❌ {m}")


def warn(m):
    alertes.append(m)
    print(f"  ⚠️ {m}")


def ok(m):
    print(f"  ✅ {m}")


# ── 1. LES GELS N'ONT PAS BOUGÉ ─────────────────────────────────────────
#
# Le bloc le plus important. Une date de gel ou un seuil qui change
# invalide l'hypothèse sans rien casser visiblement : les mesures
# continuent, elles ne veulent simplement plus rien dire.
#
# Méthode : on relit les constantes dans validation_report.py et on les
# compare à une EMPREINTE enregistrée. Première exécution : l'empreinte
# est créée et tout passe. Ensuite, toute divergence est critique.

def constantes_gel():
    """Extrait les dates de gel et les seuils par lecture de l'AST.

    Pas de regex sur le texte : une constante commentée ou dans une
    chaîne passerait. L'AST ne voit que les affectations réelles.
    """
    chemin = os.path.join(SCRIPTS, 'validation_report.py')
    try:
        arbre = ast.parse(open(chemin, encoding='utf-8').read())
    except (OSError, SyntaxError) as e:
        crit(f"validation_report.py illisible : {e}")
        return None

    out = {}
    motif = re.compile(r'^(FREEZE_DATE[A-Z0-9_]*|H\d+[A-Z]?_[A-Z_]+)$')
    for n in arbre.body:
        if not isinstance(n, ast.Assign):
            continue
        for c in n.targets:
            if not isinstance(c, ast.Name) or not motif.match(c.id):
                continue
            if isinstance(n.value, ast.Constant) and isinstance(
                    n.value.value, (str, int, float)):
                out[c.id] = n.value.value
    return out


def verifier_gels():
    print("\n1. LES GELS ET SEUILS N'ONT PAS BOUGÉ")
    actuel = constantes_gel()
    if actuel is None:
        return
    if not actuel:
        crit("aucune constante de gel trouvée — validation_report est-il intact ?")
        return

    try:
        ref = json.load(open(EMPREINTE, encoding='utf-8'))
    except (OSError, ValueError):
        json.dump(actuel, open(EMPREINTE, 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False, sort_keys=True)
        ok(f"empreinte créée : {len(actuel)} constantes enregistrées")
        print("     (les prochaines exécutions compareront à celle-ci)")
        return

    # Une constante AJOUTÉE est normale : c'est un nouveau gel.
    # Une constante MODIFIÉE ou SUPPRIMÉE ne l'est jamais.
    for k, v in ref.items():
        if k not in actuel:
            crit(f"constante gelée DISPARUE : {k} (valait {v!r})")
        elif actuel[k] != v:
            crit(f"constante gelée MODIFIÉE : {k} {v!r} -> {actuel[k]!r}")
    nouvelles = [k for k in actuel if k not in ref]
    if nouvelles:
        ok(f"{len(nouvelles)} nouvelle(s) constante(s) : {', '.join(sorted(nouvelles))}")
        json.dump(actuel, open(EMPREINTE, 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False, sort_keys=True)
    if not critiques:
        ok(f"{len(ref)} constantes inchangées depuis l'empreinte")


# ── 2. AUCUN FILTRE N'UTILISE UNE COLONNE RÉTROSPECTIVE ─────────────────
#
# Le défaut de H14, deux fois : `mag_cote_pct` contenait l'amplitude à la
# CLÔTURE, et H14 filtrait dessus. Trois semaines de mesures jetées.
#
# Règle : une colonne suffixée _POSTHOC ne doit JAMAIS apparaître dans
# une comparaison. Elle peut être lue, écrite, affichée — jamais filtrée.

COMPARAISONS = ('>', '<', '>=', '<=', '==', '!=')


def verifier_posthoc():
    print("\n2. AUCUN FILTRE SUR UNE COLONNE RÉTROSPECTIVE")
    trouve = False
    for p in sorted(glob.glob(os.path.join(SCRIPTS, '*.py'))):
        for i, l in enumerate(open(p, encoding='utf-8'), 1):
            if 'POSTHOC' not in l or l.lstrip().startswith('#'):
                continue
            # un filtre = la colonne est comparée à quelque chose
            if any(f' {c} ' in l for c in COMPARAISONS):
                crit(f"{os.path.basename(p)}:{i} — comparaison sur une "
                     f"colonne _POSTHOC : {l.strip()[:70]}")
                trouve = True
    if not trouve:
        ok("aucune colonne _POSTHOC utilisée comme critère")


# ── 3. LES SCRIPTS DE SIGNAL IMPORTENT BIEN LEURS BORNES ────────────────
#
# Les bornes vivent dans validation_report — source unique. Si un script
# de signal les redéfinit en dur, il mesurera autre chose que ce qui est
# gelé, et personne ne le verra.

def verifier_signaux():
    print("\n3. LES SCRIPTS DE SIGNAL LISENT LES BORNES GELÉES")
    attendu = {
        'h15_signal': ['H15_COTE_MIN', 'H15_COTE_MAX'],
        'h16_signal': ['H16_PIN_OPEN_MAX'],
        'h16b_signal': ['H16B_PIN_OPEN_MIN', 'H16_PIN_OPEN_MAX'],
        'h17_signal': ['H17_ECART_MIN', 'H17_ECART_MAX'],
        'h18_signal': ['H16_PIN_OPEN_MAX', 'H17_ECART_MIN'],
    }
    for nom, bornes in attendu.items():
        p = os.path.join(SCRIPTS, f'{nom}.py')
        if not os.path.exists(p):
            crit(f"{nom}.py ABSENT — l'hypothèse ne produit plus de signal")
            continue
        s = open(p, encoding='utf-8').read()
        manq = [b for b in bornes if b not in s]
        if manq:
            crit(f"{nom}.py n'importe pas : {', '.join(manq)}")
        elif 'validation_report' not in s:
            warn(f"{nom}.py utilise les noms mais n'importe pas "
                 f"validation_report — valeurs en dur ?")
        else:
            ok(f"{nom}.py : {len(bornes)} borne(s) depuis validation_report")


# ── 4. QUI LIT L'HISTORIQUE RESTAURE L'HISTORIQUE ───────────────────────
#
# Le défaut du 02/10 : sept workflows lisaient hist_* sans appeler
# restore_curves. Depuis que archive_curves sort les partitions de plus
# de 28 jours vers les releases, ils travaillaient sur un historique
# tronqué SANS lever d'erreur.

MARQUEURS_HIST = ('hist_partitions', 'iter_hist_lines', 'hist_book_',
                  'hist_set1_', 'hist_set2_')

# Ces scripts TOUCHENT les partitions sans avoir besoin qu'elles soient
# restaurées : ils les suppriment, les compressent ou les déduplisent.
# Exiger restore_curves avant eux ferait rapatrier 160 Mo pour rien — et
# pire, purge_data effacerait ce que restore_curves vient de ramener.
#
# Le critère n'est pas « touche hist_* » mais « a besoin de l'historique
# COMPLET pour produire un résultat juste ».
GESTIONNAIRES = {
    'purge_data',                   # supprime les partitions périmées
    'cleanup_duplicate_partitions', # déduplique
    'compress_hist_partitions',     # compresse en place
    'migrate_hist_partitions',      # renomme
    'archive_curves',               # sort vers les releases
    'restore_curves',               # rapatrie — ne peut pas s'appeler lui-même
    'scan_coherence',               # CE script : il NOMME les marqueurs
                                    # hist_* pour les chercher ailleurs, il
                                    # ne lit aucune partition. Sans cette
                                    # ligne il se signale lui-même.
}


def scripts_lisant_hist():
    """Scripts dont le RÉSULTAT dépend d'un historique complet."""
    out = set()
    for p in glob.glob(os.path.join(SCRIPTS, '*.py')):
        nom = os.path.basename(p)[:-3]
        if nom in GESTIONNAIRES:
            continue
        try:
            s = open(p, encoding='utf-8').read()
        except OSError:
            continue
        # curves_parts : seul rebuild() a besoin de l'historique ;
        # append() écrit la partition du jour et n'en a pas besoin.
        if nom == 'curves_parts':
            continue
        if any(m in s for m in MARQUEURS_HIST):
            out.add(nom)
    return out


def verifier_restore():
    print("\n4. QUI LIT L'HISTORIQUE APPELLE restore_curves")
    lecteurs = scripts_lisant_hist()
    manquants = []
    for p in sorted(glob.glob(os.path.join(WF, '*.yml'))):
        s = open(p, encoding='utf-8').read()
        lances = set(re.findall(r'scripts/([a-z_0-9]+)\.py', s))
        if not (lances & lecteurs):
            continue
        if 'restore_curves' not in s:
            manquants.append((os.path.basename(p),
                              sorted(lances & lecteurs)[:3]))
    if manquants:
        for n, sc in manquants:
            crit(f"{n} lit l'historique ({', '.join(sc)}) sans restore_curves")
    else:
        ok("tous les workflows qui lisent hist_* restaurent d'abord")


# ── 5. QUI COMMITE SAIT RÉSOUDRE UN CONFLIT JSON ────────────────────────
#
# Un conflit de CONTENU sur closing_lines.json se reproduit à chaque
# tentative : relancer ne sert à rien. merge_json_state.py fusionne clé
# par clé — closing_lines est un ACCUMULATEUR, prendre une version au
# hasard effacerait les matchs ajoutés par l'autre exécution.

def verifier_fusion():
    print("\n5. QUI COMMITE SAIT RÉSOUDRE UN CONFLIT JSON")
    sans = []
    for p in sorted(glob.glob(os.path.join(WF, '*.yml'))):
        s = open(p, encoding='utf-8').read()
        if 'git push' not in s:
            continue
        if 'merge_json_state' not in s:
            sans.append(os.path.basename(p))
    if sans:
        for n in sans:
            warn(f"{n} pousse sans merge_json_state — bloquera sur un conflit")
    else:
        ok("tous les workflows qui poussent savent fusionner")


# ── 6. LES BLOCS SHELL SONT SYNTAXIQUEMENT VALIDES ──────────────────────
#
# `bash -n` aurait attrapé la précédence du 06/10 ? Non — elle était
# syntaxiquement correcte. Mais il attrape les parenthèses non fermées,
# les `fi` manquants, les heredocs mal terminés : tout ce qui casse un
# workflow au premier run plutôt qu'au premier conflit.

def verifier_bash():
    print("\n6. LES BLOCS SHELL SONT VALIDES")
    try:
        import yaml
    except ImportError:
        warn("PyYAML absent — contrôle sauté")
        return
    n_blocs, n_err = 0, 0
    for p in sorted(glob.glob(os.path.join(WF, '*.yml'))):
        try:
            d = yaml.safe_load(open(p, encoding='utf-8'))
        except Exception as e:
            crit(f"{os.path.basename(p)} : YAML invalide — {str(e)[:60]}")
            continue
        for job in (d.get('jobs') or {}).values():
            for st in (job.get('steps') or []):
                r = st.get('run')
                if not r or len(r) < 40:
                    continue
                n_blocs += 1
                pr = subprocess.run(['bash', '-n'], input=r,
                                    capture_output=True, text=True)
                if pr.returncode:
                    n_err += 1
                    crit(f"{os.path.basename(p)} étape "
                         f"'{str(st.get('name'))[:30]}' : "
                         f"{pr.stderr.strip().splitlines()[-1][:60]}")
    if not n_err:
        ok(f"{n_blocs} bloc(s) shell valides")


# ── 7. CHAQUE SCRIPT APPELÉ EXISTE ──────────────────────────────────────

def verifier_existence():
    print("\n7. CHAQUE SCRIPT APPELÉ EXISTE")
    manq = set()
    for p in sorted(glob.glob(os.path.join(WF, '*.yml'))):
        s = open(p, encoding='utf-8').read()
        for nom in re.findall(r'scripts/([a-z_0-9]+)\.py', s):
            if not os.path.exists(os.path.join(SCRIPTS, f'{nom}.py')):
                manq.add((os.path.basename(p), nom))
    if manq:
        for w, n in sorted(manq):
            crit(f"{w} appelle scripts/{n}.py qui n'existe pas")
    else:
        ok("tous les scripts appelés sont présents")


def main():
    print("=" * 70)
    print("SCAN DE COHÉRENCE DU DISPOSITIF")
    print("=" * 70)
    verifier_gels()
    verifier_posthoc()
    verifier_signaux()
    verifier_restore()
    verifier_fusion()
    verifier_bash()
    verifier_existence()

    print("\n" + "=" * 70)
    if critiques:
        print(f"❌ {len(critiques)} ANOMALIE(S) CRITIQUE(S), "
              f"{len(alertes)} alerte(s)")
        print("=" * 70)
        return 1
    if alertes:
        print(f"⚠️ {len(alertes)} alerte(s), aucune anomalie critique")
    else:
        print("✅ dispositif cohérent")
    print("=" * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
