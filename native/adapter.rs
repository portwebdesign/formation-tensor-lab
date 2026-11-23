//! Native full-election adapter for the workbench. The reviewed core is unchanged.
//!
//! CLI: workbench_election DERIVED_DIRECTORY YEAR
//! stdin: headerless district_id<TAB>donor_id<TAB>recipient_id<TAB>voters.
//! Empty input is the official baseline. Every transfer is within one district.
//! Success verifies turnout and net half-L1 cost; no political support is inferred.
//! Relevant ties and unsupported exceptions remain typed incomplete results.
#[allow(dead_code)]
#[path = "election.rs"]
mod election;
#[allow(dead_code)]
#[path = "government.rs"]
mod government;
#[allow(dead_code)]
#[path = "historical_bounds.rs"]
mod historical_bounds;

use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{self, Read};
use std::path::Path;

const MAX_INPUT: usize = 32_768;
const MAX_MOVES: usize = 256;

#[derive(Debug)]
struct Failure {
    kind: &'static str,
    message: String,
}
impl Failure {
    fn invalid(message: impl Into<String>) -> Self {
        Self {
            kind: "invalid_input",
            message: message.into(),
        }
    }
    fn invariant(message: impl Into<String>) -> Self {
        Self {
            kind: "invariant",
            message: message.into(),
        }
    }
}
impl From<election::Error> for Failure {
    fn from(error: election::Error) -> Self {
        let kind = match &error {
            election::Error::Tie { .. } => "tie",
            election::Error::UnsupportedProtectedOverhang { .. } => "unsupported",
            election::Error::Invariant(_) => "invariant",
            _ => "invalid_input",
        };
        Self {
            kind,
            message: error.to_string(),
        }
    }
}
type Result<T> = std::result::Result<T, Failure>;

