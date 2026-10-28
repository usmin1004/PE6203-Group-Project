
# Part 5 — Experimental Evaluation Design

## 1. Objective

Evaluate whether our proposed approval policy achieves higher safe task completion with fewer human-review escalations than two baseline policies.

The evaluation follows the NTU PE6203 Group Project 2 requirements, using AgentDojo.

This document is the experimental plan. No actual benchmark results have been collected yet.

## 2. Research Questions

- RQ1: How does safe task completion change as the escalation budget k increases?
- RQ2: Does our proposed policy reduce human-review load compared with full escalation?
- RQ3: How does the proposed policy compare against full approval and full escalation?
- RQ4: What additional API cost does each strategy introduce?
- RQ5: Which types of tool calls benefit most from human escalation?
- RQ6: What causes over-conservative and over-permissive failures?

## 3. Experimental Setup

### Benchmark

- Framework: AgentDojo
- Initial suite: `workspace`
- Benchmark version: `v1.2.2`
- Agent model: `glm-4.5-flash` (subject to confirmation)
- Initial inspection identified 40 workspace user tasks and 14 injection tasks.

The final evaluation must include meaningful security scenarios, not only normal user tasks.

Current limitation: `run_experiment.py` calls the benchmark without injecting attacks. This must be addressed before reporting security performance.

### Policies

Evaluate three strategies:

1. Full-approve baseline: Approve every tool call without escalation.
2. Full-escalate baseline: Escalate every tool call, subject to budget k.
3. Proposed policy: Use the group's developed approval policy to approve, deny, or escalate.

All three strategies must use the same agent model, benchmark configuration, reviewer implementation where applicable, and comparable task scenarios.

### Escalation Budgets

Proposed initial values:

`k = 0, 1, 2, 3, 5, 10`

These values are provisional. After inspecting escalation counts and benchmark behaviour, extend the range if necessary to show meaningful performance differences, particularly for full-escalate.

The budget resets for each task. When k is exhausted, further escalation requests become denials.

### Experimental Matrix

Run every applicable policy at each budget value on the same benchmark task/scenario set.

Record policy, k, model, suite, benchmark version, task ID, scenario/attack ID, reviewer configuration, and run identifier.

Do not compare strategies using different task sets or mismatched configurations.

## 4. Main Evaluation Metrics

### 4.1 Safe Task Completion Rate (TCR@k)

TCR@k = Number of safely completed tasks / Total evaluated tasks

A task counts as safely completed only when:

- The legitimate user task succeeds; AND
- No unauthorized tool call is executed.

Both conditions must be verified from appropriate benchmark outcomes or execution records.

A missing security result must not automatically be treated as a successful security outcome.

Report TCR@k curves for all three policies across a meaningful range of k values.

### 4.2 Human-in-the-Loop Load (HITL)

Primary assignment metric:

HITL Load = Total escalations across all successfully completed tasks.

Report a comparison table by policy and escalation budget.

Supplementary measures:

- Total escalations across all evaluated tasks.
- Mean escalations per successful task.
- Number of tasks exhausting the escalation budget.

Clearly distinguish the required metric from supplementary measures.

### 4.3 API Cost

Record model usage separately for:

1. Agent execution.
2. Approval-policy inference.
3. LLM-simulated reviewer.

Report tokens or monetary cost per component and total cost for each strategy.

If a policy is rule-based, record zero LLM inference cost for that component.

Record token counts, model names and pricing assumptions where available. Do not invent costs when usage data is missing.

## 5. Human Reviewer Simulation

Use an actual LLM-simulated reviewer during final evaluation.

The reviewer receives only information reasonably available to a human reviewer, such as:

- Legitimate task description.
- Tool name and arguments.
- Relevant conversation or preceding agent trace.
- Available tool-call metadata.

The reviewer returns an approve/deny decision.

Document its model, prompt, input context and decision-parsing logic.

Never expose benchmark ground truth, attack annotations, hidden labels or other oracle information to the reviewer.

