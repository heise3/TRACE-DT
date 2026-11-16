import itertools
import random
import unittest
import tempfile
from pathlib import Path
from trace_rank_audit import build_cell, exact_intersection_bounds
from trace_consensus import consensus_bounds, consensus_size, validate_witness


def exhaustive(cells,q):
    families=[list(c.strict_above|frozenset(s) for s in itertools.combinations(sorted(c.tied),c.remaining_seats)) for c in cells]
    vals=[consensus_size(a,q) for a in itertools.product(*families)]
    return min(vals),max(vals)


class ConsensusTests(unittest.TestCase):
    def test_small_exhaustive(self):
        rng=random.Random(20261115)
        for k in range(200):
            M=rng.randrange(1,5);N=rng.randrange(2,6);B=rng.randrange(1,N+1)
            cells=[build_cell('c',str(m),{str(u):float(rng.randrange(3)) for u in range(N)},B) for m in range(M)]
            for q in range(1,M+1):
                with self.subTest(k=k,q=q):
                    lo,hi=exhaustive(cells,q)
                    a=consensus_bounds(cells,q,time_limit=5)
                    self.assertEqual(a['status'],'EXACT')
                    self.assertEqual((a['certified_lower'],a['certified_upper']),(lo,hi))
                    self.assertTrue(validate_witness(cells,a['witness_min'],q,lo))
                    self.assertTrue(validate_witness(cells,a['witness_max'],q,hi))
                    z=consensus_bounds(cells,q,node_limit=0,time_limit=0)
                    self.assertLessEqual(z['certified_lower'],lo)
                    self.assertGreaterEqual(z['certified_upper'],hi)
    def test_pairwise_reduction(self):
        rng=random.Random(932)
        for _ in range(80):
            cells=[build_cell('c',str(m),{str(u):float(rng.randrange(4)) for u in range(8)},4) for m in range(2)]
            expected=exact_intersection_bounds(*cells)
            a=consensus_bounds(cells,2)
            self.assertEqual((a['certified_lower'],a['certified_upper']),expected)
    def test_coupling_counterexample(self):
        # Four candidates, three views, B=3: no marginal necessary member,
        # nine votes force at least three candidates to receive two votes.
        cells=[build_cell('c',str(m),dict.fromkeys('abcd',1.),3) for m in range(3)]
        a=consensus_bounds(cells,2)
        self.assertEqual((a['marginal_lower'],a['marginal_upper']),(0,4))
        self.assertEqual((a['certified_lower'],a['certified_upper']),(3,4))
        cells=[build_cell('c',str(m),dict.fromkeys('abc',1.),2) for m in range(3)]
        a=consensus_bounds(cells,2)
        self.assertEqual((a['marginal_lower'],a['marginal_upper']),(0,3))
        self.assertEqual((a['certified_lower'],a['certified_upper']),(2,3))
    def test_full_boundary_and_order(self):
        cells=[build_cell('c',str(m),dict.fromkeys('abcd',1.),4) for m in range(3)]
        for q in range(1,4):
            a=consensus_bounds(cells,q);self.assertEqual(a['certified_lower'],4)
            self.assertEqual(a['certified_upper'],4)
        cells=[build_cell('c',str(m),dict.fromkeys('abcde',1.),2) for m in range(3)]
        for q in range(1,4):
            a=consensus_bounds(cells,q);b=consensus_bounds(cells[::-1],q)
            self.assertEqual((a['certified_lower'],a['certified_upper']),(b['certified_lower'],b['certified_upper']))
    def test_errors(self):
        c=build_cell('c','a',{'a':1.,'b':1.},1)
        for q in [0,2,True,1.5]:
            with self.assertRaises(ValueError):consensus_bounds([c],q)
        with self.assertRaises(ValueError):consensus_bounds([c,c],1)
        with self.assertRaises(ValueError):consensus_bounds([],1)
    def test_cli_extension_preserves_existing_outputs(self):
        from trace_rank_audit import run
        source=Path(__file__).resolve().parents[1]/'examples/consensus_scores.tsv'
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'old';b=Path(tmp)/'new'
            run(source,a,2)
            receipt=run(source,b,2,consensus_thresholds=(1,2,3,4))
            self.assertEqual(receipt['consensus']['exact'],3)
            self.assertEqual(receipt['consensus']['non_evaluable'],1)
            for name in ['cell_contract.tsv','pairwise_audit.tsv','target_membership.tsv']:
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())


if __name__=='__main__':unittest.main()
