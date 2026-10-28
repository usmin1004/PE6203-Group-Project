"""Run one policy + one escalation budget k over a set of workspace tasks,
and save the results to a JSON file.

Usage (PowerShell, after activating ad-env and setting the API key env vars):
    python run_experiment.py --policy policies.stub_policy --reviewer reviewer.stub_reviewer --k 3
    python run_experiment.py --policy policies.full_approve_policy --k 0 --tasks user_task_0,user_task_1
"""
import argparse
import importlib
import json
import os
import time
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--policy", default="policies.stub_policy", help="dotted module path with policy(call, ctx)")
    p.add_argument("--reviewer", default="reviewer.stub_reviewer", help="dotted module path with reviewer(call, ctx)")
    p.add_argument("--k", type=int, default=3, help="escalation budget per task")
    p.add_argument("--model-id", default="glm-4.5-flash")
    p.add_argument("--suite", default="workspace")
    p.add_argument("--benchmark-version", default="v1.2.2")
    p.add_argument("--tasks", default="", help="comma-separated user_task IDs; empty = all tasks in the suite")
    p.add_argument("--out", default=None, help="results JSON path (default: runs/<policy>_k<k>_<timestamp>.json)")
    return p.parse_args()


def find_gate(element):
    """Recursively search the pipeline tree for the GatedToolsExecutor instance."""
    import gate_patch

    if isinstance(element, gate_patch.GatedToolsExecutor):
        return element
    for child in getattr(element, "elements", []):
        found = find_gate(child)
        if found is not None:
            return found
    return None


def main():
    args = parse_args()

    # Must be set before `import gate_patch`, since it loads the policy/reviewer at import time.
    os.environ["GATE_POLICY_MODULE"] = args.policy
    os.environ["GATE_REVIEWER_MODULE"] = args.reviewer
    os.environ["GATE_BUDGET_K"] = str(args.k)
    os.environ.setdefault("PYTHONUTF8", "1")

    import gate_patch  # noqa: F401  (applies the ToolsExecutor monkeypatch)
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.logging import OutputLogger
    from agentdojo.models import ModelsEnum
    from agentdojo.task_suite.load_suites import get_suite

    suite = get_suite(args.benchmark_version, args.suite)
    pipeline = AgentPipeline.from_config(
        PipelineConfig(
            llm=ModelsEnum.OPENAI_COMPATIBLE,
            model_id=args.model_id,
            defense=None,
            tool_delimiter="tool",
            system_message_name=None,
            system_message=None,
        )
    )

    gate = find_gate(pipeline)
    if gate is None:
        raise RuntimeError("Could not find GatedToolsExecutor inside the pipeline")

    task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()] or list(suite.user_tasks.keys())

    results = []
    with OutputLogger("./runs"):
        for task_id in task_ids:
            task = suite.get_user_task_by_id(task_id)
            gate.reset_budget()
            utility, security = suite.run_task_with_pipeline(pipeline, task, injection_task=None, injections={})
            results.append(
                {
                    "task_id": task_id,
                    "utility": utility,
                    "security": security,
                    "escalations_used": gate.escalations_used,
                    "gate": gate.summary(),
                    "budget_k": gate.budget_k,
                }
            )
            print(
                f"[{task_id}] utility={utility} security={security} "
                f"escalations_used={gate.escalations_used}/{gate.budget_k}"
            )

    out_path = Path(args.out) if args.out else Path("runs") / f"{args.policy.split('.')[-1]}_k{args.k}_{int(time.time())}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    avg_utility = sum(r["utility"] for r in results) / len(results) if results else None
    summary = {
        "policy_module": args.policy,
        "reviewer_module": args.reviewer,
        "k": args.k,
        "model_id": args.model_id,
        "suite": args.suite,
        "results": results,
        "avg_utility": avg_utility,
        "total_escalations": sum(r["escalations_used"] for r in results),
    }
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSaved results to {out_path}")
    if avg_utility is not None:
        print(f"Average utility: {avg_utility * 100:.2f}%")
    print(f"Total escalations used: {summary['total_escalations']}")


if __name__ == "__main__":
    main()
