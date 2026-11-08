# Spec Delta

## Purpose

Lets the workbench act as a system-wide IPA keyboard that inserts symbols into
the application that had focus, without stealing focus from it.

## ADDED Requirements

### Requirement: Keyboard mode

The workbench SHALL provide a keyboard mode that turns the window into a
topmost, non-activating keyboard panel, SHALL send each symbol to whatever
application is in the foreground, and SHALL restore the workbench layout when
the mode ends.

#### Scenario: Enter keyboard mode

- **WHEN** the user enables keyboard mode
- **THEN** the workbench stays on top, does not take focus, and the application
  the user selects next stays in the foreground

#### Scenario: Leave keyboard mode

- **WHEN** the user leaves keyboard mode
- **THEN** the workbench returns to its normal layout and stops injecting

### Requirement: Symbol injection

While keyboard mode is active, the workbench SHALL insert each chosen symbol
into the foreground application through Unicode input events, SHALL send
supplementary-plane symbols as valid surrogate pairs, and SHALL report when no
external application is in the foreground.

#### Scenario: Type into the target

- **WHEN** the user clicks `ʃ` while another application is in the foreground
- **THEN** that application receives `ʃ` at its caret and keeps focus

#### Scenario: No target

- **WHEN** keyboard mode has no external foreground window
- **THEN** the workbench reports that no target is available and sends nothing

### Requirement: Injection fallback

When Unicode event injection fails or is rejected, the workbench SHALL fall
back to placing the symbol on the clipboard and sending Ctrl+V, and SHALL
report the fallback in the status line.

#### Scenario: Fallback to the clipboard

- **WHEN** SendInput inserts fewer events than requested
- **THEN** the workbench copies the symbol to the clipboard, sends Ctrl+V, and
  shows a fallback notice

#### Scenario: Elevated target

- **WHEN** the target window runs at a higher integrity level
- **THEN** the workbench reports that input was rejected instead of claiming
  success
