from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextCard:
    source_path: str
    relative_path: str
    item_type: str
    extension: str
    size_bytes: int | None
    modified_at: str | None
    inspection_status: str
    extracted_context: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ProposalRow:
    source_path: str
    action: str
    destination: str
    proposed_name: str
    gate: str
    confidence: str
    reason: str


@dataclass(frozen=True)
class ApplyRecord:
    source_path: str
    destination_path: str
    action: str
    status: str
    reason: str
