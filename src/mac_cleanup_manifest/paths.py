from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


NO_DESCEND_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
}

PACKAGE_SUFFIXES = {
    ".app",
    ".bundle",
    ".framework",
    ".key",
    ".numbers",
    ".pages",
    ".photoslibrary",
    ".playground",
    ".rtfd",
    ".workflow",
    ".xcworkspace",
}

TEXT_EXTENSIONS = {
    ".csv",
    ".html",
    ".json",
    ".log",
    ".md",
    ".py",
    ".sh",
    ".txt",
    ".yaml",
    ".yml",
}

DOCUMENT_EXTENSIONS = {".doc", ".docx", ".pdf", ".rtf"}
IMAGE_EXTENSIONS = {".gif", ".heic", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
MEDIA_EXTENSIONS = {".m4a", ".m4v", ".mov", ".mp3", ".mp4", ".wav"}
ARCHIVE_EXTENSIONS = {".7z", ".dmg", ".gz", ".rar", ".tar", ".tgz", ".zip"}

SENSITIVE_NAME_RE = re.compile(
    r"(\.env|cookie|credential|password|secret|session|token|api[_-]?key|keychain|"
    r"bank|bankid|2fa|totp|certificate|private[_-]?key|mobileconfig|passport|"
    r"identity|tax|medical|health|migration|visa)",
    re.IGNORECASE,
)


def slug_time() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def safe_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def should_skip_directory(path: Path) -> bool:
    return path.name in NO_DESCEND_NAMES or path.name.startswith(".") or path.suffix.lower() in PACKAGE_SUFFIXES


def path_has_sensitive_name(path: Path | str) -> bool:
    return bool(SENSITIVE_NAME_RE.search(str(path)))


def resolve_input_path(root: Path, value: str, *, allow_absolute: bool = False) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        if not allow_absolute:
            raise ValueError(f"absolute paths are disabled: {value}")
        resolved = raw.resolve()
    else:
        if any(part == ".." for part in raw.parts):
            raise ValueError(f"path traversal is not allowed: {value}")
        resolved = (root / raw).resolve()
    root_resolved = root.resolve()
    if not is_relative_to(resolved, root_resolved):
        raise ValueError(f"path escapes root: {value}")
    return resolved


def ensure_single_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("proposed_name is empty")
    path = Path(name)
    if path.is_absolute() or len(path.parts) != 1 or name in {".", ".."}:
        raise ValueError(f"proposed_name must be a single name: {value}")
    return name


def clean_preview(text: str, *, max_lines: int = 80) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines[:max_lines])


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned[:80] or "item"


def default_destination_for(path: Path, item_type: str) -> tuple[str, str, str]:
    if item_type == "directory":
        return "Review/Directories", "low", "Directory requires human review before moving."
    suffix = path.suffix.lower()
    if suffix in DOCUMENT_EXTENSIONS:
        return "Documents", "medium", "Document-like file; review destination before apply."
    if suffix in IMAGE_EXTENSIONS:
        return "Images", "medium", "Image-like file; visual review is recommended before apply."
    if suffix in MEDIA_EXTENSIONS:
        return "Media", "medium", "Media file; review context before apply."
    if suffix in ARCHIVE_EXTENSIONS:
        return "Archives", "low", "Archive file; inspect contents before moving or extracting."
    if suffix in TEXT_EXTENSIONS:
        return "Text-and-Code", "medium", "Text file; review project coupling before moving."
    return "Review/Unassigned", "low", "No confident destination rule matched."
