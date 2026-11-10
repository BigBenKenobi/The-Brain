"""Run one explicitly supplied local check and preserve a bounded private receipt.

This developer CLI never reads a command from captured evidence or changes a Brain
store. A process exit status establishes only the observed command outcome; an
owner must still review its assertions, behavioral scope and environment before
using the receipt as verification evidence. POSIX process groups bound cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import signal
import subprocess
import time


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_identity(cwd):
    """Observe revision and tracked dirt without loading arbitrary repository data."""
    try:
        head = subprocess.run(['git', '-C', str(cwd), 'rev-parse', 'HEAD'],
                              capture_output=True, timeout=10, check=True).stdout.decode().strip()
        status = subprocess.run(['git', '-C', str(cwd), 'diff', '--quiet', '--no-ext-diff', 'HEAD', '--'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if status.returncode not in (0, 1):
            raise ValueError('Git status unavailable')
        return {'head': head, 'tracked_clean': status.returncode == 0,
                'untracked_files': 'not_inventoried',
                'limit': 'Revision and tracked status are not a source archive; untracked inputs may affect execution.'}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'head': None, 'tracked_clean': None, 'limit': 'Git source identity unavailable.'}


def run(command, cwd, output, scope, environment, timeout=60, max_bytes=1048576):
    """Capture one process tree, enforcing time/output bounds and exclusive output.

    All command arguments come from the explicit caller. Neither the environment
    label nor the scope description is independently validated. Receipts distinguish
    those assertions from observed process facts and never certify project state.
    """
    if os.name != 'posix':
        raise ValueError('The bounded verification runner currently requires POSIX')
    if not command or not scope.strip() or not environment.strip():
        raise ValueError('Command, scope and environment description are required')
    if not 0 < timeout <= 3600 or type(max_bytes) is not int or not 1 <= max_bytes <= 16777216:
        raise ValueError('Timeout must be at most 3600 seconds; output cap must be 1..16777216 bytes')
    cwd = Path(cwd).resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError('Working directory must be a directory')
    output = Path(output).absolute()
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    before = source_identity(cwd)
    started = time.time(); clock = time.monotonic()
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    outcome = 'launch_failed'; process = None
    try:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        with selectors.DefaultSelector() as selector:
            for name in streams:
                pipe = getattr(process, name)
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, name)
            outcome = 'running'
            while selector.get_map() or process.poll() is None:
                remaining = timeout - (time.monotonic() - clock)
                if remaining <= 0:
                    outcome = 'timeout'; break
                for key, _ in selector.select(min(remaining, 0.05)):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    room = max_bytes - sum(len(v) for v in streams.values())
                    streams[key.data].extend(data[:room])
                    if len(data) > room:
                        outcome = 'output_limit'; break
                if outcome == 'output_limit':
                    break
            if outcome == 'running':
                outcome = 'passed' if process.wait() == 0 else 'failed'
    except OSError:
        outcome = 'launch_failed'
    finally:
        if process is not None:
            # Reap the whole owned group even if the direct child exited first.
            # A background child must not escape the declared checking interval.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            process.stdout.close(); process.stderr.close()
    receipt = {
        'version': 1, 'status': 'execution_observed_not_adopted',
        'scope': scope, 'environment_description': environment,
        'description_authority': 'caller_supplied', 'command': command, 'cwd': str(cwd),
        'host': {'system': platform.system(), 'release': platform.release(),
                 'machine': platform.machine()},
        'source_before': before, 'source_after': source_identity(cwd),
        'started_at': started, 'duration_seconds': time.monotonic() - clock,
        'outcome': outcome, 'exit_code': process.returncode if process else None,
        'limits': {'timeout_seconds': timeout, 'output_bytes': max_bytes},
        'outputs': {name: {'bytes': len(data), 'sha256': sha(data),
                           'file': name + '.bin'} for name, data in streams.items()},
        'output_complete': outcome in ('passed', 'failed'),
        'limitations': ['Exit zero does not establish that the described behavior was tested.',
                       'Inherited environment and external dependencies are not archived.',
                       'No sandbox or network isolation is provided by this runner.',
                       'No Brain item, capture configuration or sharing approval is changed.']}
    for name, data in streams.items():
        path = output / (name + '.bin')
        with path.open('xb') as stream:
            os.chmod(path, 0o600); stream.write(data)
    path = output / 'receipt.json'
    with path.open('x') as stream:
        os.chmod(path, 0o600); json.dump(receipt, stream, indent=2); stream.write('\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scope', required=True)
    parser.add_argument('--environment', required=True)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--max-bytes', type=int, default=1048576)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        receipt = run(command, args.cwd, args.output, args.scope, args.environment,
                      args.timeout, args.max_bytes)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'receipt': str(args.output / 'receipt.json'),
                      'outcome': receipt['outcome'], 'adopted': False}))
    return 0 if receipt['outcome'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
