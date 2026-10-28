# Part 2 — Baselines and budget management

Part 2 delivers the two required baselines, verifies the escalation budget
`k`, and adds a Direct-LLM comparison baseline plus per-component token
accounting. **All Part 2 files live in `policies/`; no other part's files
were changed.**

## Files

| File | Status | What it does |
|---|---|---|
| `policies/full_approve_policy.py` | finalised | Baseline: approve every call (= no gate) |
| `policies/full_escalate_policy.py` | finalised | Baseline: escalate every call (= full human review, limited by `k`) |
| `policies/direct_llm_policy.py` | new | Comparison baseline: one plain LLM call per tool call |
| `policies/cost_tracker.py` | new | Counts LLM tokens per component: `agent` / `policy` / `reviewer` |
| `policies/test_part2.py` | new | 35 offline checks against the group's gate as it is |
| `policies/PART2.md` | new | This document |

## 1. Baselines

| Policy | How to run | Escalations | Expected TCR@k |
|---|---|---|---|
| Full-approve | `--policy policies.full_approve_policy` | never | Flat in `k`. Under attack it executes the hijacked agent's calls, so attack successes drag TCR down |
| Full-escalate | `--policy policies.full_escalate_policy` | every call | High when `k` ≥ the number of tool calls a task needs, then drops sharply. Highest HITL load |
| Direct LLM | `--policy policies.direct_llm_policy` | when the LLM says so | In between: the reference point for Part 3's checklist policy |

The logic of the two required baselines was already correct in the first
draft. Only their documentation was finalised.

## 2. Budget `k`: verification of `gate_patch.py`

Checked against the gate exactly as committed (no changes made). Each item
below is covered by `test_part2.py`:

| Behaviour | Result |
|---|---|
| Escalation within budget goes to the reviewer and costs 1 | ✅ |
| Reviewer denies: the call is denied and it still costs 1 | ✅ |
| Budget used up: further escalations are auto-denied, reviewer not called (spec requirement) | ✅ |
| `k=0`: every escalation is denied | ✅ |
| `reset_budget()` restores the full budget (`run_experiment.py` calls it before each task) | ✅ |
| A denied call is not executed, and the agent still gets a "Denied by the approval gate." result | ✅ |
| End to end on the real workspace suite with an attack: Full-escalate + a sensible reviewer blocks the attacker's email at `k=3`, but fails the task at `k=1` (budget exhausted) | ✅ |

### Observations for the team (no code changed; for Part 1 to decide)

1. **The log can't tell why a call was denied.** Policy deny, reviewer deny
   and budget-exhausted deny all look the same in `[GATE] ... -> deny`.
   Part 6 needs to separate budget-exhausted denials (an over-conservative
   failure caused by small `k`) from the others. One option: have `decide()`
   keep a per-task list of `(tool, policy_decision, final_decision, source)`
   and have `run_experiment.py` save it.
2. **A mis-spelled policy answer silently blocks the call.** For example,
   `"Approve"` or `None` is not `"approve"`, so the call is denied with no
   warning. Part 3 should return exactly lowercase `"approve"`, `"deny"` or
   `"escalate"`.
3. **`GATE_BUDGET_K=-1` doesn't raise an error.** It behaves like `k=0`.

## 3. Direct-LLM baseline (`policies/direct_llm_policy.py`)

One LLM call per tool call, temperature 0, JSON answer
`{"decision": "approve|deny|escalate", "reason": "..."}`.

- **The model sees:** the user's task, the agent's previous tool calls
  (name + arguments), and the current call with its read-only flag.
- **The model does not see:** raw tool outputs. That's where AgentDojo
  plants its injections, and showing them would make this baseline
  injectable itself. Part 3's checklist inspects untrusted content
  explicitly; that's a difference worth discussing in the report.
- **On failure:** an unparsable answer or an API error returns
  `"escalate"` (the safe direction: reviewer, or auto-deny once `k` is used
  up). It never crashes the run. The number of fallbacks is kept in
  `direct_llm_policy.fallback_count`.
- **GLM-4.5 thinking mode:** disabled automatically when the base URL is
  Zhipu's, because thinking spends tokens and can leave the answer empty.

