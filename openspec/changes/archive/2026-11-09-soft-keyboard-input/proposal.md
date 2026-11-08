# Proposal

## Why

The Rust workbench's soft keyboard is a simplified port of the C# reference.
It filters only by symbol text, groups every modifier together, keeps
favorites for the session only, and can type only into the workbench's own
input box. Users also need to enter IPA into other applications without
leaving the keyboard.

## What Changes

- Search matches the symbol, the English feature description, and the
  Chinese term when the UI is Chinese.
- Groups follow the IPA chart: consonants by manner then place; non-pulmonic
  by airstream, manner, place; vowels by tongue position; letters and
  diacritics separated, diacritics ordered by tier with a dotted-circle key
  and a larger glyph.
- Favorites persist in `%APPDATA%\vec4ipa\favorites.txt`, deduplicated and
  capped, and load at startup.
- Add a **keyboard mode**: an overlay turns the window into a topmost,
  non-activating keyboard panel, and each symbol is injected into the
  application that is in the foreground when the symbol is picked.
- Inject with SendInput Unicode; when injection fails, fall back to the
  clipboard and Ctrl+V, and report the fallback in the status line.
- The workbench keeps its conversion, reverse, view, and export workflows;
  keyboard mode is an additional state, not a replacement.
- No changes to the C core, the CLI tools, or the WinUI reference.

## Capabilities

### New Capabilities

- `ipa-keyboard-input`: keyboard mode that injects IPA into the foreground
  application, with focus preservation and a clipboard fallback.

### Modified Capabilities

- `desktop-workbench`: soft keyboard search covers descriptions and Chinese
  terms, group ordering follows the IPA chart, and favorites persist across
  sessions.

## Impact

- `ui/rust/src/app.rs`, `ui/rust/src/win32.rs`, and new `terms.rs`,
  `keyboard.rs`, `favorites.rs`, and `input.rs` modules.
- `ui/rust/README.md` parity table.
- Windows-only input injection; elevated target windows may reject input.
- No changes to `src/`, `tools/`, or `ui/winui/`.
