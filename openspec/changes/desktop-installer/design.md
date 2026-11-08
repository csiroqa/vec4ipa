# Design

## Context

See `proposal.md`. The Rust workbench already produces a self-contained `dist\`
folder through `package.bat`. Inno Setup 6 is installed under
`%LOCALAPPDATA%\Programs\Inno Setup 6`; `ISCC.exe` is the compiler. The suite
version is defined once as `IPA2VEC_VERSION` in `src/ipa2vec_core.h`.

## Goals / Non-Goals

**Goals:**

- One setup executable built from the existing `dist\` output.
- A real choice between per-user and all-users installation.
- Shortcuts, launch-after-install, and a standard uninstall entry.
- Version numbers that cannot drift from the application.

**Non-Goals:**

- MSIX packaging or Store submission.
- Code signing certificates.
- Auto-update.
- Removing user settings or favorites on uninstall.

## Decisions

### Use Inno Setup instead of MSIX

Inno Setup only copies the already verified `dist\` tree, so the WinUI runtime
keeps loading exactly as it does in the portable build. MSIX would require a
trusted signing certificate and raises the self-contained Windows App SDK
question that the C# packaged project avoids by depending on the framework
package.

Alternative: MSIX with `makeappx` and a self-signed certificate. Rejected for
this iteration because installation would require trusting the certificate and
the packaged self-contained runtime is not proven here.

### Let Inno Setup choose the scope

`PrivilegesRequired=lowest` keeps the default install per-user and
unelevated. `PrivilegesRequiredOverridesAllowed=dialog` adds the install-mode
page so the user can pick all users; Inno then requests elevation. The default
directory uses `{autopf}\vec4ipa`, which resolves to `Program Files` for the
all-users mode and `%LOCALAPPDATA%\Programs` for the per-user mode.

Alternative: two separate installers. Rejected because the single wizard
already exposes the choice and keeps one artifact.

### Read the version from the core header

`installer.bat` extracts `IPA2VEC_VERSION` from `src/ipa2vec_core.h`, passes it
to `ISCC.exe` as `/DAppVersion=...`, and the script uses `{#AppVersion}` in the
file name, wizard, and uninstall entry. A missing version stops the build.

Alternative: duplicate the number in the script. Rejected because the suite
already has one version authority.

### Keep user data on uninstall

The installer never writes to `%APPDATA%\vec4ipa`, so the uninstaller only
removes installed files and shortcuts. Favorites, layout settings, and the
settings JSON survive by construction.

### Stable application identity

Use one fixed `AppId` GUID so reinstalling upgrades in place instead of
creating a second entry. The script ships under `ui/rust/installer.iss`; the
build output is `ui/rust/installer/vec4ipa-setup-<version>.exe`.

## Risks / Trade-offs

- Unsigned installers trigger SmartScreen → document it; signing is out of
  scope.
- All-users installation needs an administrator → the per-user default remains
  available.
- Inno Setup is an external build dependency → document the expected path and
  fail with a clear message when `ISCC.exe` is missing.
- `{autopf}` requires Inno Setup 6.3 or newer → state the requirement in the
  build script and README.
