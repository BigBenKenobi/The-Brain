"""Scoped observer review never promotes an entire item or changes source evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_verification_runner import runner
from brain.core import Brain, initialize, read, write
from brain.state import ProjectState
from brain.storage import compact_copy


class VerificationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root / 'source'; self.source.mkdir()
        (self.source / 'decision.md').write_text('# Decision\nUse the fixture marker for this isolated check.\n')
        subprocess.run(['git', 'init', '-q', str(self.source)], check=True)
        subprocess.run(['git', '-C', str(self.source), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.source), '-c', 'user.name=Fixture', '-c',
                        'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        initialize(self.root / 'store'); self.brain = Brain(self.root / 'store')
        self.pid = self.brain.ingest(self.source)['project_id']; self.state = ProjectState(self.brain, self.pid)
        self.item = next(iter(self.state.view()['items'].values()))
        self.directory = self.root / 'receipt'
        runner.run([sys.executable, '-c', 'print("fixture passed")'], self.source, self.directory,
                   'The explicit fixture emits its marker', 'Synthetic local process')

    def adopt(self):
        return self.state.verify(self.item['id'], self.directory, 'Local fixture observer',
                                 'Observed the exact marker; this proves no application behavior', observed=True)

    def test_scoped_review_preserves_global_status_evidence_and_undo(self):
        snapshot = self.brain.snapshot(self.pid)
        event = self.adopt(); item = self.state.view()['items'][self.item['id']]
        self.assertEqual(item['evidence_strength'], 'reported')
        self.assertEqual(item['work_stage'], self.item['work_stage'])
        check = item['verified_behaviors'][0]
        self.assertEqual(check['applicability'], 'reviewed_subject')
        self.assertEqual(check['authority'], 'explicit_local_observer_attestation')
        self.assertEqual(read(self.state.head)['version'], 3)
        self.assertEqual(self.brain.snapshot(self.pid), snapshot)
        self.state.undo(event['id'], 'Withdraw observer review')
        self.assertNotIn('verified_behaviors', self.state.view()['items'][self.item['id']])
        self.assertFalse(self.state.receipt(event['id'])['active'])
        self.assertIn('stdout', self.state.receipt(event['id'])['event']['verification_bundle']['outputs'])

    def test_no_implicit_attestation_and_no_tampered_output(self):
        with self.assertRaisesRegex(ValueError, 'attestation'):
            self.state.verify(self.item['id'], self.directory, 'Observer', 'Reason')
        (self.directory / 'stdout.bin').write_bytes(b'different output')
        with self.assertRaisesRegex(ValueError, 'hash or size'):
            self.adopt()
        self.assertFalse(self.state.head.exists())

    def test_failed_or_dirty_receipt_is_rejected(self):
        path = self.directory / 'receipt.json'; original = read(path)
        for field, value in [('outcome', 'failed'), ('output_complete', False)]:
            bad = dict(original); bad[field] = value; write(path, bad)
            with self.assertRaises(ValueError): self.adopt()
        bad = dict(original); bad['source_after'] = dict(bad['source_after'], tracked_clean=False); write(path, bad)
        with self.assertRaisesRegex(ValueError, 'source revision'): self.adopt()
        self.assertFalse(self.state.head.exists())

    def test_foreign_project_receipt_is_rejected(self):
        path = self.directory / 'receipt.json'; receipt = read(path)
        receipt['cwd'] = str(self.root / 'another-project'); write(path, receipt)
        with self.assertRaisesRegex(ValueError, 'recorded location'): self.adopt()
        self.assertFalse(self.state.head.exists())

    def test_observation_refresh_keeps_subject_but_conflict_requires_review(self):
        self.adopt(); self.brain.ingest(self.source)
        item = self.state.view()['items'][self.item['id']]
        self.assertEqual(item['verified_behaviors'][0]['applicability'], 'reviewed_subject')
        (self.source / 'other.md').write_text('# Decision\nUse another approach instead.\n')
        self.brain.ingest(self.source)
        other = next(i for i in self.state.view()['items'].values() if i['id'] != self.item['id'])
        self.state.relate(self.item['id'], other['id'], 'contradicts', other['claims'][0], 'Conflicting fixture')
        item = self.state.view()['items'][self.item['id']]
        self.assertEqual(item['verified_behaviors'][0]['applicability'], 'historical_review_required')

    def test_changed_interpretation_is_historical_until_correction_undone(self):
        self.adopt(); evidence = self.item['claims'][0]
        correction = self.state.correct(self.item['id'], {'summary': 'A different, untested meaning'},
                                        evidence, 'Explicitly change interpretation')
        self.assertEqual(self.state.view()['items'][self.item['id']]['verified_behaviors'][0]['applicability'],
                         'historical_review_required')
        self.state.undo(correction['id'], 'Restore prior interpretation')
        self.assertEqual(self.state.view()['items'][self.item['id']]['verified_behaviors'][0]['applicability'],
                         'reviewed_subject')

    def test_compaction_preserves_review_and_undone_receipt_integrity(self):
        event = self.adopt(); before = self.state.view()
        compact_copy(self.brain, self.root / 'copy')
        copied = ProjectState(Brain(self.root / 'copy'), self.pid)
        self.assertEqual(copied.view(), before)
        self.state.undo(event['id'], 'Withdraw review')
        path = self.state.root / 'events' / (event['id'] + '.json')
        damaged = read(path); damaged['verification_bundle']['receipt_sha256'] = '0' * 64; write(path, damaged)
        with self.assertRaisesRegex(ValueError, 'hash or budget'):
            compact_copy(self.brain, self.root / 'bad-copy')
        self.assertFalse((self.root / 'bad-copy').exists())

    def test_head_failure_does_not_publish_review(self):
        from brain.state import write as real_write
        def failing(path, data):
            if Path(path) == self.state.head: raise OSError('simulated head failure')
            return real_write(path, data)
        with patch('brain.state.write', side_effect=failing):
            with self.assertRaises(OSError): self.adopt()
        self.assertNotIn('verified_behaviors', self.state.view()['items'][self.item['id']])

    def test_explicit_cli_review_and_readback(self):
        command = [sys.executable, '-m', 'brain', '--brain', str(self.brain.root)]
        result = subprocess.run(command + ['state-verify', self.pid, self.item['id'], str(self.directory),
            '--reviewer', 'Fixture observer', '--rationale', 'Observed scoped fixture only', '--attest-observed'],
            capture_output=True, text=True, check=True)
        event = json.loads(result.stdout)
        result = subprocess.run(command + ['state-receipt', self.pid, event['id']],
                                capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(result.stdout)['active'])
