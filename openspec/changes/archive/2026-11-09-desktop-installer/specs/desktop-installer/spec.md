# Spec Delta

## Purpose

Packages the self-contained Rust workbench as a Windows installer with a
per-user or all-users scope, shortcuts, version metadata, and a clean
uninstall.

## ADDED Requirements

### Requirement: Install scope choice

The installer SHALL offer a per-user installation and an all-users
installation. The per-user choice SHALL install without administrator rights
under the user's local program directory; the all-users choice SHALL install
under `Program Files` after elevation.

#### Scenario: Install for the current user

- **WHEN** the user selects the per-user option and completes the wizard
- **THEN** the workbench is installed under `%LOCALAPPDATA%\Programs` without an
  elevation prompt

#### Scenario: Install for all users

- **WHEN** the user selects the all-users option
- **THEN** the installer requests elevation and installs under `Program Files`

### Requirement: Installed application

The installer SHALL copy the complete self-contained build, create a Start Menu
shortcut, offer an optional desktop shortcut, and offer to launch the workbench
after installation.

#### Scenario: Shortcuts and launch

- **WHEN** installation finishes with the launch option selected
- **THEN** the Start Menu shortcut exists and the workbench starts from the
  install directory

### Requirement: Uninstall

The uninstaller SHALL remove the installed program files and shortcuts and
SHALL keep the user's data under `%APPDATA%\vec4ipa`.

#### Scenario: Keep favorites

- **WHEN** the user uninstalls the workbench after saving a favorite
- **THEN** the installed files are gone and the favorites file is still present

### Requirement: Version metadata

The installer SHALL use the suite version from `IPA2VEC_VERSION` in its file
name, its wizard, and the Apps & Features entry.

#### Scenario: Version agreement

- **WHEN** the core version is `3.1.0`
- **THEN** the installer is named `vec4ipa-setup-3.1.0.exe` and reports the same
  version after installation
