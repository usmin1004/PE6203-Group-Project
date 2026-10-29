# Part 3 live validation

The JSON files in this directory contain actual model decisions and measured
benchmark results. `experiment_plan.json` fixes the planned subset and budgets.
`synthetic_live.json` contains eight hand-authored cases; its expected answers
are evaluation-side annotations and were not supplied to the policy model.

`run_validation.py` is a standalone harness that imports the team's unchanged
gate and reviewer. Run it from an isolated working directory, with credentials
in environment variables and AgentDojo installed:

```text
python /path/to/run_validation.py --repo /path/to/group-repo --out /path/to/results.json --mode attack --policy checklist_policy --k 3 --tasks user_task_0,user_task_1,user_task_6
```

Required variables: `OPENAI_COMPATIBLE_API_KEY` and
`OPENAI_COMPATIBLE_BASE_URL=https://openrouter.ai/api/v1`.
The recorded model is `openai/gpt-4.1-mini`, not GLM. The harness constructs
AgentDojo's native `OpenAILLM` with an explicit client, so the released package
does not need the group's unreleased `OPENAI_COMPATIBLE` model enum.

To reproduce the benign suite, set `--mode benign --tasks all --k 3`. To compare
policies, change `--policy` to `full_approve_policy` or `full_escalate_policy`.
Use separate output paths and working directories for each process. The
`*_traces` directories hold full AgentDojo trajectories with fictional benchmark
content; each result JSON adds the policy/reviewer decisions and component
usage. Reviewer requests are explicitly tagged; checklist HTTP usage is added
once to the same cost tracker, avoiding attribution to agent execution.

Run `analyze_results.py` after collecting results to regenerate `summary.json`
and `summary.csv`. Dollar amounts are undiscounted token-price estimates using
the timestamped OpenRouter catalog response in `model_pricing.json`. Cached-input
discounts and unknown usage can make these differ from actual charges.

Safe completion is a proxy defined as utility AND NOT the configured attack's
success signal. It does not establish that every unauthorized tool execution
has been detected. HITL totals over utility-successful and proxy-safe-successful
tasks are reported separately. The full-approve baseline is evaluated once and
reused across k because its behavior does not depend on k. Experiments use one
run per setting; the attack subset is not the full benchmark suite.
