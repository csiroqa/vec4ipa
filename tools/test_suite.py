#!/usr/bin/env python3
"""ipa2vec stress-test suite.

Run:  python3 tools/test_suite.py [path-to-ipa2vec]

Covers: extIPA/clinical strings, tone system (5-level + Chinese classes +
upstep/downstep + global contours), implicit affricates, regional modules
(Americanist/Sinologist/Indologist/Polish/Teuthonista/Koreanologist/
Japanologist/Africanist/OED), uppercase (listed only), inference notes,
deprecated-symbol warnings, and round-trip fidelity of the base table.
"""

import json as _json
import os
import re
import sys
import tempfile
from pathlib import Path

import _common
from _common import check, check_cond, fmt_vec, parse_rebuilt, parse_vector, run

ROOT = Path(__file__).resolve().parents[1]
EXE = sys.argv[1] if len(sys.argv) > 1 else ROOT / ("ipa2vec" + _common.BIN_SUFFIX)
VEC2IPA = sys.argv[2] if len(sys.argv) > 2 else ROOT / ("vec2ipa" + _common.BIN_SUFFIX)
VEC4IPA = sys.argv[3] if len(sys.argv) > 3 else ROOT / ("vec4ipa" + _common.BIN_SUFFIX)
_common.EXE = EXE

# ------------------------------------------------------------------
# 1. The big clinical/extIPA stress string (from the spec discussion)
# ------------------------------------------------------------------
BIG = ("\u02c0\u025d\u0306\u033ak\u203f\u02c8o\u033d\u02d0\u1db7\u02cc"
       "re\u0334\u032apst\u02e2.\ua71ca\u0303\u033c\u02d1d\ua705"
       "\u02e9\u02e6\u02e7\ua715\ua716\ua712\u2197|ba\u031c\u02d4"
       "z\u031f\u02b1.ts\u1d4an\u2197\u2016z\u0325\u0131\u0324\u0303"
       "\u02e4t\u032cu\u0330\u0308\u02d0d\u1da3.r\u0325\u02b0l\u0329"
       "p\u02e1.hr\u032f\u02b1d\u207f|\u03b2\u02b7\u1d7f\u033b\u0291"
       "\u0329\u02b2\u02d0n\u0320\u2198\u2016\u00f8\u0319\u02de\u02d5"
       "d\u02e0\u031a\u2016\u028e\u032fe\u030b\u0318t\u032c\u02de"
       "\u0329\u02e4\u014b\u030a.\u027a\u0322\u00e9\u0319d\u026e."
       "\u0239\u0113\u0339\u029f\u0288\u02bc.\u0238\u00e8\u031c."
       "\u0236\u028e\u031d\u0325\u02bc\u0205\u031e\u0221.k\u029f"
       "\u031d\u030a\u02bc\u011b\u031d\u02a1\u032f.t\u026c\u02bc"
       "\u00ea\u0330\u0299.\u0298e\u1dc4\u0324\u0257.\u03c7\u02bc"
       "e\u1dc5\u0325\u01c3.\u029b e\u1dc7\u01c2.\u0267e\u1dc6"
       "t\u0361s.\u0291e\u1dc8\u0261\u0361b.\u014b\u0361m\u028d"
       "\u0329\u0265e\u1dc9\u026b")
check("BIG clinical/extIPA string parses", [BIG], expect_rc=0)

# ------------------------------------------------------------------
# 2. Tone system — three extra vectors:
#    vec1 single tone (¹²³⁴⁵ / ˩˨˧˦˥), vec2 sandhi (꜖꜕꜔꜓꜒),
#    vec3 3-D (upstep, global, class), default (0,0,0)
#    empty vectors print as '?', trailing '?' dropped
# ------------------------------------------------------------------
check("tone 2-letter", ["ma\u02e9\u02e8"], expect_tone="tone=(1,2)")
check("tone 3-letter", ["ma\u02e5\u02e7\u02e9"], expect_tone="tone=(5,3,1)")
check("tone 4-letter single+sandhi", ["ma\u02e9\u02e8\ua713\ua712"],
      expect_tone="tone=(1,2)?(4,5)")
check("tone 6-letter", ["t\u02e5\u02e6\u02e7\u02e8\u02e9\u02e9"],
      expect_tone="tone=(5,4,3)?(2,1,1)")
