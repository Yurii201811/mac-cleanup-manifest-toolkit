from __future__ import annotations

import csv
from pathlib import Path

from .paths import ensure_single_name, resolve_input_path


FIELDS = ["source_path", "action", "destination", "proposed_name", "gate", "confidence", "reason"]
APPLY_ACTIONS = {"move", "rename", "move_rename"}
ALL_ACTIONS = APPLY_ACTIONS | {"keep", "hold"}
ALL_GATES = {"review", "hold", "no_apply", "approved", "ready_to_apply"}


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [{key: (value or "") for key, value in row.items()} for row in reader]


def validate_manifest(
    manifest_path: Path,
    root: Path,
    *,
    require_existing: bool = True,
    allow_absolute: bool = False,
    allow_ready_to_apply: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_manifest(manifest_path)
    if not rows:
        errors.append("manifest has no data rows")
        return errors, warnings

    missing = [field for field in FIELDS if field not in rows[0]]
    if missing:
        errors.append(f"manifest is missing required columns: {', '.join(missing)}")
        return errors, warnings

    executable_targets: dict[Path, int] = {}
    for index, row in enumerate(rows, start=2):
        action = row.get("action", "").strip()
        gate = row.get("gate", "").strip()
        if action not in ALL_ACTIONS:
            errors.append(f"row {index}: unsupported action: {action}")
        if gate not in ALL_GATES:
            errors.append(f"row {index}: unsupported gate: {gate}")
        try:
            source = resolve_input_path(root, row.get("source_path", ""), allow_absolute=allow_absolute)
        except ValueError as exc:
            errors.append(f"row {index}: {exc}")
            continue
        if require_existing and not source.exists():
            errors.append(f"row {index}: source does not exist: {row.get('source_path', '')}")
        is_executable = action in APPLY_ACTIONS and gate == "approved"
        if action in APPLY_ACTIONS and gate == "ready_to_apply":
            if allow_ready_to_apply:
                is_executable = True
            else:
                warnings.append(f"row {index}: ready_to_apply row is not executable unless --allow-ready-to-apply is set")
        if gate == "approved" and action not in APPLY_ACTIONS:
            errors.append(f"row {index}: gate=approved is only valid for move, rename, or move_rename")
        if not is_executable:
            continue
        try:
            target = target_for_row(root, row, source, allow_absolute=allow_absolute)
        except ValueError as exc:
            errors.append(f"row {index}: {exc}")
            continue
        if target == source:
            errors.append(f"row {index}: target is the same as source")
        if target.exists():
            errors.append(f"row {index}: target already exists: {target.relative_to(root).as_posix()}")
        if target in executable_targets:
            errors.append(f"row {index}: duplicate target also used by row {executable_targets[target]}")
        executable_targets[target] = index
    return errors, warnings


def target_for_row(root: Path, row: dict[str, str], source: Path, *, allow_absolute: bool = False) -> Path:
    action = row.get("action", "").strip()
    proposed_name = row.get("proposed_name", "").strip() or source.name
    name = ensure_single_name(proposed_name)
    if action == "rename":
        destination_dir = source.parent
    else:
        destination_value = row.get("destination", ".").strip() or "."
        destination_dir = resolve_input_path(root, destination_value, allow_absolute=allow_absolute)
    return (destination_dir / name).resolve()
