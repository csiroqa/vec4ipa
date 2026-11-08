# AGENTS.md — vec4ipa / IPA2Vector

`vec4ipa` is a C11 tool suite that converts between IPA/extIPA strings and
articulatory vectors. Three command-line tools (`ipa2vec`, `vec2ipa`,
`vec4ipa`) share one header-only core, and a WinUI 3 workbench wraps the same
core through a small P/Invoke DLL. The Python tree under `tools/` is design,
generation, fitting, audit and test tooling; **none of it is needed at
runtime**. The shipped binaries embed their tables and do not read data files
unless the user explicitly passes `--scheme` or `--metric`.

## Build, Test, Lint

### Core CLIs (all platforms)

```sh
make                 # build ipa2vec, vec2ipa, vec4ipa
                     # (Windows also builds the legacy ui/vec4ipa_ui.exe)
make gen             # regenerate src/vectors.h and src/readme_embed.h
make test            # build, then run every gate in the Makefile test target
make verify-commit   # extract HEAD, build there, run the fast suites there
```

Individual suites are run from the **repository root**:

```sh
python tools/test_suite.py             # parsing, extIPA, tone, aliases, round-trip
python tools/test_metric_space.py      # nearest-base anchors + metric round-trip
python tools/test_alignment.py         # curve-distance alignment
python tools/test_spec_next.py         # 16-D table, metric16, scheme<->JSON sync
python tools/test_standard_chinese.py  # Mandarin initials/finals/tone
python tools/verify_modifiers.py       # modifier design model (Python, no binaries)
python tools/test_tongue_contour.py    # C contour port == Python model, exactly
python tools/test_scheme_portability.py  # runtime width/axes/weights under -D
python tools/validate_alignment.py     # alignment axioms over fuzz pairs
python tools/audit_modifier_collisions.py
python tools/test_modifiers_end_to_end.py
python tools/audit_symbol_assignments.py
python tools/check_generated_current.py
python tools/check_doc_numbers.py
python tools/check_doc_structure.py
python tools/check_readme_tests.py
python tools/check_doc_paths.py
python tools/test_winui_core.py
python tools/check_mainwindow_syntax.py
python tools/build_winui.py
```

Manual checks (deliberately outside `make test`):

```sh
python tools/fuzz_metric_space.py      # random-vector fuzz
python tools/catalogue_audits.py       # classify every audit as gate or report
```

Requirements:

- **C11 compiler**: `gcc` recommended; Windows uses MinGW-w64. `make` on
  Windows needs `windres` only for the legacy Win32 wrapper.
- **Python 3**: several suites and research tools need `numpy`; some fitting
  scripts also use `scipy`/`sklearn`. Fitting/audit scripts read large
  corpora under `tools/data/`.
- **WinUI workbench**: Visual Studio 2022 **Build Tools** with the MSBuild and
  WinUI/UWP build-tool workloads, .NET SDK 9, and `gcc`. `dotnet build` alone
  cannot load the AppxPackage PRI tasks; use `ui\winui\build.bat` or
  `tools/build_winui.py`, which invoke Visual Studio MSBuild.
- **MSIX**: `ui/winui/wap/vec4ipa_wap.wapproj` and
  `ui/winui/install_msix.ps1`.

Windows shortcuts:

```bat
ui\winui\build.bat          REM build the core DLL and publish dist\
ui\winui\build.bat clean    REM remove bin, obj, dist and the core DLL
```

`build.bat` publishes a self-contained folder. Single-file publishing is not
supported: WindowsAppSDK self-contained apps fail at startup in that mode.

### Rust workbench (Windows)

The accepted Rust front-end lives in `ui/rust/`. It uses `windows-reactor` and
links the C core through a static FFI shim. `ui/winui/` remains as the C#
reference implementation.

```bat
ui\rust\build.bat build     REM or: make rust-ui
ui\rust\build.bat test      REM or: make rust-ui-test
ui\rust\package.bat         REM or: make rust-ui-package
```

