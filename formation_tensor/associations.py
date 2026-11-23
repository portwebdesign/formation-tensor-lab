"""Retrospective all-pair vote association with explicit agenda/margin controls.

References are descriptive. Neither resampling nor conditioning establishes a
causal political mechanism, independent political events or cabinet consent.
"""
from collections import Counter, defaultdict
from itertools import combinations
import math
import random

PARTIES = ['S', 'M', 'SD', 'C', 'KD', 'MP', 'V', 'L']
SESSIONS = ['2022/23', '2023/24', '2024/25', '2025/26']
ACTIONS = ['yes', 'no', 'abstain']
DISCOVERY = SESSIONS[:2]
REPLAY = SESSIONS[2:]


def mode(counts):
    """Unique participating-action mode; absences never become a preference."""
    if len(counts) != 4 or any(type(v) is not int or v < 0 for v in counts):
        raise ValueError('Four nonnegative integer action counts required.')
    largest = max(counts[:3])
    return counts[:3].index(largest) if largest and counts[:3].count(largest) == 1 else None


def near_unanimous(row):
    total = [sum(v[k] for v in row['party_counts'].values()) for k in range(3)]
    return bool(sum(total)) and 40 * max(total) >= 39 * sum(total)


def pair_rows(records, pair, exclude_near_unanimous=False):
    rows = []
    for r in records:
        if exclude_near_unanimous and near_unanimous(r):
            continue
        a, b = [mode(r['party_counts'][p]) for p in pair]
        if a is None or b is None:
            continue
        rows.append({'a': a, 'b': b, 'session': r['session'],
                     'committee': r['committee'],
                     'report': r['session'] + '|' + (r.get('beteckning') or r['id']),
                     'id': r['id']})
    return rows


def blocks(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['session'], row['committee'], row['report'])].append(row)
    result = []
    for (session, committee, report), values in sorted(grouped.items()):
        matrix = [[0] * 3 for _ in range(3)]
        for r in values:
            matrix[r['a']][r['b']] += 1
        result.append({'session': session, 'committee': committee,
                       'report': report, 'n': len(values), 'matrix': matrix})
    return result


def matrix_statistics(grouped_matrices):
    """Condition on session/committee with exactly the displayed weighting."""
    total = sum(sum(sum(row) for row in m) for m in grouped_matrices.values())
    if total <= 0:
        return {'status': 'unavailable', 'observed_agreement': None,
                'conditional_reference': None, 'excess_agreement_pp': None,
                'conditional_kappa': None, 'effective_weight': 0,
                'conditional_strata': 0, 'weighted_contingency': [[0]*3 for _ in range(3)],
                'dominant_disagreement': None}
    observed = expected = 0.0
    all_matrix = [[0.0] * 3 for _ in range(3)]
    for matrix in grouped_matrices.values():
        n = sum(sum(row) for row in matrix)
        observed += sum(matrix[k][k] for k in range(3))
        am = [sum(row) for row in matrix]
        bm = [sum(matrix[a][b] for a in range(3)) for b in range(3)]
        expected += sum(am[k] * bm[k] for k in range(3)) / n
        for a in range(3):
            for b in range(3):
                all_matrix[a][b] += matrix[a][b]
    observed /= total
    expected /= total
    residual = observed - expected
    if abs(residual) < 1e-12:
        residual = 0.0
    off = [(all_matrix[a][b], a, b) for a in range(3) for b in range(3) if a != b]
    n, a, b = max(off)
    return {'status': 'passed', 'observed_agreement': observed,
            'conditional_reference': expected, 'excess_agreement_pp': 100*residual,
            'conditional_kappa': residual/(1-expected) if 1-expected > 1e-12 else None,
            'effective_weight': total, 'conditional_strata': len(grouped_matrices),
            'weighted_contingency': all_matrix,
            'dominant_disagreement': {'first_party_action': ACTIONS[a],
                                      'second_party_action': ACTIONS[b],
                                      'weight': n} if n > 0 else None}


