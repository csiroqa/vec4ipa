# Design

## Context

See `proposal.md` for the motivation. The current workbench is a WinUI 3
application under `ui/winui/`. Its C# side owns the window, all UI state, and
the P/Invoke wrapper around `core_wrap.c`. The C core is a header-only
implementation compiled into three CLI tools and into `ipa2vec_core.dll`.

The Rust front-end will live in a separate worktree and a new `ui/rust/`
directory. The existing `ui/winui/` application stays untouched and remains
the shipping front-end until the Rust application reaches parity.

## Goals / Non-Goals

**Goals:**

- Build a native Rust desktop workbench with `windows-reactor`.
- Reuse the C core through its existing C ABI; do not fork vector semantics.
- Match the current workbench feature set, including conversion, reverse fit,
  loop, keyboard, views, exports, themes, localization, and startup arguments.
- Produce a self-contained x64 output folder that runs without a separate
  Windows App SDK installation.
- Keep the C and Python test suites authoritative and add Rust-side parity
  checks.

**Non-Goals:**

- Rewriting the C core or the three CLI tools in Rust.
- Removing or modifying `ui/winui/` during this change.
- MSIX packaging. The first release target is a self-contained folder.
- Supporting architectures other than x64 in the first migration.
- Replacing the Python generators or data-authority rules.

## Decisions

### Use the official `windows-reactor` crate

Use `windows-reactor = "0.100"` and the matching `windows` crate version. Do
not depend on `windows-reactor-pre`; it is an unofficial pre-release mirror.
The official crate is still a preview, so pin the version and review release
notes before upgrading.

Alternative: use `egui`, `iced`, or Tauri. Rejected because the requirement is
native WinUI 3 through `windows-reactor`, and because those stacks would not
reuse the WinUI control model.

### Keep the C core behind a static C shim

Compile `ui/winui/core_wrap.c` (or a copied `ui/rust/core_wrap.c`) into a
static library with the `cc` crate in `build.rs`, then call the exported C ABI
from Rust. This keeps one executable and avoids shipping a separate DLL.

Alternative: load `ipa2vec_core.dll` with `libloading`. Keep this as a
debugging fallback for the first POC, but the shipping build uses static
linking.

`build.rs` will generate `src/vectors.h` and `src/readme_embed.h` when they are
missing by running the existing Python generators, or fail with a clear
message if Python is unavailable. Running `make gen` remains supported.

### Make the Rust engine wrapper UI-thread-only

The C core uses process-global state for the loaded scheme, metric, modules,
and width. The Rust wrapper will expose an `Engine` value whose methods take
`&mut self`, and all calls will run on the Reactor UI thread. Background work
must send a message back to the UI thread before touching the engine. This
avoids a global mutex and matches the current C# behavior.

Alternative: wrap every call in a `Mutex`. Rejected because it hides the
threading constraint and adds lock overhead to every conversion.

### Read width from the loaded scheme

The wrapper will call `ipa2v_ndim()` after `ipa2v_set_args()` and use that
value for every allocation and row stride. It will never assume 16
dimensions. The default scheme and `tongue.scheme` are both part of the parity
tests.

### Structure the UI as one root component and focused child components

The root `Workbench` component owns the input, output, selected view, theme,
language, and status. Child components own the soft keyboard, vector editor,
history, settings, and detail panels. Events become typed messages; `update`
mutates state and `view` returns the control tree. This follows the
`windows-reactor` component model and keeps the code-behind behavior out of
one giant file.

### Keep the existing build and test commands separate

Add `make rust-ui` for the Cargo build and `make rust-ui-test` for Rust tests
and FFI parity. Leave the existing `make test` target unchanged so the C and
Python gates keep their current meaning. Add a combined target only after the
Rust front-end reaches parity.

### Package with `windows-reactor-setup`

Use `windows-reactor-setup` from `build.rs` to stage the Windows App SDK
runtime next to the executable. Copy the fonts, icon, image assets, and the
three CLI tools into the output folder. The output directory is
`ui/rust/dist/` and is ignored by Git. MSIX packaging is deferred.

## Risks / Trade-offs

- **Preview API churn** → Pin `windows-reactor` 0.100 and isolate framework
  calls behind the UI modules so a future upgrade is contained.
- **No XAML reuse** → Keep `ui/winui/` running in parallel and port behavior
  panel by panel. Treat the existing XAML as the visual reference.
- **Custom pointer interactions** → Rebuild long-press pickers and the magnetic
  cursor with pointer events and explicit state. Prototype these early because
  they are the least declarative part of the current UI.
- **Acrylic and title-bar fidelity** → Use `WindowBackdrop::Mica` and
  `WindowVisuals`; for in-app acrylic and always-on-top behavior, call the
  native WinUI/Win32 APIs through the `windows` crate.
- **Engine global state** → Enforce UI-thread-only access and document it in
  the wrapper; add a test that runs conversions sequentially after changing
  schemes.
- **Build prerequisites** → The Rust MSVC toolchain needs the Visual Studio
  linker and Windows SDK. Run Cargo from a Developer Command Prompt or
  `VsDevCmd.bat`. Self-contained staging needs network access at build time.
- **Feature drift** → The C# front-end stays available, so missing Rust
  features do not block the existing release.

## Accepted Exceptions

The project owner accepted these exceptions on 2026-11-08:

- The framework has no font-family modifier, so the bundled Gentium font is
  loaded for availability but text falls back to the system UI font.
- The magnetic-cursor long-press pickers, hover cards, and in-app acrylic
  popovers are simplified to standard controls.
- The split is controlled by a slider instead of a draggable grip.
- Window position persistence, full localization of every label, MSIX, and
  non-x64 architectures are deferred.
- The clean Windows 10 1809 machine test is waived; the self-contained folder
  was launched and exercised on the development machine.

## Migration Plan

1. Create `ui/rust` with a minimal Mica window, title bar, and one conversion.
2. Add the static C shim, the Rust `Engine` wrapper, and parity tests for both
   schemes.
3. Rebuild the workbench shell: title bar, split panes, themes, localization,
   window state, and startup arguments.
4. Port the conversion, reverse, loop, keyboard, detail, history, views,
   export, and settings panels.
5. Add the self-contained packaging step and verify startup on a clean
   Windows 10 1809 x64 environment.
6. Run the full Rust and existing C/Python checks, then update the README and
   Makefile. Switch the default front-end only after parity is accepted.

Rollback is simple: the C# workbench remains in place, so the Rust front-end
can be removed or left experimental without affecting the shipped UI.
