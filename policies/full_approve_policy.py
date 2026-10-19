"""Full-approve baseline (required by the project spec). Owned by Part 2;
this is a first-cut version so the gate can be tested end to end now."""
from interfaces import ToolCallContext


def policy(call, ctx: ToolCallContext) -> str:
    return "approve"
