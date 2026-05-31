from __future__ import annotations

import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .models import ProposalRow
from .paths import DOCUMENT_EXTENSIONS, TEXT_EXTENSIONS, safe_rel, slug_time
from .scanner import write_manifest


SUPPORTED_RENAME_EXTENSIONS = DOCUMENT_EXTENSIONS | {".csv", ".md", ".txt"}

GENERIC_BASENAMES = {
    "document",
    "file",
    "img",
    "image",
    "note",
    "notes",
    "scan",
    "scanned document",
    "untitled",
}
GENERIC_WORDS = {"copy", "document", "file", "img", "image", "new", "scan", "untitled"}
GENERIC_DIRECTORY_NAMES = {"archive", "desktop", "docs", "documents", "downloads", "files", "folder", "misc", "stuff"}

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
HEX_RE = re.compile(r"^[0-9a-f]{24,}$", re.I)
IMG_RE = re.compile(r"^img[_ -]?\d+$", re.I)
NUMERIC_RE = re.compile(r"^\d{5,}$")
COPY_SUFFIX_RE = re.compile(r"\s+(copy(?:\s+\d+)?|\(\d{1,3}\))$", re.I)
DATE_PREFIX_RE = re.compile(r"^\d{6,8}[\s_-]+")
NOISE_CHUNK_RE = re.compile(r"[_\-]{2,}")
CANONICAL_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class RenameCandidate:
    title: str
    source: str
    confidence: str
    reason: str


