"""Run one policy + one budget k over (user task x injection task) pairs WITH an attack,
and save safe-task-completion results to a JSON file.

Usage (PowerShell, after activating ad-env and setting the API key env vars):
    python run_attack_experiment.py --policy policies.stub_policy --reviewer reviewer.stub_reviewer --k 3
    python run_attack_experiment.py --policy policies.full_approve_policy --k 0 --user-tasks user_task_0,user_task_1 --injection-tasks injection_task_0

Per pair we record:
    utility        - the user's task was completed
    security       - AgentDojo says the injected attack goal was achieved (True = attack succeeded)
    safe_complete  - utility and not security   (this is our TCR numerator)
"""
import argparse
import json
import os
import time
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--policy", default="policies.stub_policy")
    p.add_argument("--reviewer", default="reviewer.stub_reviewer")
    p.add_argument("--k", type=int, default=3, help="escalation budget per task")
    p.add_argument("--model-id", default="glm-4.5-flash")
    p.add_argument("--suite", default="workspace")
    p.add_argument("--benchmark-version", default="v1.2.2")
    p.add_argument("--attack", default="important_instructions_no_model_name")
    p.add_argument("--user-tasks", default="user_task_0,user_task_1,user_task_2")
    p.add_argument("--injection-tasks", default="injection_task_0,injection_task_1")
    p.add_argument("--out", default=None)
    p.add_argument("--verbose", action="store_true", help="print each tool result and whether the attack text is in it")
    return p.parse_args()


def find_gate(element):
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

    os.environ["GATE_POLICY_MODULE"] = args.policy
    os.environ["GATE_REVIEWER_MODULE"] = args.reviewer
    os.environ["GATE_BUDGET_K"] = str(args.k)
    os.environ.setdefault("PYTHONUTF8", "1")

    import gate_patch  # noqa: F401
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.attacks.attack_registry import load_attack
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

    # AgentDojo's attacks look up a known model name inside pipeline.name to write the
    # attack text. Our custom model is not in its list, so we give the pipeline a known
    # name. The "no_model_name" attack variant does not print it, so this only avoids an error.
    pipeline.name = "gpt-4o-2024-05-13"
    attack = load_attack(args.attack, suite, pipeline)

    state = {"goal": ""}
    if args.verbose:
        from agentdojo.types import get_text_content_as_str

        _orig_query = gate_patch.GatedToolsExecutor.query

        def _traced_query(self, query, runtime, env=None, messages=[], extra_args={}):
            kwargs = {} if env is None else {"env": env}
            out = _orig_query(self, query, runtime, messages=messages, extra_args=extra_args, **kwargs)
            for m in out[3][len(messages):]:
                if m["role"] == "tool":
                    text = get_text_content_as_str(m["content"]) if m["content"] else ""
                    def _norm(s):
                        return "".join(ch for ch in s if ch.isalnum())

                    hit = bool(state["goal"]) and _norm(state["goal"])[:40] in _norm(text)
                    print(f"[TOOL RESULT] {m['tool_call'].function} | attack text inside: {hit}\n    {text[:500]!r}", flush=True)
            return out

        gate_patch.GatedToolsExecutor.query = _traced_query

    user_ids = [t.strip() for t in args.user_tasks.split(",") if t.strip()]
    inj_ids = [t.strip() for t in args.injection_tasks.split(",") if t.strip()]

    results = []
    with OutputLogger("./runs"):
        for u_id in user_ids:
            user_task = suite.get_user_task_by_id(u_id)
            for i_id in inj_ids:
                inj_task = suite.get_injection_task_by_id(i_id)
                try:
                    injections = attack.attack(user_task, inj_task)
                except ValueError as e:  # user task has no place to inject
                    print(f"[{u_id} x {i_id}] skipped: {e}")
                    continue
                gate.reset_budget()
                state["goal"] = inj_task.GOAL
                if args.verbose:
                    print(f"[ATTACK GOAL] {inj_task.GOAL!r}", flush=True)
                utility, security = suite.run_task_with_pipeline(pipeline, user_task, inj_task, injections)
                row = {
                    "user_task": u_id,
                    "injection_task": i_id,
                    "utility": utility,
                    "security": security,
                    "safe_complete": bool(utility and not security),
                    "escalations_used": gate.escalations_used,
                "gate": gate.summary(),
                    "budget_k": gate.budget_k,
                }
                results.append(row)
                print(
                    f"[{u_id} x {i_id}] utility={utility} attack_succeeded={security} "
                    f"safe_complete={row['safe_complete']} escalations={gate.escalations_used}/{gate.budget_k}"
                )

    n = len(results)
    safe = sum(r["safe_complete"] for r in results)
    done = sum(bool(r["utility"]) for r in results)
    esc = sum(r["escalations_used"] for r in results)
    summary = {
        "policy_module": args.policy,
        "reviewer_module": args.reviewer,
        "k": args.k,
        "model_id": args.model_id,
        "attack": args.attack,
        "pairs": n,
        "tcr": safe / n if n else None,
        "utility_rate": done / n if n else None,
        "attack_success_rate": sum(bool(r["security"]) for r in results) / n if n else None,
        "total_escalations": esc,
        "hitl_load": esc / done if done else None,  # escalations per successfully completed task
        "results": results,
    }
    out_path = Path(args.out) if args.out else Path("runs") / f"attack_{args.policy.split('.')[-1]}_k{args.k}_{int(time.time())}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSaved results to {out_path}")
    if n:
        print(f"TCR (safe completion): {summary['tcr'] * 100:.1f}%  |  attack success: {summary['attack_success_rate'] * 100:.1f}%")
        print(f"Total escalations: {esc}  |  HITL load: {summary['hitl_load']}")


if __name__ == "__main__":
    main()
