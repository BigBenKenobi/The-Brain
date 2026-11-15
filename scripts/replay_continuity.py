"""Evaluate a new reader against an unchanged captured B06 corpus."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from evaluate_continuity import assess, save, ROOT
from brain.core import Brain, read, write
from brain.briefing import render_briefing


def replay(corpus, output):
    baseline=read(corpus/'report.json')
    output.mkdir(parents=True,exist_ok=False)
    comparisons={}
    with tempfile.TemporaryDirectory(prefix='brain-pilot-replay-') as temporary:
        store=Path(temporary)/'store'
        shutil.copytree(corpus/'store',store)
        # Historical checkpoint replay must not import a later outage attempt.
        shutil.rmtree(store/'health',ignore_errors=True)
        brain=Brain(store)
        for label, old in baseline['checkpoints'].items():
            registry=read(brain.registry_path)
            registry['projects'][old['project_id']]['snapshot']=old['snapshot']
            write(brain.registry_path,registry)
            key={e['label']:e['phrase'] for e in old['expectations']}
            briefing,result=assess(brain,old['project_id'],key)
            save(output/(label+'-briefing.json'),briefing)
            (output/(label+'-briefing.md')).write_text(render_briefing(briefing)+'\n')
            comparisons[label]={'before':old,'after':result}
    report={'source_corpus':str(corpus),'same_snapshots_replayed':True,'comparisons':comparisons,
            'human_resumption_measurement':baseline['human_resumption_measurement'],
            'limitations':baseline['limitations']}
    save(output/'report.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=replay(args.corpus.resolve(),args.output.resolve())
    print(json.dumps({k:{'before':v['before']['critical_hits'],'after':v['after']['critical_hits'],
                         'total':v['after']['critical_total'],'traceability':v['after']['traceability']}
                     for k,v in report['comparisons'].items()},indent=2))
