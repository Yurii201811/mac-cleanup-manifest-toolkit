from __future__ import annotations

import csv
import json
import os
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .models import ContextCard, ProposalRow
from .paths import (
    ARCHIVE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MEDIA_EXTENSIONS,
    TEXT_EXTENSIONS,
    clean_preview,
    default_destination_for,
    path_has_sensitive_name,
    safe_filename,
    safe_rel,
    should_skip_directory,
    slug_time,
)


def scan_root(root: Path, *, max_depth: int, include_hidden: bool, include_directories: bool) -> list[Path]:
    root = root.expanduser().resolve()
    items: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if (include_hidden or not name.startswith(".")) and not should_skip_directory(current_path / name)
        )
        if depth >= max_depth:
            dirnames[:] = []
        if current_path != root and include_directories:
            items.append(current_path)
        for name in sorted(filenames):
            if not include_hidden and name.startswith("."):
                continue
            items.append(current_path / name)
    return items


def inspect_item(path: Path, root: Path, *, preview_bytes: int) -> ContextCard:
    root = root.expanduser().resolve()
    rel = safe_rel(path, root)
    if path_has_sensitive_name(path):
        return ContextCard(
            rel,
            rel,
            "directory" if path.is_dir() else "file",
            path.suffix.lower(),
            None,
            None,
            "hold",
            "Sensitive-looking path; content was not inspected.",
            (),
        )
    try:
        stat = path.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        size_bytes: int | None = stat.st_size
    except OSError as exc:
        return ContextCard(rel, rel, "unknown", path.suffix.lower(), None, None, "error", "", (str(exc),))

    if path.is_dir():
        return inspect_directory(path, root, size_bytes=size_bytes, modified_at=modified_at, preview_bytes=preview_bytes)

    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return ContextCard(rel, rel, "file", suffix, size_bytes, modified_at, "text_preview", read_text_preview(path, preview_bytes), ())
    if suffix in DOCUMENT_EXTENSIONS:
        return ContextCard(rel, rel, "file", suffix, size_bytes, modified_at, "metadata_only", "", ())
    if suffix in IMAGE_EXTENSIONS:
        return ContextCard(rel, rel, "file", suffix, size_bytes, modified_at, "image_metadata", "", ())
    if suffix in MEDIA_EXTENSIONS:
        return ContextCard(rel, rel, "file", suffix, size_bytes, modified_at, "media_metadata", "", ())
    if suffix in ARCHIVE_EXTENSIONS:
        return ContextCard(rel, rel, "file", suffix, size_bytes, modified_at, "archive_listing", inspect_archive(path), ())
    return ContextCard(rel, rel, "file", suffix, size_bytes, modified_at, "metadata_only", "", ())


def inspect_directory(path: Path, root: Path, *, size_bytes: int, modified_at: str, preview_bytes: int) -> ContextCard:
    children: list[str] = []
    warnings: list[str] = []
    try:
        for child in sorted(path.iterdir(), key=lambda item: item.name.lower())[:40]:
            if should_skip_directory(child) or path_has_sensitive_name(child):
                children.append(f"{child.name}/ [held]")
            else:
                children.append(f"{child.name}/" if child.is_dir() else child.name)
    except OSError as exc:
        warnings.append(str(exc))
    readme_context = ""
    for readme_name in ("README.md", "README.txt", "AGENTS.md"):
        readme = path / readme_name
        if readme.exists() and readme.is_file() and not path_has_sensitive_name(readme):
            readme_context = f"\n\n{readme_name} preview:\n{read_text_preview(readme, preview_bytes // 2)}"
            break
    context = "Top-level children:\n" + "\n".join(f"- {name}" for name in children)
    return ContextCard(
        safe_rel(path, root),
        safe_rel(path, root),
        "directory",
        "",
        size_bytes,
        modified_at,
        "directory_listing",
        (context + readme_context).strip(),
        tuple(warnings),
    )


def read_text_preview(path: Path, limit: int) -> str:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return ""
    return clean_preview(data.decode("utf-8", errors="replace"))


def inspect_archive(path: Path) -> str:
    if path.suffix.lower() != ".zip":
        return ""
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()[:40]
    except (OSError, zipfile.BadZipFile) as exc:
        return f"Archive could not be listed: {exc}"
    return "Archive entries:\n" + "\n".join(f"- {name}" for name in names)


def deterministic_proposal(card: ContextCard) -> ProposalRow:
    path = Path(card.relative_path)
    name = path.name
    if card.inspection_status == "hold":
        return ProposalRow(card.relative_path, "hold", "Protected/Hold-For-Manual-Review", name, "hold", "high", "Sensitive-looking path; content was not inspected.")
    if name in {".DS_Store", ".localized"}:
        return ProposalRow(card.relative_path, "keep", ".", name, "no_apply", "high", "macOS metadata file; leave untouched.")
    destination, confidence, reason = default_destination_for(path, card.item_type)
    return ProposalRow(card.relative_path, "move", destination, name, "review", confidence, reason)


def write_run(root: Path, cards: list[ContextCard], rows: list[ProposalRow], out_root: Path) -> Path:
    run_dir = out_root.expanduser().resolve() / slug_time()
    cards_dir = run_dir / "context_cards"
    cards_dir.mkdir(parents=True, exist_ok=False)
    for index, card in enumerate(cards, start=1):
        card_path = cards_dir / f"{index:04d}_{safe_filename(Path(card.relative_path).name)}.json"
        card_path.write_text(json.dumps(asdict(card), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_manifest(run_dir / "manifest.tsv", rows)
    (run_dir / "manifest.json").write_text(json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(run_dir / "README.md", root, cards, rows)
    return run_dir


def write_manifest(path: Path, rows: list[ProposalRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ProposalRow.__dataclass_fields__), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_report(path: Path, root: Path, cards: list[ContextCard], rows: list[ProposalRow]) -> None:
    gate_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    for row in rows:
        gate_counts[row.gate] = gate_counts.get(row.gate, 0) + 1
        action_counts[row.action] = action_counts.get(row.action, 0) + 1
    lines = [
        "# Cleanup Proposal Run",
        "",
        f"- Root name: `{root.name}`",
        f"- Items inspected: `{len(cards)}`",
        "- Mode: proposal only; no files moved, renamed, or deleted.",
        "- Paths in manifests are relative to the selected root.",
        "",
        "## Gates",
        "",
        *[f"- `{key}`: {value}" for key, value in sorted(gate_counts.items())],
        "",
        "## Actions",
        "",
        *[f"- `{key}`: {value}" for key, value in sorted(action_counts.items())],
        "",
        "## Approval Boundary",
        "",
        "- Review `manifest.tsv` before any move.",
        "- Change only clearly approved rows to `gate=approved`.",
        "- Keep `hold`, `review`, and `no_apply` rows untouched.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
