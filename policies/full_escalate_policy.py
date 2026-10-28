"""Full-escalate baseline (required by the project spec, owned by Part 2).

Every tool call is sent to the (simulated) human reviewer. The gate charges
one unit of the per-task budget k per escalation; once k is used up, every
further call is auto-denied (logged with source "budget_exhausted"). So
this baseline has the highest HITL load, and its task completion drops
sharply once k is smaller than the number of tool calls a task needs.
See policies/PART2.md.
"""
from interfaces import ToolCallContext


def policy(call, ctx: ToolCallContext) -> str:
    return "escalate"
