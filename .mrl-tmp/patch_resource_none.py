from pathlib import Path

source = Path("src/medscale/mesc/_mrl_research_experiment_plan_v1.py")
tests = Path("tests/test_mesc_mrl_research_experiment_plan_v1.py")

source_text = source.read_text(encoding="utf-8")
tests_text = tests.read_text(encoding="utf-8")

old = '''        if planned is None:\n            continue\n        if planned > allowed:\n'''
new = '''        if planned is None:\n            raise ResearchExperimentPlanError(\n                f"resource_ceiling {name} cannot be not applicable when the frozen "\n                "objective defines a numeric ceiling"\n            )\n        if planned > allowed:\n'''
if source_text.count(old) != 1:
    raise SystemExit("resource subset insertion point mismatch")
source_text = source_text.replace(old, new, 1)

anchor = '''\n\ndef test_expected_manifest_rq_refs_must_fit_objective() -> None:\n'''
new_test = '''\n\n@pytest.mark.parametrize(\n    "resource_name",\n    [\n        "compute_seconds",\n        "input_tokens",\n        "generated_tokens",\n        "monetary_cost_microunits",\n        "evaluator_invocations",\n    ],\n)\ndef test_applicable_objective_resource_cannot_be_dropped_from_plan(\n    resource_name: str,\n) -> None:\n    plan = _plan()\n    if resource_name == "compute_seconds":\n        ceiling = replace(plan.resource_ceiling, compute_seconds=None)\n    elif resource_name == "input_tokens":\n        ceiling = replace(plan.resource_ceiling, input_tokens=None)\n    elif resource_name == "generated_tokens":\n        ceiling = replace(plan.resource_ceiling, generated_tokens=None)\n    elif resource_name == "monetary_cost_microunits":\n        ceiling = replace(plan.resource_ceiling, monetary_cost_microunits=None)\n    elif resource_name == "evaluator_invocations":\n        ceiling = replace(plan.resource_ceiling, evaluator_invocations=None)\n    else:\n        raise AssertionError(f"unhandled resource field: {resource_name}")\n\n    with pytest.raises(\n        ResearchExperimentPlanError,\n        match=rf"resource_ceiling {resource_name} cannot be not applicable",\n    ):\n        replace(plan, resource_ceiling=ceiling)\n'''
if tests_text.count(anchor) != 1:
    raise SystemExit("resource regression insertion point mismatch")
tests_text = tests_text.replace(anchor, new_test + anchor, 1)

source.write_text(source_text, encoding="utf-8")
tests.write_text(tests_text, encoding="utf-8")
