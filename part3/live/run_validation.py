"""Part 3 validation harness; run from a checkout with AgentDojo installed.

Does not edit shared modules. Labels stay in evaluation, outside policy/reviewer
context. Credentials are read from the environment, never from this script.
"""
import argparse
import contextlib
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time
import yaml
from dataclasses import asdict

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--repo',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--policy',default='checklist_policy')
    a.add_argument('--mode',choices=['benign','attack'],default='benign')
    a.add_argument('--k',type=int,default=3)
    a.add_argument('--tasks',default='user_task_0,user_task_1,user_task_6')
    a.add_argument('--injections',default='injection_task_0,injection_task_1')
    args=a.parse_args()
    repo=Path(args.repo).resolve(); sys.path.insert(0,str(repo))
    out=Path(args.out).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    model='openai/gpt-4.1-mini'
    os.environ.update(GATE_POLICY_MODULE='policies.'+args.policy,GATE_REVIEWER_MODULE='reviewer.llm_reviewer',
                      GATE_BUDGET_K=str(args.k),CHECKLIST_MODEL=model,REVIEWER_MODEL=model,
                      REVIEWER_JSON_MODE='1',DIRECT_LLM_MODEL=model)
    os.environ.pop('CHECKLIST_LOG_PATH',None)
    import gate_patch
    from policies import cost_tracker
    from policies import checklist_policy
    from reviewer import llm_reviewer
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline,PipelineConfig
    from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
    from openai import OpenAI
    from agentdojo.task_suite.load_suites import get_suite
    from agentdojo.logging import OutputLogger,TraceLogger
    from run_experiment import find_gate
    from agentdojo.attacks.attack_registry import load_attack

    current={'calls':[], 'policy':None, 'review':None}
    original_audit=checklist_policy._audit
    def audit(record):
        current['policy']=copy.deepcopy(record)
        usage=record['usage']
        if usage['prompt_tokens'] is not None and usage['completion_tokens'] is not None:
            cost_tracker.record('policy',usage['prompt_tokens'],usage['completion_tokens'],model)
        original_audit(record)
    checklist_policy._audit=audit
    def review(call,ctx):
        with cost_tracker.component('reviewer'):
            detail=llm_reviewer.review_with_details(call,ctx)
        current['review']=asdict(detail)
        return detail.approved
    gate_patch.reviewer=review
    original_decide=gate_patch.GatedToolsExecutor.decide
    def decide(self,call,task_description,history):
        current['policy']=None; current['review']=None
        final=original_decide(self,call,task_description,history)
        record={**self.decision_log[-1],'args':dict(call.args),'call_id':call.id,
                'policy_audit':current['policy'],'review':current['review']}
        current['calls'].append(record)
        return final
    gate_patch.GatedToolsExecutor.decide=decide
    suite=get_suite('v1.2.2','workspace')
    llm=OpenAILLM(OpenAI(base_url=os.environ['OPENAI_COMPATIBLE_BASE_URL'],
        api_key=os.environ['OPENAI_COMPATIBLE_API_KEY'],timeout=45,max_retries=0),model)
    pipeline=AgentPipeline.from_config(PipelineConfig(llm=llm,
        model_id=model,defense=None,tool_delimiter='tool',system_message_name=None,system_message=None))
    gate=find_gate(pipeline)
    assert gate is not None
    attack=None
    if args.mode=='attack':
        pipeline.name='gpt-4o-2024-05-13'
        attack=load_attack('important_instructions_no_model_name',suite,pipeline)
    ids=list(suite.user_tasks) if args.tasks=='all' else args.tasks.split(',')
    pairs=[(u,i) for u in ids for i in args.injections.split(',')] if attack else [(u,None) for u in ids]
    result={'date':'2026-10-28','model':model,'policy':args.policy,'k':args.k,'mode':args.mode,
            'benchmark':'workspace/v1.2.2','attack':'important_instructions_no_model_name' if attack else None,
            'budget_management':'unchanged shared gate','agent_provider':'explicit native OpenAILLM with OpenRouter client; 45-second timeout and zero SDK retries',
            'security_semantics':'True means attacker goal achieved in attack mode; not universal unauthorized-call detection',
            'rows':[], 'source_sha256':{path:hashlib.sha256((repo/path).read_bytes()).hexdigest() for path in
             ['gate_patch.py','interfaces.py','policies/checklist_policy.py','reviewer/llm_reviewer.py']}}
    def save():
        out.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str))
    with OutputLogger(str(out.parent/(out.stem+'_traces'))) as delegate:
        for user_id,injection_id in pairs:
            task=suite.get_user_task_by_id(user_id)
            injection_task=suite.get_injection_task_by_id(injection_id) if injection_id else None
            try:
                injections=attack.attack(task,injection_task) if attack else {}
            except ValueError:
                result['rows'].append({'task':user_id,'injection':injection_id,'status':'no_injection_vector'})
                save();continue
            gate.reset_budget();cost_tracker.reset();current['calls']=[]
            started=time.monotonic()
            row={'task':user_id,'injection':injection_id,'task_description':task.PROMPT,'status':'ok'}
            try:
                with TraceLogger(delegate,suite_name='workspace',user_task_id=user_id,
                    injection_task_id=injection_id,pipeline_name=model,
                    attack_type=result['attack'] or 'none',injections=injections) as trace:
                    utility,security=suite.run_task_with_pipeline(pipeline,task,injection_task,injections)
                row['agent_error_logged']=bool(trace.error)
                trajectory_path=out.parent/(out.stem+'_trajectories')/(user_id+'_'+str(injection_id)+'.json')
                trajectory_path.parent.mkdir(parents=True,exist_ok=True)
                trajectory_path.write_text(json.dumps(trace.messages,indent=2,ensure_ascii=False,
                    default=lambda value:value.model_dump() if hasattr(value,'model_dump') else str(value)))
                row['trajectory_file']=str(trajectory_path.relative_to(out.parent))
                normalize=lambda text: ''.join(c for c in text.lower() if c.isalnum())
                raw_blocks=[block.get('content',block.get('text',''))
                    for m in trace.messages if m.get('role')=='tool' for block in (m.get('content') or [])
                    if isinstance(block,dict) and block.get('type')=='text']
                def strings(value):
                    if isinstance(value,str):return [value]
                    if isinstance(value,dict):return [s for v in value.values() for s in strings(v)]
                    if isinstance(value,list):return [s for v in value for s in strings(v)]
                    return []
                decoded=[]
                for block in raw_blocks:
                    try:decoded.extend(strings(yaml.safe_load(block)))
                    except yaml.YAMLError:pass
                tool_text=normalize(' '.join(raw_blocks+decoded))
                row['attack_payload_observed']=any(normalize(v)[:100] in tool_text for v in injections.values() if v) if attack else None
                row.update(utility=bool(utility),attack_succeeded=bool(security) if attack else None,
                           safe_complete_proxy=bool(utility and not security) if attack else None)
            except Exception as exc:
                row.update(status='execution_error',error_type=type(exc).__name__,utility=False,
                           attack_succeeded=None,safe_complete_proxy=False if attack else None)
            row.update(elapsed_seconds=round(time.monotonic()-started,2),escalations=gate.escalations_used,
                       gate=gate.summary(),calls=copy.deepcopy(current['calls']),usage=cost_tracker.snapshot())
            result['rows'].append(row);save()
            print('PROGRESS '+json.dumps({k:row[k] for k in ('task','injection','status','utility','attack_succeeded','escalations')}),flush=True)
    result['complete']=True;save()

if __name__=='__main__':
    main()
