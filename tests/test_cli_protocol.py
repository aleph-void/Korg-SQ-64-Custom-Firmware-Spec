import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sq64_spec.protocol import validate_transfer
from sq64_spec.report import catalog
from test_contract import frame, image, integer, transcript
from test_backup import archive, pack

ROOT = Path(__file__).resolve().parents[1]


class ProtocolTests(unittest.TestCase):
    def test_candidate_version_binding(self):
        payload = image()[256:]
        events = transcript(payload)
        self.assertTrue(validate_transfer(events, payload, expected_version=(3, 0))['versionBound'])
        with self.assertRaises(ValueError): validate_transfer(events, payload, expected_version=(0, 0))

    def test_protocol_zero_fill_and_progress(self):
        payload = bytes([255]) * 0x38000
        events = [frame('host', 0), frame('device', 1, b'\0' + integer(1024, 2) + b'\2'),
                  frame('host', 2, b'\0'), frame('device', 3, b'\1\0'),
                  frame('host', 4, b'\0\0\x42\x03'), frame('device', 5, b'\0\1')]
        for n in range(224):
            events.extend([frame('host', 8, integer(n, 2) + b'\x0f\x0f'),
                           frame('device', 0x13, integer(n + 1, 2) + integer(224, 2)), frame('device', 5, b'\0')])
        result = validate_transfer(events, payload, expected_version=(2, 3))
        self.assertEqual((result['protocol'], result['packets']), (0, 224))
        events[1] = frame('device', 1, b'\0' + integer(1, 2) + b'\2')
        with self.assertRaisesRegex(ValueError, 'overflow'): validate_transfer(events, payload)

    def test_packing_every_byte_and_tail(self):
        from sq64_spec.protocol import decode
        for length in range(1, 257):
            raw = bytes(range(256))[:length]
            self.assertEqual(decode(pack(raw), length), raw)

    def test_transcript_rejects_checksum_mask_and_strict_hex(self):
        payload = image()[256:]
        for index, value in [(7 + 4, 128), (-3, 64), (-2, 1)]:
            events = transcript(payload)
            wire = bytearray.fromhex(events[6]['hex'])
            wire[index] = value
            events[6]['hex'] = wire.hex()
            with self.assertRaises(ValueError): validate_transfer(events, payload)
        events = transcript(payload)
        events[0]['hex'] += ' '
        with self.assertRaises(ValueError): validate_transfer(events, payload)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / 'image.VSB').write_bytes(image())
        (self.root / 'backup.json').write_text(json.dumps(archive()))

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'sq64_spec', *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, timeout=20)

    def test_exit_codes_and_output_file(self):
        for profile, code in [('image', 0), ('software', 2), ('hardware', 2), ('korg-compatible', 2)]:
            result = self.cli(self.root / 'image.VSB', '--profile', profile)
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertFalse(json.loads(result.stdout)['hardwareValidated'])
        path = self.root / 'result.json'
        (self.root / 'image.VSB').write_bytes(b'bad')
        result = self.cli(self.root / 'image.VSB', '--profile', 'image', '--output', path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(path.read_text())['status'], 'fail')

    def test_transcript_failure_is_in_report_and_exit_status(self):
        # A valid image with a different begin version must fail the overall run.
        (self.root / 'transfer.json').write_text(json.dumps(transcript(image()[256:])))
        result = self.cli(self.root / 'image.VSB', '--profile', 'image', '--transcript', self.root / 'transfer.json')
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report['transcript']['status'], 'fail')
        self.assertIn('version', report['transcript']['detail'])
        self.assertTrue(all(row['status'] == 'pass' for row in report['results']))

    def test_successful_transcript_is_bound_but_does_not_override_requirement(self):
        data = image()
        data[0x2a] = 3
        (self.root / 'image.VSB').write_bytes(data)
        transcript_bytes = json.dumps(transcript(data[256:])).encode()
        (self.root / 'transfer.json').write_bytes(transcript_bytes)
        result = self.cli(self.root / 'image.VSB', '--profile', 'software', '--transcript', self.root / 'transfer.json')
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(report['transcript']['versionBound'])
        self.assertEqual(next(r['status'] for r in report['results'] if r['id'] == 'VUP-004'), 'not-run')
        self.assertEqual(report['inputArtifacts']['transcript']['sha256'], hashlib.sha256(transcript_bytes).hexdigest())

    def test_generated_checklist_evaluates_as_incomplete(self):
        path = self.root / 'evidence.json'
        result = self.cli(self.root / 'image.VSB', '--profile', 'software', '--evidence-template', '--output', path)
        self.assertEqual(result.returncode, 0, result.stderr)
        template = json.loads(path.read_text())
        self.assertEqual(len(template['results']), 44)
        self.assertTrue(all(r['status'] == 'not-run' for r in template['results']))
        result = self.cli(self.root / 'image.VSB', '--profile', 'software', '--evidence', path)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['counts']['not-run'], 44)

    def test_standalone_backup_and_readback(self):
        result = self.cli('--backup', self.root / 'backup.json', '--readback', self.root / 'backup.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['readback']['records'], 95)
        (self.root / 'backup.json').write_text('{"complete":true,"complete":false}')
        result = self.cli('--backup', self.root / 'backup.json')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Duplicate', json.loads(result.stdout)['backup']['detail'])

    def test_bad_arguments_and_malformed_evidence_without_traceback(self):
        result = self.cli('--readback', 'missing.json')
        self.assertNotEqual(result.returncode, 0)
        (self.root / 'bad.json').write_text('{"format":"sq64-evidence","version":true}')
        result = self.cli(self.root / 'image.VSB', '--evidence', self.root / 'bad.json')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('Traceback', result.stderr)

    def test_catalog_and_board_contract(self):
        self.assertEqual(len(json.loads(self.cli('--catalog').stdout)['requirements']), 65)
        board = json.loads(self.cli('--board-contract').stdout)
        buttons = board['panel']['buttons']
        self.assertEqual(len(buttons), 85)
        self.assertEqual(len({(b['row'], b['bit']) for b in buttons.values()}), 85)
        self.assertEqual(len(board['panel']['encoders']), 6)
        slots = board['memory']['savedProjects']
        self.assertEqual(slots['base'] + slots['stride'] * slots['count'], 0x1000000)

    def test_catalog_docs_are_current(self):
        result = subprocess.run([sys.executable, 'tools/render_requirements.py', '--check'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for row in catalog()['requirements']:
            self.assertTrue('image' in row['profiles'] or row['cases'])
            self.assertEqual(len(row['cases']), len(set(row['cases'])))
