from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOKEN_PREFIX = "s" + "k-"
GITHUB_CLASSIC = "g" + "hp_"
GITHUB_FINE = "github" + "_pat_"
PRIVATE_KEY_MARKER = "BEGIN " + "PRIVATE KEY"
HA_TOKEN_NAME = "HOME" + "ASSISTANT_TOKEN"

PATTERNS = [
    ("private_user_path", re.compile(r"/Users/[A-Za-z0-9._-]+")),
    ("homeassistant_token_var", re.compile(re.escape(HA_TOKEN_NAME))),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{16,}")),
    ("github_token", re.compile(rf"({re.escape(GITHUB_CLASSIC)}|{re.escape(GITHUB_FINE)})[A-Za-z0-9_]+")),
    ("openai_key", re.compile(rf"{re.escape(TOKEN_PREFIX)}[A-Za-z0-9_-]{{16,}}")),
    ("private_key", re.compile(PRIVATE_KEY_MARKER)),
]

DEFAULT_SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "runs",
    "private_runs",
    "real_manifests",
}


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str
    excerpt: str


def iter_files(target: Path) -> Iterable[Path]:
    if target.is_file():
        yield target
        return
    for path in target.rglob("*"):
        if any(part in DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def scan_path(target: Path) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in iter_files(target):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "allow-secret-fixture" in line:
                continue
            for kind, pattern in PATTERNS:
                if pattern.search(line):
                    excerpt = pattern.sub("[REDACTED]", line.strip())[:200]
                    findings.append(SecretFinding(path.as_posix(), line_number, kind, excerpt))
    return findings
