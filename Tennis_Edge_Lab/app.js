/* Tennis Edge Lab V2 - snapshot de secours + synchronisation Pages */
(()=>{'use strict';
let D=window.LAB_DATA||{rows:[],curves:{},meta:{}};
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const pct=(x,d=2)=>x===null||x===undefined?'—':new Intl.NumberFormat('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d,signDisplay:'exceptZero'}).format(x)+' %';
const nf=(x,d=0)=>x===null||x===undefined?'—':new Intl.NumberFormat('fr-FR',{maximumFractionDigits:d}).format(x);
const money=(x,d=2)=>x===null||x===undefined?'—':new Intl.NumberFormat('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d}).format(x);
const styleVal=x=>num(x)===null?'':x>0?'positive':x<0?'negative':'';
const sourceLabels={moves:'Mouvements historiques',moveslive:'Mouvements live',canal:'Canal public (papier)',match:'Paper match',clv:'Journal CLV seul',h13:'Hypothèse H13',h15:'Hypothèse H15',h16:'Hypothèse H16',h16b:'Hypothèse H16-B',h17:'Hypothèse H17',h18:'Hypothèse H18'};
const sections={dashboard:['Centre de recherche','Analyser le marché sous tous les angles.','Vue d’ensemble des populations enregistrées dans l’archive.'],explorer:['Explorateur universel','Croisez les dimensions et retrouvez chaque observation.','Choisissez le circuit, la cote, le timing, le bookmaker ou les périodes ; exportez votre sélection.'],hypotheses:['Laboratoire d’hypothèses','Six hypothèses, des signaux gelés et leurs chevauchements.','Performances à mise constante avec le nombre de résultats réellement associés.'],clv:['Étude CLV × ROI','Les prix de clôture expliquent-ils réellement le rendement ?','Analyse de la relation CLV et profit réalisé, avec effectifs et incertitude.'],books:['Analyse par bookmaker','Comparer les prix, le CLV et les rendements par opérateur.','Les comparaisons sont descriptives : les profils de matchs diffèrent selon les bookmakers.'],matches:['Fiches matchs','Retrouver l’historique de cote et tous les signaux d’un match.','Courbes échantillonnées de clôture lorsqu’elles existent dans l’archive.'],quality:['Qualité & provenance','Contrôler les sources avant de conclure.','Couverture des résultats, hypothèses provisoires, règles de calcul et problèmes de collecte.']};
const ids=['population','circuit','book','status','oddsMin','oddsMax','ampMin','lead','dateMin','dateMax','q','validation'];
let view='dashboard',sortKey='date',sortDir=-1,page=0,pageSize=35,selectedRow=null;
let cfg={population:'moves',circuit:'',book:'',status:'',oddsMin:'',oddsMax:'',ampMin:'',lead:'',dateMin:'',dateMax:'',q:'',validation:''};
const sources=['moves','moveslive','canal','match','h13','h15','h16','h16b','h17','h18','clv'];
let distribution=Object.fromEntries(sources.map(x=>[x,D.rows.filter(r=>r.source===x).length]));
const selectors={population:$('#population'),circuit:$('#circuit'),book:$('#book')};
selectors.population.innerHTML=sources.map(x=>`<option value="${x}">${esc(sourceLabels[x]||x)} (${nf(distribution[x])})</option>`).join('');
let circuitNames=[...new Set(D.rows.map(r=>r.circuit).filter(Boolean))].sort();
selectors.circuit.insertAdjacentHTML('beforeend',circuitNames.map(x=>`<option>${esc(x)}</option>`).join(''));
let allBooks=[...new Set(D.rows.map(r=>r.book).filter(Boolean))].sort();
selectors.book.insertAdjacentHTML('beforeend',allBooks.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join(''));
const clearFlash=()=>{};
function toast(s){let e=$('#toast');e.textContent=s;e.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>e.classList.remove('show'),2900)}
function setCfg(o){cfg={...cfg,...o};ids.forEach(k=>{let e=$('#'+k);if(e)e.value=cfg[k]??''});page=0;render()}
function sourceData(){let s=D.rows.filter(r=>r.source===cfg.population);
  if(cfg.circuit)s=s.filter(r=>r.circuit===cfg.circuit);
  if(cfg.book)s=s.filter(r=>r.book===cfg.book);
  if(cfg.status)s=s.filter(r=>cfg.status==='settled'?r.settled:!r.settled);
  let nmin=cfg.oddsMin!==''?+cfg.oddsMin:null,nmax=cfg.oddsMax!==''?+cfg.oddsMax:null,amin=cfg.ampMin!==''?+cfg.ampMin:null;
  if(nmin!==null)s=s.filter(r=>r.odds!==null&&r.odds>=nmin);
  if(nmax!==null)s=s.filter(r=>r.odds!==null&&r.odds<=nmax);
  if(amin!==null)s=s.filter(r=>r.amplitude!==null&&r.amplitude>=amin);
  if(cfg.lead){let [lo,hi]=cfg.lead.split('-').map(Number);s=s.filter(r=>r.lead!==null&&r.lead>=lo&&r.lead<hi)}
  if(cfg.dateMin)s=s.filter(r=>(r.date||'')>=cfg.dateMin);
  if(cfg.dateMax)s=s.filter(r=>(r.date||'')<=cfg.dateMax);
  if(cfg.q){const q=cfg.q.toLocaleLowerCase();s=s.filter(r=>(r.search||'').includes(q))}
  if(cfg.validation==='strict')s=s.filter(r=>!r.provisional);
  if(cfg.validation==='direct')s=s.filter(r=>!r.settled||r.result_source==='fixture_id'||!r.source.startsWith('h'));
  return s;
}
function roiStats(s){let ok=s.filter(r=>r.settled&&num(r.pnl)!==null),n=ok.length,profits=ok.map(r=>r.pnl);
 let mean=n?profits.reduce((a,b)=>a+b,0)/n:null;let variance=n>1?profits.reduce((a,b)=>a+(b-mean)**2,0)/(n-1):null;
 let se=n>1?Math.sqrt(variance/n):null;
 let clvs=s.map(r=>r.clv).filter(x=>num(x)!==null),cs=clvs.length?clvs.reduce((a,b)=>a+b,0)/clvs.length:null;
 let mid=clvs.length?[...clvs].sort((a,b)=>a-b)[Math.floor((clvs.length-1)/2)]:null;
 return {total:s.length,settled:n,open:s.length-n,roi:mean===null?null:mean*100,ci:n>1?[100*(mean-1.96*se),100*(mean+1.96*se)]:null,
  clv:cs,median:mid,clvCount:clvs.length,positive:clvs.length?100*clvs.filter(x=>x>0).length/clvs.length:null,
  wins:ok.filter(r=>r.won===true).length, profit:profits.reduce((a,b)=>a+b,0),provisional:ok.filter(r=>r.provisional).length};
}
const statBox=(label,value,foot,extra='')=>`<article class="card kpi"><div class="kpi-label">${label}<span>${extra}</span></div><div class="kpi-value ${typeof value==='object'?'':(String(value).startsWith('+')?'positive':String(value).startsWith('−')? 'negative':'')}">${typeof value==='object'?value.html:esc(value)}</div><div class="kpi-foot">${foot}</div></article>`;
function kpis(s){let x=roiStats(s);return `<section class="kpis">${statBox('OBSERVATIONS',nf(x.total),`${nf(x.settled)} avec résultat · ${nf(x.open)} sans résultat`,'▦')}${statBox('ROI À MISE CONSTANTE',{html:`<span class="${styleVal(x.roi)}">${pct(x.roi)}</span>`},x.ci?`IC95 % normal : ${pct(x.ci[0])} à ${pct(x.ci[1])}`:'Aucun ROI fiable calculable','↗')}${statBox('CLV MOYEN',{html:`<span class="${styleVal(x.clv)}">${pct(x.clv)}</span>`},`${nf(x.clvCount)} observations disposant d’un CLV`,'⌁')}${statBox('CLV POSITIF',{html:`<span class="${styleVal(x.positive===null?null:x.positive-50)}">${pct(x.positive,1)}</span>`},`${nf(x.clvCount)} lignes avec CLV · médiane ${pct(x.median)}`,'◇')}</section>`}
function groupBy(s,fn){let d=new Map();for(let r of s){const k=fn(r);if(!d.has(k))d.set(k,[]);d.get(k).push(r)}return [...d].map(([label,rows])=>({label,rows,stats:roiStats(rows)}))}
function week(d){if(!d||d.length<10)return 'Inconnu';const dd=new Date(d+'T00:00:00Z');if(!Number.isFinite(dd.getTime()))return 'Inconnu';const first=dd.getUTCDay()||7;dd.setUTCDate(dd.getUTCDate()-first+1);return dd.toISOString().slice(0,10)}
function barsChart(groups,measure='roi',accent='#0eaa86'){let good=groups.filter(g=>num(g.stats[measure])!==null);if(!good.length)return `<div class="empty">Données insuffisantes pour représenter cette mesure.</div>`;
  let vals=good.map(g=>g.stats[measure]),max=Math.max(1,Math.max(...vals.map(Math.abs)))*1.15;
  let w=690,h=Math.max(160,good.length*31+30),zero=260,region=400;
  let elements=good.map((g,i)=>{let val=g.stats[measure],width=Math.abs(val)/max*region/2,barx=val>=0?zero:zero-width,y=21+i*31;
  return `<text x="4" y="${y+12}" fill="currentColor" font-size="11">${esc(String(g.label).slice(0,26))}</text><rect x="${barx}" y="${y}" width="${Math.max(.5,width)}" height="18" rx="3" fill="${val>=0?accent:'#e35b70'}"/><text x="${val>=0?Math.min(645,barx+width+7):Math.max(210,barx-6)}" y="${y+12}" text-anchor="${val<0?'end':'start'}" fill="currentColor" font-size="11" font-weight="700">${pct(val,1)}</text><text x="${w-3}" y="${y+12}" text-anchor="end" fill="currentColor" opacity=".5" font-size="10">${g.stats.settled || g.stats.clvCount} n</text>`}).join('');
  return `<svg class="chart" role="img" aria-label="Graphique : ${esc(measure)} par groupe" viewBox="0 0 ${w} ${h}"><line x1="${zero}" x2="${zero}" y1="10" y2="${h-2}" stroke="#8093af" opacity=".5" stroke-dasharray="3 3"/>${elements}</svg>`;
}
function tableGroups(groups,limit=15){let valid=groups.sort((a,b)=>b.rows.length-a.rows.length).slice(0,limit);return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Segment</th><th class="num">Observations</th><th class="num">Réglés</th><th class="num">ROI</th><th class="num">CLV</th><th class="num">IC95 ROI</th></tr></thead><tbody>${valid.map(g=>`<tr><td class="name">${esc(g.label)}</td><td class="num">${nf(g.stats.total)}</td><td class="num">${nf(g.stats.settled)}</td><td class="num ${styleVal(g.stats.roi)}">${pct(g.stats.roi)}</td><td class="num ${styleVal(g.stats.clv)}">${pct(g.stats.clv)}</td><td class="num smallgray">${g.stats.ci?`${pct(g.stats.ci[0],1)} / ${pct(g.stats.ci[1],1)}`:'—'}</td></tr>`).join('')}</tbody></table></div>`}
function renderDashboard(s){let st=roiStats(s),weeks=groupBy(s,r=>week(r.date)).sort((a,b)=>a.label.localeCompare(b.label));return kpis(s)+`<div class="grid2"><section class="card panel"><div class="panel-head"><h3>ROI par semaine</h3><span class="chip">Échantillon sélectionné</span></div><p class="subhead">Variation des résultats par semaine de match, sans extrapolation.</p>${barsChart(weeks.slice(-14))}</section><section class="card panel"><div class="panel-head"><h3>Lecture statistique</h3><span class="chip ${st.settled<30?'warn':'good'}">${st.settled<30?'Petit échantillon':'Échantillon ≥ 30'}</span></div><p class="subhead">Le ROI est la moyenne des profits unitaires des seuls paris réglés, non le CLV. Chaque ligne est pondérée également.</p><div class="columns3"><div><div class="metric-sub">Victoires</div><h3>${nf(st.wins)} / ${nf(st.settled)}</h3></div><div><div class="metric-sub">Profit (unités)</div><h3 class="${styleVal(st.profit)}">${nf(st.profit,2)}</h3></div><div><div class="metric-sub">Règlements provisoires</div><h3>${nf(st.provisional)}</h3></div></div><div class="callout"><strong>Attention :</strong> une borne inférieure IC95 positive n'est pas une validation hors échantillon. Les regroupements peuvent contenir plusieurs tickets du même match. La méthode d'IC affichée est une approximation normale.</div></section></div>
<div class="grid2 equal"><section class="card panel"><div class="panel-head"><h3>Par circuit</h3></div>${tableGroups(groupBy(s,r=>r.circuit),8)}</section><section class="card panel"><div class="panel-head"><h3>Par bookmaker</h3></div>${tableGroups(groupBy(s,r=>r.book||'Inconnu'),10)}</section></div>`}
function sortedRows(s){return [...s].sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(x===null||x===undefined)x='';if(y===null||y===undefined)y='';if(typeof x==='number'&&typeof y==='number')return (x-y)*sortDir;return String(x).localeCompare(String(y))*sortDir})}
function tableRows(s,showPaging=true){let sorted=sortedRows(s);let maxPage=Math.max(0,Math.ceil(sorted.length/pageSize)-1);page=Math.min(maxPage,page);let subset=showPaging?sorted.slice(page*pageSize,(page+1)*pageSize):sorted.slice(0,12);
const th=(col,label)=>`<th data-sort="${col}" title="Trier par ${label}" ${col==='pnl'?'class="num"':''}>${label} ${col===sortKey?(sortDir>0?'↑':'↓'):''}</th>`;
return `<div class="table-wrap"><table class="data-table"><thead><tr>${th('date','Date')}${th('player','Joueur')}${th('opponent','Adversaire')}${th('book','Book')}${th('odds','Cote')}${th('amplitude','Amplitude')}${th('lead','Avant (min)')}${th('clv','CLV %')}${th('pnl','Profit')}</tr></thead><tbody>${subset.map(r=>`<tr data-row="${r.id}"><td>${esc(r.date)}</td><td class="name">${esc(r.player||'—')}<div class="smallgray">${esc(r.tournament||r.group)}</div></td><td>${esc(r.opponent||'—')}</td><td><span class="chip">${esc(r.book||'—')}</span></td><td class="num">${money(r.odds)}</td><td class="num">${nf(r.amplitude,2)}</td><td class="num">${nf(r.lead)}</td><td class="num ${styleVal(r.clv)}">${pct(r.clv)}</td><td class="num ${styleVal(r.pnl)}">${r.pnl===null?'<span class="smallgray">Non réglé</span>':nf(r.pnl,2)+' u'}</td></tr>`).join('')}</tbody></table></div>${subset.length===0?'<div class="empty">Aucun match ne correspond aux filtres.</div>':''}${showPaging?`<div class="pagination"><span>${nf(s.length)} lignes · page ${page+1}/${maxPage+1}</span><button class="small-btn" data-page="-1" ${page===0?'disabled':''}>←</button><button class="small-btn" data-page="1" ${page>=maxPage?'disabled':''}>→</button></div>`:''}`;
}
function renderExplorer(s){return kpis(s)+`<section class="card panel"><div class="panel-head"><h3>Observations brutes et résultats</h3><span class="chip">Cliquez sur une ligne pour sa fiche</span></div><p class="subhead">Les variables d'amplitude sont pré-détection ; aucune amplitude posthoc n'entre dans les filtres. Les lignes sans résultat restent visibles.</p>${tableRows(s)}</section>`}
function signalsOverlap(a,b){let aSet=new Set(a.filter(r=>r.sent).map(r=>r.uid));return new Set(b.filter(r=>r.sent).map(r=>r.uid)).size?[...new Set(b.filter(r=>r.sent).map(r=>r.uid))].filter(u=>aSet.has(u)).length:0}
function hypFiltered(tag){let prev=cfg.population;cfg.population=tag;const out=sourceData();cfg.population=prev;return out}
function renderHyp(s){let hs=['h13','h15','h16','h16b','h17','h18'];let source=s[0]?.source;
 const cards=hs.map(h=>{let raw=hypFiltered(h),sent=raw.filter(r=>r.sent),ss=roiStats(sent),unmatched=sent.length-ss.settled;
 return `<article class="card hyp"><div class="hyp-header"><h3>${esc(h.toUpperCase().replace('B','-B'))}</h3><span class="chip ${ss.settled<30?'warn':'good'}">${ss.settled<30?'Échantillon réduit':'À contrôler'}</span></div><strong class="big ${styleVal(ss.roi)}">${pct(ss.roi)}</strong><span class="metric-sub">ROI indicatif des résultats retrouvés</span><div class="hyp-stats"><div><label>Signaux envoyés</label><b>${nf(sent.length)}</b></div><div><label>Résultats associés</label><b>${nf(ss.settled)}</b></div><div><label>Non réglés</label><b>${nf(unmatched)}</b></div><div><label>Profit unités</label><b>${nf(ss.profit,2)}</b></div></div><button class="small-btn" data-hyp="${h}">Explorer ${h.toUpperCase().replace('B','-B')} →</button></article>`}).join('');
 const overlap=hs.filter(h=>h!=='h15');let ov=`<div class="table-wrap"><table class="data-table"><thead><tr><th></th>${overlap.map(h=>`<th>${h.toUpperCase()}</th>`).join('')}</tr></thead><tbody>${overlap.map(a=>`<tr><td class="name">${a.toUpperCase()}</td>${overlap.map(b=>`<td>${nf(signalsOverlap(hypFiltered(a),hypFiltered(b)))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
 return `<div class="callout" style="margin:0 0 18px"><strong>Validation :</strong> les filtres sélectionnés s'appliquent à chaque hypothèse. Les résultats de ce tableau utilisent un rapprochement par identifiant de match ou par noms / date. Certains règlements sont provisoires. Les hypothèses sont corrélées : par exemple H18 recoupe H16 et H17. Ne pas additionner leurs nombres de paris.</div><div class="hyp-grid">${cards}</div><div class="grid2 equal" style="margin-top:18px"><section class="card panel"><h3>Chevauchement entre hypothèses envoyées</h3><p class="subhead">Nombre de matchs UID présents dans les deux ensembles.</p>${ov}</section><section class="card panel"><h3>Construire une hypothèse personnalisée</h3><p class="subhead">Composez vos critères dans la barre de filtres (cote, temps, circuit, amplitude, opérateur), puis enregistrez la vue. Elle sera conservée uniquement dans ce navigateur.</p><div class="callout">Les critères sont figés localement comme une sélection. Une vraie validation prospective nécessite d'enregistrer une date de gel et d'évaluer uniquement les nouvelles observations. Aucun classement automatique des combinaisons n'est encore activé, afin d'éviter le surapprentissage.</div><button class="wide-btn" id="jumpExplorer">Ouvrir l’explorateur →</button></section></div>`;
}
function buckets(s){let b=[['CLV < 0',x=>x<0],['0 à 5 %',x=>x>=0&&x<5],['5 à 10 %',x=>x>=5&&x<10],['10 à 15 %',x=>x>=10&&x<15],['15 à 25 %',x=>x>=15&&x<25],['≥ 25 %',x=>x>=25]];
 return b.map(([label,test])=>{let rows=s.filter(r=>num(r.clv)!==null&&test(r.clv));return {label,rows,stats:roiStats(rows)}})}
function renderCLV(s){let b=buckets(s);return kpis(s)+`<div class="grid2"><section class="card panel"><h3>ROI par tranche de CLV</h3><p class="subhead">Seuls les tickets réglés contribuent au rendement ; le CLV peut être disponible pour davantage de lignes. Aucun filtrage de pari à partir du CLV futur n'est valide en temps réel.</p>${barsChart(b)}</section><section class="card panel"><h3>Comparaison des tranches</h3>${tableGroups([...b],8)}<div class="callout">Chaque tranche doit être jugée sur son effectif, son intervalle de confiance et un test prospectif. La sélection des tranches après avoir vu les résultats peut produire une illusion d'avantage.</div></section></div><section class="card panel"><h3>À retenir</h3><p class="notice">Le CLV indique si la cote prise était meilleure que la cote de clôture retenue, pas si le pari a gagné. Dans le journal de mouvements, les CLV et ROI sont calculés sur une observation par ligne ; les lignes multiples d'un même match ne sont pas forcément indépendantes. Pour étudier une relation causale, il faut séparer prédicteurs antérieurs au pari et mesures postérieures.</p></section>`}
function renderBooks(s){let grp=groupBy(s,r=>r.book||'Non renseigné').filter(g=>g.rows.length>=2).sort((a,b)=>b.rows.length-a.rows.length);return kpis(s)+`<div class="grid2"><section class="card panel"><h3>ROI par bookmaker</h3><p class="subhead">Comparaison descriptive, tous types de matchs de la population retenue.</p>${barsChart(grp.slice(0,14))}</section><section class="card panel"><h3>Couverture des observations</h3><p class="subhead">Les groupes de faible effectif sont particulièrement sensibles à quelques résultats extrêmes.</p><div class="bars">${grp.slice(0,14).map(g=>`<div class="bar-row"><div>${esc(g.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${Math.round(g.rows.length/Math.max(...grp.map(g=>g.rows.length))*100)}%"></div></div><div class="bar-value">${nf(g.rows.length)}</div></div>`).join('')}</div></section></div><section class="card panel"><h3>Tableau complet des bookmakers</h3>${tableGroups(grp,60)}</section>`}
function renderMatches(s){let matches=groupBy(s,r=>r.uid||r.player+'|'+r.date).sort((a,b)=>b.rows.length-a.rows.length);const display=matches.slice(0,60);return `<section class="card panel"><div class="panel-head"><h3>Matchs distincts : ${nf(matches.length)}</h3><span class="chip">Jusqu'à 60 affichés</span></div><p class="subhead">Filtrez un joueur ou un tournoi pour isoler un match. Cliquez pour voir le détail, le résultat et, si disponible, la courbe Pinnacle.</p><div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Joueurs</th><th>Circuit</th><th>Observations</th><th>Résultats</th></tr></thead><tbody>${display.map(g=>{let r=g.rows[0];return `<tr data-row="${r.id}"><td>${esc(r.date)}</td><td class="name">${esc(r.player||'—')} ${r.opponent?' vs '+esc(r.opponent):''}</td><td>${esc(r.tournament||r.circuit)}</td><td>${nf(g.rows.length)}</td><td>${nf(g.stats.settled)}</td></tr>`}).join('')}</tbody></table></div>${display.length===0?'<div class="empty">Aucun match trouvé.</div>':''}</section>`}
function quality(){const P=D.pipeline||{},m=D.meta||{};let cs=P.closing_30j||{},rc=P.repo_size||{};let counts=Object.entries(distribution).filter(([,v])=>v>0);return `<div class="kpis">${statBox('FICHIERS DANS L’ARCHIVE',nf(m.source_file_count),'Inventaire du ZIP','□')}${statBox('LIGNES EXPOSÉES',nf(m.rows),'Populations normalisées','▦')}${statBox('COURBES DISPONIBLES',nf(Object.keys(D.curves||{}).length),'Snapshots de la cote Pinnacle','⌁')}${statBox('CLV CANAL APPARIÉS',nf(m.canal_clv_joins),'Rapprochement UID + bookmaker + cote','◇')}</div><div class="grid2 equal"><section class="card panel"><h3>État du pipeline au 12/10/2026</h3><div class="quality-item"><div><strong>Couverture des clôtures à 30 jours</strong><div class="detail">${nf(cs.n)} rencontres suivies</div></div><strong>${nf(cs.closing_pct,1)} %</strong></div><div class="quality-item"><div><strong>Taille du dépôt source</strong><div class="detail">Seuil d'alerte interne à ${nf(rc.seuil_alarme_go,1)} Go</div></div><strong class="negative">${nf(rc.taille_go,2)} Go</strong></div><div class="quality-item"><div><strong>Dernier pipeline</strong><div class="detail">${esc(P.run_termine||'non disponible')}</div></div><span class="chip warn">${esc(P.verdict_global||'À contrôler')}</span></div><div class="quality-item"><div><strong>Set 2</strong><div class="detail">Aucun ticket dans le journal de l'archive</div></div><span class="chip warn">Vide</span></div></section><section class="card panel"><h3>Mesures et formules</h3><p class="notice"><strong>Profit</strong> = cote décimale − 1 en cas de victoire, sinon −1.<br><strong>ROI</strong> = somme des profits divisée par le nombre de paris réglés × 100.<br><strong>CLV</strong> = valeur déjà calculée par Tennis Edge dans chaque source ; ne pas fusionner CLV bookmaker et CLV Pinnacle.<br><strong>IC95 approximatif</strong> = ROI moyen ± 1,96 × écart-type des profits / √n. Les dépendances entre matchs ou tickets ne sont pas corrigées.<br><strong>Unités</strong> = 1 ligne par mouvement, pari simulé ou signal selon la population. Les échantillons ne sont pas interchangeables.</p><div class="callout"><strong>Sources :</strong> ${esc(m.archive)} · Snapshot ${esc(m.snapshot)} · Aucune actualisation réseau. L’application n’envoie aucune requête aux APIs privées.</div></section></div><section class="card panel"><h3>Sources disponibles dans cette première version</h3><p class="subhead">Les journaux lourds des ticks Polymarket, Kalshi et chaque bookmaker ne sont pas encore interrogés dynamiquement : cette version utilise les extractions explicites ci-dessous.</p>${tableGroups(counts.map(([source,n])=>({label:sourceLabels[source]||source,rows:D.rows.filter(r=>r.source===source),stats:roiStats(D.rows.filter(r=>r.source===source))})),30)}<div class="callout"><strong>Prudence :</strong> les résultats d'hypothèses appariés par noms et date doivent être validés avant tout usage opérationnel. Il faut ensuite gérer les clôtures manquantes, les doublons et les résultats contradictoires, et mesurer des performances hors échantillon.</div></section>`}
function pairsig(a,b){const norm=x=>String(x||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');return [norm(a),norm(b)].sort().join('|')}
const curvesByPair={};for(const x of Object.values(D.curves||{})){let p=pairsig(x.home,x.away);(curvesByPair[p]??=[]).push(x)}
function curveFor(r){let l=(curvesByPair[pairsig(r.player,r.opponent)]||[]).filter(c=>c.date&&r.date&&Math.abs(Date.parse(c.date)-Date.parse(r.date))/86400000<=2);
 if(l.length===1)return l[0];if(l.length>1){l.sort((a,b)=>Math.abs(Date.parse(a.date)-Date.parse(r.date))-Math.abs(Date.parse(b.date)-Date.parse(r.date)));if(l[0].date!==l[1].date)return l[0]}return null}
function lineChart(curve){let rows=curve.points||[],both=rows.filter(p=>num(p[1])!==null&&num(p[2])!==null);if(both.length<2)return '<div class="empty">Courbe insuffisante.</div>';
 const all=both.flatMap(p=>[p[1],p[2]]),min=Math.max(1,Math.min(...all)*.96),max=Math.max(...all)*1.04,scale=x=>240-(x-min)/(max-min)*195,pad=36,w=750;
 const pt=k=>both.map((r,i)=>`${pad+i*(w-pad*2)/Math.max(1,both.length-1)},${scale(r[k])}`).join(' ');
 return `<svg class="chart" viewBox="0 0 750 260" role="img" aria-label="Évolution des cotes Pinnacle"><g fill="none" stroke="#8598b2" opacity=".2">${[0,1,2,3,4].map(i=>`<line x1="36" x2="714" y1="${45+i*47}" y2="${45+i*47}"/>`).join('')}</g><polyline points="${pt(1)}" stroke="#13ae88" fill="none" stroke-width="2.5"/><polyline points="${pt(2)}" stroke="#f3a53b" fill="none" stroke-width="2.5"/><text x="36" y="18" fill="currentColor" font-size="12">${esc(curve.home)} (vert) / ${esc(curve.away)} (orange)</text><text x="36" y="255" fill="currentColor" font-size="10">Premier point</text><text x="714" y="255" text-anchor="end" fill="currentColor" font-size="10">Dernier point</text></svg><div class="spark-legend">${nf(both.length)} points échantillonnés · Cotes Pinnacle brutes · Dates des points disponibles dans l'archive. Le tracé utilise l'ordre des observations, et non des intervalles temporels réguliers.</div>`}
function showDetail(id){let r=D.rows.find(x=>x.id===+id);if(!r)return;let c=curveFor(r);
const shared=D.rows.filter(x=>x.uid===r.uid).slice(0,20);
$('#detailContent').innerHTML=`<div class="modal-content"><div class="modal-header"><div><span class="badge-source">${esc(r.origin)}</span><h2>${esc(r.player||'Inconnu')} ${r.opponent?'vs '+esc(r.opponent):''}</h2><div class="modal-meta">${esc(r.date)} · ${esc(r.tournament||r.circuit)} · ${esc(r.book||'Book inconnu')}<br>ID source : <code>${esc(r.uid||'non renseigné')}</code></div></div><button class="modal-close" data-close="yes" aria-label="Fermer">×</button></div><div class="modal-grid"><div><small>Cote entrée</small><strong>${money(r.odds)}</strong></div><div><small>Amplitude</small><strong>${nf(r.amplitude,2)}</strong></div><div><small>CLV bookmaker</small><strong class="${styleVal(r.clv)}">${pct(r.clv)}</strong></div><div><small>Résultat</small><strong class="${styleVal(r.pnl)}">${r.pnl===null?'En attente':nf(r.pnl,2)+' u'}</strong></div></div><div class="callout"><strong>Statut : </strong>${esc(r.status)} ${r.provisional?'· Règlement provisoire':''}<br><strong>Avant match :</strong> ${nf(r.lead)} min · <strong>Book :</strong> ${esc(r.book)} · <strong>Source résultat :</strong> ${esc(r.result_source||'source native')}</div><h3>Historique de clôture</h3>${c?lineChart(c):'<div class="empty">Aucune courbe retrouvée avec certitude pour cette paire de joueurs et cette date.</div>'}<h3>Autres enregistrements du même UID (${shared.length})</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Source</th><th>Joueur</th><th>Book</th><th class="num">Cote</th><th class="num">Profit</th></tr></thead><tbody>${shared.map(x=>`<tr><td>${esc(sourceLabels[x.source])}</td><td>${esc(x.player)}</td><td>${esc(x.book)}</td><td class="num">${money(x.odds)}</td><td class="num">${nf(x.pnl,2)}</td></tr>`).join('')}</tbody></table></div></div>`;
 $('#detailDialog').showModal();}
function render(){const meta=sections[view];$('#breadcrumb').textContent=meta[0].toUpperCase();$('#title').textContent=meta[0];$('#sectionHeading').textContent=meta[1];$('#sectionDesc').textContent=meta[2];$('#scopeLabel').textContent=`Données ${D.meta.snapshot||'inconnues'} · ${nf(D.rows.length)} lignes`;
 $$('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.view===view));$('#sampleCount').textContent=nf(sourceData().length)+' observations';
 $('#filterNote').textContent=cfg.population.startsWith('h')?'Amplitude des hypothèses en points de probabilité.':cfg.population==='clv'?'CLV seulement : pas de ROI sur ce journal.':'Amplitude de mouvement en % de cote, sauf paper match (palier).';
 let s=sourceData();$('#view').innerHTML= view==='dashboard'?renderDashboard(s):view==='explorer'?renderExplorer(s):view==='hypotheses'?renderHyp(s):view==='clv'?renderCLV(s):view==='books'?renderBooks(s):view==='matches'?renderMatches(s):quality();renderSaved();}
function navigate(n){view=n;page=0;render();window.scrollTo({top:0,behavior:'smooth'});$('#sidebar').classList.remove('open')}
function store(){try{return JSON.parse(localStorage.getItem('tennis-edge-lab-views')||'[]')}catch{return []}}
function renderSaved(){let saved=store();let p=$('#savedLine');p.classList.toggle('active',saved.length>0);p.innerHTML=saved.length?`<span class="smallgray">Vues enregistrées :</span>${saved.map((v,i)=>`<button data-apply="${i}" title="Appliquer cette sélection">${esc(v.name)}</button>`).join('')}<button data-delete="all" title="Supprimer les vues enregistrées">Effacer</button>`:''}
function onExport(){let data=sourceData(),keys=['source','uid','date','player','opponent','tournament','circuit','book','odds','amplitude','lead','clv','clv_pin','status','settled','provisional','result_source','won','pnl','origin'];
const cell=v=>{let t=v===null||v===undefined?'':String(v);if(/^[=+@\-\t\r]/.test(t) && isNaN(Number(t)))t="'"+t;return '"'+t.replace(/"/g,'""')+'"'};
let csv='\ufeff'+keys.map(cell).join(';')+'\r\n'+data.map(r=>keys.map(k=>cell(r[k])).join(';')).join('\r\n');let blob=new Blob([csv],{type:'text/csv;charset=utf-8'});let url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`tennis_edge_lab_${cfg.population}_${D.meta.snapshot}.csv`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);toast(`${nf(data.length)} lignes exportées`)}
$$('.nav-btn').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.view)));
ids.forEach(k=>$('#'+k).addEventListener(k==='q'?'input':'change',()=>{cfg[k]=$('#'+k).value;page=0;render()}));
$('#resetFilters').addEventListener('click',()=>setCfg({population:cfg.population,circuit:'',book:'',status:'',oddsMin:'',oddsMax:'',ampMin:'',lead:'',dateMin:'',dateMax:'',q:'',validation:''}));
$('#exportCSV').addEventListener('click',onExport);
$('#saveFilter').addEventListener('click',()=>{let name=prompt('Nom de cette hypothèse / vue enregistrée :',`${sourceLabels[cfg.population]} · ${new Date().toLocaleDateString('fr-FR')}`);if(!name)return;let saved=store();saved.push({name:name.slice(0,75),filters:{...cfg},created:new Date().toISOString()});try{localStorage.setItem('tennis-edge-lab-views',JSON.stringify(saved.slice(-40)));renderSaved();toast('Vue sauvegardée dans ce navigateur')}catch{toast('Stockage local inaccessible')}});
$('#savedLine').addEventListener('click',e=>{let btn=e.target.closest('button');if(!btn)return;if(btn.dataset.delete==='all'){if(confirm('Effacer les vues enregistrées sur cet appareil ?')){localStorage.removeItem('tennis-edge-lab-views');renderSaved()}}else if(btn.dataset.apply){let s=store()[+btn.dataset.apply];if(s)setCfg(s.filters)}});
$('#view').addEventListener('click',e=>{let el=e.target.closest('[data-row]');if(el){showDetail(el.dataset.row);return}el=e.target.closest('[data-page]');if(el){page+=Number(el.dataset.page);render();return}el=e.target.closest('[data-sort]');if(el){let key=el.dataset.sort;if(sortKey===key)sortDir*=-1;else{sortKey=key;sortDir=key==='date'?-1:1}page=0;render();return}el=e.target.closest('[data-hyp]');if(el){setCfg({population:el.dataset.hyp,circuit:'',book:'',oddsMin:'',oddsMax:'',ampMin:'',lead:'',dateMin:'',dateMax:'',q:'',status:'',validation:''});navigate('explorer');return}if(e.target.closest('#jumpExplorer'))navigate('explorer')});
$('#detailDialog').addEventListener('click',e=>{if(e.target.dataset.close==='yes')$('#detailDialog').close()});
$('#menubtn').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
$('#themeBtn').addEventListener('click',()=>{document.body.classList.toggle('dark');try{localStorage.setItem('tennis-edge-lab-theme',document.body.classList.contains('dark')?'dark':'light')}catch{}});
try{if(localStorage.getItem('tennis-edge-lab-theme')==='dark')document.body.classList.add('dark')}catch{}
// Synchronisation en lecture seule du dataset GitHub Pages. L'archive incluse reste le secours hors ligne.
let liveHash=null, liveMode='snapshot', lastSync=null, refreshing=false;
const refreshUi=()=>{
  const banner=$('#liveStatus'),badge=$('#connectionBadge'),meta=$('#dataTimestamp');
  if(banner)banner.textContent=liveMode==='live'?'Synchronisé avec GitHub Pages':liveMode==='checking'?'Vérification des mises à jour…':liveMode==='error'?'Hors ligne — dernier jeu disponible':'Instantané de secours';
  if(badge){badge.textContent=liveMode==='live'?'● DONNÉES AUTO':liveMode==='checking'?'◌ SYNCHRO…':'● MODE LOCAL';badge.classList.toggle('online',liveMode==='live')}
  if(meta)meta.textContent=lastSync?`Dernière vérification ${new Date(lastSync).toLocaleString('fr-FR')}`:'En attente de synchronisation';
};
function reloadSelectors(){
  distribution=Object.fromEntries(sources.map(x=>[x,D.rows.filter(r=>r.source===x).length]));
  selectors.population.innerHTML=sources.map(x=>`<option value="${x}">${esc(sourceLabels[x]||x)} (${nf(distribution[x])})</option>`).join('');
  circuitNames=[...new Set(D.rows.map(r=>r.circuit).filter(Boolean))].sort();
  selectors.circuit.innerHTML='<option value="">Tous les circuits</option>'+circuitNames.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
  allBooks=[...new Set(D.rows.map(r=>r.book).filter(Boolean))].sort();
  selectors.book.innerHTML='<option value="">Tous les bookmakers</option>'+allBooks.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
  for(const k of ['population','circuit','book']){
    let control=selectors[k];
    if([...control.options].some(opt=>opt.value===cfg[k]))control.value=cfg[k];
    else {cfg[k]=''; if(k==='population'){cfg[k]='moves'}control.value=cfg[k]}
  }
}
async function fetchJson(url,timeout=20000,sha256=null){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);
 try {
   const resp=await fetch(url,{cache:'no-store',signal:controller.signal,mode:'same-origin'});
   if(!resp.ok)throw Error('HTTP '+resp.status);
   if(sha256){
     // Une seule lecture des données ; on vérifie le SHA-256 avant d'intégrer l'objet.
     if(typeof crypto==='undefined'||!crypto.subtle)throw Error('SHA-256 non disponible sur cette origine');
     const bytes=await resp.arrayBuffer();
     const digest=await crypto.subtle.digest('SHA-256',bytes);
     const hex=Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
     if(hex!==sha256)throw Error('Empreinte SHA-256 non conforme');
     return JSON.parse(new TextDecoder('utf-8').decode(bytes));
   }
   return await resp.json();
 }finally{clearTimeout(timer)}
}
async function refreshData(manual=false){
 if(refreshing)return;
 refreshing=true;liveMode='checking';refreshUi();
 try{
   // URLs relatives : exportées par le workflow Pages du dépôt.
   // Aucune clé API ni token de dépôt dans le navigateur.
   const manifest=await fetchJson('./live/manifest.json?rnd='+Date.now(),12000);
   if(manifest.schema_version!==1||!manifest.dataset_sha256||!Number.isInteger(manifest.row_count)||manifest.row_count<200)throw Error('Manifeste invalide');
   if(manifest.dataset_url!=='data.json')throw Error('Chemin de données non autorisé');
   if(manifest.dataset_sha256!==liveHash){
     const data=await fetchJson('./live/data.json?hash='+manifest.dataset_sha256,30000,manifest.dataset_sha256);
     if(!Array.isArray(data.rows)||!data.curves||data.rows.length!==manifest.row_count||!data.meta||!data.meta.generated_at)throw Error('Jeu incomplet');
     D=data;liveHash=manifest.dataset_sha256;reloadSelectors();render();
     if(manual)toast(`${nf(D.rows.length)} observations actualisées`);
   }else if(manual){toast('Les données sont déjà à jour')}
   liveMode='live';lastSync=Date.now();refreshUi();render();
 }catch(err){
   liveMode=lastSync?'live':'error';refreshUi();
   if(manual)toast('Synchronisation impossible : '+String(err.message||err).slice(0,100));
   console.warn('[Tennis Edge Lab] Synchronisation indisponible, données locales conservées :',err);
 }finally{refreshing=false}
}
$('#refreshData')?.addEventListener('click',()=>refreshData(true));
setCfg(cfg);refreshUi();
if(location.protocol==='https:'||location.protocol==='http:'){
 refreshData(false);setInterval(()=>{if(document.visibilityState!=='hidden')refreshData(false)},5*60*1000);
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refreshData(false)});
}
})();
