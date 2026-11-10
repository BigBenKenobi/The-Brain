from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from brain.core import Brain,initialize,read,write


class RetrievalScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);initialize(root/'store');self.b=Brain(root/'store')
        self.ids=[]
        for name in ('own','approved','unrelated'):
            source=root/name;source.mkdir()
            (source/'notes.md').write_text(f'# Decision\nSQLite locking uses bounded retry in {name}.\n')
            self.ids.append(self.b.ingest(source)['project_id'])
        self.own,self.foreign,self.unrelated=self.ids
        self.record=self.b.snapshot(self.foreign)['records'][0]
        self.approval=self.b.root/'shared'/(self.record['id']+'.json')

    def approve(self):
        self.b.promote(self.foreign,self.record['id'],['sqlite'],'Reviewed retry scope')

    def query(self, technologies=()):
        with patch.object(self.b,'snapshot',wraps=self.b.snapshot) as spy:
            result=self.b.retrieve('SQLite locking',self.own,technologies=technologies)
        return result,[c.args[0] for c in spy.call_args_list]

    def test_private_context_never_loads_unapproved_projects(self):
        result,loaded=self.query()
        self.assertEqual(loaded,[self.own])
        self.assertEqual({r['project_id'] for r in result},{self.own})
        path=self.b.root/'projects'/self.unrelated/'snapshots'/(self.b.project(self.unrelated)['snapshot']+'.json')
        path.write_text('corrupt unrelated evidence')
        self.assertEqual(self.query()[0],result)

    def test_matching_approval_loads_only_own_and_approved_and_rechecks_revocation(self):
        self.approve()
        result,loaded=self.query(['sqlite'])
        self.assertEqual(set(loaded),{self.own,self.foreign})
        self.assertEqual({r['project_id'] for r in result},{self.own,self.foreign})
        self.approval.unlink()
        self.assertEqual(self.query(['sqlite'])[1],[self.own])

    def test_expired_and_incompatible_grants_do_not_load_foreign_evidence(self):
        self.approve()
        self.assertEqual(self.query(['python'])[1],[self.own])
        a=read(self.approval);a['review_after']=0;write(self.approval,a)
        self.assertEqual(self.query(['sqlite'])[1],[self.own])

    def test_invalid_or_misbound_approvals_cannot_grant_access(self):
        self.approve();original=read(self.approval)
        for changes in ({'record_id':'wrong'}, {'project_id':self.unrelated},
                        {'review_after':float('nan')},{'permission':'private'},
                        {'technologies':[]},{'technologies':'sqlite'},
                        {'evidence_sha256':'wrong'},{'schema_version':999}):
            write(self.approval,dict(original,**changes))
            result,_=self.query(['sqlite'])
            self.assertEqual({r['project_id'] for r in result},{self.own},changes)
        self.approval.write_text('broken JSON')
        self.assertEqual(self.query(['sqlite'])[1],[self.own])

    def test_global_search_without_valid_grants_loads_no_private_snapshots(self):
        with patch.object(self.b,'snapshot',wraps=self.b.snapshot) as spy:
            self.assertEqual(self.b.retrieve('SQLite locking',technologies=['sqlite']),[])
        spy.assert_not_called()

    def test_approved_project_corruption_still_fails_closed(self):
        self.approve()
        path=self.b.root/'projects'/self.foreign/'snapshots'/(self.b.project(self.foreign)['snapshot']+'.json')
        path.write_text('broken JSON')
        with self.assertRaises(ValueError):self.query(['sqlite'])
