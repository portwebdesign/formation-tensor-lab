"""Exact eligibility guard for at most four omitted outside-party votes.

This retrospective robustness check concerns the completed interaction grid.
It does not certify unrestricted vote changes, old minimum-cost searches, or
arbitrary corrections to the data packet.
"""
import csv
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = {
    'schema': 'formation-tensor.minor-correction-protocol.v1',
    'study_kind': 'Retrospective robustness check of the stated input-correction class.',
    'maximum_added_valid_votes': 4,
    'correction_domain': 'Nonnegative vote additions to parties outside the original eight nationally eligible parties, in any admitted constituencies; no inside-party vote correction, quota change, removal, or voter-transfer change.',
    'target_domain': 'Every completed cell of the six-pair 2026 electorate-transfer tensor.',
    'national_threshold_scaled': '100 * party_votes >= 4 * all_valid_votes',
    'regional_threshold_scaled': '100 * party_votes >= 12 * constituency_valid_votes',
    'proof': 'Retain the eligible set using threshold gaps; eligible-party vote counts and all divisor comparisons then remain unchanged.',
    'excluded_claims': ['Unrestricted data-error robustness', 'Recertification of previous global minimum-cost searches', 'Political response to corrected vote totals'],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_tsv(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def residual_gaps(inside_national, outside_national, outside_regional, added_votes=4):
    """Conservative residual gaps after any allowed addition distribution.

    An inside party receives no extra votes, so its scaled national margin
    loses at most 4*k. An outside party receiving all k additions has the
    worst national loss (100-4)*k and regional loss (100-12)*k.
    """
    if any(type(x) is not int for x in (inside_national, outside_national, outside_regional, added_votes)) or added_votes < 0:
        raise ValueError('Integer scaled gaps and a nonnegative addition cap are required.')
    residual = {'inside_national': inside_national - 4*added_votes,
                'outside_national': outside_national - 96*added_votes,
                'outside_regional': outside_regional - 88*added_votes}
    return {**residual, 'eligible_set_retained': residual['inside_national'] >= 0 and residual['outside_national'] > 0 and residual['outside_regional'] > 0}


def run_experiment(root=ROOT, output_dir=None):
    root = Path(root).resolve()
    out = Path(output_dir).resolve() if output_dir else root/'results/input-correction'
    out.mkdir(parents=True, exist_ok=True)
    protocol_path = root/'data/elections/minor-correction-protocol.json'
    if protocol_path.exists():
        if json.loads(protocol_path.read_text()) != PROTOCOL:
            raise ValueError('The correction protocol changed; a new version is required.')
    else:
        protocol_path.write_text(json.dumps(PROTOCOL, ensure_ascii=False, indent=2)+'\n')
    base = root/'data/elections/2026'
    parties = read_tsv(base/'parties.tsv')
    source_rows = read_tsv(base/'votes.tsv')
    metadata = json.loads((base/'metadata.json').read_text())
    party_ids = {p['label']: p['party_id'] for p in parties}
    national = {p['party_id']: int(p['votes']) for p in parties}
    core_labels = {p['label'] for p in parties if int(p['expected_total']) > 0}
    core_ids = {party_ids[p] for p in core_labels}
    outside_ids = set(national)-core_ids
    assert len(core_ids) == 8
    total = sum(national.values())
    assert total == metadata['valid_votes']
    district_totals = {}
    local = {}
    for r in source_rows:
        key = r['district_id'], r['party_id']
        assert key not in local
        local[key] = int(r['votes'])
        district_totals[key[0]] = district_totals.get(key[0], 0)+local[key]
    assert len(local) == len(national)*len(district_totals)
    assert all(sum(local[d,p] for d in district_totals) == national[p] for p in national)
    minimum_outside_national = min((4*total-100*national[p], p) for p in outside_ids)
    minimum_outside_regional = min((12*district_totals[d]-100*local[d,p], d, p)
                                  for d in district_totals for p in outside_ids)
    native_path = root/'results/interactions/native-replays.jsonl.gz'
    tensor_path = root/'results/interactions/tensor.json'
    valid_groups = {}
    weakest_inside = None
    log_count = 0
    with gzip.open(native_path, 'rt') as stream:
        for line in stream:
            record = json.loads(line)
            log_count += 1
            assert hashlib.sha256(record['input'].encode()).hexdigest() == record['group']
            native = record['native']
            if native.get('status') != 'passed':
                continue
            if any(p['eligible_before'] != p['eligible_after'] for p in native['parties']):
                continue
            assert native['valid_votes'] == total and native['district_turnout_preserved']
            assert sum(p['votes_after'] for p in native['parties']) == total
            expected_national = dict(national)
            for move in record['input'].splitlines():
                district, donor, recipient, amount = move.split('\t')
                assert district in district_totals and donor in core_ids and recipient in core_ids
                assert int(amount) >= 0
                expected_national[donor] -= int(amount)
                expected_national[recipient] += int(amount)
            for p in native['parties']:
                identifier = party_ids[p['label']]
                assert p['votes_before'] == national[identifier]
                assert p['votes_after'] == expected_national[identifier]
                if identifier in outside_ids:
                    assert p['votes_before'] == p['votes_after'] == national[identifier]
                else:
                    item = (100*p['votes_after']-4*total, p['label'], record['group'])
                    if weakest_inside is None or item < weakest_inside:
                        weakest_inside = item
            valid_groups[record['group']] = True
    tensor = json.loads(tensor_path.read_text())
    completed = [c for c in tensor['cells'] if c['status'] == 'passed']
    assert all(c['group'] in valid_groups for c in completed)
    assert {c['group'] for c in completed} == set(valid_groups)
    assert weakest_inside is not None
    residual = residual_gaps(weakest_inside[0], minimum_outside_national[0], minimum_outside_regional[0], 4)
    if not residual['eligible_set_retained']:
        raise ValueError('The declared four-vote correction guard is inconclusive.')
    summary = {
        'schema': 'formation-tensor.minor-correction-guard.v1', 'status': 'passed',
        'protocol_sha256': sha(protocol_path),
        'maximum_added_valid_votes': 4, 'baseline_valid_votes': total,
        'native_input_records_checked': log_count,
        'completed_unique_input_tables': len(valid_groups),
        'completed_tensor_coordinates': len(completed),
        'minimum_scaled_gaps': {
            'inside_national': {'gap': weakest_inside[0], 'party': weakest_inside[1], 'native_group': weakest_inside[2]},
            'outside_national': {'gap': minimum_outside_national[0], 'party_id': minimum_outside_national[1]},
            'outside_regional': {'gap': minimum_outside_regional[0], 'district_id': minimum_outside_regional[1], 'party_id': minimum_outside_regional[2]},
        },
        'maximum_scaled_gap_losses': {'inside_national': 16, 'outside_national': 384, 'outside_regional': 352},
        'residual_scaled_gaps': residual,
        'all_completed_seat_responses_invariant': True,
        'proof': [
            'Each transfer changes only original eligible-party votes and preserves each constituency total.',
            'For at most k additions outside that set, each inside national gap loses at most 4k, each outside national gap at most 96k, and each outside regional gap at most 88k.',
            'The recorded residual gaps retain all eight nationally eligible parties and exclude every outside party from both national and regional eligibility.',
            'Eligible-party votes, fixed quotas and their exact quotient comparisons are unchanged; the full allocation and all seat-vector-based responses are unchanged.',
        ],
        'scope': PROTOCOL['correction_domain'],
        'not_recertified': PROTOCOL['excluded_claims'],
    }
    target = out/'summary.json'
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    inputs = [base/'parties.tsv', base/'votes.tsv', base/'metadata.json', base/'districts.tsv',
              protocol_path, native_path, tensor_path, Path(__file__).resolve(), root/'tests/test_minor_correction.py']
    files = {str(p.relative_to(root)): sha(p) for p in inputs}
    if out == root/'results/input-correction':
        files['results/input-correction/summary.json'] = sha(target)
    manifest = {'schema': 'formation-tensor.result-manifest.v1', 'status': 'passed',
                'files': files, 'input_sha256': {str(p.relative_to(root)): sha(p) for p in inputs},
                'output_sha256': {'summary.json': sha(target)}}
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    result = run_experiment(ROOT)
    print(json.dumps({'status': result['status'], 'completed_tensor_coordinates': result['completed_tensor_coordinates'],
                      'all_completed_seat_responses_invariant': result['all_completed_seat_responses_invariant'],
                      'residual_scaled_gaps': result['residual_scaled_gaps']}))
