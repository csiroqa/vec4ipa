#!/usr/bin/env python3
"""Property-based validation of the -A alignment AXIOMS (cross-cutting).

test_alignment.py pins golden values case by case; this file instead
fuzzes random segment strings and asserts the framework's INVARIANTS,
so a change cannot silently break a property no test happened to cover:

  M6 symmetry    d(A,B) == d(B,A)           (edit distance + symmetric
                                             absorption must be symmetric)
  M7 identity    d(A,A) == 0
  M4 licensing   every printed absorption line must be phonetically
                 licensed: no consonant point may absorb a vowel pair
                 member (vowel gate), and the printed pair must not be
                 a consonant~vowel blend (the b~(d,o) class)
  M1 mora        [aː] ≡ [aa] (geminate = long vowel, the absorption
                 identity); the one-mora price d(Vː,V) vs d(VV,V) is
                 REPORTED so the known metric-vs-trajectory rate split
                 (5 vs 1.0) cannot drift silently

The pool is deliberately small and label-exact: absorption lines print
the nearest-base label, so vowels and consonants are classified by the
same pool used to generate the strings (no free-form IPA parsing).

Run:  python tools/validate_alignment.py [N] [exe]
"""

import random
import re
import sys
import unicodedata
from pathlib import Path

import _common
from _common import run

ROOT = Path(__file__).resolve().parents[1]

ALIGN_RE = re.compile(r"aligned d=([0-9.]+)")
ABS1_RE = re.compile(r"^\s*(\S+)\s*~\s*(\S+)\s*\+\s*(\S+)\s+d=")     # X ~ Y+Z
ABS2_RE = re.compile(r"^\s*(\S+)\s*\+\s*(\S+)\s*~\s*(\S+)\s+d=")     # X+Y ~ Z
BLOCK_RE = re.compile(r"\s\+\s")

VOWELS = {"a", "i", "u", "e", "o", "ɛ", "ɔ", "ə", "ɐ", "ɨ", "ʉ", "ɯ",
          "ã", "ɛ̃", "õ", "ũ", "ĩ", "ɛː", "aː", "iː", "uː", "oː",
          "aʷ", "aʲ", "aːi", "a˥", "a˩", "i˥", "ã˥", "əː"}

# consonant members a vowel point may absorb: nasals (nasality), glides
# and laryngeals (secondary articulation).  Obstruent members (stops,
# fricatives, ejectives, clicks, implosives, affricates) carry closure /
# frication / airstream content no vowel point can realise.
ABSORBABLE_C = {"n", "m", "ŋ", "ɲ", "w", "j", "h", "ɦ", "ɣ", "ʕ", "l", "r"}

POOL = ["a", "i", "u", "e", "o", "ɛ", "ə", "ã", "aː", "ɛː",
        "t", "k", "p", "b", "d", "s", "z", "n", "m", "ŋ",
        "tʰ", "kʷ", "kʲ", "aʷ", "w", "j", "h", "ǃ", "ɓ", "kʼ"]

fail = [0]


def align_d(exe, a, b):
    r = run(exe, ["-A", a, b])
    m = ALIGN_RE.search(r.stdout)
    return (float(m.group(1)) if m else -1.0), r


def absorption_lines(stdout):
    """(point, member1, member2, direction) for every absorption line."""
    out = []
    for ln in stdout.splitlines():
        m = ABS1_RE.match(ln)
        if m and not BLOCK_RE.search(ln):
            out.append((m.group(1), m.group(2), m.group(3), "1:2"))
            continue
        m = ABS2_RE.match(ln)
        if m and not BLOCK_RE.search(ln):
            out.append((m.group(1), m.group(2), m.group(3), "2:1"))
    return out


def is_vowel(label):
    return unicodedata.normalize("NFC", label) in VOWELS


