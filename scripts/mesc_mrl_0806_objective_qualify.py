#!/usr/bin/env python3
"""Produce or independently verify exact MRL-0806 RQ1 objective/budget evidence.

The entrypoint requires a clean exact-main checkout, live owner Issue authority, exact
committed artifact/source bindings, and an external evidence output directory. It never
loads a model, activates a GPU, trains, mutates weights, or mutates production trust.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final, cast

sys.dont_write_bytecode = True

_MODULE: Final = Path("src/medscale/mesc/_mrl_0806_objective_budgets_v1.py")
_AUTH: Final = Path("specs/mesc-experiment-0/mrl-0806-objective-budgets-authorization-v1.json")
_OBJECTIVE: Final = Path("specs/mesc-experiment-0/mrl-0806-rq1-objective-v1.json")
_PROTOCOL: Final = Path("specs/mesc-experiment-0/mrl-0806-rq1-protocol-v1.json")
_SCRIPT: Final = Path("scripts/mesc_mrl_0806_objective_qualify.py")
_EXPECTED_ISSUE: Final = 421
_EXPECTED_NODE: Final = "I_kwDOTT9yMs8AAAABRUhTcw"
_EXPECTED_CREATED: Final = "2026-09-15T04:02:23Z"
_EXPECTED_BODY_SHA256: Final = "7966dffba307488c5ce51e67573103084c47453aafccbb66886ff54243a225c0"
_EXPECTED_OWNER: Final = "TheHalfMoon"
_EXPECTED_BASE: Final = "1653fe9e26aeb2f52f48afdfdc8d9c3f133fec91"
_EXPECTED_OBJECTIVE_SHA256: Final = (
    "53149a0966e88eaa0c584f3f115e624444a8e479fc4bb45adf5ce727d18ed621"
)
_EXPECTED_PROTOCOL_SHA256: Final = (
    "8a2601a76077413d65c42ff68a65f118f7479350952b4b3e45785593ae11e494"
)
_OUTPUTS: Final = {
    "receipt": "objective-budget-freeze-receipt.json",
    "evidence": "mrl-0806-real-preflight-evidence.json",
}
_PREDECESSOR_PATHS: Final = {
    "MRL-0801": Path("specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0801.json"),
    "MRL-0802": Path("specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0802.json"),
    "MRL-0803": Path("specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0803.json"),
    "MRL-0804": Path("specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0804.json"),
    "MRL-0805": Path("specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0805.json"),
    "MRL-0807": Path("specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0807.json"),
}
_FROZEN_PATHS: Final = {
    "candidate_roster_sha256": Path("specs/mesc-experiment-0/candidate-roster-v1.json"),
    "evaluation_contract_sha256": Path(
        "specs/mesc-experiment-0/mrl-0807-rq1-evaluation-contract-v1.json"
    ),
    "evaluator_identity_sha256": Path(
        "specs/mesc-experiment-0/mrl-0807-evaluator-identity-v1.json"
    ),
    "sealed_tier3_identity_sha256": Path(
        "specs/mesc-experiment-0/mrl-0807-sealed-tier3-identity-v1.json"
    ),
    "research_objective_sha256": _OBJECTIVE,
    "rq1_protocol_sha256": _PROTOCOL,
}


class EntrypointError(RuntimeError):
    """Raised when exact-source or live-authority validation fails closed."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    return parser


