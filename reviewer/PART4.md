# Part 4 simulated human reviewer

This contribution replaces the always-approve placeholder when selected by
module name. It adds `reviewer.llm_reviewer.reviewer(call, ctx) -> bool` and does
not change the shared interface, gate, policy modules, or experiment runner.

## Files

- `llm_reviewer.py`: implementation, fixed prompt, strict output parser, and token accounting.
- `test_llm_reviewer.py`: offline unit and gate integration tests.
- `test_agentdojo_context.py`: optional tests using real AgentDojo types.
- `smoke_test.py`: six optional real-model synthetic checks.
- `PART4_REPORT.md`: English report section and presentation notes.
- `LIVE_VALIDATION.md` and `live_validation.json`: measured synthetic live results.
- `AGENTDOJO_VALIDATION.md` and `agentdojo_validation.json`: native integration results.

## Run offline checks

From the repository root:

```powershell
python -m unittest reviewer.test_agentdojo_context reviewer.test_llm_reviewer -v
```

The offline tests replace the API and AgentDojo dependencies with test doubles.
When the OpenAI SDK is installed, one additional test exercises its real request
serialization with an in-memory HTTP transport and no network access.
They verify the interface, evidence boundary, request structure, parser, failure
behavior, token accounting, and the unchanged gate's actual budget logic.
They do not measure the model's judgment quality. There are 24 dependency-free
tests and two optional native-type tests. The latter skip if AgentDojo is absent;
all 26 passed inside the actual AgentDojo environment.

## Run with the group's environment

Use the existing AgentDojo environment described in the root README. The reviewer
uses its OpenAI-compatible client dependency; no additional package is required.

```powershell
.\ad-env\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
$env:OPENAI_COMPATIBLE_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
# Set OPENAI_COMPATIBLE_API_KEY locally, as described in the root README.
$env:REVIEWER_MODEL = "glm-4.5-flash"

# Optional six-call live check, using synthetic data only:
python -m reviewer.smoke_test --live --out runs/reviewer_smoke.json

# Integration benchmark: full-escalate forces the reviewer path to be exercised.
python run_experiment.py --policy policies.full_escalate_policy --reviewer reviewer.llm_reviewer --k 3 --tasks user_task_0,user_task_1
```

When Part 3's policy is ready, replace `policies.full_escalate_policy` with its
module name. The stub policy can auto-approve read calls without exercising the
reviewer; use full-escalate for initial reviewer integration checks.

## Configuration

| Variable | Default / fallback | Purpose |
|---|---|---|
| `REVIEWER_API_KEY` | `OPENAI_COMPATIBLE_API_KEY` | Reviewer credentials |
| `REVIEWER_BASE_URL` | `OPENAI_COMPATIBLE_BASE_URL`, then the class Zhipu endpoint | Compatible API endpoint |
| `REVIEWER_MODEL` | `glm-4.5-flash` | Fixed reviewer model for comparisons |
| `REVIEWER_TIMEOUT_SECONDS` | `30` | Request timeout |
| `REVIEWER_MAX_TOKENS` | `512` | Output token ceiling |
| `REVIEWER_MAX_CONTEXT_CHARS` | `100000` | Evidence character ceiling, not a token limit |
| `REVIEWER_JSON_MODE` | `0` | Set `1` for providers supporting JSON-object output |

For OpenRouter, use the same reviewer with explicit provider configuration:

```powershell
$env:REVIEWER_BASE_URL = "https://openrouter.ai/api/v1"
$env:REVIEWER_MODEL = "openai/gpt-4.1-mini"
$env:REVIEWER_JSON_MODE = "1"
# Set REVIEWER_API_KEY locally; never put it in a committed file.
python -m reviewer.smoke_test --live --out runs/reviewer_openrouter_smoke.json
```

Model availability can change. Use a fixed available model, record its ID, and
hold it constant across comparisons. The example above is distinct from the
class Zhipu model and must not be reported as a GLM evaluation.

Missing credentials, unsupported input, oversized evidence, API errors, incomplete
responses, and invalid JSON all return `False`. Evidence is never silently
truncated. The gate still counts an attempted review against `k` on these errors;
its existing behavior is unchanged. Automatic API retries are disabled, so one
review makes at most one request.

