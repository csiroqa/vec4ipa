# Spec Delta

## Purpose

Provides the complete desktop workbench for converting between IPA strings and
articulatory vectors, exploring the symbol inventory, and exporting results.

## ADDED Requirements

### Requirement: Forward conversion

The workbench SHALL convert IPA and extIPA input into one vector per segment
and SHALL offer vector, two-layer IR, and JSON output.

#### Scenario: Convert typed IPA

- **WHEN** the user submits `tʰeɪk`
- **THEN** the workbench shows four segments with vectors and the same
  airstream and note data as the CLI.

#### Scenario: Convert with a custom scheme

- **WHEN** the user loads an 18-dimension scheme and converts a segment
- **THEN** every printed vector has 18 coordinates and the axis names come
  from that scheme.

### Requirement: Reverse conversion

The workbench SHALL convert one or more vector rows into IPA, SHALL apply the
selected narrowness level, and SHALL report a clear error for malformed or
non-finite vectors.

#### Scenario: Reverse a batch

- **WHEN** the user submits two valid vector rows
- **THEN** the workbench returns one IPA fit for each row.

#### Scenario: Reject a non-finite vector

- **WHEN** a row contains `NaN` or an infinite value
- **THEN** the workbench reports an error and leaves the other rows available
  for correction.

### Requirement: Loop round-trip

The workbench SHALL support IPA → vectors → reverse fit and SHALL preserve
tone annotations across the loop.

#### Scenario: Preserve tone groups

- **WHEN** the user runs the loop on input with `tone=(…)` groups
- **THEN** the rebuilt IPA retains the same tone annotation groups.

### Requirement: Soft keyboard

The workbench SHALL provide grouped, filterable symbol input with recent and
favorite symbols, and SHALL NOT append a combining modifier before a base
segment.

#### Scenario: Filter the keyboard

- **WHEN** the user types a filter string
- **THEN** the visible symbol groups contain only matching symbols.

#### Scenario: Guard a leading modifier

- **WHEN** the input is empty and the user picks a combining modifier
- **THEN** the workbench shows a hint and does not insert the modifier.

### Requirement: Symbol exploration

The workbench SHALL show symbol details, compare two symbols, compute their
weighted distance, and align two IPA sequences.

#### Scenario: Compare two symbols

- **WHEN** the user compares `ʃ` and `s`
- **THEN** the workbench shows both vectors and their weighted distance.

#### Scenario: Align two strings

- **WHEN** the user aligns two IPA strings
- **THEN** the workbench shows the alignment cost and the aligned segments.

### Requirement: Inventory views

The workbench SHALL display the base table, regional modules, statistics,
metric weights, effective weights, and module enablement, and SHALL load a
metric file at runtime.

#### Scenario: Load a metric file

- **WHEN** the user selects a valid metric file
- **THEN** subsequent distance and reverse-fit results use its weights and
  lambda.

### Requirement: History and examples

The workbench SHALL keep a bounded session history and SHALL provide example
inputs that populate the editor.

#### Scenario: Reuse history

- **WHEN** the user selects a history entry
- **THEN** its input and output return to the workbench.

### Requirement: File conversion and export

The workbench SHALL convert IPA files, save output, export CSV and two-layer
IR files, and expose the bundled CLI tools and equivalent command lines.

#### Scenario: Convert a file

- **WHEN** the user opens an IPA file for batch conversion
- **THEN** the workbench shows one result per input line and allows saving it.

### Requirement: Window and appearance

The workbench SHALL provide a custom title bar, resizable split panes,
system/light/dark themes, an English/Chinese UI, an always-on-top toggle, and
persistent window state.

#### Scenario: Switch theme and language

- **WHEN** the user selects the dark theme and Chinese
- **THEN** the window, controls, and labels update without restarting.

### Requirement: Startup arguments

The workbench SHALL accept CLI-compatible startup arguments for an initial IPA
string, reverse vector, symbol query, narrowness, theme, and tool export.

#### Scenario: Start with an IPA string

- **WHEN** the application starts with `tʰeɪk` as an argument
- **THEN** the workbench opens with that input already converted.

### Requirement: Error recovery

The workbench SHALL keep running after a parse or conversion error and SHALL
show the error without discarding the user's input.

#### Scenario: Invalid IPA

- **WHEN** the user submits an unknown symbol
- **THEN** the workbench shows the engine error and keeps the input editable.