def block_statistics(items, weighting='report_equal'):
    if weighting not in ['report_equal', 'rollcall_equal']:
        raise ValueError('Unknown weighting.')
    matrices = {}
    for block in items:
        key = block['session'], block['committee']
        if key not in matrices:
            matrices[key] = [[0.0] * 3 for _ in range(3)]
        factor = 1/block['n'] if weighting == 'report_equal' else 1.0
        for a in range(3):
            for b in range(3):
                matrices[key][a][b] += factor * block['matrix'][a][b]
    return matrix_statistics(matrices)


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    loc = (len(values)-1)*fraction
    i = int(loc)
    j = min(i+1, len(values)-1)
    return values[i] + (values[j]-values[i])*(loc-i)


def resampling_range(items, replicates=200, seed=20261122):
    if type(replicates) is not int or replicates < 1:
        raise ValueError('Positive bootstrap replicate count required.')
    if not items:
        return {'status': 'unavailable', 'replicates': 0, 'excess_pp_percentiles': None}
    strata = defaultdict(list)
    for item in items:
        strata[(item['session'], item['committee'])].append(item)
    rng = random.Random(seed)
    results = []
    for _ in range(replicates):
        sampled = []
        for values in strata.values():
            sampled.extend(rng.choices(values, k=len(values)))
        results.append(block_statistics(sampled)['excess_agreement_pp'])
    return {'status': 'computed', 'replicates': replicates, 'seed': seed,
            'sampling_unit': 'report within session × committee; all common votes in a selected report stay together',
            'weighting': 'each sampled report occurrence has unit weight',
            'excess_pp_percentiles': [percentile(results, .025), percentile(results, .975)],
            'interpretation': 'Descriptive resampling stability range; not population confidence interval, p-value, independent replication or causal evidence.'}


def analyze_pair(records, pair, bootstrap=0, seed=20261122, controls=True):
    usable = pair_rows(records, pair)
    items = blocks(usable)
    primary = block_statistics(items)
    raw = block_statistics(items, 'rollcall_equal')
    contingency = [[0]*3 for _ in range(3)]
    for row in usable:
        contingency[row['a']][row['b']] += 1
    result = {'parties': list(pair), 'pair_id': '—'.join(pair),
              'common_rollcalls': len(usable), 'excluded_missing_or_tied_modes': len(records)-len(usable),
              'reports': len(items), 'selected_records': len(records),
              'committees': len({r['committee'] for r in usable}),
              'report_equal': primary, 'rollcall_equal': raw,
              'contingency_action_order': ACTIONS,
              'raw_contingency': contingency,
              'first_party_action_counts': [sum(row) for row in contingency],
              'second_party_action_counts': [sum(contingency[a][b] for a in range(3)) for b in range(3)]}
    if bootstrap:
        result['report_cluster_resampling'] = resampling_range(items, bootstrap, seed)
    if controls:
        trimmed = pair_rows(records, pair, True)
        result['exclude_near_unanimous'] = {
            'threshold': .975, 'common_rollcalls': len(trimmed),
            'removed_common_rollcalls': len(usable)-len(trimmed),
            'report_equal': block_statistics(blocks(trimmed))}
        drop = []
        for committee in sorted({b['committee'] for b in items}):
            remaining = [b for b in items if b['committee'] != committee]
            stat = block_statistics(remaining)
            drop.append({'excluded_committee': committee, 'reports_remaining': len(remaining),
                         'excess_agreement_pp': stat['excess_agreement_pp']})
        known = [r['excess_agreement_pp'] for r in drop if r['excess_agreement_pp'] is not None]
        result['leave_one_committee_out'] = {'rows': drop,
            'excess_pp_range': [min(known), max(known)] if known else None}
    return result


