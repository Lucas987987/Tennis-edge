from pathlib import Path
p=Path('algo/index.html')
s=p.read_text(encoding='utf-8')
if 'te-analyse-detaillee-v1' in s:
 print('Analyse déjà installée');raise SystemExit(0)
old='<button type="button" class="btn" id="b-post">📝 Générer le post X · avant match</button>'
assert old in s
s=s.replace(old,old+'<button type="button" class="btn" id="b-analyse-detaillee" aria-expanded="false" aria-controls="te-analyse-detaillee">📊 Analyse détaillée</button>',1)
anchor='<div id="video-zone" hidden'
assert anchor in s
s=s.replace(anchor,'<section id="te-analyse-detaillee" class="te-analyse-detaillee" hidden aria-live="polite"></section>\n        '+anchor,1)
anchor="  const bPost = document.getElementById('b-post');"
assert anchor in s
s=s.replace(anchor,"  const bAnalyse = document.getElementById('b-analyse-detaillee');\n  if (bAnalyse) bAnalyse.onclick = () => ouvrirAnalyseDetaillee(m);\n"+anchor,1)
# Function declaration, safe to add before render method
anchor='function rendAvantMatch(m){'
assert anchor in s
js=r'''// te-analyse-detaillee-v1 — synthèse descriptive à partir des données du match, sans appel IA.
function ouvrirAnalyseDetaillee(m){
  const zone=document.getElementById('te-analyse-detaillee');
  const btn=document.getElementById('b-analyse-detaillee');
  if(!zone||!btn)return;
  if(!zone.hidden){zone.hidden=true;btn.setAttribute('aria-expanded','false');return;}
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const pct=x=>Math.round(100*x)+' %';
  const p=num(m.p_home), q=p===null?null:1-p;
  const f=m.fiabilite||{}, C=m.cartes, J=C&&Array.isArray(C.joueurs)?C.joueurs:[];
  const safe=x=>esc(String(x==null?'':x));
  const section=(titre,contenu)=>'<section class="te-analyse-part"><h4>'+safe(titre)+'</h4><p>'+contenu+'</p></section>';
  const h=m.home,a=m.away;
  let out='<h3>📊 Analyse détaillée · '+safe(h)+' / '+safe(a)+'</h3>';
  out+='<p class="te-analyse-disclaimer">Analyse descriptive générée à partir des données Tennis Edge. Les pourcentages sont des estimations, pas des certitudes. Les statistiques des cartes sont établies avant le match.</p>';
  if(p!==null){
    const fav=p>=.5?h:a, fp=Math.max(p,q);
    out+=section('Lecture du duel','Le modèle attribue <strong>'+pct(p)+'</strong> à '+safe(h)+' et <strong>'+pct(q)+'</strong> à '+safe(a)+'. '+(Math.abs(p-.5)<.06?'La confrontation est très équilibrée.':safe(fav)+' possède un avantage estimé de '+Math.round(Math.abs(p-q)*100)+' points de probabilité.')+' Même le favori peut perdre : '+safe(fav)+' est battu dans environ '+Math.round((1-fp)*100)+' simulations sur 100.');
  }
  if(Array.isArray(m.fourchette)&&m.fourchette.length>=2){
    const lo=num(m.fourchette[0]),hi=num(m.fourchette[1]);
    if(lo!==null&&hi!==null)out+=section('Incertitude du modèle','Selon les hypothèses de niveau des joueurs, la chance estimée de '+safe(h)+' varie entre <strong>'+pct(lo)+'</strong> et <strong>'+pct(hi)+'</strong>. Cette fourchette souligne la sensibilité de la prévision.');
  }
  if(f.note!=null){out+=section('Fiabilité de la prévision','Indice affiché : <strong>'+safe(f.note)+'/100</strong>'+(f.niveau?' ('+safe(f.niveau)+')':'')+'. Cet indice décrit la calibration historique de ce type de rencontre ; il ne garantit pas la victoire du favori.');}
  if(J.length===2){
    const keys=[['ser','service'],['ret','retour'],['ace','aces'],['pre','première balle'],['df','deuxième balle'],['for','forme']];
    let lines=[];
    for(const [k,label] of keys){
      const x=num(J[0]&&J[0].attributs&&J[0].attributs[k] ?? J[0]&&J[0][k]);
      const y=num(J[1]&&J[1].attributs&&J[1].attributs[k] ?? J[1]&&J[1][k]);
      if(x===null||y===null)continue;
      const delta=Math.abs(x-y);
      lines.push('<li><strong>'+safe(label)+'</strong> : '+safe(h)+' '+x+' / '+safe(a)+' '+y+(delta>=8?' — avantage '+safe(x>y?h:a):' — niveaux proches')+'</li>');
    }
    if(lines.length)out+='<section class="te-analyse-part"><h4>Forces et faiblesses comparées</h4><ul>'+lines.join('')+'</ul><p>Notes relatives au circuit, pas des probabilités de gagner chaque point.</p></section>';
  }
  const scores=Array.isArray(m.scores_probables)?m.scores_probables.slice(0,4):[];
  if(scores.length){
    const items=scores.filter(x=>Array.isArray(x)&&x.length>=2).map(x=>'<li>'+safe(x[0])+' : '+(num(x[1])!==null?pct(x[1]):'—')+'</li>');
    if(items.length)out+='<section class="te-analyse-part"><h4>Scénarios de score les plus fréquents</h4><ul>'+items.join('')+'</ul><p>Chaque score exact reste un scénario minoritaire ; les probabilités ne doivent pas être additionnées comme des issues indépendantes.</p></section>';
  }
  const live=typeof LIVE!=='undefined'&&LIVE.par_uid&&LIVE.par_uid[m.uid];
  if(live){
    const current=typeof pctLive==='function'?pctLive(m,live):null;
    out+=section('Situation en direct','Match actuellement signalé en direct.'+(current!==null?' La probabilité recalculée de '+safe(h)+' est de <strong>'+pct(current)+'</strong>, contre '+(p!==null?pct(p):'—')+' avant match.':' Le score et les probabilités actualisés figurent dans le panneau LIVE.')+' Les caractéristiques ci-dessus restent celles d’avant-match.');
  }
  out+=section('Conclusion','Cette analyse aide à comprendre les facteurs du modèle et les scénarios possibles. Elle ne prédit ni les trajectoires réelles ni le déroulement exact des points.');
  zone.innerHTML=out;
  zone.hidden=false;btn.setAttribute('aria-expanded','true');
  zone.scrollIntoView({behavior:'smooth',block:'nearest'});
}
'''
# Avoid JS mixing ?? and && without parentheses (syntax error); use simple helper
js=js.replace("J[0]&&J[0].attributs&&J[0].attributs[k] ?? J[0]&&J[0][k]", "(J[0]&&J[0].attributs&&J[0].attributs[k]) ?? (J[0]&&J[0][k])")
js=js.replace("J[1]&&J[1].attributs&&J[1].attributs[k] ?? J[1]&&J[1][k]", "(J[1]&&J[1].attributs&&J[1].attributs[k]) ?? (J[1]&&J[1][k])")
s=s.replace(anchor,js+'\n'+anchor,1)
css='''<style id="te-analyse-detaillee-style">.te-analyse-detaillee{margin:12px 0;padding:16px;border:1px solid var(--line2);border-radius:14px;background:var(--panel)}.te-analyse-detaillee[hidden]{display:none!important}.te-analyse-detaillee h3{margin:0 0 10px}.te-analyse-part{border-top:1px solid var(--line);padding-top:10px;margin-top:10px}.te-analyse-part h4{margin:0 0 5px}.te-analyse-part p{margin:0;line-height:1.55}.te-analyse-part ul{margin:5px 0;padding-left:22px}.te-analyse-part li{margin:5px 0}.te-analyse-disclaimer{font-size:.85rem;color:var(--dim);line-height:1.5}</style>\n'''
assert '</head>' in s
s=s.replace('</head>',css+'</head>',1)
p.write_text(s,encoding='utf-8')
print('Patched',p)
