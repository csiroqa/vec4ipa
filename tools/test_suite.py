#!/usr/bin/env python3
"""ipa2vec stress-test suite.

Run:  python3 tools/test_ipa2vec.py [path-to-ipa2vec]

Covers: extIPA/clinical strings, tone system (5-level + Chinese classes +
upstep/downstep + global contours), implicit affricates, regional modules
(Americanist/Sinologist/Indologist/Polish/Teuthonista/Koreanologist/
Japanologist/Africanist/OED), uppercase (listed only), inference notes,
deprecated-symbol warnings, and round-trip fidelity of the base table.
"""

import subprocess
import sys
import re

EXE = sys.argv[1] if len(sys.argv) > 1 else r"D:\2-OGP\IPA2Vector\ipa2vec.exe"
VEC2IPA = sys.argv[2] if len(sys.argv) > 2 else r"D:\2-OGP\IPA2Vector\vec2ipa.exe"
VEC4IPA = sys.argv[3] if len(sys.argv) > 3 else r"D:\2-OGP\IPA2Vector\vec4ipa.exe"

fails = 0
total = 0

def run(args):
    return subprocess.run([EXE] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

def check(name, argv, expect_rc=0, expect_segs=None, expect_tone=None,
          expect_note=None, expect_warn=None):
    global fails, total
    total += 1
    r = run(argv)
    ok = (r.returncode == expect_rc)
    if ok and expect_segs is not None:
        n = len([l for l in r.stdout.splitlines() if l.strip().startswith("[")])
        ok = (n == expect_segs)
    if ok and expect_tone is not None:
        ok = expect_tone in r.stdout
    if ok and expect_note is not None:
        ok = expect_note in r.stderr
    if ok and expect_warn is not None:
        ok = expect_warn in r.stderr
    if not ok:
        fails += 1
        print(f"FAIL: {name}")
        print(f"  rc={r.returncode} (want {expect_rc})")
        if expect_segs is not None:
            print(f"  segs={len([l for l in r.stdout.splitlines() if l.strip().startswith('[')])} (want {expect_segs})")
        print(f"  stdout: {r.stdout.strip()[:120]!r}")
        print(f"  stderr: {r.stderr.strip()[:120]!r}")
    return ok

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
check("nasalised nasal warns", ["n\u0303"],
      expect_warn="nasalising the nasal n is redundant")
check("nasalised vowel silent", ["a\u0303"], expect_rc=0)
check("vowel nasal-release warns", ["a\u207f"],
      expect_warn="vowel a nasalises with ◌̃")
check("oral consonant tilde warns", ["t\u0303"],
      expect_warn="oral consonant t nasalises with ◌ⁿ")

# ------------------------------------------------------------------
# 3. Implicit affricates (no tie)
# ------------------------------------------------------------------
for pair in ["ts", "dz", "t\u0283", "d\u0292", "t\u0255", "d\u0291",
             "\u0288\u0282", "\u0256\u0290", "t\u026c", "d\u026e",
             "c\u00e7", "\u025f\u029d", "p\u032af",
             "t\u0282", "d\u0290", "kx", "q\u03c7", "t\u03b8", "tf",
             "\u0236\u0255", "\u0221\u0291"]:
    check(f"implicit affricate {pair!r}", [pair], expect_segs=1)
check("non-affricate pair stays 2 segs", ["gp"], expect_segs=2)

# ------------------------------------------------------------------
# 4. Regional modules
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
# 5. School-of-linguistics modules: --<name> enables without warning;
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
# 6. No extrapolated uppercase
# ------------------------------------------------------------------
for s in ["B", "I", "L", "A", "E", "U", "W", "V"]:
    check(f"no-extrapolate uppercase {s}", [s], expect_rc=1)

# ------------------------------------------------------------------
# 6. Diacritic semantics (formal readings)
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
# 7. Inferences reported
# ------------------------------------------------------------------
check("infer tie", ["ts"], expect_note="inferred tie")
check("infer synth affricate", ["t\u026c"], expect_note="synthesized tie")
check("infer ascii g", ["g"], expect_note="ASCII 'g'")
check("infer apostrophe", ["k'"], expect_note="unreleased")
check("infer prime", ["k\u2032"], expect_note="palatalization")
check("infer weak-asp quote", ["b\u2018"], expect_note="weak aspiration")
check("infer alias note", ["\u0161"], expect_note="'")
check("warn deprecated", ["\u029e"], expect_warn="warning")
check("warn dotless-i obsolete", ["\u0131"], expect_warn="warning")

# ------------------------------------------------------------------
# 8. Base-table round-trip fidelity (forward -> -r rebuild -> forward)
# ------------------------------------------------------------------
out = subprocess.run([VEC4IPA, "-t"], capture_output=True, text=True,
                     encoding="utf-8", errors="replace").stdout
# reverse search (vec2ipa) covers SEG_TABLE (132) only; extIPA EXTRA_BASE
# entries are near-equivalent additions, so test the 132 main entries.
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
    vec = ", ".join(f"{x:.4f}" for x in v)
    r1 = subprocess.run([VEC2IPA, vec], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    if r1.returncode != 0:
        rt_fail += 1
        continue
    rebuilt = r1.stdout.split("->  /")[-1].rstrip("/\n")
    r2 = run([rebuilt])
    if r2.returncode != 0:
        rt_fail += 1
        continue
    l = r2.stdout.strip().splitlines()
    if not l:
        rt_fail += 1
        continue
    body = l[0].split("(")[1].split(")")[0]
    fv = [float(x) for x in body.split(",")]
    if max(abs(a - b) for a, b in zip(v, fv)) > 0.02:
        rt_fail += 1
total += 1
if rt_fail == 0:
    print(f"round-trip: {len(segments)}/{len(segments)} base segments OK")
else:
    fails += 1
    print(f"FAIL: round-trip {rt_fail}/{len(segments)} segments drifted")

# ------------------------------------------------------------------
# 9. Advanced combos (multi-module stacking, stress robustness)
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
print(f"\n{total - fails}/{total} checks passed")
sys.exit(1 if fails else 0)
