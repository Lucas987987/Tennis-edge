#!/usr/bin/env python3
"""Install V6.4 UI in an existing Tennis-edge repo; never touch existing gels.
Run from repository root AFTER unzip; changes only front-end/pages workflow.
"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
LAB=ROOT/'Tennis_Edge_Lab'
HTML=LAB/'research.html'
PAGES=ROOT/'.github/workflows/pages.yml'


def ensure_replace(text,needle,replacement,label):
    if replacement in text:
        return text
    if text.count(needle)!=1:
        raise RuntimeError(f'{label}: expected one target, found {text.count(needle)}')
    return text.replace(needle,replacement)


def install():
    for file in (HTML,PAGES,LAB/'economic_v64.py',LAB/'research_v64.js',LAB/'research_v64.css',
                 ROOT/'.github/workflows/lab_economic_v64.yml'):
        if not file.is_file():
            raise RuntimeError(f'Missing {file.relative_to(ROOT)}; unzip archive at repo root')
    h=HTML.read_text(encoding='utf8')
    h=ensure_replace(h,'<link rel="stylesheet" href="research_v632.css">',
                     '<link rel="stylesheet" href="research_v632.css">\n<link rel="stylesheet" href="research_v64.css">','V64 style')
    h=ensure_replace(h,'<button class="tab" data-tab="v61Audit">',
                     '<button class="tab" data-tab="v64Economic">Top ROI+ / CLV+ V6.4</button><button class="tab" data-tab="v61Audit">','V64 tab')
    section='''<section id="v64Economic" class="panel view hidden" aria-labelledby="v64Title">
  <h2 id="v64Title">Sélection économique V6.4 — ROI+ et CLV+</h2>
  <p class="description"><strong>Historique descriptif uniquement.</strong> Tous les marchés participent au classement, sans quotas. Les ROI/CLV ont servi à sélectionner les pistes et ne constituent donc pas une validation prospective. La sélection V6.3 reste inchangée.</p>
  <div id="v64Notice" class="notice">Chargement de la sélection V6.4…</div>
  <div id="v64Metrics" class="kpis"></div>
  <div class="v64-filters">
    <label>Classement<select id="v64Top"><option value="top10">Top 10 global</option><option value="top20">Top 20 global</option><option value="top50">Top 50 global</option><option value="top_roi">Top ROI historique</option><option value="top_clv">Top CLV historique</option><option value="top_robust">Top robustesse</option><option value="all">Sélection complète</option></select></label>
    <label>Marché<select id="v64Market"><option value="">Tous les marchés</option><option value="match">Vainqueur match</option><option value="set1">Set 1</option><option value="set2">Set 2</option></select></label>
  </div>
  <p id="v64Count" class="mini"></p>
  <div id="v64List"></div>
  <div class="buttons"><button type="button" id="v64Prev">← Précédentes</button><span id="v64Page"></span><button type="button" id="v64Next">Suivantes →</button></div>
  <p class="mini"><a href="./live/economic_v64.json" download>Exporter la sélection V6.4 (JSON)</a></p>
</section>
'''
    h=ensure_replace(h,'<section id="v61Audit"',section+'<section id="v61Audit"','V64 section')
    h=ensure_replace(h,'<script src="research_v63.js" defer></script>',
                     '<script src="research_v63.js" defer></script><script src="research_v64.js" defer></script>','V64 JavaScript')

    y=PAGES.read_text(encoding='utf8')
    y=ensure_replace(y,'            Tennis_Edge_Lab/research_v632.css',
                     '            Tennis_Edge_Lab/research_v632.css\n            Tennis_Edge_Lab/research_v64.css\n            Tennis_Edge_Lab/research_v64.js','V64 checkout UI')
    y=ensure_replace(y,'            Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json',
                     '            Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json\n            Tennis_Edge_Lab/live/economic_v64.json','V64 checkout JSON')
    y=ensure_replace(y,'research_v63.js freshness.js research.css research_v632.css v4.js v6.js',
                     'research_v63.js research_v64.js freshness.js research.css research_v632.css research_v64.css v4.js v6.js','V64 copy UI')
    y=ensure_replace(y,'          echo "--- contenu publié ---"',
                     '''          # Archive prospective V6.3 et sélection économique V6.4 sont indépendantes.
          if [ -s Tennis_Edge_Lab/live/economic_v64.json ]; then
            cp Tennis_Edge_Lab/live/economic_v64.json _site/Tennis_Edge_Lab/live/economic_v64.json
          fi
          echo "--- contenu publié ---"''','V64 copy JSON')
    if h.count('id="v64Economic"')!=1 or y.count('research_v64.js')<2:
        raise RuntimeError('Failed V6.4 installation sanity check')
    HTML.write_text(h,encoding='utf8')
    PAGES.write_text(y,encoding='utf8')
    print('V6.4 install OK: added independent tab + pages asset staging; V6.3 gels untouched')


if __name__=='__main__':
    try:
        install()
    except Exception as exc:
        print(f'V6.4 install failed: {exc}',file=sys.stderr)
        raise SystemExit(1)
