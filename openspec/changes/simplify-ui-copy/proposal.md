# Proposal

## Why

The workbench copy grew one label at a time. The title bar chains the status,
width, and version with em dashes and dots; the module manager packs parser,
keyboard, and symbol counts into one slash-and-dot line; rows add another
separator for "always on"; and Chinese mode still shows the English built-in
profile names `All on`, `All off`, and `Custom`. The result is harder to scan
than the controls it labels, especially in the narrow layout.

## What Changes

- Establish one plain copy style for the Rust workbench: short action labels,
  sentence-case statuses, and one fact per line or sentence.
- Remove decorative separator chains (`·`, `—`, `|`, and slash-joined counts)
  from interface copy. Data output such as vector rows, file paths, commands,
  and alignment results keeps its current format.
- Keep simple Unicode aids such as `→` and `✓` where they make direction or
  state easier to scan. They are not decorative separators and may replace a
  word, but they are not chained into status lines.
- Simplify the title bar: the app name in the title and the version in the
  subtitle; the status line carries the status instead of repeating it in the
  title bar.
- Replace bracket-only selection markers with one consistent active marker.
- Rewrite the module manager summary and rows as plain lines, and localize the
  built-in profile names and `Custom` in Chinese.
- Rename ambiguous controls, including "Favorite filter", and tighten
  placeholders and empty-state hints.
- Fix the workbench help text: use the real `vec4ipa-ui` name, remove pipe and
  arrow shorthand where a comma reads better, and stop printing a fixed
  `16-D` for a runtime-width scheme.
- Add copy-formatting helpers and tests so the separator and localization
  rules do not regress.

No conversion, keyboard, module, or persistence behavior changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `desktop-workbench`: add requirements for concise copy, separator restraint,
  consistent selection and status wording, and localized built-in profile
  names.

## Impact

- `ui/rust/src/app.rs`: labels, statuses, title bar, module manager, selection
  markers, placeholders, and status-line composition.
- `ui/rust/src/copy.rs` (new): copy formatting helpers and tests.
- `ui/rust/src/modules.rs`: keyboard descriptions and profile display labels.
- `ui/rust/src/startup.rs`: workbench help text.
- `ui/rust/src/layout.rs`: pane selection labels if the marker helper needs it.
- `README.md`, `ui/rust/README.md`, and `AGENTS.md`: copy conventions and
  verification notes.
- No changes to the C core, CLI tools, installer layout, or persisted ids.
