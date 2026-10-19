# AgentDojo Approval Gate — PE6203 Group Project 2

An approval gate for the AgentDojo `workspace` suite. It intercepts every
tool call the agent wants to make and decides **approve / deny / escalate
to a human reviewer**, under a per-task escalation budget `k`.

## How it works

- `gate_patch.py` replaces AgentDojo's `ToolsExecutor` with a
  `GatedToolsExecutor` that checks every tool call before it runs.
- For each tool call, it calls your `policy(call, ctx)` function. That
  function must return `"approve"`, `"deny"`, or `"escalate"`.
- If the policy says `"escalate"`:
  - if the per-task budget `k` still has room, it calls `reviewer(call, ctx)`
    (the simulated human reviewer) and approves/denies based on that.
  - if the budget is used up, it's auto-denied.
- `interfaces.py` defines the exact shape (`ToolCallContext`, `policy()`,
  `reviewer()`) that your policy/reviewer file must follow.

## Setup (do this once, on your own computer)

Use a short folder path (e.g. `C:\dev\...` or directly under `Documents`) —
a very deeply nested path can hit a Windows file-path-length limit during
install.

```powershell
git clone https://github.com/usmin1004/PE6203-Group-Project.git
cd PE6203-Group-Project
python -m venv ad-env
.\ad-env\Scripts\Activate.ps1
pip install https://github.com/ethz-spylab/agentdojo/archive/refs/heads/main.zip
```

We install AgentDojo straight from its GitHub `main` branch (not the
stable PyPI release) because the `OPENAI_COMPATIBLE` model provider we use
isn't in a released version yet.

## Who does what (start here)

1. Read this whole README once.
2. Read `interfaces.py` — it defines the exact function shape your file must follow.
3. Depending on your part:

| Part | What to do | Where |
|---|---|---|
| 2 — Baselines + budget | Review/refine the first-draft baselines, and sanity-check the `GATE_BUDGET_K` behavior in `gate_patch.py` | `policies/full_approve_policy.py`, `policies/full_escalate_policy.py` |
| 3 — Approval policy | Write the checklist policy as a new file implementing `policy(call, ctx)` | new file in `policies/`, e.g. `policies/checklist_policy.py` |
| 4 — Simulated reviewer | Write the LLM-simulated human reviewer as a new file implementing `reviewer(call, ctx)`. Only use information a real human reviewer would see — never ground-truth or attack labels | new file in `reviewer/`, e.g. `reviewer/llm_reviewer.py` |
| 5 — Experiments | Use `run_experiment.py` to sweep policies and `k` values, collect data for the TCR@k curve and HITL Load table | `run_experiment.py`, results land in `runs/*.json` |
| 6 — Failure analysis + report | Read `PROGRESS_LOG.md` and the `runs/*.json` files for concrete numbers and trajectories | `PROGRESS_LOG.md`, `runs/` |

You only need to add your own file under `policies/` or `reviewer/` — you don't need to touch `gate_patch.py` or anyone else's file.

## Folder structure

```
interfaces.py          # shared contract — read this first
gate_patch.py           # the approval gate itself (Part 1)
zhipu_patch.py           # fixes a Zhipu API quirk, auto-loaded by gate_patch
policies/                # Part 2 (baselines) and Part 3 (your own policy) live here
  stub_policy.py          # placeholder default
  full_approve_policy.py  # baseline: always approve
  full_escalate_policy.py # baseline: always escalate
reviewer/                # Part 4 (simulated human reviewer) lives here
  stub_reviewer.py         # placeholder default (always approves)
```

## How to add your own policy or reviewer (Part 2 / 3 / 4)

1. Add a new file under `policies/` (or `reviewer/`) implementing the
   function shape from `interfaces.py`.
2. Point the gate at it with an environment variable before running the
   benchmark, e.g. (PowerShell):
   ```powershell
   $env:GATE_POLICY_MODULE = "policies.your_file_name_without_dot_py"
   $env:GATE_REVIEWER_MODULE = "reviewer.your_file_name_without_dot_py"
   $env:GATE_BUDGET_K = "3"
   ```
3. Run the benchmark as usual (see below). No need to touch `gate_patch.py`.

## Running tasks

First, every time you open a new terminal:
```powershell
.\ad-env\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
$env:OPENAI_COMPATIBLE_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
$env:OPENAI_COMPATIBLE_API_KEY = Read-Host "API key"
```

Then, to test your own policy/reviewer on a couple of tasks and save results:
```powershell
python run_experiment.py --policy policies.your_file_name --reviewer reviewer.your_file_name --k 3 --tasks user_task_0,user_task_1
```
Leave out `--tasks` to run every task in the suite. Results are saved as
`runs/<policy>_k<k>_<timestamp>.json`.

Or, to run a single task with AgentDojo's own CLI (useful for quick debugging):
```powershell
python -m agentdojo.scripts.benchmark -s workspace -ut user_task_0 --model OPENAI_COMPATIBLE --model-id glm-4.5-flash -ml gate_patch -f
```

Never commit an API key. Set it as an environment variable in your own
terminal only.

## Open question: injection/attack tasks (needs team discussion)

`run_experiment.py` currently only runs plain user tasks and measures
`utility` (did the task succeed). It does **not** yet run AgentDojo's
*injection tasks* (the attack scenarios), so it can't measure the
"without executing any unauthorized tool call" part of TCR@k — only the
"task completed" part.

To get real TCR@k numbers we need a run mode that also injects an attack
and checks `security` (AgentDojo already tracks this per task, see
`benchmark_suite_with_injections` in `agentdojo/benchmark.py`). Whoever
needs this first (likely Part 5, maybe Part 6) — flag it here or message
Part 1, and we'll extend `run_experiment.py` together rather than
duplicating the work in two places.

## Status

See `PROGRESS_LOG.md` for a detailed, chronological build log (useful for
the individual report).