Requirements: Rust MSVC toolchain, Visual Studio C++ build tools (MSVC linker
and Windows SDK), and the Windows App SDK 2.x runtime. `build.bat` loads
`VsDevCmd.bat` before running Cargo. The Rust UI does not need .NET or MSBuild
XAML tasks; those remain requirements only for `ui/winui/`.

**Lint** is not a separate tool here. The C build uses `-Wall -Wextra
-std=c11`; treat new warnings as defects. `-Wno-format-truncation` is
deliberate for bounded trace buffers — do not silence it by shrinking
buffers. There is no Python or C# formatter configured; match the surrounding
style, and let the tests be the gate.

## Architecture

### One core, three frontends

`src/ipa2vec_core.h` is the shared implementation. Every definition in it is
`static`, so each translation unit gets its own copy:

- `ipa2vec` — IPA → vectors (two-layer IR, JSON, alignment)
- `vec2ipa` — vectors → IPA (nearest base + greedy modifier fit)
- `vec4ipa` — both directions plus inventory, modules, query, stats, weights

It includes:

- `src/vectors.h` — **generated** base table and runtime defaults
  (`NDIM`, `MAXDIM`, `NSEG`, `SEG_TABLE`, `METRIC_W`, `METRIC_LAMBDA`,
  `DIM_NAMES`)
- `src/tongue_contour.h` — the C port of `tools/gen_tongue_model.py`
- `src/names.tsv` — IPA → Latin feature identifier data (the reverse-lookup keys)

`IPA2VEC_VERSION` in `ipa2vec_core.h` is the single version string for the
suite.

### Data authority and generated artifacts

The runtime authority is `tools/data/spec_next.scheme` (the current 16-D
SPEC-NEXT scheme). The chain is intentional and directional:

```
tools/data/spec_next.scheme  (hand-tuned runtime authority)
        ├─> src/vectors.h            (gen_vectors_h.py; compiled into all binaries)
        └─> tools/data/vec_table_16.json  (JSON view; test_spec_next.py checks it
                                           value-for-value against the scheme)
```

There are **two weight authorities on purpose**:

- `tools/data/metric16.json` — fitted design weights, validated by
  `test_spec_next.py`
- `tools/data/spec_next.scheme` `weight` line — hand-tuned runtime weights,
  compiled into the binaries and validated by the CLI suites

`export_scheme.py` preserves an existing `weight` line rather than overwriting
it; do not "fix" the divergence.

The 18-D tongue-contour scheme is a second, derived chain:

```
gen_tongue_table.py -> gen_tongue_modifiers.py -> gen_merged_basis.py
                    -> export_tongue_scheme.py -> tools/data/tongue.scheme
```

`check_generated_current.py` regenerates that chain and compares 11 committed
artifacts. It excludes `fit_tongue_forward` and the retrieval gates because
they read `.rda` corpora and take minutes; `check_doc_numbers.py` covers the
figures those produce.

`IPA_VECTORS.md` and `docs/SPEC.md` are the legacy v8 scheme, kept for
reference; `gen_vec_table.py` still reads `IPA_VECTORS.md`, so do not delete
it. `metric.json` at the repo root is the legacy default metric; the current
build uses the scheme weights.

### Parsing pipeline

Every frontend follows the same stages:

1. **Canonical decomposition** — precomposed characters (`ã`, `ọ`, …) become
   base + combining marks, so `ã` and `a + ◌̃` are identical.
2. **Lexing (layer 1)** — longest-prefix base match, modifier letters, ties,
   preposed modifiers, tone marks; tokens stay in input order.
3. **Canonicalisation (layer 2)** — tokens are re-sorted by feature tier:
   `airstream → laryngeal → place → manner → nasal → timing`. Modifiers apply
   in that order; order matters (e.g. aspiration then creaky).
4. **Application** — the base vector is copied, then each modifier mutates the
   axes it names.
5. **Reverse fit** — nearest base under the weighted metric, then a greedy
   modifier search; `--narrowness` controls how many marks survive.
6. **Alignment** — `-A` uses the curve-distance substitution/indel model with
   vowel-block and tone handling.

