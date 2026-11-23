"""Evaluate retrospective policy-completion alternatives against the baseline."""
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from formation_tensor.completion_sensitivity import (
    ACCESS, BUFFERS, VARIANTS, agenda_counts, edge_diagnostics, evaluate,
    feasible_states, minimum_cost, states, subset_distances,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    options = {'ensure_ascii': False, 'allow_nan': False}
    options.update({'separators': (',', ':')} if compact else {'indent': 2})
    path.write_text(json.dumps(value, **options) + '\n')


def specification():
    return {
        'schema': 'formation-tensor.completion-protocol.v1',
        'design_status': 'Retrospective sensitivity specified after the original model and its outputs were examined. Not preregistered or a prospective political test.',
        'source_role': 'Conditional C/V statements motivate alternative predicates but do not uniquely identify future actions. These are explicit hypothetical completions.',
        'variants': {
            'baseline': 'The admitted original finite-state rules, reproduced independently with no change.',
            'strict_V_outside': 'If V policy is met but V is outside and its clause is active, V votes No even when nonpivotal; inclusion or release permits its admitted support.',
            'C_package_linked': 'C requires p_C AND p_V AND p_MP for policy assent and cabinet consent, in addition to the original composition condition. The linkage concerns exogenous policy-assent bits, not endogenous PM votes.',
            'both': 'Both alternative predicates together.',
        },
        'source_to_predicate': [
            {'actor': 'C', 'source': 'data/formation/source-ledger.json / C national statement,16 November2026',
             'source_content': 'C describes a social-democratic alternative, exclusion of V from cabinet, and V/MP backing the policy package.',
             'baseline_completion': 'Independent C policy bit; V and MP policy bits can vary independently.',
             'alternative_completion': 'C policy satisfaction also requires V and MP policy satisfaction; this deliberately does not equate those bits with recorded PM actions.'},
            {'actor': 'V', 'source': 'data/formation/source-ledger.json / 2026 preliminary platform',
             'source_content': 'Conditional participation demand when V votes are necessary; broader refusal wording does not uniquely specify all other cases.',
             'baseline_completion': 'With policy met, V abstains outside when nonpivotal, including hopeless proposals.',
             'alternative_completion': 'With active inclusion condition, V remains No outside even if nonpivotal.'},
        ],
        'unchanged': 'S-led eight-cabinet family;32 states;26 exact electoral profiles;four party buffers;349 seats;No>=175 rejects; cabinet consent distinct; budget support unfilled.',
        'costs': {'added_policy_bit': 1, 'released_composition_bit': 2},
        'unpriced_choices': 'Cabinet reconfiguration is free at a reached state; external abstention is an exogenous condition, not acquired within the concession cost.',
        'reachability': 'All eight initial policy masks with rigid clauses;four release families;budgets0..8. Independent monotone subset-cost enumeration.',
        'process': 'Pinned baseline seats and no outside buffer;all three policy bits met;C/Vrelease at total1..4 from counter0 or3..4 from counter2;fixed agendas and exhaustive re-search control;all8! full orders counted.',
        'scope': 'Sensitivity of declared conditional models, not an empirical causal validation, calibrated forecast, or automatic change to the production model.',
    }


def run_experiment(root=ROOT, output_dir=None, progress=None):
    root = Path(root).resolve()
    out = Path(output_dir).resolve() if output_dir else root / 'results/completion-sensitivity'
    out.mkdir(parents=True, exist_ok=True)
    protocol = root / 'data/formation/completion-protocol.json'
    expected = specification()
    if protocol.exists():
        if json.loads(protocol.read_text()) != expected:
            raise ValueError('Completion protocol changed; retain the old version and create an explicit new protocol.')
    else:
        write(protocol, expected)
    profile_path = root / 'results/interactions/seat-profiles.json'
    profiles = json.loads(profile_path.read_text())['profiles']
    baseline_summary_path = root / 'results/bargaining/summary.json'
    baseline_id = json.loads(baseline_summary_path.read_text())['baseline_profile_id']
    old_proposal_path = root / 'results/bargaining/feasibility-tensor.json'
    old_proposals = json.loads(old_proposal_path.read_text())['rows']
    old_lookup = {(r['profile_id'], r['external_buffer'], tuple(r['state']), r['cabinet_mask']):
                  {key: value for key, value in r.items() if key != 'profile_id'} for r in old_proposals}
    old_reach_path = root / 'results/bargaining/reachability.json'
    old_reach = json.loads(old_reach_path.read_text())['rows']
    old_reach_lookup = {(r['profile_id'], r['external_buffer'], r['initial_policy_mask'],
                         r['relaxation_access'], r['budget']): r for r in old_reach}
    minimum_columns = ['variant', 'profile_id', 'external_buffer', 'initial_policy_mask',
                       'relaxation_access', 'minimum_concession_cost', 'full_agreement_state_count']
    budget_columns = minimum_columns[:5] + ['budget', 'minimum_concession_cost',
        'structural_possible', 'agreement_reachable', 'reachable_states', 'reachable_agreement_states']
    minima = []; budgets = []; diagnostics = []; process_rows = []; baseline_witnesses = []
    variant_counts = {}; identity_proposals = identity_reach = 0
    proposal_total = 0
    archive_path = out / 'proposal-records.jsonl.gz'
    with archive_path.open('wb') as archive_file:
        with gzip.GzipFile(filename='', mode='wb', fileobj=archive_file, mtime=0) as archive:
            for variant in VARIANTS:
                diff = Counter(); no_external_possible = []; no_external_impossible = []
                baseline_costs = []; profile_costs = {buffer: Counter() for buffer in BUFFERS}
                totals = Counter(); feedback = None
                for profile in profiles:
                    pid, seats = profile['profile_id'], profile['seat_vector']
                    for buffer in BUFFERS:
                        lookup = {}
                        for state in states():
                            for cabinet in range(8):
                                row = evaluate(seats, state, cabinet, buffer, variant)
                                lookup[state, cabinet] = row
                                reference = old_lookup[pid, buffer, state, cabinet]
                                if variant == 'baseline':
                                    if row != reference:
                                        raise ValueError('Independent baseline proposal mismatch: ' + repr((pid, buffer, state, cabinet)))
                                    identity_proposals += 1
                                for field in ('no', 'pm_not_rejected', 'cabinet_consented', 'agreement'):
                                    diff[field] += int(row[field] != reference[field])
                                payload = {'variant': variant, 'profile_id': pid, **row}
                                archive.write((json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
                                proposal_total += 1
                        agreements = feasible_states(lookup)
                        for initial in range(8):
                            for access in ACCESS:
                                minimum, witnesses = minimum_cost(lookup, initial, access)
                                minima.append([variant, pid, buffer, initial, access, minimum, len(agreements)])
                                distances = subset_distances(initial, access)
                                for budget in range(9):
                                    reached = [s for s, cost in distances.items() if cost <= budget]
                                    reached_agreements = [s for s in reached if s in agreements]
                                    budgets.append([variant, pid, buffer, initial, access, budget, minimum,
                                        minimum is not None, bool(reached_agreements), len(reached), len(reached_agreements)])
                                    if variant == 'baseline':
                                        old = old_reach_lookup[pid, buffer, initial, access, budget]
                                        actual = (minimum, minimum is not None, bool(reached_agreements), len(reached), len(reached_agreements))
                                        prior = tuple(old[key] for key in ('minimum_concession_cost', 'structural_possible', 'agreement_reachable', 'reachable_states', 'reachable_agreement_states'))
                                        if actual != prior:
                                            raise ValueError('Independent baseline reachability mismatch: ' + repr((pid, buffer, initial, access, budget)))
                                        identity_reach += 1
                                if initial == 0:
                                    if pid == baseline_id:
                                        entry = dict(zip(minimum_columns, minima[-1]))
                                        baseline_costs.append(entry)
                                        baseline_witnesses.append({**entry, 'minimum_witnesses': witnesses})
                                    if access == 'C+V':
                                        profile_costs[buffer][str(minimum)] += 1
                                        if buffer == 'none':
                                            (no_external_possible if minimum is not None else no_external_impossible).append(pid)
                        edge_counts, witness = edge_diagnostics(lookup)
                        totals.update(edge_counts)
                        diagnostics.append({'variant': variant, 'profile_id': pid, 'external_buffer': buffer,
                                            **edge_counts, 'first_witnesses': witness})
                        if pid == baseline_id and buffer == 'none':
                            feedback = {'before': lookup[(3, 0, 0), 0], 'after': lookup[(7, 0, 0), 0],
                                        'interpretation': 'S-only cabinet, MP policy-assent addition; a declared-rule comparison, not an observed party response.'}
                            for initial_counter in (0, 2):
                                for clause in ('C', 'V'):
                                    for trigger in range(initial_counter + 1, 5):
                                        for oracle in (False, True):
                                            process_rows.append({'variant': variant, 'initial_formal_rejections': initial_counter,
                                                'release_clause': clause, 'release_trigger_total': trigger,
                                                'exhaustive_research_oracle': oracle,
                                                **agenda_counts(lookup, initial_counter, clause, trigger, oracle)})
                    if progress:
                        progress(variant + ': profile ' + pid + ' complete')
                variant_counts[variant] = {'proposal_coordinates': len(profiles) * 4 * 32 * 8,
                    'differences_from_baseline': dict(diff), 'all_profile_edge_diagnostics': dict(totals),
                    'no_external_tolerance_with_all_permitted_internal_concessions': {
                        'possible_profile_count': len(no_external_possible), 'impossible_profile_count': len(no_external_impossible),
                        'possible_profile_ids': no_external_possible, 'impossible_profile_ids': no_external_impossible},
                    'baseline_policy000_costs': baseline_costs,
                    'all_profile_policy000_minimum_cost_distribution': {key: dict(sorted(value.items())) for key, value in profile_costs.items()},
                    'baseline_feedback_example': feedback}
    if identity_proposals != 26624 or identity_reach != 29952:
        raise ValueError('Baseline identity audit did not cover the full original domain.')
    summary = {'schema': 'formation-tensor.completion-sensitivity-summary.v1', 'status': 'passed',
        'design_status': expected['design_status'], 'distinct_seat_profiles': len(profiles),
        'baseline_profile_id': baseline_id, 'completion_variants': list(VARIANTS),
        'proposal_evaluations': proposal_total, 'minimum_cost_rows': len(minima), 'budget_reachability_rows': len(budgets),
        'process_scenario_rows': len(process_rows), 'baseline_identity': {'proposal_records': identity_proposals,
            'reachability_records': identity_reach, 'proposal_mismatches': 0, 'reachability_mismatches': 0},
        'variants': variant_counts,
        'scope': expected['scope']}
    write(out / 'summary.json', summary)
    write(out / 'minimum-costs.json', {'columns': minimum_columns, 'rows': minima}, compact=True)
    write(out / 'reachability.json', {'columns': budget_columns, 'rows': budgets}, compact=True)
    write(out / 'diagnostics.json', {'rows': diagnostics, 'baseline_minimum_witnesses': baseline_witnesses})
    write(out / 'process.json', {'rows': process_rows, 'scope': 'Pinned baseline seats, no external tolerance, full policy assent; exact agenda counts, not political probabilities.'})
    with (out / 'minimum-costs.csv').open('w', newline='') as handle:
        writer = csv.writer(handle); writer.writerow(minimum_columns); writer.writerows(minima)
    headline_columns = ['variant', 'proposal_coordinates', 'no_external_possible_profiles',
        'no_external_impossible_profiles', 'baseline_cost_none', 'baseline_cost_L',
        'baseline_cost_KD', 'baseline_cost_L_plus_KD', 'No_increasing_edges',
        'agreement_losing_edges', 'agreement_coordinates_changed', 'feedback_no_before', 'feedback_no_after']
    with (out / 'completion-summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=headline_columns); writer.writeheader()
        for variant, result in variant_counts.items():
            cost = {row['external_buffer']: row['minimum_concession_cost']
                    for row in result['baseline_policy000_costs'] if row['relaxation_access'] == 'C+V'}
            viability = result['no_external_tolerance_with_all_permitted_internal_concessions']
            writer.writerow({'variant': variant, 'proposal_coordinates': result['proposal_coordinates'],
                'no_external_possible_profiles': viability['possible_profile_count'],
                'no_external_impossible_profiles': viability['impossible_profile_count'],
                'baseline_cost_none': cost['none'], 'baseline_cost_L': cost['L'],
                'baseline_cost_KD': cost['KD'], 'baseline_cost_L_plus_KD': cost['L+KD'],
                'No_increasing_edges': result['all_profile_edge_diagnostics']['No_increasing_edges'],
                'agreement_losing_edges': result['all_profile_edge_diagnostics']['agreement_losing_edges'],
                'agreement_coordinates_changed': result['differences_from_baseline']['agreement'],
                'feedback_no_before': result['baseline_feedback_example']['before']['no'],
                'feedback_no_after': result['baseline_feedback_example']['after']['no']})
    process_columns = ['variant', 'initial_formal_rejections', 'release_clause',
        'release_trigger_total', 'exhaustive_research_oracle', 'agreement_found',
        'pm_passed_without_cabinet_agreement', 'four_rejections', 'agenda_exhausted']
    with (out / 'process-counts.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=process_columns); writer.writeheader()
        for row in process_rows:
            writer.writerow({**{key: row[key] for key in process_columns[:5]},
                             **{key: row['outcome_counts'].get(key, 0) for key in process_columns[5:]}})
    (out / 'README.md').write_text('''# Assumption-completion sensitivity

This is a separate retrospective sensitivity experiment. It leaves the original bargaining
rules and their stored results unchanged. It evaluates two explicit alternatives
to predicates that were not uniquely identified by the documentary record.

1. **Strict V outside rule:** an active inclusion demand leads to No outside the
   cabinet even when V is nonpivotal. Inclusion or the V release permits support.
2. **C package linkage:** C requires its own policy bit and both V/MP policy bits
   before its policy condition is met. These are exogenous policy conditions,
   not V/MP's endogenous prime-minister votes. There is no evaluation-order cycle.

The four completions are the original baseline, each alternative separately,
and both together. All preserve the cabinet family, chamber, costs and outside
buffers. Cabinet changes remain unpriced and outside tolerance remains exogenous.

## Executed domain

- 106,496 proposal evaluations: four completions, 26 exact seat profiles, four
  buffers, 32 states and eight cabinet compositions.
- 13,312 minimum-cost settings and 119,808 budget-specific reachability rows.
- 96 full-policy baseline agenda scenarios, each covering all 40,320 orders.
- Independent evaluator matches all 26,624 original proposal records field for
  field; independent subset-cost enumeration matches all 29,952 reachability
  records. Both baseline mismatch counts are zero.

## Results

| Completion | None | L | KD | L+KD | No-increasing edges |
|---|---:|---:|---:|---:|---:|
| Original baseline | 5 | 5 | 4 | 2 | 1,424 |
| Strict V outside | 5 | 5 | 4 | 2 | 0 |
| C package linked | 5 | 5 | 5 | 2 | 712 |
| Both | 5 | 5 | 5 | 2 | 0 |

Costs start at policy state 000, permit both composition releases, and use the
baseline seat vector. They do not price obtaining outside abstention. Each edge
count covers 66,560 fixed-cabinet state edges across the 26 profiles and buffers.
No completion has an agreement-losing edge.

All four completions preserve the split of 11 profiles admitting an internal
route and 15 requiring an outside non-No action. With the linked C requirement,
KD's minimum becomes five in every profile; originally it was four in 22 profiles
and five in four. The L+KD two-unit route survives because another acceptable
cabinet can be chosen; a specific original cabinet need not remain acceptable.

The stricter V completion changes 2,232 proposal No counts but no agreement,
consent or nonrejection predicate. When V was pivotal it already voted No; when
V was hopeless the proposal already failed; when V was redundant, the others
already supplied at least 175 non-No seats. The original feedback witness changes
from 195 to 203 No votes; its corresponding strict-V witness is 225 to 203.
With linked C it is 220 to 203, and with both alternatives 250 to 203.

The C linkage changes 800 agreement coordinates, 1,392 numerical nonrejection
coordinates and 1,872 cabinet-consent coordinates. The unchanged 11/15 profile
boundary therefore does not mean that every proposal remains unchanged.

The full-policy, no-buffer agenda experiment is unchanged in all four variants:
fixed-agenda agreements after release at total rejection 1/2/3/4 are
37,440 / 31,680 / 20,160 / 0 of 40,320. Starting at counter two, release at total
three yields 20,160 fixed-agenda agreements; an exhaustive re-search oracle
yields 40,320. Release after total four is too late in either case.

## Files and execution

`summary.json` and `completion-summary.csv` contain the headline results.
`minimum-costs.json` and `reachability.json` use explicit column schemas.
`diagnostics.json` retains edge and minimum-cost witnesses. Every evaluated
proposal is retained in deterministic `proposal-records.jsonl.gz`.
`process.json` and `process-counts.csv` retain agenda outcomes and witnesses.

From the repository root:

```sh
python3 -B -m unittest tests.test_completion_sensitivity -v
python3 -B experiments/run_completion_sensitivity.py
```

The experiment uses only Python standard libraries. It requires the existing
electoral profiles and original bargaining outputs for its full baseline audit.
It must therefore run after those experiments in a fresh reproduction directory.
The manifest binds the admitted inputs, implementation, tests and outputs.
The design is retrospective and conditional; it is not a political prediction or
an empirical validation of either completion.
''')
    sources = [profile_path, baseline_summary_path, old_proposal_path, old_reach_path, protocol,
        root / 'data/formation/bargaining-protocol.json', root / 'data/formation/source-ledger.json',
        root / 'formation_tensor/completion_sensitivity.py', root / 'experiments/run_completion_sensitivity.py',
        root / 'tests/test_completion_sensitivity.py']
    outputs = [out / name for name in ('summary.json', 'minimum-costs.json', 'reachability.json',
        'diagnostics.json', 'process.json', 'minimum-costs.csv', 'completion-summary.csv',
        'process-counts.csv', 'proposal-records.jsonl.gz', 'README.md')]
    write(out / 'manifest.json', {'schema': 'formation-tensor.completion-sensitivity-manifest.v1', 'status': 'passed',
        'files': {p.relative_to(root).as_posix(): sha(p) for p in sources + outputs},
        'design_status': expected['design_status'], 'production_rules_modified': False})
    return summary


if __name__ == '__main__':
    result = run_experiment()
    print(json.dumps({key: result[key] for key in ('status', 'proposal_evaluations', 'minimum_cost_rows', 'budget_reachability_rows', 'baseline_identity')}))
