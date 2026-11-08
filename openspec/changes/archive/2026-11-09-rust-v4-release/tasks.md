# Tasks

## 1. Remove the C# workbench

- [x] 1.1 Move `ui/winui/core_wrap.c` to `ui/rust/core_wrap.c` and update the
  include paths and build.rs input path. Verify `cargo check` compiles it.
- [x] 1.2 Delete `ui/winui/` (C# sources, XAML, MSIX project, tracked DLL,
  assets) and the three C#-specific Python checks. Verify no active source or
  Makefile target names them.
- [x] 1.3 Regenerate `tools/data/audit_catalogue.json` and update
  `tools/test_modifiers_end_to_end.py` so the catalogue matches `tools/`.

## 2. Version and executable identity

- [x] 2.1 Set `IPA2VEC_VERSION` and the Cargo package version to `4.0.0`.
  Verify the CLI banner and `vec4ipa-ui --version` report 4.0.0.
- [x] 2.2 Generate a `VERSIONINFO` resource from `IPA2VEC_VERSION` in
  `build.rs`. Verify the release executable reports 4.0.0 and still carries
  the IPA icon.
- [x] 2.3 Confirm `app.rc` embeds the icon and the window still loads
  `vec_ipa.ico`. Verify the shortcut and uninstall entry use the same icon.

## 3. Packaging and upgrade

- [x] 3.1 Update `installer.iss` with release metadata and `[InstallDelete]`
  cleanup for the old C# support files; keep the AppId.
- [x] 3.2 Run `package.bat` and `installer.bat`. Verify
  `vec4ipa-setup-4.0.0.exe`, its icon, and its version metadata.
- [x] 3.3 Install 4.0.0 over a scratch directory and verify shortcuts, version,
  icon, and that no `ipa2vec_core.dll` or `vec4ipa_ui.dll` remain. Uninstall
  and verify user data survives.

## 4. Documentation

- [x] 4.1 Update `README.md`, `ui/README.md`, and `ui/rust/README.md` so the
  Rust workbench is the only full workbench and the MSIX retirement is clear.
- [x] 4.2 Update `AGENTS.md`, `docs/SPEC-NEXT.md`, and the Makefile/README test
  list to match the removed C# checks.
- [x] 4.3 Run `check_doc_paths.py`, `check_readme_tests.py`, and
  `check_doc_structure.py`. Verify all pass.

## 5. Verification and release commit

- [x] 5.1 Run `cargo fmt`, `cargo clippy --all-targets -- -D warnings`, and
  `cargo test`. Verify all pass.
- [x] 5.2 Run `make test` and `make verify-commit`. Verify both pass.
- [x] 5.3 Commit the release and report the installer path. Do not push without
  approval.

## Workflow follow-up

- Archive completed changes after the release checks and the user's approval.
