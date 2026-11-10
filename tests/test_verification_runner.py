"""Exercise real process outcomes and bounds without certifying behavioral claims."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('verification_runner',
    Path(__file__).resolve().parents[1] / 'scripts' / 'run_verification.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class VerificationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_check(self, code, **limits):
        return runner.run([sys.executable, '-c', code], self.root,
                          self.root / 'receipt', 'A caller-described assertion',
                          'Synthetic isolated fixture', **limits)

    def test_exact_outputs_are_private_and_not_automatically_verified(self):
        result = self.run_check('import sys; print("observed"); sys.stderr.write("detail")')
        self.assertEqual(result['outcome'], 'passed')
        self.assertEqual(result['status'], 'execution_observed_not_adopted')
        self.assertEqual(result['description_authority'], 'caller_supplied')
        for name, expected in [('stdout', b'observed\n'), ('stderr', b'detail')]:
            path = self.root / 'receipt' / (name + '.bin')
            self.assertEqual(path.read_bytes(), expected)
            self.assertEqual(result['outputs'][name]['sha256'], hashlib.sha256(expected).hexdigest())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / 'receipt').stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads((self.root / 'receipt/receipt.json').read_text()), result)
        with self.assertRaises(FileExistsError):
            self.run_check('raise SystemExit(99)')

    def test_failed_command_and_missing_program_are_not_success(self):
        result = self.run_check('print("failed assertion"); raise SystemExit(7)')
        self.assertEqual((result['outcome'], result['exit_code']), ('failed', 7))
        self.assertTrue(result['output_complete'])
        result = runner.run([str(self.root / 'missing')], self.root,
                            self.root / 'missing-receipt', 'scope', 'fixture')
        self.assertEqual(result['outcome'], 'launch_failed')
        self.assertIsNone(result['exit_code'])

    def test_timeout_terminates_descendants_after_parent_exits(self):
        marker = self.root / 'escaped'
        child = 'import time,pathlib; time.sleep(.6); pathlib.Path(' + repr(str(marker)) + ').write_text("escaped")'
        code = 'import subprocess,sys; subprocess.Popen([sys.executable,"-c",' + repr(child) + '])'
        result = self.run_check(code, timeout=0.15)
        self.assertEqual(result['outcome'], 'timeout')
        self.assertFalse(result['output_complete'])
        time.sleep(0.65)
        self.assertFalse(marker.exists())

    def test_output_limit_stops_a_producer_and_marks_capture_incomplete(self):
        result = self.run_check('import os;\nwhile True: os.write(1,b"x"*4096)', max_bytes=127)
        self.assertEqual(result['outcome'], 'output_limit')
        self.assertEqual(sum(v['bytes'] for v in result['outputs'].values()), 127)
        self.assertFalse(result['output_complete'])

    def test_arguments_are_not_interpreted_by_a_shell(self):
        marker = self.root / 'shell-ran'
        value = '$(touch ' + str(marker) + ')'
        result = runner.run([sys.executable, '-c', 'import sys; print(sys.argv[1])', value],
                            self.root, self.root / 'receipt', 'scope', 'fixture')
        self.assertEqual(result['outcome'], 'passed')
        self.assertFalse(marker.exists())
        self.assertEqual((self.root / 'receipt/stdout.bin').read_text().strip(), value)

    def test_tracked_source_change_is_observed_without_claiming_an_archive(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        tracked = self.root / 'input.txt'; tracked.write_text('before')
        subprocess.run(['git', '-C', str(self.root), 'add', 'input.txt'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        result = self.run_check('from pathlib import Path; Path("input.txt").write_text("after")')
        self.assertTrue(result['source_before']['tracked_clean'])
        self.assertFalse(result['source_after']['tracked_clean'])
        self.assertEqual(result['source_before']['head'], result['source_after']['head'])
        self.assertEqual(result['source_after']['untracked_files'], 'not_inventoried')