Env vars: `DIRECT_LLM_MODEL` (default `glm-4.5-flash`), `DIRECT_LLM_HISTORY`
(how many previous calls to show, default 10). The URL and key are the same
`OPENAI_COMPATIBLE_*` as the agent.

```powershell
python run_experiment.py --policy policies.direct_llm_policy --reviewer reviewer.llm_reviewer --k 3
```

## 4. Token cost per component (`policies/cost_tracker.py`)

The report needs API cost split into policy inference, reviewer simulation
and agent execution. Once imported, `cost_tracker` wraps the OpenAI client,
so every LLM call in the process is counted, including the agent's own calls
inside AgentDojo. Calls inside `with cost_tracker.component("<name>")` are
attributed to that name. Everything else counts as `"agent"`. Only token
counts are stored, never prompts or keys.

- **Direct LLM:** already tags its calls as `"policy"`.
- **Part 3 / Part 4 (optional):** to get their own line in the cost table,
  wrap the LLM call:
  ```python
  from policies import cost_tracker
  with cost_tracker.component("reviewer"):   # or "policy"
      response = client.chat.completions.create(...)
  ```
  Untagged calls are counted as `"agent"`.
- **Part 5:** read the totals:
  ```python
  from policies import cost_tracker
  cost_tracker.reset()               # before a task (optional)
  ...
  cost_tracker.snapshot()            # {"agent": {"calls", "prompt_tokens", "completion_tokens"}, "policy": {...}, ...}
  ```
  `run_experiment.py` runs one policy and one `k` per process, so a single
  `snapshot()` at the end is that whole experiment. Multiply by the
  provider's per-token price for dollars.

## 5. Running the baselines with the group's experiment scripts

All three Part 2 policies work unchanged with `run_experiment.py`,
`run_attack_experiment.py` and `run_replay_experiment.py`:

```powershell
python run_replay_experiment.py --policy policies.full_approve_policy --k 0
python run_replay_experiment.py --policy policies.full_escalate_policy --reviewer reviewer.llm_reviewer --k 3
python run_attack_experiment.py --policy policies.direct_llm_policy --reviewer reviewer.llm_reviewer --k 3
```

Sanity check with `run_replay_experiment.py` defaults (10 user tasks × 4
injection tasks = 40 pairs), using the **stub reviewer, which approves
everything**. So these are not report numbers, only a check that the
baselines behave as designed:

| Policy | k | TCR (replay) | Benign pass | Attack blocked | Escalations |
|---|---|---|---|---|---|
| Full-approve | 0 | 0.0% | 100% | 0% | 0 |
| Full-escalate | 0 | 0.0% | 0% | 100% | 0 |
| Full-escalate | 3 | 15.0% | 100% | 15% | 108 |

Full-approve never blocks an attack. Full-escalate at `k=0` blocks
everything, including the user's own calls. At `k=3`, with a reviewer that
approves everything, attacks are only blocked when the budget happens to run
out. With Part 4's real reviewer, the attack-blocked rate should rise.

Notes for Part 5, from testing on the real workspace suite:

1. **`security` is inverted.** With an injection task, `security == True`
   means the *attack succeeded*. `run_attack_experiment.py` already handles
   this correctly (`safe_complete = utility and not security`). The tests
   include a real pair (`user_task_0` + `injection_task_0`) where the task is
   completed *and* the attack succeeds, so utility alone would overstate TCR.
2. **HITL load definition.** The spec defines it as "the total number of
   human interventions (escalations) across all successfully completed
   tasks". Both new scripts report `total_escalations / number of completed
   tasks` instead: an average, counted over all pairs. It may be worth also
   reporting the spec's version (the sum of `escalations_used` over pairs
   with `safe_complete == True`), or stating the definition used in the
   report.
3. **Cost per component:** see section 4. `cost_tracker.snapshot()` at the
   end of a run gives agent / policy / reviewer tokens.

## 6. Tests

```powershell
python policies/test_part2.py
```

These run offline, with no API key: LLM calls go to a mocked HTTP endpoint,
and the agent is a scripted stand-in that replays AgentDojo's ground-truth
tool calls on the real workspace suite (optionally followed by the
attacker's calls, to simulate a hijack).

- Result on `main` (commit `75e0e72`, which includes Part 4 and the attack/replay
  scripts): 35/35 pass, and Part 4's own tests still pass with these files
  added.

Not yet done: a live run with a real model and API key.
