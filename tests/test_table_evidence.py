"""Prose table rows retain exact citations without inheriting legacy approvals."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from brain.core import Brain,initialize,validate,read,write,digest
from brain.state import ProjectState


class TableEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        initialize(self.root/'store');self.b=Brain(self.root/'store')
        self.row='| Software validation | Open: the retry timeout still occurs in the full run and requires an independently recorded rerun. |'
        self.text='# Release gates\n\n| Gate | Required evidence |\n|---|---|\n'+self.row+'\n'
        (self.source/'gates.md').write_text(self.text)

    def test_table_issue_has_exact_line_evidence_and_reported_state(self):
        pid=self.b.ingest(self.source)['project_id'];s=self.b.snapshot(pid)
        r=next(r for r in s['records'] if r['statement']==self.row)
        self.assertEqual(r['evidence']['start_line'],5)
        self.assertEqual(r['evidence']['end_line'],5)
        self.assertEqual(self.b.retained_evidence(pid,'gates.md',5,5)['text'],self.row)
        self.assertIn(r['id'],[i['record_id'] for i in self.b.briefing(pid)['sections']['problems']['items']])
        item=next(i for i in ProjectState(self.b,pid).view()['items'].values() if i['summary']==self.row)
        self.assertEqual(item['kind'],'blocker');self.assertEqual(item['work_stage'],'unknown')
        self.assertEqual(item['evidence_strength'],'reported');self.assertFalse(item['reviewed'])
        self.assertTrue(validate(s)['valid'])

    def test_numeric_tables_are_not_promoted_to_narrative(self):
        from brain.briefing import substantive_table_row,narrative_lines
        row='| decision | 102 | 0 | 99 |'
        self.assertFalse(substantive_table_row(row))
        self.assertEqual(narrative_lines({'statement':row}),[])

    def test_recorded_failure_precedes_general_table_checklist(self):
        generic='| Candidate | Open: capture the release artifact hashes and record the complete environment before publishing any package. |'
        (self.source/'gates.md').write_text(self.text.replace(self.row,generic+'\n'+self.row))
        pid=self.b.ingest(self.source)['project_id']
        selected=self.b.briefing(pid,limit=1)['sections']['problems']['items']
        self.assertEqual(selected[0]['excerpt'],self.row)

    def test_project_introduction_surfaces_without_asserting_release_acceptance(self):
        text='# Workshop\nWorkshop is a local application and a pre-release candidate, with acceptance still unmeasured.\n'
        (self.source/'README.md').write_text(text)
        pid=self.b.ingest(self.source)['project_id']
        selected=self.b.briefing(pid)['sections']['objectives']['items']
        intro=next(i for i in selected if 'pre-release candidate' in i['excerpt'])
        self.assertEqual(intro['evidence_status'],'historical_record')

    def test_fenced_table_example_is_not_split_into_row_candidates(self):
        (self.source/'gates.md').write_text('```markdown\n'+self.text+'```\n')
        pid=self.b.ingest(self.source)['project_id']
        self.assertFalse(any(r['statement']==self.row for r in self.b.snapshot(pid)['records']))

    def test_new_extractor_does_not_reuse_legacy_record_approval(self):
        (self.source/'gates.md').write_text('# Decision\nUse retained local evidence because source paths can disappear.\n')
        pid=self.b.ingest(self.source)['project_id'];s=self.b.snapshot(pid)
        r=s['records'][0]
        legacy_id=digest(f"{pid}:gates.md:{r['evidence']['sha256']}:0".encode())
        r['id']=legacy_id;s['search_index']={legacy_id:s['search_index'].pop(next(iter(s['search_index'])))}
        s['extractor']='deterministic-3'
        write(self.b.root/'projects'/pid/'snapshots'/(s['id']+'.json'),s)
        registry=read(self.b.registry_path);registry['projects'][pid].pop('state_catalog',None);write(self.b.registry_path,registry)
        self.b.promote(pid,legacy_id,['sqlite'],'Reviewed original extraction')
        approval=self.b.root/'shared'/(legacy_id+'.json');old=approval.read_bytes()
        result=self.b.ingest(self.source)
        self.assertGreater(result['metrics']['extractions'],0)
        self.assertNotEqual(self.b.snapshot(pid)['records'][0]['id'],legacy_id)
        self.assertEqual(self.b.retrieve('retained local evidence',technologies=['sqlite']),[])
        self.assertEqual(approval.read_bytes(),old)
        self.assertTrue(self.b.retrieve('retained local evidence',pid))
