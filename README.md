# vec4ipa — IPA/extIPA ⇄ 16‑D articulatory vectors

`vec4ipa` is a suite of three command-line tools that convert between IPA /
extIPA strings (including complex combining marks, ligatures, tone letters,
Chinese tone classes, and clinical-phonetics symbols) and the
16‑dimensional articulatory vectors defined in this repository
([`docs/SPEC.md`](docs/SPEC.md), [`IPA_VECTORS.md`](IPA_VECTORS.md),
[`metric.json`](metric.json)).

All three tools share one core (`src/ipa2vec_core.h`):

| tool | direction | purpose |
| ---- | --------- | ------- |
| **`ipa2vec`** | IPA → vectors | parse IPA/extIPA strings into 16‑D vectors (2‑layer IR, JSON) |
| **`vec2ipa`** | vectors → IPA | nearest segment + modifier fit, distance |
| **`vec4ipa`** | both + inventory | full table, modules, query, stats, weights, both directions |

## Build

Requirements: C11 compiler (`gcc` recommended), `python3` (only to
regenerate generated headers).

```sh
make            # builds ./ipa2vec ./vec2ipa ./vec4ipa
                # (Windows: wmain + -municode for UTF-8 argv;
                #  plus ./ipa2vec_ui, the Win32 GUI wrapper in ui/)
make gen        # regenerate src/vectors.h and src/readme_embed.h
```

The binaries embed the full table; they do not read any file at runtime.

## GUI wrapper (Windows)

`ui/ipa2vec_ui.c` is a Win32 GUI front-end (`ipa2vec_ui.exe`,
built by `make ipa2vec_ui`). It uses the **Gentium Book Plus** font
(normative IPA letterforms) and currently provides:

- **File > Export command lines…** — a window showing the three CLI
  invocations (`ipa2vec`, `vec2ipa`, `vec4ipa`) for the current
  directory, with **Copy to clipboard** and **Save as .bat** buttons.
- **File > Exit**, **Help > About**.

Tool integration (input box, live IPA→vector→IPA round-trip) is
planned for a later build.

## Usage

```
ipa2vec <STRING>            parse each segment -> vectors
ipa2vec -i <STRING>         show the two-layer IR, then rebuild IPA (inverse demo)
ipa2vec -j <STRING>         JSON output
ipa2vec -v                  version

vec2ipa <V0,...,V15>        nearest segment + modifier fit -> IPA
vec2ipa -n <V0,...,V15>     nearest base segment only
vec2ipa -d <A> <B>          weighted distance (Mahalanobis + airstream penalty λ)
vec2ipa --width <0-4>       transcription narrowness (default 3)

vec4ipa -i | -t             full information table (main + extIPA bases)
vec4ipa -m                  regional modules and their symbols
vec4ipa -q <SYM>            query one symbol (base / modifier / alias)
vec4ipa -s                  statistics
vec4ipa -w                  metric weights / lambda
vec4ipa <STRING>            forward: IPA -> vectors
vec4ipa -r <V0,...,V15>     reverse: vectors -> IPA
vec4ipa -n <V0,...,V15>     nearest base segment
vec4ipa -d <A> <B>          weighted distance
vec4ipa -h                  help (this README, embedded)
vec4ipa -v                  version
```

### I/O (all tools)

- **stdin**: no input argument — or an explicit `-` — reads from stdin
  (`echo "tʰa" | ipa2vec`, `echo "V0,...,V15" | vec2ipa`)
- **`-o FILE`, `--output FILE`**: write output to FILE (stderr stays on the
  terminal)
- **`-x BASE`, `--ir-out BASE`**: export the two-layer intermediate
  representation to `BASE.layer1` (character-composition order) and
  `BASE.layer2` (feature-tier order), one token per line:
  `BASE<TAB>ipa<TAB>latin` · `MOD<TAB>ipa<TAB>latin<TAB>tier` · `TIE`
- **`--`**: treat every following argument as positional (for strings that
  start with `-`)

## Examples