def normalize_whitespace(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00a0", " ")
    value = value.replace("\u200b", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_for_compare(value: str) -> str:
    cleaned = normalize_whitespace(value).casefold()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def sanitize_title(value: str) -> str:
    cleaned = normalize_whitespace(value)
    cleaned = cleaned.replace("_", " ")
    cleaned = cleaned.replace("/", " ")
    cleaned = cleaned.replace(":", " - ")
    cleaned = cleaned.replace("\\", " ")
    cleaned = cleaned.replace("\n", " ")
    cleaned = cleaned.replace("\r", " ")
    cleaned = re.sub(r"[*?\"<>|]", "", cleaned)
    cleaned = re.sub(r"\s+[._-]+\s*$", "", cleaned)
    cleaned = NOISE_CHUNK_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-")
    return cleaned[:120].strip()


def alpha_words(value: str) -> list[str]:
    return CANONICAL_WORD_RE.findall(normalize_whitespace(value))


def looks_opaque(stem: str) -> bool:
    normalized = normalize_for_compare(stem)
    plain = normalized.replace(" ", "")
    if not normalized:
        return True
    if normalized in GENERIC_BASENAMES:
        return True
    if UUID_RE.fullmatch(stem) or HEX_RE.fullmatch(plain):
        return True
    if IMG_RE.fullmatch(normalized) or NUMERIC_RE.fullmatch(plain):
        return True
    if DATE_PREFIX_RE.match(stem) and len(alpha_words(stem)) <= 1:
        return True
    words = alpha_words(stem)
    if len(words) == 0:
        return True
    if len(words) == 1 and len(words[0]) <= 4:
        return True
    if len(words) <= 1 and re.search(r"\d", stem):
        return True
    if COPY_SUFFIX_RE.search(stem) and len(words) <= 2:
        return True
    return False


def clarity_score(stem: str) -> int:
    words = alpha_words(stem)
    score = 0
    if 2 <= len(words) <= 8:
        score += 4
    elif words:
        score += 2
    if not looks_opaque(stem):
        score += 4
    if re.search(r"\d", stem):
        score -= 1
    if any(word.casefold() in GENERIC_WORDS for word in words):
        score -= 2
    if 5 <= len(stem) <= 80:
        score += 1
    return score


def current_name_is_clear(stem: str) -> bool:
    if looks_opaque(stem):
        return False
    words = alpha_words(stem)
    return len(words) >= 2 or any(len(word) >= 10 for word in words)


def build_context_label(path: Path, root: Path) -> str:
    try:
        parts = path.parent.relative_to(root).parts
    except ValueError:
        parts = path.parent.parts
    meaningful: list[str] = []
    for part in parts:
        normalized = normalize_for_compare(part)
        if not normalized or normalized in GENERIC_DIRECTORY_NAMES or normalized.startswith("."):
            continue
        meaningful.append(" ".join(token[:1].upper() + token[1:] for token in re.split(r"[\s_-]+", part) if token))
    return " - ".join(meaningful[-2:])


def best_text_heading(text: str) -> str | None:
    best_line = None
    best_score = -1
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        line = sanitize_title(raw_line.lstrip("#*- \t"))
        if not line:
            continue
        words = alpha_words(line)
        if len(words) < 2 or len(words) > 12 or len(line) > 90:
            continue
        if re.search(r"https?://|www\.|%[0-9a-f]{2}", line, flags=re.I):
            continue
        if any(mark in stripped for mark in [",", ";", "!", "?"]):
            continue
        score = 0
        if stripped.startswith("#"):
            score += 3
        if len(words) >= 3:
            score += 2
        if clarity_score(line) >= 6:
            score += 1
        if score > best_score:
            best_score = score
            best_line = line[:1].upper() + line[1:]
    return best_line


def infer_csv_title(text: str, context: str) -> str | None:
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return None
    header = [normalize_for_compare(cell) for cell in rows[0]]
    sample_rows = rows[1:6]
    if {"symbol", "type", "quantity", "price", "value"}.issubset(set(header)):
        symbol_index = header.index("symbol")
        symbols = {row[symbol_index].strip().upper() for row in sample_rows if len(row) > symbol_index and row[symbol_index].strip()}
        if len(symbols) == 1:
            return f"{next(iter(symbols))} Transaction History"
        return "Crypto Transaction History"
    if {"date", "amount", "description"}.issubset(set(header)):
        return "Transaction History"
    if context:
        return f"{context} Data Export"
    return None


def read_text(path: Path, limit: int = 12000) -> str:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def infer_filename_title(path: Path, root: Path, *, aggressive: bool) -> RenameCandidate | None:
    stem = path.stem
    context = build_context_label(path, root)
    if DATE_PREFIX_RE.match(stem) and len(alpha_words(stem)) >= 2:
        cleaned = sanitize_title(DATE_PREFIX_RE.sub("", stem))
        if cleaned:
            return RenameCandidate(cleaned, "filename_cleanup", "medium", "removed date prefix")
    if COPY_SUFFIX_RE.search(stem) and len(alpha_words(stem)) >= 2:
        cleaned = sanitize_title(COPY_SUFFIX_RE.sub("", stem))
        if cleaned:
            return RenameCandidate(cleaned, "filename_cleanup", "medium", "removed duplicate suffix")
    if looks_opaque(stem) and context:
        label = "Data Export" if path.suffix.lower() == ".csv" else "Document"
        suffix = f" {stem}" if NUMERIC_RE.fullmatch(stem.replace(" ", "")) else ""
        return RenameCandidate(sanitize_title(f"{context} {label}{suffix}"), "context_fallback", "low", "used folder context for opaque filename")
    if aggressive:
        humanized = sanitize_title(stem.replace("_", " ").replace("-", " "))
        if humanized and normalize_for_compare(humanized) != normalize_for_compare(stem):
            return RenameCandidate(humanized, "filename_humanized", "low", "humanized filename punctuation and separators")
    return None


def infer_candidate(path: Path, root: Path, *, aggressive: bool = False) -> RenameCandidate | None:
    current_stem = path.stem
    candidates: list[RenameCandidate] = []
    if not aggressive and current_name_is_clear(current_stem) and not COPY_SUFFIX_RE.search(current_stem) and not DATE_PREFIX_RE.match(current_stem):
        return None

    text = read_text(path)
    if path.suffix.lower() == ".csv":
        csv_title = infer_csv_title(text, build_context_label(path, root))
        if csv_title:
            candidates.append(RenameCandidate(sanitize_title(csv_title), "content_csv", "high", "used CSV headers and sample rows"))
    elif path.suffix.lower() in {".md", ".txt"}:
        heading = best_text_heading(text[:8000])
        if heading:
            candidates.append(RenameCandidate(heading, "content_heading", "medium", "used leading text heading"))

    filename_candidate = infer_filename_title(path, root, aggressive=aggressive)
    if filename_candidate:
        candidates.append(filename_candidate)

    candidates = [candidate for candidate in candidates if candidate.title and normalize_for_compare(candidate.title) != normalize_for_compare(current_stem)]
    if not candidates:
        return None
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    candidates.sort(key=lambda item: (confidence_rank[item.confidence], clarity_score(item.title)), reverse=True)
    best = candidates[0]
    if not looks_opaque(current_stem) and clarity_score(best.title) < clarity_score(current_stem) + 1:
        return None
    return best


def iter_document_files(root: Path, extensions: set[str]) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [name for name in sorted(dirnames) if not name.startswith(".")]
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            path = Path(current_root) / filename
            if path.suffix.lower() in extensions:
                files.append(path)
    return files


def suggest_renames(root: Path, out_root: Path, *, extensions: set[str], sample: int = 0, aggressive: bool = False) -> Path:
    root = root.expanduser().resolve()
    out_dir = out_root.expanduser().resolve() / slug_time()
    out_dir.mkdir(parents=True, exist_ok=False)
    files = iter_document_files(root, extensions)
    if sample:
        files = files[:sample]
    rows: list[ProposalRow] = []
    for path in files:
        candidate = infer_candidate(path, root, aggressive=aggressive)
        if candidate is None:
            continue
        try:
            destination = path.parent.relative_to(root).as_posix() or "."
        except ValueError:
            destination = "."
        rows.append(
            ProposalRow(
                source_path=safe_rel(path, root),
                action="rename",
                destination=destination,
                proposed_name=f"{candidate.title}{path.suffix}",
                gate="review",
                confidence=candidate.confidence,
                reason=f"{candidate.reason}; source={candidate.source}",
            )
        )
    write_manifest(out_dir / "rename_manifest.tsv", rows)
    summary = [
        "# Rename Suggestion Run",
        "",
        f"- Root name: `{root.name}`",
        f"- Files scanned: `{len(files)}`",
        f"- Rename candidates: `{len(rows)}`",
        "- Mode: proposal only; edit `gate` to `approved` before apply.",
    ]
    (out_dir / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return out_dir
