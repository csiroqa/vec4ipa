#!/usr/bin/env python3
"""Randomised fuzz test for the reverse direction.

Generates random segment strings (base + up to 4 random modifiers),
parses them with ipa2vec, rebuilds each segment with vec2ipa, and
verifies the invariant that the REBUILT spelling re-parses:

  * rc = 0 (the emitted string is always parseable);
  * same segment count (no accidental cross-boundary merges);
  * max |dv| ≤ tolerance (the emitted canonical order reproduces
    the fitted vector — this is what "order matters" guarantees).

Also reports the max|dv| distribution so metric/table changes that
degrade reconstruction show up as a drift in the tail.

Run:  python tools/fuzz_metric_space.py [n] [seed] [ipa2vec] [vec2ipa]
"""

import random
import sys
import time
from pathlib import Path

import _common
from _common import MD_LINE_RE, fmt_vec, parse_rebuilt, parse_vector, run

ROOT = Path(__file__).resolve().parents[1]
EXE = sys.argv[3] if len(sys.argv) > 3 else ROOT / f"ipa2vec{_common.BIN_SUFFIX}"
VEC2IPA = sys.argv[4] if len(sys.argv) > 4 else ROOT / f"vec2ipa{_common.BIN_SUFFIX}"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else time.time_ns()

BUCKETS = (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0)

# base segments from the table
BASES = []
for line in open(ROOT / "IPA_VECTORS.md", encoding="utf-8"):
    m = MD_LINE_RE.match(line.strip())
    if m:
        BASES.append(m.group(1))

# postposable modifiers that never change segment count
MODS = ["̃", "ː", "ˑ", "̥", "̬", "̤", "̰", "̚", "̩", "̯", "ʰ", "ʲ", "ʷ",
        "ˠ", "ˤ", "˞", "̺", "̟", "̠", "̹", "̜", "̽", "̘", "̙", "̪", "̻",
        "̝", "̞", "ʼ"]

def segs_and_vecs(ipa):
    r = run(EXE, [ipa])
    if r.returncode != 0:
        return None, r.stderr.strip()
    vecs = []
    for l in r.stdout.splitlines():
        if l.strip().startswith("["):
            vecs.append([float(x) for x in parse_vector(l).split(",")])
    return vecs, None

def rebuild(v):
    vec = fmt_vec(v)
    r = run(VEC2IPA, [vec])
    if r.returncode != 0:
        return None, r.stderr.strip()
    return parse_rebuilt(r.stdout).strip(), None

def bucket(dv):
    for b in BUCKETS:
        if dv <= b:
            return b
    return None   # > 1.0

def main():
    rng = random.Random(SEED)

    parse_errs = 0
    rebuild_errs = 0
    count_mismatch = 0
    n_segs = 0
    maxdv_all = 0.0
    bad = []          # (input, rebuilt, maxdv)
    hist = {}         # exact-bucket counts

    for it in range(N):
        base = rng.choice(BASES)
        k = rng.randint(0, 4)
        mods = rng.sample(MODS, k)
        s = base + "".join(mods)
        vecs, err = segs_and_vecs(s)
        if vecs is None:
            parse_errs += 1
            bad.append((s, f"PARSE-ERR {err[:60]}", 9.9))
            continue
        if len(vecs) != 1:
            count_mismatch += 1
            bad.append((s, f"SEG-COUNT {s}", 9.9))
        for v in vecs:
            n_segs += 1
            rebuilt, rerr = rebuild(v)
            if rebuilt is None:
                rebuild_errs += 1
                bad.append((s, f"REBUILD-ERR {rerr[:60]}", 9.9))
                continue
            vecs2, err2 = segs_and_vecs(rebuilt)
            if vecs2 is None:
                rebuild_errs += 1
                bad.append((s, f"REPARSE-ERR {err2[:60]}", 9.9))
                continue
            if len(vecs2) != 1:
                count_mismatch += 1
                bad.append((s, f"SEG-COUNT {rebuilt}", 9.9))
                continue
            if len(v) != len(vecs2[0]):
                count_mismatch += 1
                bad.append((s, f"VEC-LEN {rebuilt}", 9.9))
                continue
            dv = max(abs(a - b) for a, b in zip(v, vecs2[0]))
            maxdv_all = max(maxdv_all, dv)
            hist[bucket(dv)] = hist.get(bucket(dv), 0) + 1
            if dv > 0.2:
                bad.append((s, rebuilt, round(dv, 4)))

    def cum(up_to):
        return sum(v for k, v in hist.items() if k is not None and k <= up_to)

    frac_02 = cum(0.2) / n_segs if n_segs else 0
    frac_05 = cum(0.5) / n_segs if n_segs else 0

    print(f"seed={SEED} iters={N} segments={n_segs}")
    print(f"parse errors   : {parse_errs}")
    print(f"rebuild errors : {rebuild_errs}")
    print(f"seg mismatches : {count_mismatch}")
    print(f"max |dv| over all rebuilt segments: {maxdv_all:.4f}")
    print(f"fraction |dv| <= 0.2 : {frac_02:.3f}")
    print(f"fraction |dv| <= 0.5 : {frac_05:.3f}")
    print("|dv| histogram (exact buckets):")
    for b in BUCKETS:
        print(f"  <= {b:<5}: {hist.get(b, 0)}")
    print(f"  >  1.0  : {hist.get(None, 0)}")
    print("cases with |dv| > 0.2 or errors:")
    for item in bad[:30]:
        print("  ", item)

    # hard invariants: every random string parses, every rebuilt spelling
    # re-parses to the same segment count; reconstruction quality must stay
    # in the calibrated envelope (>=84% within 0.2, >=95% within 0.5,
    # max <= 1.0) — a metric/table change that degrades the reverse fit
    # shows up here as a drift of these numbers.
    ok = (parse_errs == 0 and rebuild_errs == 0 and count_mismatch == 0
          and frac_02 >= 0.84 and frac_05 >= 0.95 and maxdv_all <= 1.0)
    print(f"\nRESULT: {'OK' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