Every token carries a Latin identifier (`vl.bil.pls`, `front.opn.unr.vwl`,
`nas`, …); those are the keys used by the reverse direction.

### Width is runtime state, not a constant

`NDIM` is the width of the **compiled default** scheme. A user can load a
different scheme with `-D/--scheme`, so the live width is `g_ndim`, which may
differ from `NDIM` (the shipped 18-D `tongue.scheme` is the standing example).
Rules:

- Index and stride by `g_ndim`; use `MAXDIM` (32) for storage.
- Resolve axes by name with `dim_of_ok(name, fallback)`; the fallback must
  name the same feature, because it only fires when a custom scheme omits the
  axis.
- Never print or hard-code "16-D" in UI text, help, or XAML; the CLI's
  `-v` banner already uses `g_ndim`.
- The WinUI side must query `Core.NDim` **after** `Core.SetArgs`, because that
  is where a scheme is loaded.

`MAX_TOKS` is the C core's fixed parse/IR capacity. `Core.cs` allocates its
own, larger buffers (`MAX_TOKS = 512`) and reads back the segment count; do not
add a silent truncation on either side.

### WinUI boundary

`ui/winui/core_wrap.c` is a thin export layer over `src/ipa2vec_core.h`;
`ui/winui/Core.cs` is the matching P/Invoke surface. The DLL is not a second
implementation:

- `ipa2v_ndim()` reports the loaded scheme width.
- `ipa2v_forward` / `ipa2v_reverse` / `ipa2v_query` / table and stats calls
  forward to the same functions the CLIs use.
- `ipa2v_set_args` applies CLI-style settings (school modules, `--width`,
  `-D scheme`), and UTF-8 path marshalling is explicit because Windows argv is
  not UTF-8.

`tools/test_winui_core.py` compiles `Core.cs` against the real DLL and compares
every coordinate against `vec4ipa` for both `spec_next.scheme` and
`tongue.scheme`. This is the guard against a mis-strided wrapper, which would
otherwise fill the tail with **another segment's** coordinates and still look
plausible.

The workbench (`ui/winui/MainWindow.xaml` + 3,700-line code-behind) is a single
imperative WinUI 3 window: custom title bar, Mica, acrylic popovers, soft
keyboard, pointer-magnet pickers, splitter, history, exports. It is UI layer
only; keep the vector semantics in the C core.

### Python tooling

All scripts live in one flat `tools/` directory on purpose. Running
`python tools/<name>.py` puts `tools/` on `sys.path[0]`, which is how scripts
import `_common`, `place_anchors`, `gen_vec_table`, etc. Moving scripts into
subdirectories breaks those imports. **Run from the repository root**; scripts
locate the root with `Path(__file__).parents[1]` and invoke the root binaries.

Script families:

- `gen_*` — generators (vectors, README embed, tongue chain, anchors)
- `fit_*` — fitting/research, often slow and corpus-dependent
- `audit_*` / `verify_*` / `validate_*` — design and data audits
- `test_*` — suites (some pure Python, some drive the built binaries)
- `check_*` — repository/doc/generated-artifact gates

`catalogue_audits.py` classifies every audit as a gate or a report; use it
before assuming a script is part of the build.

## Key Conventions

### Data over code, generators over edits

- Edit the authority (`tools/data/spec_next.scheme`, `src/names.tsv`, the
  `gen_*` inputs), not the generated output.
- `src/vectors.h` and `src/readme_embed.h` are generated and gitignored; `make`
  regenerates them as dependencies. `make gen` does it explicitly.
- The derived files under `tools/data/` (the tongue-chain JSON,
  `tongue.scheme`, and `vec_table_16.json`) are committed generated artifacts.
  Run their generators and commit the result. The other JSON/CSV/RDA files are
  research inputs or measurement outputs; do not regenerate them blindly.
- `ui/winui/ipa2vec_core.dll` is a tracked test artifact rebuilt in place by
  `test_winui_core.py`; commit the refreshed binary when the wrapper/core
  changed, as the history does.

### Scheme and metric changes

