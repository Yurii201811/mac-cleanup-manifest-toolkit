# Architecture

The package is intentionally small and standard-library only.

- `scanner.py`: walks a root and creates context cards.
- `renamer.py`: suggests clearer document names using conservative heuristics.
- `manifest.py`: reads, writes, and validates TSV manifests.
- `executor.py`: dry-runs, applies, and undoes approved rows.
- `secret_scan.py`: scans generated artifacts for obvious private data.
- `cli.py`: exposes the command-line interface.

Generated artifacts are designed for review. The CLI avoids hidden state and
does not need a daemon, database, cloud account, or file-provider integration.
