from __future__ import annotations

from pathlib import Path

from mac_cleanup_manifest.scanner import deterministic_proposal, inspect_item, scan_root


def test_sensitive_paths_are_held_without_preview(tmp_path: Path) -> None:
    secret = tmp_path / "session-token.txt"
    secret.write_text("do not include this preview", encoding="utf-8")

    card = inspect_item(secret, tmp_path, preview_bytes=200)
    proposal = deterministic_proposal(card)

    assert card.inspection_status == "hold"
    assert "do not include" not in card.extracted_context
    assert proposal.gate == "hold"


def test_scan_root_walks_files_in_order(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("beta", encoding="utf-8")

    found = scan_root(tmp_path, max_depth=2, include_hidden=False, include_directories=False)

    assert [path.relative_to(tmp_path).as_posix() for path in found] == ["a.txt", "nested/b.txt"]
