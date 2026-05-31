# Privacy

The safest public artifact is the tool, not your generated cleanup output.

## Safe To Share

- Source code.
- Fake sample manifests.
- Redacted schema examples.
- Counts and workflow summaries that do not identify private files.

## Do Not Share

- Real cleanup manifests.
- Raw context cards from personal folders.
- Full local paths.
- Undo scripts from real machines.
- Tokens, cookies, keychains, mobile profiles, certificates, or `.env` files.
- Personal legal, health, tax, migration, banking, housing, or identity records.

## Built-In Guardrails

- Generated paths are relative by default.
- Sensitive-looking paths are held without preview.
- Apply is dry-run by default.
- Only approved rows apply by default.
- Undo manifests are generated for executed moves.
