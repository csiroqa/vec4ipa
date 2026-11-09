# Design

## Context

See `proposal.md` for the motivation. `ui/rust/src/app.rs` holds most strings
as `self.t(english, chinese)` pairs and builds derived lines with `format!`.
`modules.rs` owns keyboard descriptions, `startup.rs` owns the workbench help,
and the built-in profile names live in `settings.rs` as both persisted ids and
display text. There are unit tests for behavior but no GUI automation, so the
copy rules need pure helpers that can be tested without a window.

## Goals / Non-Goals

**Goals:**

- One copy style that is short, plain, and free of decorative separator chains.
- One active marker for every selected control or row.
- Built-in profile labels that follow the interface language without changing
  persisted ids.
- Pure tests for the composed copy that replaced inline `format!` chains.

**Non-Goals:**

- Redesigning controls, layout, or interaction flow.
- Translating the installer, CLI tools, or documentation.
- Changing vector, IR, JSON, CSV, alignment, or command output formatting.
- Changing settings keys or the persisted profile ids.

## Decisions

### Add a small copy module, not a full string catalog

Add `ui/rust/src/copy.rs` for the strings that are composed or repeated:

- app name, window title, and subtitle;
- the active marker and the selected-label helper;
- module summary lines and module row metadata;
- built-in profile display labels;
- status sentences for module, profile, file, and export actions.

Individual button labels stay at their call sites. A full catalog would touch
every line mechanically and separate a label from the code that gives it
meaning.

Alternative: keep composing strings inline and rely on review. Rejected
because the separator and localization rules would have no regression test.

### Use one active marker and plain state words

Selected formats, narrowness levels, panes, profiles, and modules use a single
trailing check mark: `Vectors ✓`, `3 ✓`, `Input ✓`, `All on ✓`. This replaces
the bracket pairs without adding a separator or another sentence.

State words carry the rest:

- module rows say `Always on` in their metadata;
- module rows that are off have no marker;
- the module summary uses `on` or `off` counts;
- profile names use the localized built-in label plus the marker when active.

Alternative: keep `[label]` and only remove other separators. Rejected because
brackets remain the noisiest part of dense controls such as the format and
narrowness rows.

### One fact per line for the title bar and module summary

The window title becomes `vec4ipa Workbench`. The title-bar subtitle becomes
`Version 4.0.0, 16 dimensions` (`版本 4.0.0，16 维`), with the runtime width
still visible. The current status moves to the status line only; it is no
longer repeated in the title bar.

The module summary becomes three short lines:

```text
Parser modules: 2 of 9 on
Keyboard groups: 6 of 6 on
Symbols: 123
```

Chinese uses `解析模块：9 个中已启用 2 个`, `键盘组：6 个中已启用 6 个`, and
`符号：123 个`. A module row reads `Description. 4 symbols.` rather than
`Description · 4 symbols`.

Alternative: one sentence for the summary. Rejected because it becomes long in
the narrow pane and hides the per-kind counts.

### Treat built-in profile names as ids, not display text

Keep `All on`, `All off`, and `Custom` as the persisted names. Add
`copy::profile_label(name, zh)`:

| id | English | Chinese |
|---|---|---|
| `All on` | `All on` | `全部启用` |
| `All off` | `All off` | `全部禁用` |
| `Custom` | `Custom` | `自定义` |

User-named profiles pass through unchanged. Every place that displays a profile
uses the helper. Persistence and profile matching continue to use the id.

Alternative: rename the stored profiles to the Chinese strings. Rejected
because language switching would change the active profile and corrupt settings.

### Ban decorative separators in interface copy

Interface lines use at most one of `·`, `—`, `|`, or `/`, and `·` and `—` are
not used in new copy. A slash remains valid in a file path, command, vector
row, or other data output. Counts are words or separate lines, not slash
fractions.

Simple Unicode aids are allowed when they replace a word: `→` for direction,
`⇄` for a two-way exchange, and `✓` for selection. They are not separators, but
they follow the same restraint: one aid per label, never a chain such as
`A → B → C` in a status line. Existing directional labels such as
`Vector → IPA` and `IPA → vectors` keep their arrow.

Status messages are sentence-cased and end with a period in English or `。` in
Chinese. Technical detail may follow one colon, for example
`Scheme file not found: D:\...\custom.scheme`. Internal ids such as
`parser:americanist` never appear in user-facing copy.

### Update help text separately from layout copy

`startup::help_text` keeps the option list but uses the real `vec4ipa-ui` name,
removes pipe-separated value lists, replaces `->` with `to`, and says
`vector to IPA` instead of a fixed `16-D` width. Option parsing does not change.

## Risks / Trade-offs

- **A check mark may read poorly to some screen readers** → keep the adjacent
  state word in the same row, and test the rendered labels in both languages.
- **Short labels can become ambiguous** → keep the action and its object up to
  three words; do not reduce `Open IPA file` to `Open`.
- **Separate summary lines take more vertical space** → the module manager is
  already scrollable; the narrow layout gains the most clarity.
- **Localized profile labels could leak into settings** → keep the display
  helper read-only and add a test that settings still serialize the stable ids.
- **Copy changes can break tests that assert exact strings** → update affected
  tests and add the copy-helper tests in the same change.
