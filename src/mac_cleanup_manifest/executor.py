from __future__ import annotations

import csv
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
    records: list[ApplyRecord] = []
    for index, row in enumerate(rows, start=2):
        try:
            current = resolve_input_path(root, row["current_path"], allow_absolute=allow_absolute)
            original = resolve_input_path(root, row["original_path"], allow_absolute=allow_absolute)
        except KeyError as exc:
            raise ValueError(f"row {index}: missing undo column: {exc}") from exc
        if not current.exists():
            raise ValueError(f"row {index}: current path does not exist: {row['current_path']}")
        if original.exists():
            raise ValueError(f"row {index}: original path already exists: {row['original_path']}")
        if execute:
            original.parent.mkdir(parents=True, exist_ok=True)
            current.rename(original)
            status = "undone"
        else:
            status = "would_undo"
        records.append(ApplyRecord(safe_rel(current, root), safe_rel(original, root), "undo", status, "undo manifest row"))
    return records


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
