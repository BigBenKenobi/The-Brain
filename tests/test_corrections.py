import unittest
import test_brain
from brain.core import validate

class Corrections(unittest.TestCase):
    setUp = test_brain.Lifecycle.setUp
    ingest = test_brain.Lifecycle.ingest
    def fixture(self):
        for name, content in [('old.md', '# Decision\nStaff uncommitted published main: publication pending.'), ('new.md', '# Decision\nVerified release merged as abc123; dirty local checkout is separate.'), ('latest.md', '# Decision\nRelease corrected to def456; artistic acceptance remains pending.')]:
            (self.source / name).write_text(content)
        pid = self.ingest()
        ids = {r['evidence']['path']: r['id'] for r in self.b.snapshot(pid)['records']}
        self.b.relate(pid, ids['old.md'], ids['new.md'], 'corrects', 'Verified publication evidence')
        return pid, ids

    def test_chain_history_budget_reingest(self):
        pid, ids = self.fixture()
        self.b.relate(pid, ids['new.md'], ids['latest.md'], 'supersedes', 'Reviewed release update')
        hits = self.b.retrieve('staff uncommitted published main', pid, limit=1)
        self.assertEqual([r['id'] for r in hits], [ids['latest.md']])
        self.assertEqual(len(hits[0]['resolution']), 2)
        self.assertEqual(self.b.retrieve('staff uncommitted published main', pid, max_chars=1), [])
        history = self.b.retrieve('staff uncommitted published main', pid, history=True)
        self.assertEqual(history[0]['id'], ids['old.md'])
        self.assertEqual(history[0]['retrieval_state'], 'historical')
        self.b.ingest(self.source)
        self.assertEqual(self.b.retrieve('staff uncommitted published main', pid)[0]['id'], ids['latest.md'])

    def test_missing_blocked_unapproved_correction_never_falls_back(self):
        pid, ids = self.fixture()
        self.assertEqual(self.b.retrieve('staff uncommitted published main', pid, blocked=['abc123']), [])
        self.b.promote(pid, ids['old.md'], ['staff'], 'Explicit fixture sharing')
        self.assertEqual(self.b.retrieve('staff uncommitted published main', technologies=['staff']), [])
        self.b.promote(pid, ids['new.md'], ['staff'], 'Explicit fixture sharing')
        shared = self.b.retrieve('staff uncommitted published main', technologies=['staff'])
        self.assertEqual(shared[0]['id'], ids['new.md'])
        self.assertNotIn('Verified publication evidence', str(shared))
        (self.source / 'new.md').unlink()
        self.b.ingest(self.source)
        self.assertTrue(validate(self.b.snapshot(pid))['relationship_warnings'])
        report = self.b.retrieve('staff uncommitted published main', pid, explain=True)
        self.assertEqual(report['results'], [])
        self.assertTrue(report['omitted'])

    def test_cycles_ambiguity_cross_project_idempotency(self):
        pid, ids = self.fixture()
        before = self.b.snapshot(pid)['id']
        self.assertFalse(self.b.relate(pid, ids['old.md'], ids['new.md'], 'corrects', 'Verified publication evidence')['changed'])
        for older, newer in [(ids['new.md'], ids['old.md']), (ids['old.md'], ids['latest.md']), (ids['old.md'], 'a'*64)]:
            with self.assertRaises(ValueError):
                self.b.relate(pid, older, newer, 'corrects', 'Invalid edge')
        self.assertEqual(self.b.snapshot(pid)['id'], before)

    def test_consolidation_keeps_corrections(self):
        pid, ids = self.fixture()
        other = self.base / 'target'; other.mkdir()
        (other / 'README.md').write_text('Target')
        target = self.b.ingest(other)['project_id']
        self.b.consolidate(target, pid)
        hits = self.b.retrieve('staff uncommitted published main', target)
        self.assertEqual(hits[0]['consolidated_from']['record_id'], ids['new.md'])
        self.b.ingest(other)
        self.assertEqual(self.b.retrieve('staff uncommitted published main', target)[0]['id'], hits[0]['id'])

    def test_duplicate_and_substantive_priority(self):
        (self.source / 'heading.md').write_text('# Motion-first\n')
        (self.source / 'decision.md').write_text('# Decision\nMotion-first means review the gray mannequin before clothing.')
        pid = self.ingest()
        hits = self.b.retrieve('motion-first', pid, limit=1)
        self.assertIn('gray mannequin', hits[0]['statement'])

    def test_cli_and_failed_pointer_preserve_history(self):
        import json
        import subprocess
        import sys
        from unittest.mock import patch
        from brain.core import write
        pid, ids = self.fixture()
        previous = self.b.snapshot(pid)
        def fail(path, value):
            if path == self.b.registry_path:
                raise OSError('fixture write failure')
            return write(path, value)
        with patch('brain.core.write', side_effect=fail):
            with self.assertRaises(OSError):
                self.b.relate(pid, ids['new.md'], ids['latest.md'], 'corrects', 'Reviewed update')
        self.assertEqual(self.b.snapshot(pid), previous)
        command = [sys.executable, '-m', 'brain', '--brain', str(self.b.root)]
        result = subprocess.run(command + ['context', pid, 'staff uncommitted published main', '--explain', '--limit', '1'], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['results'][0]['id'], ids['new.md'])
        subprocess.run(command + ['relate', pid, ids['new.md'], ids['latest.md'], '--kind', 'corrects', '--rationale', 'Reviewed update'], capture_output=True, text=True, check=True)
        self.assertEqual(self.b.retrieve('staff uncommitted published main', pid)[0]['id'], ids['latest.md'])