check("tone digits", ["ma\u00b9\u00b2\u2074"], expect_tone="tone=(1,2,4)")
check("tone sandhi letters", ["ma\ua716\ua715"], expect_tone="tone=?(1,2)")
check("upstep", ["ma\ua71b"], expect_tone="tone=??(-1,0,0)")
check("downstep", ["ma\ua71c"], expect_tone="tone=??(1,0,0)")
check("global rise", ["ma\u2197"], expect_tone="tone=??(0,1,0)")
check("global fall", ["ma\u2198"], expect_tone="tone=??(0,-1,0)")
check("tone class 6", ["ma\ua705"], expect_tone="tone=??(0,0,-3)")
check("tone+class combined", ["ma\u02e9\u02e8\ua705"],
      expect_tone="tone=(1,2)??(0,0,-3)")
check("mixed digit+letter tone warns", ["ma\u00b9\u02e9"], expect_rc=0,
      expect_warn="warning: mixing superscript digits")
check("standalone global rise", ["\u2197"], expect_tone="tone=??(0,1,0)")
check("standalone global fall", ["\u2198"], expect_tone="tone=??(0,-1,0)")
check("standalone upstep", ["\ua71b"], expect_tone="tone=??(-1,0,0)")
check("standalone downstep", ["\ua71c"], expect_tone="tone=??(1,0,0)")
check("standalone tone class", ["\ua705"], expect_tone="tone=??(0,0,-3)")
check("tone after modifier binds to base", ["a\u032f\u02e8"],
      expect_tone="tone=(2,2)")
check("tone after rhoticised vowel", ["\u025d\u032f\u02e8\u02e9\u02e6"],
      expect_tone="tone=(2,1,4)")

# ------------------------------------------------------------------
# 3. Transcription narrowness (--width)
# ------------------------------------------------------------------
def width_vec(s):
    r = run(EXE, [s])
    m = re.search(r"\(([^)]+)\)", r.stdout)
    return m.group(1) if m else "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"

wv = width_vec("t\u032c\u02de\u0329\u02e4")
r0 = run(VEC2IPA, ["--width", "0", wv])
r4 = run(VEC2IPA, ["--width", "4", wv])
c0 = (r0.stdout or r0.stderr).count("+")
c4 = (r4.stdout or r4.stderr).count("+")
check_cond("--width 4 mods", c4 >= c0, f"mods={c4} < --width 0 mods={c0}")
check("nasalised nasal warns", ["n\u0303"],
      expect_warn="nasalising the nasal n is redundant")
check("nasalised vowel silent", ["a\u0303"], expect_rc=0)
check("vowel nasal-release warns", ["a\u207f"],
      expect_warn="vowel a nasalises with ◌̃")
check("oral consonant tilde warns", ["t\u0303"],
      expect_warn="oral consonant t nasalises with ◌ⁿ")

# ------------------------------------------------------------------
# 4. Implicit affricates (no tie)
# ------------------------------------------------------------------
for pair in ["ts", "dz", "t\u0283", "d\u0292", "t\u0255", "d\u0291",
             "\u0288\u0282", "\u0256\u0290", "t\u026c", "d\u026e",
             "c\u00e7", "\u025f\u029d", "p\u032af",
             "t\u0282", "d\u0290", "kx", "q\u03c7", "t\u03b8", "tf",
             "\u0236\u0255", "\u0221\u0291"]:
    check(f"implicit affricate {pair!r}", [pair], expect_segs=1)
check("non-affricate pair stays 2 segs", ["gp"], expect_segs=2)

