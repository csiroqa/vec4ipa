# Spec Delta

## Purpose

Manages optional workbench features uniformly across parser modules and
keyboard symbol groups: descriptors, reversible toggles, ordering, profiles,
persistence, and status.

## ADDED Requirements

### Requirement: Module registry

The workbench SHALL expose every optional feature as a module descriptor with
an id, label, description, kind, item count, and always-on flag, and SHALL
reject duplicate module ids.

#### Scenario: Two kinds

- **WHEN** the registry is built
- **THEN** it contains the parser modules from the core and the six keyboard
  symbol groups, each with its kind and item count

#### Scenario: Duplicate id

- **WHEN** two providers register the same module id
- **THEN** the registry reports the duplicate instead of silently merging them

### Requirement: Parser modules

The workbench SHALL list the core's alias modules, SHALL allow toggling the
school modules, and SHALL treat the enable order as the alias priority.
Always-on modules SHALL NOT be disableable.

#### Scenario: Disable a parser module

- **WHEN** the user disables an enabled school module
- **THEN** only that module turns off and the other modules keep their order

#### Scenario: Always-on module

- **WHEN** the manager lists an always-on alias module
- **THEN** the module is marked as always on and offers no disable action

### Requirement: Keyboard modules

The workbench SHALL treat the six keyboard symbol groups as modules, enabled
by default, and hiding a module SHALL remove its group from the keyboard.

#### Scenario: Hide a keyboard group

- **WHEN** the user disables the consonants module
- **THEN** the consonants group disappears from the soft keyboard and the other
  groups stay visible

#### Scenario: Restore a keyboard group

- **WHEN** the user enables the consonants module again
- **THEN** the group returns in its normal IPA-chart position

### Requirement: Profiles

The workbench SHALL provide built-in All on and All off profiles and SHALL let
the user save, apply, and delete named profiles that store both parser and
keyboard selections. Changes after applying a profile SHALL mark the state as
custom.

#### Scenario: Apply a profile

- **WHEN** the user applies a saved profile
- **THEN** the parser and keyboard modules match that profile

#### Scenario: Edit after applying

- **WHEN** the user toggles a module after applying a profile
- **THEN** the active profile shows a custom state until it is saved again

### Requirement: Module persistence

The workbench SHALL persist the enabled module ids per kind, the custom
profiles, and the active profile, SHALL restore them at startup, and SHALL
ignore ids that are no longer registered.

#### Scenario: Restore after restart

- **WHEN** the user changes modules, restarts, and opens the manager
- **THEN** the same modules are enabled in the same order

#### Scenario: Unknown saved id

- **WHEN** the settings name a module that is no longer registered
- **THEN** the workbench ignores that id and keeps the known modules enabled

### Requirement: Module manager

The workbench SHALL provide one manager grouped by kind with a name and
description filter, per-module toggles, item counts, per-kind bulk actions, a
profile selector, and a summary of enabled modules and symbols.

#### Scenario: Filter the manager

- **WHEN** the user types part of a module name or description
- **THEN** only matching modules remain visible

#### Scenario: Summary

- **WHEN** a module is enabled, disabled, or applied through a profile
- **THEN** the enabled-module and symbol counts update immediately

#### Scenario: Bulk action

- **WHEN** the user disables all modules of one kind
- **THEN** every optional module of that kind is off and always-on modules are
  unchanged
