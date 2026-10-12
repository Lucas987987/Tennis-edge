/* Tennis Edge Lab V4: tableaux audités et archives segmentées, 100 % lecture seule */
(() => {'use strict';
const el=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,k=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[k]));
const number=x=>x===null||x===undefined?'—':new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(x);
const pct=x=>x===null||x===undefined?'—':(x>0?'+':'')+number(x)+' %';
async function load(file){const r=await fetch(file+'?v='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error(file+' : HTTP '+r.status);return await r.json()}
const wrapRows=(head,rows)=>`<div class="table-wrap"><table><thead><tr>${head.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
const kpi=(title,count,detail)=>`<div class="kpi"><small>${esc(title)}</small><b>${esc(count)}</b><small>${esc(detail)}</small></div>`;
async function prospects(){try{
 const d=await load('./live/prospective.json');if(d.schema_version!==1||!Array.isArray(d.models))throw Error('Schéma incompatible');
 el('prospectiveNotice').innerHTML=`<b>${number(d.total_frozen)} pistes gelées</b> · registre : <code>${esc(d.ledger_tip).slice(0,16)}</code><div class="meta-list">${esc(d.validation_minimum)}. Un ROI rétroactif n'autorise aucun statut validé.</div>`;
 if(!d.models.length){el('prospectiveCards').innerHTML='<p>Aucune piste encore gelée. Le cycle quotidien crée les premiers gels lorsqu’un candidat remplit les conditions prédéfinies, sans modifier H13–H18.</p>';return}
 el('prospectiveCards').innerHTML=d.models.map(x=>{const n=x.metrics||{},ci=n.ci95;
 return `<article class="candidate"><h3>${esc(x.label)}</h3><p class="small-rule"><span class="badge">${esc(x.type)}</span> · Gel : ${esc(x.freeze_date)} · Premiers matchs admissibles : ${esc(x.eligible_after)}</p>
  <div class="stats"><div><small>Résultats futurs</small><strong>${number(n.n)}</strong></div><div><small>ROI post-gel</small><strong class="${n.roi===null?'neutral':n.roi>0?'good':'bad'}">${pct(n.roi)}</strong></div><div><small>Jours distincts</small><strong>${number(x.days)}</strong></div></div>
  <p class="detail">IC95 bootstrap ${ci?pct(ci[0])+' à '+pct(ci[1]):'—'} · p Holm ${number(x.p_holm)} · 5 meilleurs gains / P&L : ${pct(x.concentration_5_best_percent)}</p>
  <span class="chip">${esc(x.status)}</span></article>`}).join('');
 }catch(e){el('prospectiveNotice').textContent='Le registre n’est pas encore publié : '+e.message;el('prospectiveCards').innerHTML=''} }
let archive=null,yearRows=[];
function archiveTable(){const key=(el('archiveSearch').value||'').toLowerCase().trim();const r=yearRows.filter(x=>!key||((x.winner||'')+' '+(x.loser||'')+' '+(x.tournament||'')).toLowerCase().includes(key));
 el('archiveSummary').textContent=number(r.length)+' matchs dans la sélection. Seuls les 100 premiers sont affichés pour préserver le mobile.';
 el('archiveTable').innerHTML=wrapRows(['Date','Vainqueur','Adversaire','Tournoi','Circuit / surface','Prix historiques'],r.slice(0,100).map(x=>`<tr><td>${esc(x.date)}</td><td><b>${esc(x.winner)}</b></td><td>${esc(x.loser)}</td><td>${esc(x.tournament)}</td><td>${esc(x.circuit)} / ${esc(x.surface||'—')}</td><td>${number(x.psw)} / ${number(x.psl)}</td></tr>`));}
async function selectArchive(){const year=el('archiveYear').value;if(!year){yearRows=[];archiveTable();return}
 try{const d=await load('./live/archive/'+encodeURIComponent(year)+'.json');if(!Array.isArray(d.matches))throw Error('Invalide');yearRows=d.matches;archiveTable()}catch(e){yearRows=[];el('archiveTable').textContent='Cette année est indisponible : '+e.message}}
async function sources(){try{
 const [d,a]=await Promise.all([load('./live/source_catalog.json'),load('./live/archive/index.json').catch(()=>null)]);
 el('sourceMetrics').innerHTML=kpi('Fichiers inventoriés',number(d.total_data_files),'Sources versionnées')+kpi('Taille des sources',number(d.total_bytes/1e6)+' Mo','Pas chargées dans le navigateur')+kpi('Partitions indexées',number(d.indexed_partition_files),'Agrégées avant le signal')+kpi('Historique de matchs',number(a?.unique_matches),'Noms archivés tels quels');
 el('sourceTable').innerHTML=wrapRows(['Famille','Fichiers','Données (Mo)'],(d.families||[]).map(x=>`<tr><td>${esc(x.family)}</td><td>${number(x.files)}</td><td>${number(x.bytes/1e6)}</td></tr>`))+'<p class="mini">'+esc(d.warning)+'</p>';
 if(a){archive=a;
 const sel=el('archiveYear');sel.innerHTML='<option value="">Choisir une année</option>'+a.years.slice().reverse().map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
 el('archiveSegments').innerHTML=wrapRows(['Circuit','Surface','Cote favori','N','ROI descriptif','Avant 2024','Depuis 2024'],(a.historical_segments||[]).slice(0,50).map(x=>`<tr><td>${esc(x.circuit)}</td><td>${esc(x.surface)}</td><td>${esc(x.prix_favori)}</td><td>${number(x.count)}</td><td>${pct(x.roi_total)}</td><td>${pct(x.before_2024?.roi)} (${number(x.before_2024?.n)})</td><td>${pct(x.since_2024?.roi)} (${number(x.since_2024?.n)})</td></tr>`))+
  '<p class="mini">Prix historiques de référence, pas des paris effectivement réalisés ni des promesses de rentabilité.</p>';
 }else{el('archiveSegments').innerHTML='<p>Archive non encore construite par la tâche quotidienne.</p>'}
 }catch(e){el('sourceTable').textContent='L’inventaire complet sera disponible après la première collecte nocturne : '+e.message;el('sourceMetrics').innerHTML='';}}
