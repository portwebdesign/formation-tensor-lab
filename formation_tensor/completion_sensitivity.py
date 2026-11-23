"""Retrospective sensitivity to two explicitly completed bargaining predicates.

This module does not change the original bargaining model.  It supplies a
separate evaluator and an acyclic subset-cost oracle so that the consequences
of alternative completions can be compared with the recorded baseline.
"""
from collections import Counter
from itertools import permutations

PARTIES = ('S', 'M', 'SD', 'V', 'C', 'KD', 'MP', 'L')
CORE = ('C', 'V', 'MP')
BUFFERS = {'none': (), 'L': ('L',), 'KD': ('KD',), 'L+KD': ('L', 'KD')}
ACCESS = {'none': 0, 'C': 1, 'V': 2, 'C+V': 3}
VARIANTS = {
    'baseline': (False, False),
    'strict_V_outside': (True, False),
    'C_package_linked': (False, True),
    'both': (True, True),
}


def checked(seats, state, cabinet, buffer, variant):
    if set(seats) != set(PARTIES) or any(type(v) is not int or v < 0 for v in seats.values()) or sum(seats.values()) != 349:
        raise ValueError('Eight nonnegative integer seat counts summing to 349 are required.')
    if (len(state) != 3 or any(type(v) is not int for v in state)
            or not 0 <= state[0] < 8 or state[1] not in (0, 1) or state[2] not in (0, 1)):
        raise ValueError('State must be (policy mask0..7, C release0/1, V release0/1).')
    if type(cabinet) is not int or not 0 <= cabinet < 8:
        raise ValueError('Cabinet index must be 0..7.')
    if buffer not in BUFFERS or variant not in VARIANTS:
        raise ValueError('Unknown outside buffer or completion variant.')


def states():
    return [(p, c, v) for c in (0, 1) for v in (0, 1) for p in range(8)]


def members(cabinet):
    return ['S'] + [party for bit, party in enumerate(CORE) if cabinet & (1 << bit)]


def evaluate(seats, state, cabinet, buffer='none', variant='baseline'):
    """Return party actions and consent under one declared completion.

    C's package-linked alternative requires all three policy-assent bits.
    These are exogenous package conditions, not endogenous votes by V or MP.
    The V alternative requires inclusion or a V-clause release even when V is
    not pivotal.  Neither alternative is claimed as a uniquely sourced action.
    """
    checked(seats, state, cabinet, buffer, variant)
    strict_v, linked_c = VARIANTS[variant]
    policy, release_c, release_v = state
    cabinet_parties = members(cabinet)
    raw_assent = {party: bool(policy & (1 << bit)) for bit, party in enumerate(CORE)}
    c_assent = raw_assent['C'] and (not linked_c or (raw_assent['V'] and raw_assent['MP']))
    c_composition = 'V' not in cabinet_parties or bool(release_c)
    actions = {party: 'no' for party in PARTIES}
    actions['S'] = 'yes'
    if c_assent and c_composition:
        actions['C'] = 'yes' if 'C' in cabinet_parties else 'abstain'
    if raw_assent['MP']:
        actions['MP'] = 'yes' if 'MP' in cabinet_parties else 'abstain'
    for party in BUFFERS[buffer]:
        actions[party] = 'abstain'
    others = sum(seats[party] for party in PARTIES if party != 'V' and actions[party] != 'no')
    pivotal_v = others < 175 <= others + seats['V']
    inclusion_ok = ('V' in cabinet_parties or bool(release_v)
                    or (not strict_v and not pivotal_v))
    if raw_assent['V'] and inclusion_ok:
        actions['V'] = 'yes' if 'V' in cabinet_parties else 'abstain'
    consent = {'S': True}
    for party in cabinet_parties[1:]:
        consent[party] = c_assent and c_composition if party == 'C' else raw_assent[party]
    counts = {action: sum(seats[party] for party in PARTIES if actions[party] == action)
              for action in ('yes', 'no', 'abstain')}
    assert sum(counts.values()) == 349
    cabinet_consented = all(consent.values())
    nonrejection = counts['no'] < 175
    blocking = []
    for party in CORE:
        if not raw_assent[party]:
            blocking.append(party + '_policy_requirement')
    if not c_composition:
        blocking.append('C_composition_condition')
    if raw_assent['V'] and not inclusion_ok:
        blocking.append('V_essential_inclusion_condition' if not strict_v else 'V_outside_inclusion_condition')
    if linked_c and raw_assent['C'] and not c_assent:
        blocking.append('C_linked_package_requirement')
    # The baseline record deliberately has the same schema as the admitted
    # original output, allowing field-for-field identity checks.
    return {
        'state': list(state), 'cabinet_mask': cabinet,
        'cabinet_members': cabinet_parties, 'external_buffer': buffer,
        'anonymous_external_seats': None, 'pm_roles': actions,
        'roles_before_anonymous_adjustment': None,
        **counts, 'v_essential_holding_others_fixed': pivotal_v,
        'cabinet_consent': consent, 'cabinet_consented': cabinet_consented,
        'pm_not_rejected': nonrejection,
        'agreement': cabinet_consented and nonrejection,
        'budget_support': 'not_modelled', 'active_clause_diagnostics': blocking,
    }


