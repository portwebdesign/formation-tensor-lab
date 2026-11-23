# Assumption-completion sensitivity

This is a separate retrospective sensitivity experiment. It leaves the original bargaining
rules and their stored results unchanged. It evaluates two explicit alternatives
to predicates that were not uniquely identified by the documentary record.

1. **Strict V outside rule:** an active inclusion demand leads to No outside the
   cabinet even when V is nonpivotal. Inclusion or the V release permits support.
2. **C package linkage:** C requires its own policy bit and both V/MP policy bits
   before its policy condition is met. These are exogenous policy conditions,
   not V/MP's endogenous prime-minister votes. There is no evaluation-order cycle.

The four completions are the original baseline, each alternative separately,
and both together. All preserve the cabinet family, chamber, costs and outside
buffers. Cabinet changes remain unpriced and outside tolerance remains exogenous.

## Executed domain

- 106,496 proposal evaluations: four completions, 26 exact seat profiles, four
  buffers, 32 states and eight cabinet compositions.
- 13,312 minimum-cost settings and 119,808 budget-specific reachability rows.
- 96 full-policy baseline agenda scenarios, each covering all 40,320 orders.
- Independent evaluator matches all 26,624 original proposal records field for
  field; independent subset-cost enumeration matches all 29,952 reachability
  records. Both baseline mismatch counts are zero.

## Results

| Completion | None | L | KD | L+KD | No-increasing edges |
|---|---:|---:|---:|---:|---:|
| Original baseline | 5 | 5 | 4 | 2 | 1,424 |
| Strict V outside | 5 | 5 | 4 | 2 | 0 |
| C package linked | 5 | 5 | 5 | 2 | 712 |
| Both | 5 | 5 | 5 | 2 | 0 |

Costs start at policy state 000, permit both composition releases, and use the
baseline seat vector. They do not price obtaining outside abstention. Each edge
count covers 66,560 fixed-cabinet state edges across the 26 profiles and buffers.
No completion has an agreement-losing edge.

All four completions preserve the split of 11 profiles admitting an internal
route and 15 requiring an outside non-No action. With the linked C requirement,
KD's minimum becomes five in every profile; originally it was four in 22 profiles
and five in four. The L+KD two-unit route survives because another acceptable
cabinet can be chosen; a specific original cabinet need not remain acceptable.

The stricter V completion changes 2,232 proposal No counts but no agreement,
consent or nonrejection predicate. When V was pivotal it already voted No; when
V was hopeless the proposal already failed; when V was redundant, the others
already supplied at least 175 non-No seats. The original feedback witness changes
from 195 to 203 No votes; its corresponding strict-V witness is 225 to 203.
With linked C it is 220 to 203, and with both alternatives 250 to 203.

The C linkage changes 800 agreement coordinates, 1,392 numerical nonrejection
coordinates and 1,872 cabinet-consent coordinates. The unchanged 11/15 profile
boundary therefore does not mean that every proposal remains unchanged.

The full-policy, no-buffer agenda experiment is unchanged in all four variants:
fixed-agenda agreements after release at total rejection 1/2/3/4 are
37,440 / 31,680 / 20,160 / 0 of 40,320. Starting at counter two, release at total
three yields 20,160 fixed-agenda agreements; an exhaustive re-search oracle
yields 40,320. Release after total four is too late in either case.

## Files and execution

`summary.json` and `completion-summary.csv` contain the headline results.
`minimum-costs.json` and `reachability.json` use explicit column schemas.
`diagnostics.json` retains edge and minimum-cost witnesses. Every evaluated
proposal is retained in deterministic `proposal-records.jsonl.gz`.
`process.json` and `process-counts.csv` retain agenda outcomes and witnesses.

From the repository root:

```sh
python3 -B -m unittest tests.test_completion_sensitivity -v
python3 -B experiments/run_completion_sensitivity.py
```

The experiment uses only Python standard libraries. It requires the existing
electoral profiles and original bargaining outputs for its full baseline audit.
It must therefore run after those experiments in a fresh reproduction directory.
The manifest binds the admitted inputs, implementation, tests and outputs.
The design is retrospective and conditional; it is not a political prediction or
an empirical validation of either completion.
