"""Small real-history Tinker pilot from three explicitly selected tracked documents.

Read exact Git blobs; never execute source instructions or inspect application data.
Answer keys and revision manifests stay outside capture input. Report lexical
visibility separately from retained evidence and human/semantic acceptance.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from brain.core import Brain,initialize,digest,read,write,validate
from brain.state import ProjectState,bounded_view
from brain.briefing import render_briefing

REVISIONS=(
 '2631a427da905179a3550a535256a5c8209b17dd',
 '99edf8a74582553a9730d9680524ad6089564155',
 '424d1b52b69147a3ff29d32b3c2721e3b1d70109')
FILES=('README.md','docs/PROJECT_ASSISTANT.md','docs/RELEASE_READINESS.md')
KEYS=(
 {'local inference':'application-owned offline text inference','explicit source review':'Approve reads',
  'physical acceptance still open':'physical-device'},
 {'host ownership':'service owns models','model expansion':'gpt-oss-20b',
  'review separate from verification':'real-model usefulness'},
 {'pre-release status':'pre-release candidate','retired gate not passed':'not been relabelled',
  'unresolved validation':'Note retry first-stream timeout','host connectivity limitation':'direct access',
  'source review boundary':'Approve reads'})


def git(repo,*args):
    """Read versioned content only; no checked-out script is executed."""
    return subprocess.check_output(['git','-C',str(repo),*args])


def assess(b,pid,key):
    """Compare short-view visibility with full retained evidence and scoped retrieval."""
    started=time.monotonic();brief=b.briefing(pid);state=ProjectState(b,pid).view()
    snapshot=b.snapshot(pid);validate(snapshot)
    excerpts=[i for section in brief['sections'].values() for i in section['items']]
    for item in excerpts:
        e=item['evidence']
        retained=b.retained_evidence(pid,e['path'],e['start_line'],e['end_line'],item['snapshot'])
        if item['excerpt'] not in retained['text']:raise ValueError('Untraceable briefing excerpt')
    checks={}
    for label,phrase in key.items():
        needle=phrase.casefold()
        checks[label]={'phrase':phrase,
          'retained':any(needle in text.casefold() for text in snapshot['evidence'].values()),
          'briefing_visible':any(needle in i['excerpt'].casefold() for i in excerpts),
          'state_retained':any(needle in i['summary'].casefold() for i in state['items'].values()),
          'context_retrievable':any(needle in i['statement'].casefold() for i in b.retrieve(phrase,pid,limit=5))}
    return brief,{'checks':checks,'traceable_excerpts':len(excerpts),
        'private_canary_absent':'SECOND_PROJECT_PRIVATE_CANARY' not in json.dumps(brief),
        'all_current_records_reported':all(r['evidence_status'] in ('historical_record','proposal') for r in snapshot['records']),
        'assessment_seconds':time.monotonic()-started,'state_items':len(state['items'])}


def run(repo,output):
    """Capture selected historical revisions in a disposable independent pilot store."""
    prepared=[]
    for revision in REVISIONS:
        if git(repo,'rev-parse',revision).decode().strip()!=revision:raise ValueError('Revision mismatch')
        paths=set(git(repo,'ls-tree','-r','--name-only',revision).decode().splitlines())
        prepared.append({p:git(repo,'show',revision+':'+p) for p in FILES if p in paths})
    output.mkdir(parents=True,exist_ok=False)
    source=output/'selected-source';source.mkdir()
    initialize(output/'store');b=Brain(output/'store')
    unrelated=output/'unrelated-fixture';unrelated.mkdir()
    (unrelated/'note.md').write_text('# Decision\nSECOND_PROJECT_PRIVATE_CANARY stays private.\n')
    b.ingest(unrelated)
    manifest=[];checkpoints=[]
    write(output/'answer-keys.json',list(KEYS))
    for revision,files,key in zip(REVISIONS,prepared,KEYS):
        for relative in FILES:
            path=source/relative
            if relative not in files:path.unlink(missing_ok=True);continue
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(files[relative])
        capture=b.ingest(source)
        manifest.append({'revision':revision,'selected_sha256':{p:digest(data) for p,data in files.items()},
            'absent_at_revision':sorted(set(FILES)-set(files))})
        briefing,evaluation=assess(b,capture['project_id'],key)
        label=str(len(checkpoints)+1)
        write(output/(label+'-briefing.json'),briefing)
        (output/(label+'-briefing.md')).write_text(render_briefing(briefing)+'\n')
        evaluation.update(revision=revision,project_id=capture['project_id'],snapshot=capture['snapshot'])
        checkpoints.append(evaluation)
    pid=capture['project_id'];sid=capture['source_id']
    original=b.snapshot(pid)
    observed=b.refresh(sid);unchanged=b.snapshot(pid)
    if unchanged['evidence']!=original['evidence']:raise ValueError('Unchanged refresh lost evidence')
    # Deliberately unavailable copied source tests recovery without touching Tinker.
    source.rename(output/'temporarily-unavailable')
    try:b.refresh(sid)
    except OSError:pass
    else:raise ValueError('Missing pilot source unexpectedly refreshed')
    failed=b.briefing(pid)
    (output/'temporarily-unavailable').rename(source)
    recovery=b.refresh(sid)
    if recovery['capture']['state']!='complete':raise ValueError('Pilot source did not recover')
    report={'project':'Tinker','selection':list(FILES),'manifest':manifest,'checkpoints':checkpoints,
      'resilience':{'unchanged_observation':observed['observation_only'],
        'outage_preserved_snapshot':failed['snapshot']==unchanged['id'],
        'failure_visible':any(h['state']=='failed' for h in failed['source_health']),
        'recovery_complete':True,'recovered_snapshot_valid':validate(b.snapshot(pid))['valid']},
      'automation_enabled':False,'sharing_approved':False,'live_tinker_modified':False,
      'owner_resumption':{'baseline_seconds':None,'with_brain_seconds':None,'accepted':False},
      'limitations':['Three tracked documents only; no application database, chat, model, source-code execution or bulk import.',
        'Historical source claims are retained reports, not independently verified present-day product status.',
        'Lexical checks do not prove semantic understanding, supersession or human resumption benefit.',
        'Missing release-readiness file in older revisions is absence of evidence, not evidence of readiness.',
        'The second-project technical pilot does not complete owner acceptance or local-model evaluation.']}
    write(output/'report.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--tinker-repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    report=run(args.tinker_repo.resolve(),args.output.resolve())
    print(json.dumps(report,indent=2))
