"""Generate publication figures directly from the completed numerical outputs."""
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'paper/figures'


def read(relative):return json.loads((ROOT/relative).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
        'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    paths=[]
    def save(fig,name):
        for suffix in ('pdf','svg','png'):
            p=OUT/(name+'.'+suffix);fig.savefig(p,bbox_inches='tight',dpi=230);paths.append(p)
        plt.close(fig)
    tensor=read('results/interactions/summary.json')
    pairs=tensor['pairs'];labels=[' / '.join(a+'>'+b for a,b in p['directions']) for p in pairs]
    fig,axes=plt.subplots(1,2,figsize=(8.7,3.6),layout='constrained')
    y=np.arange(len(pairs))
    neg=[p['negative_seat_interactions'] for p in pairs];pos=[p['positive_seat_interactions'] for p in pairs]
    axes[0].barh(y,-np.array(neg),color='#b36543',label='Negative seat difference')
    axes[0].barh(y,pos,color='#157b7e',label='Positive seat difference')
    axes[0].axvline(0,color='#4a5a66',lw=.8);axes[0].set_yticks(y,labels)
    axes[0].set(xlabel='Complete interior comparisons',title='A  Seat interactions')
    axes[0].legend(frameon=False,fontsize=7,loc='lower left')
    vals=[p['positive_threshold_interactions'] for p in pairs]
    axes[1].barh(y,vals,color='#157b7e')
    for i,v in enumerate(vals):axes[1].text(v+1,i,str(v),va='center',fontsize=8)
    axes[1].set_yticks(y,labels);axes[1].set(xlabel='Complete interior comparisons',title='B  Positive threshold interactions')
    for ax in axes:ax.invert_yaxis();ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
    save(fig,'tensor-interactions')

    bargaining=read('results/bargaining/summary.json');baseline=bargaining['baseline_profile_id']
    reach=read('results/bargaining/reachability.json')['rows']
    buffers=['none','L','KD','L+KD'];access=['none','C','V','C+V']
    matrix=np.full((4,4),np.nan)
    for r in reach:
        if r['profile_id']==baseline and r['initial_policy_mask']==0 and r['budget']==8:
            value=r['minimum_concession_cost']
            if value is not None:matrix[buffers.index(r['external_buffer']),access.index(r['relaxation_access'])]=value
    fig,axes=plt.subplots(1,3,figsize=(9.3,3.1),layout='constrained')
    cmap=plt.get_cmap('YlGnBu').copy();cmap.set_bad('#edf0f2')
    axes[0].imshow(matrix,cmap=cmap,vmin=0,vmax=6)
    for yy in range(4):
        for xx in range(4):
            v=matrix[yy,xx];axes[0].text(xx,yy,str(int(v)) if np.isfinite(v) else 'none',ha='center',va='center',fontsize=8,color='white' if v>=4 else '#253946')
    axes[0].set_xticks(range(4),access);axes[0].set_yticks(range(4),buffers)
    axes[0].set(xlabel='Composition clauses available for release',ylabel='Outside abstention buffer',title='A  Minimum concession cost')
    process=bargaining['baseline_full_episode_process']
    for adaptive,label,color in [(False,'Fixed agenda','#b36543'),(True,'Exhaustive re-search','#157b7e')]:
        values=[]
        for k in (1,2,3,4):
            row=next(r for r in process if r['pressure_clause']=='C' and r['pressure_trigger_total_rejections']==k and r['adaptive_after_release']==adaptive)
            values.append(row['outcome_counts'].get('agreement_found',0))
        axes[1].plot([1,2,3,4],values,marker='o',color=color,label=label)
    axes[1].set_xticks([1,2,3,4]);axes[1].set(xlabel='Formal rejection triggering clause release',ylabel='Agendas reaching agreement (of 40,320)',title='B  Timing and agenda')
    axes[1].legend(frameon=False,fontsize=7);axes[1].grid(alpha=.16)
    coupled=read('results/bargaining/coupled-profiles.json');profiles={p['profile_id']:p for p in coupled['profiles']}
    groups=[176,175,174];totals=[sum(p['S_C_V_MP_seats']==n for p in profiles.values()) for n in groups]
    for i,(buffer,label,color) in enumerate([('none','No external abstention','#b36543'),('L','L abstains','#157b7e')]):
        counts=[]
        for n in groups:
            ids={pid for pid,p in profiles.items() if p['S_C_V_MP_seats']==n}
            counts.append(sum(r['profile_id'] in ids and r['external_buffer']==buffer and r['relaxation_access']=='C+V' and r['structural_possible'] for r in coupled['rows']))
        axes[2].bar(np.arange(3)+(i-.5)*.34,counts,width=.34,label=label,color=color)
    axes[2].set_xticks(range(3),[str(n)+'\n('+str(t)+(' profile)' if t==1 else ' profiles)') for n,t in zip(groups,totals)])
    axes[2].set(xlabel='S/C/V/MP seats',ylabel='Profiles admitting an agreement',title='C  Seat--agreement coupling')
    axes[2].legend(frameon=False,fontsize=7);axes[2].set_ylim(0,17);axes[2].grid(axis='y',alpha=.16);axes[2].set_axisbelow(True)
    save(fig,'bargaining-sensitivity')

    events=read('data/formation/events2026.json')['events']
    fig,ax=plt.subplots(figsize=(8.5,3.1),layout='constrained')
    actors={'Magdalena Andersson':2,'Elisabeth Thand Ringqvist':1,'Ulf Kristersson':0}
    starts={'Magdalena Andersson':'2026-09-18','Elisabeth Thand Ringqvist':'2026-10-19','Ulf Kristersson':'2026-11-03'}
    ends={'Magdalena Andersson':'2026-10-15','Elisabeth Thand Ringqvist':'2026-11-03','Ulf Kristersson':'2026-11-22'}
    for actor,ypos in actors.items():
        ax.plot([date.fromisoformat(starts[actor]),date.fromisoformat(ends[actor])],[ypos,ypos],lw=3,color='#b5cfce')
    symbols={'exploratory_mandate_started':('o','#157b7e','Initial exploratory task'),
             'exploratory_mandate_resumed':('s','#49739c','Resumed task'),
             'exploratory_mandate_extended':('s','#49739c','Extension'),
             'formal_nomination':('D','#8c6c44','Formal nomination'),
             'formal_pm_vote':('X','#b36543','Rejected PM vote')}
    seen=set()
    for e in events:
        if e['actor'] in actors and e['event_type'] in symbols:
            marker,color,label=symbols[e['event_type']]
            ax.scatter(date.fromisoformat(e['event_date']),actors[e['actor']],marker=marker,color=color,s=60,label=label if label not in seen else None,zorder=4);seen.add(label)
    ax.axvline(date(2026,11,22),ls=':',color='#52626d');ax.text(date(2026,11,22),2.43,'Source cutoff',ha='right',fontsize=8)
    ax.scatter(date(2026,11,24),-.43,marker='>',color='#536a7b',s=45)
    ax.text(date(2026,11,24),-.65,'Scheduled\nconsultations',ha='right',fontsize=7)
    ax.set_yticks([0,1,2],['M: Kristersson','C: Thand Ringqvist','S: Andersson'])
    ax.set_ylim(-.95,2.65);ax.set_xlim(date(2026,9,15),date(2026,11,28))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2));ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.legend(loc='lower left',ncol=3,fontsize=7,frameon=False,bbox_to_anchor=(0,1.01));ax.grid(axis='x',alpha=.16)
    save(fig,'process-chronology')

    parl=read('results/parliament/summary.json')
    fig,axes=plt.subplots(1,2,figsize=(8.5,3.2),layout='constrained')
    profile=parl['overall']['budget_profile'][1:]
    for field,label,color in [('rollcall_fraction','Equal roll-call weight','#157b7e'),('report_fraction','Equal report weight','#b36543')]:
        axes[0].plot([x['budget'] for x in profile],[100*x[field] for x in profile],marker='o',color=color,label=label,markersize=3)
    axes[0].set(xlabel='Maximum existing ballots switching sides',ylabel='Reversible balances (%)',title='A  Parliamentary boundary profile')
    axes[0].legend(frameon=False,fontsize=7);axes[0].grid(alpha=.16)
    for c in parl['selected_candidates']:
        p=c['selected_candidate'];ys=[p['excess_agreement_pp']]+[x['analysis']['report_equal']['excess_agreement_pp'] for x in c['periods']]
        axes[1].plot(range(3),ys,marker='o',lw=1.2,label=p['pair_id'],markersize=3)
    axes[1].axhline(0,color='#596c79',lw=.7);axes[1].set_xticks(range(3),['First two sessions','2024/25','2025/26'])
    axes[1].set(ylabel='Conditional excess agreement (pp)',title='B  Fixed-candidate retrospective replay')
    axes[1].legend(frameon=False,ncol=2,fontsize=7,loc='lower right');axes[1].grid(alpha=.16)
    save(fig,'rollcall-patterns')
    inputs=['results/interactions/summary.json','results/bargaining/summary.json','results/bargaining/reachability.json','results/bargaining/coupled-profiles.json','data/formation/events2026.json','results/parliament/summary.json']
    (OUT/'manifest.json').write_text(json.dumps({'schema':'formation-tensor.figures.v1','files':{str(p.relative_to(ROOT)):sha(p) for p in paths},'input_sha256':{n:sha(ROOT/n) for n in inputs},'script_sha256':sha(Path(__file__)),'matplotlib':matplotlib.__version__,'numpy':np.__version__,'python':sys.version},indent=2)+'\n')
    print(json.dumps({'figures':4,'files':len(paths)}))


if __name__=='__main__':main()
