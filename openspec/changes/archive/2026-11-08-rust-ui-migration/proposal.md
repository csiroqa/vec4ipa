# Proposal

## Why

The WinUI 3 workbench is a 3,700-line C# code-behind file plus a 33 KB XAML
file. It depends on .NET 9, MSBuild, and the XAML/PRI toolchain. The project
owner wants a Rust front-end built with `windows-reactor` while keeping the
tested C core and CLI tools. A Rust UI can start faster, ship as a smaller
self-contained output, and use one declarative component model.

## What Changes

- Add a new `ui/rust` Cargo application built with `windows-reactor`.
- Keep `src/ipa2vec_core.h` and the three CLI tools unchanged; bind the Rust
  UI to the existing `core_wrap.c` C ABI.
- Rebuild all current workbench features in Rust: forward and reverse
  conversion, loop, soft keyboard, symbol details, history, compare, distance,
  alignment, table/module/statistics/weight views, exports, settings, themes,
  English/Chinese UI, window state, and CLI startup arguments.
- Keep `ui/winui` as the shipping front-end until the Rust front-end reaches
  parity. Do not delete or modify it in this change.
- Produce a self-contained Cargo output folder first. MSIX packaging is out of
  scope for this change.
- Add Rust FFI parity tests that compare the Rust wrapper against `vec4ipa`
  for both `spec_next.scheme` and `tongue.scheme`.
- Update build/test documentation and Makefile targets to include the Rust UI.
  The existing C and Python tests remain authoritative for the core.
- **BREAKING** for the UI build: the Rust front-end uses Cargo, not
  MSBuild/.NET. The C# front-end remains available, so the repository does not
  drop its current UI.

## Capabilities

### New Capabilities

- `desktop-workbench`: user-visible workbench behavior in the Rust front-end.
- `engine-ffi`: correctness of the Rust-to-C engine boundary, including
  runtime scheme width and value parity.
- `desktop-packaging`: self-contained Rust desktop build and distribution
  output.

### Modified Capabilities

None.

## Impact

- New `ui/rust/` Cargo project, `build.rs`, FFI module, and UI components.
- New dependencies: `windows-reactor` 0.100, `windows`, `cc`, and supporting
  crates.
- Build: Cargo, the MSVC linker, and the Windows SDK. `make` continues to build
  the C core and CLI tools.
- Tests and docs: new Rust checks. Existing `ui/winui` C# checks remain while
  that UI exists.
- No changes to the C core, generated data, runtime scheme or metric formats,
  or CLI behavior.