```sh
$ ipa2vec "tʰeɪk"
[0]    (0.0000, 0.0000, 0.5500, 1.0000, ...)  pulmonic  [asp
[1]    ...
[3]    ...

$ ipa2vec -i "ã"            # precomposed char decomposed like a + ◌̃
  layer1 (char order) : [a:front.opn.unr.vwl] → [◌̃:nas/nasal]
  layer2 (feature order): [a:front.opn.unr.vwl] → [◌̃:nas/nasal]
vector[0]: (... vel_open 0.8000 ...)  pulmonic  [nas
rebuilt[0]: /a◌̃/

$ vec2ipa "1.0000, 0.0000, 0.5500, 0.2500, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.9000, 0.0000, 0.0000, 0.0000, 0.0000, 1.0000"
/p/  (vl.bil.pls +asp)  d=0.8849  ->  /pʰ/

$ vec4ipa -q "ʃ"
base: /ʃ/  vl.pst.frc  (pulmonic)
  (0.0000, 0.2500, 0.2500, 0.6500, ...)
```

## Internal logic (two-layer IR)

The parser follows a strict pipeline:

1. **Precomposed characters** (`ã`, `ẽ`, `ọ` …) are canonically decomposed
   into base + combining sequence, so `ã` and `a + ◌̃` produce identical
   vectors.
2. **Character composition** — the lexer emits tokens in the order they
   appear in the input string (layer 1): base segments (longest-prefix match
   against the 132-entry table), modifier letters, ligature ties (`͡`, `͜`,
   `͠`), and preposed modifiers (`ᵑǃ`, `ˀa`).
3. **Feature ordering** — tokens are re-sorted into the natural-language
   (layer 2) order by feature tier:

   ```
   airstream → laryngeal → place → manner → nasal → timing
   ```

   and applied to the vector **in that order** (order matters, e.g. `asp`
   then `creaky`).

Every token carries a **latin identifier** — a scholarly feature name, not
the symbol itself and not a folk name:

| IPA | latin | | IPA | latin |
|-----|-------|-|-----|-------|
| `p` | `vl.bil.pls` | | `t͡ʃ` | `vl.pst.afc` |
| `b` | `vd.bil.pls` | | `ʘ` | `vl.bil.clk` |
| `s` | `vl.alv.frc` | | `i` | `front.cls.unr.vwl` |
| `ʃ` | `vl.pst.frc` | | `a` | `front.opn.unr.vwl` |
| `m` | `vd.bil.nas` | | `ʰ` | `asp` |

Abbreviations: `vl` voiceless, `vd` voiced, `pls` plosive, `nas` nasal,
`trl` trill, `tap`, `frc` fricative, `lat` lateral, `apx` approximant,
`afc` affricate, `clk` click, `ejt` ejective, `imp` implosive, `bil`
bilabial, `lbd` labiodental, `den` dental, `alv` alveolar, `pst`
postalveolar, `rfl` retroflex, `alvpal` alveolo‑palatal, `pal` palatal,
`vel` velar, `uvu` uvular, `pha` pharyngeal, `epl` epiglottal, `glo`
glottal, `cls` close, `ncls` near‑close, `cmid` close‑mid, `omid`
open‑mid, `nopn` near‑open, `opn` open, `unr` unrounded, `rnd` rounded,
`vwl` vowel.

The full name table is data in [`src/names.tsv`](src/names.tsv) — edit it
and re-run `make gen`.

## Reverse direction

`vec2ipa` maps a vector back to IPA: find the nearest base segment
(weighted Mahalanobis, including `EXTRA_BASE` entries), then greedily add
the modifier that most reduces the residual distance. Verified: **all 132
base segments round-trip losslessly** (forward → reverse → forward
reproduces the vector to ≤ 0.02 per dimension). Modifier reconstruction
is approximate for combinations the greedy search cannot separate (e.g.
a ligature that is not a table entry).

### Transcription narrowness (`--width`)

How many diacritics the reverse fit keeps is controlled by
`--width <0-4>` (default **3**): each level sets the maximum number
of modifiers per segment and the minimum relative distance gain a
modifier must achieve to be kept.

| level | max mods | min gain | style |
| ----- | -------- | -------- | ----- |
| 0 | 2 | 25% | broadest — phonemic, few marks |
| 1 | 3 | 10% | broad |
| 2 | 4 | 4% | medium |
| 3 | 6 | 1.5% | narrow (default) |
| 4 | 10 | 0.1% | narrowest — keep almost every mark |

