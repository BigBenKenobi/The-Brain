from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from brain.core import Brain, initialize, read, write, validate
from brain.storage import blob_path, compact_copy, preview, materialize
from brain.state import ProjectState


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        (self.source/'stable.md').write_text('# Decision\nKeep retained evidence.\n'+'Repeated source documentation.\n'*1000)
        (self.source/'changing.md').write_text('# Known issue\nUnresolved publication failure.\n')
        initialize(self.root/'store');self.b=Brain(self.root/'store')
        self.pid=self.b.ingest(self.source)['project_id']

    def hashes(self):
        return {str(p.relative_to(self.b.root)):p.read_bytes() for p in self.b.root.rglob('*') if p.is_file()}

    def test_changed_snapshots_share_immutable_evidence_and_observation_reads(self):
        first=self.b.snapshot(self.pid)
        sha=next(f['sha256'] for f in first['files'] if f['path']=='stable.md')
        blob=blob_path(self.b.root,self.pid,sha);before=blob.read_bytes()
        for n in range(3):
            (self.source/'changing.md').write_text(f'# Known issue\nUnresolved publication failure number {n}.\n')
            self.b.ingest(self.source)
        self.b.ingest(self.source)
        self.assertEqual(blob.read_bytes(),before)
        self.assertEqual(len(list(blob.parent.glob('*.zlib'))),5)
        self.assertTrue(validate(self.b.snapshot(self.pid))['valid'])
        self.assertEqual(self.b.snapshot(self.pid,first['id']),first)
        self.assertTrue(self.b.archive(self.pid)['integrity_verified'])

    def test_missing_and_corrupt_blobs_fail_closed(self):
        s=self.b.snapshot(self.pid);sha=next(iter(s['evidence']));p=blob_path(self.b.root,self.pid,sha)
        p.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'Invalid compressed'):
            self.b.snapshot(self.pid)
        with self.assertRaises(ValueError):
            self.b.ingest(self.source)
        p.unlink()
        with self.assertRaises(FileNotFoundError):
            self.b.snapshot(self.pid)

    def test_blob_refs_reject_traversal_conflicting_embedded_content_and_duplicates(self):
        path=self.b.root/'projects'/self.pid/'snapshots'/(self.b.project(self.pid)['snapshot']+'.json')
        raw=read(path)
        for refs in (['../../foreign'],raw['evidence_refs']*2):
            bad=dict(raw,evidence_refs=refs)
            with self.assertRaises(ValueError): materialize(self.b.root,bad)
        with self.assertRaises(ValueError): materialize(self.b.root,dict(raw,evidence={}))

    def test_failed_publication_keeps_old_snapshot_and_retry_uses_safe_orphans(self):
        before=self.b.snapshot(self.pid);real=write
        (self.source/'changing.md').write_text('# Decision\nUse bounded retry for failed writes.\n')
        def fail(path,value):
            if Path(path)==self.b.registry_path:raise OSError('publication failure')
            real(path,value)
        with patch('brain.core.write',side_effect=fail):
            with self.assertRaises(OSError): self.b.ingest(self.source)
        self.assertEqual(self.b.snapshot(self.pid),before)
        self.b.ingest(self.source)
        self.assertTrue(validate(self.b.snapshot(self.pid))['valid'])

    def legacy_fixture(self):
        # Simulate pre-blob physical storage while retaining real canonical evidence.
        self.b.ingest(self.source)
        for path in (self.b.root/'projects'/self.pid/'snapshots').glob('*.json'):
            snapshot=self.b.snapshot(self.pid,path.stem)
            write(path,snapshot)
        config=read(self.b.root/'config.json');config['schema_version']=3;write(self.b.root/'config.json',config)
        return Brain(self.b.root)

    def test_copy_preserves_snapshots_approvals_state_archive_and_sources(self):
        snap=self.b.snapshot(self.pid);r=next(r for r in snap['records'] if r['reuse_candidate'])
        self.b.promote(self.pid,r['id'],['sqlite'],'Reviewed evidence')
        self.b.archive(self.pid)
        state=ProjectState(self.b,self.pid);item=next(iter(state.view()['items'].values()))
        state.correct(item['id'],{'currency':'active'},item['claims'][0],'Explicit review')
        old=self.legacy_fixture();before=self.hashes();source_before=(self.source/'stable.md').read_bytes()
        expected=old.briefing(self.pid)
        report=compact_copy(old,self.root/'compact')
        new=Brain(self.root/'compact')
        self.assertFalse(report['activated']);self.assertEqual(report['snapshots_compared_equal'],2)
        self.assertEqual(old.snapshot(self.pid),new.snapshot(self.pid))
        self.assertEqual(expected,new.briefing(self.pid))
        self.assertEqual(old.retrieve('retained evidence',self.pid),new.retrieve('retained evidence',self.pid))
        # A worker-lock file can be created, but no retained artifact may change.
        self.assertEqual(before,{k:v for k,v in self.hashes().items() if k in before})
        self.assertEqual(source_before,(self.source/'stable.md').read_bytes())
        self.assertTrue(new.archive(self.pid)['integrity_verified'])

    def test_failed_migration_never_publishes_destination(self):
        old=self.legacy_fixture();before=self.hashes()
        with patch('brain.storage.store_blobs',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):compact_copy(old,self.root/'failed')
        self.assertFalse((self.root/'failed').exists())
        self.assertEqual(before,{k:v for k,v in self.hashes().items() if k in before})
        self.assertFalse(list(self.root.glob('.brain-compact-*')))

    def test_copy_rejects_links_that_could_modify_original_or_external_files(self):
        external=self.root/'external';external.mkdir()
        (self.b.root/'projects'/self.pid/'outside').symlink_to(external,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'unexpected symlink'):
            compact_copy(self.b,self.root/'unsafe-copy')
        self.assertFalse((self.root/'unsafe-copy').exists())
        self.assertEqual(list(external.iterdir()),[])

    def test_capacity_counts_pending_blobs_before_publication(self):
        before=self.b.snapshot(self.pid)
        (self.source/'changing.md').write_text('# Decision\nDifferent source content.\n')
        with self.assertRaisesRegex(OSError,'capacity'):
            self.b.ingest(self.source,max_store_bytes=1)
        self.assertEqual(self.b.snapshot(self.pid),before)

    def test_preview_has_no_loss_and_destination_cannot_overwrite_source(self):
        self.assertEqual(preview(self.b)['loss_preview']['evidence_removed'],0)
        for path in (self.b.root,self.b.root/'nested',self.root):
            with self.assertRaises(ValueError):compact_copy(self.b,path)

    def test_version_three_observations_upgrade_without_rewriting_history(self):
        first=self.b.snapshot(self.pid)
        first_path=self.b.root/'projects'/self.pid/'snapshots'/(first['id']+'.json')
        write(first_path,first)
        self.b.ingest(self.source)
        before={str(p):p.read_bytes() for p in first_path.parent.glob('*.json')}
        config=read(self.b.root/'config.json');config['schema_version']=3;write(self.b.root/'config.json',config)
        legacy=Brain(self.b.root)
        result=legacy.upgrade_store(self.root/'upgrade-backup')
        self.assertEqual(result['schema_version'],4)
        self.assertEqual(before,{str(p):p.read_bytes() for p in first_path.parent.glob('*.json')})
        self.assertTrue(validate(legacy.snapshot(self.pid))['valid'])

    def test_copy_preserves_group_conflict_and_undo_without_touching_original(self):
        (self.source/'other.md').write_text('# Decision\nPreserve local evidence because original sources can disappear.\n')
        self.b.ingest(self.source)
        state=ProjectState(self.b,self.pid)
        items=state.view()['items']
        first=next(i for i in items.values() if i['claims'][0]['path']=='stable.md')
        second=next(i for i in items.values() if i['claims'][0]['path']=='other.md')
        event=state.consolidate(first['id'],second['id'],'Reviewed equivalent preservation support')
        self.b.relate(self.pid,second['claims'][0]['record_id'],first['claims'][0]['record_id'],
                      'supersedes','Later review identifies successive choices')
        before=self.hashes();expected=state.view()
        report=compact_copy(self.b,self.root/'grouped-copy')
        copied=Brain(self.root/'grouped-copy');view=ProjectState(copied,self.pid)
        self.assertEqual(view.view(),expected)
        self.assertTrue(view.view()['items'][first['id']]['consolidation_conflicts'])
        view.undo(event['id'],'Withdraw grouping on the copy')
        self.assertNotIn('consolidated_into',view.view()['items'][second['id']])
        self.assertNotIn('consolidated_members',view.view()['items'][first['id']])
        self.assertEqual(before,{k:v for k,v in self.hashes().items() if k in before})
        self.assertTrue(copied.archive(self.pid)['integrity_verified'])
        self.assertGreaterEqual(report['derived_state_projects_checked'],1)

    def test_unreadable_published_state_prevents_verified_copy_publication(self):
        state=ProjectState(self.b,self.pid);item=next(iter(state.view()['items'].values()))
        event=state.correct(item['id'],{'currency':'active'},item['claims'][0],'Reviewed evidence')
        (state.root/'events'/(event['id']+'.json')).unlink()
        before=self.hashes()
        with self.assertRaises((OSError,ValueError)):
            compact_copy(self.b,self.root/'broken-state-copy')
        self.assertFalse((self.root/'broken-state-copy').exists())
        self.assertEqual(before,{k:v for k,v in self.hashes().items() if k in before})

    def test_catalogue_reference_missing_from_snapshot_prevents_copy(self):
        project=self.b.project(self.pid)
        path=self.b.root/'projects'/self.pid/'state/catalogs'/(project['state_catalog']+'.json')
        catalog=read(path);entry=next(iter(catalog['entries'].values())).copy()
        entry['record_id']='f'*64;catalog['entries']['f'*64]=entry;write(path,catalog)
        with self.assertRaises(ValueError):compact_copy(self.b,self.root/'broken-catalogue-copy')
        self.assertFalse((self.root/'broken-catalogue-copy').exists())

    def test_undone_event_evidence_still_requires_valid_historical_reference(self):
        state=ProjectState(self.b,self.pid);item=next(iter(state.view()['items'].values()))
        event=state.correct(item['id'],{'currency':'active'},item['claims'][0],'Reviewed evidence')
        state.undo(event['id'],'Withdraw interpretation')
        path=state.root/'events'/(event['id']+'.json')
        saved=read(path);saved['evidence']['sha256']='0'*64;write(path,saved)
        # The ordinary view can skip the undone correction; migration must retain
        # a valid audit trail even for evidence outside that active interpretation.
        self.assertTrue(state.view()['items'])
        with self.assertRaisesRegex(ValueError,'disagrees with canonical evidence'):
            compact_copy(self.b,self.root/'invalid-audit-copy')
        self.assertFalse((self.root/'invalid-audit-copy').exists())
