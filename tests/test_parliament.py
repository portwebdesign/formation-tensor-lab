import itertools
import unittest
from formation_tensor.parliament import reach, boundary_profile, joint_profile

class ParliamentTests(unittest.TestCase):
    def test_reach_against_explicit_action_updates(self):
        for y,n,a,x in itertools.product(range(4),repeat=4):
            if y==n:continue
            for s,ac,xc in itertools.product(range(3),repeat=3):
                states=[]
                for ss in range(min(s,max(y,n))+1):
                    for aa in range(min(ac,a)+1):
                        for xx in range(min(xc,x)+1):
                            states.append((y-ss,n+ss+aa+xx) if y>n else (y+ss+aa+xx,n-ss))
                expected=any((yy<nn if y>n else yy>nn) for yy,nn in states)
                self.assertEqual(reach([y,n,a,x],s,ac,xc),expected)
    def test_tie_direction_missing_and_invalid_caps_rejected(self):
        self.assertIsNone(reach([2,2,1,1],1))
        with self.assertRaises(ValueError):reach([2,1,1,1],-1)
    def test_joint_requirement_is_not_two_independent_reversals(self):
        row={'counts':[153,149,0,47],'session':'s','report':'r'}
        self.assertEqual(joint_profile([row],2,3)['both_required'],1)
        self.assertFalse(reach(row['counts'],2))
        self.assertFalse(reach(row['counts'],0,0,3))
    def test_report_weights_prevent_repeated_item_dominance(self):
        rows=[{'counts':[4,3,0,0],'session':'s','report':'a'}]*9+[{'counts':[7,0,0,0],'session':'s','report':'b'}]
        p=boundary_profile(rows)['budget_profile'][1]
        self.assertAlmostEqual(p['rollcall_fraction'],.9)
        self.assertAlmostEqual(p['report_fraction'],.5)
    def test_even_sample_median_averages_the_two_middle_boundaries(self):
        rows=[{'counts':[2,1,0,0],'session':'s','report':'a'},
              {'counts':[4,1,0,0],'session':'s','report':'b'}]
        self.assertEqual(boundary_profile(rows)['median_switch_boundary'],1.5)
