from itertools import product
import unittest

from formation_tensor.election import (AMOUNTS,DIRECTIONS,PAIRS,attach_interactions,
    interpret_native,mixed_differences,net_transfer_cost,pair_id,summary_for,transfer_body)


def corner(g):
    return {'status':'passed','nonreject_seats':g,'nonreject_at_least_175':g>=175}


def native():
    seats={'M':70,'S':99,'L':19,'C':25,'V':30,'MP':22,'KD':22,'SD':62}
    return {'status':'passed','district_turnout_preserved':True,'valid_votes':800,
        'cost_voters':0,'parties':[{'label':p,'seats_before':n,'seats_after':n,
            'votes_before':100,'votes_after':100,'eligible_before':True,'eligible_after':True}
            for p,n in seats.items()]},seats


class ExactElectionTests(unittest.TestCase):
    def test_protocol_pairs_disjoint_and_body_conserves_every_small_table(self):
        self.assertEqual(len(PAIRS),6)
        ids={p:str(i) for i,p in enumerate(sum((list(d) for d in DIRECTIONS),[]))}
        for pair in PAIRS:
            self.assertEqual(len(set(sum((list(d) for d in pair),[]))),4)
            for a,b in product(range(4),repeat=2):
                before={p:4 for p in ids};after=dict(before)
                body=transfer_body('01',ids,pair,a,b)
                for direction,amount in zip(pair,(a,b)):
                    after[direction[0]]-=amount;after[direction[1]]+=amount
                self.assertEqual(net_transfer_cost(list(before.values()),list(after.values())),a+b)
                self.assertEqual(len(body.splitlines()),int(a>0)+int(b>0))

    def test_transfer_input_validation_and_cost_not_gross_path_length(self):
        for amount in (-1,True,1.5):
            with self.assertRaises(ValueError):transfer_body('01',{'MP':'a','SD':'b','S':'c','M':'d'},PAIRS[0],amount,0)
        with self.assertRaises(ValueError):transfer_body('01\n',{},PAIRS[0],0,0)
        self.assertEqual(net_transfer_cost([10,10],[10,10]),0)
        with self.assertRaises(ValueError):net_transfer_cost([1,2],[1,3])

    def test_exact_seat_interaction_differs_from_threshold_interaction(self):
        redundant=mixed_differences(corner(174),corner(174),corner(174),corner(173))
        self.assertEqual((redundant['mixed_seats'],redundant['mixed_threshold']),(-1,0))
        complementary=mixed_differences(corner(175),corner(174),corner(174),corner(173))
        self.assertEqual((complementary['mixed_seats'],complementary['mixed_threshold']),(0,1))

    def test_all_missing_corner_positions_are_retained(self):
        for failed in range(4):
            corners=[corner(175),corner(174),corner(174),corner(173)]
            corners[failed]={'status':'masked','nonreject_seats':None,'nonreject_at_least_175':None}
            result=mixed_differences(*corners)
            self.assertIsNone(result['mixed_seats']);self.assertIsNone(result['mixed_threshold'])
            self.assertEqual(result['masked_corner_indices'],[failed])

    def test_native_guard_checks_denominator_cost_turnout_and_eligibility(self):
        record,seats=native()
        self.assertEqual(interpret_native(record,0,seats,800,True)['nonreject_seats'],173)
        record['parties'][0]['eligible_after']=False
        self.assertEqual(interpret_native(record,0,seats,800)['error_type'],'outside_fixed_eligibility')
        record,seats=native();record['valid_votes']=799
        with self.assertRaises(ValueError):interpret_native(record,0,seats,800)
        record,seats=native();record['cost_voters']=1
        with self.assertRaises(ValueError):interpret_native(record,0,seats,800)
        record,seats=native();record['district_turnout_preserved']=False
        with self.assertRaises(ValueError):interpret_native(record,0,seats,800)

    def test_native_failure_keeps_nulls_and_reason(self):
        result=interpret_native({'status':'not_completed','error_type':'tie','message':'unresolved'},5,{},800)
        self.assertEqual(result['error_type'],'tie');self.assertIsNone(result['nonreject_seats'])

    def test_tensor_coordinates_require_unique_complete_corners(self):
        rows=[]
        for a,b in product((0,1),repeat=2):
            rows.append({'pair_id':pair_id(PAIRS[0]),'district_id':'01','amount_a':a,'amount_b':b,
                **corner(173+a+b),'error_type':None})
        attached=attach_interactions(rows)
        self.assertEqual(summary_for(attached)['positive_threshold_interactions'],1)
        with self.assertRaises(ValueError):attach_interactions(rows+[rows[0]])
        with self.assertRaises(ValueError):attach_interactions(rows[1:])


if __name__=='__main__':unittest.main()
