# Part 4 submission and integration guide

Jeff's contribution is the LLM-simulated human reviewer. The assignment requests
submission through the group GitHub repository. This directory supplies the
reviewer implementation, its report section, and supporting validation evidence.

Current integration entry point: [FINAL_HANDOFF.md](FINAL_HANDOFF.md). The
28 October update passes 31 checks and includes the shared cost-tracker adapter
and [run_with_accounting.py](run_with_accounting.py). PR #1 is already merged;
this follow-up must also be merged before using the new accounting behavior.

## Required contribution and uploaded materials

| Part 4 requirement | Material |
|---|---|
| Independent approve/deny reviewer using the shared interface | [llm_reviewer.py](llm_reviewer.py) |
| Design, exact prompt location, allowed evidence and configuration | [PART4.md](PART4.md); `SYSTEM_PROMPT` in the implementation |
| No benchmark answers, attack labels or oracle access in reviewer input | Allowlisted context projection in the implementation; evidence-boundary tests in [test_llm_reviewer.py](test_llm_reviewer.py) |
| Report contribution and speaking notes | [PART4_REPORT.md](PART4_REPORT.md) |
| Offline and native integration checks | [test_llm_reviewer.py](test_llm_reviewer.py), [test_agentdojo_context.py](test_agentdojo_context.py) |
| Reproducible optional live sanity check | [smoke_test.py](smoke_test.py), [LIVE_VALIDATION.md](LIVE_VALIDATION.md), [live_validation.json](live_validation.json) |
| Real AgentDojo integration, including an authorized write | [AGENTDOJO_VALIDATION.md](AGENTDOJO_VALIDATION.md), [agentdojo_validation.json](agentdojo_validation.json) |
| Complete benign workspace run and reviewer cost/load evidence | [WORKSPACE_VALIDATION.md](WORKSPACE_VALIDATION.md), [workspace_validation.json](workspace_validation.json) |

The original shared `stub_reviewer.py` remains a placeholder. Select the new
reviewer explicitly from the repository root:

```powershell
python -m unittest reviewer.test_agentdojo_context reviewer.test_llm_reviewer -v
python run_experiment.py --policy policies.full_escalate_policy --reviewer reviewer.llm_reviewer --k 3 --tasks user_task_0,user_task_1
```

Configure credentials locally following [PART4.md](PART4.md) before a live run.
The unit tests do not make paid requests. The two native tests require AgentDojo;
a skipped native test does not establish integration success.

## What the evidence establishes

All 26 tests passed in the recorded AgentDojo environment. The 40-task benign
workspace run completed 25 tasks (62.5%), with 73 valid reviews overall and 45
reviews on successful tasks. Reviewer usage was 78,131 tokens. These measured
runs used OpenRouter GPT-4.1 mini, not the default class GLM model. Details,
source hashes, cost assumptions and limitations are retained in the evidence.

The JSON records preserve proposed tool calls and reviewer/gate decisions;
they are not complete conversation transcripts. Original failed compatibility
checks are retained alongside the successful corrected runs.

## Remaining group submission work

This completes the Part 4 contribution for integration. The final group report
and presentation must additionally combine the custom policy and both baselines,
attack-aware safe TCR@k curves across budgets, successful-task HITL load,
separate policy/reviewer/agent costs, over-conservative and over-permissive
failure trajectories, and escalation-value analysis. The current benign run
does not satisfy those attack-aware comparisons by itself.

The report owner can incorporate PART4_REPORT.md into the group report. The
experiment owner can select this reviewer with each policy while holding the
reviewer model and prompt fixed. Shared gate, interface, policy and runner files
are outside this contribution.

Only source, documentation and synthetic/benchmark validation records belong in
this upload. API keys, local environments, caches and private WhatsApp history
are excluded. A local ZIP is a convenience copy; the GitHub files are the
submission materials and do not require uploading a duplicate ZIP to the repo.
