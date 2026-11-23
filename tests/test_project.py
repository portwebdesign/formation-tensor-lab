from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from formation_tensor.project import checked_manifest,same_value

class ReproductionTests(unittest.TestCase):
    def test_integer_differences_are_not_tolerated(self):
        self.assertIsNotNone(same_value({'seats':174},{'seats':175}))
        self.assertIsNone(same_value({'excess':.2},{'excess':.2+1e-12}))
        self.assertIsNotNone(same_value({'excess':.2},{'excess':.201}))
    def test_missing_fields_and_types_are_not_discarded(self):
        self.assertIsNotNone(same_value({'x':None},{'x':0}))
        self.assertIsNotNone(same_value({'x':1},{'y':1}))
        self.assertIsNotNone(same_value([1,2],[1]))
    def test_manifest_integrity_and_resolved_containment(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();(root/'x').write_text('a')
            h=hashlib.sha256(b'a').hexdigest();(root/'m.json').write_text(json.dumps({'files':{'x':h}}))
            checked_manifest(root,'m.json');(root/'x').write_text('b')
            with self.assertRaises(ValueError):checked_manifest(root,'m.json')
