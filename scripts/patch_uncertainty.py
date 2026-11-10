from pathlib import Path
p=Path('algo/index.html')
s=p.read_text(encoding='utf-8')
marker='te-incertitude-fiabilite-v1'
if marker in s:
 print('Déjà appliqué');raise SystemExit(0)
a='${rendType(m)}${rendFiabilite(m.fiabilite, true)}'
b='${rendType(m)}<div class="te-fiab-incertitude">${rendFiabilite(m.fiabilite, true)}${rendIncertitude(m)}</div>'
assert s.count(a)==1,('missing target',s.count(a))
s=s.replace(a,b,1)
anchor='function rendFiabilite(f, detail=false){'
assert s.count(anchor)==1
fn='''// te-incertitude-fiabilite-v1 : indicateur de sensibilité propre au match.
function rendIncertitude(m){
  if (!Array.isArray(m?.fourchette) || m.fourchette.length < 2) return '';
  const vals = m.fourchette.slice(0,2).map(Number);
  if (!vals.every(Number.isFinite)) return '';
  const [lo,hi] = vals.map(v=>v<=1 ? v*100 : v).sort((a,b)=>a-b);
  if (lo<0 || hi>100) return '';
  const amp = hi-lo;
  const label = L==='fr' ? 'Incertitude' : 'Uncertainty';
  const amplitude = L==='fr' ? 'points d’amplitude' : 'percentage-point range';
  const detail = L==='fr' ? 'Fourchette de sensibilité du modèle, pas un intervalle de confiance validé.' : 'Model sensitivity range, not a validated confidence interval.';
  return `<span class="te-uncertainty" title="${esc(detail)}"><span>${esc(label)}</span><b>${Math.round(lo)}–${Math.round(hi)} %</b><span class="te-uncertainty-amp">· ${Math.round(amp)} ${esc(amplitude)}</span><span class="te-uncertainty-scale" aria-hidden="true"><i style="left:${lo}%;width:${amp}%"></i></span></span>`;
}
'''
s=s.replace(anchor,fn+anchor,1)
css='''<style>/* te-incertitude-fiabilite-v1 */
.te-fiab-incertitude{display:flex;align-items:flex-start;gap:10px 22px;flex-wrap:wrap;margin:12px 0}
.te-fiab-incertitude>.fiab{margin:0}
.te-uncertainty{display:inline-flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:.93em;padding:3px 0;max-width:100%}
.te-uncertainty b{font-weight:800;color:var(--ink,inherit)}
.te-uncertainty-amp{opacity:.7;font-size:.86em}
.te-uncertainty-scale{display:block;position:relative;flex-basis:100%;height:5px;border-radius:8px;background:rgba(125,140,165,.2);overflow:hidden}
.te-uncertainty-scale i{position:absolute;top:0;bottom:0;background:#1699b7;border-radius:8px}
@media(max-width:600px){.te-fiab-incertitude{gap:8px 12px}.te-uncertainty-amp{display:none}}
</style>'''
assert '</head>' in s
s=s.replace('</head>',css+'\n</head>',1)
p.write_text(s,encoding='utf-8')
print('OK : indicateur ajouté à côté de la fiabilité')