Example (`t̬˞̩ˤ` → vector → back): `--width 0` gives `/ɾˤ˞/`,
`--width 3` gives `/ɾ̝ˤ̆˞/`. (Place `--width` before `-r`/`-n` —
those consume the vector argument that follows them.)

## Supported notations

- All 132 base segments of `IPA_VECTORS.md` (vowels, consonants,
  affricates, co‑articulated, ejectives, implosives, clicks).
- ExtIPA base segments not in the table: `ʬ ʭ ʩ ʪ ʫ ꞎ ᶑ ᴇ ɚ ɞ ɝ`
  (see `EXTRA_BASE` in `src/ipa2vec_core.h`).
- ASCII alias: Latin `g` == IPA `ɡ`.
- Diacritics of §10: nasalised `̃`, long `ː`, half‑long `ˑ`, aspirated `ʰ`,
  creaky `̰`, breathy `̤` (U+0324), pharyngealised `ˤ/̴`, velarised `ˠ`,
  palatalised `ʲ`, labialised `ʷ`, syllabic `̩`, non‑syllabic `̯`,
  unreleased `̚`, voiceless `̥`, voiced `̬`, nasal‑click `ᵑ` (preposed),
  ejective `ʼ` (U+02BC, sets `cg=1 sg=0 lt=0.6 voiced=0` and airstream =
  glottalic egressive), macron `◌̄` (U+0304, level tone).
- extIPA/clinical marks: dental `̪`, linguolabial `̼`, laminal `̻`, raised
  `̝`/`˔`, lowered `̞`, advanced `̟`, retracted `̠`, more/less rounded
  `̹/̜`, bridged `͆`, apical `̺`, ATR `̘`, RTR `̙`, denasal `̻`,
  mid‑centralised `̽`, rhotacised `˞`, extra‑short `̆`, fortis `͈`,
  lenis `͉`, alveolar `͇`, whistled `͎`, labiodental `ᶹ`, sliding `͢`.
- Ligature ties `͡` `͜` `͠` — table entries (`t͡ʃ`) match directly;
  out‑of‑table pairs (`tɬ`) combine closure + release by the affricate
  rule.
- Implicit (no-tie) affricates per the IPA affricate table:
  `ts dz tʃ dʒ tɕ dʑ ʈʂ ɖʐ tɬ dɮ cç ɟʝ p̪f` each become a single affricate
  segment. Other letter pairs (`gp`) stay separate.
- Precomposed Unicode characters (`ã ẽ ĩ õ ũ ỹ ạ ẹ ọ ụ é è ê ě ē ā ō ī ū ȅ`)
  decompose to base + combining marks.
