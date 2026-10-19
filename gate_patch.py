"""Step 2 gate: approve / deny / escalate-to-human, with a per-run budget k.

Load it with:  -ml gate_patch
Env vars:
  GATE_POLICY_MODULE    dotted path to a module with policy(call, ctx) -> str
                         (default: policies.stub_policy)
  GATE_REVIEWER_MODULE  dotted path to a module with reviewer(call, ctx) -> bool
                         (default: reviewer.stub_reviewer)
  GATE_BUDGET_K         escalations allowed before they turn into auto-deny (default: 3)

Note: the same GatedToolsExecutor instance is reused for every task in a
benchmark sweep, so the escalation budget does NOT reset between tasks by
itself yet. Call .reset_budget() before each task -- the task-runner script
(upcoming step) will do this.
"""
import importlib
import os

import zhipu_patch  # noqa: F401  (also loads the Zhipu fix, so only one -ml is needed)
import agentdojo.agent_pipeline.agent_pipeline as ap
from agentdojo.agent_pipeline.tool_execution import ToolsExecutor
from agentdojo.functions_runtime import EmptyEnv
from agentdojo.types import ChatToolResultMessage, text_content_block_from_string
from interfaces import ToolCallContext

_READ_ONLY_PREFIXES = ("get_", "read_", "search_", "list_", "find_")


def _load(env_var, default_module, attr):
    module = importlib.import_module(os.environ.get(env_var, default_module))
    return getattr(module, attr)


policy = _load("GATE_POLICY_MODULE", "policies.stub_policy", "policy")
reviewer = _load("GATE_REVIEWER_MODULE", "reviewer.stub_reviewer", "reviewer")


class GatedToolsExecutor(ToolsExecutor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.budget_k = int(os.environ.get("GATE_BUDGET_K", "3"))
        self.escalations_used = 0

    def reset_budget(self):
        """Call this before starting a new task so k applies per task."""
        self.escalations_used = 0

    def decide(self, tc, task_description):
        ctx = ToolCallContext(
            task_description=task_description,
            tool_name=tc.function,
            tool_args=dict(tc.args),
            is_read_only=tc.function.startswith(_READ_ONLY_PREFIXES),
        )
        decision = policy(tc, ctx)
        if decision == "escalate":
            if self.escalations_used >= self.budget_k:
                decision = "deny"  # budget exhausted -> auto-deny
            else:
                self.escalations_used += 1
                decision = "approve" if reviewer(tc, ctx) else "deny"
        print(f"[GATE] tool={tc.function} args={dict(tc.args)} -> {decision}", flush=True)
        return decision

    def query(self, query, runtime, env=EmptyEnv(), messages=[], extra_args={}):
        if not messages or messages[-1]["role"] != "assistant" or not messages[-1].get("tool_calls"):
            return super().query(query, runtime, env, messages, extra_args)

        allowed, denied = [], []
        for tc in messages[-1]["tool_calls"]:
            (allowed if self.decide(tc, query) == "approve" else denied).append(tc)

        trimmed = [*messages[:-1], {**messages[-1], "tool_calls": allowed}]
        query, runtime, env, out, extra_args = super().query(query, runtime, env, trimmed, extra_args)
        results = list(out[len(messages):])

        for tc in denied:
            results.append(
                ChatToolResultMessage(
                    role="tool",
                    content=[text_content_block_from_string("")],
                    tool_call_id=tc.id,
                    tool_call=tc,
                    error="Denied by the approval gate.",
                )
            )
        return query, runtime, env, [*messages, *results], extra_args


ap.ToolsExecutor = GatedToolsExecutor
