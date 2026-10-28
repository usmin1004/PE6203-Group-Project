# Part 4 final integration handoff

Owner: Gao Zihan (Jeff). Updated 28 October 2026.

## Ready for Part 1 and Part 5 integration

`reviewer.llm_reviewer.reviewer(call, ctx) -> bool` is the final candidate for
comparative evaluation. The earlier implementation is already on main through
PR #1. This follow-up adapts accounting to Part 2's merged tracker and adds
current experiment-handoff checks. Merge the follow-up before final runs.

The decision prompt is unchanged. The reviewer never inspects task objects,
ground-truth methods, attack labels or evaluator outcomes. It only receives the
shared visible context. A replay runner may generate candidate calls from ground
truth, but it must not pass their correctness labels into this reviewer. The
visible injected instruction in a tool message is untrusted evidence, not an
oracle label or authorization.

## Changes since the previous delivery

- Reviewer requests run inside `cost_tracker.component("reviewer")`. Previously,
  the new tracker could attribute them to its default `agent` component.
- The actual class GLM-4.5 endpoint receives `thinking: {type: disabled}` to keep
  its 512-token decision budget available for output, consistent with Part 2.
  Other providers do not receive that option.
- An optional wrapper calls existing shared runners and saves reviewer records
  and shared component totals separately from experiment results. Shared gate,
  interfaces, policies and experiment scripts are unchanged.
- Missing usage remains unknown in reviewer records. Semantic denials and
  operational/configuration denials are counted separately.

## Configuration

Use the group's environment and set credentials locally. Do not commit keys.

```powershell
$env:REVIEWER_MODEL = "glm-4.5-flash"
$env:OPENAI_COMPATIBLE_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
# Set OPENAI_COMPATIBLE_API_KEY locally before live requests.
```

The agent and reviewer both fall back to the shared key and endpoint. A distinct
`REVIEWER_API_KEY` / `REVIEWER_BASE_URL` overrides only the reviewer. For the
previous OpenRouter model, explicitly set reviewer model and endpoint as shown
in PART4.md; do not compare it against GLM runs as though models were identical.
Keep model, prompt, JSON-mode setting and context/token limits fixed across
policy and budget comparisons.

## Run the new replay workflow

Direct use remains compatible with Part 1's command:

```powershell
python run_replay_experiment.py --policy policies.full_escalate_policy --reviewer reviewer.llm_reviewer --k 3
```

For Part 5, export accounting alongside results with the wrapper:

```powershell
python -m reviewer.run_with_accounting --mode replay --accounting-out runs/replay_k3_costs.json --policy policies.full_escalate_policy --k 3 --user-tasks user_task_0 --injection-tasks injection_task_0 --out runs/replay_k3.json
python -m reviewer.run_with_accounting --mode attack --accounting-out runs/attack_k3_costs.json --policy policies.full_escalate_policy --k 3 --user-tasks user_task_0 --injection-tasks injection_task_0 --out runs/attack_k3.json
```

Replace the policy module with the actual Part 3 module once merged, and use
matching task/injection sets for every policy and k. `--mode benign` selects
run_experiment.py. The wrapper selects reviewer.llm_reviewer automatically;
do not pass another --reviewer. Use different paths for costs and results.
Each invocation starts a fresh run-level cost snapshot.

`component_usage` contains the shared tracker totals for agent, policy and
reviewer when present. `reviewer_summary` and `reviews` retain reviewer status,
returned/requested model IDs and token counts. Do not add reviewer tokens from
both sources. These are ordered run-level records, not complete task traces;
Part 5 should retain task-linked trajectories in its evaluation logger.
Responses without usage and requests that fail before a response can be missing
from shared tracker totals. Inspect unknown counts and errors before reporting
costs. A run that raises still writes a partial sidecar with runner_completed=false.

## Metrics to retain in the evaluation

- Replay uses synthetic history, omitted tool outputs and an assumed attempted
  attack. Its `tcr` is replay gate completion, not measured live-agent safe TCR.
- Real-attack safe completion is utility AND NOT attack success. With no attack,
  AgentDojo's security flag is not evidence of attack resistance.
- The current shared `hitl_load` divides all escalations by successful tasks.
  That differs from the assignment's sum of escalations on successful tasks.
  Compute the required sum from per-task results: for replay select benign_ok;
  for live runs select utility. Report the sum on safe_complete tasks separately
  if desired, and label any mean clearly. Budget auto-denials do not call the
  reviewer and incur no reviewer request.
- Gate summary reviewer_denials includes both valid semantic denials and reviewer
  errors/configuration failures. Use reviewer status records to distinguish them;
  do not label every reviewer denial a model judgment error.

## Verification and scope

Against merged main 77e68b0, all 31 tests pass:

```powershell
python -m unittest reviewer.test_agentdojo_context reviewer.test_llm_reviewer reviewer.test_experiment_handoff -v
```

The new native regression executes the actual run_replay_experiment.py with one
workspace task/injection pair at k=0, 1 and 3, the actual gate, and the installed
OpenAI SDK over an in-memory HTTP transport. It verifies exact request/budget
counts, evidence serialization and reviewer-only component attribution. Scripted
model responses are test fixtures; no network request is made and these results
are not a reviewer accuracy or security score. Missing dependencies cause skips.

The previous live OpenRouter results (six synthetic cases, three integration
tasks and the 40-task benign run) retain their original commit/hash provenance.
This follow-up has not repeated those paid runs or established live GLM accuracy.
The implementation is ready for the team's pilot and final comparative runs;
model decisions can remain conservative or be manipulated by untrusted text.

Machine-readable source hashes, check outcomes and the zero-budget replay result
are retained in FINAL_VALIDATION.json. The existing Part 2 baseline, budget and
cost tests also pass.
