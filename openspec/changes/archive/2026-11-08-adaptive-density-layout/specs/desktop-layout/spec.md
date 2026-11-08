# Spec Delta

## Purpose

Provides a responsive, density-aware workbench layout that keeps primary
actions and output reachable while secondary tools remain available.

## ADDED Requirements

### Requirement: Density modes

The workbench SHALL offer Compact and Comfortable density modes, SHALL default
to Compact, and SHALL apply a mode without restarting the application.

#### Scenario: Switch to Comfortable

- **WHEN** the user selects Comfortable
- **THEN** spacing, control padding, and fixed heights increase immediately

#### Scenario: Compact target size

- **WHEN** Compact is active
- **THEN** every interactive control has a click target of at least 32×32 DIP
  and no label is clipped.

### Requirement: Primary actions stay visible

The workbench SHALL keep Convert, Loop, Reverse, the format choice, and the
narrowness choice visible without vertical scrolling at the default window
size.

#### Scenario: Default window

- **WHEN** the workbench opens at 1280×820 DIP
- **THEN** the primary action row and the output area are visible without
  scrolling.

#### Scenario: Narrow window

- **WHEN** the window is narrowed below the responsive threshold
- **THEN** the primary action row remains visible in the active pane.

### Requirement: Responsive pane composition

The workbench SHALL use two panes with an inline keyboard when the client width
is at least 1000 DIP. Below that threshold it SHALL use one pane chosen by an
Input, Output, and Tools selector, wrap the action bar into two rows, group tool
buttons into rows of four, and open the soft keyboard from a Keyboard button as
a modal panel.

#### Scenario: Wide window

- **WHEN** the client width is 1000 DIP or greater
- **THEN** input and output appear side by side with the split control and the
  keyboard is inline in the input pane.

#### Scenario: Narrow window

- **WHEN** the client width is below 1000 DIP
- **THEN** only one of Input, Output, or Tools is visible at a time and no
  horizontal scrolling is required.

#### Scenario: Keyboard panel

- **WHEN** the user opens the soft keyboard in a narrow window
- **THEN** the keyboard appears over the window with its filter fixed and its
  groups scrolling, and Close returns to the pane.

#### Scenario: Resize across the threshold

- **WHEN** the user resizes the window across the threshold
- **THEN** the workbench switches layout without losing input, output, or
  history.

### Requirement: Independent scrolling

Each pane SHALL give its long list a separate scroll region. The keyboard
groups SHALL scroll inside the input pane while the IPA input and the keyboard
filter stay fixed. The tools sections SHALL scroll inside the tools region while
the output, reverse, and view units stay fixed. The narrow Input pane SHALL fill
the space below the input with an inline Output unit that scrolls on its own.

#### Scenario: Inline narrow output

- **WHEN** the narrow Input pane has spare height
- **THEN** the conversion output fills it with its own scrollbar

#### Scenario: Scroll the keyboard

- **WHEN** the user scrolls the keyboard groups
- **THEN** the IPA input and the symbol filter remain visible

#### Scenario: Scroll the tools

- **WHEN** the user scrolls the tools sections
- **THEN** the output and view units remain visible

### Requirement: Collapsible sections

The workbench SHALL make secondary sections collapsible, including keyboard
groups, regional modules, views, symbol tools, files and exports, history, and
examples.

#### Scenario: Default collapsed state

- **WHEN** the workbench opens
- **THEN** recent, favorites, and the active keyboard group are open and the
  remaining keyboard groups are collapsed.

#### Scenario: Preserve collapse state

- **WHEN** the user collapses a section and restarts the workbench
- **THEN** that section remains collapsed.

### Requirement: Keyboard density

The soft keyboard SHALL show a persistent filter, group headers with symbol
counts, and symbols in a compact grid with at least 32×32 DIP targets. Each
symbol cell SHALL center its glyph horizontally and vertically and SHALL render
that glyph without clipping or overlap from the cell edge or from adjacent
cells.

#### Scenario: Centered, unobscured symbols

- **WHEN** a keyboard group is expanded
- **THEN** every symbol glyph sits at the center of its cell and the whole glyph
  is visible

#### Scenario: Filter while groups scroll

- **WHEN** the user scrolls the keyboard and types in the filter
- **THEN** the filter stays visible and the visible groups update to matching
  symbols.

#### Scenario: Group count

- **WHEN** a keyboard group is collapsed or expanded
- **THEN** its header shows the number of symbols in the group.

### Requirement: Layout persistence and reset

The workbench SHALL persist the density mode, split ratio, and collapsed
sections, and SHALL provide a Reset layout action.

#### Scenario: Restore preferences

- **WHEN** the user restarts the workbench
- **THEN** the saved density, split, and collapsed sections are restored.

#### Scenario: Reset layout

- **WHEN** the user selects Reset layout
- **THEN** density, split, and collapsed sections return to their defaults and
  the defaults are saved.

### Requirement: Keyboard-accessible layout controls

The workbench SHALL expose density, collapse, keyboard, and reset actions
through the keyboard focus order with a visible focus indicator.

#### Scenario: Keyboard-only collapse

- **WHEN** the user reaches a section header with Tab and activates it with the
  keyboard
- **THEN** the section collapses or expands without a pointer.

### Requirement: Feature coverage

The responsive and compact layouts SHALL keep every existing workbench
workflow reachable.

#### Scenario: Narrow Tools

- **WHEN** the window is narrow
- **THEN** views, symbol tools, files, exports, and regional modules remain
  reachable in the tools region of the right pane.

#### Scenario: Narrow Output

- **WHEN** the window is narrow
- **THEN** conversion output, reverse output, and the current view text remain
  visible in the right pane.
