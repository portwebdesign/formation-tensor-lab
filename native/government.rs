//! Conditional cabinet feasibility under Sweden's negative investiture rule.
//!
//! `cabinet` denotes cabinet membership. `external_nonrejecting` denotes an
//! outside party voting yes OR abstaining; these actions have the same effect
//! on the 175-no rejection threshold, but neither implies cabinet membership.
//! All remaining seats are assumed to vote no, and party groups are assumed
//! cohesive. Actual absences, individual defections, ordinary legislation and
//! budget votes are outside this model. Constraints are scenario assumptions,
//! not inferred political facts. This module computes no Myerson value.

use std::fmt;

pub const RIKSDAG_SEATS: u16 = 349;
pub const REJECTION_THRESHOLD: u16 = 175;
pub const MAX_ENUMERATION_ASSIGNMENTS: u64 = 1_000_000;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Party {
    pub id: String,
    pub seats: u16,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Constraints {
    /// Undirected pairs forbidden from belonging to the same cabinet.
    pub forbidden_cabinet_pairs: Vec<(usize, usize)>,
    /// Directed (external party, cabinet party) pairs: the first refuses to
    /// support/tolerate any cabinet containing the second.
    pub external_nonrejection_vetoes: Vec<(usize, usize)>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Arrangement {
    pub cabinet: u64,
    pub external_nonrejecting: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Violation {
    ForbiddenCabinetPair { left: usize, right: usize },
    ExternalNonrejectionVeto { external: usize, cabinet: usize },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Assessment {
    pub arrangement: Arrangement,
    pub cabinet_seats: u16,
    pub external_nonrejecting_seats: u16,
    pub opposition_seats: u16,
    pub passes_investiture_rule: bool,
    pub violations: Vec<Violation>,
}

impl Assessment {
    pub fn feasible(&self) -> bool {
        self.passes_investiture_rule && self.violations.is_empty()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ModelError {
    InvalidPartyCount,
    EmptyOrDuplicatePartyId,
    ZeroSeatParty,
    WrongSeatTotal {
        actual: u32,
    },
    InvalidConstraint {
        left: usize,
        right: usize,
    },
    EmptyCabinet,
    OverlappingRoles,
    UnknownPartyBits,
    EnumerationLimit {
        assignments: Option<u64>,
        maximum: u64,
    },
}

impl fmt::Display for ModelError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for ModelError {}

#[derive(Clone, Debug)]
pub struct Model {
    parties: Vec<Party>,
    constraints: Constraints,
    all: u64,
}

impl Model {
    /// Construct a full 349-seat party-block scenario. Party order defines bits.
    pub fn new(parties: Vec<Party>, constraints: Constraints) -> Result<Self, ModelError> {
        if parties.is_empty() || parties.len() > 63 {
            return Err(ModelError::InvalidPartyCount);
        }
        let mut ids = std::collections::HashSet::new();
        for party in &parties {
            if party.id.trim().is_empty() || !ids.insert(party.id.clone()) {
                return Err(ModelError::EmptyOrDuplicatePartyId);
            }
            if party.seats == 0 {
                return Err(ModelError::ZeroSeatParty);
            }
        }
        let actual: u32 = parties.iter().map(|p| u32::from(p.seats)).sum();
        if actual != u32::from(RIKSDAG_SEATS) {
            return Err(ModelError::WrongSeatTotal { actual });
        }
        for &(left, right) in constraints
            .forbidden_cabinet_pairs
            .iter()
            .chain(constraints.external_nonrejection_vetoes.iter())
        {
            if left >= parties.len() || right >= parties.len() || left == right {
                return Err(ModelError::InvalidConstraint { left, right });
            }
        }
        let all = (1_u64 << parties.len()) - 1;
        Ok(Self {
            parties,
            constraints,
            all,
        })
    }

    pub fn parties(&self) -> &[Party] {
        &self.parties
    }

    pub fn constraints(&self) -> &Constraints {
        &self.constraints
    }

    pub fn mask_for(&self, ids: &[&str]) -> Result<u64, ModelError> {
        let mut mask = 0;
        for id in ids {
            let position = self
                .parties
                .iter()
                .position(|p| p.id == *id)
                .ok_or(ModelError::UnknownPartyBits)?;
            let bit = 1_u64 << position;
            if mask & bit != 0 {
                return Err(ModelError::OverlappingRoles);
            }
            mask |= bit;
        }
        Ok(mask)
    }

    fn seats(&self, mask: u64) -> u16 {
        self.parties
            .iter()
            .enumerate()
            .filter(|(i, _)| mask & (1_u64 << i) != 0)
            .map(|(_, party)| party.seats)
            .sum()
    }

    pub fn evaluate(&self, arrangement: Arrangement) -> Result<Assessment, ModelError> {
        let Arrangement {
            cabinet,
            external_nonrejecting,
        } = arrangement;
        if (cabinet | external_nonrejecting) & !self.all != 0 {
            return Err(ModelError::UnknownPartyBits);
        }
        if cabinet == 0 {
            return Err(ModelError::EmptyCabinet);
        }
        if cabinet & external_nonrejecting != 0 {
            return Err(ModelError::OverlappingRoles);
        }
        let cabinet_seats = self.seats(cabinet);
        let external_nonrejecting_seats = self.seats(external_nonrejecting);
        let opposition_seats = RIKSDAG_SEATS - cabinet_seats - external_nonrejecting_seats;
        let mut violations = Vec::new();
        for &(left, right) in &self.constraints.forbidden_cabinet_pairs {
            if cabinet & (1_u64 << left) != 0 && cabinet & (1_u64 << right) != 0 {
                violations.push(Violation::ForbiddenCabinetPair { left, right });
            }
        }
        for &(external, cabinet_party) in &self.constraints.external_nonrejection_vetoes {
            if external_nonrejecting & (1_u64 << external) != 0
                && cabinet & (1_u64 << cabinet_party) != 0
            {
                violations.push(Violation::ExternalNonrejectionVeto {
                    external,
                    cabinet: cabinet_party,
                });
            }
        }
        Ok(Assessment {
            arrangement,
            cabinet_seats,
            external_nonrejecting_seats,
            opposition_seats,
            passes_investiture_rule: opposition_seats < REJECTION_THRESHOLD,
            violations,
        })
    }

    /// Enumerate possible role assignments, not their probabilities. Even an
    /// unconstrained arrangement is not evidence that a cabinet would form.
    pub fn enumerate_feasible(&self) -> Result<Vec<Arrangement>, ModelError> {
        let assignments = 3_u64.checked_pow(self.parties.len() as u32);
        if assignments.is_none() || assignments.unwrap() > MAX_ENUMERATION_ASSIGNMENTS {
            return Err(ModelError::EnumerationLimit {
                assignments,
                maximum: MAX_ENUMERATION_ASSIGNMENTS,
            });
        }
        let mut feasible = Vec::new();
        for code in 0..assignments.unwrap() {
            let mut rest = code;
            let mut arrangement = Arrangement {
                cabinet: 0,
                external_nonrejecting: 0,
            };
            for i in 0..self.parties.len() {
                match rest % 3 {
                    1 => arrangement.cabinet |= 1_u64 << i,
                    2 => arrangement.external_nonrejecting |= 1_u64 << i,
                    _ => (),
                }
                rest /= 3;
            }
            if arrangement.cabinet != 0 && self.evaluate(arrangement)?.feasible() {
                feasible.push(arrangement);
            }
        }
        Ok(feasible)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn party(id: &str, seats: u16) -> Party {
        Party {
            id: id.into(),
            seats,
        }
    }

    fn example_2022() -> Model {
        Model::new(
            vec![
                party("S", 107),
                party("SD", 73),
                party("M", 68),
                party("V", 24),
                party("C", 24),
                party("KD", 19),
                party("MP", 18),
                party("L", 16),
            ],
            Constraints::default(),
        )
        .unwrap()
    }

    #[test]
    fn actual_2022_nonrejection_total_is_not_confused_with_cabinet_size() {
        let model = example_2022();
        let result = model
            .evaluate(Arrangement {
                cabinet: model.mask_for(&["M", "KD", "L"]).unwrap(),
                external_nonrejecting: model.mask_for(&["SD"]).unwrap(),
            })
            .unwrap();
        assert_eq!(result.cabinet_seats, 103);
        assert_eq!(result.external_nonrejecting_seats, 73);
        assert_eq!(result.opposition_seats, 173);
        assert!(result.feasible());
        // SD actually voted YES. Nonrejecting does not claim abstention.
        let without_external = model
            .evaluate(Arrangement {
                external_nonrejecting: 0,
                ..result.arrangement
            })
            .unwrap();
        assert_eq!(without_external.opposition_seats, 246);
        assert!(!without_external.feasible());
    }

    #[test]
    fn exactly_175_no_rejects_and_174_does_not() {
        let model = Model::new(
            vec![party("A", 174), party("B", 1), party("C", 174)],
            Constraints::default(),
        )
        .unwrap();
        assert!(
            !model
                .evaluate(Arrangement {
                    cabinet: 1,
                    external_nonrejecting: 0
                })
                .unwrap()
                .feasible()
        );
        assert!(
            model
                .evaluate(Arrangement {
                    cabinet: 1,
                    external_nonrejecting: 2
                })
                .unwrap()
                .feasible()
        );
    }

    #[test]
    fn forbidden_pair_is_enforced_even_when_a_third_party_could_connect_them() {
        let model = Model::new(
            vec![party("A", 100), party("B", 100), party("C", 149)],
            Constraints {
                forbidden_cabinet_pairs: vec![(0, 2)],
                ..Constraints::default()
            },
        )
        .unwrap();
        let result = model
            .evaluate(Arrangement {
                cabinet: 7,
                external_nonrejecting: 0,
            })
            .unwrap();
        assert!(result.passes_investiture_rule);
        assert!(!result.feasible());
        assert_eq!(
            result.violations,
            vec![Violation::ForbiddenCabinetPair { left: 0, right: 2 }]
        );
    }

    #[test]
    fn external_veto_has_a_direction() {
        let model = Model::new(
            vec![party("A", 100), party("B", 100), party("C", 149)],
            Constraints {
                external_nonrejection_vetoes: vec![(0, 1)],
                ..Constraints::default()
            },
        )
        .unwrap();
        assert!(
            !model
                .evaluate(Arrangement {
                    cabinet: 2,
                    external_nonrejecting: 1
                })
                .unwrap()
                .feasible()
        );
        assert!(
            model
                .evaluate(Arrangement {
                    cabinet: 1,
                    external_nonrejecting: 2
                })
                .unwrap()
                .feasible()
        );
    }

    #[test]
    fn invalid_role_masks_are_rejected() {
        let model = example_2022();
        assert_eq!(
            model.evaluate(Arrangement {
                cabinet: 0,
                external_nonrejecting: 0
            }),
            Err(ModelError::EmptyCabinet)
        );
        assert_eq!(
            model.evaluate(Arrangement {
                cabinet: 1,
                external_nonrejecting: 1
            }),
            Err(ModelError::OverlappingRoles)
        );
        assert_eq!(
            model.evaluate(Arrangement {
                cabinet: 256,
                external_nonrejecting: 0
            }),
            Err(ModelError::UnknownPartyBits)
        );
    }

    #[test]
    fn invalid_party_data_and_constraints_are_rejected() {
        assert!(matches!(
            Model::new(vec![party("A", 348)], Constraints::default()),
            Err(ModelError::WrongSeatTotal { actual: 348 })
        ));
        assert!(matches!(
            Model::new(vec![party("A", 349), party("B", 0)], Constraints::default()),
            Err(ModelError::ZeroSeatParty)
        ));
        assert!(matches!(
            Model::new(
                vec![party("A", 174), party("A", 175)],
                Constraints::default()
            ),
            Err(ModelError::EmptyOrDuplicatePartyId)
        ));
        assert!(matches!(
            Model::new(
                vec![party("A", 349)],
                Constraints {
                    forbidden_cabinet_pairs: vec![(0, 1)],
                    ..Constraints::default()
                }
            ),
            Err(ModelError::InvalidConstraint { .. })
        ));
    }

    #[test]
    fn single_party_and_bounded_enumeration() {
        let model = Model::new(vec![party("A", 349)], Constraints::default()).unwrap();
        assert_eq!(
            model.enumerate_feasible().unwrap(),
            vec![Arrangement {
                cabinet: 1,
                external_nonrejecting: 0
            }]
        );
        let parties: Vec<Party> = (0..13)
            .map(|i| party(&format!("P{i}"), if i == 0 { 337 } else { 1 }))
            .collect();
        assert!(matches!(
            Model::new(parties, Constraints::default())
                .unwrap()
                .enumerate_feasible(),
            Err(ModelError::EnumerationLimit { .. })
        ));
    }

    #[test]
    fn enumeration_contains_only_unique_feasible_arrangements() {
        let model = example_2022();
        let arrangements = model.enumerate_feasible().unwrap();
        let unique: std::collections::HashSet<(u64, u64)> = arrangements
            .iter()
            .map(|a| (a.cabinet, a.external_nonrejecting))
            .collect();
        assert_eq!(unique.len(), arrangements.len());
        assert!(
            arrangements
                .iter()
                .all(|a| model.evaluate(*a).unwrap().feasible())
        );
        assert!(arrangements.contains(&Arrangement {
            cabinet: model.mask_for(&["M", "KD", "L"]).unwrap(),
            external_nonrejecting: model.mask_for(&["SD"]).unwrap()
        }));
    }
}
