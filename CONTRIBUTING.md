# Contributing

Thanks for helping make cautious file cleanup less scary.

## Principles

- Keep dry-run behavior as the default.
- Keep manifests reviewable by a human.
- Prefer relative paths in generated artifacts.
- Never add real private cleanup logs, raw personal filenames, or machine paths.
- Avoid deletion features unless they are designed with a stronger approval and
  rollback model than move or rename workflows.

## Local Checks

```bash
python -m pytest
python -m compileall src tests
```

Before opening a pull request, also scan the tree for private paths and secrets:

```bash
mac-cleanup scan-secrets .
```