## Evidence and prompt design

The reviewer only serializes task description, proposed tool name and arguments,
the two metadata flags, and the visible conversation's roles, text, tool calls,
tool results, and errors. It supports AgentDojo FunctionCall objects and text
content blocks. Native AgentDojo blocks use `content` while OpenAI-style blocks
use `text`; both are normalized to visible text in the evidence envelope. Blocks
with conflicting values are denied. Additional context attributes, arbitrary message metadata, and
the original `call` object's extra fields are not serialized. Unsupported content
fails closed instead of being removed from the trace.

Metadata flags must be Boolean or null. Tool-call IDs and tool error fields must
be text or null, preventing arbitrary nested metadata from entering through those
scalar fields. JSON container nesting is limited to 64 levels before serialization;
missing context fields and excessive nesting cause denial before any API request.

The caller must keep oracle labels out of visible text and tool arguments too:
an allowlist cannot determine whether arbitrary text contains hidden annotations.
The current gate's context construction is the source of these visible fields.

The prompt asks for an independent decision based on authorization, purpose,
exact targets, scope, and consequences. Tool output and assistant claims do not
grant authority. Historical messages are quoted inside one JSON evidence message;
they cannot become top-level reviewer system messages. The model can still be
susceptible to prompt injection; this structure is a mitigation, not a guarantee.
Both reads and writes are judged by context. Missing material evidence means deny.
The only accepted response schema is:

```json
{"decision": "approve", "reason": "The exact action matches the user's request."}
```

Only `approve` and `deny` are accepted, with a nonempty short explanation. Extra
fields, duplicate keys, Markdown, missing decisions, and non-string decisions are
rejected. The gate receives an actual Boolean, not the truthiness of a string.

## Reviewer API cost and diagnostics

`review_with_details` returns the decision, status, brief explanation, model,
latency, and provider-reported prompt/completion/total token counts. Missing token
counts remain `None`. `reviewer` emits the same record through the module's INFO
logger, which experiments can enable without changing shared files:

Diagnostics also include `response_model` (the model returned by the provider),
`finish_reason`, and, for failures, `http_status` and `error_type`. Exception
bodies are not logged. These distinguish failures such as HTTP 429 rate limits
and output-length exhaustion from semantic deny decisions. A missing diagnostic
remains null; the requested model continues to be recorded as `model`.

```powershell
New-Item -ItemType Directory -Force runs | Out-Null
@'
import logging, runpy
logging.basicConfig(filename="runs/reviewer.log", level=logging.INFO, encoding="utf-8")
runpy.run_module("run_experiment", run_name="__main__")
'@ | python - --policy policies.full_escalate_policy --reviewer reviewer.llm_reviewer --k 3 --tasks user_task_0,user_task_1
```

Log messages contain `REVIEWER ` followed by JSON. Aggregate
token counts only across records for this component; account for policy and agent
tokens separately. Dollar cost requires the provider/model prices applicable to
the experiment. Never interpret missing usage as zero or fabricate dollar values.
The root runner does not yet aggregate reviewer costs automatically.

The log omits credentials and full traces, but explanations may mention evidence;
treat logs as experiment data. `runs/` is already ignored by Git.

## Verification status

All 26 checks pass in the actual AgentDojo environment (24 unit checks plus two
native-type integration checks). The original six-case live synthetic check passed with
OpenRouter `openai/gpt-4.1-mini` and JSON mode enabled; see `LIVE_VALIDATION.md`.
Three benign AgentDojo workspace tasks also pass after fixing native message
compatibility, including an authorized calendar write. See `AGENTDOJO_VALIDATION.md`.
Full suite and attack-aware results remain separate experimental work.
No TCR, HITL performance, or general attack-resistance result is claimed.
The original synthetic live records remain historical evidence rather than being
relabeled as a new run. The later native integration run has its own records,
source archive hash, and reviewer source hash.
The live smoke test compares six synthetic decisions externally; expected answers
are never included in reviewer prompts. It is a sanity check, not a benchmark.

The current shared runner has no injection mode. Its plain-task utility numbers
cannot establish safe TCR@k under attacks; Part 5 should evaluate attack trajectories
as well and distinguish operational denials from semantic reviewer denials.
