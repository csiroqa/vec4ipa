# Tasks

## 1. Search across descriptions

- [x] 1.1 Port the C# term map into `terms.rs` with token-boundary
  translation. Verify unit tests cover a consonant, a vowel, and a tone term.
- [x] 1.2 Cache per-symbol search text (symbol, English name, Chinese term)
  with the keyboard model. Verify a test returns all three for `ʃ`.
- [x] 1.3 Match the filter against symbol, English name, and term, ignoring
  Latin case. Verify `plosive`, `擦音`, and `ʃ` each narrow the groups.

## 2. Keyboard groups

- [x] 2.1 Build the keyboard model at startup and after scheme changes.
  Verify a scheme reload rebuilds every group and count.
- [x] 2.2 Sort consonants by manner then place, non-pulmonic by airstream,
  manner, place, vowels by position, diacritics by tier. Verify ordering.
- [x] 2.3 Split letters from diacritics, add the dotted-circle key and tie
  composites, and render diacritics at 20 DIP. Verify membership and size.
- [x] 2.4 Keep the non-pulmonic airstream class for sorting while displaying
  only the symbol. Verify ejective, implosive, click, percussive order.

## 3. Favorites

- [x] 3.1 Read and write `%APPDATA%\vec4ipa\favorites.txt` with trim, dedupe,
  and a 200-entry cap. Verify round-trip and cap tests.
- [x] 3.2 Load at startup and rewrite on change through a temporary file.
  Verify restart persistence and that an I/O error keeps the memory list.
- [x] 3.3 Verify duplicate favorites appear once in the group and once in the
  file.

## 4. Keyboard mode

- [x] 4.1 Add the keyboard-mode state and an overlay with groups, status, and
  Exit. Verify the overlay renders and Exit returns to the workbench.
- [x] 4.2 Apply `WS_EX_NOACTIVATE` and topmost placement to the workbench
  window on entry, and restore the styles on exit. Verify clicks do not take
  focus.
- [x] 4.3 Verify the workbench layout and pinned state return after leaving
  the mode.

## 5. Injection

- [x] 5.1 Add `input.rs` SendInput Unicode injection with surrogate pairs and
  an inserted-event count check. Verify BMP and supplementary symbols.
- [x] 5.2 Add the clipboard + Ctrl+V fallback and a status notice. Verify the
  fallback path with a simulated SendInput failure.
- [x] 5.3 Report rejected input when both transports fail instead of claiming
  success. Verify with a simulated SendInput and clipboard failure.

## 6. Integration and docs

- [x] 6.1 Run `cargo fmt`, `clippy -D warnings`, and `cargo test`. Verify all
  pass.
- [x] 6.2 Update `ui/rust/README.md` parity and accepted differences for
  search, groups, favorites, and keyboard mode. Verify doc path check.
- [x] 6.3 Build `dist` and inject into a plain editor. Verify symbols land at
  the caret and the elevated case reports rejection.

## Workflow follow-up

- Archive the change after the acceptance checks and the user's approval.
