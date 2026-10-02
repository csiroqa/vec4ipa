# tools/data/consonant

Produced by `python tools/fetch_consonant_data.py`. Nothing here was
interpolated, and no vowel measurement has been relabelled as a consonant.

## Why this directory exists

All nine formant datasets in `tools/data/` are vowel-only. A vowel makes no
tip or root gesture, so those tongue coordinates cannot vary in that corpus and
their apparent coefficients are meaningless (`tools/fit_tongue_forward.py`
already says so). This directory holds the measured consonant material that was
actually obtainable from the network, so that the dead-axis question can be
tested with real numbers instead of left open.

## What was obtained

| file | what it measures | rows | languages |
|---|---|---|---|
| `raw/G6PJ5F_laterals_data_ns_tab.txt` | `/l/` F1 and F2 in Hz, clear vs dark | 383 | German (native) |
| `raw/G6PJ5F_laterals_data_learners_tab.txt` | `/l/` F1 and F2 in Hz, clear vs dark | 897 | German learner English |
| `emudata_stops10_b_d_g_spectra.csv` | 129-bin burst spectrum, 10 ms after release | 72 tokens (b/d/g, 24 each) | German |
| `emudata_keng_aspiration_spectra.csv` | 257-bin noise spectrum of `/k/` aspiration | 23 segments | Australian English |
| `epmc_consonant_table_rows.json` | F1–F4 of Greek vowels keyed by preceding fricative | 8 rows (ɣ, ʝ × 2 varieties) | Greek |

Consonant segments with a measurement of the consonant itself: `/l/ /b/ /d/
/g/ /k/ /ɣ/ ʝ/` — 7 symbols, 3 languages. The Greek rows are labelled
`measure_target: consonant-conditioned`, because the formants there belong to
the neighbouring vowel; they are evidence about place, not consonant formants,
and the label is there so they cannot be misread.

## The one measurement worth making immediately

Mean burst-spectrum peak bin, from `emudata_stops10_b_d_g_spectra.csv`
(129 bins; the frequency axis of this object is NOT documented, so bins, not
Hz):

| stop | mean peak bin | per-token sd |
|---|---|---|
| b | 8.1 | 8.3 |
| g | 28.5 | 13.1 |
| d | 47.1 | 18.8 |

Labial < velar < alveolar, the classic burst locus ordering. Place is audible
in the noise, and place is exactly what the tip / dorsum / lip coordinates
encode. This is a small sample from one speaker, not a validation.

## What is NOT here, and why

* **PhoneticBank** (multi-language fricative and affricate spectra) — TLS
  failure from every route: direct, and no capture in the Wayback CDX index
  (`numFound=0`). This is the most valuable source for the ʃ/ɕ question and it
  remains unreachable.
* **TIMIT** — absent from OpenSLR. 115 resource descriptors were read and no
  TIMIT exists there.
* **Zeno/HuggingFace** — `zenodo.org` returns 403, `huggingface.co` fails TLS.
* **emudata files that need R** — `dorfric`, `sib`, `plos`, `dorsal`, `fr`,
  `stops2` are downloaded and stored in `raw/emudata/`, but pyreadr refuses
  EMU trackdata objects. They hold German fricative spectra and would be worth
  loading where R is available. Their contents are unverified here.

## Coverage against the four known gaps

* ɕ vs ʃ — **not covered**. No palatal-fricative dataset was reachable.
* lips vs jaw — **not covered**. No jaw-position measurement was reachable.
* dead tongue axes — **partly covered**: `/b/` (lips), `/d/` (tip), `/g/` and
  `/k/` and `/ɣ/` (dorsum), `/l/` (tip + dorsum). The **blade** and the
  **root** still have nothing that varies them.
* place = 0.00 overloading — untestable from this material; it needs
  consonants of the same place but different manner.

## Files written by the fetch script

* `screen_report.json` — the current screen's verdict on every file still on
  disk, plus records carried over for files that a later prune deleted.
* `fetch_manifest.json` — every attempt: source, URL, HTTP status, byte count
  or the exact error. 1060 attempts, 66 succeeded, 154.9 MB retrieved. It also
  holds the per-file rejection record of the first sweep (967 `DataverseNO-file`
  rows: 627 "no acoustic column", 274 "fewer than 3 columns", 36 "no column
  delimiter", and 9 others). Those reasons come from the first, looser version
  of the screen; the screen was then rewritten and re-run offline, which is how
  the 19 vowel tables that first pass accepted were caught.
* `consonant_measurements.json` — the 2 files that passed the current screen.
* `stage_*.json` — per-stage results, so one stage can be re-run with
  `--stage` without losing the others.
* `raw/` — the two accepted files, unaltered, plus `raw/emudata/*.rda` (23 MB,
  stored for anyone with R). The 111.9 MB of rejected downloads were deleted by
  `--stage prune`; the manifest is the record of what they were.

Reproduce with:

```
python tools/fetch_consonant_data.py                     # everything, ~50 min
python tools/fetch_consonant_data.py --stage screen      # re-screen offline
```