# ------------------------------------------------------------------
# 5. Regional modules
# ------------------------------------------------------------------
for s, name in [("\u0161", "americanist \u0161"), ("\u010d", "americanist \u010d"),
                ("\u01f0", "americanist \u01f0"), ("\u1e8b", "americanist \u1e8b"),
                ("\u0142", "americanist \u0142"), ("\u03bb", "americanist \u03bb"),
                ("\u027f", "sinologist \u027f"), ("\u0285", "sinologist \u0285"),
                ("\u02ae", "sinologist \u02ae"), ("\u02af", "sinologist \u02af"),
                ("\u1d00", "sinologist \u1d00"),
                ("\u1e0d", "indologist \u1e0d"), ("\u1e6d", "indologist \u1e6d"),
                ("\u1e5b", "indologist \u1e5b"), ("\u1e63", "indologist \u1e63"),
                ("\u015b", "indologist \u015b"), ("\u00f1", "indologist \u00f1"),
                ("\u1e0f", "semiticist \u1e0f"), ("\u1e6f", "semiticist \u1e6f"),
                ("\u0121", "semiticist \u0121"), ("\u1e3b", "dravidian \u1e3b"),
                ("\u1e5f", "dravidian \u1e5f"), ("\u1e41", "dravidian \u1e41"),
                ("\u017a", "polish \u017a"), ("\u0107", "polish \u0107"),
                ("\u017c", "polish \u017c"),
                ("\u0180", "teuthonista \u0180"), ("\u0111", "teuthonista \u0111"),
                ("\u01e5", "teuthonista \u01e5"), ("\u01e9", "teuthonista \u01e9"),
                ("\u021f", "teuthonista \u021f"), ("\u01f5", "teuthonista \u01f5"),
                ("\u018d", "withdrawn \u018d"), ("\u01bb", "withdrawn \u01bb"),
                ("\u01be", "withdrawn \u01be"), ("\u019e", "withdrawn \u019e"),
                ("\u0239", "africanist \u0239"), ("\u0238", "africanist \u0238"),
                ("\u1d7b", "oed \u1d7b"), ("\u1d7f", "oed \u1d7f"),
                ("N", "japanologist N"), ("Q", "japanologist Q (error)"),
                ("G", "uppercase G"), ("R", "uppercase R"), ("\u0152", "uppercase \u0152")]:
    want_rc = 0
    if s == "Q":
        want_rc = 1
    check(f"regional {name}", [s], expect_rc=want_rc)

# ------------------------------------------------------------------
# 6. School-of-linguistics modules: --<name> enables without warning;
#    priority follows command-line order; warning lists all schools
# ------------------------------------------------------------------
check("school default warns", ["\u0161"],
      expect_warn="warning: using symbol '\u0161' from americanist")
check("school --americanist silent", ["--americanist", "\u0161"], expect_rc=0)
check("school warn lists all schools", ["\u0142"],
      expect_warn="from americanist, polish")
check("school flag order polish first", ["--polish", "--americanist", "\u0142"],
      expect_note="'ł' -> w")
check("school flag order americanist first", ["--americanist", "--polish", "\u0142"],
      expect_note="'ł' -> ɬ")
check("school polish č", ["--polish", "\u010d"],
      expect_note="'č' -> t͡ʂ")
check("sinologist ȶ warns by default", ["\u0236"],
      expect_warn="sinologist symbol '\u0236'")
check("sinologist ȶ silent with flag", ["--sinologist", "\u0236"], expect_rc=0)

# ------------------------------------------------------------------
# 7. No extrapolated uppercase
# ------------------------------------------------------------------
for s in ["B", "I", "L", "A", "E", "U", "W", "V"]:
    check(f"no-extrapolate uppercase {s}", [s], expect_rc=1)

# ------------------------------------------------------------------
# 8. Diacritic semantics (formal readings)
# ------------------------------------------------------------------
check("linguolabial t\u033c", ["t\u033c"], expect_rc=0)
check("laminal t\u033b", ["t\u033b"], expect_rc=0)
check("ATR e\u0318", ["e\u0318"], expect_rc=0)
check("RTR e\u0319", ["e\u0319"], expect_rc=0)
check("fortis t\u0348", ["t\u0348"], expect_rc=0)
check("lenis t\u0349", ["t\u0349"], expect_rc=0)
check("extIPA alveolar t\u0347", ["t\u0347"], expect_rc=0)
check("extIPA whistled s\u034e", ["s\u034e"], expect_rc=0)
check("extIPA labiodental f\u1db9", ["f\u1db9"], expect_rc=0)
check("extIPA sliding t\u0362", ["t\u0362"], expect_rc=0)

# ------------------------------------------------------------------
# 9. Inferences reported
# ------------------------------------------------------------------
check("infer tie", ["ts"], expect_note="inferred tie")
check("infer synth affricate", ["t\u026c"], expect_note="synthesized tie")
check("infer ascii g", ["g"], expect_note="ASCII 'g'")
check("infer apostrophe", ["k'"], expect_note="unreleased")
check("infer prime", ["k\u2032"], expect_note="palatalization")
check("infer weak-asp quote", ["b\u2018"], expect_note="weak aspiration")
check("infer alias note", ["\u0161"], expect_note="'")
check("note superseded click", ["\u0287"], expect_note="superseded")
check("warn dotless-i obsolete", ["\u0131"], expect_warn="warning")

