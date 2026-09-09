#!/usr/bin/env python3
"""Run and qualify the exact authorized MRL-0802 Synthea FHIR corpus."""

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_MODULE = Path("src/medscale/mesc/_mrl_0802_synthea_fhir_v1.py")
_AUTH = Path("specs/mesc-experiment-0/mrl-0802-synthetic-fhir-corpus-authorization-v1.json")
_RIGHTS = Path("specs/mesc-experiment-0/mrl-0802-synthetic-fhir-rights-review-v1.json")


class EntrypointError(RuntimeError):
    """Raised when exact repository execution identity cannot be established."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--synthea-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _git_text(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise EntrypointError("repository Git identity cannot be resolved")
    return completed.stdout


def _git_bytes(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise EntrypointError("repository Git identity cannot be resolved")
    return completed.stdout


def _require_clean_repository(root: Path) -> Path:
    repository = root.resolve(strict=True)
    if not (repository / ".git").exists():
        raise EntrypointError("repository_root is not a Git work tree")
    top = Path(_git_text(repository, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    if top != repository:
        raise EntrypointError("repository_root is not the exact Git work-tree root")
    if _git_text(repository, "status", "--porcelain", "--untracked-files=all").strip():
        raise EntrypointError("repository work tree must be clean before corpus execution")
    for relative in (_MODULE, _AUTH, _RIGHTS):
        path = (repository / relative).resolve(strict=True)
        committed = _git_bytes(repository, "show", f"HEAD:{relative.as_posix()}")
        if path.read_bytes() != committed:
            raise EntrypointError(f"repository bytes differ from exact HEAD: {relative.as_posix()}")
    return repository


def _require_loaded_medscale_modules_match_head(repository: Path) -> None:
    source_root = (repository / "src").resolve(strict=True)
    for name, module in tuple(sys.modules.items()):
        if name != "medscale" and not name.startswith("medscale."):
            continue
        if module is None:
            raise EntrypointError("loaded medscale module identity is unavailable")
        module_file = getattr(module, "__file__", None)
        if type(module_file) is not str:
            raise EntrypointError("loaded medscale module has no exact source file")
        try:
            resolved = Path(module_file).resolve(strict=True)
            relative = resolved.relative_to(source_root)
        except (OSError, ValueError):
            raise EntrypointError(
                "loaded medscale module is outside the exact checked-out repository source"
            ) from None
        repository_relative = Path("src") / relative
        if resolved.read_bytes() != _git_bytes(
            repository, "show", f"HEAD:{repository_relative.as_posix()}"
        ):
            raise EntrypointError("loaded medscale module bytes differ from the exact Git commit")


def _load_module(repository: Path) -> ModuleType:
    for name in tuple(sys.modules):
        if name == "medscale" or name.startswith("medscale."):
            raise EntrypointError(
                "preloaded medscale modules are prohibited before exact-source import"
            )
    source_root = str((repository / "src").resolve(strict=True))
    sys.path[:] = [entry for entry in sys.path if entry != source_root]
    sys.path.insert(0, source_root)
    module = importlib.import_module("medscale.mesc._mrl_0802_synthea_fhir_v1")
    module_file = getattr(module, "__file__", None)
    expected = (repository / _MODULE).resolve(strict=True)
    if type(module_file) is not str or Path(module_file).resolve(strict=True) != expected:
        raise EntrypointError("MRL-0802 executor imported from a non-canonical source")
    _require_loaded_medscale_modules_match_head(repository)
    return module


def _write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repository = _require_clean_repository(args.repository_root)
        module = _load_module(repository)
        output_root = args.output_root.expanduser().resolve(strict=True)
        authorization = module.parse_mrl_0802_synthea_authorization(
            (repository / _AUTH).read_bytes()
        )
        rights_review = module.parse_mrl_0802_synthea_rights_review(
            (repository / _RIGHTS).read_bytes()
        )
        result = module.run_authorized_synthea_corpus(
            source_root=args.synthea_root,
            output_root=output_root,
            authorization=authorization,
            rights_review=rights_review,
            repository_root=repository,
        )
        evidence_root = output_root / "evidence"
        evidence_root.mkdir()
        _write_new(evidence_root / "corpus.jsonl", result.corpus_bytes)
        _write_new(evidence_root / "rights.json", result.rights_bytes)
        _write_new(evidence_root / "provenance.json", result.provenance_bytes)
        _write_new(evidence_root / "mrl-0802-real-preflight-evidence.json", result.evidence_bytes)
    except (EntrypointError, OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1

    print(f"corpus_sha256={result.corpus_sha256}")
    print(f"rights_evidence_sha256={result.rights_evidence_sha256}")
    print(f"provenance_sha256={result.provenance_sha256}")
    print(f"evidence_sha256={result.evidence_sha256}")
    print(f"raw_run_a_sha256={result.raw_run_a_sha256}")
    print(f"raw_run_b_sha256={result.raw_run_b_sha256}")
    print(f"record_count={len(result.record_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
