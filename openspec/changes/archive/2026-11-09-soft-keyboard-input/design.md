# Design

## Context

See `proposal.md` for motivation. The Rust workbench already loads the keyboard
inventory from the C core (`keyboard_*`, `consonant_positions`,
`vowel_positions`, `modifier_tiers`) and renders it with the shared cell and
popup components. It has no description-aware search, no separate letter
group, no favorite persistence, and no way to send input outside the window.

`win32.rs` already owns window styling and file helpers, and the engine exposes
`query` text that contains the feature description. The C# reference workbench
defines the target behavior: a term map for Chinese feature names, a manner and
airstream order for groups, and a favorites file under `%APPDATA%`.

## Goals / Non-Goals

**Goals:**

- Match the C# keyboard search, grouping, and favorites behavior.
- Add a keyboard mode that injects IPA into the application that had focus.
- Keep the workbench usable while keyboard mode is active.
- Keep all keyboard data and behavior in the Rust front-end.

**Non-Goals:**

- Replacing the system IME or implementing a TSF text service.
- Injecting into elevated or secure-desktop windows.
- Changing the C core, the CLI tools, or the WinUI reference.
- Porting the magnetic long-press pickers.

## Decisions

### Port the term map for searchable Chinese names

Add `terms.rs` with the C# `TermMap` entries and a token-boundary replacement
function. Building search text per symbol translates the query description once
and caches it with the keyboard model. Search lowercases Latin text and matches
the symbol, the English description, and the translated Chinese term.

The C# reorders place before manner for Chinese names; the filter only needs
substrings, so token-wise translation is enough. Document that simplification
in the module.

Alternative: match only symbols. Rejected because the keyboard is unusable
when the user knows the feature but not the character.

### Build the keyboard model once, then render it

Add a `Keyboard` model built at startup and after a scheme change:

- Favorites and recent stay first.
- Consonants sort by manner weight (`plosive`, `affricate`, `fricative`,
  `nasal`, `lateral`, `tap/flap`, `trill`, `approximant`) then by the place
  position from `consonant_positions`.
- Non-pulmonic entries keep the airstream class that the C core writes after a
  tab, then sort by class, manner, place. The class is currently stripped for
  display; keep it in the model and strip it only when rendering.
- Vowels sort by row then column from `vowel_positions`.
- Diacritics and letters split with `is_modifier_symbol`; diacritics sort by
  `modifier_tiers`, gain a `◌` key, and render at 20 DIP instead of 16.
- The C# tie-composite list is appended to consonants and deduplicated against
  the scheme entries.

Alternative: sort inside each render. Rejected because every keystroke
rebuilds the view and would repeat the query and sort work.

### Persist favorites beside the workbench settings

Store one symbol per line in `%APPDATA%\vec4ipa\favorites.txt`, matching the C#
path. Load at startup, trim empty lines, deduplicate, cap at 200, and rewrite
the file on every change through a temporary file and rename. A read or write
failure keeps the in-memory list and reports the error in the status line. The
favorite action itself is unchanged.

Alternative: store favorites in `rust-ui.json`. Rejected because the file is
shared with the C# workbench and should keep its format.

### Keyboard mode is a window state, not a second process

Add `keyboard_mode: bool` and `window_handle: isize` to the workbench. Entering
the mode:

1. Captures the workbench window handle from `GetForegroundWindow()`.
2. Applies `WS_EX_NOACTIVATE` and topmost placement with `SWP_NOACTIVATE`.
3. Renders a keyboard overlay over the toolbar and panes: header with mode
   state and Exit, the group list, and a status line. The title bar and root
   grid stay in place so WinUI never has to clear and re-create the title bar.
4. Leaves the window in the foreground until the user clicks the target
   application once; from then on, clicks on the keyboard do not take focus.

Every symbol goes to whatever window is in the foreground when it is picked.
If that window is the workbench itself, the status line asks the user to click
the target application first. Leaving the mode removes `WS_EX_NOACTIVATE`,
restores the pinned state, and reactivates the workbench window.

Alternative: capture the previous foreground window and reactivate it on
entry. Rejected because the click that opens keyboard mode already activates
the workbench, so the previous window is gone, and a background foreground
tracker would add a thread and Windows focus rules for little gain.

Alternative: a separate keyboard process. Rejected because it would duplicate
the keyboard model, settings, and localization.

### Inject with SendInput, fall back to the clipboard

Add `input.rs`:

- Encode every Unicode scalar as UTF-16 units and send `KEYEVENTF_UNICODE`
  down/up pairs in one `SendInput` call.
- If the returned event count is lower than requested, or the target is
  elevated, fall back to `CF_UNICODETEXT` on the clipboard followed by
  `Ctrl+V`, and report the fallback.
- Leave the injected text on the clipboard; do not restore the previous
  content, because restoring races with the target's paste.
- Report rejected input instead of claiming success.

Alternative: clipboard only. Rejected because it overwrites the clipboard for
every symbol. Alternative: UI Automation value patterns. Rejected because many
editors and games expose no writable pattern.

## Risks / Trade-offs

- Elevated or secure-desktop targets reject both transports → report the
  limitation in the status line and document it.
- `WS_EX_NOACTIVATE` can complicate dragging and closing → verify the header,
  Exit, and window drag still work in keyboard mode.
- SendInput requires the target to stay foreground → if focus moves, stop
  sending and report it.
- The term table duplicates C# data → add a parity test for representative
  terms and keep the table in one Rust module.
- A non-activating topmost window can cover the target → keep the panel
  compact and remember its size.
