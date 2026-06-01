## Summary

- 

## Checks

- [ ] `python3 -m pytest`
- [ ] `python3 -m compileall src tests`
- [ ] `mac-cleanup scan-secrets .`

## Safety

- [ ] No real local paths, private filenames, generated manifests, tokens, or
      undo/apply logs are committed.
- [ ] Dry-run and explicit approval gates remain the default.
- [ ] Documentation was updated if CLI behavior or manifest format changed.
