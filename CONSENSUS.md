# Consensus extension — 1.3.0

The v1.3.0 release adds capacity-coupled consensus auditing. The archived
v1.2.1.post1 release does not contain this module. Runtime dependencies remain empty.

```
python trace_rank_audit.py --input examples/consensus_scores.tsv \
  --budget 2 --consensus-thresholds 1,2,3 --output-dir /tmp/trace-consensus-demo
```

The optional switch adds `consensus_audit.tsv` and `consensus_witnesses.json`.
The three existing audit TSVs retain their schemas and values. Receipt versions
change to identify the new implementation. For a context with M views, q>M is
reported as NON_EVALUABLE_Q_GT_M. Unevaluable scores must never be padded with zero.

For q-of-M, `marginal_lower` counts individually necessary candidates;
`marginal_upper` counts individually possible candidates. Their difference need
not describe attainable variation in the SIZE of a common consensus set.
The certified interval encloses every attainable size. `minimum_feasible` and
`maximum_feasible` are accompanied by complete, legal per-view shortlist witnesses.
EXACT means both endpoint proofs are closed. BOUNDED_NOT_EXACT means at least one
endpoint remains unproved at the specified resource limits; it is not an exact result.

Algorithm: boundary-fits normalization; feasible identifier and greedy seeds;
integer vote-conservation bounds; candidate-pattern branch-and-bound with
capacity feasibility and dominance memoization. The q=1 maximum additionally uses
capacitated bipartite maximum matching. General search is exponential in the worst
case. No generic polynomial-time or globally scalable 32-view claim is made.

For the example, each view chooses two of three tied candidates. All candidates
are individually possible and none individually necessary. For q=2 the exact
consensus-size range is [2,3], whereas marginal counting gives [0,3]. Six total
votes and at most three votes per candidate force at least two candidates to
receive two votes. The witness file supplies allocations attaining both bounds.

Run `python -m unittest discover -s tests -v`. The scientific tests include small
exhaustive allocation comparisons, timeout enclosure, pairwise intersection
reduction, boundary-fits normalization, input errors and view-order invariance.
Empirical input extraction uses pandas/pyarrow separately from the generic engine.
