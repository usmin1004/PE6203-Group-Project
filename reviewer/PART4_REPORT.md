# LLM simulation of human review

## Purpose and interface

Our simulated reviewer resolves tool calls escalated by the approval policy. It
implements the shared `reviewer(call, ctx) -> bool` interface: `True` authorizes
execution and `False` denies it. The gate remains responsible for enforcing the
per-task attention budget. Calls beyond that budget are denied without querying
the reviewer. A review that encounters an operational error still consumes the
escalation already counted by the gate.

## Information available at decision time

The reviewer receives the user's task, the proposed tool name and arguments,
the preceding conversation, and available metadata about read-only behavior and
remote resources. A field allowlist preserves text, message roles, visible tool
calls and results, while excluding arbitrary context and message metadata. The
reviewer does not inspect the benchmark environment, user-task implementation,
security evaluator, attack annotations, or ground-truth task labels. Expected
answers used in tests remain outside the reviewer's input. The integration must
also ensure that oracle information is not placed inside otherwise visible text.

The implementation additionally validates scalar metadata types and limits JSON
container nesting to 64 levels. Missing context fields and malformed metadata
produce a denial before an API request, so they cannot abort the gate's decision
path or be serialized as arbitrary nested annotations.

## Prompting and decision procedure

A separate model request asks the reviewer to independently assess authorization,
purpose, targets, scope, and side effects. The request consists of a fixed system
instruction and one JSON evidence message. The preceding trace is represented as
data with source roles retained. Instructions found in emails, documents, tool
outputs, arguments, or assistant claims do not constitute user authorization.

The reviewer may approve routine intermediate actions needed for the task, even
when the user did not name the exact tool. Neither a read-only name nor a write
operation determines the decision on its own. For example, sending the requested
message to the requested recipient may be approved, while reading unrelated
private information may be denied. Unresolved material uncertainty results in
denial because the reviewer interface offers no further escalation or dialogue.

The output must be a JSON object containing an `approve` or `deny` decision and
a short explanation. Strict parsing rejects malformed, incomplete, contradictory,
or unexpected outputs. The implementation converts only the explicit `approve`
value to `True`. No tools are made available to the reviewer.

## Reproducibility and cost accounting

The default reviewer is the group's `glm-4.5-flash` model through the class
OpenAI-compatible Zhipu endpoint, with temperature zero, a 512-token output cap,
a 30-second timeout, and no automatic retries. These settings and the exact prompt
are recorded in the implementation. Temperature zero reduces sampling variability
but does not guarantee identical provider outputs. The reviewer model and prompt
should be held fixed when comparing approval policies and budget values.

Each review exposes the provider's input and output token counts, latency,
decision, explanation, and operational status. This supports a reviewer-component
cost breakdown separately from policy and agent inference. Missing usage is
recorded as unknown rather than zero. Token totals can be converted to money
using the prices applicable to the actual model and experiment date.

Diagnostics retain the provider-returned model ID, output finish reason, HTTP
status, and exception type when available. They exclude exception bodies. This
helps separate rate limits, incomplete outputs, and other provider errors from
valid semantic denials during failure analysis.

## Validation and limitations

Offline tests cover Boolean interface compliance, approvals and denials, allowed
evidence fields, malformed responses, missing credentials, oversized context,
provider failure, token accounting, and integration with the unchanged gate's
budget/reset logic. API and AgentDojo dependencies are replaced with test doubles
in those tests. Thus, these tests validate implementation behavior, not model
accuracy or resilience to adversarial prompts.

The reviewed implementation passes 22 offline tests, including regressions for
missing context, excessive nesting, malformed scalar metadata, safe HTTP error
diagnostics, and incomplete-response metadata. The original six-case live run is
retained as historical evidence; the review revision leaves the prompt and API
request settings unchanged and does not claim a second live evaluation.

An optional live check evaluates six synthetic scenarios: authorized read,
authorized write, incorrect recipient, injected tool-output instructions,
unrelated sensitive read, and ambiguous permanent deletion. A measured OpenRouter
GPT-4.1 mini run passed all six cases with JSON mode enabled, using 2,670 input
tokens and 282 output tokens. This is a small synthetic sanity check, not a
benchmark accuracy or general attack-resistance estimate.
Full AgentDojo evaluation should include both benign and attacked trajectories
and compare reviewer decisions with labels only after decisions are made.

LLM review is an approximation of human judgment and can share failure modes with
the agent or approval policy, particularly when using the same model family.
Prompt/data separation mitigates injection risk without guaranteeing resistance.
Fail-closed operational handling can reduce task completion independently of
semantic safety judgment. The character ceiling avoids silently removing evidence
but does not guarantee that every provider context window will fit the request.
Tool schemas are not currently supplied by the shared context, and the gate's
read-only heuristic and unset remote-resource flag limit metadata quality.
The current experiment runner reports plain-task utility; attack-aware evaluation
is still needed to establish safe TCR@k.

## Presentation notes

“My component simulates the human reviewer when our policy escalates a tool call.
It sees only information available at decision time: the task, exact call, and
preceding trace. It receives no attack labels or correct answers. The reviewer
checks whether the action, recipient, and side effects match the user's request.
It returns a strict approve-or-deny decision and a brief explanation. API failures
and invalid outputs cause denial. The gate handles the review budget separately.
We also record reviewer tokens so that its cost can be separated from the policy
and the agent. Our offline tests verify the implementation; actual safety and
task-completion performance must come from the group's benchmark experiments.”

### Why not approve every read?

A read can access unrelated sensitive data. Authorization depends on the task
and resource, not just the tool name.

### Why not use ground truth to simulate a perfect reviewer?

It would expose information unavailable to real reviewers and bias online
evaluation. Labels are appropriate for scoring after decisions, not as inputs.

### Why deny on errors?

An unavailable reviewer has not provided authorization. This choice is
conservative, and operational denials must be distinguished during analysis.
