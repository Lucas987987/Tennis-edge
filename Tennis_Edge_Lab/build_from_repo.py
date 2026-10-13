#!/usr/bin/env python3
"""Met à jour le snapshot Tennis Edge Lab depuis les fichiers du dépôt courant.
Usage: python Tennis_Edge_Lab/build_from_repo.py [racine_du_repo]
"""
from pathlib import Path
import json, zipfile, tempfile, subprocess, sys
here=Path(__file__).resolve().parent
repo=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else here.parent
sources=['closing_lines.json','resultats_oddspapi.json','resultats_derived.json',
'moves_detail_hist.csv','moves_detail.csv','paper_trades_canal.jsonl',
'canal_clv_detail.csv','paper_trades_match.jsonl','pipeline_status.json','book_index.json','paper_canal_report.json',
'h13_signal_log.jsonl','h15_signal_log.jsonl','h16_signal_log.jsonl','h16b_signal_log.jsonl','h17_signal_log.jsonl','h18_signal_log.jsonl']
found=[x for x in sources if (repo/x).is_file()]
missing=[x for x in sources if x not in found]
print('Lab rebuild:',len(found),'fichiers disponibles sur',len(sources))
if missing:print('Sources absentes :',', '.join(missing))
if not (repo/'moves_detail_hist.csv').exists():
    raise SystemExit('ERREUR: historique absent. Publication annulée pour ne pas afficher une base périmée comme récente.')
for required in ['resultats_oddspapi.json','h16_signal_log.jsonl','closing_lines.json']:
    if not (repo/required).exists():
        raise SystemExit('ERREUR: source critique absente : '+required)
with tempfile.TemporaryDirectory() as tmp:
    archive=Path(tmp)/'tennis-edge-input.zip'
    sys.path.insert(0,str(repo/'scripts'))
    from partitioned_store import load_closing
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as out:
        for name in found:
            if name=='closing_lines.json':
                merged=Path(tmp)/name
                merged.write_text(json.dumps(load_closing(root=repo),ensure_ascii=False),encoding='utf-8')
                out.write(merged,arcname='Tennis-edge-main/'+name)
            else:
                out.write(repo/name,arcname='Tennis-edge-main/'+name)
    subprocess.run([sys.executable,str(here/'build_data.py'),str(archive)],check=True)
print('Snapshot recalculé :',here/'data.js')
