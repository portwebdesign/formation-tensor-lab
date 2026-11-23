"""Finite-state, source-inspired bargaining scenarios with exact state enumeration.

The rules below are experimental assumptions. They are not admitted predictions
of party behaviour. Cabinet consent, the prime-minister ballot and budget support
are distinct objects. No utility or political probability is estimated.
"""
from collections import Counter
from heapq import heappop, heappush
from itertools import permutations

PARTIES = ('S', 'M', 'SD', 'V', 'C', 'KD', 'MP', 'L')
CORE = ('C', 'V', 'MP')
BUFFERS = {'none': (), 'L': ('L',), 'KD': ('KD',), 'L+KD': ('L', 'KD')}
RELAXATION_ACCESS = {'none': 0, 'C': 1, 'V': 2, 'C+V': 3}
CHAMBER = 349
REJECTION = 175


def checked_seats(seats):
    if set(seats) != set(PARTIES) or any(type(v) is not int or v < 0 for v in seats.values()):
        raise ValueError('Eight nonnegative integer parliamentary seat counts are required.')
    if sum(seats.values()) != CHAMBER:
        raise ValueError('This experiment requires a 349-seat chamber.')
    return dict(seats)


def checked_state(state):
    if len(state) != 3 or any(type(v) is not int for v in state):
        raise ValueError('State is (policy_mask, C_relaxed, V_relaxed).')
    policy, c_relaxed, v_relaxed = state
    if not 0 <= policy < 8 or c_relaxed not in (0, 1) or v_relaxed not in (0, 1):
        raise ValueError('Invalid bargaining state.')
    return tuple(state)


def cabinet_members(mask):
    if type(mask) is not int or not 0 <= mask < 8:
        raise ValueError('Cabinet index must be 0..7.')
    return ['S'] + [p for i, p in enumerate(CORE) if mask & (1 << i)]


def evaluate_proposal(seats, state, cabinet_mask, external_buffer='none', external_weight=None):
    """Evaluate one explicitly completed S-led proposal.

    Non-V actions are evaluated first. V is essential precisely when changing
    only V from No to non-No would change rejection to nonrejection. A proposal
    that cannot pass even with V is not called V-essential.
    """
    seats = checked_seats(seats)
    policy, c_relaxed, v_relaxed = checked_state(state)
    if external_buffer not in BUFFERS:
        raise ValueError('Unknown external abstention buffer.')
    members = cabinet_members(cabinet_mask)
    assent = {p: bool(policy & (1 << i)) for i, p in enumerate(CORE)}
    c_compatible = 'V' not in members or bool(c_relaxed)
    roles = {p: 'no' for p in PARTIES}
    roles['S'] = 'yes'
    roles['C'] = ('yes' if 'C' in members else 'abstain') if assent['C'] and c_compatible else 'no'
    roles['MP'] = ('yes' if 'MP' in members else 'abstain') if assent['MP'] else 'no'
    for p in BUFFERS[external_buffer]:
        roles[p] = 'abstain'
    other_non_no = sum(seats[p] for p in PARTIES if p != 'V' and roles[p] != 'no')
    # Continuous buffer experiment moves this many existing outsider No seats to
    # abstention. It is an anonymous-seat capacity, not an additional party.
    if external_weight is not None:
        if external_buffer != 'none' or type(external_weight) is not int or not 0 <= external_weight <= seats['M'] + seats['SD'] + seats['KD'] + seats['L']:
            raise ValueError('Anonymous external capacity must come from existing outsider seats.')
        other_non_no += external_weight
    essential = other_non_no < REJECTION <= other_non_no + seats['V']
    v_inclusion_ok = not essential or 'V' in members or bool(v_relaxed)
    if assent['V'] and v_inclusion_ok:
        roles['V'] = 'yes' if 'V' in members else 'abstain'
    consent = {'S': True}
    for p in members:
        if p == 'S':
            continue
        consent[p] = assent[p] and (c_compatible if p == 'C' else True)
    no = sum(seats[p] for p in PARTIES if roles[p] == 'no')
    yes = sum(seats[p] for p in PARTIES if roles[p] == 'yes')
    abstain = CHAMBER - no - yes
    if external_weight is not None:
        no -= external_weight
        abstain += external_weight
    assert yes + no + abstain == CHAMBER
    not_rejected = no < REJECTION
    cabinet_consented = all(consent.values())
    blocking = []
    if not assent['C']:
        blocking.append('C_policy_requirement')
    if not assent['V']:
        blocking.append('V_policy_requirement')
    if not assent['MP']:
        blocking.append('MP_policy_requirement')
    if not c_compatible:
        blocking.append('C_composition_condition')
    if assent['V'] and not v_inclusion_ok:
        blocking.append('V_essential_inclusion_condition')
    return {
        'state': [policy, c_relaxed, v_relaxed], 'cabinet_mask': cabinet_mask,
        'cabinet_members': members, 'external_buffer': external_buffer,
        'anonymous_external_seats': external_weight,
        'pm_roles': roles if external_weight is None else None,
        'roles_before_anonymous_adjustment': roles if external_weight is not None else None,
        'yes': yes, 'no': no, 'abstain': abstain,
        'v_essential_holding_others_fixed': essential,
        'cabinet_consent': consent, 'cabinet_consented': cabinet_consented,
        'pm_not_rejected': not_rejected,
        'agreement': cabinet_consented and not_rejected,
        'budget_support': 'not_modelled', 'active_clause_diagnostics': blocking,
    }


