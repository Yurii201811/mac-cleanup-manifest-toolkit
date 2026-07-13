from __future__ import annotations

from pathlib import Path

import pytest

from mac_cleanup_manifest.executor import apply_manifest, undo_manifest
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
