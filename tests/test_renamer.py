from __future__ import annotations

from pathlib import Path

from mac_cleanup_manifest.renamer import infer_candidate, infer_csv_title, looks_opaque


def test_looks_opaque_detects_uuid() -> None:
    assert looks_opaque("0e47bfa5-adf0-45a6-80db-3ad6e31f648d")


def test_infer_csv_title_for_crypto_history() -> None:
    text = "\n".join(
        [
            "Symbol,Type,Quantity,Price,Value,Fees,Date",
            "BTC,Buy,0.0052,1000,5,1,2026-01-01",
            "BTC,Buy,0.0050,1000,5,1,2026-01-02",
        ]
    )
    assert infer_csv_title(text, "") == "BTC Transaction History"


def test_context_fallback_builds_readable_label(tmp_path: Path) -> None:
    folder = tmp_path / "visas" / "work visa"
    folder.mkdir(parents=True)
    path = folder / "170691.pdf"
    path.write_text("fake", encoding="utf-8")

    candidate = infer_candidate(path, tmp_path)

    assert candidate is not None
    assert candidate.title == "Visas - Work Visa Document 170691"
