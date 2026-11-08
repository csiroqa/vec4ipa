# Rust workbench

The Rust workbench is the accepted front-end for the vec4ipa migration. It
uses `windows-reactor` and shares the parser, metric, reverse fit, and
inventory behavior with the CLI tools through the `core_wrap.c` C ABI. The
WinUI C# workbench remains in `ui/winui/` as a reference implementation.

## Build

```bat
build.bat build     REM debug build
build.bat test      REM cargo test
package.bat         REM release build plus self-contained dist\
```

`build.bat` loads `VsDevCmd.bat`, then runs Cargo. The build needs the Rust
MSVC toolchain, the Visual Studio C++ build tools, and the Windows SDK.
`build.rs` generates the C headers, compiles the C shim, and stages the
Windows App SDK runtime with `windows-reactor-setup`.

## Packaging

`package.bat` writes `dist\` with the executable, staged Windows App SDK
runtime, WinUI resource folders, fonts, icon, assets, and the three CLI tools.
The folder is self-contained for x64 Windows 10 1809 or later.

## Parity with the WinUI workbench

| Area | Status | Notes |
|---|---|---|
| Forward conversion | Complete | Vectors, two-layer IR, JSON; matches the CLI. |
| Reverse conversion | Complete | Batch rows and five narrowness levels. |
| Loop | Complete | Tone annotations are preserved as `tone=(…)` groups. |
| Soft keyboard | Complete | Groups, search by symbol or name, IPA-chart order, persistent favorites, hover cards. |
| Keyboard mode | Complete | Topmost non-activating panel; SendInput Unicode with a clipboard fallback. |
| Symbol tools | Complete | Query, compare, weighted distance, alignment. |
| Views | Complete | Table, modules, stats, weights, effective weights, axes, docs. |
| History and examples | Complete | Bounded history; example inputs. |
| Files and exports | Complete | Batch file conversion, save, CSV, IR, tool export, command display. |
| Window | Complete | Mica, TitleBar, themes, English/Chinese, pin, size/state persistence. |
| Startup arguments | Complete | IPA, reverse, query, narrowness, theme, scheme, metric, tool export. |
| Engine parity | Complete | Width, values, UTF-8 paths, errors, and sequential scheme changes are tested. |
| Self-contained packaging | Complete | `windows-reactor-setup` plus asset and tool staging. |

## Layout

The workbench defaults to **Compact** density: tighter pane padding, a 72 DIP
input box, and 32 DIP minimum targets. **Comfortable** restores the earlier
spacing and heights. Both modes apply immediately, and the toolbar toggle shows
the active mode.

Above 1000 DIP the workbench shows two panes, a split slider, and the keyboard
inline in the input pane. Below 1000 DIP it shows one pane chosen by an
**Input / Output / Tools** selector. The action bar wraps into two rows, tool
buttons group into fours, and a **Keyboard** button in the action bar opens the
keyboard as a modal panel with a fixed filter and scrolling groups; symbols
insert into the input behind it. The rest of the Input pane is an inline
**Output** unit with its own scrollbar, so spare height is never blank.

Secondary sections collapse from their header buttons: views, regional modules,
symbol tools, files and exports, history, examples, and most keyboard groups.
Each header shows an item count, and recent, favorites, and consonants start
open. Density, split, and collapsed section ids persist in
`%LOCALAPPDATA%\vec4ipa\rust-ui.json`.

Scrolling is per unit, not per pane. The IPA box and filter stay fixed while the
keyboard groups scroll; output, reverse, and view text stay fixed while the tools
sections scroll on their own.

**Keyboard mode** turns the window into a topmost panel that does not take
focus. Pick the target application once, then click symbols to type IPA into it;
SendInput handles the text and the clipboard + Ctrl+V path is the fallback.
Exit returns to the workbench. Elevated and secure-desktop targets reject the
input and the status line says so.

**Reset layout** restores Compact, the 0.46 split, and the default collapsed set.

Keyboard symbols are centered in their cells at 16 DIP. Compact cells are 52×44
DIP and Comfortable cells are 56×48 DIP, so multi-codepoint symbols such as
`ŋ͡m` clear the default content inset. The grid picks 1–12 columns from the pane
width, which keeps every symbol unclipped.

## Accepted differences

The project owner accepted these differences on 2026-11-08:

- **Font application**: the workbench loads the bundled Gentium font and warns
  when it is missing, but `windows-reactor` 0.100 has no font-family modifier.
  Text uses the system UI font until the framework exposes one.
- **Long-press pickers**: the Rust workbench uses buttons and a slider for
  narrowness, format, and split control. The magnetic-cursor long-press
  interaction is not ported. Keyboard hover cards use the framework tooltip.
- **In-app acrylic**: the window uses Mica and theme resources. In-app acrylic
  popovers are approximated with standard controls.
- **Window placement**: size, theme, language, and pin state persist. Position
  persistence needs the newer placement API.
- **Localization**: the main workflow is translated. Some format, view, and
  example labels remain English.
- **MSIX**: deferred. The self-contained folder is the current release shape.
- **Architecture**: x64 only for the first migration.

## Verification

- `cargo test` covers the engine contract, both schemes, UTF-8 paths, invalid
  metrics, non-finite vectors, segment limits, CLI parity, keyboard search
  terms, group order, favorite persistence, UTF-16 encoding, and the delivery
  fallback (34 tests).
- `cargo fmt --check` and `cargo clippy -- -D warnings` pass.
- The repository `make test` and `make verify-commit` suites pass.
- `dist\vec4ipa-ui.exe` launches, converts, reverses, loops, queries, searches
  and filters the keyboard, restores favorites after a restart, and types IPA
  into another application through keyboard mode.
- The clean Windows 10 1809 machine test is waived by the project owner. The
  self-contained folder was launched and exercised locally.
