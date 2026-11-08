# vec4ipa user interfaces

The Rust workbench in `rust/` is the full Windows front-end for the vec4ipa
suite. It uses `windows-reactor` and compiles the shared C core through
`rust/core_wrap.c`, so its vectors, reverse fits, and inventory match the CLI
tools. Version 4.0.0 makes it the only workbench; the WinUI 3 C# reference is
gone.

The legacy Win32 wrapper (`vec4ipa_ui.c`) is still built by plain `make` on
Windows as a minimal fallback. The installer does not ship it.

## Layout

```
ui/
├── rust/                   Rust workbench, FFI shim, packaging
│   ├── src/                window, engine bridge, keyboard, modules, settings
│   ├── core_wrap.c         C export layer compiled into the executable
│   ├── app.rc              embedded application icon
│   ├── package.bat         release build plus self-contained dist/
│   └── installer.bat       Inno Setup package
├── vec4ipa_ui.c            legacy Win32 wrapper (not installed)
├── app.rc / app.res        legacy Win32 resources
├── assets/                 application icon sources (SVG/PNG)
└── fonts/                  Gentium Book Plus + NewComputerModern10 (SIL OFL 1.1)
```

## Build

The workbench needs the Rust MSVC toolchain, the Visual Studio C++ build tools,
the Windows SDK, and the Windows App SDK runtime. Build and package it from
`rust/`:

```bat
rust\build.bat build        REM debug build
rust\build.bat test         REM cargo test
rust\package.bat            REM release build plus dist\
rust\installer.bat          REM setup executable from dist\ (Inno Setup 6)
```

`dist\` is self-contained: it includes the Windows App SDK runtime, fonts,
icon, assets, and the three CLI tools. The installer reads the version from
`IPA2VEC_VERSION` and writes `rust\installer\vec4ipa-setup-<version>.exe`.

## Retired C# workbench

The WinUI 3/C# workbench and its MSIX project were removed in 4.0.0. The new
installer replaces an existing vec4ipa install and deletes the old
`ipa2vec_core.dll` and managed support files. A separately installed MSIX
package is not removed automatically; uninstall it from **Settings → Apps**.

See [`rust/README.md`](rust/README.md) for features, accepted differences, and
the verification list.
