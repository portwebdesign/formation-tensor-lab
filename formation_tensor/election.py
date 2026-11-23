"""Exact joint-intervention response tensors for a fixed electoral domain.

The native allocator determines seats. This module constructs interventions,
checks invariants, and compares complete four-corner responses. Political roles
are explicit experimental inputs and are not inferred from the vote table.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

AMOUNTS = (0, 2000, 5000, 10000, 15000, 20000)
DIRECTIONS = (('MP', 'SD'), ('S', 'M'), ('V', 'KD'), ('C', 'L'))
PAIRS = tuple(combinations(DIRECTIONS, 2))
NONREJECT = ('M', 'KD', 'L', 'SD')
CHAMBER = 349


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def read_tsv(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def pair_id(pair):
    return '__'.join('_'.join(direction) for direction in pair)


def transfer_body(district, party_ids, pair, amount_a, amount_b):
    if not isinstance(district, str) or not district or any(c in district for c in '\t\r\n'):
        raise ValueError('A district identifier is required.')
    if tuple(tuple(d) for d in pair) not in PAIRS:
        raise ValueError('Use a protocol-defined transfer pair.')
    if any(type(x) is not int or x < 0 for x in (amount_a, amount_b)):
        raise ValueError('Transfer amounts must be nonnegative integers.')
    return ''.join(f'{district}\t{party_ids[d]}\t{party_ids[r]}\t{n}\n'
                   for (d, r), n in zip(pair, (amount_a, amount_b)) if n)


def net_transfer_cost(before, after):
    if len(before) != len(after) or any(type(n) is not int or n < 0 for n in list(before) + list(after)):
        raise ValueError('Equal-length nonnegative integer vote tables are required.')
    if sum(before) != sum(after):
        raise ValueError('Valid votes must be conserved.')
    distance = sum(abs(a-b) for a, b in zip(before, after))
    if distance % 2:
        raise ValueError('A conserved integer transfer has an even L1 distance.')
    return distance // 2


def masked(reason, message=None):
    return {'status': 'masked', 'error_type': reason, 'message': message,
            'nonreject_seats': None, 'nonreject_at_least_175': None,
            'seat_vector': None, 'cost_voters': None}


def interpret_native(native, expected_cost, official, valid_votes, baseline=False):
    if native.get('status') != 'passed':
        return masked(native.get('error_type', 'native_failure'), native.get('message'))
    parties = native['parties']
    before = {p['label']: p['seats_before'] for p in parties}
    after = {p['label']: p['seats_after'] for p in parties}
    if len(before) != len(parties) or sum(before.values()) != CHAMBER or sum(after.values()) != CHAMBER:
        raise ValueError('Seat conservation or party identifiers are inconsistent.')
    if any(type(n) is not int or n < 0 for n in list(before.values()) + list(after.values())):
        raise ValueError('Native seat counts must be nonnegative integers.')
    if {p: n for p, n in before.items() if n} != official:
        raise ValueError('Native baseline differs from the admitted official packet.')
    if not native.get('district_turnout_preserved') or native['valid_votes'] != valid_votes:
        raise ValueError('Constituency totals or valid-vote denominator changed.')
    actual_cost = net_transfer_cost([p['votes_before'] for p in parties], [p['votes_after'] for p in parties])
    if native['cost_voters'] != expected_cost or actual_cost != expected_cost:
        raise ValueError('The disjoint same-district transfer cost is inconsistent.')
    if baseline and {p: n for p, n in after.items() if n} != official:
        raise ValueError('Zero-transfer allocation differs from the official baseline.')
    if any(p['eligible_before'] != p['eligible_after'] for p in parties):
        return masked('outside_fixed_eligibility', 'The result changes the admitted eligible-party set.')
    if any(n for p, n in after.items() if p not in official):
        raise ValueError('An outside party acquired seats in the fixed domain.')
    seats = {p: after[p] for p in official}
    target = sum(seats[p] for p in NONREJECT)
    return {'status': 'passed', 'error_type': None, 'message': None,
            'nonreject_seats': target, 'nonreject_at_least_175': target >= 175,
            'seat_vector': seats, 'cost_voters': expected_cost,
            'returned_before': native.get('returned_before'),
            'returned_after': native.get('returned_after')}


def mixed_differences(joint, a_alone, b_alone, baseline):
    corners = [joint, a_alone, b_alone, baseline]
    missing = [i for i, row in enumerate(corners) if row['status'] != 'passed']
    if missing:
        return {'status': 'masked', 'mixed_seats': None, 'mixed_threshold': None,
                'masked_corner_indices': missing}
    g = [row['nonreject_seats'] for row in corners]
    y = [int(row['nonreject_at_least_175']) for row in corners]
    return {'status': 'passed', 'mixed_seats': g[0]-g[1]-g[2]+g[3],
            'mixed_threshold': y[0]-y[1]-y[2]+y[3], 'masked_corner_indices': []}


def protocol():
    return {'schema': 'formation-tensor.interaction-protocol.v1', 'year': 2026,
        'directions': [list(d) for d in DIRECTIONS],
        'pairs': [[list(d) for d in pair] for pair in PAIRS],
        'amount_voters': list(AMOUNTS), 'districts': 'all 29 admitted constituencies',
        'shape': [6, 29, 6, 6],
        'operation': 'Two disjoint transfers in one constituency, applied to the same baseline; full 29-constituency native allocation.',
        'target': {'nonreject_parties': list(NONREJECT), 'threshold': 175,
            'political_status': 'Researcher-fixed hypothetical roles; not a contemporary support agreement.'},
        'cost': 'Within-constituency half-L1; equal to a+b for the four disjoint directions.',
        'interaction': 'f(a,b)-f(a,0)-f(0,b)+f(0,0), separately for seat counts and threshold indicators.',
        'mask': 'All four corners must be valid; insufficient supply, changed eligibility, ties and unsupported computations are typed null.',
        'reporting': 'Every pair, constituency and amount combination retained; equal-cost witnesses selected in source order at every sampled total cost.',
        'beneficiary_unit': 'Unique nonzero native input table, not tensor coordinate; gains at recipient and nonrecipient parties reported separately.',
        'interpretation': 'Retrospective exact counterfactual experiment; no probabilistic support model, empirical voter-flow estimate or global minimum claim.'}


def freeze_protocol(root):
    path = Path(root) / 'data/elections/interaction-protocol.json'
    expected = protocol()
    if path.exists():
        saved = json.loads(path.read_text())
        if saved['protocol'] != expected:
            raise ValueError('Protocol changed; create a new version rather than overwrite it.')
    else:
        write_json(path, {'frozen_at_utc': datetime.now(timezone.utc).isoformat(), 'protocol': expected})
    return sha(path)


def attach_interactions(cells, pairs=PAIRS, amounts=AMOUNTS):
    table = {(c['pair_id'], c['district_id'], c['amount_a'], c['amount_b']): c for c in cells}
    if len(table) != len(cells):
        raise ValueError('Duplicate tensor coordinates.')
    output = []
    for cell in cells:
        prefix = cell['pair_id'], cell['district_id']
        try:
            corners = [cell, table[prefix + (cell['amount_a'], 0)],
                       table[prefix + (0, cell['amount_b'])], table[prefix + (0, 0)]]
        except KeyError as exc:
            raise ValueError('A required tensor corner is missing.') from exc
        output.append({**cell, 'interaction': mixed_differences(*corners)})
    return output


def summary_for(cells):
    interior = [c for c in cells if c['amount_a'] > 0 and c['amount_b'] > 0]
    complete = [c for c in interior if c['interaction']['status'] == 'passed']
    return {'coordinates': len(cells),
        'valid_coordinates': sum(c['status'] == 'passed' for c in cells),
        'masked_coordinates': sum(c['status'] != 'passed' for c in cells),
        'mask_counts': dict(Counter(c['error_type'] for c in cells if c['status'] != 'passed')),
        'interior_coordinates': len(interior), 'valid_interior_four_corners': len(complete),
        'masked_interior_four_corners': len(interior)-len(complete),
        'mixed_seat_histogram': dict(sorted(Counter(str(c['interaction']['mixed_seats']) for c in complete).items())),
        'mixed_threshold_histogram': dict(sorted(Counter(str(c['interaction']['mixed_threshold']) for c in complete).items())),
        'positive_seat_interactions': sum(c['interaction']['mixed_seats'] > 0 for c in complete),
        'negative_seat_interactions': sum(c['interaction']['mixed_seats'] < 0 for c in complete),
        'positive_threshold_interactions': sum(c['interaction']['mixed_threshold'] > 0 for c in complete),
        'negative_threshold_interactions': sum(c['interaction']['mixed_threshold'] < 0 for c in complete)}


def witness_record(cell):
    return {k: cell[k] for k in ('pair_id', 'district_id', 'amount_a', 'amount_b',
        'cost_voters', 'nonreject_seats', 'seat_vector', 'group')}


def summarize(cells):
    result = summary_for(cells)
    pairs = []
    for pair in PAIRS:
        identifier = pair_id(pair)
        rows = [c for c in cells if c['pair_id'] == identifier]
        group = {'pair_id': identifier, 'directions': [list(d) for d in pair], **summary_for(rows)}
        strata = []
        regional_variation = 0
        for a in AMOUNTS:
            for b in AMOUNTS:
                slab = [c for c in rows if c['amount_a'] == a and c['amount_b'] == b]
                values = sorted({c['nonreject_seats'] for c in slab if c['status'] == 'passed'})
                regional_variation += int(len(values) > 1)
                strata.append({'amount_a': a, 'amount_b': b, 'cost_voters': a+b,
                    'valid_districts': sum(c['status'] == 'passed' for c in slab),
                    'nonreject_seat_values': values,
                    'mixed_seat_histogram': dict(Counter(str(c['interaction']['mixed_seats']) for c in slab if c['interaction']['status'] == 'passed')),
                    'mixed_threshold_histogram': dict(Counter(str(c['interaction']['mixed_threshold']) for c in slab if c['interaction']['status'] == 'passed'))})
        group['all_amount_strata'] = strata
        group['regional_consistency'] = {'amount_pairs_with_different_seats_across_valid_districts': regional_variation,
            'scope': 'This sampled fixed-domain target only; donor capacity masks can differ by constituency.'}
        cost_rows = defaultdict(list)
        for row in rows:
            if row['status'] == 'passed':
                cost_rows[row['cost_voters']].append(row)
        witnesses = []
        for cost, options in sorted(cost_rows.items()):
            low = min(options, key=lambda c: c['nonreject_seats'])
            high = max(options, key=lambda c: c['nonreject_seats'])
            if low['nonreject_seats'] != high['nonreject_seats']:
                witnesses.append({'cost_voters': cost, 'min_seats': low['nonreject_seats'],
                    'max_seats': high['nonreject_seats'], 'lower_example': witness_record(low),
                    'upper_example': witness_record(high)})
        group['equal_cost_witnesses'] = witnesses
        successes = [c['cost_voters'] for c in rows if c['nonreject_at_least_175'] is True]
        group['smallest_successful_sampled_cost'] = min(successes) if successes else None
        pairs.append(group)
    result['pairs'] = pairs
    unique = {}
    for row in cells:
        if row['status'] == 'passed' and row['cost_voters'] and row['group'] not in unique:
            unique[row['group']] = row
    diag = Counter()
    examples = []
    for row in unique.values():
        pair = next(pair for pair in PAIRS if pair_id(pair) == row['pair_id'])
        recipients = {direction[1] for direction, amount in zip(pair, (row['amount_a'], row['amount_b'])) if amount}
        gains = {p: n-row['baseline_seats'][p] for p,n in row['seat_vector'].items() if n > row['baseline_seats'][p]}
        extra = {p:n for p,n in gains.items() if p not in recipients}
        diag['nonzero_valid_unique_tables'] += 1
        diag['any_recipient_seat_gain'] += int(bool(set(gains) & recipients))
        diag['any_nonrecipient_seat_gain'] += int(bool(extra))
        diag['all_receiving_parties_without_seat_gain'] += int(not (set(gains) & recipients))
        if extra and len(examples) < 12:
            examples.append({**witness_record(row), 'receiving_parties': sorted(recipients),
                'nonrecipient_seat_gains': extra, 'all_seat_changes': {p:n-row['baseline_seats'][p] for p,n in row['seat_vector'].items() if n != row['baseline_seats'][p]}})
    result['beneficiary_diagnostics'] = {'unit': 'Unique valid nonzero native input table; not an independent election.',
        **dict(diag), 'examples_source_order': examples}
    profiles = {}
    for row in cells:
        if row['status'] != 'passed':
            continue
        key = json.dumps(row['seat_vector'], sort_keys=True, separators=(',', ':'))
        if key not in profiles:
            profiles[key] = {'profile_id': 'seats-' + hashlib.sha256(key.encode()).hexdigest()[:12],
                'seat_vector': row['seat_vector'], 'coordinates': 0,
                'native_groups': set(), 'minimum_sampled_cost': row['cost_voters'],
                'minimum_cost_example': witness_record(row)}
        profile = profiles[key]
        profile['coordinates'] += 1
        profile['native_groups'].add(row['group'])
        if row['cost_voters'] < profile['minimum_sampled_cost']:
            profile['minimum_sampled_cost'] = row['cost_voters']
            profile['minimum_cost_example'] = witness_record(row)
    result['distinct_seat_profiles'] = [
        {**{k:v for k,v in profile.items() if k != 'native_groups'},
         'unique_native_tables': len(profile['native_groups'])} for profile in profiles.values()]
    result['distinct_seat_profile_count'] = len(profiles)
    original = pairs[0]
    expected = {'coordinates':1044, 'valid_coordinates':638, 'masked_coordinates':406,
        'valid_interior_four_corners':388, 'negative_seat_interactions':74,
        'positive_threshold_interactions':73}
    result['original_pair_replication'] = {'expected':expected,
        'actual':{k:original[k] for k in expected},
        'passed':all(original[k] == v for k,v in expected.items())}
    return result


def run_experiment(root, output_dir=None, progress=None):
    root = Path(root).resolve()
    out = Path(output_dir).resolve() if output_dir else root / 'results/interactions'
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    protocol_hash = freeze_protocol(root)
    source = root / 'data/elections/2026'
    parties = read_tsv(source/'parties.tsv'); districts = read_tsv(source/'districts.tsv')
    metadata = json.loads((source/'metadata.json').read_text())
    ids = {p['label']:p['party_id'] for p in parties}
    official = {p['label']:int(p['expected_total']) for p in parties if int(p['expected_total'])}
    votes = {(r['district_id'],r['party_id']):int(r['votes']) for r in read_tsv(source/'votes.tsv')}
    if len(districts) != 29 or sum(official.values()) != CHAMBER or sum(votes.values()) != metadata['valid_votes']:
        raise ValueError('The admitted 2026 packet fails its size or total invariants.')
    input_paths = [source/n for n in ('parties.tsv','votes.tsv','districts.tsv','metadata.json','official_seats.tsv')]
    input_paths += [root/'native'/n for n in ('adapter.rs','election.rs','government.rs','historical_bounds.rs')]
    input_paths += [root/'formation_tensor/election.py',root/'experiments/run_interactions.py',root/'tests/test_election.py',root/'data/elections/interaction-protocol.json']
    inputs = {str(p.relative_to(root)):sha(p) for p in input_paths}
    binary = root / 'build/election'
    binary.parent.mkdir(parents=True, exist_ok=True)
    command = ['rustc','--edition=2024','-O','native/adapter.rs','-o','build/election']
    compiled = subprocess.run(command,cwd=root,capture_output=True,text=True)
    (out/'compile.txt').write_text(compiled.stdout+compiled.stderr)
    if compiled.returncode:
        raise RuntimeError('Native compilation failed: '+compiled.stderr)
    cache = {}; cells = []
    with (out/'native-replays.jsonl.gz').open('wb') as raw_file:
        with gzip.GzipFile(filename='',fileobj=raw_file,mode='wb',mtime=0) as archive:
            for pi,pair in enumerate(PAIRS):
                for di,district in enumerate(districts):
                    did = district['district_id']
                    for ai,a in enumerate(AMOUNTS):
                        for bi,b in enumerate(AMOUNTS):
                            body = transfer_body(did,ids,pair,a,b)
                            group = hashlib.sha256(body.encode()).hexdigest()
                            if group not in cache:
                                native_run = subprocess.run([str(binary),str(source),'2026'],input=body,capture_output=True,text=True,timeout=30)
                                native = json.loads(native_run.stdout)
                                if native.get('status') == 'passed' and native_run.returncode:
                                    raise ValueError('Native success returned a failure exit code.')
                                interpreted = interpret_native(native,a+b,official,metadata['valid_votes'],baseline=not body)
                                cache[group] = interpreted
                                archive.write((json.dumps({'group':group,'input':body,'returncode':native_run.returncode,'native':native},ensure_ascii=False,separators=(',',':'))+'\n').encode())
                            cell = {'index':[pi,di,ai,bi], 'pair_id':pair_id(pair),
                                'district_id':did,'district_label':district['label'],
                                'amount_a':a,'amount_b':b,'declared_cost_voters':a+b,
                                'donor_a_votes':votes[did,ids[pair[0][0]]],
                                'donor_b_votes':votes[did,ids[pair[1][0]]],
                                'group':group,'baseline_seats':official,**cache[group]}
                            cells.append(cell)
                    if progress:
                        progress(f"{pair_id(pair)} {did}: {len(cells)} coordinates, {len(cache)} unique inputs")
    cells = attach_interactions(cells)
    summary = {'schema':'formation-tensor.interaction-summary.v1','status':'passed',
        'protocol_sha256':protocol_hash,'shape':[6,29,6,6],
        'unique_native_tables':len(cache),'baseline_seats':official,
        'hypothetical_nonreject_parties':list(NONREJECT),
        'baseline_nonreject_seats':sum(official[p] for p in NONREJECT),**summarize(cells),
        'scope':'Exact fixed-domain counterfactuals under hypothetical political roles. Coordinates share an election and repeated input tables; not independent events or government probabilities.'}
    if not summary['original_pair_replication']['passed']:
        raise ValueError('The pre-existing pair does not reproduce its recorded counts.')
    tensor = {'schema':'formation-tensor.electoral-response.v1','protocol_sha256':protocol_hash,
        'axes':{'pair':[{'id':pair_id(p),'directions':[list(d) for d in p]} for p in PAIRS],
            'district':districts,'amount_voters':list(AMOUNTS)},'shape':[6,29,6,6],
        'baseline_seats':official,'hypothetical_nonreject_parties':list(NONREJECT),
        'cell_unit':'Within-constituency voters as inputs; national seats and a conditional threshold indicator as responses.',
        'cells':cells}
    write_json(out/'tensor.json',tensor);write_json(out/'summary.json',summary)
    write_json(out/'seat-profiles.json', {'schema':'formation-tensor.seat-profile-coupling.v1',
        'count':summary['distinct_seat_profile_count'], 'profiles':summary['distinct_seat_profiles'],
        'scope':'Deduplicated exact eight-party seat vectors for scenario coupling; not independent elections or political role observations.'})
    fields = ['pair_id','district_id','district_label','amount_a','amount_b','declared_cost_voters',
        'cost_voters','status','error_type','nonreject_seats','nonreject_at_least_175',
        'mixed_seats','mixed_threshold','interaction_status','group']
    with (out/'cells.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for cell in cells:
            row={k:cell.get(k) for k in fields}
            row.update({k:cell['interaction'][k] for k in ('mixed_seats','mixed_threshold')})
            row['interaction_status']=cell['interaction']['status'];writer.writerow(row)
    if any(sha(root/p) != h for p,h in inputs.items()):
        raise ValueError('An input changed during the calculation.')
    write_json(out/'run.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds':time.monotonic()-started,'python':platform.python_version(),
        'compile_command':command,'binary_sha256':sha(binary),
        'unique_native_tables':len(cache)})
    outputs=('tensor.json','summary.json','seat-profiles.json','cells.csv','native-replays.jsonl.gz')
    write_json(out/'manifest.json',{'schema':'formation-tensor.interaction-manifest.v1','status':'passed',
        'protocol_sha256':protocol_hash,'input_sha256':inputs,
        'output_sha256':{n:sha(out/n) for n in outputs},
        'files':{**inputs, **{'results/interactions/'+n:sha(out/n) for n in outputs}},
        'native_engine_modified':False,'roles_are_hypothetical':True})
    return summary
