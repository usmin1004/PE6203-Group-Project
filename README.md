# Safety Approval Policies for Agent Harnesses (AgentDojo) — PE6203 Group Project 2

An **approval gate** for the AgentDojo `workspace` suite. Before every tool call the agent wants to make, the gate decides:

- **approve** — the call runs;
- **deny** — the call is blocked (the agent sees "Denied by the approval gate.");
- **escalate** — a simulated human reviewer decides, using one unit of the per-task escalation budget **k**. When the budget is used up, further escalations are **auto-denied**.

We compare our checklist policy with two baselines (full-approve, full-escalate) and a Direct-LLM baseline, using two metrics from the assignment:

- **TCR@k** — fraction of tasks completed safely (user task succeeds and no unauthorized tool call runs) when at most k calls per task may be escalated.
- **HITL load** — total number of escalations across all successfully completed tasks (a **sum**, not an average).

## Repository layout

```
interfaces.py            Shared contract: ToolCallContext, policy(call, ctx), reviewer(call, ctx)
gate_patch.py            The approval gate (Part 1): approve / deny / escalate, budget k, denial-reason log
zhipu_patch.py           Fixes a Zhipu API quirk; loaded automatically by gate_patch

policies/                Approval policies and baselines
  full_approve_policy.py   Baseline: approve every call
  full_escalate_policy.py  Baseline: escalate every call (limited by k)
  direct_llm_policy.py     Baseline: one plain LLM call per tool call
  checklist_policy.py      Our policy (Part 3): authorization / target & side effects / untrusted instructions
  stub_policy.py           Placeholder default
  cost_tracker.py          Token accounting per component (agent / policy / reviewer)
  PART2.md, test_part2.py  Baseline + budget documentation and 35 offline checks

reviewer/                LLM-simulated human reviewer (Part 4)
  llm_reviewer.py          reviewer(call, ctx) -> bool, sees only human-visible information
  run_with_accounting.py   Runs the experiment scripts and saves per-component costs
  stub_reviewer.py         Placeholder (always approves)
  FINAL_HANDOFF.md         Commands and configuration for experiments

run_experiment.py          Benign tasks only (no attack)
run_attack_experiment.py   Live agent + AgentDojo attack (safe task completion)
run_replay_experiment.py   No agent model: replays ground-truth benign + attack calls through the gate
check_security.py          Sanity check that AgentDojo's attack scoring can return "attack succeeded"

evaluation/EXPERIMENT_DESIGN.md   Experiment plan (Part 5)
part3/                    Part 3 report, tests and live results for the checklist policy
part6/                    Failure analysis, escalation-value discussion and original case evidence
```

## How the gate works

`gate_patch.py` replaces AgentDojo's `ToolsExecutor` with a `GatedToolsExecutor`. For each tool call it builds a `ToolCallContext` (task description, conversation history, tool name and arguments, read-only flag) and calls the policy. If the policy returns `escalate` and the budget has room, the reviewer is called (its answer is final, and the escalation costs 1). If the budget is used up, the call is denied. The budget resets before every task.

The gate records why each call was approved or denied (`policy_approve`, `policy_deny`, `reviewer_approve`, `reviewer_deny`, `budget_exhausted`, `invalid_policy_answer`). Result rows contain a `gate` entry with these counts, so over-conservative failures caused by a small k can be separated from other denials. A policy answer that is not exactly `"approve"`, `"deny"` or `"escalate"` is treated as deny and prints a warning.

## Setup (once, on your own computer)

Use a short folder path (e.g. directly under `Documents`); very deep paths can hit the Windows path-length limit during install.

```powershell
git clone https://github.com/usmin1004/PE6203-Group-Project.git
cd PE6203-Group-Project
python -m venv ad-env
.\ad-env\Scripts\Activate.ps1
pip install https://github.com/ethz-spylab/agentdojo/archive/refs/heads/main.zip
```

AgentDojo is installed from its GitHub `main` branch because the `OPENAI_COMPATIBLE` model provider we use was not in a released version when we started.

## Models and API keys

All LLM calls use an OpenAI-compatible endpoint. **Never commit API keys.** Set them in your own terminal only:

```powershell
$env:PYTHONUTF8 = "1"
$env:OPENAI_COMPATIBLE_BASE_URL = "<endpoint, e.g. https://open.bigmodel.cn/api/paas/v4/ or https://openrouter.ai/api/v1>"
$env:OPENAI_COMPATIBLE_API_KEY = Read-Host "API key"
```

Optional, per component (defaults to `glm-4.5-flash` where applicable):

