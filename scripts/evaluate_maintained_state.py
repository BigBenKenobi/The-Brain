"""Replay real retained history, then simulate absence on a disposable source copy.

No source script is executed. Reference answers remain outside captured inputs.
The absence extension is a synthetic stress case, not another real project trial.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from brain.core import Brain,read,write,digest
from brain.state import ProjectState,bounded_view


def legacy_selection(state,limit=20):
    """Reproduce the preceding all-blockers-first display for paired comparison."""
    priority={'blocker':0,'decision':1,'attempt':2,'idea':3}
    items=[i for i in state['items'].values() if i['currency']!='superseded']
    return [{**i,'summary':i['summary'][:400]} for i in sorted(items,key=lambda i:(-i['reviewed'],priority[i['kind']],i['id']))[:limit]]


def traced(brain,pid,items):
    """Require each displayed item claim to resolve to its canonical same-project record."""
    count=0
    for item in items:
        for claim in item['claims']:
            s=brain.snapshot(pid,claim['snapshot'])
            r=next(r for r in s['records'] if r['id']==claim['record_id'])
            for key in ('path','sha256','start_line','end_line'):
                if claim[key]!=r['evidence'][key]:raise ValueError('State claim provenance changed')
            text=brain.retained_evidence(pid,claim['path'],claim['start_line'],claim['end_line'],claim['snapshot'])['text']
            if r['statement'] not in text:raise ValueError('State record not supported by retained evidence')
            count+=1
    return count


def evaluate(corpus,output):
    reference=read(corpus/'report.json')
    before={str(p.relative_to(corpus/'store')):digest(p.read_bytes()) for p in (corpus/'store').rglob('*') if p.is_file()}
    output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(corpus/'store',output/'store')
    b=Brain(output/'store');b.upgrade_store(output/'pre-upgrade')
    comparisons={}
    for label,point in reference['checkpoints'].items():
        registry=read(b.registry_path);registry['projects'][point['project_id']]['snapshot']=point['snapshot'];write(b.registry_path,registry)
        state=ProjectState(b,point['project_id']).view();shown=bounded_view(state);old=legacy_selection(state)
        checks={}
        for entry in point['expectations']:
            phrase=entry['phrase'].lower()
            checks[entry['label']]={'in_full_state':any(phrase in i['summary'].lower() for i in state['items'].values()),
                'previous_display':any(phrase in i['summary'].lower() for i in old),
                'balanced_display':any(phrase in i['summary'].lower() for i in shown['items'])}
        comparisons[label]={'total_items':len(state['items']),'displayed':len(shown['items']),
            'displayed_kinds':sorted({i['kind'] for i in shown['items']}),'omitted':shown['omitted_items'],
            'claims_traced':traced(b,point['project_id'],shown['items']),'checks':checks,
            'private_canary_absent':'PRIVATE_CANARY_JUNIPER' not in json.dumps(shown)}
        write(output/(label+'-state.json'),shown)
    # Extend the actual captured local checkpoint with a labelled synthetic absence
    # case. Only the disposable copy is altered; no real project event is claimed.
    point=reference['checkpoints']['04-unchanged'];pid=point['project_id']
    state=ProjectState(b,pid);state.sync()
    prior=state.view()
    remembered=[i for i in prior['items'].values() if i['claims'][0]['path']=='history/capture-review.md']
    if not remembered:raise ValueError('Missing capture-review pilot evidence')
    shutil.copytree(corpus/'source',output/'source')
    (output/'source'/'history'/'capture-review.md').unlink()
    for n in range(10):
        (output/'source'/'simulation.md').write_text(f'# Decision\nSynthetic capture number {n} exercises state retention.\n')
        b.ingest(output/'source',project_id=pid)
    after=state.view(max_snapshots=1)
    preserved=all(i['id'] in after['items'] and
        after['items'][i['id']]['availability']=='retained_history_only' and
        after['items'][i['id']]['work_stage']==i['work_stage'] and
        after['items'][i['id']]['currency']==i['currency'] for i in remembered)
    if not preserved:raise ValueError('Absence changed state or lost a historical item')
    traced(b,pid,[after['items'][i['id']] for i in remembered])
    after_hashes={str(p.relative_to(corpus/'store')):digest(p.read_bytes()) for p in (corpus/'store').rglob('*') if p.is_file()}
    if before!=after_hashes:raise ValueError('Original corpus changed')
    result={'comparisons':comparisons,'original_corpus_unchanged':True,
        'synthetic_absence_extension':{'captures':10,'history_scan_budget':1,'items_preserved':len(remembered),
            'stages_and_currency_unchanged':preserved,'claims_traced':True},
        'limitations':['Phrase checks measure visibility, not semantic accuracy.',
            'Objectives belong primarily to briefing sections, not the four maintained item kinds.',
            'Absence extension is simulated against copied real-history inputs.',
            'Human resumption, model evaluation and a second real project remain pending.']}
    write(output/'report.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--corpus',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(evaluate(a.corpus.resolve(),a.output.resolve()),indent=2))
