#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repo_sentinel.py — l'alarme de taille du dépôt (créé le 26/08/2026).

La croissance de l'HISTORIQUE (2,6 Go le 25/08, +0,5 Go dans la journée) a
été découverte par accident, en regardant défiler un clone. Plus jamais : la
taille serveur est mesurée, tracée, et le run devient ROUGE au-delà du seuil
— avant que GitHub ne s'en mêle (zone d'intervention : ~5 Go).

BRANCHÉE LE 29/08/2026 (validation externe). Jusque-là ce script était
ORPHELIN : aucun workflow ne l'appelait, sa seule mention dans tout le dépôt
était une case à cocher manuelle dans RUNBOOK_FILTER_REPO.md. La docstring
affirmait pourtant qu'il tournait chaque semaine -- ce n'était pas vrai. Il
est désormais appelé par health_check.yml, tous les jours à 7h37 UTC.

POURQUOI QUOTIDIEN ET PAS HEBDO. Mesure réelle du 29/08 : 3,48 Go, soit
0,52 Go de marge sous le seuil. Au rythme observé (~0,1 à 0,2 Go/jour), un
cron dominical laisserait franchir le seuil un lundi et ne le signalerait
que six jours plus tard.

Usage : python scripts/repo_sentinel.py [--strict]
Env : REPO (défaut Lucas987987/Tennis-edge), SEUIL_GO (défaut 4.0),
      SEUIL_VIGILANCE_GO (défaut 3.0), GH_TOKEN (fourni par le workflow).
"""
import json
import os
import subprocess
import sys
import datetime
import oddspapi_v5 as ov   # AJOUTÉ 29/08/2026 (validation externe, point 1) : ov.ecriture_atomique()

REPO = os.environ.get('REPO', 'Lucas987987/Tennis-edge')
SEUIL_GO = float(os.environ.get('SEUIL_GO', '4.0'))
SEUIL_VIGILANCE_GO = float(os.environ.get('SEUIL_VIGILANCE_GO', '3.0'))


def _ecrire_statut(zone, taille_go=None, marge_go=None, message=''):
    """AJOUTÉ LE 29/08/2026 (validation externe, point 1) : jusqu'ici cette
    sentinelle n'écrivait RIEN -- son verdict, y compris un dépassement de
    seuil, ne vivait que dans le log du run (health_check.yml), derrière un
    `|| true`. C'était, mot pour mot, "l'alerte la plus urgente du projet"
    et la moins visible. Écrit dans repo_size_status.json, lu par
    pipeline_status.py (même motif que q3_status.json/
    polymarket_studies_status.json) -- rendu dans pipeline_status.md, visible
    sans ouvrir un seul log de run."""
    maintenant = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # AJOUTÉ LE 04/09/2026 (audit) : la date de la dernière mesure RÉUSSIE
    # survit aux runs indisponibles. Sans elle, `genere_le` est frais chaque
    # jour même quand rien n'a été mesuré : pipeline_status voyait un statut
    # récent, zone != 'alarme', et concluait que tout allait bien alors que
    # la sentinelle était muette depuis six jours (secrets.GH_TOKEN
    # inexistant, taille_go = null en continu). C'est ce champ, et non
    # `genere_le`, qui dit si la surveillance fonctionne encore.
    derniere_reussie = maintenant if taille_go is not None else None
    if derniere_reussie is None:
        try:
            _prec = json.load(open('repo_size_status.json', encoding='utf-8'))
            derniere_reussie = _prec.get('derniere_mesure_reussie_le')
        except (OSError, ValueError):
            derniere_reussie = None
    try:
        ov.ecriture_atomique('repo_size_status.json', {
            'zone': zone,   # 'ok' | 'vigilance' | 'alarme' | 'indisponible'
            'taille_go': round(taille_go, 2) if taille_go is not None else None,
            'marge_go': round(marge_go, 2) if marge_go is not None else None,
            'seuil_vigilance_go': SEUIL_VIGILANCE_GO,
            'seuil_alarme_go': SEUIL_GO,
            'message': message,
            'derniere_mesure_reussie_le': derniere_reussie,
            'genere_le': maintenant,
        }, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"  ℹ️ repo_size_status non écrit: {e}")


def main():
    strict = '--strict' in sys.argv
    r = subprocess.run(['gh', 'api', f'repos/{REPO}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # CORRIGÉ LE 29/08/2026 : « je n'ai pas pu mesurer » n'est PAS
        # « le dépôt est trop gros ». La version précédente sortait 1 sous
        # --strict dans les deux cas -- exactement le défaut corrigé en
        # v9-v10 sur le --strict de pipeline_status (avertissements
        # Polymarket normaux comptés comme échecs). Une panne passagère de
        # `gh` aurait rendu health_check rouge tous les jours, et le rouge
        # aurait cessé d'être un signal. L'indisponibilité est un
        # AVERTISSEMENT, pas un échec.
        msg = (f"gh api indisponible ({r.stderr.strip()[:120]}) — taille NON "
              f"vérifiée ce run.")
        print(f"⚠️ sentinelle : {msg} Ce n'est PAS un dépassement de seuil ; "
             f"mais si ce message revient plusieurs jours d'affilée, la "
             f"surveillance est AVEUGLE et il faut traiter la cause.")
        _ecrire_statut('indisponible', message=msg)
        return 0

    try:
        taille_go = json.loads(r.stdout).get('size', 0) / 1e6   # l'API renvoie des Ko
    except (ValueError, AttributeError) as e:
        msg = f"réponse gh illisible ({e}) — taille NON vérifiée."
        print(f"⚠️ sentinelle : {msg}")
        _ecrire_statut('indisponible', message=msg)
        return 0

    print(f"SENTINELLE DÉPÔT : {taille_go:.2f} Go côté serveur "
          f"(vigilance {SEUIL_VIGILANCE_GO:.1f} Go, alarme {SEUIL_GO:.1f} Go, "
          f"zone GitHub ~5 Go).")
    # NOTE : le champ `size` de l'API GitHub reflète l'état après le dernier
    # `gc` côté serveur. Il peut être en retard sur la réalité et tend donc à
    # SOUS-estimer. À lire comme un plancher, pas comme une mesure exacte.

    if taille_go >= SEUIL_GO:
        msg = "SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre."
        print(f"  🔴 {msg}")
        _ecrire_statut('alarme', taille_go=taille_go, marge_go=SEUIL_GO - taille_go, message=msg)
        return 1 if strict else 0

    marge = SEUIL_GO - taille_go
    if taille_go >= SEUIL_VIGILANCE_GO:
        # AJOUTÉ LE 29/08/2026 : avec 0,52 Go de marge mesurés, un simple
        # « ✅ marge restante » était trompeusement rassurant. La bande de
        # vigilance rend l'approche du seuil visible AVANT le franchissement,
        # sans rendre le run rouge (ce n'est pas encore une urgence).
        msg = f"ZONE DE VIGILANCE — marge restante : {marge:.2f} Go. Planifier la purge, ne pas attendre le rouge."
        print(f"  🟠 {msg}")
        _ecrire_statut('vigilance', taille_go=taille_go, marge_go=marge, message=msg)
        return 0

    print(f"  ✅ marge restante : {marge:.2f} Go.")
    _ecrire_statut('ok', taille_go=taille_go, marge_go=marge, message=f"marge restante : {marge:.2f} Go.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
