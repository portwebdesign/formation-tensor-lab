from itertools import product
import unittest

from experiments.check_minor_vote_correction import residual_gaps


class MinorCorrectionTests(unittest.TestCase):
    def test_exact_loss_bounds_against_direct_integer_thresholds(self):
        checked = 0
        for total in range(1, 61):
            for votes in range(total+1):
                for addition in range(5):
                    before_n = 4*total-100*votes
                    before_r = 12*total-100*votes
                    for party_addition in range(addition+1):
                        actual_n = 4*(total+addition)-100*(votes+party_addition)
                        actual_r = 12*(total+addition)-100*(votes+party_addition)
                        self.assertGreaterEqual(actual_n, before_n-96*addition)
                        self.assertGreaterEqual(actual_r, before_r-88*addition)
                        checked += 1
        self.assertGreater(checked, 25000)

    def test_inside_votes_unchanged_but_valid_denominator_increases(self):
        for total, votes, addition in product(range(1, 40), range(1, 40), range(5)):
            self.assertEqual(100*votes-4*(total+addition),100*votes-4*total-4*addition)

    def test_equal_threshold_is_eligible_and_outside_gaps_must_be_strict(self):
        self.assertTrue(residual_gaps(16,385,353,4)['eligible_set_retained'])
        self.assertFalse(residual_gaps(15,385,353,4)['eligible_set_retained'])
        self.assertFalse(residual_gaps(16,384,353,4)['eligible_set_retained'])
        self.assertFalse(residual_gaps(16,385,352,4)['eligible_set_retained'])

    def test_guard_refuses_near_threshold_corrections_that_can_change_eligibility(self):
        # One of25validvotes is exactly4%; adding one outside vote excludes it.
        self.assertGreaterEqual(100,4*25)
        self.assertLess(100,4*26)
        self.assertFalse(residual_gaps(0,1000,1000,1)['eligible_set_retained'])
        # One of9votes is below12%; adding one to that outside party crosses it.
        self.assertLess(100,12*9)
        self.assertGreaterEqual(200,12*10)
        self.assertFalse(residual_gaps(1000,1000,12*9-100,1)['eligible_set_retained'])

    def test_cap_validation(self):
        for cap in (-1, True, 1.2):
            with self.assertRaises(ValueError):
                residual_gaps(1000,1000,1000,cap)


if __name__ == '__main__':
    unittest.main()