def states():
    return [(policy, c, v) for c in (0, 1) for v in (0, 1) for policy in range(8)]


def transitions(state, access='C+V', policy_costs=(1, 1, 1), release_costs=(2, 2)):
    policy, c, v = checked_state(state)
    if access not in RELAXATION_ACCESS or len(policy_costs) != 3 or len(release_costs) != 2:
        raise ValueError('Unknown relaxation family or cost dimensions.')
    if any(type(x) is not int or x <= 0 for x in (*policy_costs, *release_costs)):
        raise ValueError('Concession costs must be positive integers.')
    for i, p in enumerate(CORE):
        if not policy & (1 << i):
            yield ((policy | (1 << i), c, v), policy_costs[i], 'meet_' + p + '_policy')
    available = RELAXATION_ACCESS[access]
    if available & 1 and not c:
        yield ((policy, 1, v), release_costs[0], 'relax_C_composition')
    if available & 2 and not v:
        yield ((policy, c, 1), release_costs[1], 'relax_V_inclusion')


def shortest_paths(initial, access='C+V', policy_costs=(1, 1, 1), release_costs=(2, 2)):
    initial = checked_state(initial)
    costs = {initial: 0}
    actions = {initial: []}
    queue = [(0, initial)]
    while queue:
        cost, state = heappop(queue)
        if cost != costs[state]:
            continue
        for next_state, step, label in transitions(state, access, policy_costs, release_costs):
            proposed = cost + step
            if proposed < costs.get(next_state, 10**9):
                costs[next_state] = proposed
                actions[next_state] = actions[state] + [label]
                heappush(queue, (proposed, next_state))
    return costs, actions


def proposal_lookup(seats, buffer='none'):
    return {(state, cabinet): evaluate_proposal(seats, state, cabinet, buffer)
            for state in states() for cabinet in range(8)}


def reachability_rows(seats, buffer='none', profile_id='baseline'):
    lookup = proposal_lookup(seats, buffer)
    agreement_states = {state for state in states() if any(lookup[state, c]['agreement'] for c in range(8))}
    rows = []
    for initial_policy in range(8):
        initial = (initial_policy, 0, 0)
        for access in RELAXATION_ACCESS:
            distances, actions = shortest_paths(initial, access)
            candidates = [(distances[s], s) for s in agreement_states if s in distances]
            minimum = min((c for c, _ in candidates), default=None)
            optimal = sorted(s for c, s in candidates if c == minimum)
            for budget in range(9):
                reachable = [s for s, d in distances.items() if d <= budget]
                feasible = [s for s in reachable if s in agreement_states]
                rows.append({'profile_id': profile_id, 'external_buffer': buffer,
                    'initial_policy_mask': initial_policy, 'relaxation_access': access,
                    'budget': budget, 'structural_possible': minimum is not None,
                    'structural_definition': 'Agreement exists under this permitted concession family with unrestricted cost budget.',
                    'full_state_agreement_count': len(agreement_states),
                    'minimum_concession_cost': minimum, 'agreement_reachable': bool(feasible),
                    'status': 'reachable' if feasible else ('beyond_budget' if minimum is not None else 'no_feasible_agreement'),
                    'reachable_states': len(reachable), 'reachable_agreement_states': len(feasible),
                    'minimum_action_witnesses': [{'terminal_state': list(s), 'actions': actions[s],
                        'consented_cabinets': [lookup[s,c]['cabinet_members'] for c in range(8) if lookup[s,c]['agreement']]}
                        for s in optimal],
                    'cost_unit': 'synthetic concession units, not money, voters or estimated utility'})
    return rows