1. Edit `tools/data/spec_next.scheme` (or the appropriate source data).
2. Run `make gen` so `src/vectors.h` matches.
3. If the derived JSON view is affected, regenerate/update
   `tools/data/vec_table_16.json`; `test_spec_next.py` checks it value-for-value
   against the scheme.
4. Run at least `test_spec_next.py`, `test_scheme_portability.py`,
   `audit_symbol_assignments.py`, then the full `make test`.

Do not assume `gen_vec_table.py` reads the scheme: its hand-tuned constants
(e.g. `VOWEL_COL`) must stay in sync with the scheme, and the sync check is
what catches drift. `export_scheme.py` goes the other way (JSON → scheme) and
preserves the existing runtime `weight` line.

### Modifier semantics

- Modifiers are applied in tier order, not input order.
- A modifier must move the axis it names; `test_modifiers_end_to_end.py`
  checks that through the built binary.
- Keep the Python design model (`verify_modifiers.py`) synchronized with the C
  `MODS` table; the C side is the runtime authority.
- No two base segments may share a vector. `audit_symbol_assignments.py`
  treats that as blocking; the homophone allowlist is only for true duplicate
  spellings, not "similar" segments.

### Documentation is part of the build

- `docs/TONGUE-MODEL.md` is where the conclusions live. Every generator change
  moves the numbers under it; `check_doc_numbers.py` compares the anchor
  figures against the committed artifacts.
- `check_doc_structure.py` enforces sequential subsection numbering and live
  `§` cross-references.
- `check_doc_paths.py` verifies every repository path named in `README.md` and
  `docs/TONGUE-MODEL.md` still exists.
- `check_readme_tests.py` requires the README's test list to match the
  Makefile `test` target exactly. When adding a gate to the Makefile, add it to
  the README block; manual-only scripts go in the trailing
  "Not part of `make test`" sentence.
- Do not state a measured number without naming (or linking) the artifact it
  came from. A stale number is how a conclusion outlives its evidence.

### Commit messages

Recent history follows a consistent shape:

```
type(scope): 中文摘要

问题：...
做法：...
验证：...
```

Recent types: `feat`, `fix`, `test`, `docs`, `chore`. Keep the body concrete:
what was wrong, what changed, and which check proves it. Generated binaries
and artifacts that belong to the change go in the same commit.

### Portability

- Windows argv is wide; the CLI entry points use `wmain` + `-municode` and
  `argv_utf8_from_wide`. File paths go through `path_fopen` (UTF-8 → UTF-16 →
  `_wfopen`) so non-ASCII paths work on Chinese Windows.
- Use `_common.BIN_SUFFIX` in Python scripts; Windows binaries carry `.exe`.
- All source and data files are UTF-8. `gen_readme_embed.py` and
  `export_scheme.py` write LF/UTF-8 deliberately for byte-identical
  regeneration across platforms.

## Project Layout

```
src/
  ipa2vec_core.h       Shared C core: parser, IR, modifiers, metric, reverse fit,
                       alignment, scheme/metric loading
  tongue_contour.h     C port of the tongue model; parity-tested against Python
  vectors.h            GENERATED base table (gitignored)
  readme_embed.h       GENERATED embedded README (gitignored)
  names.tsv            IPA -> Latin feature identifiers
  ipa2vec_main.c       forward CLI
  vec2ipa_main.c       reverse CLI
  vec4ipa_main.c       inventory / both-directions CLI

tools/
  _common.py           shared test helpers (run, check, BIN_SUFFIX, parsers)
  place_anchors.py     place-anchor table + v8 remap
  gen_*.py             generators (vectors, README embed, tongue chain, anchors)
  fit_*.py             fitting/research (slow; not part of make test)
  audit_*.py           data/model audits
  verify_*.py          design-model verification
  test_*.py            suites
  check_*.py           repository/doc/generated-artifact gates
  build_winui.py       real MSBuild build of the WinUI project
  verify_commit.py     build/test git HEAD in a scratch tree
  data/
    spec_next.scheme   runtime authority (16-D, hand-tuned)
    tongue.scheme      derived 18-D tongue-contour scheme
    vec_table_16.json  derived JSON view (sync-checked)
    metric16.json      fitted design weights (different from runtime weights)
    tongue_table.json, merged_basis.json, ...  generated tongue chain
    corpus/, consonant/  raw corpora (not runtime input)

ui/
  vec4ipa_ui.c         legacy Win32 wrapper (still built on Windows)
  winui/               WinUI 3 workbench
    Core.cs            P/Invoke bindings
    core_wrap.c        thin C export layer
    MainWindow.xaml    UI markup
    MainWindow.xaml.cs imperative UI logic
    build.bat          gcc DLL + MSBuild publish
    wap/               MSIX packaging project
    dist/              publish output (gitignored)

docs/
  SPEC-NEXT.md         current 16-D design (authoritative)
  TONGUE-MODEL.md      tongue-contour model, measurements, conclusions
  SPEC.md              legacy v8 design (historical)
  ...

IPA_VECTORS.md         legacy v8 table (still read by gen_vec_table.py)
metric.json            legacy default metric
Makefile               build, gen, test, verify-commit
README.md              user-facing documentation; embedded into the CLIs
```

