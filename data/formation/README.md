# Government-formation observations

This is a reviewed chronology of the Swedish formation process as observed on 22 November 2026. It records 19 typed events and 22 sources. It distinguishes three initial exploratory assignments, the resumption of S exploration, an M extension, a general adjournment, two formal nominations, and two rejected prime-ministerial votes. M exploration remained incomplete at the cutoff. Consultations scheduled for 24 November are future events.

The Speaker's 29 October account explicitly connects exploration, formal ballots and pressure on parties as the extra-election endpoint approaches. This provides an actor's explanation for a model mechanism; it does not estimate its causal effect. The episode contains two rejected proposals, rather than two independent formation episodes. Cabinet proposals and conditional party statements are retained separately from observed votes.

## Files

- `events2026.json`: typed chronology, source links, separate actor statements and legal rules.
- `chronology.csv`: flat event table for inspection.
- `source-ledger.json`: source identity, event/publication/update/access fields, response status and hashes.
- `sources/`: 21 successful fresh HTML captures and one explicit HTTP-403 response for the V preliminary platform PDF. The PDF's text was read through web retrieval; this folder does not claim to contain a downloaded PDF.
- `source-specifications.json`: reviewed source metadata before response-capture fields.
- `manifest.json`: hashes of this curated module and its captured sources. Other formation datasets have their own provenance and are bound by the repository's final input manifest.

Publication, event, effective and access dates are different fields. An unknown publication day remains null. Reading an old page today does not establish when its content became historically available. A source's publication date is not a point-in-time data vintage.

## Rebuild and check

From the repository root:

```sh
python3 data/formation/build_curated_events.py
python3 -m unittest discover -s data/formation -p test_curated_events.py -v
```

These commands use the frozen files and perform no network requests. The builder reproduces the reviewed records; it does not independently interpret political statements. The tests verify captured-response hashes, ballot totals, source links, date separation and rejection-counter semantics. The inventory covers the cited official public process, not every private negotiation or telephone call.

Under the Instrument of Government, an exploratory assignment does not consume one of the four formal rejected-proposal opportunities. Approval of a prime minister is distinct from the subsequent change of government. The caretaker continues until the new government takes office.
