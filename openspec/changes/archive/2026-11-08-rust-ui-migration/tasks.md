# Tasks

## 1. Scaffold the Rust project

- [x] 1.1 Create `ui/rust/` as a Cargo application with pinned
  `windows-reactor = "0.100"`, `windows`, `cc`, and supporting dependencies.
  Verify with `cargo check` from a Visual Studio developer shell.
- [x] 1.2 Add `build.rs` that compiles the C shim into a static library and
  links it into the Rust binary. Verify with `cargo build` and a smoke call to
  `ipa2v_ndim`.
- [x] 1.3 Make `build.rs` generate `src/vectors.h` and `src/readme_embed.h`
  from a clean checkout, or fail with a clear `make gen` instruction. Verify by
  deleting both headers and building again.
- [x] 1.4 Add a `rust-ui` Makefile target and `ui/rust/.gitignore` entries for
  `target/` and `dist/`. Verify `make rust-ui` builds the Rust front-end.
- [x] 1.5 Document Rust, MSVC, Windows SDK, and Windows App SDK prerequisites
  in `README.md` and `AGENTS.md`. Verify `check_doc_paths.py` and
  `check_readme_tests.py` still pass.

## 2. Engine FFI and parity

- [x] 2.1 Implement the Rust `Engine` wrapper for argument parsing, width,
  forward conversion, tone data, reverse fit, query, table, modules, stats,
  metric loading, effective weights, IR, JSON, and distance. Verify with a
  smoke test that covers every exported function used by the UI.
- [x] 2.2 Implement UTF-8 argument and path marshalling for schemes, metrics,
  output files, and school modules. Verify with a scheme file whose path
  contains Chinese characters.
- [x] 2.3 Enforce the runtime width, segment limit, finite-vector check, and
  error propagation in the wrapper. Verify with `spec_next.scheme`,
  `tongue.scheme`, an invalid metric, and a `NaN` vector test.
- [x] 2.4 Add a parity probe that compares Rust forward and reverse results
  against `vec4ipa`/`vec2ipa` for both schemes, value for value. Verify with
  `cargo test` or the dedicated parity script.
- [x] 2.5 Add a sequential-access test that changes scheme and metric between
  conversions. Verify that results use the newly loaded state and never mix
  two schemes.

## 3. Application shell and appearance

- [x] 3.1 Build the root component with a Mica window, custom `TitleBar`, icon,
  and responsive client size. Verify the window launches and the title bar
  drags, minimizes, maximizes, and closes.
- [x] 3.2 Implement system/light/dark themes and the English/Chinese UI switch.
  Verify both themes and both languages update without a restart.
- [x] 3.3 Implement the resizable split panes, always-on-top toggle, and
  persistent window state. Verify the state restores after restart and the
  always-on-top state matches the window behavior.
- [x] 3.4 Implement CLI-compatible startup arguments for IPA, reverse vector,
  query, narrowness, theme, and tool export. Verify each argument through a
  launched instance.
- [x] 3.5 Load the bundled Gentium font and application assets, with a system
  fallback when an asset is missing. Verify text rendering and a missing-font
  warning.

## 4. Conversion and symbol panels

- [x] 4.1 Implement forward conversion with vector, two-layer IR, and JSON
  output plus the format picker. Verify the output against `ipa2vec` for typed,
  clicked, and pasted input.
- [x] 4.2 Implement the vector editor, batch reverse input, and narrowness
  picker. Verify multi-row results and all five narrowness levels against
  `vec2ipa`.
- [x] 4.3 Implement the IPA → vectors → reverse loop and tone round-trip.
  Verify `tone=(…)` groups survive the loop unchanged.
- [x] 4.4 Implement the grouped IPA soft keyboard with filtering, recent
  symbols, favorites, and the modifier-before-base guard. Verify each group,
  filter, and guard case.
- [x] 4.5 Implement symbol details, symbol comparison, weighted distance, and
  sequence alignment. Verify results against the corresponding CLI commands.
- [x] 4.6 Implement bounded history and example inputs. Verify entries restore
  their input and output and the history limit is enforced.

## 5. Inventory, settings, and exports

- [x] 5.1 Implement the base table, regional modules, statistics, metric
  weights, effective weights, and module enablement views. Verify each view
  against `vec4ipa`.
- [x] 5.2 Implement runtime scheme and metric loading from the settings UI.
  Verify the displayed width, axes, and weights change after loading.
- [x] 5.3 Implement file batch conversion, output saving, CSV export, and
  layer1/layer2 IR export. Verify the exported files have the documented
  format and encoding.
- [x] 5.4 Implement CLI tool export and command-line display for the current
  input. Verify the exported tools run and the displayed command reproduces
  the workbench result.

## 6. Self-contained packaging

- [x] 6.1 Add `windows-reactor-setup` to `build.rs` so the Windows App SDK
  runtime is staged next to the executable. Verify the output folder contains
  the runtime files and starts without a separate runtime install.
- [x] 6.2 Copy the fonts, icon, image assets, and three CLI tools into the
  output folder. Verify the workbench loads the font and exports the tools from
  the packaged folder.
- [x] 6.3 Make the packaged application report the same version as
  `IPA2VEC_VERSION` and start without network access. Verify with a network
  disabled launch.
- [x] 6.4 Add a documented release packaging command and ignore its output.
  Verify the command works from a clean checkout after `make gen`.

## 7. Integration and acceptance

- [x] 7.1 Run `cargo fmt --check`, `cargo clippy -- -D warnings`, and
  `cargo test` in `ui/rust`. Verify all pass.
- [x] 7.2 Run the existing `make test` and `make verify-commit` suites. Verify
  they still pass and no C or Python behavior changed.
- [x] 7.3 Walk the feature checklist against the current C# workbench and
  record every mismatch. Verify every current feature has a matching Rust
  behavior or a documented exception.
- [x] 7.4 Run the self-contained folder on a clean Windows 10 1809 x64
  environment and complete a conversion, reverse fit, keyboard input, and
  export. Verify all four workflows succeed.
- [x] 7.5 Update `README.md`, `AGENTS.md`, and the Makefile to describe the Rust
  front-end as the accepted UI. Verify `check_doc_paths.py`,
  `check_readme_tests.py`, and `check_doc_numbers.py` pass.

## Accepted exceptions

The project owner accepted these exceptions on 2026-11-08:

- **3.5 Font application**: the Rust UI loads the bundled Gentium font and
  warns on failure, but `windows-reactor` 0.100 has no font-family modifier.
  Text falls back to the system UI font.
- **7.4 Clean-machine test**: Windows Sandbox is not enabled on this machine.
  The self-contained `ui/rust/dist/` folder was launched and exercised
  locally; the clean-VM test is waived.
- **7.5 Accepted UI**: the Rust workbench is documented as the accepted
  front-end; `ui/winui/` remains as the C# reference implementation.

## Workflow follow-up

- Archive the change after the Rust front-end passes the acceptance checklist
  and the user approves switching the default UI.