```powershell
$env:CHECKLIST_MODEL = "<model id>"    # Part 3 policy
$env:REVIEWER_MODEL = "<model id>"     # Part 4 reviewer
$env:DIRECT_LLM_MODEL = "<model id>"   # Direct-LLM baseline
```

Keep the model, prompts and token limits fixed across policy and k comparisons.

Which model was used where:

- **Final experiments (Part 5, reported in the group report): `openai/gpt-4o-mini`** via OpenRouter, for the agent, policies and simulated reviewer.
- Separate earlier runs ("cohort A") in `part3/live/` and `part6/evidence/` (28 October 2026) used `openai/gpt-4.1-mini` via OpenRouter. They are kept as a separate experiment and are not pooled with the final results.
- `glm-4.5-flash` is only the default value in the code (class Zhipu endpoint); pass `--model-id` or set the `*_MODEL` variables to use another model.
- Small free models rarely followed injected instructions, so live attack runs with them could not separate policies; see "Limitations".

Results from different models must not be mixed in one comparison. State the model next to every number in the report.

## Running experiments

Select the policy, reviewer and budget on the command line:

```powershell
# Replay test (no agent model; fast and cheap): ground-truth benign + attack calls through the gate
python run_replay_experiment.py --policy policies.checklist_policy --reviewer reviewer.llm_reviewer --k 3

# Live agent with an AgentDojo attack
python run_attack_experiment.py --policy policies.checklist_policy --reviewer reviewer.llm_reviewer --k 3 --model-id <model id> --user-tasks user_task_0,user_task_1 --injection-tasks injection_task_0

# Benign tasks only
python run_experiment.py --policy policies.checklist_policy --reviewer reviewer.llm_reviewer --k 3 --tasks user_task_0,user_task_1

# Same runs with per-component cost accounting
python -m reviewer.run_with_accounting --mode replay --accounting-out runs/replay_k3_costs.json --policy policies.checklist_policy --k 3 --out runs/replay_k3.json
```

Baselines: `--policy policies.full_approve_policy`, `--policy policies.full_escalate_policy`, `--policy policies.direct_llm_policy`. Use the same tasks and k values for every policy. Results are written to `runs/*.json` (this folder is git-ignored; copy final results you cite into the repository).

Fields to use in the report:

| Metric | Field |
|---|---|
| TCR@k | `tcr` (attack and replay runs) |
| HITL load (assignment definition) | `hitl_load_official` (sum of escalations over safely completed tasks); `hitl_load_utility_success` in benign runs |
| Old ratio (all escalations / successes), do not use in the report | `hitl_load` |
| Why calls were denied | `gate` entry in each result row |
| Component cost | `api_usage` / accounting JSON (agent, policy, reviewer) |

## Reproducing the sanity checks

```powershell
python check_security.py                                  # attacker's own calls must score "attack succeeded"
python run_replay_experiment.py --policy policies.full_approve_policy --k 0     # benign 100%, attacks blocked 0%
python run_replay_experiment.py --policy policies.full_escalate_policy --k 0    # benign 0%, attacks blocked 100%
```

## Adding your own policy or reviewer

Add a file under `policies/` or `reviewer/` that follows `interfaces.py`, then select it with `--policy` / `--reviewer` (or the environment variables `GATE_POLICY_MODULE`, `GATE_REVIEWER_MODULE`, `GATE_BUDGET_K`). Policies must return exactly the lowercase strings `approve`, `deny` or `escalate`. A reviewer may only use information a real human reviewer would see; benchmark labels and attack annotations must never reach it.

## Limitations

- The replay test assumes the agent always attempts the attack (worst case) and uses a synthetic conversation history; tool outputs are not simulated.
- Small free models rarely followed injected instructions in live runs, so attack success was near zero there.
- Free models vary from run to run, so a single run of a policy can differ from the next; compare policies over many tasks.

## Documentation by part

| Part | Topic | Where |
|---|---|---|
| 1 | Gate, budget k, experiment runners | `gate_patch.py`, `run_*_experiment.py` |
| 2 | Baselines, budget checks, Direct-LLM, cost tracker | `policies/PART2.md` |
| 3 | Checklist approval policy | `part3/PART3_REPORT.md`, `part3/live/` |
| 4 | Simulated human reviewer | `reviewer/PART4.md`, `reviewer/PART4_REPORT.md`, `reviewer/FINAL_HANDOFF.md` |
| 5 | Experiment design and results | `evaluation/EXPERIMENT_DESIGN.md` |
| 6 | Failure analysis and escalation value | `part6/FAILURE_ANALYSIS.md` |
