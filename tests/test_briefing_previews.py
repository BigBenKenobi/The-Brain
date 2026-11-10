"""Paragraph previews remain exact, bounded projections of immutable records."""
import copy
from pathlib import Path
import tempfile
import unittest
from brain.core import Brain, initialize
from brain.briefing import preview_candidates, render_briefing


class BriefingPreviewTests(unittest.TestCase):
    def test_later_emphasized_principles_keep_exact_offsets_and_citations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir()
            text=('# Mission\n\n'+('Introductory context with no settled commitment. '*12)+
                  '\n\n**Keep observations attributable.** Preserve the original evidence and its uncertainty.\n\n'
                  '**Make interrupted work recoverable.** Keep the reason for an unfinished idea.\n')
            (source/'vision.md').write_text(text)
            initialize(root/'store');b=Brain(root/'store');pid=b.ingest(source)['project_id']
            snap=b.snapshot(pid);records={r['id']:r for r in snap['records']}
            before={p:p.read_bytes() for p in b.root.rglob('*') if p.is_file()}
            brief=b.briefing(pid,limit=2);items=brief['sections']['objectives']['items']
            self.assertEqual(len(items),2)
            self.assertTrue(any('observations attributable' in i['excerpt'] for i in items))
            self.assertTrue(any('interrupted work recoverable' in i['excerpt'] for i in items))
            for item in items:
                record=records[item['record_id']]
                self.assertEqual(item['excerpt'],record['statement'][item['excerpt_start_char']:item['excerpt_end_char']])
                self.assertGreater(item['excerpt_start_char'],0)
                self.assertTrue(item['excerpt_truncated'])
                self.assertLessEqual(len(item['excerpt']),400)
                self.assertEqual(item['evidence'],record['evidence'])
            self.assertIn('surrounding qualifications',render_briefing(brief))
            self.assertEqual(before,{p:p.read_bytes() for p in b.root.rglob('*') if p.is_file()})

    def test_configuration_source_and_fences_are_not_prose_paragraphs(self):
        record={'id':'x','statement':'# Objective\n\n'+('long prose '*50)+'\n\n**Another paragraph** with a qualification.',
                'source_role':'documented_claim','evidence_status':'historical_record','knowledge_kinds':[], 'evidence':{'path':'notes.md','start_line':1}}
        for changed in ({'statement':record['statement'].replace('# Objective', '# General notes')}, {'source_role':'implementation'}, {'evidence':{'path':'config.toml'}},
                        {'statement':record['statement']+'\n```\ncode\n```'},
                        {'statement':record['statement']+'\n~~~\ncode\n~~~'}):
            value={**record,**changed};before=copy.deepcopy(value)
            self.assertEqual(preview_candidates([value]),[value])
            self.assertEqual(value,before)

    def test_paragraph_offsets_do_not_join_disjoint_or_duplicate_text(self):
        text='# Objective\n\n'+('Résumé context. '*35)+'\n\n**Preserve nuance.** This may change.\n\n**Preserve nuance.** This may change.'
        record={'id':'x','statement':text,'source_role':'documented_claim','evidence_status':'historical_record','knowledge_kinds':[], 'evidence':{'path':'notes.md','start_line':1}}
        before=copy.deepcopy(record);candidates=preview_candidates([record])
        self.assertGreater(len(candidates),1)
        for candidate in candidates:
            start=candidate['_excerpt_start']
            self.assertEqual(candidate['statement'],text[start:start+len(candidate['statement'])])
            self.assertEqual(candidate['id'],record['id'])
        self.assertEqual(record,before)
