from __future__ import annotations

import csv
import unicodedata
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .manifest import APPLY_ACTIONS, read_manifest, target_for_row, validate_manifest
from .models import ApplyRecord
from .paths import resolve_input_path, safe_rel


def top_level_rows(rows: list[dict[str, str]], root: Path, *, allow_absolute: bool = False) -> list[dict[str, str]]:
    selected: list[tuple[Path, dict[str, str]]] = []
    for row in sorted(rows, key=lambda item: len(Path(item.get("source_path", "")).parts)):
        source = resolve_input_path(root, row.get("source_path", ""), allow_absolute=allow_absolute)
        if any(is_child_of(source, existing_source) for existing_source, _ in selected):
            continue
        selected.append((source, row))
    return [row for _, row in selected]


def is_child_of(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return path.resolve() != parent.resolve()


def path_identity(path: Path) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in path.resolve().parts)


def paths_overlap(first: Path, second: Path) -> bool:
    first_parts = path_identity(first)
    second_parts = path_identity(second)
    shared_length = min(len(first_parts), len(second_parts))
    return first_parts[:shared_length] == second_parts[:shared_length]


def apply_manifest(
    manifest_path: Path,
    root: Path,
    *,
    execute: bool = False,
    undo_out: Path | None = None,
    allow_ready_to_apply: bool = False,
    allow_absolute: bool = False,
) -> list[ApplyRecord]:
    errors, _warnings = validate_manifest(
        manifest_path,
        root,
        require_existing=True,
        allow_absolute=allow_absolute,
        allow_ready_to_apply=allow_ready_to_apply,
    )
    if errors:
        raise ValueError("\n".join(errors))
    rows = [
        row
        for row in read_manifest(manifest_path)
        if row.get("action") in APPLY_ACTIONS
        and (row.get("gate") == "approved" or (allow_ready_to_apply and row.get("gate") == "ready_to_apply"))
    ]
    rows = top_level_rows(rows, root, allow_absolute=allow_absolute)
    records: list[ApplyRecord] = []
    undo_rows: list[dict[str, str]] = []
    for row in rows:
        source = resolve_input_path(root, row["source_path"], allow_absolute=allow_absolute)
        target = target_for_row(root, row, source, allow_absolute=allow_absolute)
        action = "rename" if source.parent == target.parent else "move"
        if execute:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            status = "applied"
            undo_rows.append(
                {
                    "current_path": safe_rel(target, root),
                    "original_path": safe_rel(source, root),
                    "action": action,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
            )
        else:
            status = "would_apply"
        records.append(ApplyRecord(safe_rel(source, root), safe_rel(target, root), action, status, row.get("reason", "")))

    if execute and undo_rows:
        undo_path = undo_out or (manifest_path.parent / "undo.tsv")
        write_undo_manifest(undo_path, undo_rows)
    return records


def undo_manifest(
    undo_path: Path,
    root: Path,
    *,
    execute: bool = False,
    allow_absolute: bool = False,
) -> list[ApplyRecord]:
    rows = read_tsv(undo_path)
    plan = plan_undo(rows, root, allow_absolute=allow_absolute)
    records: list[ApplyRecord] = []
    for current, original in plan:
        if execute:
            original.parent.mkdir(parents=True, exist_ok=True)
            current.rename(original)
            status = "undone"
        else:
            status = "would_undo"
        records.append(ApplyRecord(safe_rel(current, root), safe_rel(original, root), "undo", status, "undo manifest row"))
    return records


def plan_undo(
    rows: list[dict[str, str]],
    root: Path,
    *,
    allow_absolute: bool = False,
) -> list[tuple[Path, Path]]:
    if not rows:
        raise ValueError("undo manifest has no data rows")

    errors: list[str] = []
    plan: list[tuple[Path, Path]] = []
    current_rows: dict[tuple[str, ...], tuple[Path, int]] = {}
    original_rows: dict[tuple[str, ...], tuple[Path, int]] = {}
    for index, row in enumerate(rows, start=2):
        current_value = (row.get("current_path") or "").strip()
        original_value = (row.get("original_path") or "").strip()
        if not current_value:
            errors.append(f"row {index}: missing undo column: current_path")
        if not original_value:
            errors.append(f"row {index}: missing undo column: original_path")
        if not current_value or not original_value:
            continue
        try:
            current = resolve_input_path(root, current_value, allow_absolute=allow_absolute)
            original = resolve_input_path(root, original_value, allow_absolute=allow_absolute)
        except ValueError as exc:
            errors.append(f"row {index}: {exc}")
            continue

        if not current.exists():
            errors.append(f"row {index}: current path does not exist: {current_value}")
        if original.exists():
            errors.append(f"row {index}: original path already exists: {original_value}")
        current_key = path_identity(current)
        original_key = path_identity(original)
        if current_key in current_rows:
            errors.append(
                f"row {index}: duplicate current path also used by row {current_rows[current_key][1]}"
            )
        if original_key in original_rows:
            errors.append(
                f"row {index}: duplicate original path also used by row {original_rows[original_key][1]}"
            )
        for previous_current, previous_index in current_rows.values():
            if current_key != path_identity(previous_current) and paths_overlap(
                current, previous_current
            ):
                errors.append(
                    f"row {index}: current path overlaps row {previous_index}: {current_value}"
                )
                break
        for previous_original, previous_index in original_rows.values():
            if original_key != path_identity(previous_original) and paths_overlap(
                original, previous_original
            ):
                errors.append(
                    f"row {index}: original path overlaps row {previous_index}: {original_value}"
                )
                break
        for previous_current, previous_index in current_rows.values():
            if paths_overlap(original, previous_current):
                errors.append(
                    f"row {index}: original path overlaps current path from row {previous_index}"
                )
                break
        for previous_original, previous_index in original_rows.values():
            if paths_overlap(current, previous_original):
                errors.append(
                    f"row {index}: current path overlaps original path from row {previous_index}"
                )
                break
        if paths_overlap(current, original):
            errors.append(f"row {index}: current and original paths overlap")

        current_rows[current_key] = (current, index)
        original_rows[original_key] = (original, index)
        plan.append((current, original))

    if errors:
        raise ValueError("\n".join(errors))
    return plan


def write_undo_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["current_path", "original_path", "action", "timestamp"], delimiter="\t")
        writer.writeheader()
        for row in reversed(rows):
            writer.writerow(row)


def write_records(path: Path, records: list[ApplyRecord]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ApplyRecord.__dataclass_fields__), delimiter="\t")
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))