fn quote(text: &str) -> String {
    let mut out = String::from("\"");
    for c in text.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn unsigned(raw: &str, name: &str) -> Result<u64> {
    if raw.is_empty() || !raw.bytes().all(|b| b.is_ascii_digit()) {
        return Err(Failure::invalid(format!(
            "{name} must be unsigned decimal digits"
        )));
    }
    raw.parse()
        .map_err(|_| Failure::invalid(format!("{name} exceeds u64")))
}

fn small(raw: &str, name: &str) -> Result<u16> {
    u16::try_from(unsigned(raw, name)?).map_err(|_| Failure::invalid(format!("{name} exceeds u16")))
}

fn table(path: &Path, header: &str) -> Result<Vec<Vec<String>>> {
    let text = fs::read_to_string(path)
        .map_err(|e| Failure::invalid(format!("cannot read {}: {e}", path.display())))?;
    let mut lines = text.lines();
    if lines.next() != Some(header) {
        return Err(Failure::invalid(format!(
            "invalid table header: {}",
            path.display()
        )));
    }
    let width = header.split('\t').count();
    let mut out = Vec::new();
    for (line, row) in lines.enumerate() {
        let values: Vec<_> = row.split('\t').map(str::to_owned).collect();
        if values.len() != width || values.iter().any(|s| s.is_empty()) {
            return Err(Failure::invalid(format!(
                "malformed {} row {}",
                path.display(),
                line + 2
            )));
        }
        out.push(values);
    }
    Ok(out)
}

#[derive(Debug, PartialEq, Eq)]
struct Move {
    district: String,
    donor: String,
    recipient: String,
    voters: u64,
}

fn parse_moves(input: &str) -> Result<Vec<Move>> {
    if input.len() > MAX_INPUT {
        return Err(Failure::invalid("transfer input exceeds 32768 bytes"));
    }
    let mut out = Vec::new();
    for row in input.lines() {
        if out.len() >= MAX_MOVES {
            return Err(Failure::invalid("at most 256 transfer rows supported"));
        }
        let values: Vec<_> = row.split('\t').collect();
        if values.len() != 4
            || values[..3]
                .iter()
                .any(|s| s.is_empty() || s.trim() != *s || s.chars().any(char::is_control))
        {
            return Err(Failure::invalid("transfer row requires four TSV columns"));
        }
        let voters = unsigned(values[3], "transfer voters")?;
        if voters == 0 || values[1] == values[2] {
            return Err(Failure::invalid(
                "transfer must be positive with distinct parties",
            ));
        }
        out.push(Move {
            district: values[0].to_owned(),
            donor: values[1].to_owned(),
            recipient: values[2].to_owned(),
            voters,
        });
    }
    Ok(out)
}

fn apply_moves(e: &mut election::Election, moves: &[Move]) -> Result<u64> {
    let party: HashMap<_, _> = e
        .parties
        .iter()
        .enumerate()
        .map(|(i, p)| (p.id.clone(), i))
        .collect();
    let district: HashMap<_, _> = e
        .districts
        .iter()
        .enumerate()
        .map(|(i, d)| (d.id.clone(), i))
        .collect();
    let original: Vec<_> = e.districts.iter().map(|d| d.votes.clone()).collect();
    let totals: Vec<u128> = original
        .iter()
        .map(|v| v.iter().map(|&n| u128::from(n)).sum())
        .collect();
    let mut cost = 0u64;
    for m in moves {
        let d = *district
            .get(&m.district)
            .ok_or_else(|| Failure::invalid("unknown transfer district"))?;
        let from = *party
            .get(&m.donor)
            .ok_or_else(|| Failure::invalid("unknown donor party"))?;
        let to = *party
            .get(&m.recipient)
            .ok_or_else(|| Failure::invalid("unknown recipient party"))?;
        let votes = &mut e.districts[d].votes;
        votes[from] = votes[from]
            .checked_sub(m.voters)
            .ok_or_else(|| Failure::invalid("donor supply exceeded"))?;
        votes[to] = votes[to]
            .checked_add(m.voters)
            .ok_or_else(|| Failure::invalid("recipient votes overflow"))?;
        cost = cost
            .checked_add(m.voters)
            .ok_or_else(|| Failure::invalid("transfer cost exceeds u64"))?;
    }
    let mut l1 = 0u128;
    for (index, (district_votes, prior)) in e.districts.iter().zip(original.iter()).enumerate() {
        if district_votes
            .votes
            .iter()
            .map(|&n| u128::from(n))
            .sum::<u128>()
            != totals[index]
        {
            return Err(Failure::invariant("district turnout changed"));
        }
        for (&a, &b) in district_votes.votes.iter().zip(prior.iter()) {
            l1 += u128::from(a.abs_diff(b));
        }
    }
    if l1 != 2 * u128::from(cost) {
        return Err(Failure::invalid(
            "listed transfers contain cancellation: net half-L1 differs from declared cost",
        ));
    }
    Ok(cost)
}

fn calculate(root: &Path, year: u16, input: &str) -> Result<String> {
    let rules = election::RuleVersion::for_year(year)?;
    let parties = table(
        &root.join("parties.tsv"),
        "party_id\tlabel\tvotes\texpected_total",
    )?;
    let districts = table(
        &root.join("districts.tsv"),
        "district_id\tlabel\tfixed_seats",
    )?;
    let votes = table(&root.join("votes.tsv"), "district_id\tparty_id\tvotes")?;
    let pi: HashMap<_, _> = parties
        .iter()
        .enumerate()
        .map(|(i, p)| (p[0].clone(), i))
        .collect();
    let di: HashMap<_, _> = districts
        .iter()
        .enumerate()
        .map(|(i, d)| (d[0].clone(), i))
        .collect();
    if pi.len() != parties.len() || di.len() != districts.len() {
        return Err(Failure::invalid("duplicate party or district identifiers"));
    }
    let mut e = election::Election {
        parties: parties
            .iter()
            .map(|p| election::Party { id: p[0].clone() })
            .collect(),
        districts: districts
            .iter()
            .map(|d| {
                Ok(election::District {
                    id: d[0].clone(),
                    fixed_seats: small(&d[2], "fixed seats")?,
                    votes: vec![0; parties.len()],
                })
            })
            .collect::<Result<Vec<_>>>()?,
        total_seats: 349,
    };
    let mut seen = HashSet::new();
    for v in &votes {
        let d = *di
            .get(&v[0])
            .ok_or_else(|| Failure::invalid("unknown district in vote table"))?;
        let p = *pi
            .get(&v[1])
            .ok_or_else(|| Failure::invalid("unknown party in vote table"))?;
        if !seen.insert((d, p)) {
            return Err(Failure::invalid("duplicate vote cell"));
        }
        e.districts[d].votes[p] = unsigned(&v[2], "votes")?;
    }
    if seen.len() != parties.len() * districts.len() {
        return Err(Failure::invalid(
            "complete derived district-party vote table required",
        ));
    }
    election::validate_riksdag(&e)?;
    let before = election::allocate_with_rules(&e, rules)?;
    for (i, p) in parties.iter().enumerate() {
        if before.national[i] != small(&p[3], "expected seats")?
            || before.national_votes[i] != unsigned(&p[2], "expected votes")?
        {
            return Err(Failure::invariant(format!(
                "official baseline mismatch for {}",
                p[0]
            )));
        }
    }
    let cost = apply_moves(&mut e, &parse_moves(input)?)?;
    let after = election::allocate_with_rules(&e, rules)?;
    if before.valid_votes != after.valid_votes {
        return Err(Failure::invariant("valid national turnout changed"));
    }
    let party_json: Vec<_> = parties.iter().enumerate().map(|(i,p)|format!(
        "{{\"id\":{},\"label\":{},\"votes_before\":{},\"votes_after\":{},\"seats_before\":{},\"seats_after\":{},\"eligible_before\":{},\"eligible_after\":{}}}",
        quote(&p[0]),quote(&p[1]),before.national_votes[i],after.national_votes[i],before.national[i],after.national[i],before.eligible_national[i],after.eligible_national[i]
    )).collect();
    let district_json: Vec<_> = districts
        .iter()
        .map(|d| {
            format!(
                "{{\"id\":{},\"label\":{},\"fixed_seats\":{}}}",
                quote(&d[0]),
                quote(&d[1]),
                d[2]
            )
        })
        .collect();
    Ok(format!(
        "{{\"status\":\"passed\",\"year\":{year},\"rule_version\":{},\"cost_voters\":{cost},\"valid_votes\":{},\"district_turnout_preserved\":true,\"eligibility_preserved\":{},\"returned_before\":{},\"returned_after\":{},\"parties\":[{}],\"districts\":[{}]}}",
        quote(rules.code()),
        after.valid_votes,
        before.eligible_national == after.eligible_national,
        before.returned_seats,
        after.returned_seats,
        party_json.join(","),
        district_json.join(",")
    ))
}

fn run() -> Result<String> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 3 {
        return Err(Failure::invalid(
            "usage: workbench_election DERIVED_DIRECTORY YEAR; headerless transfers on stdin",
        ));
    }
    let year = small(&args[2], "year")?;
    let mut input = String::new();
    io::stdin()
        .lock()
        .take((MAX_INPUT + 1) as u64)
        .read_to_string(&mut input)
        .map_err(|e| Failure::invalid(format!("cannot read UTF-8 transfer input: {e}")))?;
    calculate(Path::new(&args[1]), year, &input)
}

