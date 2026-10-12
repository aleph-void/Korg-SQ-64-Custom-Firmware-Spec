"""Build original, non-deployable shared vectors with independently stated outcomes.

Expected outcomes are authored below, never obtained by executing the monitor.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sq64_spec.watch import load_rules, ruleset_digest, required_capabilities, state_addresses


def build():
    contract = load_rules(); checksum = ruleset_digest(contract)
    identity = dict(imageSha256='0'*64, specVersion=contract['specVersion'], rulesetSha256=checksum,
                    modelContractSha256=contract['modelContractSha256'], emulator=dict(name='synthetic-fixture', version='1', sha256='1'*64, tickUnit='synthetic-instruction-ticks'))
    def event(kind, **payload):
        return dict(kind=kind, sequence=1, tick=1, source='cpu', pc=0x200008, exception=0, phase='boot', mode='run', **payload)
    def write(address, value=1, width=4, locked=None):
        return event('memory-write', space='cpu', address=address, width=width, value=value.to_bytes(width,'little').hex(), locked=locked)
    def initial(values=None):
        e=event('initial-state', registers=[dict(address=a,value=(values or {}).get(a,0)) for a in state_addresses(contract)])
        e.update(sequence=0,tick=0,source='model',pc=None,exception=None);return e
    def command(value):return event('spi-command',command=value,locked=None)
    def mutation(address,length=1,operation='program',locked=None):
        return event('spi-mutation',address=address,length=length,operation=operation,value='00'*length if operation=='program' else None,locked=locked)
    def dma(address=0x20000000,width=1,count=1,increment=False,buffer='primary'):
        e=event('dma-transfer',controller=0x40026000,stream=0,buffer=buffer,address=address,width=width,count=count,increment=increment);e['source']='dma';return e
    cases=[]
    def add(name, events, rule=None, *, initial_values=None, error=None, tags=(), contract_changes=None, capability_changes=None, identity_changes=None, raw_events=None, matches=None, rebind=False):
        rows=[initial(initial_values), *deepcopy(events)] if raw_events is None else deepcopy(raw_events)
        if raw_events is None:
            for index,e in enumerate(rows):e['sequence']=index;e['tick']=index
        status='monitoring-error' if error else 'violation' if rule else 'active'
        expected=dict(status=status,ruleId=rule,errorCode=error)
        if rule:
            # Every positive scenario triggers on its final event except explicit
            # transient/first-hit cases, whose authored sequence is set below.
            expected['sequence']=len(rows)-1;expected['matchingRuleIds']=matches or [rule]
        cases.append(dict(name=name,tags=list(tags),events=rows,expected=expected,
                          contractChanges=contract_changes or [],capabilityChanges=capability_changes or [],identityChanges=identity_changes or [],rebindRules=rebind))
        return cases[-1]
    R1,R2,R3,R4,R5=[f'CRITICAL-{i:03}' for i in range(1,6)]
    for start,end in ((0x200000,0x300000),(0x8000000,0x8200000)):
        for address in (start,start+1,end-1):add(f'internal-write-{address:x}',[write(address,1,1)],R1,tags=('positive','alias','partial-access'))
        add(f'internal-cross-start-{start:x}',[write(start-1,1,2)],R1,tags=('boundary','overlap'))
        add(f'internal-before-{start:x}',[write(start-1,1,1)],tags=('negative','boundary'))
        add(f'internal-after-{end:x}',[write(end,1,1)],tags=('negative','boundary'))
    add('locked-internal-write',[write(0x8000000,0,4,True)],R1,tags=('positive','locked-attempt'))
    for address,value,width in ((0x40023c10,2,1),(0x40023c10,4,2),(0x40023c0e,6<<16,4),(0x40023c0c,6<<32,8)):
        add(f'erase-lanes-{address:x}-{width}',[write(address,value,width)],R1,tags=('positive','partial-access','byte-order'))
    for address in (0x40023c11,0x40023c12,0x40023c13):add(f'erase-other-lane-{address:x}',[write(address,6,1)],tags=('negative','partial-access'))
    add('erase-zero-bits',[write(0x40023c10,0)],tags=('negative',))
    add('initial-armed-erase',[],R1,initial_values={0x40023c10:2},tags=('positive','initial-state'))
    transition=event('register-transition',registers=[dict(address=0x40023c10,value=2)]);transition['source']='peripheral'
    c=add('transient-erase-state',[transition,event('register-transition',registers=[dict(address=0x40023c10,value=0)])],R1,tags=('sequence','transient'));c['expected']['sequence']=1
    for start,end in ((0x1ff00000,0x20000000),(0x40023c08,0x40023c0c),(0x40023c14,0x40023c20)):
        add(f'option-system-start-{start:x}',[write(start,0,1,True)],R2,tags=('positive','locked-attempt'))
        add(f'option-system-tail-{end:x}',[write(end-1,0,1)],R2,tags=('positive','partial-access'))
        add(f'option-cross-start-{start:x}',[write(start-1,0,2)],R2,tags=('boundary','overlap'))
        add(f'option-after-{end:x}',[write(end,0,1)],tags=('negative','boundary'))
    simultaneous=write(0x40023c08,6 << 48,8) # Ends at 0x10, so only option control is covered.
    add('wide-option-access',[simultaneous],R2,tags=('positive','partial-access'))
    both=write(0x40023c10,6,8)
    add('simultaneous-erase-option',[both],R1,matches=[R1,R2],tags=('positive','simultaneous','ordering'))
    c=add('transient-option-write',[write(0x20000000,0),write(0x40023c14,0),write(0x20000000,0)],R2,tags=('sequence','transient'));c['expected']['sequence']=2
    c=add('spi-forbidden-then-reset',[command(6),command(199),command(4)],R3,tags=('sequence','transient'));c['expected']['sequence']=2
    for value in (0,2,3,4,5,6,11,32,159,216):add(f'spi-allowed-{value:02x}',[command(value)],tags=('negative','spi-command'))
    for value in (1,0x42,0x60,0xc7,0xff):add(f'spi-forbidden-{value:02x}',[command(value)],R3,tags=('positive','spi-command'))
    e=command(0xc7);e.update(source='dma',pc=None,exception=None,phase='interrupt',mode='fast');e['locked']=True
    add('spi-dma-locked-interrupt',[e],R3,tags=('positive','locked-attempt','mode','source'))
    add('spi-program-zero',[mutation(0)],R4,tags=('positive',))
    add('spi-program-tail',[mutation(0x2ffff)],R4,tags=('boundary',))
    add('spi-program-cross-boundary',[mutation(0x2ffff,2)],R4,tags=('boundary','overlap'))
    add('spi-program-after',[mutation(0x30000)],tags=('negative','boundary'))
    add('spi-staging',[mutation(0x40000,2)],tags=('negative',))
    add('spi-last-byte',[mutation(0xffffff)],tags=('negative','boundary'))
    add('spi-erase-overlap',[mutation(0x20000,65536,'erase',True)],R4,tags=('positive','locked-attempt'))
    add('spi-erase-after',[mutation(0x30000,65536,'erase')],tags=('negative',))
    c=add('spi-unsafe-then-restore',[mutation(0x40000),mutation(0),mutation(0x40000)],R4,tags=('sequence','first-hit'));c['expected']['sequence']=2
    for width in (1,2,4,8):
        add(f'dma-exact-end-{width}',[dma(0x100000000-width,width,1)],tags=('negative','boundary'))
        if width>1:add(f'dma-overflow-{width}',[dma(0x100000001-width,width,1)],R5,tags=('positive','overflow'))
    add('dma-increment-wrap',[dma(0xfffffff0,4,8,True)],R5,tags=('positive','overflow'))
    add('dma-no-increment-wrap',[dma(0xfffffff0,4,65535,False)],tags=('negative','increment'))
    add('dma-crosses-internal-boundary',[dma(0x1fffff,1,2,True)],R1,tags=('positive','dma-span'))
    add('dma-crosses-system-boundary',[dma(0x1fefffff,1,2,True)],R2,tags=('positive','dma-span'))
    add('dma-unknown-erase-value',[dma(0x40023c11)],R1,tags=('positive','conservative'))
    base=0x40026010
    cfg={base:1|1024|(2<<13),base+4:8,base+12:0x20000000,base+16:0xfffffff0}
    add('dma-inactive-secondary',[],initial_values=cfg,tags=('negative','secondary'))
    alternate=dict(cfg);alternate[base]|=0x40000
    add('dma-secondary-overflow-at-start',[],R5,initial_values=alternate,tags=('positive','secondary','initial-state'))
    add('dma-secondary-enable-partial',[write(base+2,4,1,True)],R5,initial_values=cfg,tags=('positive','secondary','partial-access','locked-attempt'))
    disabled=dict(alternate);disabled[base]&=~1
    add('dma-disabled-unsafe-destination',[],initial_values=disabled,tags=('negative','disabled'))
    add('dma-enable-unsafe',[write(base,alternate[base])],R5,initial_values=disabled,tags=('positive','configuration'))
    a={base:1,base+4:1,base+12:0x20000000}
    add('dma-active-target-partial',[write(base+15,8,1)],R1,initial_values=a,tags=('positive','configuration','partial-access'))
    cfg={base:1|1024,base+4:8,base+12:0xfffffff0}
    e=event('register-transition',registers=[dict(address=base+4,value=32)]);e['source']='dma'
    c=add('dma-transient-reload',[e,event('register-transition',registers=[dict(address=base+4,value=8)])],R5,initial_values=cfg,tags=('positive','transient','sequence'));c['expected']['sequence']=1
    add('dma-direction-peripheral',[],R2,initial_values={base:1|64,base+4:1,base+8:0x40023c14},tags=('positive','direction'))
    add('dma-zero-count-still-checks-one-unit',[],R1,initial_values={base:1,base+12:0x8000000},tags=('positive','zero-count'))
    # A positive for the other controller's last stream prevents slot omissions.
    b=0x40026400+16+7*24
    add('dma-last-controller-stream',[],R5,initial_values={b:1|1024,b+4:2,b+12:0xffffffff},tags=('positive','coverage'))
    c=add('first-hit-latches',[write(0x200000),command(0xc7),dict(kind='broken')],R1,tags=('sequence','first-hit'));c['expected']['sequence']=1
    for mode in ('run','step','replay','fast'):
        e=write(0x8000000);e['mode']=mode;e['phase']='interrupt';e['exception']=16
        add('critical-in-mode-'+mode,[e],R1,tags=('positive','mode','interrupt'))
    # Contract-driven semantics: no runtime copy of command/range constants.
    allowed=[0,2,3,4,5,6,11,32,159,216,199]
    add('changed-spec-command-list',[command(199)],contract_changes=[dict(path=['rules',2,'predicate','args',1,'values'],value=allowed)],rebind=True,tags=('contract-driven','negative'))
    ranges=[[0x200000,0x300000],[0x8000000,0x8200000],[0x200010,0x200020]]
    add('overlapping-predicate-ranges',[write(0x200010)],R1,contract_changes=[dict(path=['rules',0,'predicate','args',0,'args',1,'ranges'],value=ranges)],rebind=True,tags=('positive','overlap'))
    # Structural failures for each source/rule are monitoring errors, not hazards.
    malformed=[('memory-missing-value',write(0x8000000),'value',None),('memory-boolean-width',write(0x8000000),'width',True),
      ('memory-overflow',write(0),'address',0xffffffff),('memory-negative',write(0),'address',-1),('memory-wide-value',write(0),'value','0000000000'),
      ('option-invalid-locked',write(0x40023c08),'locked',[]),('option-unknown-source',write(0x40023c14),'source','hidden'),
      ('spi-command-out-of-range',command(199),'command',256),('spi-command-bool',command(199),'command',True),
      ('spi-program-missing-value',mutation(0),'value',None),('spi-effect-overflow',mutation(0,2),'address',0xffffff),('spi-unknown-operation',mutation(0),'operation','restore'),
      ('dma-transfer-zero-count',dma(),'count',0),('dma-transfer-invalid-width',dma(),'width',3),('dma-transfer-controller',dma(),'controller',0),
      ('dma-transfer-invalid-buffer',dma(),'buffer','third'),('dma-transfer-invalid-increment',dma(),'increment',1)]
    for name,e,key,value in malformed:e[key]=value;add(name,[e],error='invalid-event',tags=('malformed',))
    e=write(0x8000000);del e['pc'];add('missing-required-location-field',[e],error='invalid-event',tags=('malformed',))
    e=command(199);e['extra']=1;add('unknown-event-field',[e],error='invalid-event',tags=('malformed',))
    e=initial();e['registers'].pop();add('missing-initial-dma-register',[],raw_events=[e],error='invalid-event',tags=('malformed','initial-state'))
    e=initial();e['registers'].append(e['registers'][0]);add('duplicate-initial-register',[],raw_events=[e],error='invalid-event',tags=('malformed',))
    add('unknown-transition-register',[event('register-transition',registers=[dict(address=0,value=0)])],error='invalid-event',tags=('malformed',))
    e=command(199);e['sequence']=2;add('sequence-gap',[],raw_events=[initial(),e],error='event-order',tags=('malformed','sequence'))
    e=event('instruction-boundary');e.update(sequence=1,tick=5);late=command(199);late.update(sequence=2,tick=4)
    add('backward-virtual-time',[],raw_events=[initial(),e,late],error='event-order',tags=('malformed','sequence'))
    e=event('instruction-boundary');e.update(sequence=0,tick=0);add('execution-before-initial-state',[],raw_events=[e],error='missing-initial-state',tags=('malformed','sequence'))
    add('duplicate-json-event-key',[],raw_events=[initial(),'{"kind":"spi-command","kind":"memory-write"}'],error='invalid-event',tags=('malformed','json'))
    add('nonfinite-json-event',[],raw_events=[initial(),'{"kind":"spi-command","command":NaN}'],error='invalid-event',tags=('malformed','json'))
    for path,value in [(['version'],2),(['rules',0,'predicate','op'],'python-eval'),(['rules',0,'mandatory'],False),(['rules',0,'legacy','unsafeWhen'],'fail'),(['rules',0,'predicate','args',0,'args',1,'ranges'],[[9,8]]),(['normalization','dma','streams'],100000),(['normalization','dma','registers','secondary'],12)]:
        add('invalid-contract-'+'-'.join(map(str,path)),[],error='invalid-contract',contract_changes=[dict(path=path,value=value)],tags=('malformed','contract'))
    for field in ('eventKinds','sources','modes','guarantees','predicateOps','rules'):
        supplied=required_capabilities(contract)[field][:-1]
        add('missing-capability-'+field,[],error='missing-capability',capability_changes=[dict(path=[field],value=supplied)],tags=('malformed','capability'))
    add('wrong-rules-digest',[],error='invalid-identity',identity_changes=[dict(path=['rulesetSha256'],value='f'*64)],tags=('malformed','identity'))
    return dict(format='sq64-watch-fixtures',version=1,rulesetSha256=checksum,identity=identity,capabilities=required_capabilities(contract),cases=cases)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    text=json.dumps(build(),indent=2)+'\n';target=ROOT/'sq64_spec/watch-fixtures.json'
    if args.check:
        if target.read_text(encoding='utf-8')!=text:raise SystemExit('Watch fixtures are stale')
    else:target.write_text(text,encoding='utf-8')
if __name__=='__main__':main()
