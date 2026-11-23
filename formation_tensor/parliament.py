"""Reproduce parliamentary boundary profiles and conditional party associations."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

from .associations import DISCOVERY, REPLAY, discovery_candidates, replay_candidates, descriptive_inventory
from .raw_parliament import audit

BUDGETS = (0, 1, 2, 3, 5, 10, 20)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def reach(counts, switches, abstentions=0, absentees=0):
    if len(counts) != 4 or any(type(x) is not int or x < 0 for x in counts):
        raise ValueError('Four nonnegative integer member counts are required.')
    if any(type(x) is not int or x < 0 for x in (switches, abstentions, absentees)):
        raise ValueError('Interventions use separate nonnegative integer caps.')
    yes, no, abstain, absent = counts
    if yes == no:
        return None
    return 2*min(switches, max(yes,no))+min(abstentions,abstain)+min(absentees,absent)>abs(yes-no)


def boundary_profile(rows):
    eligible = [r for r in rows if r['counts'][0] != r['counts'][1]]
    report_sizes = Counter((r['session'],r['report']) for r in eligible)
    report_count = len(report_sizes)
    weights = [1/(report_count*report_sizes[r['session'],r['report']]) for r in eligible]
    budget_rows = []
    for budget in BUDGETS:
        values = [int(reach(r['counts'],budget)) for r in eligible]
        budget_rows.append({'budget':budget,'reversible_count':sum(values),
            'rollcall_fraction':sum(values)/len(values) if values else None,
            'report_fraction':sum(w*v for w,v in zip(weights,values)) if values else None})
    return {'rollcalls':len(rows),'eligible_rollcalls':len(eligible),'reports':report_count,
        'budget_profile':budget_rows,'median_switch_boundary':median(abs(r['counts'][0]-r['counts'][1])//2+1 for r in eligible) if eligible else None,
        'absence_capacity_count':sum(bool(reach(r['counts'],0,0,r['counts'][3])) for r in eligible),
        'abstention_capacity_count':sum(bool(reach(r['counts'],0,r['counts'][2],0)) for r in eligible)}


def joint_profile(rows, switches, absentees):
    triples = [(bool(reach(r['counts'],switches,0,absentees)),bool(reach(r['counts'],switches)),bool(reach(r['counts'],0,0,absentees)))
               for r in rows if r['counts'][0] != r['counts'][1]]
    return {'switch_cap':switches,'absence_cap':absentees,'joint_reachable':sum(t[0] for t in triples),
        'switch_alone':sum(t[1] for t in triples),'absence_alone':sum(t[2] for t in triples),
        'both_required':sum(j and not a and not b for j,a,b in triples),
        'either_already_sufficient':sum(a and b for j,a,b in triples)}


def run_experiment(root, output_dir=None, progress=None):
    root=Path(root).resolve(); out=Path(output_dir) if output_dir else root/'results/parliament'
    out.mkdir(parents=True,exist_ok=True)
    source=root/'data/parliament/rollcalls.json'; rows=json.loads(source.read_text())['rows']
    assert len(rows)==2612
    write(out/'reconciliation.json',audit(root,rows))
    for r in rows:
        assert sum(r['counts'])==349
        assert [sum(v[k] for v in r['party_counts'].values())+r['independent_counts'][k] for k in range(4)]==r['counts']
    discovery=discovery_candidates([r for r in rows if r['session'] in DISCOVERY])
    write(out/'selection.json',discovery['selection'])
    replay=replay_candidates([r for r in rows if r['session'] in REPLAY],discovery['selection'])
    inventory=descriptive_inventory(rows)
    summary={'schema':'formation-tensor.parliament.v1','status':'passed','member_rows':sum(sum(r['counts']) for r in rows),
        'overall':boundary_profile(rows),
        'sessions':{s:boundary_profile([r for r in rows if r['session']==s]) for s in sorted({r['session'] for r in rows})},
        'committees':{s:boundary_profile([r for r in rows if r['committee']==s]) for s in sorted({r['committee'] for r in rows})},
        'joint_caps':[joint_profile(rows,2,3),joint_profile(rows,5,5)],
        'selected_candidates':replay['candidates'],
        'scope':'Conditional member-ballot arithmetic and retrospective party-action associations; not repeated government formations.'}
    assert summary['overall']['budget_profile'][4]['reversible_count']==163
    assert summary['joint_caps'][0]['both_required']==36
    write(out/'summary.json',summary);write(out/'discovery.json',discovery);write(out/'replay.json',replay);write(out/'inventory.json',inventory)
    groups=[('discovery',discovery['all_pairs']),('pooled',inventory['all_pairs_pooled'])]+[(p['session'],p['pairs']) for p in inventory['periods']]+[('committee:'+p['committee'],p['pairs']) for p in inventory['committees']]
    with (out/'associations.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['scope','party_a','party_b','common_votes','reports','observed','conditional_reference','excess_pp'])
        for scope,pairs in groups:
            for p in pairs:
                a=p['report_equal'];writer.writerow([scope,*p['parties'],p['common_rollcalls'],p['reports'],a['observed_agreement'],a['conditional_reference'],a['excess_agreement_pp']])
    inputs=[source,root/'data/parliament/protocol.json',Path(__file__),root/'formation_tensor/associations.py',
            root/'formation_tensor/raw_parliament.py',root/'data/parliament/raw-sources.json']
    inputs+=sorted((root/'data/parliament/raw').glob('votering-*.csv.zip'))
    files={str(p.relative_to(root)):sha(p) for p in inputs}
    if out==root/'results/parliament':
        files.update({str(p.relative_to(root)):sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'})
    write(out/'manifest.json',{'schema':'formation-tensor.result-manifest.v1','status':'passed','files':files,
        'input_sha256':{str(p.relative_to(root)):sha(p) for p in inputs},
        'output_sha256':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'}})
    if progress:progress('parliament completed: 2612 roll calls, 28 pairs')
    return summary