def discovery_candidates(records, top=3, bootstrap=200, seed=20261122):
    if any(r['session'] not in DISCOVERY for r in records):
        raise ValueError('Discovery function cannot read later-session records.')
    pairs = [analyze_pair(records, pair, bootstrap, seed+i) for i,pair in enumerate(combinations(PARTIES,2))]
    eligible = [r for r in pairs if r['common_rollcalls'] >= 40 and r['reports'] >= 10
                and r['report_equal']['conditional_kappa'] is not None]
    positive = sorted([r for r in eligible if r['report_equal']['excess_agreement_pp'] > 0],
                      key=lambda r: (-r['report_equal']['excess_agreement_pp'], r['pair_id']))[:top]
    negative = sorted([r for r in eligible if r['report_equal']['excess_agreement_pp'] < 0],
                      key=lambda r: (r['report_equal']['excess_agreement_pp'], r['pair_id']))[:top]
    return {'discovery_sessions': DISCOVERY, 'all_pairs': pairs,
            'selection': [{'pair_id': r['pair_id'], 'parties': r['parties'],
                           'direction': direction,
                           'excess_agreement_pp': r['report_equal']['excess_agreement_pp'],
                           'common_rollcalls': r['common_rollcalls'], 'reports': r['reports']}
                          for direction, rows in [('positive', positive), ('negative', negative)] for r in rows],
            'selection_rule': 'top 3 positive and top 3 negative report-equal conditional excess among pairs with ≥40 common votes, ≥10 reports and defined kappa; ties by pair ID',
            'eligible_pairs': len(eligible)}


def replay_candidates(records, selection, bootstrap=200, seed=20261122):
    if any(r['session'] not in REPLAY for r in records):
        raise ValueError('Replay function expects only declared later sessions.')
    result = []
    for i, candidate in enumerate(selection):
        periods = []
        for j, session in enumerate(REPLAY):
            analysis = analyze_pair([r for r in records if r['session'] == session],
                                    candidate['parties'], bootstrap, seed+i*10+j)
            excess = analysis['report_equal']['excess_agreement_pp']
            direction = 1 if candidate['direction'] == 'positive' else -1
            stability = analysis['report_cluster_resampling']['excess_pp_percentiles']
            periods.append({'session': session, 'analysis': analysis,
                'same_direction_as_discovery': bool(excess is not None and direction*excess > 0),
                'resampling_range_excludes_zero_in_selected_direction': bool(stability and
                    (stability[0] > 0 if direction == 1 else stability[1] < 0))})
        result.append({'selected_candidate': candidate, 'periods': periods,
                       'same_direction_both_periods': all(p['same_direction_as_discovery'] for p in periods)})
    return {'status': 'retrospective_fixed_candidate_replay', 'candidates': result,
            'interpretation': 'Previously inspected public outcomes, not blind or prospective evaluation. Pair selection uses only the declared first two sessions; no re-ranking in replay.'}


def descriptive_inventory(records):
    """Full pairs/committees remain visible rather than only selected successes."""
    pair_ids = list(combinations(PARTIES, 2))
    periods = []
    for session in SESSIONS:
        subset = [r for r in records if r['session'] == session]
        periods.append({'session': session, 'rollcalls': len(subset),
                        'pairs': [analyze_pair(subset,pair,controls=False) for pair in pair_ids]})
    committees = []
    for committee in sorted({r['committee'] for r in records}):
        subset = [r for r in records if r['committee'] == committee]
        pairs = [analyze_pair(subset,pair,controls=False) for pair in pair_ids]
        eligible = [p for p in pairs if p['common_rollcalls'] >= 40 and p['reports'] >= 10
                    and p['report_equal']['conditional_kappa'] is not None]
        committees.append({'committee': committee, 'rollcalls': len(subset),
            'reports': len({(r['session'],r.get('beteckning') or r['id']) for r in subset}),
            'pairs': pairs,
            'descriptive_positive_ranking': [p['pair_id'] for p in sorted(
                [p for p in eligible if p['report_equal']['excess_agreement_pp'] > 0],
                key=lambda p:(-p['report_equal']['excess_agreement_pp'],p['pair_id']))],
            'descriptive_negative_ranking': [p['pair_id'] for p in sorted(
                [p for p in eligible if p['report_equal']['excess_agreement_pp'] < 0],
                key=lambda p:(p['report_equal']['excess_agreement_pp'],p['pair_id']))],
            'period_coverage': dict(Counter(r['session'] for r in subset))})
    return {'periods': periods, 'committees': committees,
            'all_pairs_pooled': [analyze_pair(records,pair) for pair in pair_ids],
            'role': 'Descriptive inventory, not additional selected validation or independent event counts.'}
