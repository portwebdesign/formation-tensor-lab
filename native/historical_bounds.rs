//! Exact full-party investiture bounds for a fixed, independently supplied cohort.
//!
//! This calculator accepts only voting weights and explicit nonrejection facts.
//! It has no observed-ballot or cabinet-membership input. The caller must admit
//! the cohort and facts from evidence available at the chosen cutoff, and must
//! assess actual absences, mixed party ballots and unaffiliated members in a
//! separate evaluation gate. The `Party` DTO supplies weights; it does not turn
//! an aggregate of unaffiliated members into a cohesive political party.
//!
//! Unknown units range over no and nonrejection (yes or abstention). Counts are
//! numbers of assignments, not probabilities. The exact possible-no set is
//! retained because its minimum/maximum interval can contain unattainable sums.

use crate::government::{Party, REJECTION_THRESHOLD, RIKSDAG_SEATS};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

pub const MAX_VOTING_UNITS: usize = 12;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BoundFact {
    pub party: String,
    pub nonreject: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum IdentifiedOutcome {
    Accepted,
    Rejected,
    Undetermined,
}

impl IdentifiedOutcome {
    pub fn code(self) -> &'static str {
        match self {
            Self::Accepted => "accepted",
            Self::Rejected => "rejected",
            Self::Undetermined => "undetermined",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Bounds {
    /// Sorted unique exact sums, not every integer between the endpoints.
    pub possible_no: Vec<u16>,
    pub no_min: u16,
    pub no_max: u16,
    pub assignments: u64,
    pub accepting_assignments: u64,
    pub identified_outcome: IdentifiedOutcome,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BoundsError {
    InvalidUnitCount { actual: usize, maximum: usize },
    InvalidPartyId { party: String },
    DuplicateParty { party: String },
    ZeroSeatParty { party: String },
    SeatSumOverflow,
    WrongSeatTotal { actual: u32 },
    UnknownFactParty { party: String },
    DuplicateFact { party: String },
    EmptyPossibilityFamily,
}

impl fmt::Display for BoundsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for BoundsError {}

fn valid_id(value: &str) -> bool {
    !value.is_empty() && value.trim() == value && !value.chars().any(char::is_control)
}

/// Enumerate at most 2^12 assignments, preserving exact possible no totals.
///
/// Duplicate facts, including identical duplicates, are invalid. Opposite facts
/// are therefore rejected rather than silently overwritten. Valid fact inputs
/// always admit at least one assignment; no empty-family guarantee is produced.
pub fn evaluate(parties: &[Party], facts: &[BoundFact]) -> Result<Bounds, BoundsError> {
    if parties.is_empty() || parties.len() > MAX_VOTING_UNITS {
        return Err(BoundsError::InvalidUnitCount {
            actual: parties.len(),
            maximum: MAX_VOTING_UNITS,
        });
    }
    let mut index = BTreeMap::new();
    let mut total = 0u32;
    for (position, party) in parties.iter().enumerate() {
        if !valid_id(&party.id) {
            return Err(BoundsError::InvalidPartyId {
                party: party.id.clone(),
            });
        }
        if index.insert(party.id.as_str(), position).is_some() {
            return Err(BoundsError::DuplicateParty {
                party: party.id.clone(),
            });
        }
        if party.seats == 0 {
            return Err(BoundsError::ZeroSeatParty {
                party: party.id.clone(),
            });
        }
        total = total
            .checked_add(u32::from(party.seats))
            .ok_or(BoundsError::SeatSumOverflow)?;
    }
    if total != u32::from(RIKSDAG_SEATS) {
        return Err(BoundsError::WrongSeatTotal { actual: total });
    }
    let mut seen = BTreeSet::new();
    let (mut fact_mask, mut nonreject_mask) = (0u64, 0u64);
    for fact in facts {
        let position =
            *index
                .get(fact.party.as_str())
                .ok_or_else(|| BoundsError::UnknownFactParty {
                    party: fact.party.clone(),
                })?;
        if !seen.insert(fact.party.as_str()) {
            return Err(BoundsError::DuplicateFact {
                party: fact.party.clone(),
            });
        }
        let bit = 1u64 << position;
        fact_mask |= bit;
        if fact.nonreject {
            nonreject_mask |= bit;
        }
    }
    let mut possible = BTreeSet::new();
    let (mut assignments, mut accepting_assignments) = (0u64, 0u64);
    for code in 0..(1u64 << parties.len()) {
        if code & fact_mask != nonreject_mask {
            continue;
        }
        // Positive weights were checked to total 349, so every subset fits u16.
        let nonrejecting: u16 = parties
            .iter()
            .enumerate()
            .filter(|(position, _)| code & (1u64 << position) != 0)
            .map(|(_, party)| party.seats)
            .sum();
        let no = RIKSDAG_SEATS - nonrejecting;
        possible.insert(no);
        assignments += 1;
        if no < REJECTION_THRESHOLD {
            accepting_assignments += 1;
        }
    }
    let no_min = possible
        .first()
        .copied()
        .ok_or(BoundsError::EmptyPossibilityFamily)?;
    let no_max = possible
        .last()
        .copied()
        .ok_or(BoundsError::EmptyPossibilityFamily)?;
    let identified_outcome = if accepting_assignments == assignments {
        IdentifiedOutcome::Accepted
    } else if accepting_assignments == 0 {
        IdentifiedOutcome::Rejected
    } else {
        IdentifiedOutcome::Undetermined
    };
    Ok(Bounds {
        possible_no: possible.into_iter().collect(),
        no_min,
        no_max,
        assignments,
        accepting_assignments,
        identified_outcome,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn weights(values: &[(&str, u16)]) -> Vec<Party> {
        values
            .iter()
            .map(|(id, seats)| Party {
                id: (*id).into(),
                seats: *seats,
            })
            .collect()
    }
    fn fact(party: &str, nonreject: bool) -> BoundFact {
        BoundFact {
            party: party.into(),
            nonreject,
        }
    }

    #[test]
    fn exact_174_and_175_no_boundary_uses_full_chamber() {
        let parties = weights(&[("A", 174), ("B", 175)]);
        let reject = evaluate(&parties, &[fact("A", true), fact("B", false)]).unwrap();
        assert_eq!(reject.possible_no, [175]);
        assert_eq!(reject.assignments, 1);
        assert_eq!(reject.accepting_assignments, 0);
        assert_eq!(reject.identified_outcome.code(), "rejected");
        let accept = evaluate(&parties, &[fact("A", false), fact("B", true)]).unwrap();
        assert_eq!(accept.possible_no, [174]);
        assert_eq!(accept.accepting_assignments, 1);
        assert_eq!(accept.identified_outcome.code(), "accepted");
    }

    #[test]
    fn unknown_facts_have_maximal_interval_but_identify_no_outcome() {
        let result = evaluate(&weights(&[("A", 174), ("B", 175)]), &[]).unwrap();
        assert_eq!(result.possible_no, [0, 174, 175, 349]);
        assert_eq!((result.no_min, result.no_max), (0, 349));
        assert_eq!(result.assignments, 4);
        assert_eq!(result.accepting_assignments, 2);
        assert_eq!(result.identified_outcome.code(), "undetermined");
    }

    #[test]
    fn exact_possible_set_preserves_gaps_inside_the_bounds() {
        let result = evaluate(&weights(&[("A", 100), ("B", 249)]), &[]).unwrap();
        assert_eq!(result.possible_no, [0, 100, 249, 349]);
        assert!(result.no_min <= 174 && 174 <= result.no_max);
        assert!(!result.possible_no.contains(&174));
    }

    #[test]
    fn one_known_stance_can_identify_acceptance_or_rejection() {
        let parties = weights(&[("A", 175), ("B", 174)]);
        let accept = evaluate(&parties, &[fact("A", true)]).unwrap();
        assert_eq!(accept.possible_no, [0, 174]);
        assert_eq!(accept.assignments, 2);
        assert_eq!(accept.accepting_assignments, 2);
        assert_eq!(accept.identified_outcome, IdentifiedOutcome::Accepted);
        let reject = evaluate(&parties, &[fact("A", false)]).unwrap();
        assert_eq!(reject.possible_no, [175, 349]);
        assert_eq!(reject.identified_outcome, IdentifiedOutcome::Rejected);
    }

    #[test]
    fn duplicate_identical_and_opposite_facts_both_fail() {
        let parties = weights(&[("A", 175), ("B", 174)]);
        for second in [true, false] {
            assert!(matches!(
                evaluate(&parties, &[fact("A", true), fact("A", second)]),
                Err(BoundsError::DuplicateFact { .. })
            ));
        }
        assert!(matches!(
            evaluate(&parties, &[fact("missing", true)]),
            Err(BoundsError::UnknownFactParty { .. })
        ));
    }

    #[test]
    fn invalid_weights_and_identifiers_fail_before_enumeration() {
        assert!(matches!(
            evaluate(&[], &[]),
            Err(BoundsError::InvalidUnitCount { .. })
        ));
        assert!(matches!(
            evaluate(&weights(&[("A", 349), ("B", 0)]), &[]),
            Err(BoundsError::ZeroSeatParty { .. })
        ));
        assert!(matches!(
            evaluate(&weights(&[("A", 174), ("A", 175)]), &[]),
            Err(BoundsError::DuplicateParty { .. })
        ));
        for id in ["", " A", "A\nB"] {
            assert!(matches!(
                evaluate(&weights(&[(id, 349)]), &[]),
                Err(BoundsError::InvalidPartyId { .. })
            ));
        }
        assert!(matches!(
            evaluate(&weights(&[("A", u16::MAX), ("B", u16::MAX)]), &[]),
            Err(BoundsError::WrongSeatTotal { actual: 131070 })
        ));
    }

    #[test]
    fn twelve_unit_limit_is_bounded_and_thirteenth_is_rejected() {
        let mut parties: Vec<_> = (0..12)
            .map(|n| Party {
                id: format!("U{n}"),
                seats: if n == 0 { 338 } else { 1 },
            })
            .collect();
        let result = evaluate(&parties, &[]).unwrap();
        assert_eq!(result.assignments, 4096);
        assert_eq!(result.identified_outcome, IdentifiedOutcome::Undetermined);
        parties.push(Party {
            id: "U12".into(),
            seats: 1,
        });
        assert!(matches!(
            evaluate(&parties, &[]),
            Err(BoundsError::InvalidUnitCount { actual: 13, .. })
        ));
    }

    #[test]
    fn input_order_does_not_change_exact_sums_or_assignment_counts() {
        let mut parties = weights(&[("A", 100), ("B", 80), ("C", 90), ("D", 79)]);
        let mut facts = vec![fact("A", true), fact("D", false)];
        let original = evaluate(&parties, &facts).unwrap();
        parties.reverse();
        facts.reverse();
        assert_eq!(original, evaluate(&parties, &facts).unwrap());
    }
}
