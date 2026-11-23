'use strict';
const $ = id => document.getElementById(id);
const fmt = value => typeof value === 'number' ? value.toLocaleString('en-GB') : String(value ?? '—');
const node = (tag, text = '', className = '') => { const n = document.createElement(tag); n.textContent = text; if (className) n.className = className; return n; };
const clear = target => { target.replaceChildren(); return target; };
const paragraph = (target, text, className = '') => target.append(node('p', text, className));
let research;
let electoralIndex;
let bargainingRows = [];
let sequenceRows = [];

function sourceLink(url, label = 'Official source ↗') {
  if (typeof url !== 'string' || !url.startsWith('https://')) return node('span', label, 'muted');
  const a = node('a', label); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
}
function options(select, values, label, preferred) {
  select.replaceChildren();
  for (const value of values) { const option = node('option', label(value)); option.value = String(value); select.append(option); }
  if (preferred !== undefined && values.map(String).includes(String(preferred))) select.value = String(preferred);
}
function table(headers, rows) {
  const wrapper = node('div', '', 'table-scroll'); const t = node('table'); const thead = node('thead'); const hrow = node('tr');
  for (const title of headers) hrow.append(node('th', title)); thead.append(hrow); t.append(thead); const body = node('tbody');
  for (const row of rows) { const tr = node('tr'); for (const value of row) tr.append(node('td', fmt(value))); body.append(tr); }
  t.append(body); wrapper.append(t); return wrapper;
}
function metric(target, value, label) { const card = node('article', '', 'metric'); card.append(node('strong', fmt(value)), node('span', label)); target.append(card); }
function miniStats(target, rows) { const wrap = node('div', '', 'mini-stats'); for (const [value,label] of rows) { const item=node('div');item.append(node('strong',fmt(value)),node('span',label));wrap.append(item); }target.append(wrap); }
function showPanel(id) {
  document.body.dataset.view=id;
  for (const tab of document.querySelectorAll('[role=tab]')) { const active=tab.dataset.panel===id;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1; }
  for (const panel of document.querySelectorAll('[role=tabpanel]')) panel.hidden=panel.id!==id;
}
for (const tab of document.querySelectorAll('[role=tab]')) {
  tab.addEventListener('click', () => showPanel(tab.dataset.panel));
  tab.addEventListener('keydown', e => {if(!['ArrowRight','ArrowLeft'].includes(e.key))return;const tabs=Array.from(document.querySelectorAll('[role=tab]'));const i=tabs.indexOf(tab);const next=tabs[(i+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length];showPanel(next.dataset.panel);next.focus();e.preventDefault();});
}

function overview() {
  const summary=research.interactions.summary; const census=research.parliament.summary;
  const events=research.events.events || [];
  const voteEvents=events.filter(e=>e.ballot_counts);
  const target=$('metrics');clear(target);
  metric(target,summary.coordinates,'electoral response coordinates');
  metric(target,summary.valid_coordinates,'completed exact allocations');
  metric(target,census.overall?.rollcalls ?? census.rollcalls,'parliamentary roll calls');
  metric(target,voteEvents.length,'observed 2026 investiture ballots');
  const cards=clear($('finding-cards'));
  const findings=[
    ['01 · REPRESENTATION','A party can gain a seat without receiving transferred votes.',`${fmt(summary.beneficiary_diagnostics?.any_nonrecipient_seat_gain)} of ${fmt(summary.beneficiary_diagnostics?.nonzero_valid_unique_tables)} distinct completed nonzero vote tables contain a seat gain for a party outside the receiving parties.`],
    ['02 · INTERACTION','Seat gains and threshold crossings behave differently.',`${fmt(summary.valid_interior_four_corners)} complete interior comparisons contain ${fmt(summary.positive_seat_interactions)} positive and ${fmt(summary.negative_seat_interactions)} negative seat interactions, alongside ${fmt(summary.positive_threshold_interactions)} positive threshold interactions.`],
    ['03 · FORMATION','An arithmetic majority is not an agreement.','Cabinet conditions, policy assent, and the path of concessions determine which agreements are available and which can be reached within a finite process.']
  ];
  for (const [number,title,text] of findings) { const card=node('article','','finding');card.append(node('div',number,'number'),node('h3',title),node('p',text));cards.append(card); }
  const p=clear($('parliament-summary')); const overall=census.overall || census;
  paragraph(p,`${fmt(overall.rollcalls)} roll calls contain ${fmt(census.member_rows)} recorded member actions. The median winning-side switch boundary is ${fmt(overall.median_switch_boundary)} members.`);
  const five=(overall.budget_profile||[]).find(r=>r.budget===5);
  if(five)paragraph(p,`${fmt(five.reversible_count)} recorded balances can be reversed by at most five existing winning-side ballots switching sides under the stated simple-majority counterfactual.`);
  const selected=census.selected_candidates || [];
  const mpv=selected.find(r=>(r.selected_candidate?.parties||[]).includes('MP')&&(r.selected_candidate?.parties||[]).includes('V'));
  if(mpv){const latest=mpv.periods?.at(-1);const excess=latest?.analysis?.report_equal?.excess_agreement_pp;if(typeof excess==='number')paragraph(p,`MP–V agreement remains ${excess.toFixed(2)} percentage points above the committee-by-session marginal reference in the final session.`);}
}

function setupElectoral() {
  const tensor=research.interactions.tensor;
  electoralIndex=new Map(tensor.cells.map(c=>[[c.pair_id,c.district_id,c.amount_a,c.amount_b].join('|'),c]));
  options($('transfer-pair'),tensor.axes.pair.map(p=>p.id),id=>{const p=tensor.axes.pair.find(v=>v.id===id);return p.directions.map(d=>d.join(' → ')).join('  +  ');},tensor.axes.pair[0].id);
  options($('constituency'),tensor.axes.district.map(d=>d.district_id),id=>tensor.axes.district.find(d=>d.district_id===id).label,'01');
  options($('amount-a'),tensor.axes.amount_voters,fmt,15000);options($('amount-b'),tensor.axes.amount_voters,fmt,10000);
  for(const id of ['transfer-pair','constituency','amount-a','amount-b'])$(id).addEventListener('change',renderElectoral);
  $('electoral-scope').textContent=`The declared nonrejecting group is ${(tensor.hypothetical_nonreject_parties||[]).join(' / ')}. This is a fixed hypothetical voting-role template. Cabinet consent and budget support are separate variables.`;
  renderElectoral();
}
function selectedCell(pair,district,a,b){return electoralIndex.get([pair,district,a,b].join('|'));}
function renderElectoral() {
  const tensor=research.interactions.tensor;const pairId=$('transfer-pair').value;const district=$('constituency').value;
  const a=Number($('amount-a').value),b=Number($('amount-b').value);const pair=tensor.axes.pair.find(p=>p.id===pairId);
  $('amount-a-label').firstChild.textContent=pair.directions[0].join(' → ')+' · voters';
  $('amount-b-label').firstChild.textContent=pair.directions[1].join(' → ')+' · voters';
  const grid=clear($('electoral-grid'));grid.append(node('div','A↓ / B→','axis'));
  for(const amount of tensor.axes.amount_voters)grid.append(node('div',amount?fmt(amount/1000)+'k':'0','axis'));
  for(const first of tensor.axes.amount_voters){grid.append(node('div',first?fmt(first/1000)+'k':'0','axis'));
    for(const second of tensor.axes.amount_voters){const row=selectedCell(pairId,district,first,second);const passed=row?.status==='passed';const button=node('button',passed?fmt(row.nonreject_seats):'—');button.type='button';button.classList.toggle('met',passed&&row.nonreject_at_least_175);button.classList.toggle('masked',!passed);button.classList.toggle('current',first===a&&second===b);button.setAttribute('aria-pressed',String(first===a&&second===b));button.setAttribute('aria-label',`${pair.directions[0].join(' to ')} ${first}; ${pair.directions[1].join(' to ')} ${second}: ${passed?row.nonreject_seats+' nonrejecting seats':'unavailable'}`);button.addEventListener('click',()=>{$('amount-a').value=String(first);$('amount-b').value=String(second);renderElectoral();});grid.append(button);}}
  $('grid-axis-note').textContent=`Rows: ${pair.directions[0].join(' → ')}. Columns: ${pair.directions[1].join(' → ')}. Striped coordinates are unavailable, not zero effects.`;
  const cell=selectedCell(pairId,district,a,b);const body=clear($('electoral-response'));const seats=clear($('party-seats'));
  const districtLabel=tensor.axes.district.find(d=>d.district_id===district)?.label || district;
  $('electoral-title').textContent=districtLabel+' · '+fmt(a+b)+' voters';
  if(!cell||cell.status!=='passed'){
    body.append(node('div','Unavailable','big-response'));
    paragraph(body,cell?.error_type==='insufficient_donor_votes'||cell?.error_type==='invalid_input'?'The selected transfer exceeds a donor’s available votes.':'This coordinate is outside the completed calculation domain.','result-line');
    paragraph(body,'No seat count or zero effect is assigned to an unavailable coordinate.');
  } else {
    const base=selectedCell(pairId,district,0,0);
    body.append(node('div',fmt(base.nonreject_seats)+' → '+fmt(cell.nonreject_seats),'big-response'),node('div','seats in the declared nonrejecting group','response-unit'));
    paragraph(body,cell.nonreject_at_least_175?'The nonrejection condition is met under the fixed voting-role template.':'The nonrejection condition is not met under the fixed voting-role template.','result-line');
    const interaction=cell.interaction;
    if(interaction?.status==='passed')paragraph(body,`Mixed seat difference: ${interaction.mixed_seats>0?'+':''}${interaction.mixed_seats}. Mixed threshold difference: ${interaction.mixed_threshold>0?'+':''}${interaction.mixed_threshold}.`);
    else paragraph(body,'The mixed difference is unavailable because at least one comparison corner is masked.');
    for(const [party,n] of Object.entries(cell.seat_vector||{}))if(n>0)seats.append(node('span',party+' '+n));
  }
  const corner=clear($('corner-table'));
  const corners=[['Baseline',0,0],['First transfer only',a,0],['Second transfer only',0,b],['Both transfers',a,b]];
  corner.append(table(['Calculation','Voter cost','Group seats'],corners.map(([label,x,y])=>{const c=selectedCell(pairId,district,x,y);return[label,fmt(x+y),c?.status==='passed'?c.nonreject_seats:'Unavailable'];})));
  const summary=research.interactions.summary.pairs.find(p=>p.pair_id===pairId);const note=clear($('pair-summary'));
  if(summary){miniStats(note,[[summary.valid_coordinates,'completed coordinates'],[summary.masked_coordinates,'masked coordinates'],[summary.valid_interior_four_corners,'complete interior comparisons']]);
    paragraph(note,'Mixed differences compare the joint allocation with both single-transfer allocations and their shared baseline. Seat-count interaction and threshold interaction are different quantities.');}
}

function pickRows(doc) {
  if(Array.isArray(doc))return doc;
  if(Array.isArray(doc?.columns)&&Array.isArray(doc?.rows))return doc.rows.map(row=>Object.fromEntries(doc.columns.map((name,i)=>[name,row[i]])));
  return doc?.rows || doc?.scenarios || doc?.results || [];
}
function setupBargaining() {
  const docs=research.bargaining;
  const dashboard=docs.dashboard||{};
  bargainingRows=pickRows(dashboard.reachability||docs.reachability);
  if(!bargainingRows.length)bargainingRows=pickRows(docs.summary);
  const policyLabel=v=>Number(v)===0?'None met':Number(v)===7?'All three met':['C','V','MP'].filter((_,i)=>Number(v)&(1<<i)).join(' + ')+' met';
  const profiles=dashboard.profiles||docs.reachability?.profiles||[];
  const profileLabel=v=>(profiles.find(p=>p.profile_id===v)?.label||String(v).replaceAll('_',' ')).replace('Pinned2026','Pinned 2026');
  const controlSpecs=[['bargaining-profile','profile_id',profileLabel,dashboard.baseline_profile_id||docs.reachability?.baseline_profile_id||'baseline'],['outside-buffer','external_buffer',v=>v==='none'?'None':v,'none'],['initial-policy','initial_policy_mask',policyLabel,0],['relaxation-access','relaxation_access',v=>v==='none'?'Neither clause':v==='C+V'?'Both clauses':v+' clause','C+V'],['concession-budget','budget',fmt,2]];
  for(const [id,key,label,preferred] of controlSpecs){const values=Array.from(new Set(bargainingRows.map(r=>r[key]))).filter(v=>v!==undefined);values.sort((a,b)=>typeof a==='number'?a-b:String(a).localeCompare(String(b)));options($(id),values,label,preferred);$(id).addEventListener('change',renderBargaining);}
  $('process-scope').textContent='The model varies explicit cabinet clauses, policy assent, outside abstention, and concession costs. These completed scenarios are source-inspired research assumptions, not a reconstruction of unobserved party preferences.';
  const envelope=clear($('source-envelope'));paragraph(envelope,'The documentary record does not complete all future prime-minister actions. Conditional cabinet statements remain conditional, and an action recorded toward one candidate is not carried over to another.');paragraph(envelope,'The controls define completed model scenarios so that their implications can be compared. Cabinet agreement, passage of an investiture ballot, and a budget agreement remain separate outcomes.');
  const design=clear($('process-design'));paragraph(design,'Three policy-assent bits describe the initial position. Each policy concession and clause relaxation has an explicit model cost. The exact state graph identifies the least-cost path to an agreement and whether that path fits the selected budget.');
  const account=clear($('speaker-account'));const statement=(research.events.actor_statements||[]).find(s=>s.id==='speaker-pressure-account');
  if(statement){paragraph(account,statement.description);const source=(research.sources.sources||[]).find(s=>s.id===statement.source_id);if(source)account.append(sourceLink(source.url,'Speaker’s statement · '+statement.statement_date+' ↗'));}
  const summary=docs.summary||{};
  if(summary.scope)paragraph(design,typeof summary.scope==='string'?summary.scope:JSON.stringify(summary.scope));
  sequenceRows=pickRows(dashboard.process||docs.process);
  for(const id of ['sequence-counter','pressure-clause','pressure-trigger','sequence-patience','adaptive-rule'])$(id).addEventListener('change',renderSequence);
  renderBargaining();
}
function renderBargaining(){
  const row=bargainingRows.find(r=>String(r.profile_id)===$('bargaining-profile').value&&String(r.external_buffer)===$('outside-buffer').value&&String(r.initial_policy_mask)===$('initial-policy').value&&String(r.relaxation_access)===$('relaxation-access').value&&String(r.budget)===$('concession-budget').value);
  const result=clear($('bargaining-result'));const movement=clear($('concession-result'));
  if(!row){paragraph(result,'This combination is not part of the completed sensitivity design.');return;}
  const structural=row.structural_possible;const reachable=row.agreement_reachable;
  const pair=node('div','','status-pair');for(const [label,value] of [['An agreement exists',structural],['Reachable within budget',reachable]]){const box=node('div','','status-box');box.append(node('span',label),node('strong',value?'Yes':'No'));pair.append(box);}result.append(pair);
  result.append(node('span',reachable?'Agreement reachable':structural?'Concession budget binds':'No feasible agreement',reachable?'badge':'badge blocked'));
  paragraph(result,reachable?'At least one permitted concession path reaches an agreement within this budget.':structural?'The completed agreement set is nonempty, but no permitted path fits this concession budget.':'The current rule profile admits no agreement in its stated candidate and cabinet family.');
  if(row.minimum_concession_cost!==null&&row.minimum_concession_cost!==undefined){movement.append(node('div',fmt(row.minimum_concession_cost),'big-response'),node('div','minimum concession cost','response-unit'));paragraph(movement,'Selected budget: '+fmt(row.budget)+'.');}else paragraph(movement,'No permitted finite concession path reaches an agreement.');
  const witness=row.witness || row.minimum_path || row.path;
  if(witness&&Array.isArray(witness))paragraph(movement,'One minimum path: '+witness.map(v=>typeof v==='string'?v:v.action||v.label||JSON.stringify(v)).join(' → '));
  const process=clear($('process-summary'));
  paragraph(process,'An exploratory assignment concerns negotiations. A formal rejection is a recorded vote on the Speaker’s nominee. Only the latter uses one of the four formal proposal opportunities.');
  paragraph(process,'Repeating the same rules and state is the null control: a new mandate does not itself create an agreement. Agenda rotation can change a bounded proposal path; it does not automatically relax cabinet or policy constraints.');
  renderSequence();
}

function renderSequence(){
  let selected=sequenceRows.filter(r=>String(r.profile_id)===$('bargaining-profile').value&&String(r.external_buffer)===$('outside-buffer').value);
  const specs=[['sequence-counter','initial_formal_rejections',2,v=>fmt(v)],['pressure-clause','pressure_clause','V',v=>v==='none'?'Neither':v+' clause'],['pressure-trigger','pressure_trigger_total_rejections',3,v=>v===null?'No release':fmt(v)],['sequence-patience','additional_vote_patience',2,fmt],['adaptive-rule','adaptive_after_release',false,v=>v?'Exhaustive re-search (oracle)':'Fixed agenda']];
  for(const [id,key,fallback,label] of specs){const select=$(id);const prior=select.value;const values=Array.from(new Set(selected.map(r=>r[key]))).filter(v=>v!==undefined).sort((a,b)=>typeof a==='number'?a-b:String(a).localeCompare(String(b)));const preferred=values.some(v=>String(v)===prior)?prior:fallback;options(select,values,label,preferred);selected=selected.filter(r=>String(r[key])===select.value);}
  const result=clear($('sequence-result'));const trace=clear($('sequence-trace'));const row=selected[0];
  if(!row){paragraph(result,'No stored proposal-order experiment matches this selection.');return;}
  paragraph(result,`${fmt(row.full_agenda_orders)} full proposal orders are enumerated. ${fmt(row.remaining_institutional_attempts)} formal proposal opportunities remain at the selected starting counter.`,'result-line');
  const names={agreement_found:'Agreement reached',four_rejections:'Four formal rejections',patience_exhausted:'Patience exhausted',pm_passed_without_cabinet_agreement:'PM passes; cabinet agreement absent'};
  result.append(table(['Outcome','Proposal-order count'],Object.entries(row.outcome_counts||{}).map(([status,count])=>[names[status]||status.replaceAll('_',' '),count])));
  paragraph(result,'These are exact counts over agenda orders in the model, not estimated probabilities of Swedish government outcomes.','small');
  const examples=research.bargaining.dashboard?.process?.trace_rows||research.bargaining.dashboard?.sequence_witnesses||[];
  const example=examples.find(r=>String(r.profile_id)===String(row.profile_id)&&r.external_buffer===row.external_buffer&&r.initial_formal_rejections===row.initial_formal_rejections&&r.pressure_clause===row.pressure_clause&&r.pressure_trigger_total_rejections===row.pressure_trigger_total_rejections&&r.additional_vote_patience===row.additional_vote_patience&&r.adaptive_after_release===row.adaptive_after_release);
  const witnesses=row.witnesses||example?.witnesses;
  const witness=witnesses?.agreement_found||Object.values(witnesses||{})[0];
  if(witness?.trace?.length){trace.append(node('h4','One enumerated proposal path'));trace.append(table(['Proposal','Cabinet parties','No ballots','Cabinet consent','Rejections before vote'],witness.trace.map((step,i)=>[i+1,(step.cabinet_members||[]).join(' / '),step.no,step.cabinet_consented?'Yes':'No',step.rejections_before_evaluation])));}
}

function history(){
  const events=research.events.events||[];const sources=new Map((research.sources.sources||[]).map(s=>[s.id||s.source_id,s]));
  $('history-scope').textContent=`The source record is dated ${research.events.as_of_date||'22 November 2026'}. Assignments, resumptions, nominations, recorded votes, and future consultations retain their distinct event types.`;
  const votes=events.filter(e=>e.ballot_counts);const holders=new Set(events.filter(e=>String(e.event_type).includes('exploratory')&&!/extension|resumption|report/.test(e.event_type)).map(e=>e.actor_party||e.actor).filter(Boolean));
  const counts=clear($('history-counts'));metric(counts,research.events.summary?.distinct_exploratory_holders??holders.size,'initial exploratory mandate holders');metric(counts,votes.length,'recorded prime-minister ballots');metric(counts,events.filter(e=>e.formal_rejection_count_delta===1).length,'recorded formal rejections');metric(counts,events.length,'dated event records');
  const voteCards=clear($('actual-votes'));
  for(const event of votes){const card=node('article','','plain-card observed-card');card.append(node('div',event.event_date,'date'),node('h3',event.actor||event.candidate||'Prime-minister ballot'));const values=node('div','','vote-counts');for(const [key,label] of [['yes','Yes'],['no','No'],['abstain','Abstain'],['absent','Absent']]){const item=node('div');item.append(node('strong',fmt(event.ballot_counts[key])),node('span',label));values.append(item);}card.append(values);const boundary=Math.max(0,event.ballot_counts.no-174);paragraph(card,`${fmt(boundary)} existing No ballots would have to become abstentions, with other actions fixed, to reduce No to 174. This is the retrospective member-ballot boundary.`);const source=sources.get(event.source_ids?.[0]);if(source)card.append(sourceLink(source.url));voteCards.append(card);}
  const timeline=clear($('chronology'));
  for(const event of events){const item=node('article','','timeline-event');item.classList.toggle('ballot',Boolean(event.ballot_counts));item.classList.toggle('future',event.status==='announced_future');item.append(node('div',event.event_date||'Date not specified','timeline-date'));const body=node('div','','timeline-body');body.append(node('span',String(event.event_type||'event').replaceAll('_',' '),'kind'),node('h4',event.actor||event.actor_party||'Institutional event'));paragraph(body,event.description||'');if(event.status==='announced_future')body.append(node('span','Announced future event','badge'));const links=node('div','','source-links');for(const id of event.source_ids||[]){const source=sources.get(id);if(source)links.append(sourceLink(source.url,source.publisher||'Source ↗'));}body.append(links);item.append(body);timeline.append(item);}
  const sourceBody=clear($('source-table'));for(const source of sources.values()){const row=node('tr');row.append(node('td',source.id||source.source_id),node('td',source.event_date||'—'),node('td',source.first_publication_at||'—'),node('td',source.accessed_at_utc||'—'));const link=node('td');link.append(sourceLink(source.url,'Open ↗'));row.append(link);sourceBody.append(row);}
}

async function start(){
  try{const response=await fetch('/api/research');if(!response.ok){let detail;try{detail=await response.json();}catch{}throw Error(detail?.message||'The research record is unavailable.');}research=await response.json();if(research.integrity!=='passed')throw Error('The research record could not be verified.');overview();setupElectoral();setupBargaining();history();const inventory=clear($('inventory'));for(const [name,digest] of Object.entries(research.manifest_sha256||{}))paragraph(inventory,name+': '+digest);$('workspace').hidden=false;$('load-status').textContent='Research record verified · source snapshot '+(research.events.as_of_date||'22 November 2026');}
  catch(error){$('load-status').textContent=error.message;$('load-status').classList.add('error');}
}
start();
