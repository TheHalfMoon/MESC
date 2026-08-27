from __future__ import annotations

from pathlib import Path

IMPL = Path("src/medscale/mesc/_mrl_research_objective_v1.py")
TEST = Path("tests/test_mesc_mrl_research_objective_v1.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


impl = IMPL.read_text(encoding="utf-8")
impl = replace_once(
    impl,
    """    monetary_cost_microunits: int | None\n    retries: int\n""",
    """    monetary_cost_microunits: int | None\n    max_experiments: int\n    retries: int\n""",
    "resource field",
)
impl = replace_once(
    impl,
    """        _require_optional_nonnegative_int(self.monetary_cost_microunits, \"monetary_cost_microunits\")\n        _require_nonnegative_int(self.retries, \"retries\")\n""",
    """        _require_optional_nonnegative_int(self.monetary_cost_microunits, \"monetary_cost_microunits\")\n        _require_nonnegative_int(self.max_experiments, \"max_experiments\")\n        _require_nonnegative_int(self.retries, \"retries\")\n""",
    "resource validation",
)
impl = replace_once(
    impl,
    """            \"monetary_cost_microunits\": self.monetary_cost_microunits,\n            \"retries\": self.retries,\n""",
    """            \"monetary_cost_microunits\": self.monetary_cost_microunits,\n            \"max_experiments\": self.max_experiments,\n            \"retries\": self.retries,\n""",
    "resource serialization",
)
impl = replace_once(
    impl,
    """        monetary_cost_microunits=value.monetary_cost_microunits,\n        retries=value.retries,\n""",
    """        monetary_cost_microunits=value.monetary_cost_microunits,\n        max_experiments=value.max_experiments,\n        retries=value.retries,\n""",
    "resource snapshot",
)
IMPL.write_text(impl, encoding="utf-8")


test = TEST.read_text(encoding="utf-8")
test = replace_once(
    test,
    """            monetary_cost_microunits=500_000,\n            retries=3,\n""",
    """            monetary_cost_microunits=500_000,\n            max_experiments=12,\n            retries=3,\n""",
    "fixture resource budget",
)
test = replace_once(
    test,
    """        lambda value: replace(\n            value,\n            resource_budget=replace(value.resource_budget, wall_clock_seconds=601),\n        ),\n        lambda value: replace(\n            value,\n            adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=4, tier_2_queries=0),\n        ),\n""",
    """        lambda value: replace(\n            value,\n            resource_budget=replace(value.resource_budget, wall_clock_seconds=601),\n        ),\n        lambda value: replace(\n            value,\n            resource_budget=replace(value.resource_budget, max_experiments=13),\n        ),\n        lambda value: replace(\n            value,\n            adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=4, tier_2_queries=0),\n        ),\n""",
    "identity sensitivity",
)
test = replace_once(
    test,
    """        (\"storage_bytes\", -1),\n        (\"retries\", -1),\n""",
    """        (\"storage_bytes\", -1),\n        (\"max_experiments\", -1),\n        (\"max_experiments\", True),\n        (\"retries\", -1),\n""",
    "invalid ceiling cases",
)
test = replace_once(
    test,
    """        \"monetary_cost_microunits\": 500_000,\n        \"retries\": 3,\n""",
    """        \"monetary_cost_microunits\": 500_000,\n        \"max_experiments\": 12,\n        \"retries\": 3,\n""",
    "resource kwargs",
)
test = replace_once(
    test,
    """def test_post_construction_nested_metric_mutation_rechecks_cross_field_invariants() -> None:\n""",
    """def test_post_construction_max_experiments_mutation_fails_closed_at_public_views() -> None:\n    objective = _objective()\n    object.__setattr__(objective.resource_budget, \"max_experiments\", -1)\n\n    with pytest.raises(ResearchObjectiveContractError, match=\"max_experiments must be a non-negative\"):\n        objective.semantic_dict()\n    with pytest.raises(ResearchObjectiveContractError, match=\"max_experiments must be a non-negative\"):\n        _ = objective.content_sha256\n    with pytest.raises(ResearchObjectiveContractError, match=\"max_experiments must be a non-negative\"):\n        objective.to_dict()\n\n\ndef test_post_construction_nested_metric_mutation_rechecks_cross_field_invariants() -> None:\n""",
    "forged maximum experiment ceiling",
)
TEST.write_text(test, encoding="utf-8")
