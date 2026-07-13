# Changelog

All notable changes to this project are documented here.

## Unreleased

- Rejected directory moves into their own descendants before execution can
  create nested paths or mutate the source tree.
- Added public repository polish: README quality signals, documentation links,
  package project URLs, GitHub issue templates, and a pull request template.
- Fixed direct local test discovery by adding `src` to the pytest import path.

## 0.1.0 - 2026-05-31

- Initial public MVP for manifest-first local file cleanup, rename suggestions,
  approval-gated apply/undo workflows, and secret scanning.
- Added fake sample data, privacy documentation, manifest docs, security policy,
  and tests for the core CLI behavior.
