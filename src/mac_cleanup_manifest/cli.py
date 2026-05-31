from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .executor import apply_manifest, undo_manifest, write_records
from .manifest import validate_manifest
from .renamer import SUPPORTED_RENAME_EXTENSIONS, suggest_renames
from .scanner import deterministic_proposal, inspect_item, scan_root, write_run
from .secret_scan import scan_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manifest-first file cleanup toolkit.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a folder and write a proposal manifest.")
    inspect_parser.add_argument("root", type=Path)
    inspect_parser.add_argument("--out", type=Path, default=Path("runs"))
    inspect_parser.add_argument("--max-depth", type=int, default=1)
    inspect_parser.add_argument("--limit", type=int, default=0)
    inspect_parser.add_argument("--include-hidden", action="store_true")
    inspect_parser.add_argument("--include-directories", action="store_true")
    inspect_parser.add_argument("--preview-bytes", type=int, default=12000)

    rename_parser = subparsers.add_parser("suggest-renames", help="Suggest safer document names.")
    rename_parser.add_argument("root", type=Path)
    rename_parser.add_argument("--out", type=Path, default=Path("runs"))
    rename_parser.add_argument("--extensions", default=",".join(sorted(SUPPORTED_RENAME_EXTENSIONS)))
    rename_parser.add_argument("--sample", type=int, default=0)
    rename_parser.add_argument("--aggressive", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate a cleanup manifest.")
    validate_parser.add_argument("manifest", type=Path)
    validate_parser.add_argument("--root", type=Path, required=True)
    validate_parser.add_argument("--allow-ready-to-apply", action="store_true")
    validate_parser.add_argument("--allow-absolute-paths", action="store_true")

    apply_parser = subparsers.add_parser("apply", help="Dry-run or execute approved manifest rows.")
    apply_parser.add_argument("manifest", type=Path)
    apply_parser.add_argument("--root", type=Path, required=True)
    apply_parser.add_argument("--execute", action="store_true")
    apply_parser.add_argument("--undo-out", type=Path)
    apply_parser.add_argument("--log-out", type=Path)
    apply_parser.add_argument("--allow-ready-to-apply", action="store_true")
    apply_parser.add_argument("--allow-absolute-paths", action="store_true")

    undo_parser = subparsers.add_parser("undo", help="Dry-run or execute an undo manifest.")
    undo_parser.add_argument("undo_manifest", type=Path)
    undo_parser.add_argument("--root", type=Path, required=True)
    undo_parser.add_argument("--execute", action="store_true")
    undo_parser.add_argument("--allow-absolute-paths", action="store_true")

    scan_parser = subparsers.add_parser("scan-secrets", help="Scan files for obvious private paths or secrets.")
    scan_parser.add_argument("target", type=Path)

    args = parser.parse_args(argv)
    if args.command == "inspect":
        root = args.root.expanduser().resolve()
        items = scan_root(root, max_depth=args.max_depth, include_hidden=args.include_hidden, include_directories=args.include_directories)
        if args.limit:
            items = items[: args.limit]
        cards = [inspect_item(path, root, preview_bytes=args.preview_bytes) for path in items]
        rows = [deterministic_proposal(card) for card in cards]
        run_dir = write_run(root, cards, rows, args.out)
        print(json.dumps({"run_dir": run_dir.as_posix(), "items_inspected": len(cards)}, indent=2, sort_keys=True))
        return 0

    if args.command == "suggest-renames":
        extensions = parse_extensions(args.extensions)
        run_dir = suggest_renames(args.root, args.out, extensions=extensions, sample=args.sample, aggressive=args.aggressive)
        print(json.dumps({"run_dir": run_dir.as_posix()}, indent=2, sort_keys=True))
        return 0

    if args.command == "validate":
        errors, warnings = validate_manifest(
            args.manifest,
            args.root.expanduser().resolve(),
            allow_ready_to_apply=args.allow_ready_to_apply,
            allow_absolute=args.allow_absolute_paths,
        )
        payload = {"ok": not errors, "errors": errors, "warnings": warnings}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if errors else 0

    if args.command == "apply":
        try:
            records = apply_manifest(
                args.manifest,
                args.root.expanduser().resolve(),
                execute=args.execute,
                undo_out=args.undo_out,
                allow_ready_to_apply=args.allow_ready_to_apply,
                allow_absolute=args.allow_absolute_paths,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.log_out:
            write_records(args.log_out, records)
        print(json.dumps([asdict(record) for record in records], indent=2, sort_keys=True))
        return 0

    if args.command == "undo":
        try:
            records = undo_manifest(
                args.undo_manifest,
                args.root.expanduser().resolve(),
                execute=args.execute,
                allow_absolute=args.allow_absolute_paths,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps([asdict(record) for record in records], indent=2, sort_keys=True))
        return 0

    if args.command == "scan-secrets":
        findings = scan_path(args.target)
        print(json.dumps([asdict(finding) for finding in findings], indent=2, sort_keys=True))
        return 1 if findings else 0

    return 2


def parse_extensions(value: str) -> set[str]:
    extensions: set[str] = set()
    for raw_item in value.split(","):
        item = raw_item.strip().lower()
        if not item:
            continue
        if not item.startswith("."):
            item = f".{item}"
        extensions.add(item)
    return extensions
