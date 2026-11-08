# Spec Delta

## ADDED Requirements

### Requirement: Module manager

The workbench SHALL replace the regional-module button row with a unified
manager grouped by module kind, with a name and description filter, a profile
selector, per-module toggles, item counts, per-kind bulk actions, and a summary.

#### Scenario: Manage a module

- **WHEN** the user opens the manager and activates a module
- **THEN** the module turns on, its row reflects the state, and the summary
  updates

#### Scenario: Filter the manager

- **WHEN** the user types part of a module name or description
- **THEN** only matching modules remain visible

#### Scenario: Always-on module

- **WHEN** the manager shows an always-on parser module
- **THEN** the row is marked as always on and has no toggle

#### Scenario: Profiles in the manager

- **WHEN** the user applies a profile from the manager
- **THEN** every parser and keyboard module follows that profile
