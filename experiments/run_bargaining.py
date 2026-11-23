"""Exact bargaining-state and agenda experiments, including electoral coupling."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from formation_tensor.bargaining import (
    BUFFERS, CORE, PARTIES, RELAXATION_ACCESS, evaluate_proposal,
    exhaustive_agendas, proposal_lookup, reachability_rows, shortest_paths,
    simulate_agenda, states, transitions,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    options={'ensure_ascii':False,'allow_nan':False}
    if path.name=='dashboard.json':
        options['separators']=(',',':')
    else:
        options['indent']=2
    path.write_text(json.dumps(value, **options)+'\n')


def protocol():
    return {
        'schema':'formation-tensor.bargaining-protocol.v1',
        'model':'Hypothetical finite-state S-led proposal family; not fitted party intentions.',
        'cabinet_family':'S plus every subset of C,V,MP: eight proposals; other cabinets outside scope.',
        'policy_bits':{'0':'C requirement met','1':'V requirement met','2':'MP requirement met'},
        'state':'(three-bit policy mask, C composition condition relaxed, V essential-inclusion condition relaxed)',
        'state_count':32,
        'pm_actions':'S Yes. C non-No iff its policy requirement met and either V outside cabinet or C clause relaxed. MP non-No iff its policy met. V non-No iff its policy met and either V not essential, V in cabinet, or V clause relaxed. Cabinet members Yes; admitted nonmember support abstains. Other parties No except explicit external abstention buffers.',
        'V_essential':'With all other party actions held fixed: other_non_No<175<=other_non_No+V_seats. Hopeless proposals are not V-essential.',
        'consent':'S consents; every other included member must have its policy requirement met; included C additionally requires its composition condition. Consent is separate from PM nonrejection.',
        'budget_support':'Not modelled; no inference from cabinet or PM actions.',
        'external_buffers':{'none':[],'L':['L'],'KD':['KD'],'L+KD':['L','KD']},
        'initial_policy_masks':list(range(8)), 'initial_composition_relaxations':[0,0],
        'relaxation_access':['none','C','V','C+V'],
        'main_costs':{'each_policy_concession':1,'each_composition_clause_release':2},
        'budget_grid':list(range(9)),
        'cost_sensitivity':'Baseline profile; uniform policy costs1,2,3 crossed with uniform clause-release costs1,2,3; minimum cost recalculated, no utility estimation.',
        'profile_population':'All distinct eight-party seat vectors in results/interactions/seat-profiles.json; not independent elections.',
        'anonymous_capacity_sensitivity':'0..60 existing outsider No seats moved to abstention, full-policy strict clauses; no party-level mapping inferred.',
        'process_initial_policy_mask':7,
        'process_initial_formal_rejections':[0,2],
        'process_pressure':'None, or release C/V clause at an explicitly specified total formal rejection1..4 later than the initial counter, provided two synthetic release units available.',
        'process_formal_limit':'At most four TOTAL formal rejections. The fourth rejection terminates before a subsequent concession. The actual cutoff counter2 leaves at most two additional rejected proposals.',
        'process_patience':'Additional formal-vote horizons1..4 when starting0,1..2 when starting2.',
        'process_agendas':'Every8! cabinet order; exactly enumerated as1680 distinct first-four prefixes weighted4!. These counts are design coverage, not political probabilities.',
        'adaptive_control':'After the hypothetical clause release, search all eight proposals for an agreement before choosing the next formal proposal.',
        'null_controls':'Repeated unchanged proposals; exploratory-only evaluations never increase formal rejection counter; underfunded pressure does not relax a clause.',
        'process_terminal_categories':['agreement_found','pm_passed_without_cabinet_agreement','four_rejections','patience_exhausted'],
        'proposal_evaluation_unit':'One modeled proposal assessment, not one observed speaker exploratory mandate.',
        'diagnostics':'Enumerate all monotone-concession edges, recording No-count increases and agreement losses separately. Pivotality feedback was identified before the expanded run.',
        'source_scope':'Chronology and actor statements anchor questions only. Future candidate-specific PM and budget actions remain unknown in the documentary layer.',
        'development_status':'Retrospective specification, frozen before the expanded 26-profile/process run. Baseline unit examples and mathematical checks had already been inspected. Not a blind or prospective political registration.',
    }


def run_experiment(root=ROOT, output_dir=None, progress=None):
    root=Path(root).resolve()
    out=Path(output_dir).resolve() if output_dir else root/'results/bargaining'
    out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    frozen=root/'data/formation/bargaining-protocol.json'
    specification=protocol()
    if frozen.exists():
        if json.loads(frozen.read_text())['protocol']!=specification:
            raise ValueError('The bargaining protocol changed; create an explicit new version.')
    else:
        write(frozen,{'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'protocol':specification})
    profile_path=root/'results/interactions/seat-profiles.json'
    profiles=json.loads(profile_path.read_text())['profiles']
    events_path=root/'data/formation/events2026.json'
    events=json.loads(events_path.read_text())
    observed_rejections=sum(e['formal_rejection_count_delta'] for e in events['events'])
    if observed_rejections!=2:
        raise ValueError('The fixed22November source cutoff requires two observed formal rejections.')
    party_path=root/'data/elections/2026/parties.tsv'
    with party_path.open(newline='') as handle:
        baseline={r['label']:int(r['expected_total']) for r in csv.DictReader(handle,delimiter='\t') if int(r['expected_total'])}
    baseline_profile=next(p for p in profiles if p['seat_vector']==baseline)
    baseline_id=baseline_profile['profile_id']
    metadata=[]; all_reachability=[]; tensor_rows=[]; coupled=[]; capacity_rows=[]; diagnostic_rows=[]
    process_rows=[]; cache={}
    for position, profile in enumerate(profiles):
        pid=profile['profile_id']; seats=profile['seat_vector']
        left=sum(seats[p] for p in ('S','C','V','MP'))
        metadata.append({'profile_id':pid,'label':('Pinned2026 baseline' if pid==baseline_id else f'S/C/V/MP {left} seats; sampled cost {profile["minimum_sampled_cost"]:,}'),
            'seat_vector':seats,'S_C_V_MP_seats':left,'minimum_sampled_electorate_cost':profile['minimum_sampled_cost'],
            'source_coordinate_count':profile['coordinates'],'is_baseline':pid==baseline_id})
        for buffer in BUFFERS:
            lookup=proposal_lookup(seats,buffer)
            reach=reachability_rows(seats,buffer,pid)
            all_reachability.extend(reach)
            for state in states():
                for cabinet in range(8):
                    tensor_rows.append({'profile_id':pid,**lookup[state,cabinet]})
            for access in RELAXATION_ACCESS:
                selected=next(r for r in reach if r['initial_policy_mask']==0 and r['relaxation_access']==access and r['budget']==8)
                coupled.append({k:selected[k] for k in ('profile_id','external_buffer','relaxation_access','minimum_concession_cost','structural_possible')})
            no_increases=[]; agreement_losses=[]; total_edges=0
            for state in states():
                for terminal,cost,action in transitions(state):
                    for cabinet in range(8):
                        total_edges+=1
                        before,after=lookup[state,cabinet],lookup[terminal,cabinet]
                        witness={'from_state':list(state),'to_state':list(terminal),'cabinet_mask':cabinet,'action':action,
                                 'no_before':before['no'],'no_after':after['no'],'V_before':before['pm_roles']['V'],'V_after':after['pm_roles']['V']}
                        if after['no']>before['no']:
                            no_increases.append(witness)
                        if before['agreement'] and not after['agreement']:
                            agreement_losses.append(witness)
            diagnostic_rows.append({'profile_id':pid,'external_buffer':buffer,'proposal_edges':total_edges,
                'No_increasing_edges':len(no_increases),'agreement_losing_edges':len(agreement_losses),
                'No_increase_witnesses':no_increases,'agreement_loss_witnesses':agreement_losses})
            # Exact compression: process outcomes depend on these Boolean proposal
            # decisions, not the magnitude of No beyond its rejection threshold.
            signature=tuple((lookup[s,c]['agreement'],lookup[s,c]['pm_not_rejected'])
                            for s in ((7,0,0),(7,1,0),(7,0,1)) for c in range(8))
            for initial_counter in (0,2):
                pressure_options=[('none',1)]+[(clause,k) for clause in ('C','V') for k in range(initial_counter+1,5)]
                for clause,trigger in pressure_options:
                    for adaptive in (False,True):
                        for patience in range(1,5-initial_counter):
                            key=(signature,initial_counter,clause,trigger,adaptive,patience)
                            if key not in cache:
                                cache[key]=exhaustive_agendas(lookup,formal_limit=patience,pressure_clause=clause,
                                    pressure_trigger=trigger,adaptive_after_release=adaptive,initial_rejections=initial_counter)
                            counts=cache[key]
                            witnesses={}
                            for status,witness in counts['witnesses'].items():
                                order=witness['agenda_prefix']
                                outcome=simulate_agenda(lookup,order,formal_limit=patience,pressure_clause=clause,
                                    pressure_trigger=trigger,adaptive_after_release=adaptive,initial_rejections=initial_counter)
                                assert outcome['status']==status
                                witnesses[status]={'agenda_prefix':order,**outcome}
                            process_rows.append({'profile_id':pid,'external_buffer':buffer,
                                'initial_policy_mask':7,'initial_formal_rejections':initial_counter,
                                'remaining_institutional_attempts':4-initial_counter,
                                'pressure_clause':clause,'pressure_trigger_total_rejections':None if clause=='none' else trigger,
                                'release_budget':2,'additional_vote_patience':patience,
                                'adaptive_after_release':adaptive,'full_agenda_orders':40320,
                                'distinct_four_prefixes':1680,'outcome_counts':counts['outcome_counts'],
                                'formal_rejection_count_distribution':counts['formal_rejection_count_distribution'],
                                'witnesses':witnesses,'counts_are_probabilities':False})
        capacities=[]
        for capacity in range(61):
            cabinets=[c for c in range(8) if evaluate_proposal(seats,(7,0,0),c,external_weight=capacity)['agreement']]
            capacities.append({'anonymous_external_abstentions':capacity,'agreement_cabinet_masks':cabinets})
        capacity_rows.append({'profile_id':pid,'minimum_anonymous_external_capacity':next((r['anonymous_external_abstentions'] for r in capacities if r['agreement_cabinet_masks']),None),'cells':capacities})
        if progress:
            progress(f'Bargaining profile {position+1}/{len(profiles)} completed')
    baseline_lookup=proposal_lookup(baseline)
    sensitivity=[]
    for policy_cost in (1,2,3):
        for clause_cost in (1,2,3):
            for buffer in BUFFERS:
                lookup=proposal_lookup(baseline,buffer)
                agreements={s for s in states() if any(lookup[s,c]['agreement'] for c in range(8))}
                for initial_policy in range(8):
                    for access in RELAXATION_ACCESS:
                        distances,_=shortest_paths((initial_policy,0,0),access,(policy_cost,)*3,(clause_cost,)*2)
                        minimum=min((distances[s] for s in agreements if s in distances),default=None)
                        sensitivity.append({'policy_cost_each':policy_cost,'clause_cost_each':clause_cost,'external_buffer':buffer,
                            'initial_policy_mask':initial_policy,'relaxation_access':access,'minimum_concession_cost':minimum})
    baseline_rows=[r for r in all_reachability if r['profile_id']==baseline_id and r['initial_policy_mask']==0 and r['budget']==8]
    main_process=[r for r in process_rows if r['profile_id']==baseline_id and r['external_buffer']=='none' and r['additional_vote_patience']==4 and r['initial_formal_rejections']==0]
    cutoff_process=[r for r in process_rows if r['profile_id']==baseline_id and r['external_buffer']=='none' and r['additional_vote_patience']==2 and r['initial_formal_rejections']==2]
    diagnostics=[r for r in diagnostic_rows if r['profile_id']==baseline_id]
    feedback_example={'before':evaluate_proposal(baseline,(3,0,0),0),'after':evaluate_proposal(baseline,(7,0,0),0),
                      'scope':'Rule-derived diagnostic identified in development; not an observed party response.'}
    outputs={
        'feasibility-tensor.json':{'schema':'formation-tensor.bargaining-feasibility.v1','profile_count':len(profiles),'shape':[len(profiles),4,4,8,8],
            'axis_order':['exact_seat_profile','external_buffer','composition_relaxation_mask','policy_mask','cabinet_mask'],
            'rows':tensor_rows,'assumption_scope':specification['model']},
        'reachability.json':{'schema':'formation-tensor.bargaining-reachability.v1','baseline_profile_id':baseline_id,'profiles':metadata,
            'policy_bits':specification['policy_bits'],'rows':all_reachability,'costs':specification['main_costs'],
            'structural_definition':'Feasible under the selected permitted concession family with unrestricted budget.',
            'scope':specification['model']},
        'process.json':{'schema':'formation-tensor.sequential-proposals.v1','rows':process_rows,
            'initial_rejections_context':{'0':'Whole hypothetical episode','2':'As-of22November2026 institutional counter; not a forecast of its remaining proposals.'},
            'proposal_evaluations_are_speaker_mandates':False,'counts_are_probabilities':False,
            'scope':'Exhaustive synthetic agenda sensitivity under explicit institutional-pressure assumptions.'},
        'coupled-profiles.json':{'schema':'formation-tensor.coupled-bargaining.v1','profiles':metadata,'rows':coupled,
            'scope':'Distinct exact counterfactual seat profiles, not distinct observed elections.'},
        'capacity-sensitivity.json':{'schema':'formation-tensor.anonymous-abstention-capacity.v1','rows':capacity_rows,
            'scope':'Anonymous existing outsider seats; does not identify individual or party intentions.'},
        'cost-sensitivity.json':{'schema':'formation-tensor.concession-cost-sensitivity.v1','rows':sensitivity,
            'cost_unit':'Synthetic ordinal cost units; not measured bargaining utilities.'},
        'state-edge-diagnostics.json':{'schema':'formation-tensor.pivotality-feedback-diagnostics.v1','rows':diagnostic_rows,
            'baseline_example':feedback_example,'scope':'Deductive mechanism of the stated behavioural rules, not causal evidence.'},
        'summary.json':{'schema':'formation-tensor.bargaining-summary.v1','status':'passed','baseline_profile_id':baseline_id,
            'distinct_exact_seat_profiles':len(profiles),'proposal_tensor_coordinates':len(tensor_rows),
            'reachability_rows':len(all_reachability),'process_rows':len(process_rows),
            'unique_process_signature_cases_evaluated':len(cache),
            'observed_formal_rejections_at_cutoff':observed_rejections,'remaining_formal_attempts_at_cutoff':4-observed_rejections,
            'baseline_initial_policy000':baseline_rows,'baseline_full_episode_process':main_process,
            'baseline_cutoff_counter2_process':cutoff_process,
            'baseline_minimum_strict_anonymous_external_capacity':next(r['minimum_anonymous_external_capacity'] for r in capacity_rows if r['profile_id']==baseline_id),
            'baseline_state_edge_diagnostics':[{k:r[k] for k in ('external_buffer','proposal_edges','No_increasing_edges','agreement_losing_edges')} for r in diagnostics],
            'all_profile_agreement_losing_edges':sum(r['agreement_losing_edges'] for r in diagnostic_rows),
            'null_controls':{'unchanged_formal':simulate_agenda(baseline_lookup,[0]*4),
                'unchanged_exploratory':simulate_agenda(baseline_lookup,[0]*12,exploratory_only=True),
                'underfunded_pressure':simulate_agenda(baseline_lookup,[0,1,2,3],pressure_clause='C',release_budget=1)},
            'source_only_future_ballots':'Unknown; no source-only next-candidate probability or definitive vote imputed.',
            'scope':specification['model']},
    }
    reach_columns=['profile_id','external_buffer','initial_policy_mask','relaxation_access','budget',
                   'structural_possible','minimum_concession_cost','agreement_reachable','status']
    process_columns=['profile_id','external_buffer','initial_formal_rejections','remaining_institutional_attempts',
                     'pressure_clause','pressure_trigger_total_rejections','additional_vote_patience',
                     'adaptive_after_release','full_agenda_orders','outcome_counts']
    outputs['dashboard.json']={
        'schema':'formation-tensor.bargaining-dashboard.v1','baseline_profile_id':baseline_id,
        'profiles':metadata,'policy_bits':specification['policy_bits'],
        'reachability':{'columns':reach_columns,'rows':[[row[k] for k in reach_columns] for row in all_reachability]},
        'process':{'columns':process_columns,'rows':[[row[k] for k in process_columns] for row in process_rows],
                   'trace_rows':[row for row in process_rows if row['profile_id']==baseline_id and row['external_buffer']=='none']},
        'scope':specification['model'],
    }
    for filename,data in outputs.items():
        write(out/filename,data)
    process_csv=out/'process-counts.csv'
    keys=['profile_id','external_buffer','initial_formal_rejections','pressure_clause','pressure_trigger_total_rejections','additional_vote_patience','adaptive_after_release']
    statuses=['agreement_found','pm_passed_without_cabinet_agreement','four_rejections','patience_exhausted','agenda_exhausted']
    with process_csv.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys+statuses);writer.writeheader()
        for r in process_rows:
            writer.writerow({**{k:r[k] for k in keys},**{s:r['outcome_counts'].get(s,0) for s in statuses}})
    sources=[profile_path,events_path,root/'data/formation/source-ledger.json',party_path,frozen,
             root/'formation_tensor/bargaining.py',root/'tests/test_bargaining.py',root/'experiments/run_bargaining.py']
    test=subprocess.run([sys.executable,'-B','-m','unittest','tests.test_bargaining','-v'],cwd=root,capture_output=True,text=True)
    (out/'tests.txt').write_text(test.stdout+test.stderr)
    if test.returncode:
        raise RuntimeError('Bargaining tests failed.')
    write(out/'run.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-started,
        'protocol_sha256':sha(frozen),'input_sha256':{str(p.relative_to(root)):sha(p) for p in sources},
        'test_returncode':test.returncode,'test_count':13})
    members=sources+[out/name for name in outputs]+[process_csv,out/'tests.txt',out/'run.json']
    write(out/'manifest.json',{'schema':'formation-tensor.bargaining-manifest.v1','status':'passed',
        'files':{str(p.relative_to(root)):sha(p) for p in members},
        'protocol_sha256':sha(frozen)})
    return outputs['summary.json']


if __name__=='__main__':
    result=run_experiment(progress=lambda message:print(message,flush=True))
    print(json.dumps({k:result[k] for k in ('distinct_exact_seat_profiles','proposal_tensor_coordinates','reachability_rows','process_rows','baseline_minimum_strict_anonymous_external_capacity')},ensure_ascii=False))
