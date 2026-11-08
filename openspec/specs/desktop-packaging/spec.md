# desktop-packaging Specification

## Purpose

Defines a self-contained Rust desktop build that runs without a separate
Windows App SDK installation.

## Requirements

### Requirement: Self-contained output

The build SHALL produce a folder that contains the executable and every
Windows App SDK runtime file needed to start on Windows 10 version 1809 or
later on x64.

#### Scenario: Start on a clean machine

- **WHEN** the folder is copied to a clean Windows 10 1809 x64 machine without
  a Windows App SDK runtime installed
- **THEN** the workbench starts and shows its main window.

#### Scenario: Build from a clean tree

- **WHEN** a developer runs the documented release build command on a clean
  checkout
- **THEN** the command creates the self-contained output folder and exits
  successfully.

### Requirement: Bundled application assets

The output SHALL include the fonts, icon, image assets, and CLI tools that the
workbench uses at runtime.

#### Scenario: Bundled fonts and tools

- **WHEN** the workbench starts from the output folder
- **THEN** it uses the bundled Gentium font and can export the bundled
  `ipa2vec`, `vec2ipa`, and `vec4ipa` tools.

#### Scenario: Missing required asset

- **WHEN** a required asset is absent from the output folder
- **THEN** the workbench reports a startup error naming the missing asset
  instead of failing silently.

### Requirement: Reproducible build metadata

The release build SHALL use the same suite version as the C core and SHALL NOT
require network access at application startup.

#### Scenario: Version agreement

- **WHEN** the workbench reports its version
- **THEN** it matches `IPA2VEC_VERSION` from the C core.

#### Scenario: Offline startup

- **WHEN** the machine has no network connection
- **THEN** the workbench starts and performs local conversions normally.

### Requirement: Single workbench distribution

The release SHALL ship the Rust workbench as the only full desktop
front-end. The self-contained folder and installer SHALL NOT contain .NET,
WinUI, or C# workbench binaries, and building or running the shipped
workbench SHALL NOT require MSBuild.

#### Scenario: Fresh install

- **WHEN** the user installs the 4.0.0 package
- **THEN** the install directory contains `vec4ipa-ui.exe`, its Windows App SDK
  runtime files, fonts, assets, and the CLI tools, and does not contain
  `ipa2vec_core.dll` or `vec4ipa_ui.dll`

#### Scenario: Upgrade from an older install

- **WHEN** the user installs 4.0.0 over an existing vec4ipa install directory
- **THEN** stale C# support files are removed and the Rust executable is the
  program the shortcuts start

### Requirement: Executable identity

The executable SHALL embed the application icon and a Windows version resource
whose file and product versions match `IPA2VEC_VERSION`. The installer,
Start Menu shortcut, desktop shortcut, and uninstall entry SHALL use the same
icon.

#### Scenario: Inspect the executable

- **WHEN** the user opens the executable's Properties dialog
- **THEN** the Product version is `4.0.0` and the IPA icon is shown in Explorer

#### Scenario: Inspect the installer

- **WHEN** the user views the installer or the installed app in Apps & features
- **THEN** the IPA icon and version `4.0.0` are shown