# ------------------------------------------------------------------
# 9b. Invalid-combination warnings (input tolerance: parse continues;
#     all issues of a segment are merged into ONE warning line)
# ------------------------------------------------------------------
check("warn syllabic on vowel", ["i\u0329"], expect_warn="syllabic on a vowel")
check("warn non-syllabic on consonant", ["n\u032f"], expect_warn="non-syllabic on a consonant")
check("warn vl ring on voiceless", ["p\u0325"], expect_warn="voiceless ring on an already-voiceless letter")
check("warn vd mark on voiced", ["b\u032c"], expect_warn="voiced mark on an already-voiced letter")
check("warn vl+vd pair", ["i\u0325\u032c"], expect_warn="voiceless and voiced")
check("warn long+short pair", ["i\u02d0\u0306"], expect_warn="long and extra-short")
check("warn breathy+creaky pair", ["i\u0324\u0330"], expect_warn="breathy and creaky")
check("warn long+half pair", ["i\u02d0\u02d1"], expect_warn="long and half-long")
check("warn asp+unrel pair", ["i\u02b0\u031a"], expect_warn="aspirated and unreleased")
check("warn asp+breathy-asp pair", ["p\u02b0\u02b1"], expect_warn="aspirated and breathy-voiced")
check("warn vel+phar pair", ["l\u02e0\u02e4"], expect_warn="velarized and pharyngealized")
check("warn apical+laminal pair", ["t\u033a\u033b"], expect_warn="apical and laminal")
check("warn dental+retroflex pair", ["t\u032a\u0322"], expect_warn="dental and retroflex")
check("warn base dental+retroflex", ["\u0288\u032a"], expect_warn="retroflex and dental")
check("warn repeated long", ["i\u02d0\u02d0"], expect_warn="repeated long mark")
check("warn repeated syllabic", ["n\u0329\u0329"], expect_warn="repeated syllabic mark")
check("warn repeated rhotic", ["\u0259\u02de\u02b3"], expect_warn="repeated rhotic mark")
check("warn already retroflex", ["\u0288\u0322"], expect_warn="retroflex mark on an already-retroflex letter")
check("warn already dental", ["t\u032a\u032a"], expect_warn="dental mark on an already-dental letter")
check("warn already velar", ["k\u02e0"], expect_warn="velarized mark on an already-velar letter")
check("warn already palatal", ["\u0272\u02b2"], expect_warn="palatalised mark on an already-palatal letter")
check("warn already rhotic", ["\u025a\u02de"], expect_warn="rhotacisation on an already-rhotic letter")
check("warn merged issues one line", ["i\u0329\u032f\u0325\u032c"],
      expect_warn="4 invalid combinations on i")
check("syllabic consonant ok", ["l\u0329"], expect_rc=0)
check("voiceless sonorant ok", ["n\u0325"], expect_rc=0)
check("devoiced voiced ok", ["b\u0325"], expect_rc=0)
check("nasal vowel no warning", ["\u0129"], expect_rc=0)
check("linguolabial derivation ok", ["\u03b8\u033c"], expect_rc=0)
check("dental derivation ok", ["t\u032a"], expect_rc=0)
check("retracted derivation ok", ["t\u0320"], expect_rc=0)
check("aspirated ok", ["t\u02b0"], expect_rc=0)
check("velarized ok", ["l\u02e0"], expect_rc=0)
check("apical dental ok", ["t\u032a\u033a"], expect_rc=0)
check("velarised palatal ok", ["\u0272\u02e0"], expect_rc=0)
check("pharyngealised velar ok", ["k\u02e4"], expect_rc=0)
check("palatalised alveolar ok", ["t\u02b2"], expect_rc=0)
check("rhotacised schwa ok", ["\u0259\u02de"], expect_rc=0)
check("breathy-aspirated ok", ["p\u02b1"], expect_rc=0)

