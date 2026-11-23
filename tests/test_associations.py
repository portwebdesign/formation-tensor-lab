import unittest

from formation_tensor.associations import (mode, matrix_statistics, pair_rows, blocks,
    block_statistics, resampling_range, discovery_candidates, replay_candidates)


def row(i, a, b, report='R1', session='2022/23', committee='SoU'):
    counts = {}
    for p, action in [('S',a),('M',b)]:
        values = [0,0,0,2]
        if action is not None:
            values[action] = 10
        counts[p] = values
    return {'id':str(i),'session':session,'committee':committee,
            'beteckning':report,'party_counts':counts}


class AssociationTests(unittest.TestCase):
    def test_mode_ignores_absence_and_rejects_tie(self):
        self.assertEqual(mode([2,0,0,100]),0)
        self.assertIsNone(mode([2,2,0,0]))
        self.assertIsNone(mode([0,0,0,349]))
        with self.assertRaises(ValueError):mode([1,-1,0,0])

    def test_identical_balanced_actions(self):
        r=matrix_statistics({('a','b'):[[5,0,0],[0,5,0],[0,0,0]]})
        self.assertAlmostEqual(r['observed_agreement'],1)
        self.assertAlmostEqual(r['conditional_reference'],.5)
        self.assertAlmostEqual(r['conditional_kappa'],1)

    def test_degenerate_unanimity_is_not_excess(self):
        r=matrix_statistics({('a','b'):[[10,0,0],[0,0,0],[0,0,0]]})
        self.assertEqual(r['excess_agreement_pp'],0)
        self.assertIsNone(r['conditional_kappa'])

    def test_conditional_reference_controls_agenda(self):
        # Perfect pooled co-movement entirely explained by two fixed agendas.
        r=matrix_statistics({('a','b'):[[8,0,0],[0,0,0],[0,0,0]],
                             ('c','b'):[[0,0,0],[0,2,0],[0,0,0]]})
        self.assertEqual(r['observed_agreement'],1)
        self.assertEqual(r['conditional_reference'],1)
        self.assertEqual(r['excess_agreement_pp'],0)

    def test_independent_contingency_zero_excess(self):
        r=matrix_statistics({('a','b'):[[2,2,0],[2,2,0],[0,0,0]]})
        self.assertEqual(r['conditional_kappa'],0)

    def test_report_equal_does_not_count_repeated_items_as_reports(self):
        rs=[row(i,0,0) for i in range(10)]+[row(11,0,1,report='R2')]
        b=blocks(pair_rows(rs,['S','M']))
        self.assertEqual(len(b),2)
        self.assertAlmostEqual(block_statistics(b)['observed_agreement'],.5)
        self.assertAlmostEqual(block_statistics(b,'rollcall_equal')['observed_agreement'],10/11)

    def test_missing_mode_denominator(self):
        rs=[row(1,0,1),row(2,None,1),row(3,0,None)]
        self.assertEqual(len(pair_rows(rs,['S','M'])),1)

    def test_bootstrap_is_reproducible_and_preserves_constant_pattern(self):
        b=blocks(pair_rows([row(1,0,0),row(2,0,0,report='R2')],['S','M']))
        a=resampling_range(b,20,17)
        self.assertEqual(a,resampling_range(b,20,17))
        self.assertEqual(a['excess_pp_percentiles'],[0,0])
        with self.assertRaises(ValueError):resampling_range(b,0)

    def test_discovery_rejects_later_sessions(self):
        with self.assertRaises(ValueError):discovery_candidates([row(1,0,0,session='2025/26')])

    def test_replay_rejects_discovery_sessions(self):
        with self.assertRaises(ValueError):replay_candidates([row(1,0,0)],[])


if __name__=='__main__':unittest.main()
