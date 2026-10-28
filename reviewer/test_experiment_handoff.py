"""Offline handoff checks; native replay tests require AgentDojo and OpenAI."""
import contextlib
import importlib
import io
import json
import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reviewer import run_with_accounting as runner
from reviewer import llm_reviewer


class AccountingTests(unittest.TestCase):
    def test_unknown_usage_and_operational_denials_are_separate(self):
        records = [dict(status="ok", approved=False, prompt_tokens=10, completion_tokens=2, total_tokens=12),
                   dict(status="api_error", approved=False, prompt_tokens=None, completion_tokens=None, total_tokens=None)]
        result = runner.summarize(records)
        self.assertEqual(result["semantic_denials"], 1)
        self.assertEqual(result["operational_denials"], 1)
        self.assertEqual(result["total_tokens"], {"known_sum": 12, "unknown_reviews": 1})

    def test_partial_run_keeps_diagnostics_and_restores_logging(self):
        logger = logging.getLogger("reviewer.llm_reviewer")
        level, disabled = logger.level, logger.disabled
        def fail(*args, **kwargs):
            raise RuntimeError("private exception body")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "cost.json"
            with patch.object(runner.runpy, "run_module", side_effect=fail):
                with self.assertRaises(RuntimeError):
                    runner.main(["--mode", "replay", "--accounting-out", str(out)])
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(result["runner_completed"])
            self.assertEqual(result["error_type"], "RuntimeError")
            self.assertNotIn("private exception body", out.read_text(encoding="utf-8"))
        self.assertEqual((logger.level, logger.disabled), (level, disabled))

    def test_result_and_accounting_paths_must_differ(self):
        with tempfile.TemporaryDirectory() as directory:
            out = str(Path(directory) / "result.json")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.main(["--mode", "replay", "--accounting-out", out, "--out", out])

    def test_real_replay_gate_and_sdk_accounting_without_network(self):
        try:
            sdk = importlib.import_module("openai")
            import agentdojo
        except ImportError:
            self.skipTest("Install AgentDojo and OpenAI for the native replay check")
        http_name = next(c.__module__.split(".")[0] for c in sdk.DefaultHttpxClient.__mro__ if c.__name__ == "Client")
        http = importlib.import_module(http_name)
        from policies import cost_tracker
        import gate_patch
        from policies.full_escalate_policy import policy
        from agentdojo.task_suite.load_suites import get_suite
        suite = get_suite("v1.2.2", "workspace")
        env = suite.load_and_inject_default_environment(suite.get_injection_vector_defaults())
        user = suite.get_user_task_by_id("user_task_0")
        injection = suite.get_injection_task_by_id("injection_task_0")
        total_calls = len(user.ground_truth(env)) + len(injection.ground_truth(env))
        actual_factory = sdk.OpenAI
        requests = []
        def handle(request):
            requests.append(json.loads(request.content))
            return http.Response(200, json={
                "id": "offline-replay", "object": "chat.completion", "created": 0,
                "model": "offline-test-model", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"decision":"approve","reason":"Scripted transport fixture."}'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}})
        def factory(**kwargs):
            return actual_factory(http_client=sdk.DefaultHttpxClient(transport=http.MockTransport(handle)), **kwargs)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                "REVIEWER_API_KEY": "offline-test-key", "REVIEWER_BASE_URL": "https://example.invalid/v1",
                "REVIEWER_MODEL": "offline-test-model"}), \
                patch.object(gate_patch, "policy", policy), patch.object(gate_patch, "reviewer", llm_reviewer.reviewer), \
                patch.object(sdk, "OpenAI", side_effect=factory):
            for k in (0, 1, 3):
                requests.clear()
                result_path = Path(directory) / f"replay{k}.json"
                accounting_path = Path(directory) / f"cost{k}.json"
                with contextlib.redirect_stdout(io.StringIO()):
                    runner.main(["--mode", "replay", "--accounting-out", str(accounting_path),
                                 "--policy", "policies.full_escalate_policy", "--k", str(k),
                                 "--user-tasks", "user_task_0", "--injection-tasks", "injection_task_0",
                                 "--out", str(result_path)])
                result = json.loads(result_path.read_text(encoding="utf-8"))
                accounting = json.loads(accounting_path.read_text(encoding="utf-8"))
                n = min(k, total_calls)
                self.assertEqual(result["pairs"], 1)
                self.assertEqual(result["total_escalations"], n)
                self.assertEqual(len(requests), n)
                self.assertEqual(result["results"][0]["gate"]["budget_denials"], total_calls - n)
                self.assertEqual(accounting["reviewer_summary"]["review_attempts"], n)
                self.assertEqual(accounting["reviewer_summary"]["operational_denials"], 0)
                expected = {"reviewer": {"calls": n, "prompt_tokens": n * 11, "completion_tokens": n * 3}} if n else {}
                self.assertEqual(accounting["component_usage"], expected)
                if k == 3:
                    evidence = json.loads(requests[-1]["messages"][1]["content"])
                    self.assertIn(injection.GOAL, json.dumps(evidence, ensure_ascii=False))
                    self.assertEqual(set(evidence), {"task_description", "proposed_tool_call", "metadata", "conversation_history"})
                    self.assertEqual([m["role"] for m in requests[-1]["messages"]], ["system", "user"])
        cost_tracker.reset()


if __name__ == "__main__":
    unittest.main()
