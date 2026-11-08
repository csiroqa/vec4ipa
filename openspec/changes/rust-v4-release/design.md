# Design

## Context

See `proposal.md`. The Rust workbench compiles the shared C shim through
`build.rs` and does not need a DLL. The C# workbench is the only consumer of
`ui/winui/Core.cs`, `ui/winui/ipa2vec_core.dll`, the MSIX project, and the
three C#-specific Python checks. `IPA2VEC_VERSION` in
`src/ipa2vec_core.h` is already the single release version used by the CLI
banner and `installer.bat`.

## Goals / Non-Goals

**Goals:**

- One full workbench and one FFI source in the repository.
- Version 4.0.0 reported consistently by CLI, executable metadata, installer,
  and Apps & features.
- A clean upgrade that removes the old C# runtime files.
- Keep the embedded icon on the executable, shortcuts, installer, and
  uninstall entry.

**Non-Goals:**

- Removing the legacy Win32 wrapper (`ui/vec4ipa_ui.c`).
- Changing parser, vector, metric, or CLI behavior.
- Automatically uninstalling a separately installed MSIX package.

## Decisions

### Move the shim into the Rust tree

`git mv ui/winui/core_wrap.c ui/rust/core_wrap.c` keeps one implementation and
makes the Rust build self-contained. `build.rs` reads `core_wrap.c` from its
manifest directory and keeps the existing `/utf-8` and nested-helper fixes for
MSVC.

Alternative: keep the shim under `ui/winui/` after deleting the C# project.
Rejected because the path would name a front-end that no longer exists.

### Delete the C# sources and their checks

Delete `ui/winui/` entirely, including the MSIX project and tracked DLL. Delete
`tools/test_winui_core.py`, `tools/check_mainwindow_syntax.py`, and
`tools/build_winui.py`. The Rust tests already cover the wrapper contract:
`engine_contract`, `runtime_width_and_sequential_scheme_switch`, and
`parity_with_cli` exercise width, scheme swaps, and value parity.

Alternative: keep the C# sources as an archived reference. Rejected because
the user asked for a complete replacement, and dead sources keep the MSBuild
requirement alive in documentation.

### Read the version once in `build.rs`

`build.rs` parses `#define IPA2VEC_VERSION "..."` from
`src/ipa2vec_core.h`, then writes a small `version.rc` in `OUT_DIR` with
`FILEVERSION` and `PRODUCTVERSION`. The existing `app.rc` still supplies the
icon. Both resources are compiled with `embed-resource`.

Alternative: hard-code 4.0.0 in `app.rc`. Rejected because the next version
bump would silently leave the executable metadata behind.

### Keep the installer AppId and clean old files

The AppId stays `{085C8C44-...}` so 4.0.0 upgrades a 3.x install in place.
`[InstallDelete]` removes `ipa2vec_core.dll`, `vec4ipa_ui.dll`, and the C#
runtime JSON files if an older layout left them. The Rust executable keeps the
name `vec4ipa-ui.exe`, so shortcuts continue to resolve.

### Package the same folder

`package.bat` still produces `dist/`; `installer.bat` reads the new version and
writes `installer/vec4ipa-setup-4.0.0.exe`. The installer continues to offer a
per-user install by default and an all-users install through
`PrivilegesRequiredOverridesAllowed`.

## Risks / Trade-offs

- Removing the C# tests reduces independent surface → the Rust engine tests and
  `make test` remain the gate; the wrapper is compiled by Cargo on every build.
- The old MSIX package is not removed automatically → the README tells users to
  uninstall it themselves.
- `VERSIONINFO` generation runs on every build → `build.rs` reparses one header
  line, which is cheap and already a rerun dependency.
- Deleting `ui/winui` removes its assets → the Rust package already uses
  `ui/assets` and `ui/fonts`.
