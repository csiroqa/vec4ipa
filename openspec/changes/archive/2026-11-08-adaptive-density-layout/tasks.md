# Tasks

## 1. Layout model and settings

- [x] 1.1 Add a `layout` module with `Density`, `LayoutMetrics`, the 1000 DIP
  wide/narrow breakpoint, and default collapsed section IDs. Verify pure unit
  tests for metrics, breakpoint choice, and defaults.
- [x] 1.2 Extend `Settings` with `density`, `narrow_pane`, and
  `collapsed_sections` with serde defaults and backward-compatible loading.
  Verify a settings file without the new fields loads and saves.
- [x] 1.3 Add a Reset layout action that restores Compact, the 0.46 split,
  Input as the narrow pane, and the default collapsed set. Verify the reset
  values are written to the settings file.

## 2. Primary action bar and density

- [x] 2.1 Move Convert, Loop, Reverse, the format choice, and the narrowness
  choice into an always-visible action bar below the title bar. Verify the
  controls remain visible at 1280×820 and in the narrow layout.
- [x] 2.2 Add a Compact/Comfortable density toggle and Reset layout control to
  the toolbar. Verify switching density changes spacing and heights without a
  restart.
- [x] 2.3 Apply compact input, output, view, section, and pane metrics from the
  layout module. Verify no label is clipped and every target is at least
  32×32 DIP.
- [x] 2.4 Render every keyboard symbol in a centered cell with the full glyph
  visible. Verify horizontal and vertical centering and that no cell clips or
  overlaps its neighbour in both densities.

## 3. Collapsible sections

- [x] 3.1 Add a reusable section header button with disclosure glyph, title,
  optional count, and expanded/collapsed state. Verify pointer and keyboard
  activation toggle the body.
- [x] 3.2 Convert views, regional modules, symbol tools, files and exports,
  history, and examples to collapsible sections. Verify secondary sections
  start collapsed and remain reachable.
- [x] 3.3 Make keyboard groups collapsible with symbol counts; keep recent,
  favorites, and the active group open by default. Verify the filter stays
  visible and collapsed groups remain searchable.
- [x] 3.4 Persist collapsed section IDs across restart. Verify a collapsed
  section stays collapsed and Reset layout reopens the defaults.

## 4. Responsive layout

- [x] 4.1 Add the `Wide`/`Narrow` layout switch at 1000 DIP using the current
  client width. Verify two panes above the threshold and one pane below it.
- [x] 4.2 Add the narrow Input/Output/Tools selector. Below the threshold,
  replace the inline keyboard with a Soft keyboard button that opens a modal
  panel with a fixed filter and scrolling groups, and group tool buttons into
  rows of four.
- [x] 4.3 Preserve input, output, history, and view text across resize and
  narrow-pane changes. Verify data survives a resize across the threshold.
- [x] 4.4 Verify every existing workflow is reachable in the narrow Tools and
  Output panes: views, symbol tools, files, exports, regional modules,
  conversion output, reverse output, and view text.
- [x] 4.5 Give the keyboard groups and the tools sections their own scroll
  regions, keeping the input, filter, output, reverse, and view units fixed.
  Verify scrolling one list does not move the fixed units.

## 5. Accessibility and visual verification

- [x] 5.1 Add the new density, collapse, keyboard, and reset controls to the
  keyboard focus order with a visible focus indicator. Verify keyboard-only
  operation for each control.
- [x] 5.2 Capture wide and narrow screenshots at Compact and Comfortable
  densities. Verify the primary action bar and output are visible at the
  documented window sizes.

## 6. Integration and documentation

- [x] 6.1 Run `cargo fmt --check`, `cargo clippy -- -D warnings`, and
  `cargo test` in `ui/rust`. Verify all pass.
- [x] 6.2 Run the repository `make test` and `make verify-commit` suites.
  Verify no C or Python behavior changed.
- [x] 6.3 Build `ui/rust/package.bat` and launch `ui/rust/dist/vec4ipa-ui.exe`.
  Verify the packaged app uses the new layout and still converts, reverses,
  loops, and exports tools.
- [x] 6.4 Update `ui/rust/README.md` and the main README with density,
  responsive layout, collapse behavior, and Reset layout. Verify
  `check_doc_paths.py` and `check_readme_tests.py` pass.

## Workflow follow-up

- Archive the change after the layout acceptance checks pass and the user
  approves the new default density.
