# Workflow

This project is built around a simple rule: no meaningful file cleanup happens
without a manifest.

## 1. Inspect

Run `mac-cleanup inspect` against a narrow root. The command writes:

- `context_cards/`: one small JSON card per item.
- `manifest.tsv`: reviewable proposal rows.
- `manifest.json`: the same rows for tools.
- `README.md`: run counts and approval boundary.

Sensitive-looking paths are held without content preview.

## 2. Review

Open the manifest and change only rows you truly approve:

- Set `gate` to `approved`.
- Keep sensitive or ambiguous rows as `hold` or `review`.
- Keep system files and runtime dependencies as `no_apply`.

## 3. Validate

Run `mac-cleanup validate MANIFEST --root ROOT`. Validation checks required
columns, path containment, destination collisions, and gate/action combinations.

## 4. Apply

Run `mac-cleanup apply MANIFEST --root ROOT` first. This is a dry-run.

Use `--execute` only after reviewing the dry-run output. The command writes an
undo TSV beside the manifest unless `--undo-out` is provided.

## 5. Undo

Run `mac-cleanup undo UNDO_TSV --root ROOT` first for a dry-run, then add
`--execute` after review. Undo preflights every row before the first move and
fails closed on missing, duplicate, or overlapping rollback paths—including
case and Unicode aliases common on APFS—so an invalid later row cannot leave an
earlier row partially undone. Filesystem races or permission failures during
execution can still produce a partial undo; keep the undo TSV until the restored
paths have been checked.
