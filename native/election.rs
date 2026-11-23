//! Exact party-seat allocation with explicit 2014 and 2018+ rule regimes.
//!
//! Input votes are final valid party votes, including parties below the threshold.
//! Fixed district quotas must come from the election-year official decision.
//! No candidate/personal-vote allocation is attempted. A lottery is required by
//! law for tied relevant quotients; this initial engine returns `Error::Tie`
//! rather than secretly substituting alphabetical order or randomness.
//!
//! In the 2018+ regime, the protected overhang exception (a surplus that cannot be returned because
//! all remaining awards are in districts with fewer than three fixed seats)
//! returns `UnsupportedProtectedOverhang`, explicitly, pending separate proof
//! and official fixtures for that exceptional residual calculation.

use std::cmp::Ordering;
use std::collections::HashSet;
use std::fmt;

/// Reviewed parliamentary apportionment regimes. The year binding deliberately
/// accepts only the election years admitted by this research project.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RuleVersion {
    /// First divisor 7/5; excess fixed seats remain with the party, whose votes
    /// and fixed seats are removed before recalculating other entitlements.
    Swedish2014,
    /// First divisor 6/5 and the fixed-seat return/reallocation procedure.
    Swedish2018Plus,
}

impl RuleVersion {
    pub fn for_year(year: u16) -> Result<Self, Error> {
        match year {
            2014 => Ok(Self::Swedish2014),
            2018 | 2022 | 2026 => Ok(Self::Swedish2018Plus),
            _ => Err(Error::InvalidInput(format!(
                "no reviewed apportionment regime for election year {year}"
            ))),
        }
    }