def _run(arguments: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _git(root: Path, *args: str) -> str:
    completed = _run(["git", "-C", str(root), *args])
    if completed.returncode != 0:
        raise EntrypointError("repository Git identity cannot be resolved")
    return completed.stdout.strip()


def _live_remote_main(root: Path) -> str:
    completed = _run(["git", "-C", str(root), "ls-remote", "--heads", "origin", "refs/heads/main"])
    if completed.returncode != 0:
        raise EntrypointError("live remote main identity cannot be resolved")
    lines = [line for line in completed.stdout.splitlines() if line]
    if len(lines) != 1:
        raise EntrypointError("live remote main response is ambiguous")
    fields = lines[0].split("\t")
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise EntrypointError("live remote main response is malformed")
    sha = fields[0]
    if len(sha) != 40 or any(character not in "0123456789abcdef" for character in sha):
        raise EntrypointError("live remote main SHA is malformed")
    return sha


def _require_clean_repository(root: Path) -> tuple[Path, str, str]:
    repository = root.expanduser().resolve(strict=True)
    if Path(_git(repository, "rev-parse", "--show-toplevel")).resolve(strict=True) != repository:
        raise EntrypointError("repository_root is not the exact Git work-tree root")
    if _git(repository, "status", "--porcelain", "--untracked-files=all"):
        raise EntrypointError("repository work tree must be clean")
    if _git(repository, "clean", "-ndx"):
        raise EntrypointError("repository must contain no ignored or untracked state")
    head = _git(repository, "rev-parse", "HEAD")
    tree = _git(repository, "rev-parse", "HEAD^{tree}")
    if head != _live_remote_main(repository):
        raise EntrypointError("repository HEAD must equal live remote main")
    ancestry = _run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            _EXPECTED_BASE,
            head,
        ]
    )
    if ancestry.returncode != 0:
        raise EntrypointError("repository HEAD is outside the authorized predecessor lineage")
    for relative in (_MODULE, _AUTH, _OBJECTIVE, _PROTOCOL, _SCRIPT):
        candidate = repository / relative
        if candidate.is_symlink():
            raise EntrypointError(f"required source is not a regular file: {relative.as_posix()}")
        path = candidate.resolve(strict=True)
        if not path.is_file():
            raise EntrypointError(f"required source is not a regular file: {relative.as_posix()}")
        shown = subprocess.run(
            ["git", "-C", str(repository), "show", f"HEAD:{relative.as_posix()}"],
            check=False,
            capture_output=True,
        )
        if shown.returncode != 0 or shown.stdout != path.read_bytes():
            raise EntrypointError(f"repository bytes differ from exact HEAD: {relative.as_posix()}")
    return repository, head, tree