fn main() {
    match run() {
        Ok(value) => println!("{value}"),
        Err(error) => {
            println!(
                "{{\"status\":\"not_completed\",\"error_type\":{},\"message\":{}}}",
                quote(error.kind),
                quote(&error.message)
            );
            std::process::exit(2);
        }
    }
}

#[cfg(test)]
mod adapter_tests {
    use super::*;
    fn toy() -> election::Election {
        election::Election {
            parties: vec![
                election::Party { id: "A".into() },
                election::Party { id: "B".into() },
            ],
            districts: vec![election::District {
                id: "d".into(),
                fixed_seats: 3,
                votes: vec![10, 20],
            }],
            total_seats: 3,
        }
    }
    #[test]
    fn empty_baseline_and_transfer_parsing_are_explicit() {
        assert!(parse_moves("").unwrap().is_empty());
        assert_eq!(parse_moves("d\tA\tB\t3\n").unwrap()[0].voters, 3);
        for bad in [
            "d\tA\tB\t0",
            "d\tA\tA\t1",
            "d\tA\tB\t-1",
            "d\tA\tB\t1.5",
            "d\tA\tB\t+1",
            "d\tA\tB\t1e2",
            "d\tA\tB\t18446744073709551616",
            "\n",
            "district\tdonor\trecipient\tvoters",
        ] {
            assert!(parse_moves(bad).is_err(), "{bad}");
        }
    }
    #[test]
    fn conservation_and_net_cost_are_checked() {
        let mut e = toy();
        assert_eq!(
            apply_moves(&mut e, &parse_moves("d\tA\tB\t3").unwrap()).unwrap(),
            3
        );
        assert_eq!(e.districts[0].votes, [7, 23]);
        let mut e = toy();
        assert!(apply_moves(&mut e, &parse_moves("d\tA\tB\t3\nd\tB\tA\t1").unwrap()).is_err());
        let mut e = toy();
        assert!(apply_moves(&mut e, &parse_moves("d\tA\tB\t11").unwrap()).is_err());
    }
    #[test]
    fn errors_keep_lottery_and_unsupported_types() {
        let tie: Failure = election::Error::Tie {
            context: "x".into(),
            contenders: vec!["A".into()],
        }
        .into();
        let unsupported: Failure = election::Error::UnsupportedProtectedOverhang {
            party: "A".into(),
            remaining_surplus: 1,
        }
        .into();
        assert_eq!(tie.kind, "tie");
        assert_eq!(unsupported.kind, "unsupported");
    }
    #[test]
    fn json_strings_are_escaped() {
        assert_eq!(
            quote("a\"b\\c\n\t\u{0001}ö"),
            "\"a\\\"b\\\\c\\n\\t\\u0001ö\""
        );
    }
}
