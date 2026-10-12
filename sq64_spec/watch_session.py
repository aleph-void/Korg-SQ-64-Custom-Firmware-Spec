"""Offline replay of supplied watch observations. This cannot prove hook coverage."""
from .validation import load_json
from .watch import WatchMonitor, load_rules


def replay_session(raw):
    if not isinstance(raw, bytes) or len(raw)>16*1024*1024:
        raise ValueError('Watch session must be JSON bytes, at most 16 MiB')
    session=load_json(raw.decode('utf-8'))
    if (type(session) is not dict or set(session)!={'format','version','identity','capabilities','events'}
            or session['format']!='sq64-watch-session' or type(session['version']) is not int or session['version']!=1
            or type(session['events']) is not list or len(session['events'])>100000):
        raise ValueError('Invalid watch session envelope')
    monitor=WatchMonitor(load_rules(),identity=session['identity'],capabilities=session['capabilities'])
    for event in session['events']:
        monitor.evaluate(event)
        if monitor.terminated:break
    if not monitor.can_execute and not monitor.terminated:monitor.fail('observer-failure')
    report=monitor.report()
    report['inputScope']='supplied-observations-only'
    return report