def subset_distances(initial_policy, access='C+V'):
    """Independent cost oracle; state bits can only be added, never removed.

    Cabinet changes are freely available at a reached state.  Only the added
    policy bits and permitted clause releases carry the declared cost index.
    """
    if type(initial_policy) is not int or not 0 <= initial_policy < 8 or access not in ACCESS:
        raise ValueError('Invalid initial policy mask or release family.')
    allowed = ACCESS[access]
    output = {}
    for p, c, v in states():
        if p & initial_policy != initial_policy or (c and not allowed & 1) or (v and not allowed & 2):
            continue
        output[p, c, v] = bin(p ^ initial_policy).count('1') + 2 * (c + v)
    return output


def feasible_states(lookup):
    return {state for state in states() if any(lookup[state, cabinet]['agreement'] for cabinet in range(8))}


def minimum_cost(lookup, initial_policy, access='C+V'):
    distances = subset_distances(initial_policy, access)
    candidates = [(distances[state], state) for state in feasible_states(lookup) if state in distances]
    if not candidates:
        return None, []
    cost = min(value for value, _ in candidates)
    witnesses = [
        {'state': list(state), 'cabinet_masks': [cabinet for cabinet in range(8) if lookup[state, cabinet]['agreement']]}
        for value, state in sorted(candidates) if value == cost
    ]
    return cost, witnesses


def edges():
    for state in states():
        policy, c, v = state
        for bit in range(3):
            if not policy & (1 << bit):
                yield state, (policy | (1 << bit), c, v), 'meet_' + CORE[bit] + '_policy'
        if not c:
            yield state, (policy, 1, v), 'release_C_composition'
        if not v:
            yield state, (policy, c, 1), 'release_V_inclusion'


def edge_diagnostics(lookup):
    counts = Counter()
    witness = {}
    for before, after, action in edges():
        for cabinet in range(8):
            left, right = lookup[before, cabinet], lookup[after, cabinet]
            counts['proposal_edges'] += 1
            for name, active in (
                ('No_increasing_edges', right['no'] > left['no']),
                ('agreement_losing_edges', left['agreement'] and not right['agreement']),
            ):
                if active:
                    counts[name] += 1
                    witness.setdefault(name, {'from_state': list(before), 'to_state': list(after),
                        'cabinet_mask': cabinet, 'action': action, 'no_before': left['no'],
                        'no_after': right['no'], 'agreement_before': left['agreement'],
                        'agreement_after': right['agreement']})
    return {key: counts[key] for key in ('proposal_edges', 'No_increasing_edges', 'agreement_losing_edges')}, witness


def agenda_counts(lookup, initial_rejections=0, release_clause='V', release_trigger=1, oracle=False):
    """Independent baseline full-policy agenda enumeration, with 4! compression."""
    if initial_rejections not in (0, 2) or release_clause not in ('none', 'C', 'V'):
        raise ValueError('Invalid process variant.')
    if release_clause != 'none' and not initial_rejections < release_trigger <= 4:
        raise ValueError('Release must follow the starting rejection counter.')
    totals = Counter()
    witnesses = {}
    for prefix in permutations(range(8), 4):
        state = (7, 0, 0)
        rejected = initial_rejections
        released = False
        trace = []
        for cabinet in prefix:
            if released and oracle:
                cabinet = next((c for c in range(8) if lookup[state, c]['agreement']), cabinet)
            proposal = lookup[state, cabinet]
            trace.append({'state': list(state), 'cabinet_mask': cabinet, 'no': proposal['no'],
                          'cabinet_consented': proposal['cabinet_consented'], 'rejections_before': rejected})
            if proposal['agreement']:
                outcome = 'agreement_found'
                break
            if proposal['pm_not_rejected']:
                outcome = 'pm_passed_without_cabinet_agreement'
                break
            rejected += 1
            if rejected == 4:
                outcome = 'four_rejections'
                break
            if not released and release_clause != 'none' and rejected >= release_trigger:
                state = (7, int(release_clause == 'C'), int(release_clause == 'V'))
                released = True
        else:
            outcome = 'agenda_exhausted'
        totals[outcome] += 24
        witnesses.setdefault(outcome, {'agenda_prefix': list(prefix), 'trace': trace})
    assert sum(totals.values()) == 40320
    return {'full_agenda_orders': 40320, 'outcome_counts': dict(sorted(totals.items())), 'witnesses': witnesses}
