from pathlib import Path

source = Path("src/medscale/mesc/_mrl_research_experiment_plan_v1.py")
tests = Path("tests/test_mesc_mrl_research_experiment_plan_v1.py")

source_text = source.read_text(encoding="utf-8")
tests_text = tests.read_text(encoding="utf-8")

old = '''    missing_failures = tuple(\n        sorted(\n            condition.value\n            for condition in required_failures.difference(plan.failure_conditions)\n        )\n    )\n    if missing_failures:\n        raise ResearchExperimentPlanError(\n            "failure_conditions omit frozen objective requirements: "\n            + ", ".join(missing_failures)\n        )\n'''
new = old + '''\n    if (\n        controls.invalidation_rules\n        and PlanStopCondition.FAILURE_CONDITION_TRIGGERED not in plan.stop_conditions\n    ):\n        raise ResearchExperimentPlanError(\n            "stop_conditions must include FAILURE_CONDITION_TRIGGERED when the frozen "\n            "objective defines invalidation_rules"\n        )\n'''
if source_text.count(old) != 1:
    raise SystemExit("source insertion point mismatch")
source_text = source_text.replace(old, new, 1)

anchor = '''\n\ndef test_material_semantic_changes_change_plan_identity() -> None:\n'''
new_test = '''\n\ndef test_objective_invalidation_rules_require_failure_triggered_stop() -> None:\n    plan = _plan()\n    assert plan.objective.adaptive_evaluation_controls.invalidation_rules\n    reduced = tuple(\n        condition\n        for condition in plan.stop_conditions\n        if condition is not PlanStopCondition.FAILURE_CONDITION_TRIGGERED\n    )\n\n    with pytest.raises(ResearchExperimentPlanError, match="FAILURE_CONDITION_TRIGGERED"):\n        replace(plan, stop_conditions=reduced)\n'''
if tests_text.count(anchor) != 1:
    raise SystemExit("test insertion point mismatch")
tests_text = tests_text.replace(anchor, new_test + anchor, 1)

source.write_text(source_text, encoding="utf-8")
tests.write_text(tests_text, encoding="utf-8")