def simulate_agenda(lookup, agenda, initial=(7, 0, 0), formal_limit=4,
                    pressure_clause='none', pressure_trigger=1, release_budget=2,
                    adaptive_after_release=False, exploratory_only=False,
                    initial_rejections=0):
    """One hypothetical process; formal_limit is additional-vote patience.

    Four TOTAL rejections is an institutional stop. initial_rejections=2 gives
    at most two further rejected proposals. A pressure trigger counts total
    rejections and must lie after the starting counter in a pressure scenario.
    Exploratory proposal evaluations never consume a formal vote.
    """
    state = checked_state(initial)
    if type(formal_limit) is not int or not 1 <= formal_limit <= 4:
        raise ValueError('Additional formal-vote patience must be 1..4.')
    if type(initial_rejections) is not int or not 0 <= initial_rejections <= 3:
        raise ValueError('Initial total rejections must be 0..3.')
    if pressure_clause not in ('none', 'C', 'V') or not 1 <= pressure_trigger <= 4 or release_budget < 0:
        raise ValueError('Invalid synthetic pressure rule.')
    if pressure_clause != 'none' and pressure_trigger <= initial_rejections:
        raise ValueError('A new pressure trigger must follow the initial rejection counter.')
    if not agenda or any(type(c) is not int or not 0 <= c < 8 for c in agenda):
        raise ValueError('An explicit cabinet agenda is required.')
    rejections = initial_rejections
    explorations = spent = 0
    rejection_limit = min(4, initial_rejections + formal_limit)
    released = False
    trace = []

    def finish(status, accepted_vote=False):
        return {'status': status, 'initial_formal_rejections': initial_rejections,
                'formal_rejections': rejections,
                'new_formal_rejections': rejections-initial_rejections,
                'formal_votes': 0 if exploratory_only else rejections-initial_rejections+int(accepted_vote),
                'proposal_evaluations': explorations,
                'remaining_institutional_attempts': 4-rejections,
                'concession_spent': spent, 'terminal_state': list(state), 'trace': trace}

    for original in agenda:
        cabinet = original
        if released and adaptive_after_release:
            candidates = [c for c in range(8) if lookup[state,c]['agreement']]
            if candidates:
                cabinet = candidates[0]
        proposal = lookup[state,cabinet]
        explorations += 1
        trace.append({'step': explorations, 'state': list(state), 'cabinet_mask': cabinet,
                      'cabinet_members': proposal['cabinet_members'],
                      'cabinet_consented': proposal['cabinet_consented'],
                      'pm_not_rejected': proposal['pm_not_rejected'], 'no': proposal['no'],
                      'rejections_before_evaluation': rejections})
        if proposal['agreement']:
            return finish('agreement_identified' if exploratory_only else 'agreement_found', not exploratory_only)
        if exploratory_only:
            continue
        if proposal['pm_not_rejected']:
            return finish('pm_passed_without_cabinet_agreement', True)
        rejections += 1
        if rejections == rejection_limit:
            return finish('four_rejections' if rejections == 4 else 'patience_exhausted')
        if not released and pressure_clause != 'none' and rejections >= pressure_trigger and release_budget >= 2:
            policy, c, v = state
            state = (policy, 1 if pressure_clause == 'C' else c, 1 if pressure_clause == 'V' else v)
            spent += 2
            released = True
    return finish('exploration_exhausted' if exploratory_only else 'agenda_exhausted')


def exhaustive_agendas(lookup, initial=(7, 0, 0), formal_limit=4,
                       pressure_clause='none', pressure_trigger=1,
                       release_budget=2, adaptive_after_release=False, initial_rejections=0):
    """All 8! agenda orders, compressed to their distinct first-four prefixes."""
    counts = Counter()
    rejection_totals = Counter()
    witnesses = {}
    prefixes = 0
    for prefix in permutations(range(8), 4):
        prefixes += 1
        outcome = simulate_agenda(lookup, prefix, initial, formal_limit,
            pressure_clause, pressure_trigger, release_budget, adaptive_after_release, initial_rejections=initial_rejections)
        counts[outcome['status']] += 24  # each four-prefix has 4! full completions
        rejection_totals[outcome['formal_rejections']] += 24
        witnesses.setdefault(outcome['status'], {'agenda_prefix': list(prefix), **outcome})
    assert prefixes == 1680 and sum(counts.values()) == 40320
    return {'full_agenda_orders': 40320, 'distinct_four_prefixes_enumerated': 1680,
            'outcome_counts': dict(counts), 'formal_rejection_count_distribution': dict(rejection_totals),
            'witnesses': witnesses, 'counts_are_probabilities': False}
