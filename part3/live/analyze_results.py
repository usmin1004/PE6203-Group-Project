"""Summarize saved results only; never makes API calls."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
pricing=json.loads((ROOT/'model_pricing.json').read_text())['pricing']
pin=float(pricing['prompt']);pout=float(pricing['completion'])
summaries=[]
for path in sorted(ROOT.glob('*.json')):
    data=json.loads(path.read_text())
    if 'rows' not in data:continue
    rows=data['rows'];valid=[r for r in rows if r['status']=='ok']
    tested=[r for r in rows if r['status']!='no_injection_vector']
    n=len(tested)
    if not n:continue
    costs={}
    for r in tested:
        for component,u in r.get('usage',{}).items():
            t=costs.setdefault(component,{'calls':0,'prompt_tokens':0,'completion_tokens':0,'estimated_usd':0})
            for key in ('calls','prompt_tokens','completion_tokens'):t[key]+=u[key]
    for u in costs.values():u['estimated_usd']=u['prompt_tokens']*pin+u['completion_tokens']*pout
    calls=[c for r in tested for c in r.get('calls',[])]
    row={'file':path.name,'policy':data['policy'],'mode':data['mode'],'k':data['k'],'n':n,
         'complete':data.get('complete',False),'execution_errors':sum(r['status']!='ok' for r in tested),
         'utility_successes':sum(r.get('utility',False) for r in tested),
         'utility_rate':sum(r.get('utility',False) for r in tested)/n,
         'safe_complete_count':sum(r.get('safe_complete_proxy',False) or False for r in tested) if data['mode']=='attack' else None,
         'safe_completion_proxy':sum(r.get('safe_complete_proxy',False) or False for r in tested)/n if data['mode']=='attack' else None,
         'attack_successes':sum(r.get('attack_succeeded',False) or False for r in tested) if data['mode']=='attack' else None,
         'hitl_all':sum(r.get('escalations',0) for r in tested),
         'hitl_utility_success':sum(r.get('escalations',0) for r in tested if r.get('utility')),
         'hitl_safe_success':sum(r.get('escalations',0) for r in tested if r.get('safe_complete_proxy')) if data['mode']=='attack' else None,
         'policy_api_or_format_errors':sum(c.get('policy_audit') is not None and c['policy_audit']['error_type'] is not None for c in calls),
         'reviewer_operational_errors':sum(c.get('review') is not None and c['review']['status']!='ok' for c in calls),
         'policy_denials':sum(c['source']=='policy_deny' for c in calls),
         'reviewer_denials':sum(c['source']=='reviewer_deny' for c in calls),
         'budget_denials':sum(c['source']=='budget_exhausted' for c in calls),
         'component_usage':costs,'estimated_usd':sum(u['estimated_usd'] for u in costs.values())}
    summaries.append(row)
(ROOT/'summary.json').write_text(json.dumps(summaries,indent=2))
flat=[{k:v for k,v in row.items() if k!='component_usage'} for row in summaries]
if flat:
    with (ROOT/'summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
print(json.dumps(flat,indent=2))
