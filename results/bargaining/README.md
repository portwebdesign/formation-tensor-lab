# Exact bargaining-state and agenda experiments

This experiment studies consent and proposal reachability in a restricted S-led
cabinet family. Its behavioural clauses are explicit research assumptions
inspired by documented cabinet conditions. They are not coded future party votes.

## State and decision rules

The state `(policy, C_relaxed, V_relaxed)` contains three policy-assent bits and two
composition-condition bits. Policy bit0 is C, bit1 V, bit2 MP. Eight proposed
cabinets contain S and an arbitrary subset of C/V/MP. All 32 states and eight
cabinets are evaluated under four outside-abstention buffers: none, L, KD, L+KD.

S votes Yes. C and MP do not vote No when their modelled policy requirements are
met; C additionally requires V to be outside the proposed cabinet unless the C
composition clause has been relaxed. V does not vote No when its policy condition
is met and either it is nonessential, it is included, or its inclusion clause is
relaxed. Essentiality holds other parties' actions fixed and means
`other_non_No < 175 <= other_non_No + V_seats`. A hopeless proposal is not labelled
essential. Supporting cabinet members vote Yes; supporting nonmembers abstain.
Other parties vote No except the specified external buffer.

Cabinet consent is evaluated separately. Every included party must meet its
policy requirement; included C must also meet its composition condition. The
agreement indicator requires both cabinet consent and fewer than175 No votes.
Budget support is not modelled.

## Exact state graph

Meeting one policy requirement costs one synthetic unit. Releasing either
composition clause costs two. Actions only add concessions. The experiment
evaluates every initial policy mask, four permitted clause-release families and
budgets0 through8. The statement `structural_possible` means an agreement exists
within that permitted action family at an unrestricted cost budget. It does not
mean every government outside the S-led family is covered.

At the pinned baseline and initial policy000:

| External abstention | No composition release allowed | C or V release allowed |
|---|---:|---:|
| None | No agreement | Minimum cost5 |
| L,19 seats | No agreement | Minimum cost5 |
| KD,22 seats | No agreement | Minimum cost4 |
| L+KD,41 seats | Minimum cost2 | Minimum cost2 |

The KD buffer substitutes for one policy-assent requirement because
S99+C25+V30+KD22=176. The L buffer alone gives173 on that same subset. Nine
cost-rescaling scenarios cross policy costs1/2/3 with clause costs1/2/3.
These costs are ordinal experimental units, not measured money or utility.

## Coupling to exact election responses

All26 distinct eight-party seat vectors from the six-pair electorate experiment
enter the same graph. Their S/C/V/MP totals are176 in one profile,175 in ten and
174 in fifteen. With no outside abstention, an agreement is possible somewhere
in the full state graph for the first11 profiles and impossible for the latter15.
No amount of internal concession can repair a missing vote under those roles.

Under full policy assent and strict composition conditions, the anonymous outside
non-No capacity required is24 seats at the baseline. Across all26 profiles the
minimum is24 in five,25 in fourteen and26 in seven. Anonymous capacity refers to
existing outsider seats; it is not assigned to whole parties or to named people.

## Sequential proposal experiment

The process evaluates an explicit cabinet agenda. A failed formal PM proposal
increments the rejection counter. Exploratory proposal evaluations do not.
At four total rejections, the process stops before a later concession could take
effect. The institutional cutoff starts either at zero or at the two actual
rejections recorded by22November2026. The latter permits at most two additional
rejected proposals. These are hypothetical continuations, not fitted forecasts.

A specified pressure rule releases C or V's clause after a total rejection count.
At the cutoff counter2, only future triggers3 and4 are considered. Earlier triggers
are rejected rather than silently assuming their consequences had not occurred.
Every one of the8! agenda orders is counted exactly, compressed to1680 distinct
four-position prefixes, each with24 completions. Counts represent sensitivity to
the designed agenda universe; they are not probabilities of political events.

At baseline, full policy assent, no external buffer and a four-vote horizon:

| Clause released after total rejection | Fixed-agenda agreements /40,320 | Adaptive search agreements /40,320 |
|---:|---:|---:|
| 1 | 37,440 | 40,320 |
| 2 | 31,680 | 40,320 |
| 3 | 20,160 | 40,320 |
| 4 | 0 | 0 |

With the actual cutoff counter2, a release after total rejection3 gives20,160
fixed-agenda agreements or40,320 with adaptive search. A release after rejection4
is too late. Repeating an unchanged blocked proposal four times is the null
control and changes no party condition.

A proposal may be formally nonrejected without consent to its announced cabinet.
The simulator stops with `pm_passed_without_cabinet_agreement` and does not
continue nominating candidates after a passed PM vote. At baseline with L+KD,
full policy assent and no clause release,30,240 agenda orders first identify a
consented proposal;10,080 first pass a proposal whose cabinet lacks consent.
Neither outcome asserts an observed government appointment.

## Pivotality feedback diagnostic

A policy concession need not reduce the number of No votes. At the baseline,
an S-only cabinet with policy mask3 has195 No votes. Meeting MP's policy condition
changes the mask to7, makes V essential, and activates V's still-unmet inclusion
condition; No votes rise to203. There are64 No-increasing proposal edges among
2,560 baseline proposal-edge evaluations. No edge loses an already-existing
agreement, and no agreement-losing edge occurs across all26 profiles. This is a
deductive feature of the stated rules, not evidence that an actual party changed
its vote for this reason. The diagnostic was identified during model development.

## Files and reproduction

- `feasibility-tensor.json`: all26,624 proposal coordinates, roles and consent.
- `reachability.json`:29,952 cost-bounded rows and minimum-cost witnesses.
- `process.json`:9,568 agenda/pressure/patience rows and concrete traces.
- `coupled-profiles.json`: all distinct exact seat-profile coupling summaries.
- `capacity-sensitivity.json`, `cost-sensitivity.json`: boundary/rescaling tables.
- `state-edge-diagnostics.json`: all relevant nonmonotone No-count edges.
- `dashboard.json`: compact columnar interface view; no numerical information
  needed by the interface is fitted or imputed.
- `summary.json`, `process-counts.csv`, `run.json`, `tests.txt`, `manifest.json`.

```sh
python3 -B experiments/run_bargaining.py
python3 -B -m unittest tests.test_bargaining -v
```

Thirteen tests cover independent path-cost formulae, current versus total
rejection counters, four-rejection ordering, exhaustive agenda compression,
source-seat capacity boundaries, consent versus PM nonrejection, and missing
budget interpretation. The full numerical specification was frozen before the
expanded run; baseline unit examples and mathematical checks had already
been examined. The source chronology and all future party votes remain separate.