def _strict_object(raw: str, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EntrypointError(f"{label} is not JSON") from exc
    if type(value) is not dict:
        raise EntrypointError(f"{label} must be one object")
    return cast(dict[str, object], value)


def _require_live_issue() -> None:
    completed = _run(["gh", "api", f"repos/TheHalfMoon/MESC/issues/{_EXPECTED_ISSUE}"])
    if completed.returncode != 0:
        raise EntrypointError("live MRL-0806 authority issue cannot be fetched")
    issue = _strict_object(completed.stdout, label="live authority issue")
    author = issue.get("user")
    if type(author) is not dict:
        raise EntrypointError("live authority issue author is malformed")
    if issue.get("number") != _EXPECTED_ISSUE or issue.get("node_id") != _EXPECTED_NODE:
        raise EntrypointError("live authority issue identity drifted")
    if author.get("login") != _EXPECTED_OWNER or issue.get("author_association") != "OWNER":
        raise EntrypointError("live authority issue is not repository-owner authority")
    if issue.get("created_at") != _EXPECTED_CREATED or issue.get("state") != "open":
        raise EntrypointError("live authority issue state/creation identity drifted")
    body = issue.get("body")
    if type(body) is not str or hashlib.sha256(body.encode()).hexdigest() != _EXPECTED_BODY_SHA256:
        raise EntrypointError("live authority issue body digest drifted")


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EntrypointError(f"{label} cannot be read") from exc
    if type(value) is not dict:
        raise EntrypointError(f"{label} must be one object")
    return cast(dict[str, object], value)


def _require_committed_bindings(repository: Path) -> None:
    authorization = _read_json(repository / _AUTH, label="authorization")
    predecessor = authorization.get("predecessor_evidence")
    if type(predecessor) is not dict:
        raise EntrypointError("authorization predecessor_evidence is malformed")
    for task_id, relative in _PREDECESSOR_PATHS.items():
        actual = hashlib.sha256((repository / relative).read_bytes()).hexdigest()
        if predecessor.get(task_id) != actual:
            raise EntrypointError(f"{task_id} predecessor evidence binding drifted")
    frozen = authorization.get("frozen_artifacts")
    if type(frozen) is not dict:
        raise EntrypointError("authorization frozen_artifacts is malformed")
    for field_name, relative in _FROZEN_PATHS.items():
        actual = hashlib.sha256((repository / relative).read_bytes()).hexdigest()
        if frozen.get(field_name) != actual:
            raise EntrypointError(f"{field_name} committed binding drifted")
    if frozen.get("research_objective_sha256") != _EXPECTED_OBJECTIVE_SHA256:
        raise EntrypointError("research objective authority digest drifted")
    if frozen.get("rq1_protocol_sha256") != _EXPECTED_PROTOCOL_SHA256:
        raise EntrypointError("RQ1 protocol authority digest drifted")


def _load_module(repository: Path) -> ModuleType:
    for name in tuple(sys.modules):
        if name == "medscale" or name.startswith("medscale."):
            del sys.modules[name]
    sys.path.insert(0, str((repository / "src").resolve(strict=True)))
    module = importlib.import_module("medscale.mesc._mrl_0806_objective_budgets_v1")
    module_file = getattr(module, "__file__", None)
    if type(module_file) is not str or Path(module_file).resolve(strict=True) != (
        repository / _MODULE
    ).resolve(strict=True):
        raise EntrypointError("MRL-0806 qualifier imported from non-canonical source")
    return module


def _require_output_root(path: Path, repository: Path, *, verify_existing: bool) -> Path:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise EntrypointError("output_root must be an existing non-symlink directory")
    output = candidate.resolve(strict=True)
    if not output.is_dir():
        raise EntrypointError("output_root must be an existing non-symlink directory")
    try:
        output.relative_to(repository)
    except ValueError:
        pass
    else:
        raise EntrypointError("output_root must remain outside the repository")
    entries = tuple(output.iterdir())
    if verify_existing:
        if {entry.name for entry in entries} != set(_OUTPUTS.values()):
            raise EntrypointError(
                "verification output_root must contain exactly expected artifacts"
            )
        if any(entry.is_symlink() or not entry.is_file() for entry in entries):
            raise EntrypointError("verification artifacts must be regular non-symlink files")
    elif entries:
        raise EntrypointError("production output_root must be empty")
    return output


def _main() -> int:
    args = _parser().parse_args()
    repository, head, tree = _require_clean_repository(args.repository_root)
    _require_live_issue()
    _require_committed_bindings(repository)
    output = _require_output_root(
        args.output_root, repository, verify_existing=args.verify_existing
    )
    module = _load_module(repository)
    inputs = (
        (repository / _AUTH).read_bytes(),
        (repository / _OBJECTIVE).read_bytes(),
        (repository / _PROTOCOL).read_bytes(),
    )
    if args.verify_existing:
        result = module.verify_mrl_0806_bundle(
            *inputs,
            repository_sha=head,
            repository_tree=tree,
            freeze_receipt_bytes=(output / _OUTPUTS["receipt"]).read_bytes(),
            evidence_bytes=(output / _OUTPUTS["evidence"]).read_bytes(),
        )
    else:
        result = module.qualify_mrl_0806_objective_budgets(
            *inputs,
            repository_sha=head,
            repository_tree=tree,
        )
        (output / _OUTPUTS["receipt"]).write_bytes(result.freeze_receipt_bytes)
        (output / _OUTPUTS["evidence"]).write_bytes(result.evidence_bytes)
    print(f"MRL0806_OBJECTIVE_EVIDENCE_SHA256={result.evidence_sha256}")
    print(f"MRL0806_FREEZE_RECEIPT_SHA256={result.freeze_receipt_sha256}")
    print(f"MRL0806_RESEARCH_OBJECTIVE_SHA256={result.research_objective_sha256}")
    print(f"MRL0806_RQ1_PROTOCOL_SHA256={result.rq1_protocol_sha256}")
    print(f"MRL0806_REPOSITORY_SHA={head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
