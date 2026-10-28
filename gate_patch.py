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
        self.decision_log = []

    def reset_budget(self):
        """Call this before starting a new task so k applies per task.

        Also clears the per-task decision log (see summary())."""
        self.escalations_used = 0
        self.decision_log = []

    def summary(self):
        """Per-task counts of WHY calls were approved / denied (for Part 6 failure analysis).

        budget_denials = denials caused only by an exhausted budget k (over-conservative
        failures that a larger k would fix).
        """
        sources = [d["source"] for d in self.decision_log]
        return {
            "n_calls": len(sources),
            "approved": sum(d["final"] == "approve" for d in self.decision_log),
            "denied": sum(d["final"] == "deny" for d in self.decision_log),
            "policy_denials": sources.count("policy_deny"),
            "reviewer_denials": sources.count("reviewer_deny"),
            "budget_denials": sources.count("budget_exhausted"),
            "invalid_policy_answers": sources.count("invalid_policy_answer"),
        }

    def decide(self, tc, task_description, conversation_history):
        ctx = ToolCallContext(
            task_description=task_description,
            conversation_history=list(conversation_history),
            tool_name=tc.function,
            tool_args=dict(tc.args),
            is_read_only=tc.function.startswith(_READ_ONLY_PREFIXES),
        )
        policy_decision = policy(tc, ctx)
        decision = policy_decision
        if policy_decision == "approve":
            source = "policy_approve"
        elif policy_decision == "deny":
            source = "policy_deny"
        elif policy_decision == "escalate":
            if self.escalations_used >= self.budget_k:
                decision = "deny"  # budget exhausted -> auto-deny
                source = "budget_exhausted"
            else:
                self.escalations_used += 1
                if reviewer(tc, ctx):
                    decision, source = "approve", "reviewer_approve"
                else:
                    decision, source = "deny", "reviewer_deny"
        else:
            # Not exactly "approve"/"deny"/"escalate" (e.g. "Approve" or None): the call is
            # blocked, same as before, but now it is recorded and warned about.
            decision = "deny"
            source = "invalid_policy_answer"
            print(f"[GATE] WARNING: policy returned {policy_decision!r}; treated as deny", flush=True)
        self.decision_log.append(
            {"tool": tc.function, "policy_decision": policy_decision, "final": decision, "source": source}
        )
        print(f"[GATE] tool={tc.function} args={dict(tc.args)} -> {decision} ({source})", flush=True)
        return decision

    def query(self, query, runtime, env=EmptyEnv(), messages=[], extra_args={}):
        if not messages or messages[-1]["role"] != "assistant" or not messages[-1].get("tool_calls"):
            return super().query(query, runtime, env, messages, extra_args)

        allowed, denied = [], []
        for tc in messages[-1]["tool_calls"]:
            (allowed if self.decide(tc, query, messages[:-1]) == "approve" else denied).append(tc)

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
