import csv
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from formation_tensor.raw_parliament import recount

class RawParliamentTests(unittest.TestCase):
    def archive(self,root,rows):
        out=io.StringIO(newline='');writer=csv.writer(out);writer.writerows(rows)
        path=root/'data.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('votes.csv',out.getvalue())
        return path
    def row(self,party,action,member='1'):
        return ['2022/23','SoU1','v','1','Name',member,party,'District',action,'issue','1','x','1980','2023-01-01']
    def test_independent_abstention_not_counted_as_absence(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.archive(Path(d),[self.row('-','Avstår'),self.row('S','Ja','2')])
            totals,parties=recount([p]);self.assertEqual(totals['v'],[1,0,1,0]);self.assertEqual(parties['v']['-'],[0,0,1,0])
    def test_duplicate_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.archive(Path(d),[self.row('S','Ja'),self.row('S','Nej')])
            with self.assertRaises(ValueError):recount([p])
    def test_unknown_action_is_not_silently_imputed(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.archive(Path(d),[self.row('S','missing')])
            with self.assertRaises(ValueError):recount([p])
