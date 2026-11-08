# Proposal

## Why

The self-contained build is a folder of 200+ files. Users need a normal Windows
install: a single setup executable, a Start Menu entry, and an uninstaller, with
a choice between a per-user install that needs no administrator and an
all-users install.

## What Changes

- Add an Inno Setup script and build script that turn `dist\` into
  `vec4ipa-setup-<version>.exe`.
- Offer **per-user** and **all-users** installation in one installer. Per-user
  installs under `%LOCALAPPDATA%\Programs` without elevation; all-users
  installs under `Program Files` after elevation.
- Create a Start Menu shortcut and an optional desktop shortcut, and offer to
  launch the workbench after installation.
- Register a normal uninstaller that removes program files and shortcuts while
  keeping `%APPDATA%\vec4ipa` favorites and settings.
- Take the version from `IPA2VEC_VERSION` so the installer, the executable, and
  Apps & Features agree.
- Add a `rust-ui-installer` build target and document the output.

No changes to the C core, the Rust application code, or the packaged `dist`
layout.

## Capabilities

### New Capabilities

- `desktop-installer`: Windows setup for the self-contained Rust workbench,
  including install scope, shortcuts, version metadata, and uninstall.

### Modified Capabilities

None.

## Impact

- `ui/rust/installer.iss`, `ui/rust/installer.bat`, `Makefile`,
  `ui/rust/README.md`.
- Build dependency: Inno Setup 6 (`ISCC.exe`), installed separately.
- Output: `ui/rust/installer/vec4ipa-setup-<version>.exe`.
