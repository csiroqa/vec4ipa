# Proposal

## Why

The C tools are advertised as portable, but the repository has no CI matrix,
no branch gate, and no automated release. The 4.0.0 package was built by hand
on one Windows machine. That makes platform claims unverified and puts release
uploads outside the repository's audit trail.

## What Changes

- Add a GitHub Actions CI workflow for the C tools on Linux, macOS (x64 and
  arm64), and Windows (MSYS2), plus the Rust workbench on Windows.
- Add a tag-triggered release workflow that checks the tag against
  `IPA2VEC_VERSION`, builds platform archives, packages the Windows workbench,
  and publishes the assets with the repository `GITHUB_TOKEN`.
- Use least-privilege permissions, pinned action revisions, explicit timeouts,
  concurrency keys, and `persist-credentials: false` on checkout.
- Build the Inno Setup installer when the runner can install Inno Setup; keep
  the portable workbench ZIP as the fallback release asset.
- Document the workflows and the local commands they mirror.

No parser, vector, workbench, or packaging behavior changes.

## Capabilities

### New Capabilities

None. This is repository automation; no spec-level behavior changes.

### Modified Capabilities

None.

## Impact

- `.github/workflows/ci.yml` and `.github/workflows/release.yml` (new).
- `README.md`, `AGENTS.md`, and `ui/rust/README.md` gain CI and release notes.
- No changes to `src/`, `ui/rust/src/`, settings, or release artifacts already
  published.
