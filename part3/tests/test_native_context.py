import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path.cwd()))
from interfaces import ToolCallContext
from policies import checklist_policy as p

@unittest.skipUnless(importlib.util.find_spec('agentdojo'), 'AgentDojo not installed')
class NativeContextTests(unittest.TestCase):
    def test_real_function_call_and_text_blocks(self):
        from agentdojo.functions_runtime import FunctionCall
        from agentdojo.types import text_content_block_from_string
        call=FunctionCall(function='search_calendar_events',args={'query':'meeting'},id='t1')
        ctx=ToolCallContext(task_description='Find my meetings',tool_name=call.function,tool_args=dict(call.args),
            conversation_history=[{'role':'user','content':[text_content_block_from_string('Find my meetings')]}])
        payload=p._payload(call,ctx)
        self.assertEqual(payload['conversation_history'][0]['content'][0]['text'],'Find my meetings')
        self.assertNotIn('placeholder_args',json.dumps(payload))

    def test_real_gate_budget_without_network(self):
        from agentdojo.functions_runtime import FunctionCall
        from agentdojo.types import text_content_block_from_string
        with patch.dict(os.environ,{'GATE_POLICY_MODULE':'policies.checklist_policy','GATE_BUDGET_K':'1'}):
            import gate_patch
            gate=gate_patch.GatedToolsExecutor()
        call=FunctionCall(function='search_calendar_events',args={'query':'meeting'},id='t1')
        history=[{'role':'user','content':[text_content_block_from_string('Find my meetings')]}]
        checks={name:{'status':'uncertain','reason':'Test fixture'} for name in p.CHECKS}
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(checks)}}]}
        with patch.object(gate_patch,'policy',p.policy),patch.object(gate_patch,'reviewer',return_value=True) as reviewer:
            with patch.object(p,'_request',return_value=response),patch.object(p,'_audit'),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.decide(call,'Find my meetings',history),'approve')
                self.assertEqual(gate.decide(call,'Find my meetings',history),'deny')
                reviewer.assert_called_once()
                gate.reset_budget()
                self.assertEqual(gate.escalations_used,0)
                self.assertEqual(gate.decide(call,'Find my meetings',history),'approve')
