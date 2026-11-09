# Tasks

## 1. Copy helpers

- [x] 1.1 Add `ui/rust/src/copy.rs` with helpers for the app title, subtitle,
  active marker, built-in profile labels, module summary lines, module row
  metadata, and status sentences. Verify unit tests cover both languages and
  reject `·`, `—`, `|`, and slash-joined interface counts.
- [x] 1.2 Declare the module in `main.rs` and add tests that built-in profile
  ids still serialize unchanged while their display labels localize. Verify
  `cargo test` passes.

## 2. Title, status, and selection

- [x] 2.1 Set the window title to the app name and the subtitle to version plus
  runtime width, with no status or separator chain. Verify the title-bar unit
  helper and the startup status line.
- [x] 2.2 Replace bracket-only markers for format, narrowness, pane, profile,
  and module selection with the single active marker. Verify exactly one marker
  can be produced for a choice set in the copy tests.
- [x] 2.3 Rewrite module, profile, file, export, and keyboard statuses as plain
  sentences, keeping paths and engine detail after one colon. Verify the status
  helpers and the existing interaction tests.
- [x] 2.4 Keep or add simple Unicode aids where they replace words, including
  `→` in directional labels such as `Vector → IPA` and `IPA → vectors`, without
  chaining them into status lines. Verify the copy tests allow the aids and
  still reject decorative separator chains.

## 3. Module manager, keyboard, and help

- [x] 3.1 Render the module summary as separate parser, keyboard, and symbol
  lines; render each module row as a description sentence plus a symbols
  sentence, and say `Always on` in words. Verify the copy tests and the module
  manager rendering.
- [x] 3.2 Display built-in profiles through the localized labels in the profile
  row, active-profile text, and statuses, while settings keep `All on`,
  `All off`, and `Custom`. Verify the profile persistence test and a language
  switch test.
- [x] 3.3 Tighten placeholders and ambiguous labels, including `Favorite
  filter`, and update the workbench help to use `vec4ipa-ui`, commas instead of
  pipes, `to` instead of `->`, and no fixed `16-D` width. Verify `--help` output
  and the startup parser tests.

## 4. Documentation and review

- [x] 4.1 Document the copy rules (short labels, one fact per line, one active
  marker, localized built-in profiles) in `README.md`, `ui/rust/README.md`, and
  `AGENTS.md`. Verify `check_doc_paths.py` and `check_readme_tests.py` pass.
- [ ] 4.2 Review every workbench surface in English and Chinese at wide and
  narrow widths, including the module manager, title bar, status line, keyboard
  popup, and help. Verify no interface line uses a decorative separator chain
  and no control loses its meaning after shortening.

## 5. Integration

- [x] 5.1 Run `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`,
  `cargo test`, `make test`, and `make verify-commit`. Verify all pass and no
  data-output or persisted-value change appears in the diff.

## Workflow follow-up

- Commit the change after the user approves the copy review.
- Archive the change after the release checks and approval.