- Tone letters `˥˦˧˨˩`/`꜒꜓꜔꜕꜖` (5‑level), Chinese tone classes
  `꜀꜁꜂꜃꜄꜅꜆꜇`, upstep `ꜛ`, downstep `ꜜ`, global rise `↗`/fall `↘`,
  and pitch diacritics — see [Tone system](#tone-system-5-level).
- Superscript letters as modifiers (`ʳʴʵʶ ᵉᵌᵤ ᵢᵣ ᴬᴮᴼᴾᵁᵂ ᵊ ⁿ ˡ ˢ`),
  releases (`ˀ` glottal onset, `ʱ` breathy/aspirated), offglides
  (`ᶷ ᶣ ʸ`), stress marks `ˈ ˌ` (ignored), linking undertie `‿`
  (ignored).
- Dotless letters: `ȷ`→`j`; `ı` is `ɪ` when bare (obsolete, warning) but
  plain `i` when followed by diacritics.

Unknown symbols produce a `U+XXXX` error with the byte offset.

## Tone system (5-level)

Tone letters after a segment are grouped into a 5‑field annotation printed
after the vector as `(g1)?(g2)?(g3)?(g4)?(g5)` with `?` as the unknown
placeholder and trailing empty groups omitted:

| input | meaning | output |
| ----- | ------- | ------ |
| `ma˩˨` | 2 letters, single tone | `()?(1,2)` |
| `ma˥˧˩` | 3 letters, 3‑degree single tone | `()?(5,3,1)` |
| `ma˩˨꜓꜒` | 4 letters, single tone + tone sandhi | `()?(1,2)?(4,5)` |
| `ma˥˦˧˨˩˩` | 6 letters, 3‑degree + 3‑degree sandhi | `()?(5,4,3)?(2,1,1)` |
| `maꜛ` | upstep | `()?()?()?(-1,?)` |
| `maꜜ` | downstep | `()?()?()?(1,?)` |
| `ma↗` | global rise | `()?()?()?(?,1)` |
| `ma↘` | global fall | `()?()?()?(?,-1)` |
| `꜅` | Chinese tone class 6 | group 5 = `(-3)` |

Groups: 1 = reserved, 2 = single tone, 3 = tone sandhi, 4 = upstep /
downstep / global contour, 5 = Chinese tone class. Chinese tone classes
`꜀꜁꜂꜃꜄꜅꜆꜇` map to `1, -1, 2, -2, 3, -3, 4, -4`. Tone marks bind to
the preceding segment.

## Regional / tradition modules

Deprecated and regional symbols are organised into **modules** in
`src/ipa2vec_core.h` (the registry `ALIAS_MODULES` lists them).
School-of-linguistics modules (`americanist`, `sinologist`, `indologist`,
`polish`, `teuthonista`, `koreanologist`, `japanologist`, `africanist`,
`oed`) resolve their symbols by default but print a warning listing
**every** school that contains the symbol:

```
ipa2vec: warning: using symbol 'ł' from americanist, polish — enable with --americanist --polish
```

Pass `--<name>` (e.g. `--polish`) to use that school's readings without
a warning. When a symbol exists in several enabled schools, the
**command-line order** decides: `--polish --americanist ł` gives Polish
[w], `--americanist --polish ł` gives Americanist [ɬ]. `generic`,
`withdrawn`, `equiv` and `uppercase` are always on and never warn.

| module | symbols |
| ------ | ------- |
| `generic` | `?`→`ʔ`, `я`→`ʢ`, `∅ Ø` null, `ȷ ɫ ı` dotless/dark, small-capital glyphs |
| `withdrawn` | ƍ σ ƺ ƪ ƻ ƾ ʦ ʣ ʧ ʤ ʨ ʥ ʇ ʗ ʖ ʞ ƥ ƭ ƈ ƙ ʠ ƞ ƫ ʓ ʆ ɼ ɩ ʚ ɷ ω ȣ |
| `americanist` | š č ž ǰ ǧ ǯ ẋ ƛ ł λ |
| `sinologist` | ɿ ʅ ʮ ʯ ᴀ, plus base segments ȶ ȡ ȵ ȴ (alveolo-palatal stop/nasal/lateral, gated on `--sinologist`) |
| `indologist` | ḍ ṭ ṇ ṛ ḷ ṣ ś ṃ ṅ ñ ḥ ḫ ẓ ẖ ḏ ṯ ġ ḡ ḻ ṟ ṁ |
| `polish` | ź ć ż, plus Polish values for č š ž ł (conflict with Americanist) |
| `teuthonista` | ƀ đ ǥ ǩ ȟ ǵ |
| `koreanologist` | Ǝ→ɤ, `K P T` fortis |
| `japanologist` | `Q` sokuon, `N` syllabic nasal |
| `africanist` | ȹ ȸ |
| `oed` | ᵻ ᵿ |
| `uppercase` | `G`→`ɢ`, `R`→`ʀ`, `Œ`→`ɶ` (only explicitly listed; no shape extrapolation) |

## Inference reporting

Every inference the parser makes is reported to **stderr**:

- `note: inferred tie: 'ts' -> 't͡s'` — implicit (no-tie) affricates merged
- `note: inferred affricate with synthesized tie` — out-of-table pairs
  (`tɬ`, `dɮ`, `cç`, `ɟʝ`, `p̪f`)
- `note: ASCII 'g' interpreted as IPA ɡ`
- `note: ... reinterpreted ...` — symbol reinterpretation: ASCII `'` →
  unreleased, `′` → palatalization (Irish), `ʻ ‘ ‛` → weak aspiration,
  `ʱ` → breathy/aspirated release
- `note: '<alias>' -> <repl> (<name>)` — any deprecated / non-standard
  mapping
- `warning: '<alias>' -> <repl> (<name>)` — deprecated or ambiguous usage
  where the formal reading was preferred (`ʞ`→`ǃ`, `Q`→gemination,
  `K P T`→fortis, bare `ı`→`ɪ`)

## Stress tests

Run the full suite:

```sh
python3 tools/test_suite.py       # 122 checks: parsing, tone, regional,
                                  # inference, warnings, round-trip
```

**The clinical/extIPA stress string** — every feature in one input
(glottal onset, rhotacised vowel, apical, undertie, stress,
mid-centralised, offglides, pharyngealisation, dentalisation, fricative
release, syllable break, downstep, nasalised linguolabial, half-long,
tone classes, 5-level tones, tone sandhi, global rise, prosodic breaks,
creak, breathy, dotless i, diaeresis, labio-palatal offglide, syllabic,
lateral release, non-syllabic, nasal release, denasal, palatalised,
retracted, more-open, rhotacised, lowered, velarised, unreleased,
extra-high tone, more-close, voiced, voiceless ring, retroflex hook,
precomposed accented vowels, labiodental plosives (ȹ ȸ), alveolo-palatal
(ȶ ȡ), ejectives, clicks, implosives, lateral affricates, pitch contours):

```
ˀɝ̺̆k‿ˈo̽ːᶷˌre̴̪pstˢ.ꜜã̼ˑd꜅˩˦˧꜕꜖꜒↗|ba̜˔z̟ʱ.tsᵊn↗‖z̥ı̤̃ˤt̬ṵ̈ːdᶣ.r̥ʰl̩pˡ.hr̯ʱdⁿ|
βʷᵿ̻ʑ̩ʲːn̠↘‖ø̙˞˕dˠ̚‖ʎ̯e̘̋t̬˞̩ˤŋ̊.ɺ̢ é̙dɮ.ȹē̹ʟʈʼ.ȸè̜.ȶʎ̝̥ʼȅ̞ȡ.kʟ̝̊ʼě̝ʡ̯.tɬʼḛ̂ʙ.
ʘe̤᷄ɗ.χʼe̥᷅ǃ.ʛe᷇ǂ.ɧe᷆t͡s.ʑe᷉ɡ͡b.ŋ͡mʍ̩ɥe᷈ɫ
```

`ipa2vec "<above>"` parses all **76 segments**; the tone annotation on the
`d꜅˩˦˧꜕꜖꜒↗` group reads `tone=()?(1,4,3)?(2,1,5)?(?,1)?(-3)`.

## Files

| File | Purpose |
| ---- | ------- |
| `src/ipa2vec_core.h` | shared core: UTF-8, modifiers, aliases (modules), lexer, canonicaliser, applier, reverse fit |
| `src/ipa2vec_main.c` | `ipa2vec` — IPA → vectors (parse, IR, JSON) |
| `src/vec2ipa_main.c` | `vec2ipa` — vectors → IPA (nearest, reverse fit, distance) |
| `src/vec4ipa_main.c` | `vec4ipa` — inventory + both directions |
| `src/vectors.h` | generated: 132 base segments + metric weights + latin names |
| `src/names.tsv` | data: symbol → scholarly feature name (edit + `make gen`) |
| `src/readme_embed.h` | generated: this README embedded for `vec4ipa -h` |
| `tools/gen_vectors_h.py` | regenerates `src/vectors.h` |
| `tools/gen_readme_embed.py` | regenerates `src/readme_embed.h` |
| `tools/test_suite.py` | 122-check regression suite (incl. the stress string) |
| `docs/SPEC.md` | the 16-D vector specification |
| `IPA_VECTORS.md` | the 132-segment vector table (data for the generator) |
| `METRIC.md` | metric derivation (weights, λ) |
| `metric.json` | machine-readable weights + λ (v3) |
| `Makefile` | build all three tools (auto `-municode` on Windows) |

## License

MIT — see [`LICENSE`](LICENSE).
