# Design

## Context

See `proposal.md`. The CLI builds through the root `Makefile`; the Rust
workbench builds through `ui/rust/build.bat`, which loads `VsDevCmd.bat`, and
`ui/rust/installer.bat` wraps the package in Inno Setup. CI must not require a
Windows-only runner for the C tests, and the release must not depend on a
maintainer's local toolchain.

## Goals / Non-Goals

**Goals:**

- Verify the C tools on Linux, macOS x64/arm64, and Windows on every push and
  pull request.
- Verify the Rust workbench compile, lint, and tests on Windows.
- Produce reproducible tag releases with version checks and attached assets.
- Keep workflow permissions minimal and actions pinned.

**Non-Goals:**

- Cross-platform GUI support. The Rust workbench remains Windows-only.
- Code signing, notarization, or an MSIX package.
- Replacing the local Inno Setup fallback when it is unavailable.

## Decisions

### Two workflows: CI and tag release

`ci.yml` runs on `push` to `master` and on pull requests. It has read-only
permissions and a concurrency group that cancels superseded runs.

`release.yml` runs on `push` tags matching `v*`. It checks the tag against
`IPA2VEC_VERSION`, builds the assets, and creates or updates the GitHub
release. Only this workflow gets `contents: write`.

Alternative: one workflow with conditional jobs. Rejected because the release
permission should not be available to branch builds.

### Pin actions and avoid third-party release actions

Use full commit SHAs for:

- `actions/checkout` v4.2.2
- `actions/setup-python` v5.6.0
- `actions/upload-artifact` v4.6.2
- `actions/download-artifact` v4.3.0
- `msys2/setup-msys2` v2.30.0

The release upload uses the preinstalled `gh` CLI with `GITHUB_TOKEN`; it does
not use a third-party release action. Checkout uses
`persist-credentials: false`.

### Use MSYS2 for the Windows C build

The Makefile builds the legacy Win32 wrapper with `windres` on Windows. MSYS2
provides `gcc`, `make`, and `windres`. The workflow installs Python and NumPy
with `actions/setup-python`, then passes the Windows interpreter path through
`cygpath` as `PYTHON` to `make test`.

Alternative: build the C tools with MSVC. Rejected because the Makefile and
legacy wrapper are MinGW-oriented.

### Use the native shell for each platform

Linux and macOS jobs run `make` and `make test` directly. The macOS matrix uses
`macos-15-intel` for x64 and `macos-15` for arm64. `macos-13` is retired, so do
not use it. The Windows matrix uses the MSYS2 shell for the C half and a
PowerShell/cmd step for the Rust half.

### Build the installer best-effort

The Windows release job installs Inno Setup with Chocolatey using
`--requirechecksums`. If the package cannot be installed, the release still
publishes the portable workbench ZIP. The installer step is skipped, not
silently replaced by an empty file. The `gh release` step accepts whatever
assets the jobs produced.

Alternative: make the release fail without Inno Setup. Rejected because it
would make the whole release hostage to one optional packaging tool.

### Version gate before publishing

The release job reads `IPA2VEC_VERSION` from `src/ipa2vec_core.h` and compares
it with the tag without the leading `v`. A mismatch fails before any asset is
uploaded. This prevents a `v4.0.1` tag from publishing a 4.0.0 executable.

## Risks / Trade-offs

- **Windows CI is the slowest job** → keep it to `make test` and the Rust
  workbench checks; do not build the installer in CI.
- **macOS runners change architecture** → pin `macos-15-intel` and `macos-15`,
  not `macos-latest`; `macos-13` and `macos-14` are retired or retiring.
- **Inno Setup installation is optional** → release includes a portable ZIP
  even when the installer is unavailable; the workflow does not publish a
  missing or stale installer.
- **Pinned actions need periodic updates** → document the versions and keep
  the update as a small, reviewable change.
- **The public release uses the repository token** → only tag builds get
  `contents: write`; all other jobs are read-only.
