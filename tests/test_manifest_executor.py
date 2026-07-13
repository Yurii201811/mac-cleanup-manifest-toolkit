from __future__ import annotations

from pathlib import Path

import pytest

from mac_cleanup_manifest.executor import apply_manifest, undo_manifest, write_undo_manifest
from mac_cleanup_manifest.manifest import validate_manifest
from mac_cleanup_manifest.models import ProposalRow
from mac_cleanup_manifest.scanner import write_manifest


def test_validate_rejects_path_traversal(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.tsv"
    write_manifest(
        manifest,
        [
            ProposalRow(
                source_path="../outside.txt",
                action="move",
                destination="Filed",
                proposed_name="outside.txt",
                gate="approved",
                confidence="high",
                reason="bad path",
            )
        ],
    )

    errors, _warnings = validate_manifest(manifest, tmp_path)

    assert errors
    assert "path traversal" in errors[0]


def test_apply_and_undo_approved_move(tmp_path: Path) -> None:
    source = tmp_path / "loose.txt"
    source.write_text("hello", encoding="utf-8")
    manifest = tmp_path / "manifest.tsv"
    undo = tmp_path / "undo.tsv"
    write_manifest(
        manifest,
        [
            ProposalRow(
                source_path="loose.txt",
                action="move_rename",
                destination="Filed",
                proposed_name="clean-name.txt",
                gate="approved",
                confidence="high",
                reason="test move",
            )
        ],
    )

    dry_run = apply_manifest(manifest, tmp_path)
    assert dry_run[0].status == "would_apply"
    assert source.exists()

    applied = apply_manifest(manifest, tmp_path, execute=True, undo_out=undo)
    target = tmp_path / "Filed" / "clean-name.txt"
    assert applied[0].status == "applied"
    assert target.exists()
    assert undo.exists()

    undo_dry_run = undo_manifest(undo, tmp_path)
    assert undo_dry_run[0].status == "would_undo"
    undone = undo_manifest(undo, tmp_path, execute=True)
    assert undone[0].status == "undone"
    assert source.exists()
    assert not target.exists()


def test_apply_rejects_directory_target_inside_source_before_mutation(tmp_path: Path) -> None:
    source = tmp_path / "folder"
    source.mkdir()
    (source / "keep.txt").write_text("preserve me", encoding="utf-8")
    manifest = tmp_path / "manifest.tsv"
    write_manifest(
        manifest,
        [
            ProposalRow(
                source_path="folder",
                action="move",
                destination="folder/nested",
                proposed_name="folder",
                gate="approved",
                confidence="high",
                reason="invalid self-nesting move",
            )
        ],
    )

    errors, _warnings = validate_manifest(manifest, tmp_path)

    assert errors == ["row 2: target is inside source directory"]
    with pytest.raises(ValueError, match="target is inside source directory"):
        apply_manifest(manifest, tmp_path, execute=True)
    assert (source / "keep.txt").read_text(encoding="utf-8") == "preserve me"
    assert not (source / "nested").exists()


def test_undo_preflights_every_row_before_mutation(tmp_path: Path) -> None:
    moved = tmp_path / "Filed" / "valid.txt"
    moved.parent.mkdir()
    moved.write_text("preserve me", encoding="utf-8")
    undo = tmp_path / "undo.tsv"
    write_undo_manifest(
        undo,
        [
            {
                "current_path": "Filed/missing.txt",
                "original_path": "missing.txt",
                "action": "move",
                "timestamp": "2026-07-13T12:00:00",
            },
            {
                "current_path": "Filed/valid.txt",
                "original_path": "valid.txt",
                "action": "move",
                "timestamp": "2026-07-13T12:00:00",
            },
        ],
    )

    with pytest.raises(ValueError, match="current path does not exist: Filed/missing.txt"):
        undo_manifest(undo, tmp_path, execute=True)

    assert moved.read_text(encoding="utf-8") == "preserve me"
    assert not (tmp_path / "valid.txt").exists()


def test_undo_rejects_duplicate_targets_before_mutation(tmp_path: Path) -> None:
    first = tmp_path / "Filed" / "first.txt"
    second = tmp_path / "Filed" / "second.txt"
    first.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    undo = tmp_path / "undo.tsv"
    write_undo_manifest(
        undo,
        [
            {
                "current_path": "Filed/first.txt",
                "original_path": "restored.txt",
                "action": "move",
                "timestamp": "2026-07-13T12:00:00",
            },
            {
                "current_path": "Filed/second.txt",
                "original_path": "restored.txt",
                "action": "move",
                "timestamp": "2026-07-13T12:00:00",
            },
        ],
    )

    with pytest.raises(ValueError, match="duplicate original path"):
        undo_manifest(undo, tmp_path, execute=True)

    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"
    assert not (tmp_path / "restored.txt").exists()


@pytest.mark.parametrize(
    ("first_target", "second_target"),
    [
        ("Restored.txt", "restored.txt"),
        ("Résumé.txt", "Re\u0301sume\u0301.txt"),
    ],
)
def test_undo_rejects_apfs_equivalent_targets_before_mutation(
    tmp_path: Path, first_target: str, second_target: str
) -> None:
    first = tmp_path / "Filed" / "first.txt"
    second = tmp_path / "Filed" / "second.txt"
    first.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    undo = tmp_path / "undo.tsv"
    write_undo_manifest(
        undo,
        [
            {
                "current_path": "Filed/first.txt",
                "original_path": first_target,
                "action": "move",
                "timestamp": "2026-07-13T12:00:00",
            },
            {
                "current_path": "Filed/second.txt",
                "original_path": second_target,
                "action": "move",
                "timestamp": "2026-07-13T12:00:00",
            },
        ],
    )

    with pytest.raises(ValueError, match="duplicate original path"):
        undo_manifest(undo, tmp_path, execute=True)

    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_undo_rejects_cross_set_overlaps_before_mutation(
    tmp_path: Path, reverse_rows: bool
) -> None:
    container = tmp_path / "Filed" / "container"
    container.mkdir(parents=True)
    (container / "keep.txt").write_text("keep", encoding="utf-8")
    injected = tmp_path / "Filed" / "injected.txt"
    injected.write_text("inject", encoding="utf-8")
    rows = [
        {
            "current_path": "Filed/container",
            "original_path": "restored-container",
            "action": "move",
            "timestamp": "2026-07-13T12:00:00",
        },
        {
            "current_path": "Filed/injected.txt",
            "original_path": "Filed/container/injected.txt",
            "action": "move",
            "timestamp": "2026-07-13T12:00:00",
        },
    ]
    if reverse_rows:
        rows.reverse()
    undo = tmp_path / "undo.tsv"
    write_undo_manifest(undo, rows)

    with pytest.raises(ValueError, match="overlaps"):
        undo_manifest(undo, tmp_path, execute=True)

    assert (container / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert injected.read_text(encoding="utf-8") == "inject"
    assert not (tmp_path / "restored-container").exists()
