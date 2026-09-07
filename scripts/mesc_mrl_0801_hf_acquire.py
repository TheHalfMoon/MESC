"""Run one authorized MRL-0801 public Hugging Face acquisition transaction."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_MODULE_RELATIVE_PATH = Path("src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py")
_AUTHORIZATION_RELATIVE_PATH = Path(
    "specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json"
)


class AcquisitionEntrypointError(RuntimeError):
    """Raised before importing repository code when execution identity is invalid."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire one exact MRL-0801 authorized public Hugging Face candidate."
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--custody-receipt-output", type=Path, required=True)
    parser.add_argument("--provenance-receipt-output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser


def _git(repository_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        raise AcquisitionEntrypointError("Git execution is unavailable") from None
    if completed.returncode != 0:
        raise AcquisitionEntrypointError("repository Git identity cannot be resolved")
    return completed.stdout.strip()


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError:
        raise AcquisitionEntrypointError("Git execution is unavailable") from None
    if completed.returncode != 0:
        raise AcquisitionEntrypointError("repository Git identity cannot be resolved")
    return completed.stdout


def _require_clean_repository_before_import(repository_root: Path) -> Path:
    root = repository_root.resolve(strict=True)
    if not (root / ".git").exists():
        raise AcquisitionEntrypointError("repository_root is not a Git work tree")
    top_level = Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if top_level != root:
        raise AcquisitionEntrypointError("repository_root is not the exact Git work-tree root")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise AcquisitionEntrypointError("repository work tree must be clean before acquisition")
    module_path = (root / _MODULE_RELATIVE_PATH).resolve(strict=True)
    if not module_path.is_file():
        raise AcquisitionEntrypointError("canonical acquisition executor source is missing")
    return root


def _require_module_file(module: ModuleType, expected: Path, *, label: str) -> None:
    module_file = getattr(module, "__file__", None)
    if type(module_file) is not str or Path(module_file).resolve(strict=True) != expected:
        raise AcquisitionEntrypointError(
            f"{label} must import from the exact checked-out repository source"
        )


def _require_no_preloaded_medscale_modules() -> None:
    preloaded = tuple(
        sorted(name for name in sys.modules if name == "medscale" or name.startswith("medscale."))
    )
    if preloaded:
        raise AcquisitionEntrypointError(
            "preloaded medscale modules are prohibited before exact-source acquisition import"
        )


def _require_loaded_medscale_modules_match_head(
    *, repository_root: Path, source_root: Path
) -> None:
    for name, module in tuple(sys.modules.items()):
        if name != "medscale" and not name.startswith("medscale."):
            continue
        if module is None:
            raise AcquisitionEntrypointError("loaded medscale module identity is unavailable")
        module_file = getattr(module, "__file__", None)
        if type(module_file) is not str:
            raise AcquisitionEntrypointError("loaded medscale module has no exact source file")
        try:
            resolved = Path(module_file).resolve(strict=True)
            relative_source = resolved.relative_to(source_root)
        except (OSError, ValueError):
            raise AcquisitionEntrypointError(
                "loaded medscale module is outside the exact checked-out repository source"
            ) from None
        repository_relative = Path("src") / relative_source
        committed = _git_bytes(
            repository_root,
            "show",
            f"HEAD:{repository_relative.as_posix()}",
        )
        if resolved.read_bytes() != committed:
            raise AcquisitionEntrypointError(
                "loaded medscale module bytes differ from the exact Git commit"
            )


def _import_exact_repository_modules(repository_root: Path) -> tuple[ModuleType, ModuleType]:
    source_root_path = (repository_root / "src").resolve(strict=True)
    source_root = str(source_root_path)
    _require_no_preloaded_medscale_modules()
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    try:
        custody = importlib.import_module("medscale.mesc._mrl_0801_acquisition_custody_v1")
        acquisition = importlib.import_module("medscale.mesc._mrl_0801_hf_acquisition_v1")
    except ImportError:
        raise AcquisitionEntrypointError(
            "repository acquisition modules could not be imported"
        ) from None
    expected_custody = (
        repository_root / "src/medscale/mesc/_mrl_0801_acquisition_custody_v1.py"
    ).resolve(strict=True)
    expected_acquisition = (repository_root / _MODULE_RELATIVE_PATH).resolve(strict=True)
    _require_module_file(custody, expected_custody, label="custody contract")
    _require_module_file(acquisition, expected_acquisition, label="acquisition executor")
    _require_loaded_medscale_modules_match_head(
        repository_root=repository_root,
        source_root=source_root_path,
    )
    return custody, acquisition


def _is_descendant(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_no_existing_symlink_components(path: Path, *, label: str) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise AcquisitionEntrypointError(f"{label} must not traverse a symbolic link")


def _require_external_new_output(
    *,
    path: Path,
    repository_root: Path,
    snapshot_root: Path,
) -> Path:
    repo = repository_root.resolve(strict=True)
    snapshot = snapshot_root.expanduser().absolute().resolve(strict=False)
    raw = path.expanduser().absolute()
    if raw == repo or _is_descendant(raw, repo):
        raise AcquisitionEntrypointError("receipt output must be outside the repository")
    if raw == snapshot or _is_descendant(raw, snapshot):
        raise AcquisitionEntrypointError("receipt output must be outside the raw snapshot root")
    _require_no_existing_symlink_components(raw, label="receipt output")
    value = raw.resolve(strict=False)
    if value == repo or _is_descendant(value, repo):
        raise AcquisitionEntrypointError("receipt output must be outside the repository")
    if value == snapshot or _is_descendant(value, snapshot):
        raise AcquisitionEntrypointError("receipt output must be outside the raw snapshot root")
    if value.exists():
        raise AcquisitionEntrypointError("receipt output must not already exist")
    value.parent.mkdir(parents=True, exist_ok=True)
    return value


def _write_exact_new(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    custody_output: Path | None = None
    provenance_output: Path | None = None
    try:
        repository_root = _require_clean_repository_before_import(args.repository_root)
        custody_module, acquisition_module = _import_exact_repository_modules(repository_root)
        authorization_path = (repository_root / _AUTHORIZATION_RELATIVE_PATH).resolve(strict=True)
        authorization = custody_module.parse_mrl_0801_acquisition_authorization(
            authorization_path.read_bytes()
        )
        custody_output_path = _require_external_new_output(
            path=args.custody_receipt_output,
            repository_root=repository_root,
            snapshot_root=args.destination,
        )
        provenance_output_path = _require_external_new_output(
            path=args.provenance_receipt_output,
            repository_root=repository_root,
            snapshot_root=args.destination,
        )
        custody_output = custody_output_path
        provenance_output = provenance_output_path
        if custody_output_path == provenance_output_path:
            raise AcquisitionEntrypointError("custody and provenance outputs must be distinct")

        def publish_receipts(custody_value: object, provenance_value: object) -> None:
            custody_bytes = getattr(custody_value, "canonical_bytes", None)
            provenance_bytes = getattr(provenance_value, "canonical_bytes", None)
            if type(custody_bytes) is not bytes or type(provenance_bytes) is not bytes:
                raise AcquisitionEntrypointError("executor returned non-canonical receipt values")
            _write_exact_new(custody_output_path, custody_bytes)
            _write_exact_new(provenance_output_path, provenance_bytes)

        custody, provenance = acquisition_module.acquire_mrl_0801_hf_candidate(
            authorization=authorization,
            transport=acquisition_module.UrllibHfPublicTransport(
                timeout_seconds=args.timeout_seconds
            ),
            repository_root=repository_root,
            destination=args.destination,
            model_id=args.model_id,
            revision=args.revision,
            finalizer=publish_receipts,
        )
        print(
            json.dumps(
                {
                    "artifact_identity_sha256": custody.artifact_identity_sha256,
                    "asset_custody_sha256": custody.asset_custody_sha256,
                    "model_id": custody.model_id,
                    "provenance_receipt_sha256": provenance.receipt_sha256,
                    "revision": custody.revision,
                    "weights_sha256": custody.weights_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (AcquisitionEntrypointError, ImportError, OSError, RuntimeError, ValueError):
        if custody_output is not None:
            custody_output.unlink(missing_ok=True)
        if provenance_output is not None:
            provenance_output.unlink(missing_ok=True)
        print(
            "MRL-0801 acquisition blocked: bounded acquisition requirements were not met",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