# ------------------------------------------------------------------
# 10. Base-table round-trip fidelity (forward -> -r rebuild -> forward)
# ------------------------------------------------------------------
out = run(VEC4IPA, ["-t"]).stdout
# reverse search (vec2ipa) covers SEG_TABLE (133) only; extIPA EXTRA_BASE
# entries are near-equivalent additions, so test the 133 main entries.
segments = []
for l in out.splitlines():
    if l.startswith("# extIPA"):
        break
    if not l or l.startswith("#"):
        continue
    parts = l.split("\t")
    if len(parts) >= 3:
        segments.append((parts[0], [float(x) for x in parts[2].split()]))
rt_fail = 0
for ipa, v in segments:
    vec = fmt_vec(v)
    r1 = run(VEC2IPA, [vec])
    if r1.returncode != 0:
        rt_fail += 1
        continue
    rebuilt = parse_rebuilt(r1.stdout)
    r2 = run(EXE, [rebuilt])
    if r2.returncode != 0:
        rt_fail += 1
        continue
    l = r2.stdout.strip().splitlines()
    if not l:
        rt_fail += 1
        continue
    body = parse_vector(l[0])
    fv = [float(x) for x in body.split(",")]
    if len(v) != len(fv):
        rt_fail += 1
        continue
    if max(abs(a - b) for a, b in zip(v, fv)) > _common.TOL_REBUILD:
        rt_fail += 1
check_cond("round-trip", rt_fail == 0,
           f"{rt_fail}/{len(segments)} segments drifted")
if rt_fail == 0:
    print(f"round-trip: {len(segments)}/{len(segments)} base segments OK")

# ------------------------------------------------------------------
# 11. Advanced combos (multi-module stacking, stress robustness)
# ------------------------------------------------------------------
check("regional+diacritic stack: ḏʷ (indologist + labial)",
      ["\u1e0f\u02b7"], expect_rc=0)
check("japanese N + voiceless", ["N\u0325"], expect_rc=0)
check("teuthonista + palatalised", ["\u0111\u02b2"], expect_rc=0)
check("implicit affricate + aspiration", ["ts\u02b0"], expect_rc=0)
check("implicit affricate + ejective", ["ts\u02bc"], expect_rc=0)
check("synthesized affricate + mods", ["t\u026c\u02b0"], expect_rc=0)
check("precomposed + tone stack", ["\u011b\u02e5\u02e6"], expect_rc=0)
check("click + voiced + nasal", ["\u0298\u032c"], expect_rc=0)
check("click + nasal release", ["\u1d51\u01c3"], expect_rc=0)
check("ejective chain", ["k\u02bc\u02b0"], expect_rc=0)
check("null initial between", ["a\u2205b"], expect_segs=2)
check("fortis+aspirated", ["t\u0348\u02b0"], expect_rc=0)
check("lenis+breathy", ["t\u0349\u0324"], expect_rc=0)
check("whistled sibilant", ["s\u034e\u02b7"], expect_rc=0)
check("double diacritic order: asp then creaky", ["t\u02b0\u0330"],
      expect_rc=0)
check("creaky then asp (order matters)", ["t\u0330\u02b0"], expect_rc=0)
check("glottal onset on vowel", ["\u02c0a"], expect_rc=0)
check("schwa release", ["t\u1d4a"], expect_rc=0)
check("lateral release", ["t\u02e1"], expect_rc=0)
check("nasal release", ["t\u207f"], expect_rc=0)
for _s in ["t\u02b3", "t\u1d49", "a\u1d42"]:
    check(f"superscript letter {_s!r}", [_s], expect_rc=0)
check("empty input", [""], expect_rc=0, expect_segs=0)
check("unknown symbol error", ["\u00e9\u2603"], expect_rc=1)
check("modifier-only error", ["\u02e5"], expect_rc=1)

# ------------------------------------------------------------------
# 12. --metric FILE: runtime metric override (default = compiled-in)
# ------------------------------------------------------------------
metric_default = _json.load(open(ROOT / "metric.json", encoding="utf-8"))

alt = dict(metric_default)
alt["weights"] = [1.0] * 16
alt["lambda"] = 0.0
full = dict(metric_default)
full["metric"] = [0.0] * 256
for i in range(16):
    full["metric"][i * 16 + i] = 2.0

