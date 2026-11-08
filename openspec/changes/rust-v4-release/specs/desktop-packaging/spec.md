# Spec Delta

## ADDED Requirements

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
