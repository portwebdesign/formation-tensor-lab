import json
from pathlib import Path
import unittest

from formation_tensor.completion_sensitivity import (
    BUFFERS, VARIANTS, agenda_counts, edge_diagnostics, evaluate,
    minimum_cost, states, subset_distances,
)

SEATS = {'S': 99, 'M': 70, 'SD': 62, 'V': 30, 'C': 25, 'KD': 22, 'MP': 22, 'L': 19}
ROOT = Path(__file__).resolve().parents[1]


def lookup(variant='baseline', buffer='none'):
    return {(state, cabinet): evaluate(SEATS, state, cabinet, buffer, variant)
            for state in states() for cabinet in range(8)}


class CompletionTests(unittest.TestCase):
    def test_independent_baseline_matches_every_admitted_proposal(self):
        path = ROOT / 'results/bargaining/feasibility-tensor.json'
        if not path.exists():
            self.skipTest('Stored cross-audit oracle is absent from a fresh calculation directory.')
        profiles = {p['profile_id']: p['seat_vector'] for p in json.loads((ROOT / 'results/interactions/seat-profiles.json').read_text())['profiles']}
        count = 0
        for original in json.loads(path.read_text())['rows']:
            pid = original['profile_id']
            result = evaluate(profiles[pid], original['state'], original['cabinet_mask'], original['external_buffer'])
            self.assertEqual(result, {k: v for k, v in original.items() if k != 'profile_id'})
            count += 1
        self.assertEqual(count, 26624)

    def test_strict_v_changes_hopeless_nonpivotal_action_without_a_policy_change(self):
        baseline = evaluate(SEATS, (3, 0, 0), 0)
        strict = evaluate(SEATS, (3, 0, 0), 0, variant='strict_V_outside')
        self.assertFalse(baseline['v_essential_holding_others_fixed'])
        self.assertEqual(baseline['pm_roles']['V'], 'abstain')
        self.assertEqual(strict['pm_roles']['V'], 'no')
        self.assertEqual((baseline['no'], strict['no']), (195, 225))
        released = evaluate(SEATS, (3, 0, 1), 0, variant='strict_V_outside')
        self.assertEqual(released['pm_roles']['V'], 'abstain')

    def test_c_link_is_to_policy_bits_not_v_actual_vote(self):
        partial = evaluate(SEATS, (3, 0, 0), 0, variant='C_package_linked')
        self.assertEqual(partial['pm_roles']['C'], 'no')
        full = evaluate(SEATS, (7, 0, 0), 0, variant='both')
        # V's actual No does not recurse into C's already satisfied policy bits.
        self.assertEqual(full['pm_roles']['V'], 'no')
        self.assertEqual(full['pm_roles']['C'], 'abstain')
        included_partial = evaluate(SEATS, (3, 0, 0), 1, variant='C_package_linked')
        self.assertFalse(included_partial['cabinet_consent']['C'])

    def test_counts_conserved_and_consent_distinct_for_all_variants(self):
        seen_pass_without_consent = False
        for variant in VARIANTS:
            for buffer in BUFFERS:
                for state in states():
                    for cabinet in range(8):
                        result = evaluate(SEATS, state, cabinet, buffer, variant)
                        self.assertEqual(result['yes'] + result['no'] + result['abstain'], 349)
                        self.assertEqual(result['pm_not_rejected'], result['no'] < 175)
                        self.assertEqual(result['agreement'], result['cabinet_consented'] and result['pm_not_rejected'])
                        seen_pass_without_consent |= result['pm_not_rejected'] and not result['cabinet_consented']
        self.assertTrue(seen_pass_without_consent)

    def test_subset_costs_and_baseline_minima(self):
        self.assertEqual(subset_distances(3, 'none'), {(3, 0, 0): 0, (7, 0, 0): 1})
        self.assertEqual(subset_distances(7, 'V'), {(7, 0, 0): 0, (7, 0, 1): 2})
        self.assertEqual(minimum_cost(lookup(), 0, 'C+V')[0], 5)
        self.assertIsNone(minimum_cost(lookup(), 0, 'none')[0])
        self.assertEqual(minimum_cost(lookup(buffer='KD'), 0, 'C+V')[0], 4)
        self.assertEqual(minimum_cost(lookup('C_package_linked', 'KD'), 0, 'C+V')[0], 5)

    def test_strict_v_preserves_agreements_but_removes_no_increase(self):
        original, strict = lookup(), lookup('strict_V_outside')
        self.assertEqual([r['agreement'] for r in original.values()], [r['agreement'] for r in strict.values()])
        self.assertEqual(edge_diagnostics(original)[0]['No_increasing_edges'], 16)
        self.assertEqual(edge_diagnostics(strict)[0]['No_increasing_edges'], 0)

    def test_cutoff_and_late_release_exact_counts(self):
        original = lookup()
        for variant in VARIANTS:
            candidate = lookup(variant)
            expected = [37440, 31680, 20160, 0]
            for trigger, successes in enumerate(expected, 1):
                counts = agenda_counts(candidate, 0, 'V', trigger)['outcome_counts']
                self.assertEqual(counts.get('agreement_found', 0), successes)
            self.assertEqual(agenda_counts(candidate, 2, 'V', 3)['outcome_counts']['agreement_found'], 20160)
            self.assertEqual(agenda_counts(candidate, 2, 'V', 4, True)['outcome_counts'], {'four_rejections': 40320})
        self.assertEqual(agenda_counts(original, 2, 'V', 3, True)['outcome_counts'], {'agreement_found': 40320})

    def test_invalid_domains_are_rejected(self):
        for state in ((8, 0, 0), (1, 2, 0), (True, 0, 0)):
            with self.assertRaises(ValueError):
                evaluate(SEATS, state, 0)
        with self.assertRaises(ValueError):
            evaluate({**SEATS, 'S': 98}, (0, 0, 0), 0)
        with self.assertRaises(ValueError):
            evaluate(SEATS, (0, 0, 0), 0, variant='unknown')
        with self.assertRaises(ValueError):
            subset_distances(0, 'unknown')


if __name__ == '__main__':
    unittest.main()
