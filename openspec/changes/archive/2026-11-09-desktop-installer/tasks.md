# Tasks

## 1. Installer script

- [x] 1.1 Add `ui/rust/installer.iss` with the per-user/all-users scope dialog
  and `{autopf}\vec4ipa`. Verify the wizard shows both choices.
- [x] 1.2 Copy `dist\*`, create a Start Menu shortcut, offer a desktop
  shortcut, and offer to launch the app. Verify the shortcuts and launch.
- [x] 1.3 Register the uninstaller and keep `%APPDATA%\vec4ipa` untouched.
  Verify favorites survive an uninstall.
- [x] 1.4 Use a stable `AppId`, the application icon, and x64-only install
  mode. Verify the Apps & Features entry uses the product icon.

## 2. Versioned build

- [x] 2.1 Add `ui/rust/installer.bat` that runs `package.bat`, extracts
  `IPA2VEC_VERSION`, and calls `ISCC.exe /DAppVersion=...`. Verify the output
  name `vec4ipa-setup-<version>.exe`.
- [x] 2.2 Add a `rust-ui-installer` Makefile target. Verify `make
  rust-ui-installer` builds the installer from a clean `dist`.
- [x] 2.3 Fail the build with a clear message when `ISCC.exe` is missing or the
  version cannot be parsed. Verify both failure paths.

## 3. Install and uninstall verification

- [x] 3.1 Run a silent per-user install into a temporary directory. Verify
  the executable, tools, fonts, and assets are present.
- [x] 3.2 Run the uninstaller silently. Verify program files and shortcuts are
  removed and `%APPDATA%\vec4ipa` still exists.
- [x] 3.3 Verify the installed version matches `IPA2VEC_VERSION` in the Apps &
  Features entry.

## 4. Documentation

- [x] 4.1 Add the installer build and output to `ui/rust/README.md` and the
  main README build block. Verify `check_doc_paths.py` passes.

## Workflow follow-up

- Archive the change after the installer checks and the user's approval.
