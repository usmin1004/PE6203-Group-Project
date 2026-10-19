"""Placeholder reviewer, used until Part 4 delivers the real LLM-simulated
human reviewer. Always approves, so the escalate path can be tested now."""
from interfaces import ToolCallContext


def reviewer(call, ctx: ToolCallContext) -> bool:
    return True