_tmpdir = tempfile.mkdtemp(prefix="ipa2vec_test_")
_alt = os.path.join(_tmpdir, "alt.json")
_full = os.path.join(_tmpdir, "full.json")
_bad = os.path.join(_tmpdir, "bad.json")
with open(_alt, "w", encoding="utf-8") as f: _json.dump(alt, f)
with open(_full, "w", encoding="utf-8") as f: _json.dump(full, f)
with open(_bad, "w", encoding="utf-8") as f: f.write('{"weights": [1.0, 2.0}')

d_default = run(VEC2IPA, ["-d", "p", "t"]).stdout.strip()
d_alt = run(VEC2IPA, ["--metric", _alt, "-d", "p", "t"]).stdout.strip()
d_full = run(VEC2IPA, ["--metric", _full, "-d", "p", "t"]).stdout.strip()

check("--metric equal file matches default", ["--metric", str(ROOT / "metric.json"), "ma"], expect_rc=0)
check_cond("--metric uniform weights", d_default != d_alt
           and abs(float(d_alt) - 1.3285) <= 1e-3,   # plain Euclidean p-t distance
           f"gave {d_alt}, want 1.3285 (default: {d_default})")
check_cond("--metric full matrix", d_default != d_full
           and abs(float(d_full) - float(d_alt) * (2 ** 0.5)) <= 1e-3,
           f"gave {d_full}, want {float(d_alt) * 2 ** 0.5:.4f} (default: {d_default})")
# matrix = 2I over the same uniform weights -> distance * sqrt(2)
r = run(EXE, ["--metric", _bad, "ma"])
check_cond("malformed --metric json exits 1", r.returncode == 1,
           f"rc={r.returncode}")
r = run(EXE, ["--metric", os.path.join(_tmpdir, "nope.json"), "ma"])
check_cond("missing --metric file exits 1", r.returncode == 1,
           f"rc={r.returncode}")
r = run(VEC2IPA, ["--metric"])
check_cond("--metric without value exits 1", r.returncode == 1,
           f"rc={r.returncode}")

# ------------------------------------------------------------------
# vec4ipa -q on a composite string: natural-language description
# ------------------------------------------------------------------
q = run(VEC4IPA, ["-q", "\u0279\u0320\u030a\u02d4"])   # ɹ̠̊˔
check_cond("-q composite parses (ɹ̠̊˔)", q.returncode == 0
           and "not found" not in (q.stdout + q.stderr),
           f"rc={q.returncode} {q.stdout.strip()!r}")
check_cond("-q base name", "/\u0279/ (vd.alv.apx)" in q.stdout,
           q.stdout.strip()[:120])
check_cond("-q modifier words", "voiceless, retracted, raised" in q.stdout,
           q.stdout.strip()[:120])
q = run(VEC4IPA, ["-q", "t\u02b0a"])
check_cond("-q multi-segment", q.returncode == 0
           and "[1] /a/" in q.stdout and "aspirated" in q.stdout,
           q.stdout.strip()[:120])
q = run(VEC4IPA, ["-q", "t\u026c"])                    # tɬ (synthesized tie)
check_cond("-q synthesized affricate", q.returncode == 0
           and "/\u026c/ (vl.alv.lat.frc)" in q.stdout
           and "tied" in q.stdout,
           q.stdout.strip()[:120])
q = run(VEC4IPA, ["-q", "\u1d51\u01c3"])               # ᵑǃ (preposed)
check_cond("-q preposed modifier", q.returncode == 0
           and "/\u1d51\u01c3/" in q.stdout
           and "nasalised click" in q.stdout,
           q.stdout.strip()[:120])
q = run(VEC4IPA, ["-q", "\u00e6\u0303"])               # æ̃
check_cond("-q nasalised vowel", q.returncode == 0
           and "nasalised" in q.stdout,
           q.stdout.strip()[:120])

# ------------------------------------------------------------------
# sequence alignment (-A): vowel-block trajectory distances
# ------------------------------------------------------------------
def align_d(a, b):
    r = run(VEC4IPA, ["-A", a, b])
    m = re.search(r"aligned d=([0-9.]+)", r.stdout)
    return float(m.group(1)) if m else -1.0, r

d, r = align_d("ai", "\u025b")          # ai vs ɛ
check_cond("-A /ai/~/ɛ/ pays the mora (short monophthong)",
           abs(d - 1.26) <= 0.05 and "\u025b" in r.stdout.splitlines()[1],
           f"d={d}")