## Choosing the Right Checks

| If you changed… | Run at minimum |
|---|---|
| Parser, modifier, metric, reverse fit, alignment | `make test` |
| `tools/data/spec_next.scheme` or `src/names.tsv` | `make gen`, `python tools/test_spec_next.py`, `python tools/test_scheme_portability.py`, `python tools/audit_symbol_assignments.py`, then `make test` |
| Tongue generators / derived tongue data | `python tools/check_generated_current.py`, `python tools/test_tongue_contour.py`, `python tools/test_scheme_portability.py`, `python tools/check_doc_numbers.py` |
| `docs/TONGUE-MODEL.md` | `check_doc_numbers.py`, `check_doc_structure.py`, `check_doc_paths.py` |
| `README.md` test list or Makefile test target | `python tools/check_readme_tests.py` |
| A documented file path / rename | `python tools/check_doc_paths.py` |
| `ui/winui/Core.cs` or `core_wrap.c` | `python tools/test_winui_core.py` |
| `ui/winui/MainWindow.xaml.cs` | `python tools/check_mainwindow_syntax.py`, then `python tools/build_winui.py` |
| `ui/winui/MainWindow.xaml` | `python tools/check_mainwindow_syntax.py` (also rejects literal vector widths) |
| Anything about to be committed | `make verify-commit` |

`make test` builds and runs the **working tree**. `make verify-commit` extracts
`HEAD` with `git archive`, builds there, and runs the fast suites; only the
latter says whether the commit itself is sound.

## Field Notes (Gotchas From Past Sessions)

- **`make test` is not a commit check.** This repo once shipped a commit whose
  caller was added to `ipa2vec_core.h` without the definition in
  `tongue_contour.h`; every revision failed to compile while `make test` stayed
  green, because it builds the working tree. Use `make verify-commit` before
  declaring a commit good.

- **`NDIM` vs `g_ndim` is the recurring defect family.** Three silent bugs came
  from treating the compiled width as the loaded width: the wrong axis was
  written, derived site axes vanished from diagnostics, and cross terms were
  dropped from the metric. The then-existing checks could not see them because
  they all ran the committed 16-D scheme, where the two happen to agree.
  `test_scheme_portability.py` deliberately tests the **swap** (including
  `tongue.scheme`), and it must run on every `make test`.

- **`test_tongue_contour.py` requires exact equality, not a tolerance.** The C
  port and `gen_tongue_model.py` are doing the same double-precision
  arithmetic on the same constants. A difference means one of the two is
  wrong; loosening the comparison would hide which one.

- **`test_winui_core.py` must compare value-for-value against the CLI.** A
  mis-strided wrapper fills the tail with another segment's coordinates, so
  "the last axis is non-zero" proves nothing. It also rebuilds the checked-in
  `ui/winui/ipa2vec_core.dll` in place; after a core/wrapper change, inspect
  and commit the refreshed binary.

