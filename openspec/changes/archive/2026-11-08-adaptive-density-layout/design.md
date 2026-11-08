# Design

## Context

See `proposal.md` for the motivation. The accepted Rust workbench currently
renders a fixed title bar, a toolbar, and two equal-width panes. The left pane
contains the input, the action buttons, the format row, and every keyboard
group in one long scroll. The right pane contains output, reverse controls,
views, regional modules, symbol tools, files, and the split slider.

The current constants are generous: 96 DIP input height, 240 DIP output
height, 180 DIP view height, 10 DIP pane padding, 8 DIP stack spacing, and
36×30 DIP keyboard targets. The split ratio persists, but density, pane mode,
and collapse state do not.

## Goals / Non-Goals

**Goals:**

- Make Compact the default with more content above the fold.
- Keep primary actions and current output visible at 1280×820.
- Switch to a single-pane Input/Output/Tools layout below 1000 DIP.
- Make secondary sections and keyboard groups collapsible.
- Persist density, split, collapsed sections, and narrow-pane choice.
- Keep every existing workflow reachable with keyboard and pointer.

**Non-Goals:**

- Redesigning the C engine, conversion output, or CLI behavior.
- Changing the accepted visual identity, Mica backdrop, or theme colors.
- Adding new conversion features or data views.
- Replacing `windows-reactor` or adopting a new UI framework.
- Full localization of every label, which remains an accepted exception.

## Decisions

### Use a layout metrics table instead of scattered constants

Add a `layout` module with `Density::{Compact, Comfortable}` and a
`LayoutMetrics` struct. It supplies section spacing, pane padding, input
height, output height, view height, control height, and keyboard target size.
Views read metrics through the `Workbench` state instead of hard-coded values.

Compact uses tighter gaps but keeps interactive targets at least 32×32 DIP:
input 72 DIP, output 180 DIP, view 140 DIP, section spacing 4 DIP, pane
padding 6 DIP. Comfortable preserves the current spacious values.

Alternative: reduce individual constants in place. Rejected because it leaves
density inconsistent and makes a future theme or accessibility adjustment
harder.

### Center keyboard symbols inside their cells

Each keyboard cell is a `Button` whose content is a `TextBlock` with centered
horizontal and vertical alignment, no text wrapping, and a 16 DIP glyph. The
button uses centered content alignment and a zero `ButtonPadding` resource
override, so the glyph is positioned by the cell, not by the default chrome
inset. Cells grow to 52×44 DIP in Compact and 56×48 DIP in Comfortable; the
width keeps the widest label (`ŋ͡m`, about 23 DIP at 16 DIP text) clear of the
default 11 DIP content inset on each side.

Alternative: keep the default padding and shrink the font. Rejected because
padding, not font size, was pushing glyphs off center, and smaller glyphs hurt
legibility.

### Give each long list its own scroll region

Each pane is a `Grid` with fixed rows for the controls and a star-sized row for
the long list. The IPA input and keyboard filter sit in auto rows; the keyboard
groups scroll in the star row. On the right, output, reverse, and view output
sit in auto rows and the tools sections scroll in the star row. Narrow mode uses
the same grids inside a two-row layout, so the pane receives a bounded height.

Alternative: one `ScrollViewer` per pane. Rejected because scrolling the
keyboard moved the input out of view, and scrolling to the tools hid the
conversion output.

### Keep the primary action bar outside the scrolling panes

Move Convert, Loop, Reverse, the format choice, and the narrowness choice into
a compact action bar directly below the title bar. The bar is always visible,
including in the narrow layout, where it wraps into two rows. The output pane
stays visible at every width.

Alternative: keep actions in the input pane. Rejected because the input pane
scrolls and the primary action row would disappear when the keyboard is long.

### Use a single narrow pane with a modal keyboard

Wide windows (1000 DIP or more) keep the two-pane grid, split control, and
inline keyboard. Below that threshold the workbench shows one pane selected by
an Input/Output/Tools selector. The action bar adds a **Keyboard** button that
opens a modal panel: a fixed header and filter over a scrolling group list,
sized from the client area. The spare height below the input becomes an inline
Output unit with its own scrollbar, so the narrow Input pane never leaves a
blank block. Tool button rows group into fours, and the action bar wraps into
two rows.

Alternative: keep both panes side by side below the threshold. Rejected because
each pane becomes too narrow for the keyboard and the tool button rows.

Alternative: stack the panes vertically. Rejected because the fixed output units
consume the height and the tools region collapses.

### Implement collapse with section header buttons

A section header is a focusable Button with a disclosure glyph and an optional
count. The body is rendered only when the section is expanded. This avoids
depending on a specific `Expander` API in `windows-reactor` 0.100 and gives a
single keyboard-accessible control.

Keyboard groups use the same header component. Recent, favorites, and the
active group start open; other groups start collapsed. The filter remains
outside the scrolling group list so it stays visible.

Alternative: use native `Expander` controls. Rejected for this iteration
because the preview framework's expander surface is less predictable than a
plain button plus conditional body.

### Persist layout state in the existing settings file

Extend `Settings` with `density`, `narrow_pane`, and `collapsed_sections`.
Serde defaults make old settings files load cleanly. `Reset layout` restores
Compact, a 0.46 split, Input as the narrow pane, and the default collapsed set,
then saves.

Alternative: store layout in a separate file. Rejected because theme,
language, window size, and scheme already live in one settings object.

### Use pure layout helpers for testability

Keep breakpoint selection, default collapsed sections, density metrics, and
section-toggle logic in pure functions in the layout module. Unit-test them
without constructing WinUI controls. Use `winapp ui` checks for the rendered
wide/narrow states and persistence.

## Risks / Trade-offs

- **Information density versus readability** → Compact reduces whitespace but
  keeps 32 DIP targets and avoids clipping; Comfortable remains available.
- **Narrow layout hides content** → The Input/Output/Tools selector keeps every
  pane reachable, and the active choice persists.
- **Collapse state complexity** → Use stable string section IDs and a single
  toggle message; persist the set, not per-control booleans.
- **Keyboard group size** → Collapsed groups keep the keyboard usable while the
  filter still searches every group.
- **Window-size timing** → The initial view uses the saved window size until
  `on_window_size` reports the real client width; the breakpoint is re-evaluated
  on each size change.
- **Feature loss during redesign** → Keep the existing actions and panels, and
  add a feature-coverage check to the acceptance list.

## Migration Plan

1. Add the layout module and pure tests.
2. Extend settings and defaults with density, narrow pane, and collapsed
   sections.
3. Add the always-visible action bar and density/Reset controls.
4. Convert sections and keyboard groups to collapsible headers.
5. Add the 1000 DIP responsive switch and narrow selector.
6. Verify wide/narrow workflows, persistence, keyboard access, and the
   existing Rust and C/Python test suites.
