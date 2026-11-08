# Design

## Context

See `proposal.md`. The core's alias modules are described by `ALIAS_MODULES`;
the wrapper can list them but only enable them. The six keyboard groups are
hard-coded in `keyboard_groups`. The current regional-module row exposes only
school aliases and no state. This design puts both families behind one registry
so the manager, profiles, and persistence work the same way.

## Goals / Non-Goals

**Goals:**

- One registry and manager for parser and keyboard modules.
- Ordered parser state, set-like keyboard state.
- Profiles over both kinds.
- Persistence with a safe migration from files without module fields.
- Keep the CLI and the C# reference unchanged.

**Non-Goals:**

- New CLI module flags.
- Workspace/panel modules beyond the keyboard groups.
- Third-party or dynamically loaded modules.
- Per-module symbol previews.

## Decisions

### Registry with two providers

Add a Rust registry:

```text
Module { id, label, description, kind, count, always_on }
ModuleKind { Parser, Keyboard }
```

Ids are namespaced (`parser:americanist`, `keyboard:consonants`). The parser
provider reads `ipa2v_modules_all`; the keyboard provider describes the six
groups from `KeyboardModel`. Registration rejects duplicate ids and exposes
`modules(kind)` and `find(id)`.

Keyboard counts come from the group lengths; parser counts come from the
wrapper's symbol count. Descriptions are short static strings per keyboard
group and `"school alias module"` / `"always-on alias module"` for parser
modules.

Alternative: a trait-object plugin registry. Rejected because two fixed
providers do not need dynamic dispatch.

### Separate state per kind

`enabled_parser: Vec<String>` is ordered; its order is the alias priority.
`enabled_keyboard: Vec<String>` is a set; the keyboard renders groups in the
model's fixed order, so the list order is irrelevant.

Every change validates ids against the registry, removes always-on ids, then:

- parser: `engine.set_modules(&enabled_parser)`;
- keyboard: the keyboard view filters groups by the set.

Applying an exact parser set avoids priority drift, as in the previous
design.

### Profiles store both kinds

```text
Profile { name, parser: Vec<String>, keyboard: Vec<String> }
```

Built-ins are `All on` and `All off`. User profiles live in settings. Applying
a profile copies its two lists; saving captures the current lists under a
name; deleting removes a user profile. Any edit after applying sets the active
profile to `Custom`, which is a display state, not a stored profile.

Alternative: profiles per kind. Rejected because users think in terms of a
working setup, not two independent selections.

### Settings carry a migration-safe payload

Add to `Settings`:

- `enabled_parser_modules: Vec<String>` (default empty);
- `keyboard_modules: Option<Vec<String>>` where `None` means all six, so old
  files keep the current keyboard;
- `module_profiles: Vec<Profile>` (default empty);
- `active_profile: String` (default `Custom`).

Startup reconciles: drop unknown ids, drop always-on ids, and treat `None` as
all keyboard groups. The reconciled state is saved on the next change.

Alternative: a single `enabled_modules` list. Rejected because parser order
carries meaning and the two kinds have different defaults.

### Manager UI replaces the regional row

The `modules` section keeps its collapsible header and contains:

- a profile row: active name, built-in and user profile buttons, Save current,
  Delete;
- a filter box matching id, label, and description;
- one group per kind with a bulk All on / All off row;
- module rows: toggle, label, description, count, always-on marker;
- a summary line with enabled count per kind and total symbols.

The keyboard groups section is driven by `enabled_keyboard`; fresh installs see
all six groups.

### Parser ABI stays in the wrapper

`core_wrap.c` exposes `ipa2v_modules_all`, `ipa2v_set_modules`, and
`ipa2v_enabled_modules`. The core header and CLI are untouched; always-on
modules are skipped by the set call.

## Risks / Trade-offs

- Two module kinds in one manager can be long → group headers and the filter
  keep it usable.
- Keyboard modules default to all → the `Option` encoding prevents an old
  settings file from hiding every group.
- Profile names can collide → saving replaces an existing user profile with the
  same name after the UI confirms, or the manager reports the conflict.
- The tracked `ipa2vec_core.dll` must be rebuilt after the wrapper change →
  `test_winui_core.py` refreshes it and the change commit includes it.
