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

## Running a benchmark task

```powershell
.\ad-env\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
$env:OPENAI_COMPATIBLE_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
$env:OPENAI_COMPATIBLE_API_KEY = Read-Host "API key"
python -m agentdojo.scripts.benchmark -s workspace -ut user_task_0 --model OPENAI_COMPATIBLE --model-id glm-4.5-flash -ml gate_patch -f
```

Never commit an API key. Set it as an environment variable in your own
terminal only.

## Status

See `PROGRESS_LOG.md` for a detailed, chronological build log (useful for
the individual report).