function v5SegmentCard(x){
 const marketLabel={match:'Vainqueur du match',set1:'Vainqueur du set 1',set2:'Vainqueur du set 2'};
 const criteria=(x.criteria||[]).map(c=>`${c.dimension} : ${c.value}`).join(' · ')||'Segment complet';
 const ci=x.roi_ci95?`${pct(x.roi_ci95[0])} à ${pct(x.roi_ci95[1])}`:'—';
 return `<article class="candidate"><h3>${esc(marketLabel[x.market]||x.market)} · ${esc(x.book)} · ${esc(x.horizon)} · ${esc(x.selection)}</h3><p>${esc(criteria)}</p><div class="stats"><div><small>Paris uniques</small><strong>${number(x.unique_matches)}</strong></div><div><small>ROI</small><strong class="${x.roi_pct===null?'neutral':x.roi_pct>0?'good':'bad'}">${pct(x.roi_pct)}</strong></div><div><small>CLV même marché</small><strong>${pct(x.clv_mean_pct)}</strong></div></div><p class="detail">Âge moyen de la cote : ${number(x.quote_age_mean_min)} min · IC95 ROI ${ci} · p Holm ${number(x.p_holm)} · première / seconde moitié ${pct(x.first_half?.roi_pct)} / ${pct(x.second_half?.roi_pct)} · ${number(x.clv_n)} CLV</p><span class="chip">${esc(x.status)} · gel automatique désactivé</span></article>`;
}
async function bookmakersSets(){try{
 const d=await load('./live/bookmakers_sets.json');
 if(d.schema_version!==1||!d.coverage||!d.summary)throw Error('Schéma V5 incompatible');
 el('v5Notice').innerHTML=`Généré le ${esc(new Date(d.generated_at).toLocaleString('fr-FR'))} · ${number(d.summary.tested_segments)} tests corrigés globalement par Holm · aucune nouvelle hypothèse n’est gelée.`;
 el('v5Metrics').innerHTML=kpi('Matchs-bookmakers-marchés',number(d.summary.unique_market_book_matches),'Après contrôle des identifiants')+kpi('Snapshots pré-match réglés',number(d.summary.settled_snapshots),'Match, set 1 et set 2')+kpi('Couvertures bookmaker-marché',number(Object.values(d.coverage).reduce((n,m)=>n+m.bookmaker_count,0)),'Un bookmaker peut couvrir plusieurs marchés')+kpi('Signaux rétrospectifs',number(d.summary.signals),'Validation prospective requise');
 const labels={match:'Vainqueur du match',set1:'Vainqueur du set 1',set2:'Vainqueur du set 2'};
 const coverage=[];
 for(const [market,info] of Object.entries(d.coverage)){
  for(const [book,x] of Object.entries(info.bookmakers||{})){
   coverage.push(`<tr><td>${esc(labels[market]||market)}</td><td><b>${esc(book)}</b></td><td>${number(x.partition_records)}</td><td>${number(x.matched_results)}</td>${['24h','6h','1h','10m'].map(h=>`<td>${number(x.snapshots?.[h])}</td>`).join('')}</tr>`);
  }
 }
 el('v5Coverage').innerHTML=coverage.length?`<div class="table-wrap"><table><thead><tr><th>Marché</th><th>Bookmaker</th><th>Matchs couverts</th><th>Avec résultat exact</th><th>24 h</th><th>6 h</th><th>1 h</th><th>10 min</th></tr></thead><tbody>${coverage.join('')}</tbody></table></div>`:'<p class="mini">Aucun bookmaker apparié avec résultats exacts.</p>';
 el('v5Discoveries').innerHTML=d.discoveries?.length?d.discoveries.slice(0,8).map(v5SegmentCard).join(''):'<p class="mini">Aucun signal rétrospectif n’atteint les seuils statistiques prédéfinis.</p>';
 el('v5Unconfirmed').innerHTML=d.unconfirmed?.length?d.unconfirmed.slice(0,20).map(v5SegmentCard).join(''):'<p class="mini">Aucune piste non confirmée disponible.</p>';
 const w=d.methodology?.warnings||[];
 el('v5Methodology').innerHTML=`<b>Méthode :</b> ${esc(d.methodology?.temporal_rule)} ${esc(d.methodology?.set2_rule)}<br>${esc(d.methodology?.horizon_rule)}<br>${esc(d.methodology?.roi)}<br>${esc(d.methodology?.movement)}<br>${esc(d.methodology?.margin)}<br>${esc(d.methodology?.clv)}<br>${esc(d.methodology?.inference)}<br>${w.map(esc).join('<br>')}`;
 }catch(e){el('v5Notice').textContent='Analyse Bookmakers & Sets indisponible : '+e.message;el('v5Coverage').textContent='L’inventaire sera publié après le calcul V5 sans requête API.';}}
el('archiveYear').addEventListener('change',selectArchive);
el('archiveSearch').addEventListener('input',archiveTable);
prospects();sources();bookmakersSets();
})();
