# Proposal

## Why

The Rust workbench currently spreads controls across two long scrolling
columns. The soft keyboard takes most of the left column, while views, symbol
tools, regional modules, and file actions sit below the fold. The layout also
keeps the same two-column split at every window width, which wastes space on
large displays and clips controls on narrow ones. Users need more information
on screen and faster access to the actions they use most.

## What Changes

- Add **Compact** and **Comfortable** density modes. Compact becomes the
  default; it reduces section spacing, control padding, and fixed heights
  while keeping interactive targets at least 32×32 DIP.
- Add a responsive layout:
  - Wide windows keep two panes with a compact split control and an inline
    keyboard.
  - Below 1000 DIP the workbench shows one pane with **Input / Output /
    Tools** choices; the soft keyboard opens from a **Soft keyboard** button
    as a modal panel, and the action bar wraps into two rows.
  - The primary action row, the output, and the keyboard stay reachable
    without horizontal scrolling.
- Make secondary sections collapsible: keyboard groups, regional modules,
  views, symbol tools, files and exports, history, and examples. Recent,
  favorites, and the active keyboard group start open; other groups start
  collapsed.
- Replace the always-visible reaction controls with a compact action bar that
  keeps **Convert**, **Loop**, **Reverse**, the format choice, and the
  narrowness choice visible.
- Add group headers with symbol counts and a keyboard filter that stays visible
  while groups scroll.
- Persist density mode, collapsed sections, and the split ratio. Provide a
  **Reset layout** action.
- **BREAKING** for the default visual layout: the workbench opens denser and
  with secondary sections collapsed. No feature is removed, and every existing
  workflow remains reachable.
- Keep the C core, CLI behavior, generated data, and the C# reference UI
  unchanged.

## Capabilities

### New Capabilities

- `desktop-layout`: responsive pane composition, density modes, collapsible
  sections, control sizing, layout persistence, and keyboard-accessible
  navigation for the workbench.

### Modified Capabilities

None.

## Impact

- `ui/rust/src/app.rs`: view composition, section components, keyboard groups,
  responsive pane selection, and action bar.
- `ui/rust/src/settings.rs`: new persisted layout fields and defaults.
- New layout helpers and tests under `ui/rust/src/`.
- No changes to `src/ipa2vec_core.h`, `core_wrap.c`, the CLI tools, or
  `ui/winui/`.
- UI verification: narrow and wide window checks, density toggle, collapse
  persistence, keyboard reachability, and existing conversion workflows.
