# Proposal

## Why

Optional features are managed ad hoc: regional parser modules are a one-way row
of buttons, keyboard groups are always built, and neither carries metadata,
profiles, or persisted state. Users who switch between school conventions or
who never use some symbol groups need one general module system instead of
per-feature switches.

## What Changes

- Introduce a **module registry** with a uniform descriptor: id, label,
  description, kind, item count, and always-on flag. Two kinds are defined:
  - `parser` modules: the core's alias modules (school and always-on);
  - `keyboard` modules: the six symbol groups (consonants, non-pulmonic,
    vowels, diacritics, letters, tones).
- Make every optional module a **reversible toggle**. Parser modules keep an
  enable order that acts as alias priority; disabling one keeps the rest and
  their order. Keyboard modules hide or show their group.
- Add **profiles**: built-in All on and All off, plus user-named profiles that
  store both parser and keyboard selections. Apply, save, and delete profiles;
  edits after applying mark the state as custom.
- Add **bulk actions** per kind and a **summary** of enabled modules and
  symbols.
- **Persist** enabled ids per kind, custom profiles, and the active profile.
  Restore at startup and ignore ids the core no longer exposes.
- Replace the regional-module row with a unified **module manager** grouped by
  kind, with a name filter, per-module toggles, descriptions, counts, bulk
  actions, profiles, and the summary.
- Add a wrapper ABI for the parser kind: list modules, apply an exact ordered
  set, and report the enabled set. Keyboard modules are a front-end concern.
- The CLI keeps its enable-only flags and parsing behavior.

No change to alias tables, symbol membership, or vector semantics.

## Capabilities

### New Capabilities

- `module-management`: registry and descriptors across parser and keyboard
  kinds, reversible toggles, ordering, profiles, bulk actions, persistence, and
  status.

### Modified Capabilities

- `desktop-workbench`: the regional-module row becomes the unified module
  manager.
- `engine-ffi`: the wrapper exposes exact parser-module sets and enabled-state
  reporting.

## Impact

- `ui/winui/core_wrap.c`: three new exports; existing exports unchanged.
- `ui/rust/src/engine.rs`: parser inventory, exact-set, and enabled-list FFI.
- `ui/rust/src/app.rs`: registry, manager UI, keyboard-group filtering.
- `ui/rust/src/settings.rs`: module state and profiles.
- `ui/winui/ipa2vec_core.dll`: refreshed tracked test artifact.
- No changes to `src/ipa2vec_core.h` or CLI behavior.
