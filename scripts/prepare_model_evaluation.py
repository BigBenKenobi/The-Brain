"""Prepare reproducible project-scoped inputs; this does not run inference."""
import argparse
import json
from pathlib import Path
from brain.core import Brain, read
from brain.interpretation import build_input


def prepare(corpus, output):
    report=read(corpus/'report.json')
    brain=Brain(corpus/'store')
    output.mkdir(parents=True,exist_ok=False)
    checkpoints={}
    for label, checkpoint in report['checkpoints'].items():
        payload=build_input(brain,checkpoint['project_id'],snapshot_id=checkpoint['snapshot'])
        (output/(label+'-input.json')).write_text(json.dumps(payload,indent=2)+'\n')
        text='\n'.join(r['text'] for r in payload['records']).lower()
        hits={entry['label']:entry['phrase'].lower() in text for entry in checkpoint['expectations']}
        checkpoints[label]={'input_sha256':payload['input_sha256'],
            'records':len(payload['records']),'text_chars':payload['coverage']['text_chars'],
            'omitted':len(payload['coverage']['omitted']), 'answer_key_phrase_in_input':hits}
    result={'inference_run':False,'model_selected':False,'source_corpus':str(corpus),
        'checkpoints':checkpoints,'limitations':[
            'Phrase presence measures input coverage, not extraction quality or factual support.',
            'Answers remain outside model inputs. Actual host inference, latency and memory measurement are pending.',
            'Hosting device SSH work deferred at user request.']}
    (output/'preparation-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.corpus.resolve(),args.output.resolve()),indent=2))
