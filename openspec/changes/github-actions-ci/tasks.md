# Tasks

## 1. CI workflow

- [x] 1.1 Add `.github/workflows/ci.yml` with read-only permissions, pinned
  actions, concurrency, and a C matrix for Ubuntu, macOS x64/arm64, and Windows
  MSYS2. Verify the YAML parses and each CLI job runs `make test`.
- [x] 1.2 Add the Windows Rust job with `cargo fmt --check`,
  `clippy --all-targets -- -D warnings`, and `cargo test`. Verify the job uses
  `build.bat` for the MSVC environment and does not depend on `.NET`.

## 2. Release workflow

- [ ] 2.1 Add `.github/workflows/release.yml` on `v*` tags with a
  `contents: write` release job, a tag/version gate, and artifact upload via
  `gh`. Verify the workflow creates or updates a release and does not overwrite
  unrelated assets.
- [ ] 2.2 Build Linux, macOS x64/arm64, and Windows CLI archives, the Windows
  portable workbench ZIP, and the optional Inno Setup installer. Verify each
  upload path exists before `gh release` runs.

## 3. Documentation and validation

- [x] 3.1 Document the CI matrix, release assets, and local equivalents in
  `README.md`, `AGENTS.md`, and `ui/rust/README.md`. Verify
  `check_doc_paths.py` and `check_readme_tests.py` pass.
- [x] 3.2 Parse both workflow files with PyYAML, run `actionlint` if available,
  and confirm the workflow permissions and pinned revisions. Verify no
  `pull_request_target` or plaintext secret is present.
- [ ] 3.3 Run `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`,
  `cargo test`, `make test`, and `make verify-commit`. Verify all pass.

## Workflow follow-up

- Commit the workflow change after review.
- Push the branch and observe the first CI run before tagging a release.
- Update pinned action revisions as a separate maintenance change.
