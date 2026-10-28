"""Full-approve baseline (required by the project spec, owned by Part 2).

Every tool call is auto-approved: no human review, so the escalation budget
k is never used and results do not depend on k (a flat TCR@k line). This is
equivalent to running the agent with no gate at all, so under AgentDojo
injection attacks it executes whatever the hijacked agent asks for.
See policies/PART2.md.
"""
from interfaces import ToolCallContext


def policy(call, ctx: ToolCallContext) -> str:
    return "approve"