    pub fn code(self) -> &'static str {
        match self {
            Self::Swedish2014 => "swedish_2014",
            Self::Swedish2018Plus => "swedish_2018_plus",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Party {
    pub id: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct District {
    pub id: String,
    pub fixed_seats: u16,
    /// Party order is exactly `Election::parties` order.
    pub votes: Vec<u64>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Election {
    pub parties: Vec<Party>,
    pub districts: Vec<District>,
    pub total_seats: u16,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Allocation {
    pub national: Vec<u16>,
    /// District × party; after any returned fixed seats are reallocated.
    pub fixed: Vec<Vec<u16>>,
    /// District × party; additional adjustment/leveling seats.
    pub leveling: Vec<Vec<u16>>,
    pub eligible_national: Vec<bool>,
    pub national_votes: Vec<u64>,
    pub valid_votes: u64,
    pub returned_seats: u16,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Error {
    InvalidInput(String),
    Tie {
        context: String,
        contenders: Vec<String>,
    },
    NoEligibleParty(String),
    UnsupportedProtectedOverhang {
        party: String,
        remaining_surplus: u16,
    },
    Invariant(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidInput(s) => write!(f, "invalid election input: {s}"),
            Self::Tie {
                context,
                contenders,
            } => write!(
                f,
                "official lottery required at {context}: {}",
                contenders.join(", ")
            ),
            Self::NoEligibleParty(s) => write!(f, "no eligible positive-vote party: {s}"),
            Self::UnsupportedProtectedOverhang {
                party,
                remaining_surplus,
            } => write!(
                f,
                "protected overhang not yet supported: {party}, surplus {remaining_surplus}"
            ),
            Self::Invariant(s) => write!(f, "allocation invariant failed: {s}"),
        }
    }
}
impl std::error::Error for Error {}

#[derive(Clone, Copy, Debug)]
struct Quotient {
    numerator: u128,
    denominator: u128,
}

impl Quotient {
    fn compare(self, other: Self) -> Ordering {
        // At most 5*u64::MAX times (2*u16::MAX+1): strictly below u128::MAX.
        (self.numerator * other.denominator).cmp(&(other.numerator * self.denominator))
    }
}

#[cfg(test)]
fn quotient(votes: u64, already_awarded: u16, leveling: bool) -> Quotient {
    quotient_with_rules(
        votes,
        already_awarded,
        leveling,
        RuleVersion::Swedish2018Plus,
    )
}

fn quotient_with_rules(
    votes: u64,
    already_awarded: u16,
    leveling: bool,
    rules: RuleVersion,
) -> Quotient {
    if already_awarded == 0 {
        if leveling {
            Quotient {
                numerator: votes as u128,
                denominator: 1,
            }
        } else {
            Quotient {
                numerator: 5 * votes as u128,
                denominator: match rules {
                    RuleVersion::Swedish2014 => 7,
                    RuleVersion::Swedish2018Plus => 6,
                },
            }
        }
    } else {
        Quotient {
            numerator: votes as u128,
            denominator: 2 * already_awarded as u128 + 1,
        }
    }
}

fn add_votes(a: u64, b: u64) -> Result<u64, Error> {
    a.checked_add(b)
        .ok_or_else(|| Error::InvalidInput("vote total exceeds u64".into()))
}

/// Check the scope used for an actual Riksdag fixture. The generic allocator
/// also accepts small seat counts for independently hand-checkable examples.
pub fn validate_riksdag(election: &Election) -> Result<(), Error> {
    if election.total_seats != 349
        || election.districts.len() != 29
        || election
            .districts
            .iter()
            .map(|d| u32::from(d.fixed_seats))
            .sum::<u32>()
            != 310
    {
        return Err(Error::InvalidInput(
            "Riksdag requires 349 seats, 29 constituencies, and 310 fixed seats".into(),
        ));
    }
    validate(election).map(|_| ())
}

fn validate(e: &Election) -> Result<(Vec<u64>, Vec<u64>, u64), Error> {
    if e.parties.is_empty() || e.districts.is_empty() || e.total_seats == 0 {
        return Err(Error::InvalidInput(
            "nonempty parties/districts and positive total seats required".into(),
        ));
    }
    let unique_parties: HashSet<_> = e.parties.iter().map(|p| &p.id).collect();
    let unique_districts: HashSet<_> = e.districts.iter().map(|d| &d.id).collect();
    if unique_parties.len() != e.parties.len() || e.parties.iter().any(|p| p.id.trim().is_empty()) {
        return Err(Error::InvalidInput(
            "party IDs must be unique and nonempty".into(),
        ));
    }
    if unique_districts.len() != e.districts.len()
        || e.districts.iter().any(|d| d.id.trim().is_empty())
    {
        return Err(Error::InvalidInput(
            "district IDs must be unique and nonempty".into(),
        ));
    }
    let mut national = vec![0; e.parties.len()];
    let mut district_totals = Vec::with_capacity(e.districts.len());
    let mut fixed_count: u32 = 0;
    for district in &e.districts {
        if district.votes.len() != e.parties.len() {
            return Err(Error::InvalidInput(format!(
                "party-vector length in {}",
                district.id
            )));
        }
        let mut total = 0;
        for (p, &votes) in district.votes.iter().enumerate() {
            national[p] = add_votes(national[p], votes)?;
            total = add_votes(total, votes)?;
        }
        if total == 0 {
            return Err(Error::InvalidInput(format!(
                "zero valid votes in {}",
                district.id
            )));
        }
        district_totals.push(total);
        fixed_count += u32::from(district.fixed_seats);
    }
    if fixed_count > u32::from(e.total_seats) {
        return Err(Error::InvalidInput(
            "fixed quotas exceed chamber size".into(),
        ));
    }
    let total = national.iter().try_fold(0, |a, &v| add_votes(a, v))?;
    Ok((national, district_totals, total))
}

/// Select a unique maximum (or minimum). Irrelevant losing ties do not require
/// a lottery; tied winners do, even when input order happens to be stable.
fn select(
    candidates: &[(usize, Quotient, String)],
    smallest: bool,
    context: &str,
) -> Result<usize, Error> {
    let Some(first) = candidates.first() else {
        return Err(Error::NoEligibleParty(context.into()));
    };
    let mut best = first;
    let mut tied = vec![first.2.clone()];
    for candidate in candidates.iter().skip(1) {
        let order = candidate.1.compare(best.1);
        let better = if smallest {
            order == Ordering::Less
        } else {
            order == Ordering::Greater
        };
        if better {
            best = candidate;
            tied.clear();
            tied.push(candidate.2.clone());
        } else if order == Ordering::Equal {
            tied.push(candidate.2.clone());
        }
    }
    if tied.len() > 1 {
        return Err(Error::Tie {
            context: context.into(),
            contenders: tied,
        });
    }
    Ok(best.0)
}

fn apportion(
    votes: &[u64],
    eligible: &[bool],
    seats: u16,
    ids: &[String],
    context: &str,
    rules: RuleVersion,
) -> Result<Vec<u16>, Error> {
    let mut counts = vec![0; votes.len()];
    for seat in 0..seats {
        let candidates: Vec<_> = votes
            .iter()
            .enumerate()
            .filter(|&(p, &v)| eligible[p] && v > 0)
            .map(|(p, &v)| {
                (
                    p,
                    quotient_with_rules(v, counts[p], false, rules),
                    ids[p].clone(),
                )
            })
            .collect();
        let p = select(&candidates, false, &format!("{context}, seat {}", seat + 1))?;
        counts[p] += 1;
    }
    Ok(counts)
}

/// Pre-2018 law retains every fixed award. Exclude overrepresented parties and
/// their fixed seats, then repeat national apportionment among the remainder.
/// Removing more seats than a party's entitlement cannot increase the other
/// entitlements, so already overrepresented parties remain locked. At most one
/// new exclusion per party is possible; no unbounded adjustment loop is used.
fn legacy_national_target(
    votes: &[u64],
    eligible: &[bool],
    fixed: &[u16],
    total: u16,
    regional_reserved: u16,
    ids: &[String],
) -> Result<Vec<u16>, Error> {
    let mut active = eligible.to_vec();
    let mut locked = vec![0u16; votes.len()];
    let mut reserved = regional_reserved;
    for _ in 0..=votes.len() {
        let target = apportion(
            votes,
            &active,
            total - reserved,
            ids,
            "2014 national entitlement after fixed overhang exclusion",
            RuleVersion::Swedish2014,
        )?;
        let overrepresented: Vec<_> = (0..votes.len())
            .filter(|&p| active[p] && fixed[p] > target[p])
            .collect();
        if overrepresented.is_empty() {
            return Ok((0..votes.len())
                .map(|p| if active[p] { target[p] } else { locked[p] })
                .collect());
        }
        for p in overrepresented {
            active[p] = false;
            locked[p] = fixed[p];
            reserved = reserved
                .checked_add(fixed[p])
                .ok_or_else(|| Error::Invariant("2014 reserved-seat overflow".into()))?;
            if reserved > total {
                return Err(Error::Invariant(
                    "2014 reserved seats exceed chamber".into(),
                ));
            }
        }
    }
    Err(Error::Invariant(
        "2014 overhang exclusion did not terminate".into(),
    ))
}

/// Allocate fixed and adjustment seats. A successful value is exact under the
/// documented rules and contains no guessed lottery result.
pub fn allocate(e: &Election) -> Result<Allocation, Error> {
    allocate_with_rules(e, RuleVersion::Swedish2018Plus)
}

/// Allocate under an explicitly selected historical regime. This does not
/// infer a year from vote magnitudes or silently apply modern law to 2014.
pub fn allocate_with_rules(e: &Election, rules: RuleVersion) -> Result<Allocation, Error> {
    let (national_votes, district_totals, valid_votes) = validate(e)?;
    let np = e.parties.len();
    let nd = e.districts.len();
    let ids: Vec<_> = e.parties.iter().map(|p| p.id.clone()).collect();
    let eligible_national: Vec<_> = national_votes
        .iter()
        .map(|&v| 100 * v as u128 >= 4 * valid_votes as u128)
        .collect();
    let mut fixed = Vec::with_capacity(nd);
    for (d, district) in e.districts.iter().enumerate() {
        let eligible_local: Vec<_> = district
            .votes
            .iter()
            .enumerate()
            .map(|(p, &v)| {
                eligible_national[p] || 100 * v as u128 >= 12 * district_totals[d] as u128
            })
            .collect();
        fixed.push(apportion(
            &district.votes,
            &eligible_local,
            district.fixed_seats,
            &ids,
            &format!("fixed {}", district.id),
            rules,
        )?);
    }
    let mut fixed_totals: Vec<u16> = (0..np)
        .map(|p| fixed.iter().map(|row| row[p]).sum())
        .collect();
    let regional_reserved: u16 = (0..np)
        .filter(|&p| !eligible_national[p])
        .map(|p| fixed_totals[p])
        .sum();
    let target = if rules == RuleVersion::Swedish2014 {
        legacy_national_target(
            &national_votes,
            &eligible_national,
            &fixed_totals,
            e.total_seats,
            regional_reserved,
            &ids,
        )?
    } else {
        apportion(
            &national_votes,
            &eligible_national,
            e.total_seats - regional_reserved,
            &ids,
            "national proportional entitlement",
            rules,
        )?
    };

    // Return each nationally eligible party's excess fixed awards, weakest last
    // awarded quotient first, preserving districts whose original quota is <3.
    let mut returned_seats = 0;
    if rules == RuleVersion::Swedish2018Plus {
        let mut vacancies = vec![0u16; nd];
        for p in 0..np {
            if !eligible_national[p] {
                continue;
            }
            while fixed_totals[p] > target[p] {
                let candidates: Vec<_> = (0..nd)
                    .filter(|&d| e.districts[d].fixed_seats >= 3 && fixed[d][p] > 0)
                    .map(|d| {
                        (
                            d,
                            quotient_with_rules(
                                e.districts[d].votes[p],
                                fixed[d][p] - 1,
                                false,
                                rules,
                            ),
                            e.districts[d].id.clone(),
                        )
                    })
                    .collect();
                if candidates.is_empty() {
                    return Err(Error::UnsupportedProtectedOverhang {
                        party: ids[p].clone(),
                        remaining_surplus: fixed_totals[p] - target[p],
                    });
                }
                let d = select(
                    &candidates,
                    true,
                    &format!("return fixed award for {}", ids[p]),
                )?;
                fixed[d][p] -= 1;
                fixed_totals[p] -= 1;
                vacancies[d] += 1;
                returned_seats += 1;
            }
        }

        // Vallag 14:4b uses the highest next quotient globally across affected
        // districts, not district-code order, with both local vacancy and national
        // entitlement caps. Regional-only parties already retain their fixed awards.
        while vacancies.iter().any(|&n| n > 0) {
            let mut candidates = Vec::new();
            for d in 0..nd {
                if vacancies[d] == 0 {
                    continue;
                }
                for p in 0..np {
                    if eligible_national[p]
                        && fixed_totals[p] < target[p]
                        && e.districts[d].votes[p] > 0
                    {
                        candidates.push((
                            d * np + p,
                            quotient_with_rules(e.districts[d].votes[p], fixed[d][p], false, rules),
                            format!("{}/{}", e.districts[d].id, ids[p]),
                        ));
                    }
                }
            }
            let index = select(&candidates, false, "reallocation of returned fixed awards")?;
            let (d, p) = (index / np, index % np);
            fixed[d][p] += 1;
            fixed_totals[p] += 1;
            vacancies[d] -= 1;
        }
    }

    // Consistency of divisor allocation means excluding parties whose fixed
    // total exactly meets their national target leaves the other target counts
    // unchanged. Protected overhang is rejected above rather than approximated.
    let mut leveling = vec![vec![0u16; np]; nd];
    for p in 0..np {
        if !eligible_national[p] {
            continue;
        }
        for number in 0..(target[p] - fixed_totals[p]) {
            let candidates: Vec<_> = (0..nd)
                .filter(|&d| e.districts[d].votes[p] > 0)
                .map(|d| {
                    (
                        d,
                        quotient_with_rules(
                            e.districts[d].votes[p],
                            fixed[d][p] + leveling[d][p],
                            true,
                            rules,
                        ),
                        e.districts[d].id.clone(),
                    )
                })
                .collect();
            let d = select(
                &candidates,
                false,
                &format!("leveling {} seat {}", ids[p], number + 1),
            )?;
            leveling[d][p] += 1;
        }
    }
    let national: Vec<u16> = (0..np)
        .map(|p| (0..nd).map(|d| fixed[d][p] + leveling[d][p]).sum())
        .collect();
    if national.iter().map(|&n| u32::from(n)).sum::<u32>() != u32::from(e.total_seats) {
        return Err(Error::Invariant("chamber total".into()));
    }
    for (row, district) in fixed.iter().zip(&e.districts) {
        if row.iter().map(|&n| u32::from(n)).sum::<u32>() != u32::from(district.fixed_seats) {
            return Err(Error::Invariant(format!(
                "fixed district quota {}",
                district.id
            )));
        }
    }
    Ok(Allocation {
        national,
        fixed,
        leveling,
        eligible_national,
        national_votes,
        valid_votes,
        returned_seats,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn election(votes: &[&[u64]], fixed: &[u16], total: u16) -> Election {
        Election {
            parties: (0..votes[0].len())
                .map(|p| Party {
                    id: format!("P{p}"),
                })
                .collect(),
            districts: votes
                .iter()
                .enumerate()
                .map(|(d, v)| District {
                    id: format!("D{d}"),
                    fixed_seats: fixed[d],
                    votes: v.to_vec(),
                })
                .collect(),
            total_seats: total,
        }
    }

    #[test]
    fn initial_and_later_divisors_are_exact() {
        assert_eq!(
            quotient(12, 0, false).compare(Quotient {
                numerator: 10,
                denominator: 1
            }),
            Ordering::Equal
        );
        assert_eq!(
            quotient(12, 1, false).compare(Quotient {
                numerator: 4,
                denominator: 1
            }),
            Ordering::Equal
        );
        assert_eq!(
            quotient(12, 2, false).compare(Quotient {
                numerator: 12,
                denominator: 5
            }),
            Ordering::Equal
        );
        assert_eq!(
            quotient(12, 0, true).compare(Quotient {
                numerator: 12,
                denominator: 1
            }),
            Ordering::Equal
        );
    }

    #[test]
    fn historical_year_binding_is_explicit_and_unknown_years_fail() {
        assert_eq!(
            RuleVersion::for_year(2014).unwrap(),
            RuleVersion::Swedish2014
        );
        for year in [2018, 2022, 2026] {
            assert_eq!(
                RuleVersion::for_year(year).unwrap(),
                RuleVersion::Swedish2018Plus
            );
        }
        for year in [0, 2010, 2016, 2030] {
            assert!(RuleVersion::for_year(year).is_err());
        }
        assert_eq!(RuleVersion::Swedish2014.code(), "swedish_2014");
        assert_eq!(RuleVersion::Swedish2018Plus.code(), "swedish_2018_plus");
    }

    #[test]
    fn first_divisor_changes_real_awards_between_historical_regimes() {
        // The second seat compares 100/3 with 45/1.4 or 45/1.2.
        let e = election(&[&[100, 45]], &[2], 2);
        let old = allocate_with_rules(&e, RuleVersion::Swedish2014).unwrap();
        let modern = allocate_with_rules(&e, RuleVersion::Swedish2018Plus).unwrap();
        assert_eq!(old.fixed, [vec![2, 0]]);
        assert_eq!(old.national, [2, 0]);
        assert_eq!(modern.fixed, [vec![1, 1]]);
        assert_eq!(modern.national, [1, 1]);
        assert_eq!(allocate(&e).unwrap(), modern);
        assert_eq!(
            quotient_with_rules(14, 0, false, RuleVersion::Swedish2014).compare(Quotient {
                numerator: 10,
                denominator: 1
            }),
            Ordering::Equal
        );
    }

    #[test]
    fn historical_overhang_is_retained_instead_of_returned() {
        let e = election(&[&[90, 10], &[10, 489]], &[5, 3], 10);
        let old = allocate_with_rules(&e, RuleVersion::Swedish2014).unwrap();
        assert_eq!(old.returned_seats, 0);
        assert_eq!(old.fixed, [vec![5, 0], vec![0, 3]]);
        assert_eq!(old.leveling, [vec![0, 0], vec![0, 2]]);
        assert_eq!(old.national, [5, 5]);
        let modern = allocate(&e).unwrap();
        assert_eq!(modern.returned_seats, 3);
        assert_eq!(modern.national, [2, 8]);
    }

    #[test]
    fn historical_small_district_overhang_needs_no_modern_return_exception() {
        let e = election(&[&[90, 10], &[10, 489]], &[2, 3], 6);
        let old = allocate_with_rules(&e, RuleVersion::Swedish2014).unwrap();
        assert_eq!(old.returned_seats, 0);
        assert_eq!(old.national, [2, 4]);
        assert!(matches!(
            allocate(&e),
            Err(Error::UnsupportedProtectedOverhang { .. })
        ));
    }

    #[test]
    fn historical_entitlement_repeats_exclusion_until_no_party_is_overrepresented() {
        let target = legacy_national_target(
            &[600, 300, 100],
            &[true, true, true],
            &[7, 3, 0],
            10,
            0,
            &["A".into(), "B".into(), "C".into()],
        )
        .unwrap();
        assert_eq!(target, [7, 3, 0]);
    }

    #[test]
    fn historical_first_leveling_in_zero_fixed_district_uses_raw_votes() {
        let a = allocate_with_rules(
            &election(&[&[880, 120], &[700, 300]], &[1, 2], 8),
            RuleVersion::Swedish2014,
        )
        .unwrap();
        assert_eq!(a.fixed, [vec![1, 0], vec![2, 0]]);
        assert_eq!(a.leveling[0][1], 1);
        assert_eq!(a.leveling[1][1], 1);
        assert_eq!(a.national, [6, 2]);
    }

    #[test]
    fn historical_regional_party_seats_are_reserved_before_national_allocation() {
        let a = allocate_with_rules(
            &election(&[&[860, 140], &[9000, 0]], &[5, 3], 10),
            RuleVersion::Swedish2014,
        )
        .unwrap();
        assert_eq!(a.eligible_national, [true, false]);
        assert_eq!(a.fixed[0], [4, 1]);
        assert_eq!(a.national, [9, 1]);
        assert!(a.leveling.iter().all(|row| row[1] == 0));
        assert!(matches!(
            allocate_with_rules(&election(&[&[10, 10]], &[1], 1), RuleVersion::Swedish2014),
            Err(Error::Tie { .. })
        ));
    }

    #[test]
    fn quotient_does_not_lose_single_vote_above_float_precision() {
        let large = 1u64 << 54;
        assert_eq!(
            quotient(large + 1, 0, false).compare(quotient(large, 0, false)),
            Ordering::Greater
        );
        assert_eq!(
            quotient(u64::MAX, u16::MAX, false).compare(quotient(u64::MAX - 1, u16::MAX, false)),
            Ordering::Greater
        );
    }

    #[test]
    fn national_four_percent_is_inclusive_and_denominator_includes_small_parties() {
        let e = election(&[&[9600, 400]], &[0], 25);
        let a = allocate(&e).unwrap();
        assert_eq!(a.eligible_national, [true, true]);
        assert_eq!(a.national, [24, 1]);
        let b = allocate(&election(&[&[9601, 399]], &[0], 25)).unwrap();
        assert_eq!(b.eligible_national, [true, false]);
        assert_eq!(b.national, [25, 0]);
    }

    #[test]
    fn regional_twelve_percent_party_keeps_fixed_seat_but_gets_no_leveling() {
        // Regional P1 has exactly 12% in D0, 1.2% nationally.
        let a = allocate(&election(&[&[880, 120], &[9000, 0]], &[5, 3], 10)).unwrap();
        assert_eq!(a.eligible_national, [true, false]);
        assert_eq!(a.fixed[0], [4, 1]);
        assert_eq!(a.national, [9, 1]);
        assert!(a.leveling.iter().all(|row| row[1] == 0));
        let b = allocate(&election(&[&[881, 119], &[9000, 0]], &[5, 3], 10)).unwrap();
        assert_eq!(b.national, [10, 0]);
    }

    #[test]
    fn relevant_tie_requires_official_lottery() {
        assert!(matches!(
            allocate(&election(&[&[10, 10]], &[1], 1)),
            Err(Error::Tie { .. })
        ));
    }

    #[test]
    fn excess_fixed_awards_are_returned_and_refilled_before_leveling() {
        // P0 initially wins all five seats in D0, but its national entitlement
        // is two of ten. Three weak awards are returned in D0 and given to P1.
        let a = allocate(&election(&[&[90, 10], &[10, 489]], &[5, 3], 10)).unwrap();
        assert_eq!(a.returned_seats, 3);
        assert_eq!(a.fixed, [vec![2, 3], vec![0, 3]]);
        assert_eq!(a.leveling, [vec![0, 0], vec![0, 2]]);
        assert_eq!(a.national, [2, 8]);
    }

    #[test]
    fn returns_in_multiple_districts_use_global_next_quotient_order() {
        // Exact Fraction-arithmetic fixture for quotient ordering.
        // Processing D0 before D1 incorrectly gives P0 its retained seat in D0.
        let a = allocate(&election(
            &[&[685, 41, 22], &[959, 95, 8], &[13, 1302, 12292]],
            &[3, 3, 3],
            11,
        ))
        .unwrap();
        assert_eq!(a.returned_seats, 5);
        assert_eq!(a.national, [1, 1, 9]);
        assert_eq!(a.fixed, [vec![0, 0, 3], vec![1, 1, 1], vec![0, 0, 3]]);
        assert_eq!(a.leveling, [vec![0, 0, 0], vec![0, 0, 0], vec![0, 0, 2]]);
    }

    #[test]
    fn protected_two_seat_constituency_surplus_is_explicitly_unsupported() {
        // P0 wins two fixed seats in D0 but has national entitlement one.
        // Its surplus cannot legally be returned from an original quota of two.
        let err = allocate(&election(&[&[90, 10], &[10, 489]], &[2, 3], 6)).unwrap_err();
        assert!(matches!(
            err,
            Error::UnsupportedProtectedOverhang {
                remaining_surplus: 1,
                ..
            }
        ));
    }

    #[test]
    fn first_leveling_placement_uses_divisor_one_in_zero_fixed_district() {
        // P1 wins no fixed seat in D0. P1's first adjustment compares 120/1
        // against 300/3=100 in D1, so it must be placed in D0. Using 1.2 would
        // create a false tie here.
        let a = allocate(&election(&[&[880, 120], &[700, 300]], &[1, 2], 8)).unwrap();
        assert_eq!(a.fixed, [vec![1, 0], vec![1, 1]]);
        assert_eq!(a.leveling[0][1], 1);
        assert_eq!(a.national, [6, 2]);
    }

    #[test]
    fn zero_votes_do_not_receive_seats() {
        let a = allocate(&election(&[&[100, 0]], &[1], 2)).unwrap();
        assert_eq!(a.national, [2, 0]);
        assert!(allocate(&election(&[&[0, 0]], &[1], 2)).is_err());
    }

    #[test]
    fn invalid_dimensions_duplicate_ids_and_overflow_are_rejected() {
        let mut e = election(&[&[100, 10]], &[1], 2);
        e.districts[0].votes.pop();
        assert!(allocate(&e).is_err());
        let mut e = election(&[&[100, 10]], &[1], 2);
        e.parties[1].id = e.parties[0].id.clone();
        assert!(allocate(&e).is_err());
        assert!(allocate(&election(&[&[u64::MAX, 1]], &[1], 2)).is_err());
        assert!(allocate(&election(&[&[100, 10]], &[3], 2)).is_err());
    }

    #[test]
    fn riksdag_shape_is_separate_from_small_examples() {
        assert!(validate_riksdag(&election(&[&[100, 10]], &[1], 2)).is_err());
    }
}
