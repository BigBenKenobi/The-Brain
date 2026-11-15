"""Compare immutable-store retrieval outputs and work across two code packages."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

CHILD = '''import sys,json,time,resource,hashlib
sys.path.insert(0,sys.argv[1])
from brain.core import Brain
b=Brain(sys.argv[2]);pid=sys.argv[3];technology=sys.argv[4]
original=b.snapshot;loaded=[]
def counted(*a,**k):
 loaded.append(a[0]);return original(*a,**k)
b.snapshot=counted
start=time.perf_counter()
result=b.retrieve('automatic refresh bounded retry',pid,technologies=[technology] if technology else [],explain=True)
elapsed=time.perf_counter()-start
print(json.dumps({'elapsed_seconds':elapsed,'snapshot_loads':len(loaded),'distinct_projects_loaded':len(set(loaded)),'results_sha256':hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest(),'result_count':len(result['results']),'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
'''


def compare(baseline, candidate, store, pid, runs):
    cases={}
    for technology in ('','sqlite'):
        pairs=[]
        for _ in range(runs):
            pair={}
            for label,code in (('before',baseline),('after',candidate)):
                completed=subprocess.run([sys.executable,'-c',CHILD,str(code),str(store),pid,technology],
                    capture_output=True,text=True,check=True,timeout=180,cwd='/tmp')
                pair[label]=json.loads(completed.stdout)
            if pair['before']['results_sha256']!=pair['after']['results_sha256']:
                raise ValueError('Retrieval result mismatch')
            pairs.append(pair)
        cases[technology or 'no_foreign_technology']=pairs
    return {'store':str(store),'project_id':pid,'baseline_code':str(baseline),'candidate_code':str(candidate),
        'all_outputs_identical':True,'cases':cases,
        'limitations':['Local elapsed times are observations, not a universal latency guarantee.',
            'Each sample uses a fresh interpreter; filesystem caches may still be warm.',
            'Invalid approvals are now ignored as non-authorizing; this comparison covers the retained valid store.']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline-code',type=Path,required=True)
    p.add_argument('--store',type=Path,required=True);p.add_argument('--project-id',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--runs',type=int,default=3)
    a=p.parse_args()
    if not 1<=a.runs<=10:p.error('runs must be 1..10')
    result=compare(a.baseline_code.resolve(),Path(__file__).resolve().parents[1],a.store.resolve(),a.project_id,a.runs)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
