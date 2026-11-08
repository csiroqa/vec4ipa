# Proposal

## Why

The Rust workbench is feature-complete, but the repository still carries the
WinUI C# reference under `ui/winui/`: a second 3,700-line UI, a .NET/MSBuild
build path, an MSIX project, and a tracked `ipa2vec_core.dll` that exists only
for the C# tests. That parallel implementation makes the shipping front-end
ambiguous, keeps a large dead surface in the build documentation, and requires
toolchains that the Rust workbench does not need. The suite version is still
3.1.0, from before the module manager landed.

## What Changes

- Remove the WinUI C# workbench, its MSIX project, its assets, and the
  C#-specific checks (`test_winui_core.py`, `check_mainwindow_syntax.py`,
  `build_winui.py`).
- Move the FFI shim to `ui/rust/core_wrap.c` and make the Rust workbench the
  only full desktop workbench. The legacy Win32 wrapper stays as a minimal
  fallback and is not shipped in the installer.
- Bump the suite to **4.0.0** in the C core and the Cargo package.
- Generate a Windows `VERSIONINFO` resource in `build.rs` from
  `IPA2VEC_VERSION`, so the executable's Properties dialog, the installer, and
  the CLI all report the same version.
- Keep the embedded application icon and verify it on the executable,
  installer, shortcuts, and uninstall entry.
- Rebuild the self-contained folder and the Inno Setup installer as
  `vec4ipa-setup-4.0.0.exe`. Keep the existing AppId so the installer upgrades
  in place, and delete stale C# support files from an existing install
  directory.
- Update the README, `ui/README.md`, `AGENTS.md`, test list, and audit
  catalogue to describe the Rust-only workbench.

No vector, parser, CLI, or data-format behavior changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `desktop-packaging`: the release ships one Rust workbench, carries matching
  icon and version metadata, and upgrades over an older install without
  leaving the old C# runtime behind.

## Impact

- Delete `ui/winui/` (C# sources, XAML, MSIX project, tracked DLL, assets) and
  the three C#-specific Python checks.
- Move `ui/winui/core_wrap.c` to `ui/rust/core_wrap.c`; update `build.rs`.
- `src/ipa2vec_core.h`: version 4.0.0.
- `ui/rust/Cargo.toml` / `Cargo.lock`: package version 4.0.0.
- `ui/rust/build.rs`: generated version resource.
- `ui/rust/installer.iss`: upgrade cleanup and release metadata.
- `Makefile`, `README.md`, `ui/README.md`, `AGENTS.md`, docs table, audit
  catalogue, and test list.
- New installer artifact at `ui/rust/installer/vec4ipa-setup-4.0.0.exe`.
