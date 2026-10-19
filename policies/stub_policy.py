"""Placeholder policy, used until Part 3 delivers the real checklist policy.

Rule: tool names that look read-only (get_/read_/search_/list_/find_) are
auto-approved; everything else is escalated to the reviewer.
"""
from interfaces import ToolCallContext

_READ_ONLY_PREFIXES = ("get_", "read_", "search_", "list_", "find_")


def policy(call, ctx: ToolCallContext) -> str:
    if ctx.tool_name.startswith(_READ_ONLY_PREFIXES):
        return "approve"
    return "escalate"
