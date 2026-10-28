"""Per-component token accounting (Part 2).

The report needs API cost split into policy inference, reviewer simulation
and agent execution. This module wraps the OpenAI client's
`Completions.create` once, so every LLM call made in the process is
recorded automatically -- including the agent's own calls inside AgentDojo,
which we can't edit.

Calls are tagged with the component that is currently active:
    with cost_tracker.component("policy"):
        client.chat.completions.create(...)
Anything outside such a block is counted as "agent". The tracker is
installed as soon as this module is imported (policies.direct_llm_policy
imports it, and so does any policy/reviewer that does
`from policies import cost_tracker`).

Reading the numbers (e.g. from an experiment script):
    from policies import cost_tracker
    cost_tracker.reset()                # before a task
    ... run the task ...
    usage = cost_tracker.snapshot()     # {"agent": {...}, "policy": {...}, ...}
Without reset(), snapshot() gives totals since the process started, which
for run_experiment.py (one policy + one k per process) is the whole run.

Only token counts are stored -- never prompts, responses or keys.
"""
import contextlib
import contextvars

try:
    import openai.resources.chat.completions as comp
except ImportError:  # SDK missing (or replaced by a stub in tests): tracking is off, nothing breaks
    comp = None

_current = contextvars.ContextVar("cost_component", default="agent")
_records: list[dict] = []


@contextlib.contextmanager
def component(name: str):
    token = _current.set(name)
    try:
        yield
    finally:
        _current.reset(token)


def record(component_name: str, prompt_tokens: int, completion_tokens: int, model: str = "") -> None:
    _records.append(
        {
            "component": component_name,
            "model": model,
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
        }
    )


def reset() -> None:
    _records.clear()


def snapshot() -> dict:
    """Totals per component since the last reset()."""
    totals: dict[str, dict] = {}
    for r in _records:
        t = totals.setdefault(r["component"], {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
        t["calls"] += 1
        t["prompt_tokens"] += r["prompt_tokens"]
        t["completion_tokens"] += r["completion_tokens"]
    return totals


def _tracked_create(self, *args, **kwargs):
    response = _orig_create(self, *args, **kwargs)
    usage = getattr(response, "usage", None)
    if usage is not None:
        record(
            _current.get(),
            getattr(usage, "prompt_tokens", 0),
            getattr(usage, "completion_tokens", 0),
            kwargs.get("model", ""),
        )
    return response


if comp is not None and not getattr(comp.Completions.create, "_cost_tracked", False):
    _orig_create = comp.Completions.create
    _tracked_create._cost_tracked = True
    comp.Completions.create = _tracked_create
