"""Explicit duplicate grouping preserves original claims, approvals and undo."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from brain.core import Brain,initialize,read,write
from brain.state import ProjectState,bounded_view


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        for name,text in [('a','Use bounded retries because transient contention can clear.'),('b','Choose bounded retry because transient locking can recover.'),('c','Keep the old database schema because migration remains untested.')]:
            (self.source/(name+'.md')).write_text('# Decision\n'+text+'\n')
        initialize(self.root/'store');self.b=Brain(self.root/'store');self.pid=self.b.ingest(self.source)['project_id'];self.state=ProjectState(self.b,self.pid)
        self.a,self.bitem=[next(i for i in self.state.view()['items'].values() if i['claims'][0]['path']==p) for p in ('a.md','b.md')]

    def merge(self):
        return self.state.consolidate(self.a['id'],self.bitem['id'],'Reviewed as the same bounded retry decision')

    def test_grouping_preserves_claims_original_identity_and_undo(self):
        before=self.state.view();snapshot=self.b.snapshot(self.pid)
        rid=self.bitem['claims'][0]['record_id'];self.b.promote(self.pid,rid,['sqlite'],'Reviewed original scope')
        approval=self.b.root/'shared'/(rid+'.json');saved=approval.read_bytes()
        event=self.merge();view=self.state.view()
        self.assertEqual(len(view['items'][self.a['id']]['claims']),2)
        self.assertEqual(view['items'][self.bitem['id']]['consolidated_into'],self.a['id'])
        self.assertNotIn(self.bitem['id'],{i['id'] for i in bounded_view(view)['items']})
        self.assertIn(self.bitem['id'],{i['id'] for i in bounded_view(view,include_history=True)['items']})
        self.assertEqual(self.b.snapshot(self.pid),snapshot);self.assertEqual(approval.read_bytes(),saved)
        self.assertEqual(read(self.state.head)['version'],2)
        self.state.undo(event['id'],'Withdraw equivalence review')
        self.assertEqual(self.state.view()['items'],before['items'])
        self.assertEqual(approval.read_bytes(),saved)

    def test_stage_and_purpose_conflicts_require_explicit_correction(self):
        for field,value in [('work_stage','accepted'),('purpose','active_work'),('currency','active')]:
            event=self.state.correct(self.bitem['id'],{field:value},self.bitem['claims'][0],'Reviewed difference')
            with self.assertRaisesRegex(ValueError,'interpretation conflict'):self.merge()
            self.state.undo(event['id'],'Withdraw difference')
        self.merge()
        with self.assertRaisesRegex(ValueError,'survivor'):
            self.state.correct(self.bitem['id'],{'currency':'active'},self.bitem['claims'][0],'Cannot edit absorbed identity')

    def test_contradictory_endpoints_cannot_be_consolidated(self):
        edge=self.state.relate(self.a['id'],self.bitem['id'],'contradicts',self.a['claims'][0],'These claims conflict')
        with self.assertRaisesRegex(ValueError,'contradictory'):self.merge()
        self.state.undo(edge['id'],'Correction: equivalence requires review instead')
        self.merge()

    def test_external_relationship_remains_visible_with_original_endpoint(self):
        other=next(i for i in self.state.view()['items'].values() if i['claims'][0]['path']=='c.md')
        self.state.relate(self.bitem['id'],other['id'],'supports',self.bitem['claims'][0],'Related historical rationale')
        self.merge();shown=bounded_view(self.state.view(),1)
        self.assertEqual(shown['items'][0]['id'],self.a['id'])
        self.assertEqual(shown['relationships'][0]['from'],self.bitem['id'])

    def test_failed_publication_never_hides_original_item(self):
        before=self.state.view();real=write
        def fail(path,value):
            if Path(path)==self.state.head:raise OSError('head publication failed')
            real(path,value)
        with patch('brain.state.write',side_effect=fail):
            with self.assertRaises(OSError):self.merge()
        self.assertEqual(self.state.view()['items'],before['items'])

    def test_undo_of_dependency_is_rejected_before_journal_publication(self):
        accepted=self.state.correct(self.a['id'],{'work_stage':'accepted'},self.a['claims'][0],'Accepted decision')
        second=self.state.correct(self.bitem['id'],{'work_stage':'accepted'},self.bitem['claims'][0],'Same accepted decision')
        grouping=self.merge();before=self.state.head.read_bytes()
        with self.assertRaisesRegex(ValueError,'interpretation conflict'):
            self.state.undo(second['id'],'Withdraw acceptance')
        self.assertEqual(self.state.head.read_bytes(),before)
        self.state.undo(grouping['id'],'First separate the interpretations')
        self.state.undo(second['id'],'Now withdraw acceptance')
        self.assertEqual(self.state.view()['items'][self.bitem['id']]['work_stage'],'unknown')

    def test_unrelated_or_same_item_cannot_be_grouped(self):
        for other in ('foreign-item',self.a['id']):
            with self.assertRaises(ValueError):self.state.consolidate(self.a['id'],other,'Invalid grouping')

    def test_later_canonical_precedence_flags_group_for_review(self):
        self.merge()
        self.b.relate(self.pid,self.bitem['claims'][0]['record_id'],self.a['claims'][0]['record_id'],
                      'supersedes','Later evidence says these are successive decisions')
        target=self.state.view()['items'][self.a['id']]
        self.assertTrue(target['consolidation_conflicts'])
        self.assertEqual(target['currency'],'uncertain')
        from brain.briefing import render_briefing
        self.assertIn('Consolidation needs review',render_briefing(self.b.briefing(self.pid)))
