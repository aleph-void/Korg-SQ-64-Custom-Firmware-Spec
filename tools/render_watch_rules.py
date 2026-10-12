"""Render rule reference and legacy metadata from the executable watch contract."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sq64_spec.watch import WatchMonitor, load_rules, ruleset_digest
from build_watch_fixtures import build


def outputs():
    contract=load_rules();checksum=ruleset_digest(contract)
    lines=['# Runtime watch rule reference','',f"Specification {contract['specVersion']}; contract/vocabulary v1. Generated from `sq64_spec/watch-rules.json`.",'',
           f'Canonical ruleset SHA-256: `{checksum}`','',
           'See [runtime monitoring](runtime-watch.md) for event schemas, normalization, predicate semantics, resource limits and termination. Every rule is mandatory in boot, application and interrupt phases and in run, step, replay and fast modes. These are conservative emulator restrictions, not verified board limits. Array order selects the first violation when multiple rules match one observation.','']
    for rule in contract['rules']:
        lines.extend([f"## {rule['id']} — {rule['title']}",'',rule['description'],'',
                      '**Requirements:** '+', '.join(rule['requirements']),'',
                      '**Required observations:** '+', '.join(rule['requiredObservations']),'',
                      '**Action:** `terminate-session`. **Warning:** '+rule['warning'],'',
                      '**Violation predicate:**','', '```json',json.dumps(rule['predicate'],indent=2),'```',''])
    legacy=dict(format='sq64-critical-checks',version=1,specVersion=contract['specVersion'],terminateOnCritical=True,
                warning=contract['rules'][0]['warning'],claim='A hazard detection pass is unsafe. No detected hazard is not proof that firmware is safe to flash.',
                watchRules=dict(path='watch-rules.json',version=1,sha256=checksum,digestAlgorithm='sha256-canonical-sq64-json-v1'),
                checks=[dict(id=r['id'],title=r['title'],severity=r['legacy']['severity'],unsafeWhen=r['legacy']['unsafeWhen'],requirements=r['requirements']) for r in contract['rules']])
    fixtures = build()
    monitor = WatchMonitor(contract, identity=fixtures['identity'], capabilities=fixtures['capabilities'])
    for event in fixtures['cases'][0]['events']: monitor.evaluate(event)
    return {ROOT/'sq64_spec/watch-example.json':json.dumps(monitor.violation(),indent=2)+'\n',ROOT/'docs/watch-rules.md':'\n'.join(lines),ROOT/'sq64_spec/critical.json':json.dumps(legacy,indent=2)+'\n'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for target,content in outputs().items():
        if args.check:
            if not target.is_file() or target.read_text(encoding='utf-8')!=content:raise SystemExit('Stale watch documentation/metadata: '+str(target))
        else:target.write_text(content,encoding='utf-8')
if __name__=='__main__':main()