- **`check_mainwindow_syntax.py` is only the cheap half.** It compiles
  `MainWindow.xaml.cs` without WinUI references, so a deleted member
  (`Core.NDIM`, for example) is not a parse error. `build_winui.py` compiles
  the real project with Visual Studio MSBuild and is what caught ten references
  to a deleted constant that the syntax check had passed for months.

- **`dotnet build` cannot load the AppxPackage PRI tasks.** Use
  `ui\winui\build.bat` or `tools/build_winui.py`. In `make test`,
  `build_winui.py --skip-if-unavailable` intentionally skips when no Visual
  Studio MSBuild is installed; a skipped WinUI build is not a verified WinUI
  build. `build_winui.py` also assumes the core DLL already exists, so on a
  clean tree run `ui\winui\build.bat` or `test_winui_core.py` first.

- **`make verify-commit` runs plain `make` in the scratch tree.** On Windows
  that includes the legacy Win32 wrapper, so `windres` must be on PATH even
  when the change only touches the CLIs.

- **Never put a literal vector width in `MainWindow.xaml`.** `16-D vector`
  text is overwritten at startup from `Core.NDim`, so the stale literal
  survives review and is wrong for every scheme but the compiled one.
  `check_mainwindow_syntax.py` rejects it.

- **`check_generated_current.py` regenerates in place.** It backs up the
  committed files for comparison, then runs the generators in `tools/data`.
  If an artifact is stale, the check fails **and** the working tree already
  contains the regenerated output; inspect it, run the chain deliberately, and
  commit the result. It excludes `fit_tongue_forward` and the retrieval gates
  because those read `.rda` corpora and take minutes.

- **`make gen` is not the whole regeneration story.** It only writes
  `src/vectors.h` and `src/readme_embed.h`. The tongue chain is separate:
  `gen_tongue_table → gen_tongue_modifiers → gen_merged_basis →
  export_tongue_scheme`, checked by `check_generated_current.py`.

- **Two weight authorities are intentional.** `metric16.json` is the fitted
  design metric; `spec_next.scheme`'s `weight` line is the hand-tuned runtime
  metric. `export_scheme.py` preserves the existing weight line; blindly
  overwriting it changes every nearest-neighbour result.

- **`gen_vec_table.py` does not read `spec_next.scheme`.** Its hand-tuned
  constants (`VOWEL_COL`, ATR values, etc.) must stay in sync with the scheme;
  `test_spec_next.py` checks the resulting JSON against the scheme
  value-for-value. Edit both sides deliberately.

- **Windows binary names are not portable.** `_common.BIN_SUFFIX` adds `.exe`;
  the Makefile targets carry the suffix on Windows. `wmain` + `-municode` are
  required for UTF-8 argv, and `path_fopen` is required for non-ASCII paths.

- **`-Wno-format-truncation` is load-bearing.** The trace/IR buffers are sized
  with headroom and truncation is bounded and safe; GCC cannot prove it.
  Removing the flag or shrinking the buffers is not the fix.

- **The flat `tools/` directory is an import mechanism, not clutter.** Scripts
  rely on `sys.path[0] == tools/` for `import _common` and friends. Run from
  the repository root; do not move scripts into subdirectories without
  updating every import and Makefile reference.

- **Research scripts are not build steps.** `fit_*`, `gate_retrieval.py`,
  `explore_*` and the corpus fetchers can take minutes, need large `.rda`/CSV
  inputs, and are excluded from `make test` for that reason. Run them only
  when the task is the measurement itself.

- **MSIX / self-contained packaging has hard constraints.** The publish output
  is a folder (`dist/`), not a single file; `PublishSingleFile` fails at
  startup for WindowsAppSDK self-contained apps. `build.bat` must copy
  `resources.pri` next to the exe, and the WAP project overrides
  `WindowsAppSDKSelfContained` to `false` for the packaged build.

- **Documentation moves with the code.** Renaming a file or adding a gate
  breaks `check_doc_paths.py` / `check_readme_tests.py`; update `README.md`
  and `docs/TONGUE-MODEL.md` in the same change. The checks are intentionally
  strict because a stale path breaks the reader's first command.
