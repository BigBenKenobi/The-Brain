"""Execute actual CLI commands; delete only TemporaryDirectory fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
BRAIN = REPO / 'Project-Brain'


def main():
    logs = []
    def run(*args, plain=False):
        cmd = [sys.executable, '-m', 'brain', '--brain', str(BRAIN), *args]
        result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=True)
        value = result.stdout if plain else json.loads(result.stdout)
        logs.append({'command': ['python3', '-m', 'brain', '--brain', str(BRAIN), *args], 'exit_code': result.returncode, 'result': value})
        return value
    run('init')
    run('doctor')
    with tempfile.TemporaryDirectory(prefix='project-brain-demo-') as temp:
        source = Path(temp) / 'original'
        source.mkdir()
        (source / 'README.md').write_text('# Decision: SQLite retry\nSolution: bounded retry handles SQLite database locking during transient contention.\nLimitation: never retry permanent corruption. Outcome is documented, not independently verified.\n')
        (source / 'pyproject.toml').write_text('[project]\nname = "original"\nversion = "1.0"\n')
        (source / 'private.md').write_text('Internal confidential launch plans for orchard customers.')
        (source / '.env').write_text('PASSWORD=fixture-secret-value')
        (source / 'asset.bin').write_bytes(b'\x00\xff')
        first = run('ingest', str(source))
        pid = first['project_id']
        second = run('ingest', str(source))
        assert second['metrics']['extractions'] == 0
        own = run('context', pid, 'SQLite database locking')
        record = own[0]['id']
        run('promote', pid, record, '--approve-sharing', '--technology', 'sqlite', '--rationale', 'Reviewed as documented bounded retry advice; target must check error class')
        target = Path(temp) / 'new-project'
        target.mkdir()
        (target / 'README.md').write_text('A new application using SQLite.')
        target_id = run('ingest', str(target))['project_id']
        hits = run('context', target_id, 'SQLite database locking', '--technology', 'sqlite')
        assert len(hits) >= 1 and hits[0]['evidence_status'] == 'historical_record'
        assert run('search', 'orchard confidential launch', '--technology', 'sqlite') == []
        assert run('search', 'SQLite museum painting', '--technology', 'sqlite') == []
        run('status', pid)
        run('validate', pid)
        run('summary', pid, plain=True)
        run('retire-check', pid)
        archive = run('archive-evidence', pid)
        run('verify-archive', archive['archive'])
        shutil.rmtree(source)
        recovered = run('context', target_id, 'SQLite database locking', '--technology', 'sqlite')
        assert any(h['id'] == record for h in recovered)
        run('list')
        result = {'source_project': pid, 'target_project': target_id, 'first_ingestion_metrics': first['metrics'], 'unchanged_ingestion_metrics': second['metrics'], 'source_removed_fixture_only': True, 'retrieval_after_removal': True, 'commands': logs}
        (REPO / 'docs' / 'demo-results.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'commands'}, indent=2))

if __name__ == '__main__':
    main()
