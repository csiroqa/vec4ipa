# vec4ipa UI (WinUI 3 workbench)

A single-file, self-contained Windows GUI for the **vec4ipa** tool
suite (IPA strings ↔ 16-D articulatory vectors), built with **WinUI 3**
and .NET 9. The engine is the same header-only core the CLI tools use
(`../src/ipa2vec_core.h`), compiled once into `ipa2vec_core.dll` and
called via P/Invoke — numbers are identical to the command line.

## Layout

```
ui/
├── vec4ipa_ui.c            legacy Win32 wrapper (superseded, kept for reference)
├── app.rc / app.res        Win32 resources (legacy)
├── assets/                 application icon sources (SVG/PNG)
├── fonts/                  Gentium Book Plus + NewComputerModern10 (SIL OFL 1.1)
└── winui/                  the WinUI 3 front-end
    ├── vec4ipa_ui.csproj   project (unpackaged, self-contained)
    ├── App.xaml(.cs)       application entry, startup diagnostics
    ├── MainWindow.xaml(.cs) the whole workbench UI
    ├── Core.cs             P/Invoke bindings to ipa2vec_core.dll
    ├── core_wrap.c         C export layer (compiled into the DLL)
    ├── app.manifest        DPI awareness etc.
    └── build.bat           build script
```

## Features

- **IPA → vectors**: type or click symbols on the soft keyboard;
  output as plain vectors, two-layer IR (with rebuilt IPA) or JSON
- **Vector → IPA**: 16-D input (multi-line for batch), width 0-4,
  live **vector editor** with reverse preview
- **IPA soft keyboard**: continuous scroll with grouped sections —
  Consonants (by place), Non-pulmonic (ejectives/implosives/clicks),
  Vowels (trapezium order), Diacritics, Letters, Tones, Recent.
  Hover shows the symbol's name, double-click opens details
- **Symbol compare**, weighted **distance**, **history**, examples,
  open-file batch convert, convert+reverse **loop**
- **Views**: base table, module details, statistics, metric weights,
  effective weights, module enablement, metric.json loading
- **Export**: bundled CLI tools, command lines, table CSV, IR
  layer1/layer2 files, output saving
- **Window**: custom title bar, drag-resizable splitter, theme
  (system/light/dark), English/中文 UI, window state persistence,
  CLI-compatible startup arguments

## Build

Requirements:

- MinGW-w64 `gcc` (builds `ipa2vec_core.dll`)
- Visual Studio 2022 **Build Tools** with the *MSBuild tools* and
  *Universal Windows Platform build tools* workloads (WinUI 3 build
  tasks; plain `dotnet build` is not enough)
- .NET SDK 9

```
ui\winui\build.bat            # builds the DLL, then publishes to dist\
ui\winui\build.bat clean      # remove build output
```

Output: `ui\winui\dist\` — a self-contained folder with
`vec4ipa_ui.exe`, runnable without installing anything.

> Single-file (`PublishSingleFile`) publishing is **not** supported:
> WindowsAppSDK self-contained apps fail at startup in that mode
> (known platform limitation).

## Command line

```
vec4ipa_ui [OPTIONS] [IPA-STRING]
  --narrowness LEVEL    reverse-fit narrowness (broadest|broad|medium|narrow|narrowest, or 0-4; alias --width; default narrow)
  -q, --query SYM      query one symbol on startup
  -r, --reverse VEC    16-D vector -> IPA on startup
  --theme system|light|dark
  --export-tools DIR   write the bundled CLI tools to DIR
  -h, --help
  IPA-STRING           forward IPA -> vectors on startup
```

## Fonts

The GUI uses **Gentium Book Plus** (normative IPA letterforms); the
application icon renders its arrow with **NewComputerModern10**. Both
are SIL OFL 1.1 licensed and ship in `ui/fonts/` with the license
text; the app falls back to system fonts if they are absent.

## Notes

- Startup diagnostics (`startup.log`, `crash.log`) go to
  `%TEMP%\vec4ipa\`, never into the app folder.
- On some systems the compositor does not repaint theme resources
  after a runtime theme switch; the workbench sets container
  backgrounds explicitly to compensate.
