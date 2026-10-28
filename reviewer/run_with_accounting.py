"""Run a shared experiment with reviewer diagnostics and component token totals.

Example:
python -m reviewer.run_with_accounting --mode replay --accounting-out runs/reviewer_costs.json --policy policies.full_escalate_policy --k 3 --out runs/replay.json
No prompts, API keys or complete conversations are saved by this wrapper.
"""
import argparse
from collections import Counter
import json
import logging
import os
from pathlib import Path
import runpy
import sys

MODES = {"replay": "run_replay_experiment", "attack": "run_attack_experiment", "benign": "run_experiment"}


def summarize(records):
    summary = {
        "review_attempts": len(records),
        "valid_approvals": sum(r["status"] == "ok" and r["approved"] for r in records),
        "semantic_denials": sum(r["status"] == "ok" and not r["approved"] for r in records),
        "operational_denials": sum(r["status"] != "ok" for r in records),
        "statuses": dict(Counter(r["status"] for r in records)),
    }
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        known = [r[field] for r in records if type(r.get(field)) is int]
        summary[field] = {"known_sum": sum(known), "unknown_reviews": len(records) - len(known)}
    return summary


class ReviewCapture(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.records = []

    def emit(self, record):
        message = record.getMessage()
        if message.startswith("REVIEWER "):
            self.records.append(json.loads(message[len("REVIEWER "):]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--accounting-out", required=True)
    args, forwarded = parser.parse_known_args(argv)
    # This entry point deliberately evaluates this Part 4 implementation.
    if any(a == "--reviewer" or a.startswith("--reviewer=") for a in forwarded):
        parser.error("The wrapper selects reviewer.llm_reviewer; omit --reviewer.")
    if "--help" in forwarded or "-h" in forwarded:
        parser.error("Use the shared runner directly for its help.")
    destination = Path(args.accounting_out)
    # Prepare the output directory before the experiment starts.
    destination.parent.mkdir(parents=True, exist_ok=True)
    for index, value in enumerate(forwarded):
        result_path = value.split("=", 1)[1] if value.startswith("--out=") else (
            forwarded[index + 1] if value == "--out" and index + 1 < len(forwarded) else None)
        if result_path and Path(result_path).resolve() == destination.resolve():
            parser.error("--accounting-out must differ from the experiment --out file.")

    from policies import cost_tracker
    cost_tracker.reset()
    capture = ReviewCapture()
    logger = logging.getLogger("reviewer.llm_reviewer")
    old_level, old_disabled = logger.level, logger.disabled
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(capture)
    old_argv = sys.argv
    script = MODES[args.mode]
    sys.argv = [script + ".py", *forwarded, "--reviewer", "reviewer.llm_reviewer"]
    completed, error_type = False, None
    try:
        runpy.run_module(script, run_name="__main__")
        completed = True
    except BaseException as exc:
        error_type = type(exc).__name__
        raise
    finally:
        sys.argv = old_argv
        logger.removeHandler(capture)
        logger.setLevel(old_level)
        logger.disabled = old_disabled
        result = {
            "mode": args.mode, "runner": script, "runner_completed": completed,
            "error_type": error_type, "reviewer_module": "reviewer.llm_reviewer",
            "reviewer_model": os.environ.get("REVIEWER_MODEL", "glm-4.5-flash"),
            "reviewer_summary": summarize(capture.records),
            "component_usage": cost_tracker.snapshot(), "reviews": capture.records,
            "limitations": [
                "Component tracker counts responses with usage; missing usage is not zero cost.",
                "Reviewer records are ordered run-level records, not full task trajectories.",
                "Use runner results for task outcomes, budget denials and successful-task HITL load.",
                "Replay completion is a synthetic gate test, not live-agent safe TCR.",
            ],
        }
        destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved reviewer accounting to {destination}")


if __name__ == "__main__":
    main()
