from __future__ import annotations

from pathlib import Path

from mac_cleanup_manifest.secret_scan import scan_path


def test_secret_scan_detects_constructed_bearer_token(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("Authorization: " + "Bearer " + "A" * 20, encoding="utf-8")

    findings = scan_path(path)

    assert findings
    assert findings[0].kind == "bearer_token"


def test_secret_scan_skips_marked_fixture_line(tmp_path: Path) -> None:
    path = tmp_path / "fixture.txt"
    path.write_text("Authorization: " + "Bearer " + "B" * 20 + " allow-secret-fixture", encoding="utf-8")

    assert scan_path(path) == []
