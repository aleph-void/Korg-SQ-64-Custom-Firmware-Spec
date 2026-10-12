import argparse
import hashlib
import json
from pathlib import Path
from .report import evaluate, catalog, evidence_template
from .protocol import validate_transfer
from .backup import validate_backup, compare_backups
from .validation import load_json

def main():
    parser = argparse.ArgumentParser(description='SQ-64 candidate checks and explicit coverage reporting')
    parser.add_argument('image', type=Path, nargs='?')
    parser.add_argument('--profile', choices=list(catalog()['profiles']), default='hardware')
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--transcript', type=Path)
    parser.add_argument('--backup', type=Path, help='Independently validate a sq64-backup archive')
    parser.add_argument('--readback', type=Path, help='Compare logical content against --backup')
    parser.add_argument('--declaration', type=Path, help='Candidate features and quantitative acceptance bounds')
    parser.add_argument('--artifact-root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--catalog', action='store_true')
    parser.add_argument('--board-contract', action='store_true')
    parser.add_argument('--evidence-template', action='store_true', help='Write an image-bound checklist with every required case marked not-run')
    args = parser.parse_args()
    if args.catalog: print(json.dumps(catalog(), indent=2)); return
    if args.board_contract:
        print(Path(__file__).with_name('board.json').read_text(), end='')
        return
    if args.readback and not args.backup: parser.error('--readback requires --backup')
    if not args.image and (not args.backup or args.evidence or args.transcript or args.declaration or args.artifact_root):
        parser.error('Provide a candidate VSB file (only standalone backup checks omit it)')
    try:
        cache = {}
        def read(path):
            if path is None:
                return None
            if path not in cache:
                raw = path.read_bytes()
                cache[path] = (load_json(raw.decode('utf-8')), hashlib.sha256(raw).hexdigest())
            return cache[path][0]
        if args.evidence_template:
            if not args.image:
                parser.error('--evidence-template requires a candidate VSB')
            text = json.dumps(evidence_template(args.image.read_bytes(), args.profile), indent=2) + '\n'
            if args.output:
                args.output.write_text(text, encoding='utf-8')
            else:
                print(text, end='')
            return
        if args.image:
            data = args.image.read_bytes()
            report = evaluate(data, profile=args.profile, evidence=read(args.evidence), artifact_root=args.artifact_root, declaration=read(args.declaration))
        else:
            report = {'format': 'sq64-artifact-report', 'version': 1, 'status': 'pass',
                      'hardwareValidated': False, 'claim': 'Archive integrity and logical content only'}
        checks = []
        if args.transcript:
            checks.append(('transcript', lambda: validate_transfer(read(args.transcript), data[256:], expected_version=data[0x2a:0x2c])))
        if args.backup:
            checks.append(('backup', lambda: validate_backup(read(args.backup))))
        if args.readback:
            checks.append(('readback', lambda: compare_backups(read(args.backup), read(args.readback))))
        for name, check in checks:
            try:
                report[name] = check()
            except (ValueError, OSError) as error:
                report[name] = {'status': 'fail', 'detail': str(error)}
                report['status'] = 'fail'
        report['inputArtifacts'] = {name: {'sha256': cache[path][1]} for name in
                                   ('evidence', 'declaration', 'transcript', 'backup', 'readback')
                                   if (path := getattr(args, name)) in cache}
        text = json.dumps(report, indent=2) + '\n'
        if args.output: args.output.write_text(text, encoding='utf-8')
        else: print(text, end='')
        raise SystemExit({'pass': 0, 'fail': 1, 'incomplete': 2}[report['status']])
    except (ValueError, OSError, KeyError, IndexError) as error:
        parser.exit(1, str(error) + '\n')
