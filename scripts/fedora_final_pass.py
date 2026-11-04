"""Final knowledge-preservation audit. Reads source data; never executes it."""
from collections import Counter
from pathlib import Path
import json
import os
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain.core import Brain, read, write, validate
from scripts.ingest_fedora import SOURCE, ROOT, REVIEW, inventory

b=Brain(ROOT)
b.config.update(max_files=10000,max_file_bytes=8388608,max_total_bytes=67108864,max_seconds=180)
before=inventory()
original=read(REVIEW/'first-runs.json')
final=[]
for run in original:
 result=b.ingest(run['source'], run['project_id'], run.get('excluded_paths',[]),run['historical'])
 final.append(dict(name=run['name'],source=run['source'],historical=run['historical'],excluded_paths=run.get('excluded_paths',[]),**result))
write(REVIEW/'final-pass-runs.json',final)
latest={r['project_id']:r for r in final}
results=[]
for pid,run in latest.items():
 s=b.snapshot(pid)
 repeated=b.ingest(run['source'],pid,run['excluded_paths'],run['historical'])
 assert repeated['metrics']['extractions']==0
 current=b.snapshot(pid)
 assert current['records']==s['records'] and current['evidence']==s['evidence']
 validate(current)
 original_path_open=Path.open
 def guarded_open(path,*args,**kwargs):
  if str(path).startswith(str(SOURCE)):raise AssertionError('Original source access forbidden during verification')
  return original_path_open(path,*args,**kwargs)
 with patch.object(Path,'open',guarded_open):
  docs=[r for r in current['records'] if r['evidence']['path'].endswith(('.md','.txt','.rst'))]
  chosen=[]
  for kind in ['decision','solution','lesson','limitation','unresolved']:
   r=next((r for r in docs if kind in r.get('knowledge_kinds',[])),None)
   if r:chosen.append(r['id'])
  if not chosen:chosen=[current['records'][0]['id']]
  gaps=['Historical application references are partial copies; active retrieval searches only the latest snapshot. Earlier copies remain in history.',
        'Unsupported binary/image/archive content and sensitive material are intentionally not interpreted; source reconstruction is outside the discard-and-preserve-knowledge goal.',
        'Deterministic extraction can miss implicit relationships and text outside its windows; documented tests remain claims, not fresh hardware verification.']
  if run['name']=='Fedora setup':
   gaps.append('Delegated application and NetworkSurvey scopes have separate identities and reviews. Asset artwork, ISO and archives are disposable source materials; no full recovery objective was requested.')
  queries=['DKMS depmod','srcversion','umask'] if run['name']=='Fedora setup' else (['cross-device wireless throughput'] if run['name']=='NetworkSurvey' else ['solution decision'])
  hits={q:b.retrieve(q,pid,limit=3,max_chars=15000) for q in queries}
  # Full retained evidence for each nominated source is checked without the source tree.
  for rid in chosen:
   r=next(r for r in current['records'] if r['id']==rid);e=r['evidence']
   assert b.retained_evidence(pid,e['path'],e['start_line'],e['end_line'])['text']
  assessment=b.review_retirement(pid,
   'Final discard-oriented review: screened retained documentation and explicit decision/solution/lesson/limitation/unresolved excerpts; historical boundaries and omissions inspected. '+run['name']+' remains private. Source recovery is not the objective.',gaps,chosen)
  assert assessment['knowledge_retirement_ready']
 results.append(dict(name=run['name'],project_id=pid,snapshot=current['id'],records=len(current['records']),
   statuses=dict(Counter(f['status'] for f in current['files'])),repeat_metrics=repeated['metrics'],
   source_reads_blocked=True,queries=hits,retirement=assessment))
assert before==inventory(), 'Source metadata changed during final pass'
# Coverage includes earlier historical scopes, not only active reference copies.
entries={}
for run in final:
 s=b.snapshot(run['project_id'],run['snapshot'])
 for f in s['files']:
  if f['status']!='excluded_directory':entries[str(Path(run['source'])/f['path'])]=f
write(REVIEW/'final-pass-verification.json',dict(projects=results,source_metadata_unchanged=True,
 coverage=dict(Counter(f['status'] for f in entries.values())),files=len(entries),
 budgets={k:b.config[k] for k in ['max_files','max_file_bytes','max_total_bytes','max_seconds']},model_calls=0))
print(json.dumps({'files':len(entries),'coverage':dict(Counter(f['status'] for f in entries.values())),
 'active_records':sum(r['records'] for r in results),'identities':len(results),
 'ready':all(r['retirement']['knowledge_retirement_ready'] for r in results)},indent=2))
