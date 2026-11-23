import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from formation_tensor.server import ResearchData


class ResearchDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.data = ResearchData(self.root)
        self.inventory('data/input-manifest.json', {
            'data/formation/events2026.json': {'events': []},
            'data/formation/source-ledger.json': {'sources': []},
            'data/formation/chronology.csv': 'date,type\n2026-11-03,vote\n'})
        for module, members in {'interactions': ('summary.json', 'tensor.json', 'cells.csv'),
                                'bargaining': ('summary.json', 'dashboard.json'), 'parliament': ('summary.json',)}.items():
            self.inventory('results/' + module + '/manifest.json',
                {'results/' + module + '/' + member: {} if member.endswith('.json') else 'a,b\n1,2\n'
                 for member in members})

    def tearDown(self):
        self.temp.cleanup()

    def inventory(self, name, members):
        hashes = {}
        for relative, value in members.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value if isinstance(value, str) else json.dumps(value))
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'files': hashes}))

    def test_snapshot_requires_every_package_and_unchanged_members(self):
        self.assertEqual(self.data.snapshot()['integrity'], 'passed')
        (self.root / 'results/interactions/tensor.json').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'unavailable or changed'):
            self.data.snapshot()

    def test_present_but_unlisted_document_is_refused(self):
        path = self.root / 'results/interactions/manifest.json'
        record = json.loads(path.read_text())
        record['files'].pop('results/interactions/tensor.json')
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'outside the checked inventory'):
            self.data.snapshot()

    def test_relative_and_symlink_escape_are_refused(self):
        for name in ('../outside', '/etc/passwd'):
            with self.assertRaises(ValueError):
                self.data.path(name)
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'payload'
            target.write_text('outside')
            (self.root / 'link').symlink_to(target)
            with self.assertRaises(ValueError):
                self.data.path('link')

    def test_fixed_dataset_download_needs_hash_and_membership(self):
        self.assertEqual(self.data.download('interactions.csv').name, 'cells.csv')
        for name in ('../paper.pdf', 'tensor.json', 'not-known.csv'):
            with self.assertRaises(ValueError):
                self.data.download(name)
        (self.root / 'results/interactions/cells.csv').write_text('changed')
        with self.assertRaises(ValueError):
            self.data.download('interactions.csv')

    def test_paper_download_is_bound_to_release_inventory(self):
        self.inventory('release.json', {'paper/main.pdf': '%PDF-test'})
        release_path = self.root / 'release.json'
        release = json.loads(release_path.read_text())
        release['files']['formation-tensor-lab.zip'] = '0' * 64
        release_path.write_text(json.dumps(release))
        # A Git checkout omits the optional generated ZIP; its paper is still usable.
        self.assertEqual(self.data.download('paper.pdf').name, 'main.pdf')
        with self.assertRaises(ValueError):
            self.data.download('project.zip')
        (self.root / 'paper/main.pdf').write_text('changed')
        with self.assertRaises(ValueError):
            self.data.download('paper.pdf')


if __name__ == '__main__':
    unittest.main()
