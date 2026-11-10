"""Pin a verified package copy for the approved local refresh service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brain.core import Brain, write


def install(store, package=ROOT / 'brain'):
    brain = Brain(store)
    files = {p.name: p.read_bytes() for p in sorted(package.glob('*.py'))}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    revision = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:20]
    with brain.lock():
        runtime = brain.root / 'runtime'
        runtime.mkdir(exist_ok=True, mode=0o700)
        destination = runtime / revision
        if destination.exists():
            actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (destination / 'brain').glob('*.py')}
            if actual != hashes:
                raise ValueError('Existing pinned runtime was modified')
        else:
            stage = runtime / ('.stage-' + uuid.uuid4().hex)
            try:
                (stage / 'brain').mkdir(parents=True, mode=0o700)
                for name, data in files.items():
                    (stage / 'brain' / name).write_bytes(data)
                write(stage / 'manifest.json', {'revision': revision, 'sha256': hashes})
                os.replace(stage, destination)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        temporary = runtime / ('.current-' + uuid.uuid4().hex)
        try:
            temporary.symlink_to(revision, target_is_directory=True)
            os.replace(temporary, runtime / 'current')
        finally:
            temporary.unlink(missing_ok=True)
    return {'runtime': str(destination), 'revision': revision, 'sha256': hashes}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--brain', type=Path, required=True)
    args=parser.parse_args()
    print(json.dumps(install(args.brain), indent=2))