def run_axioms(n, exe, seed=20260813, pool=POOL):
    """Assert M1/M4/M6/M7 over `n` random pairs; return #violations."""
    fail[0] = 0
    print(f"axiom fuzz over {n} pairs (exe {Path(exe).name}, seed {seed})")

    # M1: the mora identity — long vowel ≡ geminate (one price per mora)
    d_gem, _ = align_d(exe, "aː", "aa")
    d_12, _ = align_d(exe, "aː", "a")
    d_11, _ = align_d(exe, "aa", "a")
    if d_gem > 1e-6:
        fail[0] += 1
        print(f"FAIL: M1 absorption identity broken: d(aː,aa) = {d_gem}")
    print(f"M1 mora prices: d(aː,aa)={d_gem:.4f}  d(aː,a)={d_12:.4f}  "
          f"d(aa,a)={d_11:.4f}")
    if abs(d_12 - d_11) > 0.05:
        print(f"    note: M1 split — d(aː,a)={d_12:.4f} != "
              f"d(aa,a)={d_11:.4f} (should be equal: aː≡aa forces the "
              f"triangle d(aː,a) <= {d_gem + d_11:.4f})")
    else:
        print(f"    M1 consistent: one mora, one price (substitution, "
              f"block and absorption agree)")
    # M1 generalised to consonants: the geminate moves mirror the vowels
    d_mm, _ = align_d(exe, "mm", "m")
    d_mm2, _ = align_d(exe, "mː", "mm")
    d_mm3, _ = align_d(exe, "mː", "m")
    if abs(d_mm - 1.0) > 0.05 or d_mm2 > 1e-6 or abs(d_mm3 - 1.0) > 0.05:
        fail[0] += 1
        print(f"FAIL: M1 consonant geminate: d(mm,m)={d_mm:.4f} "
              f"d(mː,mm)={d_mm2:.4f} d(mː,m)={d_mm3:.4f}")
    else:
        print(f"M1 consonant geminate: d(mm,m)={d_mm:.4f}  "
              f"d(mː,mm)={d_mm2:.4f}  d(mː,m)={d_mm3:.4f} — one mora")

    # M6 symmetry + M4 licensing over random pairs
    random.seed(seed)
    sym_bad = lic_bad = 0
    for _ in range(n):
        a = "".join(random.choice(pool) for _ in range(random.randint(1, 5)))
        b = "".join(random.choice(pool) for _ in range(random.randint(1, 5)))
        dab, ra = align_d(exe, a, b)
        dba, _ = align_d(exe, b, a)
        if abs(dab - dba) > 1e-3:
            sym_bad += 1
            if sym_bad <= 5:
                print(f"  asymmetric: {a!r}~{b!r} {dab:.3f} vs {dba:.3f}")
        for pt, m1, m2, _d in absorption_lines(ra.stdout):
            gem = unicodedata.normalize("NFC", m1) == \
                unicodedata.normalize("NFC", m2)
            if not gem and not is_vowel(pt) and \
                    (is_vowel(m1) or is_vowel(m2)):
                lic_bad += 1
                if lic_bad <= 5:
                    print(f"  unlicensed absorption: {a!r}~{b!r}: "
                          f"{pt} ~ {m1}+{m2}")
            elif is_vowel(pt) and not gem:
                for m in (m1, m2):
                    if (not is_vowel(m) and
                            unicodedata.normalize("NFC", m) not in
                            ABSORBABLE_C):
                        lic_bad += 1
                        if lic_bad <= 5:
                            print(f"  unlicensed absorption: {a!r}~{b!r}: "
                                  f"{pt} ~ {m1}+{m2} (obstruent {m})")
    if sym_bad:
        fail[0] += 1
        print(f"FAIL: M6 symmetry broken on {sym_bad}/{n} pairs")
    else:
        print(f"M6 symmetry: {n}/{n} pairs symmetric")
    if lic_bad:
        fail[0] += 1
        print(f"FAIL: M4 licensing: {lic_bad} "
              f"consonant-absorbs-vowel lines")
    else:
        print(f"M4 licensing: no consonant-absorbs-vowel absorption "
              f"in {n} pairs")

    # M7 identity
    id_bad = 0
    for _ in range(60):
        a = "".join(random.choice(pool)
                    for _ in range(random.randint(1, 4)))
        d, _ = align_d(exe, a, a)
        if d > 1e-6:
            id_bad += 1
            print(f"  non-identity: {a!r} d={d:.4f}")
    if id_bad:
        fail[0] += 1
        print(f"FAIL: M7 identity broken on {id_bad}/60 strings")
    else:
        print("M7 identity: 60/60 d(A,A) = 0")

    print(f"{'PASS' if fail[0] == 0 else 'FAIL'} "
          f"({fail[0]} axiom violations over {n} fuzz pairs)")
    return fail[0]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    exe = sys.argv[2] if len(sys.argv) > 2 else \
        ROOT / f"vec4ipa{_common.BIN_SUFFIX}"
    sys.exit(1 if run_axioms(n, exe) else 0)


if __name__ == "__main__":
    main()
