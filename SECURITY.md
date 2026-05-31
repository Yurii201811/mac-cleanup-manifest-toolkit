# Security Policy

## Supported Versions

The `main` branch receives fixes.

## Reporting

Please report issues through GitHub Issues unless the report includes private
data. If it does, share only a minimal redacted reproduction.

## Data Handling

This tool is local-first. It does not upload files. It may write context cards,
manifests, apply logs, and undo manifests to disk. Treat generated artifacts as
potentially sensitive if they came from your real folders.

Recommended boundaries:

- Do not publish generated manifests from real folders.
- Do not publish context cards from private documents.
- Use relative paths for shareable examples.
- Review undo scripts or undo manifests before sharing.
