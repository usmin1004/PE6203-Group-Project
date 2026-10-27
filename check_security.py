"""Sanity check: can AgentDojo's security check ever return True (= attack succeeded)?
No LLM, no API key. We run the ATTACKER's ground-truth calls on purpose, so security MUST be True.
"""
from agentdojo.agent_pipeline.ground_truth_pipeline import GroundTruthPipeline
from agentdojo.task_suite.load_suites import get_suite

suite = get_suite("v1.2.2", "workspace")
user_task = suite.get_user_task_by_id("user_task_0")

for i_id in ["injection_task_0", "injection_task_1", "injection_task_3"]:
    inj = suite.get_injection_task_by_id(i_id)
    pipe = GroundTruthPipeline(inj)  # pretend the agent did exactly what the attacker wants
    utility, security = suite.run_task_with_pipeline(pipe, user_task, inj, {})
    print(f"{i_id}: attack_succeeded={security}  (expected True)")
