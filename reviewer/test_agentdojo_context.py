"""Optional regression tests against installed, real AgentDojo types.

python -m unittest reviewer.test_agentdojo_context -v
No network, API credentials, or model calls are needed. Tests skip if AgentDojo
is absent; run them inside the group's actual AgentDojo environment.
"""
import json
import os
import unittest
from unittest.mock import patch

from interfaces import ToolCallContext
from reviewer.llm_reviewer import build_evidence

try:
    from agentdojo.functions_runtime import FunctionCall
    from agentdojo.types import ChatToolResultMessage, text_content_block_from_string
except ImportError:
    FunctionCall = None


@unittest.skipIf(FunctionCall is None, "Install AgentDojo to run native type checks")
class AgentDojoContextTests(unittest.TestCase):
    def history(self):
        call = FunctionCall(id="native-test", function="search_calendar_events", args={"query": "Networking event"})
        return call, [
            {"role": "user", "content": [text_content_block_from_string("Find the Networking event.")]},
            {"role": "assistant", "content": None, "tool_calls": [call]},
            ChatToolResultMessage(role="tool", content=[text_content_block_from_string("Meeting with Alice.")],
                                  tool_call_id=call.id, tool_call=call, error=None),
        ]

    def test_actual_text_factory_and_function_call_serialize(self):
        call, history = self.history()
        ctx = ToolCallContext(task_description="Find the Networking event.",
                              tool_name=call.function, tool_args=dict(call.args),
                              is_read_only=True, conversation_history=history)
        evidence = json.loads(build_evidence(ctx))
        self.assertEqual(evidence["conversation_history"][0]["content"][0]["text"], "Find the Networking event.")
        self.assertEqual(evidence["conversation_history"][2]["content"][0]["text"], "Meeting with Alice.")
        self.assertEqual(evidence["conversation_history"][2]["tool_call"]["function"], call.function)

    def test_unchanged_gate_passes_native_context_to_reviewer(self):
        with patch.dict(os.environ, {"GATE_POLICY_MODULE": "policies.full_escalate_policy",
                                     "GATE_REVIEWER_MODULE": "reviewer.llm_reviewer", "GATE_BUDGET_K": "1"}):
            import gate_patch
            call, history = self.history()
            captured = []

            def check_context(tc, ctx):
                captured.append(json.loads(build_evidence(ctx)))
                return True

            gate = gate_patch.GatedToolsExecutor()
            # Patch only the model decision, retaining the real gate and types.
            with patch.object(gate_patch, "policy", return_value="escalate"), \
                    patch.object(gate_patch, "reviewer", side_effect=check_context):
                self.assertEqual(gate.decide(call, "Find the Networking event.", history), "approve")
                self.assertEqual(gate.decide(call, "Find the Networking event.", history), "deny")
                self.assertEqual(len(captured), 1)
                gate.reset_budget()
                self.assertEqual(gate.decide(call, "Find the Networking event.", history), "approve")
                self.assertEqual(len(captured), 2)


if __name__ == "__main__":
    unittest.main()