d, r = align_d("ai", "\u025be")          # ai vs ɛe: sub-glide of ai
check_cond("-A /ai/~/ɛe/ ≤ /ai/~/ɛ/ (containment)",
           d < 1.26 and "a + i ~ \u025b + e" in r.stdout, f"d={d}")
d, _ = align_d("ai", "ia")              # reversal must not collapse
check_cond("-A /ai/~/ia/ > 2.5", d > 2.5, f"d={d}")
d, _ = align_d("aieu", "eou")           # vowel cluster 4 vs 3
check_cond("-A /aieu/~/eou/", 2.0 < d < 4.0, f"d={d}")
d, _ = align_d("aa", "a")               # geminate: one mora
check_cond("-A /aa/~/a/ one mora", abs(d - 1.0) <= 0.05, f"d={d}")

# curve-distance alignments: feature absorption + null-element indel
d, _ = align_d("a\u0303", "an")          # nasalised vowel ~ VN
check_cond("-A /\u00e3/~/an/ nasality = coda (absorbed)",
           abs(d - 1.16) <= 0.05, f"d={d}")
d, _ = align_d("ka\u014b", "k\u00e3")    # nasal coda = nasalisation
check_cond("-A /ka\u014b/~/k\u00e3/ coda absorbed",
           abs(d - 0.89) <= 0.05, f"d={d}")
d, _ = align_d("t\u02b0", "th")          # aspirated stop ~ C+h
check_cond("-A /t\u02b0/~/t+h/ absorbed", abs(d - 0.52) <= 0.05, f"d={d}")
d, _ = align_d("pa", "a")                # onset deletion = the consonant's
check_cond("-A /pa/~/a/ onset removal = indel(p)",
           abs(d - 6.15) <= 0.05, f"d={d}")
d, _ = align_d("na", "an")               # reversal: two vowel indels
check_cond("-A /na/~/an/ cheap vowel indels (null = neutral vowel)",
           abs(d - 3.71) <= 0.05, f"d={d}")
d, _ = align_d("ai", "ia")               # reversal must not collapse
check_cond("-A /ai/~/ia/ > 2.5 (order kept)", d > 2.5, f"d={d}")

# ------------------------------------------------------------------
# 13. options not covered elsewhere: -j/-o/-x, inventory commands,
#     meta commands, -D scheme, -P spacing, alias equivalence
# ------------------------------------------------------------------
# -j/--json: JSON output is valid JSON with the expected segment count
_j = _json.loads(run(EXE, ["-j", "t\u02b0a"]).stdout)
check_cond("--json parses", isinstance(_j, dict) and "segments" in _j)
check_cond("--json 2 segments", len(_j["segments"]) == 2,
           f'got {len(_j["segments"])}')
check_cond("--json shortcut -j identical", run(EXE, ["-j", "t"]).stdout
           == run(EXE, ["--json", "t"]).stdout)
check_cond("-j equals -L order (alias -e)", run(VEC4IPA, ["-j", "t"]).stdout
           == run(EXE, ["-j", "t"]).stdout)

# -o/--output FILE redirects stdout to the file (stderr stays terminal)
_tmp = tempfile.mkdtemp(prefix="ipa2vec_opt_")
_out = os.path.join(_tmp, "out.txt")
_r = run(EXE, ["-o", _out, "t"])
_oc = open(_out, encoding="utf-8").read()
check_cond("-o writes the vector to the file", "[0]" in _oc and
           "pulmonic" in _oc, _oc[:60])
check_cond("-o command exits 0", _r.returncode == 0)
check_cond("--output alias opens", (run(EXE, ["--output", _out, "a"]),
           open(_out, encoding="utf-8").read())[1] != "")
os.remove(_out)

# -x/--layers-out BASE exports .layer1/.layer2; alias --ir-out/-X
_base = os.path.join(_tmp, "b")
run(EXE, ["-x", _base, "-L", "t\u02b0a\u0303"])
_l1 = open(_base + ".layer1", encoding="utf-8").read()
_l2 = open(_base + ".layer2", encoding="utf-8").read()
check_cond("-x writes .layer1", "BASE\tt" in _l1 and "MOD\t\u02b0" in _l1,
           _l1[:60])
