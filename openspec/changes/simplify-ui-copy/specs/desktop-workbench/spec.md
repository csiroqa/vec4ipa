# Spec Delta

## ADDED Requirements

### Requirement: Concise labels and statuses

User-facing labels, placeholders, and status messages SHALL use short, plain
wording. Primary action labels SHALL use no more than three English words, and
status messages SHALL state the outcome in one sentence without internal field
names.

#### Scenario: Review action labels

- **WHEN** the user views the toolbar, action bar, and tools sections
- **THEN** each primary action label is at most three English words and none
  uses promotional or internal wording

#### Scenario: Toggle a module

- **WHEN** the user enables the Americanist module
- **THEN** the status line says `Enabled Americanist.` rather than a
  colon-separated internal field name

#### Scenario: Report a missing file

- **WHEN** a saved scheme file no longer exists at startup
- **THEN** the status names the missing scheme in plain language and keeps the
  file path as supporting detail

### Requirement: Separator restraint

Interface copy SHALL NOT join independent facts with chains of `·`, `—`, `|`,
or `/`. It SHALL use separate lines, commas, or sentences instead. Simple
Unicode aids such as `→` and `✓` MAY replace a word or show direction or
selection, but SHALL NOT be chained into status lines. Vector rows, file paths,
commands, and alignment results are data output and are exempt.

#### Scenario: Read the module summary

- **WHEN** the user opens the module manager
- **THEN** parser, keyboard, and symbol counts appear as separate plain lines
  or sentences, with no dot-and-slash chain

#### Scenario: Read the title bar

- **WHEN** the workbench starts
- **THEN** the title shows the application name, the subtitle shows the version,
  and the status is not repeated in a separator chain

#### Scenario: Read a direction label

- **WHEN** the workbench labels the reverse workflow
- **THEN** it may use a single `→` between source and target, and the label
  remains understandable without the arrow

### Requirement: Selection and state wording

The workbench SHALL mark the active format, pane, profile, and module with one
consistent selection marker, and SHALL state enabled, disabled, and always-on
states in words rather than relying on nested brackets or punctuation alone.

#### Scenario: Select an output format

- **WHEN** the user selects Vectors
- **THEN** exactly one format button carries the active marker and the other
  format buttons do not

#### Scenario: Show an always-on module

- **WHEN** the module manager lists an always-on parser module
- **THEN** the row says `Always on` and offers no toggle

### Requirement: Localized built-in profiles

Built-in profiles and the custom state SHALL display in the active interface
language, while their persisted profile names remain unchanged. Switching
language SHALL update the labels without changing the selected profile.

#### Scenario: Use the Chinese interface

- **WHEN** the interface language is Chinese
- **THEN** the built-in profiles display as `全部启用` and `全部禁用`, and the
  custom state displays as `自定义`

#### Scenario: Switch language with a profile active

- **WHEN** the user switches from English to Chinese while a built-in profile is
  active
- **THEN** the profile label changes language and the same profile remains
  active
