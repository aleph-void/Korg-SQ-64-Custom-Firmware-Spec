"""Render the normative catalog without maintaining a second set of rules."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(document):
    lines = ['# SQ-64 requirements catalog', '',
             f"Version {document['version']}. Generated from `sq64_spec/requirements.json`.", '',
             'SHALL is mandatory within the selected profile. Each named case must have an explicit expected result, observation and status. Missing cases are not-run. Extra cases may extend coverage; they cannot replace required cases.', '',
             'Hardware and compatibility profiles require candidate hardware observations for runtime requirements. The software profile also accepts candidate emulator observations against the model contract. Review evidence is accepted only where listed. Image checks are executed directly and cannot be overridden.', '']
    for r in document['requirements']:
        lines += [f"## {r['id']} — {r['title']}", '',
                  '**Requirement:** Firmware or its delivery tooling SHALL ' + r['shall'][0].lower() + r['shall'][1:], '',
                  '**Verification:** ' + r['verification'], '',
                  '**Profiles:** ' + ', '.join(r['profiles']), '',
                  '**Evidence kinds:** ' + ', '.join(r['evidenceKinds']) + ('; emulator also accepted in software' if 'software' in r['profiles'] and 'image' not in r['profiles'] else ''), '']
        if r['cases']:
            lines += ['**Required cases:** ' + ', '.join('`' + c + '`' for c in r['cases']), '']
        if r['quantitative']:
            lines += ['**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    expected = render(json.loads((ROOT / 'sq64_spec/requirements.json').read_text(encoding='utf-8')))
    target = ROOT / 'docs/requirements.md'
    if args.check:
        if target.read_text(encoding='utf-8') != expected:
            raise SystemExit('Requirement documentation is stale; run python tools/render_requirements.py')
    else:
        target.write_text(expected, encoding='utf-8')
