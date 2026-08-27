from pathlib import Path

path = Path("tests/test_mesc_mrl_research_experiment_plan_v1.py")
text = path.read_text(encoding="utf-8")

replacements = (
    (
        '            "tests/fixtures/mrl",\n',
        '            "tests/fixtures/mrl/candidates",\n',
        "objective mutation directory envelope",
    ),
    (
        '            "tests/fixtures/mrl/candidate.json",\n',
        '            "tests/fixtures/mrl/candidates/candidate.json",\n',
        "default plan mutation descendant",
    ),
    (
        '        mutation_surfaces=("tests/fixtures/mrl/deeper/candidate.json",),\n',
        '        mutation_surfaces=("tests/fixtures/mrl/candidates/deeper/candidate.json",),\n',
        "directory narrowing mutation descendant",
    ),
    (
        '    assert plan.mutation_surfaces == ("tests/fixtures/mrl/deeper/candidate.json",)\n',
        '    assert plan.mutation_surfaces == (\n        "tests/fixtures/mrl/candidates/deeper/candidate.json",\n    )\n',
        "directory narrowing assertion",
    ),
)

for old, new, label in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
