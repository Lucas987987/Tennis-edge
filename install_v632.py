#!/usr/bin/env python3
"""Install V6.3.2 in place; no registry, collector or freeze writes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS = []


def patch(relative: str, old: str, new: str):
    TASKS.append((relative, old, new))


# Mobile-readable cards, with the existing desktop table unchanged.
patch('Tennis_Edge_Lab/research.html',
      '<link rel="stylesheet" href="research.css">',
      '<link rel="stylesheet" href="research.css">\n<link rel="stylesheet" href="research_v632.css">')
patch('Tennis_Edge_Lab/research.html',
      '<div class="table-wrap"><table class="v61-audit-table"><thead><tr><th>Marché · bookmaker · horizon · côté</th>',
      '<div id="v63Cards" class="v63-card-grid" aria-label="Hypothèses V6.3 : cartes mobiles"></div><div class="table-wrap"><table class="v61-audit-table"><thead><tr><th>Marché · bookmaker · horizon · côté</th>')
patch('Tennis_Edge_Lab/research.html',
      'Le classement utilise la couverture, l’effectif, les jours, les variables disponibles, la simplicité et la diversité — jamais le ROI, les victoires, les p-values, les résultats futurs ou le CLV comme rentabilité.</p><div id="v63Notice"',
      'Le classement utilise la couverture, l’effectif, les jours, les variables disponibles, la simplicité et la diversité — jamais le ROI, les victoires, les p-values, les résultats futurs ou le CLV comme rentabilité. <strong>Le ROI et le CLV historiques sont affichés uniquement comme contexte descriptif ; les résultats prospectifs apparaissent séparément après les contrôles préenregistrés. Aucun résultat futur n’est remplacé par une valeur historique.</strong></p><div id="v63Notice"')

# Ensure the mobile stylesheet reaches GitHub Pages (sparse checkout + site copy).
patch('.github/workflows/pages.yml',
      '            Tennis_Edge_Lab/research_v63.js\n',
      '            Tennis_Edge_Lab/research_v63.js\n            Tennis_Edge_Lab/research_v632.css\n')
patch('.github/workflows/pages.yml',
      'research_v61.js research_v63.js freshness.js research.css v4.js v6.js;',
      'research_v61.js research_v63.js freshness.js research.css research_v632.css v4.js v6.js;')

# Do not relabel missing or outdated data as OK. Explain the three limits.
patch('Tennis_Edge_Lab/freshness.js',
      '<p class="description">Un rapport « ancien conservé » est la dernière version valide ; il n\'a pas été recalculé lors de cette publication.</p></details>`;',
      '<p class="description">Un rapport « ancien conservé » est la dernière version valide ; il n\'a pas été recalculé lors de cette publication.</p>\n'
      '      <p class="description"><strong>Limites connues :</strong> le suivi V6 historique (sans gel strict enregistré) peut être ancien ; le suivi exploratoire V6.1 et l’archive exhaustive V6.1 ne sont pas hébergés dans GitHub Pages. Leur absence est réelle et reste signalée, sans affecter les 60 gels V6.3. Les archives complètes sont à consulter dans les <a href="https://github.com/Lucas987987/Tennis-edge/actions/workflows/lab_autonomous.yml" target="_blank" rel="noopener noreferrer">artifacts des exécutions du Lab</a> tant qu’ils sont conservés (90 jours).</p></details>`;')
# Preflight ALL markers before writing any existing repo file: no partial installation.
planned = {}
for relative, old, new in TASKS:
    if relative not in planned:
        target = ROOT / relative
        planned[relative] = target.read_text(encoding='utf8')
    source = planned[relative]
    if new in source:
        continue  # rerun after an already completed installation
    elif old in source:
        planned[relative] = source.replace(old, new, 1)
    else:
        raise SystemExit(f'Installation annulée : marqueur incompatible dans {relative}. Aucun fichier modifié.')
for relative, updated in planned.items():
    target = ROOT / relative
    if target.read_text(encoding='utf8') != updated:
        target.write_text(updated, encoding='utf8')
        print('Updated:', relative)
    else:
        print('Already patched:', relative)
print('Installation V6.3.2 terminée. Exécuter les tests puis créer une PR.')
