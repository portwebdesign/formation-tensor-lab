import unittest
from collections import Counter
from itertools import permutations

from formation_tensor.bargaining import (
    cabinet_members, evaluate_proposal, exhaustive_agendas, proposal_lookup,
    reachability_rows, shortest_paths, simulate_agenda, states,
)

SEATS = {'S':99, 'M':70, 'SD':62, 'V':30, 'C':25, 'KD':22, 'MP':22, 'L':19}


class BargainingTests(unittest.TestCase):
    def test_conditional_inclusion_and_non_circular_essentiality(self):
        blocked = evaluate_proposal(SEATS, (7,0,0), 0)
        self.assertTrue(blocked['v_essential_holding_others_fixed'])
        self.assertEqual(blocked['pm_roles']['V'], 'no')
        hopeless = evaluate_proposal(SEATS, (2,0,0), 0)
        self.assertFalse(hopeless['v_essential_holding_others_fixed'])
        self.assertEqual(hopeless['pm_roles']['V'], 'abstain')
        self.assertFalse(hopeless['pm_not_rejected'])

    def test_cabinet_consent_is_not_formal_nonrejection(self):
        proposal = evaluate_proposal(SEATS, (7,0,0), 7, 'L+KD')
        self.assertTrue(proposal['pm_not_rejected'])
        self.assertFalse(proposal['cabinet_consent']['C'])
        self.assertFalse(proposal['agreement'])
        self.assertEqual(proposal['budget_support'], 'not_modelled')

    def test_complete_graph_distances_match_action_subset_oracle(self):
        costs = (3,1,2)
        releases = (5,4)
        distances, _ = shortest_paths((0,0,0), 'C+V', costs, releases)
        self.assertEqual(len(distances), 32)
        # Independent subset cost formula; all five one-way actions commute.
        for (policy,c,v), result in distances.items():
            expected=sum(costs[i] for i in range(3) if policy & (1<<i))+5*c+4*v
            self.assertEqual(result, expected)
        initial_relaxed,_ = shortest_paths((5,1,0), 'none', costs,releases)
        self.assertEqual(initial_relaxed, {(5,1,0):0,(7,1,0):1})

    def test_reachability_and_synthetic_cost_boundaries(self):
        rows = reachability_rows(SEATS, 'none')
        query = lambda policy,access,budget: next(r for r in rows if r['initial_policy_mask']==policy and r['relaxation_access']==access and r['budget']==budget)
        self.assertFalse(query(7,'none',8)['structural_possible'])
        self.assertEqual(query(0,'C+V',2)['minimum_concession_cost'],5)
        self.assertEqual(query(0,'C+V',2)['status'],'beyond_budget')
        self.assertTrue(query(0,'C+V',5)['agreement_reachable'])
        buffered = reachability_rows(SEATS,'L+KD')
        row = next(r for r in buffered if r['initial_policy_mask']==0 and r['relaxation_access']=='none' and r['budget']==2)
        self.assertEqual(row['minimum_concession_cost'],2)
        self.assertTrue(row['agreement_reachable'])

    def test_lower_budget_never_adds_reachable_agreements(self):
        for buffer in ('none','L','KD','L+KD'):
            rows = reachability_rows(SEATS,buffer)
            for policy in range(8):
                for access in ('none','C','V','C+V'):
                    selected=[r for r in rows if r['initial_policy_mask']==policy and r['relaxation_access']==access]
                    self.assertEqual([r['reachable_states'] for r in selected], sorted(r['reachable_states'] for r in selected))

    def test_source_seats_produce_exact_anonymous_buffer_boundary(self):
        feasible=[]
        for capacity in range(25):
            feasible.append(any(evaluate_proposal(SEATS,(7,0,0),c,external_weight=capacity)['agreement'] for c in range(8)))
        self.assertEqual(feasible,[False]*24+[True])
        anonymous=evaluate_proposal(SEATS,(7,0,0),6,external_weight=24)
        self.assertIsNone(anonymous['pm_roles'])
        self.assertEqual(anonymous['yes']+anonymous['no']+anonymous['abstain'],349)

    def test_seat_loss_can_make_all_internal_concessions_insufficient(self):
        altered={**SEATS,'S':97,'M':72}
        self.assertFalse(any(evaluate_proposal(altered,s,c)['agreement'] for s in states() for c in range(8)))
        self.assertTrue(any(evaluate_proposal(altered,s,c,'L')['agreement'] for s in states() for c in range(8)))

    def test_exploration_never_spends_a_formal_vote(self):
        lookup=proposal_lookup(SEATS)
        unchanged=simulate_agenda(lookup,[0]*12,exploratory_only=True)
        self.assertEqual(unchanged['formal_votes'],0)
        self.assertEqual(unchanged['formal_rejections'],0)
        self.assertEqual(unchanged['status'],'exploration_exhausted')
        feasible=simulate_agenda(lookup,[2],initial=(7,1,0),exploratory_only=True)
        self.assertEqual(feasible['status'],'agreement_identified')
        self.assertEqual(feasible['formal_votes'],0)

    def test_fourth_rejection_precedes_pressure(self):
        lookup=proposal_lookup(SEATS)
        fourth=simulate_agenda(lookup,[0,1,4,5],pressure_clause='C',pressure_trigger=4)
        self.assertEqual(fourth['status'],'four_rejections')
        self.assertEqual(fourth['terminal_state'],[7,0,0])
        self.assertEqual(fourth['concession_spent'],0)
        third=simulate_agenda(lookup,[0,1,4,5],pressure_clause='C',pressure_trigger=3,adaptive_after_release=True)
        self.assertEqual(third['status'],'agreement_found')
        self.assertEqual(third['formal_rejections'],3)
        self.assertEqual(third['formal_votes'],4)

    def test_rotation_without_state_change_is_a_null_control(self):
        lookup=proposal_lookup(SEATS)
        for agenda in ([0,1,2,3],[7,6,5,4],[0,0,0,0]):
            outcome=simulate_agenda(lookup,agenda)
            self.assertEqual(outcome['status'],'four_rejections')
        underfunded=simulate_agenda(lookup,[0,1,2,3],pressure_clause='C',release_budget=1)
        self.assertEqual(underfunded['status'],'four_rejections')

    def test_current_two_rejections_leave_two_future_attempts(self):
        lookup=proposal_lookup(SEATS)
        stopped=simulate_agenda(lookup,[0,1,2,3],initial_rejections=2)
        self.assertEqual(stopped['formal_rejections'],4)
        self.assertEqual(stopped['formal_votes'],2)
        self.assertEqual(stopped['new_formal_rejections'],2)
        self.assertEqual(stopped['remaining_institutional_attempts'],0)
        released=simulate_agenda(lookup,[0,1,2,3],initial_rejections=2,
            pressure_clause='C',pressure_trigger=3,adaptive_after_release=True)
        self.assertEqual(released['status'],'agreement_found')
        self.assertEqual(released['formal_votes'],2)
        self.assertEqual(released['formal_rejections'],3)
        with self.assertRaises(ValueError):
            simulate_agenda(lookup,[0],initial_rejections=2,pressure_clause='C',pressure_trigger=2)

    def test_agenda_prefix_compression_matches_all_full_orders(self):
        lookup=proposal_lookup(SEATS)
        compressed=exhaustive_agendas(lookup,pressure_clause='C',pressure_trigger=3)
        direct=Counter(simulate_agenda(lookup,order,pressure_clause='C',pressure_trigger=3)['status'] for order in permutations(range(8)))
        self.assertEqual(compressed['outcome_counts'],dict(direct))
        self.assertEqual(sum(direct.values()),40320)

    def test_inputs_and_horizons_reject_invalid_values(self):
        with self.assertRaises(ValueError):
            cabinet_members(8)
        with self.assertRaises(ValueError):
            evaluate_proposal(SEATS,(8,0,0),0)
        with self.assertRaises(ValueError):
            evaluate_proposal(SEATS,(7,0,0),0,external_weight=200)
        with self.assertRaises(ValueError):
            simulate_agenda(proposal_lookup(SEATS),[0],formal_limit=5)


if __name__=='__main__':
    unittest.main()