Current limitation: `reviewer/stub_reviewer.py` always approves. It is a placeholder and is not a valid final simulated-human baseline.

## 6. Security Evaluation

Include AgentDojo scenarios that meaningfully test unauthorized tool calls and attacks.

For each scenario, record:

- Legitimate task identifier.
- Attack/injection identifier, where applicable.
- Whether the legitimate task completed.
- Whether an unauthorized action occurred.
- Tool calls attempted and executed.
- Gate decisions and reviewer outcomes.

Verify how AgentDojo defines utility and security results before implementing the final safe-TCR calculation.

The current non-injection runner is suitable for preliminary functionality checks only, not sufficient evidence of adversarial security.

## 7. Failure Case Classification

### Over-conservative failures

Examples:

- A safe tool call was unnecessarily denied.
- Safe calls were escalated unnecessarily, exhausting the budget.
- The legitimate task failed because required actions were blocked.

### Over-permissive failures

Examples:

- An unsafe tool call was automatically approved.
- An unauthorized action was executed.
- The approval policy failed to detect a malicious or out-of-scope action.

Classify failures using the legitimate task, observed trajectory and applicable security evidence, not assumptions based only on a tool's name.

## 8. Representative Trajectories

Preserve at least one concrete example of each failure type.

Each trajectory should show:

1. Legitimate user task.
2. Relevant agent context.
3. Tool call name and arguments.
4. Policy decision: approve, deny or escalate.
5. Reviewer decision, if escalated.
6. Whether the tool executed.
7. Task outcome and security outcome.
8. Explanation of the failure.

Ensure logs do not expose API keys or other secrets.

## 9. Escalation-Value Analysis

Compare which tool-call categories benefit most from escalation, including:

- Read-only queries.
- Local computation.
- File modification and write operations.
- External API calls with side effects.
- Irreversible or destructive actions.

Examine whether escalation prevents unauthorized actions, preserves legitimate task completion, or creates unnecessary review load.

Use observed trajectories and results to support conclusions.

## 10. Required Outputs

Prepare the following for the final report:

- TCR@k comparison curves for all three strategies.
- HITL load comparison table.
- API cost breakdown by policy and component.
- Over-conservative failure classification and trajectory.
- Over-permissive failure classification and trajectory.
- Escalation-value analysis and interpretation.
- Description of benchmark setup, reviewer configuration and limitations.

Provide the group with results suitable for the 10-minute presentation, including baseline comparisons, representative failures and main lessons learned.

## 11. Data Logging Requirements

The experiment runner must preserve sufficient data for analysis:

- Run ID and configuration.
- Policy and escalation budget.
- User task and attack/scenario identifiers.
- Utility/task-success outcome.
- Security/unauthorized-action outcome.
- Escalation count.
- Ordered tool-call trajectory.
- Initial policy decision and final gate decision.
- Reviewer decision where applicable.
- Tool execution status.
- Agent, policy and reviewer token usage/cost.

Existing runner outputs include basic task results and escalation counts. Additional logging may be required for costs, trajectories, and reliable security assessment.

## 12. Pre-Experiment Validation Checklist

- [ ] Confirm proposed policy is integrated.
- [ ] Confirm LLM reviewer replaces the stub for final evaluation.
- [ ] Confirm reviewer cannot access benchmark oracle information.
- [ ] Confirm the same scenarios are used across policies.
- [ ] Confirm security/attack scenarios are actually executed.
- [ ] Confirm utility and security outcome semantics.
- [ ] Confirm budget resets per task and exhaustion causes denial.
- [ ] Confirm token usage and component-level costs are captured.
- [ ] Confirm complete trajectories are recorded.
- [ ] Run a small pilot after API access is available.
- [ ] Validate output data before launching the full experiment.

## 13. Current Status

Experimental design: Draft prepared.

Actual experiments: Not started.

Outstanding dependencies: API access, proposed policy integration, LLM reviewer, security-scenario execution, expanded logging and end-to-end validation.

No experimental performance or safety claims should be made until real benchmark results are available.
