# Mac Cleanup Manifest Toolkit

Manifest-first file cleanup for cautious rename and move workflows.

This toolkit helps you inspect messy folders, generate reviewable TSV manifests,
validate proposed moves, apply only approved rows, and produce undo logs. It was
designed for personal Mac cleanup work where guesses are expensive and every
batch should be auditable before anything moves.

## What It Does

- Inspects files into small context cards without requiring cloud services.
- Generates proposal manifests with relative paths by default.
- Suggests safer filenames for opaque document names.
- Holds sensitive-looking paths instead of previewing their contents.
- Validates manifests before apply.
- Applies only approved move or rename rows.
- Writes undo manifests for rollback.
- Scans repositories or manifests for obvious secrets and private local paths.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

## Quick Start

Create a proposal run:

```bash
mac-cleanup inspect sample_data/inbox --out runs
```

Suggest clearer names for documents:

```bash
mac-cleanup suggest-renames sample_data/inbox --out runs
```

Validate a reviewed manifest:

```bash
mac-cleanup validate runs/example_manifest.tsv --root sample_data/inbox
```

Dry-run approved rows:

```bash
mac-cleanup apply runs/example_manifest.tsv --root sample_data/inbox
```

Actually apply approved rows:

```bash
mac-cleanup apply runs/example_manifest.tsv --root sample_data/inbox --execute
```

Undo a prior apply:

```bash
mac-cleanup undo runs/undo.tsv --root sample_data/inbox --execute
```

## Manifest Contract

The core TSV columns are:

```text
source_path	action	destination	proposed_name	gate	confidence	reason
```

- `source_path`: relative path under the chosen root.
- `action`: `keep`, `hold`, `move`, `rename`, or `move_rename`.
- `destination`: relative destination directory under the chosen root.
- `proposed_name`: final file or directory name.
- `gate`: `review`, `hold`, `no_apply`, `approved`, or `ready_to_apply`.
- `confidence`: `low`, `medium`, or `high`.
- `reason`: human-readable evidence.

Only rows with `gate=approved` are executable by default. `ready_to_apply` rows
require `--allow-ready-to-apply`.

## Privacy Model

The repository includes only fake sample data. Generated manifests should use
relative paths and should be reviewed before sharing. Do not publish personal
cleanup logs, raw file previews, full local paths, tokens, private documents, or
undo scripts generated from your real machine.

## Status

Useful as a conservative CLI toolkit. The current focus is local file cleanup,
not deletion, deduplication by deletion, or automatic cloud-drive mutation.
