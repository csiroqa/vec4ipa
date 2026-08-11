#!/usr/bin/env python3
"""Metric-space sanity suite: nearest-base anchors and round-trip.

Guards the fitted metric (metric.json) and the vector table against the
"overfit" failure class where an extension of a segment lands on a
wrong-place base (e.g. ãː → /ɲ/ when `effective_oral_area` or the
nasalised-vowel value collapse).  Every check drives the real binaries:

  * every vowel-like base × {nasalised, long, both} anchors to a vowel;
  * homorganic consonant extensions anchor to the expected base
    (voicing rings, aspiration, unrelease, creak→ejective, syllabic,
    nasalised fricatives, secondary articulations);
  * a few documented near-neighbours stay where they are (x̃ → ʩ etc.);
  * every rebuilt spelling re-parses to the same vector (≤ 0.02).

Run:  python tools/test_metric_space.py [ipa2vec] [vec2ipa]
"""

import re
import sys
from pathlib import Path

import _common
from _common import (MD_LINE_RE, check_cond, fmt_vec, is_vowel_like,
                     parse_rebuilt, parse_vector, run)

ROOT = Path(__file__).resolve().parents[1]
EXE = sys.argv[1] if len(sys.argv) > 1 else ROOT / ("ipa2vec" + _common.BIN_SUFFIX)
VEC2IPA = sys.argv[2] if len(sys.argv) > 2 else ROOT / ("vec2ipa" + _common.BIN_SUFFIX)
VECTORS_MD = ROOT / "IPA_VECTORS.md"

def check(name, cond, detail=""):
    return check_cond(name, cond, detail)

_vector_cache = {}
def vector_of(ipa):
    if ipa not in _vector_cache:
        r = run(EXE, [ipa])
        if r.returncode != 0:
            _vector_cache[ipa] = None
        else:
            _vector_cache[ipa] = [float(x) for x in
                                  parse_vector(r.stdout).split(",")]
    return _vector_cache[ipa]

_nearest_cache = {}
def nearest_vec(v, charsets=()):
    key = (tuple(v), tuple(charsets))
    if key not in _nearest_cache:
        args = [a for cs in charsets for a in ("--symbols", cs)]
        r = run(VEC2IPA, args + ["-n", fmt_vec(v)])
        _nearest_cache[key] = (r.stdout.split("  ")[0]
                               if r.returncode == 0 else "ERR")
    return _nearest_cache[key]

_base_cache = {}
def nearest_base(ipa):
    if ipa not in _base_cache:
        v = vector_of(ipa)
        if v is None:
            _base_cache[ipa] = "ERR"
        else:
            nb = nearest_vec(v)
            _base_cache[ipa] = nb if nb == "ERR" else nb[1:-1]
    return _base_cache[ipa]

# ------------------------------------------------------------------
# 1. vowel-like bases × {nasalised, long, both} must anchor to a vowel
# ------------------------------------------------------------------
VOWELS = []
for line in open(VECTORS_MD, encoding="utf-8"):
    m = MD_LINE_RE.match(line.strip())
    if m:
        vals = [float(x) for x in m.group(2).split(",")]
        if is_vowel_like(vals):
            VOWELS.append(m.group(1))

for v in VOWELS:
    for ext in (v + "̃", v + "ː", v + "̃ː"):
        nb = nearest_base(ext)
        check(f"vowel anchor {ext}", nb in VOWELS, f"-> {nb}")

# the canonical reductio regression
check("ãː anchors to a vowel (not a nasal)", nearest_base("ãː") in VOWELS,
      f"-> {nearest_base('ãː')}")
check("ãː full rebuild = a + ◌̃ + ː",
      nearest_base("ãː") in VOWELS and
      parse_rebuilt(run(VEC2IPA, ["-r", fmt_vec(vector_of("ãː"))]
          ).stdout).strip() in
      ("ãː", "aː̃"), "")

