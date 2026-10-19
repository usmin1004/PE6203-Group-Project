"""Shared contract for Part 3 (policy) and Part 4 (reviewer) authors.

Each of you writes ONE function matching the shape below in your own file
(e.g. policies/checklist_policy.py, reviewer/llm_reviewer.py). The gate
(gate_patch.py) will import your function and call it for every tool call.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallContext:
    """Everything a policy or reviewer is allowed to look at when deciding."""
    task_description: str = ""
    conversation_history: list[Any] = field(default_factory=list)
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    is_read_only: bool | None = None
    touches_remote: bool | None = None  # not auto-filled by the gate yet; always None for now


def policy(call: Any, ctx: ToolCallContext) -> str:
    """Decide what to do with a tool call before it runs.

    Must return exactly one of: "approve", "deny", "escalate".
    """
    raise NotImplementedError


def reviewer(call: Any, ctx: ToolCallContext) -> bool:
    """Simulate a human reviewer's decision on an escalated tool call.

    Must return True (approve) or False (deny). May only use information
    a real human reviewer would reasonably have — no ground-truth labels,
    no attack annotations.
    """
    raise NotImplementedError
