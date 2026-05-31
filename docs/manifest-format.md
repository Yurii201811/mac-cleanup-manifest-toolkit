# Manifest Format

Manifest files are tab-separated text files with this header:

```text
source_path	action	destination	proposed_name	gate	confidence	reason
```

## Path Rules

- Prefer relative paths.
- Absolute paths are rejected by default.
- `..` path traversal is rejected.
- Destinations must stay under the root.
- `proposed_name` must be a single filename or directory name, not a path.

## Actions

- `keep`: leave in place.
- `hold`: intentionally stop and preserve.
- `move`: move to a destination with the same name unless `proposed_name` is set.
- `rename`: keep the current directory and change the name.
- `move_rename`: move to a destination and change the name.

The toolkit does not implement delete actions.

## Gates

- `review`: proposed but not approved.
- `hold`: preserve for manual review.
- `no_apply`: never applied by this CLI.
- `approved`: eligible for apply.
- `ready_to_apply`: eligible only with `--allow-ready-to-apply`.