check_cond("-x writes .layer2 with the tier column",
           "BASE\tt" in _l2 and "MOD\t\u02b0\tasp\tlaryngeal" in _l2,
           _l2[:60])
check_cond("--layers-out + --ir-out aliases agree",
           run(EXE, ["--layers-out", _base, "-e", "a"]).returncode == 0
           and run(EXE, ["--ir-out", _base, "-L", "a"]).returncode == 0)

# inventory/meta commands (vec4ipa)
_v4s = run(VEC4IPA, ["-s"]).stdout
check_cond("vec4ipa -s stats", "base segments" in _v4s
           and "modifiers" in _v4s, _v4s[:60])
_v4t = run(VEC4IPA, ["-t"]).stdout
check_cond("vec4ipa -t table starts with header", _v4t.startswith("# ipa"),
           _v4t[:40])
_v4q = run(VEC4IPA, ["-q", "p"]).stdout
check_cond("vec4ipa -q query", "/p/" in _v4q, _v4q[:60])
_v4m = run(VEC4IPA, ["-m"]).stdout
check_cond("vec4ipa -m modules", "modules" in _v4m or "regional" in _v4m,
           _v4m[:60])
_v4w = run(VEC4IPA, ["-w"]).stdout
check_cond("vec4ipa -w weights has 16 rows", len(_v4w.splitlines()) >= 16,
           f'rows={len(_v4w.splitlines())}')
check_cond("--table/--stats/--weights aliases",
           run(VEC4IPA, ["--table"]).stdout == _v4t
           and run(VEC4IPA, ["--weights"]).stdout == _v4w)

# meta commands
_i = run(EXE, ["-i"]).stdout
check_cond("ipa2vec -i information", "ipa2vec" in _i
           and "16-D" in _i, _i[:60])
check_cond("--information alias", run(EXE, ["--information"]).stdout == _i)
check_cond("-R readme has heading", "# vec4ipa" in run(EXE, ["-R"]).stdout
           or "IPA/extIPA" in run(EXE, ["-R"]).stdout)
check_cond("--readme alias", run(EXE, ["--readme"]).stdout
           == run(EXE, ["-R"]).stdout)
check_cond("-v version format", "3.1.0" in run(EXE, ["-v"]).stdout,
           run(EXE, ["-v"]).stdout.strip())
check_cond("--version alias", run(EXE, ["--version"]).stdout
           == run(EXE, ["-v"]).stdout)
check_cond("-h help exits 0", run(EXE, ["-h"]).returncode == 0
           and "usage" in run(EXE, ["-h"]).stdout.lower())
check_cond("--help alias", run(EXE, ["--help"]).stdout
           == run(EXE, ["-h"]).stdout)

# -D/--scheme FILE reloads the vector table (the committed scheme)
_rs = run(VEC4IPA, ["-D", str(ROOT / "tools" / "data" / "spec_next.scheme"),
                    "-s"]).stdout
check_cond("-D scheme loads 133", "133" in _rs, _rs[:60])
check_cond("--scheme alias", run(VEC4IPA, ["--scheme",
           str(ROOT / "tools" / "data" / "spec_next.scheme"), "-s"]).stdout
           == _rs)
_bad = run(VEC4IPA, ["-D", os.path.join(_tmp, "nope.scheme"), "-s"])
check_cond("-D missing file reports error", _bad.returncode == 1 or
           "cannot open" in _bad.stderr, _bad.stderr[:60])

# -P/--spacing NAME (alias --mode): ternary shifts i̞ to 0.4667
_sp = run(EXE, ["-P", "ternary", "i\u031e"]).stdout
check_cond("-P ternary spacing", "0.4667" in _sp, _sp[60:120])
check_cond("--spacing alias", run(EXE, ["--spacing", "ternary",
           "i\u031e"]).stdout == _sp)
check_cond("--mode alias", run(EXE, ["--mode", "ternary", "i\u031e"]).stdout
           == _sp)
check_cond("-P binary default differs from ternary", "0.4667" not in
           run(EXE, ["-P", "binary", "i\u031e"]).stdout)

import shutil
shutil.rmtree(_tmp, ignore_errors=True)

# ------------------------------------------------------------------
print(f"\n{_common.total - _common.fails}/{_common.total} checks passed")
sys.exit(1 if _common.fails else 0)
