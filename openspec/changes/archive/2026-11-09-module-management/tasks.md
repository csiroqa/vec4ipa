# Tasks

## 1. Parser wrapper ABI

- [x] 1.1 Add `ipa2v_modules_all`, `ipa2v_set_modules`, and
  `ipa2v_enabled_modules` to `ui/winui/core_wrap.c`. Verify all three are
  exported from the rebuilt DLL.
- [x] 1.2 Keep always-on modules out of the set/reset paths and report enabled
  modules in priority order. Verify a wrapper test applies two modules and
  reads them back in order.

## 2. Registry and state

- [x] 2.1 Add a module registry with descriptors, kinds, namespaced ids, and
  duplicate rejection. Verify parser and keyboard entries both appear with
  counts.
- [x] 2.2 Parse the parser inventory from the wrapper and add ordered
  `enabled_parser` state with `set_modules`. Verify an exact set round-trips.
- [x] 2.3 Add the pure toggle and bulk helpers over the registry. Verify
  disabling one module preserves the order and always-on ids are rejected.

## 3. Keyboard modules

- [x] 3.1 Build keyboard descriptors from the six groups, enabled by default.
  Verify disabling consonants hides the group and re-enabling restores its
  position.
- [x] 3.2 Filter `keyboard_groups` by the enabled set. Verify the keyboard
  model and counts are unchanged for the remaining groups.

## 4. Profiles

- [x] 4.1 Add built-in All on and All off profiles and user profile storage.
  Verify applying either built-in produces the expected module sets.
- [x] 4.2 Add save, apply, and delete actions with a `Custom` state after edits.
  Verify save captures both kinds and delete removes only the named profile.

## 5. Persistence

- [x] 5.1 Add parser ids, optional keyboard ids, profiles, and the active
  profile to `Settings`. Verify an old file loads all keyboard groups.
- [x] 5.2 Reconcile saved ids with the registry at startup, drop unknown ids,
  and apply the parser set once. Verify unknown parser and keyboard ids are
  ignored.

## 6. Manager UI

- [x] 6.1 Replace the regional-module row with the manager: kind groups,
  filter, rows with counts and always-on markers. Verify filtering and the
  always-on rows.
- [x] 6.2 Add the per-kind bulk actions and the enabled/symbol summary. Verify
  the summary after a toggle, a bulk action, and a profile apply.
- [x] 6.3 Add the profile row with apply, save, and delete. Verify a saved
  profile survives a restart and reapplies both kinds.

## 7. Integration and docs

- [x] 7.1 Run `cargo fmt`, `clippy -D warnings`, and `cargo test`. Verify all
  pass.
- [x] 7.2 Run `make test` and `make verify-commit`; confirm the refreshed
  `ipa2vec_core.dll` is the expected binary change. Verify both suites pass.
  `make test` passes and the DLL is refreshed in place; `make verify-commit`
  runs after the change is committed.
- [x] 7.3 Document the module manager and profiles in `ui/rust/README.md`.
  Verify `check_doc_paths.py` passes.

## Workflow follow-up

- Archive the change after the checks and the user's approval.
