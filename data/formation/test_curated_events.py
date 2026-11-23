"""Integrity and type checks for the curated formation chronology."""
import hashlib
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class CuratedFormationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((HERE / 'events2026.json').read_text())
        cls.ledger = json.loads((HERE / 'source-ledger.json').read_text())
        cls.events = {event['id']: event for event in cls.data['events']}
        cls.sources = {source['id']: source for source in cls.ledger['sources']}

    def test_captured_responses_match_declared_hashes(self):
        self.assertEqual(len(self.sources), 22)
        self.assertEqual(sum(s['raw_download_succeeded'] for s in self.sources.values()), 21)
        for source in self.sources.values():
            response = ROOT / source['response_path']
            self.assertEqual(hashlib.sha256(response.read_bytes()).hexdigest(), source['response_sha256'])
            self.assertEqual(response.stat().st_size, source['response_bytes'])
            self.assertTrue(source['accessed_at_utc'].startswith('2026-11-22T'))
            self.assertFalse(source['historical_accessibility_proven'])
            if source['raw_download_succeeded']:
                self.assertEqual(source['http_status'], 200)
                self.assertEqual(source['sha256'], source['response_sha256'])
        platform = self.sources['v-platform-2026']
        self.assertEqual(platform['http_status'], 403)
        self.assertIsNone(platform['path'])
        self.assertIsNone(platform['sha256'])
        self.assertTrue(platform['web_text_opened'])

    def test_only_formal_ballots_consume_rejections(self):
        rejected = [event for event in self.events.values() if event['formal_rejection_count_delta']]
        self.assertEqual(len(rejected), 2)
        self.assertEqual({event['event_type'] for event in rejected}, {'formal_pm_vote'})
        self.assertEqual(self.data['rules']['formal_rejection_allowance_remaining'], 2)
        self.assertEqual(self.data['rules']['formal_rejection_limit'], 4)
        self.assertFalse(self.data['rules']['exploratory_assignment_consumes_formal_rejection'])
        self.assertEqual(self.data['summary']['initial_exploratory_assignments'], 3)
        self.assertEqual(self.data['summary']['mandate_resumptions'], 1)

    def test_ballot_totals_and_party_breakdowns(self):
        for event in self.events.values():
            if event['event_type'] != 'formal_pm_vote':
                continue
            counts = event['ballot_counts']
            self.assertEqual(sum(counts.values()), 349)
            for index, role in enumerate(('yes', 'no', 'abstain', 'absent')):
                self.assertEqual(sum(row[index] for row in event['party_counts'].values()), counts[role])
            self.assertGreaterEqual(counts['no'], 175)
        self.assertEqual(self.events['s-rejection']['ballot_counts'], {'yes': 99, 'no': 248, 'abstain': 0, 'absent': 2})
        self.assertEqual(self.events['c-rejection']['ballot_counts'], {'yes': 25, 'no': 324, 'abstain': 0, 'absent': 0})

    def test_announcements_are_not_backdated_formal_events(self):
        self.assertEqual(self.events['c-nomination-announced']['event_date'], '2026-10-29')
        self.assertEqual(self.events['c-nomination']['event_date'], '2026-10-30')
        self.assertEqual(self.events['c-nomination']['source_ids'], ['c-formal-20261030'])
        self.assertIsNone(self.events['c-nomination']['source_publication_at'])
        self.assertEqual(self.events['s-resumption-announced']['event_date'], '2026-10-02')
        self.assertEqual(self.events['s-resumption-effective']['event_date'], '2026-10-05')
        self.assertEqual(self.events['next-round']['status'], 'announced_future')
        self.assertEqual(self.events['next-round']['event_date'], '2026-11-24')
        self.assertFalse(self.events['next-round']['nomination_announced'])
        self.assertEqual(self.events['m-report-incomplete']['report_completion'], 'incomplete')

    def test_every_event_links_to_current_frozen_source(self):
        for event in self.events.values():
            source = self.sources[event['source_ids'][0]]
            self.assertEqual(event['source_url'], source['url'])
            self.assertEqual(event['source_publication_at'], source['first_publication_at'])
            self.assertEqual(event['source_updated_at'], source['updated_at'])
            self.assertEqual(event['source_accessed_at_utc'], source['accessed_at_utc'])
            self.assertFalse(event['cabinet_consent_inferred'])
            self.assertFalse(event['future_pm_ballot_inferred'])
            if event['status'] == 'observed':
                self.assertLessEqual(event['event_date'], self.data['as_of_date'])


if __name__ == '__main__':
    unittest.main()
