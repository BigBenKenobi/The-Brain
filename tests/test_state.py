import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from brain.core import Brain, initialize, read, write, validate
from brain.state import ProjectState, item_id, load_catalog, bounded_view


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source/'decision.md').write_text('# Decision\nUse polling because partial writes need a stable observation.\n')
        (self.source/'blocker.md').write_text('# Known issue\nUnresolved blocker: incomplete writes remain possible.\n')
        (self.source/'idea.md').write_text('# Proposed idea\nUntested event batching remains a future opportunity.\n')
        initialize(self.root/'store')
        self.b = Brain(self.root/'store')
        self.pid = self.b.ingest(self.source)['project_id']
        self.state = ProjectState(self.b, self.pid)

    def find(self, phrase):
        return next(i for i in self.state.view()['items'].values() if phrase in i['summary'])

    def evidence(self, phrase):
        s = self.b.snapshot(self.pid)
        r = next(r for r in s['records'] if phrase in r['statement'])
        return {'snapshot': s['id'], 'record_id': r['id']}

    def test_candidate_status_and_purpose_do_not_infer_commitments(self):
        state = self.state.view()
        idea = self.find('batching')
        self.assertEqual(idea['work_stage'], 'proposed')
        self.assertEqual(idea['evidence_strength'], 'reported')
        self.assertFalse(idea['reviewed'])
        self.assertEqual(idea['purpose'], 'future_opportunity')
        decision = self.find('polling')
        self.assertEqual(decision['work_stage'], 'unknown')
        self.assertEqual(decision['purpose'], 'decision_rationale')
        self.assertEqual(state['visibility'], 'project_private')

    def test_catalogue_preserves_missing_blocker_beyond_recent_history_budget(self):
        blocker = self.find('incomplete writes')
        (self.source/'blocker.md').unlink()
        self.b.ingest(self.source)
        for i in range(5):
            (self.source/'decision.md').write_text(f'# Decision\nVariant {i}: observe partial writes cautiously.\n')
            self.b.ingest(self.source)
        state = self.state.view(max_snapshots=1)
        retained = state['items'][blocker['id']]
        self.assertEqual(retained['kind'], 'blocker')
        self.assertEqual(retained['availability'], 'retained_history_only')
        self.assertEqual(retained['work_stage'], 'unknown')
        self.assertNotEqual(retained['currency'], 'superseded')
        claim = retained['claims'][0]
        self.assertIn('incomplete writes', self.b.retained_evidence(self.pid, claim['path'],
            claim['start_line'], claim['end_line'], claim['snapshot'])['text'])

    def test_explicit_correction_preserves_item_identity_and_undo_history(self):
        original = self.find('polling')
        old_snapshot = self.b.snapshot(self.pid)
        (self.source/'decision.md').write_text('# Decision\nUse explicit refresh because polling repeatedly saw partial writes.\n')
        self.b.ingest(self.source)
        ref = self.evidence('explicit refresh')
        event = self.state.correct(original['id'], {'summary': 'Use explicit refresh because polling repeatedly saw partial writes.',
            'work_stage': 'accepted', 'currency': 'active'}, ref, 'Explicit review of the replacement decision')
        changed = self.state.view()['items'][original['id']]
        self.assertEqual(changed['id'], original['id'])
        self.assertEqual(changed['work_stage'], 'accepted')
        self.assertEqual(changed['evidence_strength'], 'reported')
        self.assertEqual(len(changed['claims']), 2)
        self.assertTrue(changed['reviewed'])
        self.state.undo(event['id'], 'Withdraw this interpretation pending review')
        restored = self.state.view()['items'][original['id']]
        self.assertEqual(restored['summary'], original['summary'])
        self.assertEqual(restored['work_stage'], 'unknown')
        self.assertEqual(self.b.snapshot(self.pid, old_snapshot['id']), old_snapshot)
        events = self.state.events()
        self.assertEqual([e['type'] for e in events], ['correct', 'undo'])

    def test_evidence_strength_cannot_be_certified_by_correction(self):
        item = self.find('polling')
        with self.assertRaisesRegex(ValueError, 'verification cannot be asserted'):
            self.state.correct(item['id'], {'evidence_strength': 'independently_verified'},
                self.evidence('polling'), 'Model confidence is not proof')
        self.assertFalse(self.state.head.exists())

    def test_supersession_contradiction_cycles_and_undo(self):
        older, idea = self.find('polling'), self.find('batching')
        ref = self.evidence('batching')
        conflict = self.state.relate(idea['id'], older['id'], 'contradicts', ref, 'Retain conflict for review')
        self.assertEqual(self.state.view()['items'][older['id']]['currency'], 'uncertain')
        edge = self.state.relate(idea['id'], older['id'], 'supersedes', ref, 'Explicit interpretation of replacement')
        self.assertEqual(self.state.view()['items'][older['id']]['currency'], 'superseded')
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            self.state.relate(older['id'], idea['id'], 'supersedes', self.evidence('polling'), 'Invalid reverse edge')
        self.state.undo(edge['id'], 'Replacement was not adopted')
        state = self.state.view()
        self.assertEqual(state['items'][older['id']]['currency'], 'uncertain')
        self.assertTrue(any(e['id'] == conflict['id'] for e in state['relationships']))

    def test_state_is_private_and_foreign_evidence_is_rejected(self):
        other = self.root/'other';other.mkdir()
        (other/'decision.md').write_text('Decision: unrelated-private-canary.\n')
        pid = self.b.ingest(other)['project_id'];s = self.b.snapshot(pid)
        with self.assertRaises((OSError, ValueError)):
            self.state.correct(self.find('polling')['id'], {'summary': 'Foreign evidence'},
                {'snapshot': s['id'], 'record_id': s['records'][0]['id']}, 'Not permitted')
        self.assertNotIn('unrelated-private-canary', json.dumps(self.state.view()))

    def test_failed_event_publication_and_failed_capture_preserve_old_pointers(self):
        before = self.state.view()
        def fail_head(path, value):
            if Path(path) == self.state.head:
                raise OSError('simulated journal failure')
            write(path, value)
        with patch('brain.state.write', side_effect=fail_head):
            with self.assertRaises(OSError):
                self.state.correct(self.find('polling')['id'], {'work_stage': 'accepted'}, self.evidence('polling'), 'Review')
        self.assertEqual(self.state.view(), before)
        registry = read(self.b.registry_path)
        (self.source/'decision.md').write_text('Decision: unpublished interpretation must not appear.\n')
        def fail_registry(path, value):
            if Path(path) == self.b.registry_path:
                raise OSError('simulated capture publication failure')
            write(path, value)
        with patch('brain.core.write', side_effect=fail_registry):
            with self.assertRaises(OSError):self.b.ingest(self.source)
        self.assertEqual(read(self.b.registry_path), registry)
        self.assertNotIn('unpublished interpretation', json.dumps(self.state.view()))

    def test_unchanged_capture_reuses_catalogue_and_view_is_read_only(self):
        catalog = self.b.project(self.pid)['state_catalog']
        self.b.ingest(self.source)
        self.assertEqual(self.b.project(self.pid)['state_catalog'], catalog)
        before = {str(p): p.read_bytes() for p in self.b.root.rglob('*') if p.is_file()}
        self.state.view()
        self.b.briefing(self.pid)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.b.root.rglob('*') if p.is_file()})

    def test_legacy_backfill_and_unknown_lineage_are_explicit(self):
        (self.source/'blocker.md').unlink();self.b.ingest(self.source)
        registry=read(self.b.registry_path);registry['projects'][self.pid].pop('state_catalog');write(self.b.registry_path,registry)
        result=self.state.sync(max_snapshots=1)
        self.assertEqual(result['snapshots_processed'],1)
        self.assertTrue(any('incomplete writes' in i['summary'] for i in self.state.view(max_snapshots=1)['items'].values()))
        self.assertFalse(load_catalog(self.b,self.pid)['legacy_lineage_unknown'])

    def test_legacy_record_relationship_can_be_undone_without_approval_change(self):
        old=self.evidence('polling');replacement=self.evidence('batching')
        before=self.b.snapshot(self.pid)
        self.b.promote(self.pid,old['record_id'],['sqlite'],'Reviewed prior sharing')
        approval=self.b.root/'shared'/(old['record_id']+'.json');approval_before=approval.read_bytes()
        self.b.relate(self.pid,old['record_id'],replacement['record_id'],'corrects','Reviewed correction')
        self.assertEqual(self.state.view()['items'][item_id(self.pid,old['record_id'])]['currency'],'superseded')
        self.b.undo_relation(self.pid,old['record_id'],'Withdraw correction')
        self.assertEqual(self.state.view()['items'][item_id(self.pid,old['record_id'])]['currency'],'uncertain')
        self.assertEqual(approval.read_bytes(),approval_before)
        self.assertEqual(self.b.snapshot(self.pid,before['id']),before)

    def test_sync_reconciles_stale_catalogue_from_compatible_capture_writer(self):
        old_catalog = self.b.project(self.pid)['state_catalog']
        (self.source/'new.md').write_text('# Known issue\nUnresolved adapter latency.\n')
        self.b.ingest(self.source)
        registry = read(self.b.registry_path)
        registry['projects'][self.pid]['state_catalog'] = old_catalog
        write(self.b.registry_path, registry)
        self.state.sync(max_snapshots=1)
        record = self.evidence('adapter latency')['record_id']
        self.assertIn(record, load_catalog(self.b, self.pid)['entries'])
        self.state.sync(max_snapshots=1)
        self.assertFalse(load_catalog(self.b, self.pid)['pending_snapshot'])

    def test_corrupt_undo_journal_is_rejected(self):
        item = self.find('polling')
        event = self.state.correct(item['id'], {'work_stage': 'accepted'},
                                   self.evidence('polling'), 'Reviewed acceptance')
        undo = self.state.undo(event['id'], 'Withdraw acceptance')
        path = self.state.root/'events'/(undo['id']+'.json')
        malformed = read(path)
        malformed['target'] = undo['id']
        write(path, malformed)
        with self.assertRaisesRegex(ValueError, 'Invalid state undo target'):
            self.state.view()

    def test_state_cli_is_bounded_and_undoable(self):
        def cli(*args):
            return json.loads(subprocess.check_output([sys.executable,'-m','brain','--brain',str(self.b.root),*args],text=True))
        shown=cli('state',self.pid,'--limit','1')
        self.assertEqual(len(shown['items']),1)
        self.assertGreater(shown['omitted_items'],0)
        item=self.find('polling');ref=self.evidence('polling')
        event=cli('state-correct',self.pid,item['id'],'--work-stage','accepted','--record-id',ref['record_id'],'--rationale','Explicit CLI review')
        cli('state-undo',self.pid,event['id'],'--rationale','Withdraw review')
        self.assertEqual(self.state.view()['items'][item['id']]['work_stage'],'unknown')

    def test_bounded_state_balances_kinds_instead_of_crowding_out_attempts(self):
        for n in range(12):
            (self.source/f'blocker-{n}.md').write_text(f'# Known issue\nUnresolved obstacle number {n}.\n')
        (self.source/'attempt.md').write_text('# Failed approach\nRejected retry loop because it hid faults.\n')
        self.b.ingest(self.source)
        full=self.state.view();shown=bounded_view(full,4)
        self.assertEqual({i['kind'] for i in shown['items']},{'blocker','decision','idea','attempt'})
        self.assertEqual(shown['omitted_items'],len(full['items'])-4)
        self.assertEqual(full,self.state.view())

    def test_explicitly_reviewed_items_keep_priority_over_automatic_candidates(self):
        item=self.find('batching')
        self.state.correct(item['id'],{'currency':'active'},self.evidence('batching'),'Reviewed future opportunity')
        shown=bounded_view(self.state.view(),1)
        self.assertEqual(shown['items'][0]['id'],item['id'])
