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
import subprocess
import sys
from pathlib import Path

EXE = sys.argv[1] if len(sys.argv) > 1 else r"D:\2-OGP\IPA2Vector\ipa2vec.exe"
VEC2IPA = sys.argv[2] if len(sys.argv) > 2 else r"D:\2-OGP\IPA2Vector\vec2ipa.exe"
VECTORS_MD = r"D:\2-OGP\IPA2Vector\IPA_VECTORS.md"

fails = 0
total = 0

def run(exe, args):
    return subprocess.run([exe] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

def vector_of(ipa):
    r = run(EXE, [ipa])
    if r.returncode != 0:
        return None
    return [float(x) for x in r.stdout.split("(")[1].split(")")[0].split(",")]

def nearest_base(ipa):
    v = vector_of(ipa)
    if v is None:
        return "ERR"
    vec = ", ".join(f"{x:.4f}" for x in v)
    r = run(VEC2IPA, ["-n", vec])
    if r.returncode != 0:
        return "ERR"
    return r.stdout.split("/")[1]

def check(name, cond, detail=""):
    global fails, total
    total += 1
    if not cond:
        fails += 1
        print(f"FAIL: {name}  {detail}")

# ------------------------------------------------------------------
# 1. vowel-like bases × {nasalised, long, both} must anchor to a vowel
# ------------------------------------------------------------------
pat = re.compile(r'^`/([^/`]*)/`(?: \([^)]*\))?: `\((.*)\)`$')
VOWELS = []
for line in open(VECTORS_MD, encoding="utf-8"):
    m = pat.match(line.strip())
    if m:
        vals = [float(x) for x in m.group(2).split(",")]
        if vals[8] >= 0.5 and vals[14] >= 0.4 and vals[12] >= 1.0:
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
      run(VEC2IPA, ["-r", ", ".join(f"{x:.4f}" for x in vector_of("ãː"))]
          ).stdout.split("->  /")[-1].rstrip("/\n").strip() in
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

CREAK = [("p̰", "pʼ"), ("t̰", "tʼ"), ("k̰", "kʼ"), ("q̰", "qʼ")]
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

SYL = [("m̩", "m"), ("n̩", "n"), ("ŋ̍", "ŋ"), ("l̩", "l"), ("r̩", "r")]
for ipa, want in SYL:
    check(f"syllabic {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

SECONDARY = [
    ("tʷ", "t"), ("kʷ", "k"), ("lʷ", "l"), ("sʷ", "ʃ"),  # rounding → rounded sibilant
    ("lˠ", "lˠ"), ("tʲ", "t"), ("sʲ", "s"), ("kʲ", "c"),
    ("tˤ", "t"), ("kˤ", "k"),
]
for ipa, want in SECONDARY:
    check(f"secondary {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")

# ------------------------------------------------------------------
# 3. documented near-neighbours (semantically correct, kept on purpose)
# ------------------------------------------------------------------
DOC = [
    # voiced aspirated stops have no base; the nearest plain stop wins
    ("bʱ", "p"), ("dʱ", "t"), ("ɡʱ", "k"),
]
for ipa, want in DOC:
    check(f"documented {ipa}", nearest_base(ipa) == want,
          f"-> {nearest_base(ipa)}")
# ʩ (velopharyngeal fricative) is the only voiceless nasal fricative
# base; x̃ is velar voiceless nasalised — a place-exact match.  ʩ is in
# the extipa charset class: default std falls back to /x/ (the rebuild
# still spells x̃), --charset extipa reaches the ʩ target.
check("documented x̃ -> /x/ under default std charset",
      nearest_base("x̃") == "x", f"-> {nearest_base('x̃')}")
check("documented x̃ -> /ʩ/ with --charset extipa",
      run(VEC2IPA, ["--charset", "extipa", "-n",
                    ", ".join(f"{x:.4f}" for x in vector_of("x̃"))]
          ).stdout.split("  ")[0] == "/ʩ/", "")

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
    vec = ", ".join(f"{x:.4f}" for x in v1)
    r = run(VEC2IPA, [vec])
    rebuilt = r.stdout.split("->  /")[-1].rstrip("/\n").strip()
    v2 = vector_of(rebuilt)
    if v2 is None:
        check(f"rebuild {ipa}", False, f"rebuilt {rebuilt} unparseable")
        continue
    dv = max(abs(a - b) for a, b in zip(v1, v2))
    check(f"rebuild {ipa} -> {rebuilt}", dv <= 0.02, f"max|dv|={dv:.4f}")

# ------------------------------------------------------------------
# 6. tone letters / pitch marks survive the forward-reverse rebuild
# ------------------------------------------------------------------
TONE_CASES = [
    ("ma˥",         "a˥"),
    ("ma˥˩",        "a˥˩"),
    ("ma˧˥",        "a˧˥"),
    ("ma˨˩˦",       "a˨˩˦"),
    ("ma˩˨꜓꜒",     "a˩˨꜓꜒"),
    ("maꜛ",         "aꜛ"),
    ("maꜜ",         "aꜜ"),
    ("ma↗",         "a↗"),
    ("ma↘",         "a↘"),
    ("ma꜅",         "a꜅"),
    ("ma꜆˩",        "a˩꜆"),
    ("ma˧ꜛ↗꜂",      "a˧ꜛ↗꜂"),
    ("ma˦˩˩",       "a˦˩˩"),
]
def rebuilt_of(s):
    r = run(EXE, ["-i", s])
    if r.returncode != 0:
        return None
    out = []
    for l in r.stdout.splitlines():
        if "rebuilt[" in l:
            out.append(l.split(": /")[1].rstrip("/"))
    return out

for inp, want in TONE_CASES:
    rb = rebuilt_of(inp)
    got = rb[1] if rb and len(rb) == 2 else rb
    check(f"tone rebuild {inp}", got == want, f"got {got}")

# ------------------------------------------------------------------
# 7. reverse uses standard IPA only (no ȶ ȡ ȵ ȴ ᴇ)
# ------------------------------------------------------------------
# ᴇ (lowered e, small-cap display letter) -> standard spelling e̞
E_VEC = "0.0, 0.0, 0.55, 0.1, 1.0, -0.2, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.7, 1.0"
check("ᴇ vector nearest is e", nearest_base("e̞") != "ERR" and
      run(VEC2IPA, ["-n", E_VEC]).stdout.split("  ")[0] == "/e/",
      run(VEC2IPA, ["-n", E_VEC]).stdout.splitlines()[0][:40])
check("ᴇ vector rebuilds as e̞",
      run(VEC2IPA, [E_VEC]).stdout.split("->  /")[-1].rstrip("/\n") == "e̞",
      run(VEC2IPA, [E_VEC]).stdout.splitlines()[0][:60])
# Sinologist curl letters are never reverse targets by default; their
# standard spelling is t̠ʲ/d̠ʲ/n̠ʲ/l̠ʲ, so the fallback must be t/d/n/l
for curl, fallback in (("ȶ", "/t/"), ("ȡ", "/d/"), ("ȵ", "/n/"), ("ȴ", "/l/")):
    v = vector_of(curl)
    vec = ", ".join(f"{x:.4f}" for x in v)
    nb = run(VEC2IPA, ["-n", vec]).stdout.split("  ")[0]
    check(f"{curl} vector not rebuilt as {curl} by default", nb != f"/{curl}/", nb)
    check(f"{curl} vector falls back to {fallback}", nb == fallback, nb)
# --charset is repeatable and accumulates; any combination is allowed
check("--charset sinologist allows ȶ",
      run(VEC2IPA, ["--charset", "sinologist", "-n",
                    ", ".join(f"{x:.4f}" for x in vector_of("ȶ"))]
          ).stdout.split("  ")[0] == "/ȶ/", "")
check("--charset sinologist allows ᴇ (small-cap is Sinologist)",
      run(VEC2IPA, ["--charset", "sinologist", "-n", E_VEC]
          ).stdout.split("  ")[0] == "/ᴇ/", "")
check("standard rhotacised ɝ kept under any charset",
      run(VEC2IPA, ["-n", ", ".join(f"{x:.4f}" for x in vector_of("ɝ"))]
          ).stdout.split("  ")[0] == "/ɝ/"
      and run(VEC2IPA, ["--charset", "std", "-n",
                        ", ".join(f"{x:.4f}" for x in vector_of("ɝ"))]
              ).stdout.split("  ")[0] == "/ɝ/", "")
check("extIPA ʬ gated by default (std), enabled by --charset extipa",
      run(VEC2IPA, ["-n", ", ".join(f"{x:.4f}" for x in vector_of("ʬ"))]
          ).stdout.split("  ")[0] != "/ʬ/"
      and run(VEC2IPA, ["--charset", "extipa", "-n",
                        ", ".join(f"{x:.4f}" for x in vector_of("ʬ"))]
              ).stdout.split("  ")[0] == "/ʬ/", "")
check("--charset std + sinologist: combo without extIPA",
      run(VEC2IPA, ["--charset", "std", "--charset", "sinologist", "-n", E_VEC]
          ).stdout.split("  ")[0] == "/ᴇ/"
      and run(VEC2IPA, ["--charset", "std", "--charset", "sinologist", "-n",
                        ", ".join(f"{x:.4f}" for x in vector_of("ʬ"))]
              ).stdout.split("  ")[0] != "/ʬ/", "")
check("--charset bad value rejected",
      run(VEC2IPA, ["--charset", "bogus", E_VEC]).returncode == 1, "")

# ------------------------------------------------------------------
# 8. every standard base is its own nearest base (place is primary)
# ------------------------------------------------------------------
# Regression guard for the p̪/ɱ case: the labiodental stop/nasal were
# base rows whose vectors coincided with p/m (lips_closed is 1.0 for
# both bilabial and labiodental closures), so they fell back to /p//m/.
# They are now described by the dental dimension (tt_pos 1.0, same as
# t̪ θ ð), and the derived spellings b̪ m̪ agree with the base rows.
VECTORS_H = Path(__file__).resolve().parents[1] / "src" / "vectors.h"
for line in VECTORS_H.read_text(encoding="utf-8").splitlines():
    m = re.search(r'\{ "([^"]+)", \{', line)
    if not m:
        continue
    ipa = m.group(1)
    v = vector_of(ipa)
    if v is None:
        check(f"base {ipa} parses", False, "parse failed")
        continue
    vec = ", ".join(f"{x:.4f}" for x in v)
    got = run(VEC2IPA, ["-n", vec]).stdout.split("  ")[0]
    check(f"base {ipa} is its own nearest base", got == f"/{ipa}/", got)
for derived, base in (("p̪", "p\u032a"), ("m̪", "ɱ")):
    v1, v2 = vector_of(derived), vector_of(base)
    dv = max(abs(a - b) for a, b in zip(v1, v2)) if v1 and v2 else None
    check(f"{derived} agrees with {'base row' if base == '\u0271' else 'p+\u032a'}",
          dv is not None and dv <= 0.02, f"max|dv|={dv}")

# ------------------------------------------------------------------
# 5. approximate rebuilds (semantically right, small residual by design)
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
    vec = ", ".join(f"{x:.4f}" for x in v1)
    r = run(VEC2IPA, [vec])
    rebuilt = r.stdout.split("->  /")[-1].rstrip("/\n").strip()
    v2 = vector_of(rebuilt)
    dv = max(abs(a - b) for a, b in zip(v1, v2))
    check(f"approx {ipa} -> {rebuilt}", dv <= tol, f"max|dv|={dv:.4f}")

# ------------------------------------------------------------------
print(f"\n{total - fails}/{total} checks passed")
sys.exit(1 if fails else 0)