# ------------------------------------------------------------------
# 2. homorganic consonant extensions
# ------------------------------------------------------------------
VOICING = [
    ("b̥", "p"), ("p̬", "b"), ("d̥", "t"), ("t̬", "d"),
    ("ɡ̊", "k"), ("k̬", "ɡ"), ("v̥", "f"), ("f̬", "v"),
    ("z̥", "s"), ("s̬", "z"), ("ʒ̊", "ʃ"), ("ʃ̬", "ʒ"),
    ("ð̥", "θ"), ("θ̬", "ð"), ("β̥", "ɸ"), ("ɸ̬", "β"),
    ("ɣ̊", "x"), ("x̬", "ɣ"), ("ʁ̥", "χ"), ("χ̬", "ʁ"),
    ("ʕ̥", "ħ"), ("ħ̬", "ʕ"), ("ʂ̬", "ʐ"), ("ʐ̥", "ʂ"),
    ("ɕ̬", "ʑ"), ("ʑ̥", "ɕ"),
]
for ipa, want in VOICING:
    check(f"voicing ring {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

ASP = [("pʰ", "p"), ("tʰ", "t"), ("kʰ", "k"), ("cʰ", "c"),
       ("tɕʰ", "t͡ɕ"), ("tsʰ", "t͡s"), ("tʂʰ", "ʈ͡ʂ")]
for ipa, want in ASP:
    check(f"aspirated {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

UNREL = [("p̚", "p"), ("t̚", "t"), ("k̚", "k"), ("m̚", "m"), ("n̚", "n")]
for ipa, want in UNREL:
    check(f"unreleased {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

# creaky stops are PHONATION variants of the base (aperture/tension
# differ); with the larynx-height weight at 6 the ejective mechanism
# (larynx +1) stays far enough that the nearest base is the plain stop
CREAK = [("p̰", "p"), ("t̰", "t"), ("k̰", "k"), ("q̰", "q")]
for ipa, want in CREAK:
    check(f"creaky stop {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

NASALFRIC = [
    ("ɸ̃", "ɸ"), ("f̃", "f"), ("θ̃", "θ"), ("s̃", "s"), ("ʃ̃", "ʃ"),
    ("β̃", "β"), ("ṽ", "v"), ("ð̃", "ð"), ("z̃", "z"), ("ʒ̃", "ʒ"),
    ("ɣ̃", "ŋ"),   # homorganic velar nasal
]
for ipa, want in NASALFRIC:
    check(f"nasalised fricative {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

SYL = [("m̩", "m"), ("n̩", "n"), ("ŋ̍", "ŋ"), ("l̩", "l"), ("r̩", "ɹ")]
for ipa, want in SYL:
    check(f"syllabic {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

SECONDARY = [
    ("tʷ", "t"), ("kʷ", "k"), ("lʷ", "l"), ("sʷ", "ʃ"),  # rounding → rounded sibilant
    ("lˠ", "l"), ("tʲ", "t"), ("sʲ", "s"), ("kʲ", "k"),  # no base rows: anchor to the unmodified base
    ("tˤ", "t"), ("kˤ", "k"),
]
for ipa, want in SECONDARY:
    check(f"secondary {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

# ------------------------------------------------------------------
# 3. documented near-neighbours (semantically correct, kept on purpose)
# ------------------------------------------------------------------
DOC = [
    # voiced aspirated stops: since v9 (voicing weight raised by the
    # corrected aggregation fix) they anchor to the VOICED base and
    # round-trip losslessly (bʱ -> /b/ + ʱ -> "bʱ"); pre-v9 they fell
    # on the voiceless stop
    ("bʱ", "b"), ("dʱ", "d"), ("ɡʱ", "ɡ"),
]
for ipa, want in DOC:
    check(f"documented {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")
# ʩ (velopharyngeal fricative) is the only voiceless nasal fricative
# base; x̃ is velar voiceless nasalised — a place-exact match.  ʩ is in
# the extipa charset class: default std falls back to /x/ (the rebuild
# still spells x̃), --symbols extipa reaches the ʩ target.
check("documented x̃ -> /x/ under default std charset",
      nearest_base("x̃") == "x", f"-> {nearest_base('x̃')}")
check("documented x̃ -> /ʩ/ with --symbols extipa",
      nearest_vec(vector_of("x̃"), ("extipa",)) == "[ʩ]", "")

# ------------------------------------------------------------------
# 4. rebuilt spellings re-parse to the same vector
# ------------------------------------------------------------------
ROUNDTRIP = [
    "ãː", "ĩː", "ũː", "ɯ̃", "ɨ̃ː", "pʰ", "tʷ", "kʲ", "ɸ̃", "β̃",
    "b̥", "p̚", "p̰", "t͡sʰ", "lˠ", "ŋ̍", "dʱ", "ɺ̃", "ɑ̃ː", "yː",
]
for ipa in ROUNDTRIP:
    v1 = vector_of(ipa)
    if v1 is None:
        check(f"rebuild {ipa}", False, "parse failed")
        continue
    r = run(VEC2IPA, [fmt_vec(v1)])
    rebuilt = parse_rebuilt(r.stdout).strip()
    v2 = vector_of(rebuilt)
    if v2 is None:
        check(f"rebuild {ipa}", False, f"rebuilt {rebuilt} unparseable")
        continue
    dv = max(abs(a - b) for a, b in zip(v1, v2))
    check(f"rebuild {ipa} -> {rebuilt}", dv <= _common.TOL_REBUILD,
          f"max|dv|={dv:.4f}")

# ------------------------------------------------------------------
# 4b. duration-band collisions: distinct spellings must yield distinct
# vectors, and each must rebuild losslessly.  Regression for the
# duration-axis conflation fixes:
#   B1: pː == p̚  (mod_long step 0.1 collided with mod_unrel's 0.1)
#   B2: ɡ̩ == ɣ̝̩ etc.  (syllabic stop floor 1.5 == raised fricative)
#   B3: t̩ == tˑ etc.  (syllabic 1.5 == half-long 1.5 on short bases)
# ------------------------------------------------------------------
DISTINCT_PAIRS = [
    ("pː", "p̚"),
    ("ɡ̩", "ɣ̝̩"),
    ("k̩", "x̝̩"),
    ("ɢ̩", "ʁ̝̩"),
    ("t̩", "tˑ"),
    ("m̩", "mˑ"),
    ("n̩", "nˑ"),
    ("l̩", "lˑ"),
    ("r̩", "rˑ"),
    ("ʂ̩", "ʂˑ"),
]
for a, b in DISTINCT_PAIRS:
    va, vb = vector_of(a), vector_of(b)
    check(f"distinct duration spellings {a} vs {b}",
          va is not None and vb is not None and va != vb,
          f"{va} == {vb}")

DUR_BAND = [
    "pː", "p̚", "ɡ̩", "k̩", "ɢ̩", "ɣ̝̩", "t̩", "tˑ", "m̩", "mˑ",
    "n̩", "nˑ", "l̩", "lˑ", "r̩", "rˑ", "ʂ̩", "ʂˑ",
    "ʈ͡ʂ̩", "ʈ͡ʂˑ", "ʈ͡ʂː",
]
for ipa in DUR_BAND:
    v1 = vector_of(ipa)
    if v1 is None:
        check(f"duration-band rebuild {ipa}", False, "parse failed")
        continue
    r = run(VEC2IPA, [fmt_vec(v1)])
    rebuilt = parse_rebuilt(r.stdout).strip()
    v2 = vector_of(rebuilt)
    if v2 is None:
        check(f"duration-band rebuild {ipa}", False,
              f"rebuilt {rebuilt} unparseable")
        continue
    dv = max(abs(a - b) for a, b in zip(v1, v2))
    check(f"duration-band rebuild {ipa} -> {rebuilt}",
          dv <= _common.TOL_REBUILD, f"max|dv|={dv:.4f}")

# ------------------------------------------------------------------
# 5. tone letters / pitch marks survive the forward-reverse rebuild
# ------------------------------------------------------------------
TONE_CASES = [
    ("ma˥",         "a˥"),
    ("ma˥˩",        "a˥˩"),
    ("ma˧˥",        "a˧˥"),
    ("ma˨˩˦",       "a˨˩˦"),
    ("ma˩˨꜓꜒",     "a˩˨꜓꜒"),
    ("maꜛ",         "ꜛa"),   # upstep is PREPOSED (marks the following syllable)
    ("maꜜ",         "ꜜa"),
    ("ma↗",         "a↗"),
    ("ma↘",         "a↘"),
    ("ma꜅",         "a꜅"),
    ("ma꜆˩",        "a˩꜆"),
    ("ma˧ꜛ↗꜂",      "ꜛa˧↗꜂"),
    ("ma˦˩˩",       "a˦˩˩"),
    # precomposed tone vowels -> base + 5-level tone letters
    # (IPA convention: ́=high ˦, ̀=low ˨, ̂=falling ˥˩, ̌=rising ˩˥,
    #  ̏=extra-low ˩, ̄=mid ˧, ̋=extra-high ˥)
    ("má",          "a˦"),
    ("mà",          "a˨"),
    ("mâ",          "a˥˩"),
    ("mǎ",          "a˩˥"),
    ("mȁ",          "a˩"),
    ("mā",          "a˧"),
    ("ma\u030B",    "a˥"),
    ("mé",          "e˦"),
    ("mí",          "i˦"),
    ("mó",          "o˦"),
    ("mú",          "u˦"),
    ("mý",          "y˦"),
    ("mǒ",          "o˩˥"),
    ("ma\u1DC4",    "a˦˥"),   # ᷄ high rising
    ("ma\u1DC5",    "a˩˨"),   # ᷅ low rising
    ("ma\u1DC6",    "a˥˦"),   # ᷆ high falling
    ("ma\u1DC7",    "a˧˦"),   # ᷇ mid rising
    ("ma\u1DC8",    "a˧˦˧"),  # ᷈ rising-falling
    ("ma\u1DC9",    "a˦˧˦"),  # ᷉ falling-rising
    # decomposed tone diacritics behave identically
    ("ma\u0301",    "a˦"),
    ("ma\u0300",    "a˨"),
    ("ma\u0302",    "a˥˩"),
    ("ma\u030c",    "a˩˥"),
    ("ma\u030f",    "a˩"),
    ("ma\u0304",    "a˧"),
]
def rebuilt_of(s):
    r = run(EXE, ["-L", s])
    if r.returncode != 0:
        return None
    out = []
    for l in r.stdout.splitlines():
        if "rebuilt[" in l:
            # phonetic-level rebuild prints [x] (narrowest ⟦x⟧); earlier
            # builds used phonemic /x/ — accept both
            m = re.search(r"rebuilt\[\d+\]:\s*(?:/|\[|\u27E6)\s*([^\s/\]]+)\s*", l)
            if m:
                out.append(m.group(1))
    return out

for inp, want in TONE_CASES:
    rb = rebuilt_of(inp)
    if not rb or len(rb) != 2:
        check(f"tone rebuild {inp}", False, f"unexpected -i output: {rb!r}")
        continue
    check(f"tone rebuild {inp}", rb[1] == want, f"got {rb[1]}")

# precomposed timing / centralisation marks (i rebuilds dotless: the
# breve sits above, covering the dot)
TIMING_CASES = [
    ("mă",  "ă"), ("mĕ", "ĕ"), ("mĭ", "ı̆"), ("mŏ", "ŏ"), ("mŭ", "ŭ"),
    ("mä",  "a"),  ("më", "ë"), ("mö", "ö"), ("mü", "ü"),
]
for inp, want in TIMING_CASES:
    rb = rebuilt_of(inp)
    if not rb or len(rb) != 2:
        check(f"timing rebuild {inp}", False, f"unexpected -i output: {rb!r}")
        continue
    check(f"timing rebuild {inp}", rb[1] == want, f"got {rb[1]}")

# dotless i/j: an above mark covers the dot, so the rebuild uses the
# dotless form (ı/ȷ); the voiceless ring goes above on i/j (ı̊, ȷ̊)
DOTLESS_CASES = [
    ("ȷ̊",  "ȷ̊"),   # dotless j + ring above stays dotless
    ("j̊",  "ȷ̊"),   # dotted j + ring above -> dotless (ring covers the dot)
    ("ı̊",  "ı̊"),   # dotless i + ring above stays dotless
    ("i̥",  "ı̊"),   # dotted i + ring below -> ring moves above, dotless
    ("ı̥",  "ı̊"),   # dotless i + ring below -> ring normalised above
    ("ĩ",  "ı̃"),   # nasal tilde above -> dotless
    ("i̩",  "i̩"),   # syllabic stroke below -> dot stays (not covered)
    ("ȷ",  "ȷ"),    # bare dotless j stays dotless
]
for inp, want in DOTLESS_CASES:
    rb = rebuilt_of(inp)
    if not rb or len(rb) != 1:
        check(f"dotless rebuild {inp}", False, f"unexpected -i output: {rb!r}")
        continue
    check(f"dotless rebuild {inp}", rb[0] == want, f"got {rb[0]}")

# reverse path: the voiceless i/j vectors spell ı̊ / ȷ̊ (ring above, dotless)
I_VL_VEC = [0.0, 0.4, 0.0, -0.3, 0.25, -0.4, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 1.0, 0.0, 0.4, 1.0]
J_VL_VEC = [0.0, 0.4, 0.0, -0.3, 0.25, -0.4, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 1.0, 0.0, 0.3, 1.0]
check("reverse i+vl -> ı̊",
      parse_rebuilt(run(VEC2IPA, [fmt_vec(I_VL_VEC)]).stdout) == "ı̊",
      run(VEC2IPA, [fmt_vec(I_VL_VEC)]).stdout.splitlines()[-1][:60])
check("reverse j+vl -> ȷ̊",
      parse_rebuilt(run(VEC2IPA, [fmt_vec(J_VL_VEC)]).stdout) == "ȷ̊",
      run(VEC2IPA, [fmt_vec(J_VL_VEC)]).stdout.splitlines()[-1][:60])

# ------------------------------------------------------------------
# 6. reverse uses standard IPA only (no ȶ ȡ ȵ ȴ ᴇ)
# ------------------------------------------------------------------
# ᴇ (lowered e, small-cap display letter) -> standard spelling e̞
E_VEC = [0.0, 0.35, 0.0, 0.0, 0.25, -0.2, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.7, 1.0]
check("ᴇ vector nearest is e", nearest_base("e̞") != "ERR" and
      nearest_vec(E_VEC) == "[e]",
      run(VEC2IPA, ["-n", fmt_vec(E_VEC)]).stdout.splitlines()[0][:40])
check("ᴇ vector rebuilds as e̞",
      parse_rebuilt(run(VEC2IPA, [fmt_vec(E_VEC)]).stdout) == "e̞",
      run(VEC2IPA, [fmt_vec(E_VEC)]).stdout.splitlines()[0][:60])
# Sinologist curl letters are never reverse targets by default; they are
# modeled as pre-palatal (place 0.0 + palatal body 0.40 + no tip
# gesture), so each falls back EXACTLY to the composed palatal spelling:
# ȶ -> c̟, ȡ -> ɟ̟, ȵ -> ɲ̟ (dialectology reads ȵ ~ ɲ), ȴ -> ʎ̟
for curl, base in (("ȶ", "c"), ("ȡ", "ɟ"), ("ȵ", "ɲ"), ("ȴ", "ʎ")):
    nb = nearest_vec(vector_of(curl))
    check(f"{curl} vector not rebuilt as {curl} by default", nb != f"[{curl}]", nb)
    check(f"{curl} vector falls back to [{base}]", nb == f"[{base}]", nb)
    rb = parse_rebuilt(run(VEC2IPA, [fmt_vec(vector_of(curl))]).stdout).strip()
    check(f"{curl} rebuilds as {base}\u031f (d=0)", rb == f"{base}\u031f", rb)
# --symbols is repeatable and accumulates; any combination is allowed
check("--symbols sinologist allows ȶ",
      nearest_vec(vector_of("ȶ"), ("sinologist",)) == "[ȶ]", "")
check("--symbols sinologist allows ᴇ (small-cap is Sinologist)",
      nearest_vec(E_VEC, ("sinologist",)) == "[ᴇ]", "")
check("standard rhotacised ɝ kept under any charset",
      nearest_vec(vector_of("ɝ")) == "[ɝ]"
      and nearest_vec(vector_of("ɝ"), ("std",)) == "[ɝ]", "")
check("extIPA ʬ gated by default (std), enabled by --symbols extipa",
      nearest_vec(vector_of("ʬ")) != "[ʬ]"
      and nearest_vec(vector_of("ʬ"), ("extipa",)) == "[ʬ]", "")
check("--charset std + sinologist: combo without extIPA",
      nearest_vec(E_VEC, ("std", "sinologist")) == "[ᴇ]"
      and nearest_vec(vector_of("ʬ"), ("std", "sinologist")) != "[ʬ]", "")
check("--charset bad value rejected",
      run(VEC2IPA, ["--charset", "bogus", fmt_vec(E_VEC)]).returncode == 1, "")

# ------------------------------------------------------------------
# 7. every standard base is its own nearest base (place is primary)
# ------------------------------------------------------------------
# Regression guard for the p̪/ɱ case: the labiodental stop/nasal were
# base rows whose vectors coincided with p/m (lips_closed is 1.0 for
# both bilabial and labiodental closures), so they fell back to /p//m/.
# They are now described by the dental dimension (tongue_tip_pos 1.0, same as
# t̪ θ ð), and the derived spellings b̪ m̪ agree with the base rows.
VECTORS_H = ROOT / "src" / "vectors.h"
for line in VECTORS_H.read_text(encoding="utf-8").splitlines():
    m = re.search(r'\{ "([^"]+)", \{', line)
    if not m:
        continue
    ipa = m.group(1)
    v = vector_of(ipa)
    if v is None:
        check(f"base {ipa} parses", False, "parse failed")
        continue
    got = nearest_vec(v)
    check(f"base {ipa} is its own nearest base", got == f"[{ipa}]", got)
for derived, base in (("p̪", "p\u032a"), ("m̪", "ɱ")):
    v1, v2 = vector_of(derived), vector_of(base)
    dv = max(abs(a - b) for a, b in zip(v1, v2)) if v1 and v2 else None
    check(f"{derived} agrees with {'base row' if base == '\u0271' else 'p+\u032a'}",
          dv is not None and dv <= _common.TOL_REBUILD, f"max|dv|={dv}")

# ------------------------------------------------------------------
# 8. approximate rebuilds (semantically right, small residual by design)
# ------------------------------------------------------------------
APPROX = [
    # the voicing ring is a *partial* voicing change (keeps the base's
    # duration/jet focus), so s̬ rebuilds as z̬ with a 0.1 duration gap
    ("s̬", 0.12), ("ʃ̬", 0.12),
    # labialised s lands on the rounded sibilant ʃ (nearest base)
    ("sʷ", 0.12),
]
for ipa, tol in APPROX:
    v1 = vector_of(ipa)
    r = run(VEC2IPA, [fmt_vec(v1)])
    rebuilt = parse_rebuilt(r.stdout).strip()
    v2 = vector_of(rebuilt)
    dv = max(abs(a - b) for a, b in zip(v1, v2))
    check(f"approx {ipa} -> {rebuilt}", dv <= tol, f"max|dv|={dv:.4f}")

# ------------------------------------------------------------------
# 9. full IPA consonant chart (every cell parses, rebuilds re-parse,
#    and no unexpected warnings) - regression guard for the chart as
#    printed in the Handbook of the IPA (Chinese edition layout)
# ------------------------------------------------------------------
CHART = [
    # nasals
    "m̥","m","ɱ̊","ɱ","n̼","n̥","n","ɳ̊","ɳ","ɲ̊","ɲ","ŋ̊","ŋ","ɴ̥","ɴ",
    # plosives
    "p","b","p̪","b̪","t̼","d̼","t","d","ʈ","ɖ","c","ɟ","k","ɡ","q","ɢ","ʡ","ʔ",
    # sibilant affricates
    "ts","dz","t̠ʃ","d̠ʒ","ʈʂ","ɖʐ","tɕ","dʑ",
    # non-sibilant affricates
    "pɸ","bβ","p̪f","b̪v","t̪θ","d̪ð","tɹ̝̊","dɹ̝","t̠ɹ̠̊˔","d̠ɹ̠˔","cç","ɟʝ","kx","ɡɣ","qχ","ʡʢ","ʔh",
    # sibilant fricatives
    "s","z","ʃ","ʒ","ʂ","ʐ","ɕ","ʑ",
    # non-sibilant fricatives
    "ɸ","β","f","v","θ̼","ð̼","θ","ð","θ̠","ð̠","ɹ̠̊˔","ɹ̠˔","ɻ˔","ç","ʝ","x","ɣ","χ","ʁ","ħ","ʕ","ʜ","ʢ","h","ɦ",
    # approximants
    "ʋ̥","ʋ","ɹ̥","ɹ","ɻ̊","ɻ","j̊","j","ɰ̊","ɰ","ʔ̞",
    # taps / flaps
    "ⱱ̟","ⱱ","ɾ̼","ɾ̥","ɾ","ɽ̊","ɽ","ɢ̆","ʡ̆",
    # trills
    "ʙ̥","ʙ","r̥","r","ɽ̊r̥","ɽr","ʀ̥","ʀ",
    # lateral affricates
    "tɬ","dɮ","ʈɭ̊˔","cʎ̝̊","kʟ̝̊","ɡʟ̝",
    # lateral fricatives
    "ɬ","ɮ","ɭ̊˔","ɭ˔","ʎ̝̊","ʎ̝","ʟ̝̊","ʟ̝",
    # lateral approximants
    "l̥","l","ɭ̊","ɭ","ʎ̥","ʎ","ʟ̥","ʟ","ʟ̠",
    # lateral flaps
    "ɺ","ɭ̆","ʎ̆","ʟ̆",
    # extIPA / Unicode 15 extended symbols
    "ʩ","ʪ","ʫ","ʬ","ʭ","¡","ꞎ",
    "𝼅","𝼆","𝼆̬","𝼄","𝼄̬","𝼀","𝼃","𝼁","𝼇","ꞯ","𝼂",
    # ejective plosives
    "pʼ","tʼ","ʈʼ","cʼ","kʼ","qʼ","ʡʼ",
    # ejective affricates / fricatives
    "t̪θʼ","tsʼ","t̠ʃʼ","ʈʂʼ","kxʼ","qχʼ","ɸʼ","fʼ","θʼ","sʼ","ʃʼ","ʂʼ","çʼ","xʼ","χʼ",
    # ejective lateral affricates / fricatives
    "tɬʼ","cʎ̝̊ʼ","kʟ̝̊ʼ","ɬʼ",
    # clicks (incl. Unicode 15 𝼊 retroflex click, ʞ velar click)
    "ʘ","ǀ","ǃ","𝼊","ǂ","ʞ","ǁ",
    "ʘ̬","ǀ̬","ǃ̬","𝼊̬","ǂ̬","ʞ̬","ǁ̬",
    "ʘ̃","ǀ̃","ǃ̃","𝼊̃","ǂ̃","ʞ̃","ǁ̃",
    # implosives
    "ɓ","ɗ","ᶑ","ʄ","ɠ","ʛ",
    "ɓ̥","ɗ̥","ᶑ̊","ʄ̊","ɠ̊","ʛ̥",
]
for ipa in CHART:
    r = run(EXE, ["-L", ipa])
    if r.returncode != 0:
        check(f"chart {ipa} parses", False,
              r.stderr.strip().splitlines()[-1][:80])
        continue
    rb = rebuilt_of(ipa)
    if not rb or not all(vector_of(seg) is not None for seg in rb):
        check(f"chart {ipa} rebuild re-parses", False,
              f"rebuilt {rb!r} has an unparseable segment")
        continue
    warned = False
    for l in r.stderr.splitlines():
        if "warning" in l and "redundant" not in l and "did you mean" not in l:
            check(f"chart {ipa} no unexpected warning", False, l.strip()[:80])
            warned = True
            break
    if not warned:
        check(f"chart {ipa} parses & rebuilds", True, "")

# ------------------------------------------------------------------
print(f"\n{_common.total - _common.fails}/{_common.total} checks passed")
sys.exit(1 if _common.fails else 0)
