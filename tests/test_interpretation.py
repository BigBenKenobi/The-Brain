import copy
import json
from pathlib import Path
import tempfile
import unittest
from brain.core import Brain, initialize
from brain.interpretation import build_input, validate_proposals


class InterpretationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root/'source';source.mkdir()
        (source/'notes.md').write_text('# Decision\nUse explicit refresh to avoid incomplete writes.\n\n# Known issue\nUnresolved issue: watcher misses are unmeasured.\n')
        initialize(self.root/'store');self.brain=Brain(self.root/'store')
        self.pid=self.brain.ingest(source)['project_id']
        foreign=self.root/'foreign';foreign.mkdir()
        (foreign/'notes.md').write_text('# Decision\nPrivate unrelated canary CERAMICS-991.\n')
        self.brain.ingest(foreign)
        self.payload=build_input(self.brain,self.pid)
        record=self.payload['records'][0]
        self.raw={'items':[{'id':'decision1','kind':'decision','summary':'Prefer explicit refresh.',
            'claims':[{'record_id':record['record_id'],'quote':record['text']}]}], 'relationships':[]}
        self.identity={'runtime':'fixture','version':'1','model':'fixture-not-inference','digest':'test-only','configuration':{'temperature':0}}

    def check(self, raw=None, payload=None):
        return validate_proposals(self.brain,payload or self.payload,json.dumps(raw or self.raw),model_identity=self.identity)

    def test_private_read_only_attribution_does_not_certify_semantics(self):
        before={str(p):p.read_bytes() for p in self.brain.root.rglob('*') if p.is_file()}
        self.assertNotIn('CERAMICS-991',json.dumps(self.payload))
        self.raw['items'][0]['summary']='Everything is complete and independently verified.'
        result=self.check()
        self.assertEqual(result['items'][0]['work_stage'],'unknown')
        self.assertEqual(result['items'][0]['evidence_strength'],'reported')
        self.assertFalse(result['items'][0]['reviewed'])
        self.assertEqual(result['validation'],'structural_and_exact_quote_attribution_only')
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.brain.root.rglob('*') if p.is_file()})

    def test_fabricated_quote_and_foreign_record_rejected(self):
        for field,value in [('quote','Fabricated result'),('record_id','foreign-record')]:
            raw=copy.deepcopy(self.raw);raw['items'][0]['claims'][0][field]=value
            with self.assertRaisesRegex(ValueError,'not in the supplied'):
                self.check(raw)

    def test_tampered_input_cannot_authorize_invented_evidence(self):
        payload=copy.deepcopy(self.payload);payload['records'][0]['text']='Fabricated result'
        with self.assertRaisesRegex(ValueError,'differs from retained'):
            self.check(payload=payload)

    def test_extra_authority_fields_rejected(self):
        for field in ('confidence','work_stage','evidence_strength','reviewed'):
            raw=copy.deepcopy(self.raw);raw['items'][0][field]='verified'
            with self.assertRaisesRegex(ValueError,'Unexpected interpretation fields'):
                self.check(raw)

    def test_duplicate_json_keys_and_oversized_response_rejected(self):
        for response in ('{"items":[],"items":[],"relationships":[]}', ' '*65537):
            with self.assertRaises(ValueError):
                validate_proposals(self.brain,self.payload,response,model_identity=self.identity)

    def test_relationship_endpoints_and_quotes_required(self):
        self.raw['relationships']=[{'from':'decision1','to':'missing','kind':'supersedes','rationale':'Replacement', 'claims':[]}]
        with self.assertRaisesRegex(ValueError,'Invalid proposal relationship'):
            self.check()

    def test_input_budgets_and_reproducibility(self):
        limited=build_input(self.brain,self.pid,max_records=1)
        self.assertEqual(len(limited['records']),1)
        self.assertTrue(limited['coverage']['omitted'])
        self.assertEqual(self.payload,build_input(self.brain,self.pid))
        with self.assertRaises(ValueError):
            build_input(self.brain,self.pid,max_records=0)

    def test_source_instructions_are_data_and_do_not_grant_tools(self):
        self.assertIn('untrusted quoted data',self.payload['instructions'])
        raw=copy.deepcopy(self.raw);raw['tool_calls']=[{'command':'execute'}]
        with self.assertRaisesRegex(ValueError,'Unexpected interpretation fields'):
            self.check(raw)
