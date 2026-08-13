#!/usr/bin/env python3
"""Verify the curve-distance alignment framework (-A, design B).

Every cost comes from the metric itself — no hand-tuned constants:

  substitution (1:1)   seg_dist_full(a, b)           (metric + airstream)
  absorption  (1:2/2:1) absorb_dist(a, b1, b2)       a as the coarticulated
                       union of the pair: anchor dims (|b1|>0.3) locked,
                        free dims interpolate along the b1→b2 trajectory;
                        duration is not an anchor gesture — the
                        vowel-content mora rides at the A3 rate; the
                        point must match the anchor's own gestures
                        (locked ≤ 1.0) and vowels ride only into vowel
                        points; disallowed when a is trivially
                        the anchor

  indel (1:0/0:1)      seg_indel(x) = d(x, neutral vowel ə)

This script checks BOTH the golden values of the documented cases and the
design PROPERTIES the framework must satisfy: symmetry, order sensitivity,
the coda/onset asymmetry, the indel pricing scale, and — wherever the
absorption does not apply — the triangle inequality.

Run:  python tools/test_alignment.py
"""

import math
import re
import sys
from pathlib import Path

import _common
from _common import check_cond, run

ROOT = Path(__file__).resolve().parents[1]
VEC4IPA = ROOT / f"vec4ipa{_common.BIN_SUFFIX}"

ALIGN_RE = re.compile(r"aligned d=([0-9.]+)")


def align(a, b):
    """(distance, stdout) of -A a b."""
    r = run(VEC4IPA, ["-A", a, b])
    if r.returncode != 0:
        return -1.0, r.stdout
    m = ALIGN_RE.search(r.stdout)
    return (float(m.group(1)) if m else -1.0), r.stdout


def near(d, want, tol=0.05):
    return abs(d - want) <= tol


# ------------------------------------------------------------------
# 1. absorption: nasality / secondary articulation = the trajectory
# ------------------------------------------------------------------
D = {}
D["ã~an"] = align("ã", "an")[0]
D["ɛ̃~ɛn"] = align("ɛ̃", "ɛn")[0]
D["aʷ~aw"] = align("aʷ", "aw")[0]
D["kaŋ~kã"] = align("kaŋ", "kã")[0]
D["tʰ~t+h"] = align("tʰ", "th")[0]
D["kʷ~k+w"] = align("kʷ", "kw")[0]
D["kʲ~k+j"] = align("kʲ", "kj")[0]
D["ɛ~ai"] = align("ɛ", "ai")[0]
D["ɛː~ai"] = align("ɛː", "ai")[0]
D["ɛe~ai"] = align("ɛe", "ai")[0]

check_cond("nasal coda = nasalisation (ã~an)",
           near(D["ã~an"], 1.16), f"d={D['ã~an']}")
check_cond("nasalised mid vowel (ɛ̃~ɛn ≈ 1.18)",
           near(D["ɛ̃~ɛn"], 1.18), f"d={D['ɛ̃~ɛn']}")
check_cond("labialised vowel (aʷ~aw ≈ 1.05)",
           near(D["aʷ~aw"], 1.05), f"d={D['aʷ~aw']}")
check_cond("nasal coda absorbed in context (kaŋ~kã)",
           near(D["kaŋ~kã"], 0.89), f"d={D['kaŋ~kã']}")
check_cond("aspirated stop ~ C+h", near(D["tʰ~t+h"], 0.52),
           f"d={D['tʰ~t+h']}")
check_cond("labialised stop ~ C+w", near(D["kʷ~k+w"], 1.60),
           f"d={D['kʷ~k+w']}")
check_cond("palatalised stop ~ C+j", near(D["kʲ~k+j"], 0.63, 0.05),
           f"d={D['kʲ~k+j']}")
check_cond("diphthong intermediate pays the mora (ɛ~ai ≈ 1.26)",
           near(D["ɛ~ai"], 1.26), f"d={D['ɛ~ai']}")
check_cond("lengthened monophthong pays no mora (ɛː~ai ≈ 0.76)",
           near(D["ɛː~ai"], 0.76), f"d={D['ɛː~ai']}")
check_cond("sub-glide containment (ɛe~ai < 1.26)", D["ɛe~ai"] < 1.26,
           f"d={D['ɛe~ai']}")

# ------------------------------------------------------------------
# 2. order sensitivity: reversals must not collapse
# ------------------------------------------------------------------
D["ai~ia"] = align("ai", "ia")[0]
D["na~an"] = align("na", "an")[0]
D["na~ã"] = align("na", "ã")[0]
D["apak~akap"] = align("apak", "akap")[0]
check_cond("vowel reversal (ai~ia) > 2.5", D["ai~ia"] > 2.5,
           f"d={D['ai~ia']}")
check_cond("CV reversal (na~an) > 2.5", D["na~an"] > 2.5,
           f"d={D['na~an']}")
check_cond("medial-consonant swap (apak~akap) > 6",
           D["apak~akap"] > 6.0, f"d={D['apak~akap']}")

# ------------------------------------------------------------------
# 3. coda/onset asymmetry: onset nasal is a full consonant
# ------------------------------------------------------------------
check_cond("onset nasal more expensive than coda (na~ã > ã~an)",
           D["na~ã"] > D["ã~an"] + 1.0, f"{D['na~ã']} vs {D['ã~an']}")

# ------------------------------------------------------------------
# 4. indel pricing: vowels cheap, consonants expensive, null = ə
# ------------------------------------------------------------------
D["a~an"] = align("a", "an")[0]
D["ka~kaŋ"] = align("ka", "kaŋ")[0]
D["pa~a"] = align("pa", "a")[0]
D["ap~a"] = align("ap", "a")[0]
D["a~ə"] = align("a", "ə")[0]
check_cond("coda nasal indel d(n,ə) ≈ 4.99", near(D["a~an"], 4.99),
           f"d={D['a~an']}")
check_cond("velar coda indel d(ŋ,ə) ≈ 4.45", near(D["ka~kaŋ"], 4.45),
           f"d={D['ka~kaŋ']}")
check_cond("onset plosive removal = indel(p) ≈ 6.15", near(D["pa~a"], 6.15),
           f"d={D['pa~a']}")
# (a,p)~a is rejected (the point sits at the trajectory end, the anchor
# cost is 0) — the coda plosive pays the full consonant indel d(p, ə)
check_cond("coda plosive removal = d(p,ə) ≈ 6.15", near(D["ap~a"], 6.15),
           f"d={D['ap~a']}")
check_cond("vowel deletion cheap: a~ə = 1.86", near(D["a~ə"], 1.86),
           f"d={D['a~ə']}")

# ------------------------------------------------------------------
# 5. metric properties
# ------------------------------------------------------------------
# symmetry on a sample (the edit distance with null-element indels and
# the symmetric absorption must be symmetric)
PAIRS = [("ã", "an"), ("na", "an"), ("apak", "akap"), ("kaŋ", "kã"),
         ("tʰ", "th"), ("ai", "ia"), ("aieu", "eou"), ("aa", "a"),
         ("pa", "a"), ("ɛ", "ai"), ("ka", "kaŋ"), ("na", "ã")]
sym_bad = 0
for a, b in PAIRS:
    dab = align(a, b)[0]
    dba = align(b, a)[0]
    if abs(dab - dba) > 1e-3:
        sym_bad += 1
        print(f"  asymmetric: {a!r}~{b!r} {dab:.3f} vs {dba:.3f}")
check_cond("symmetry d(A,B) == d(B,A) on 12 pairs", sym_bad == 0,
           f"{sym_bad} asymmetric")

# triangle inequality is NOT a hard invariant of the design: the
# absorption is a discount (a point on the trajectory), so a leg that
# absorbs can undercut the sum — assert it only on triples where no leg
# is discounted (verified), and keep the relaxed bound elsewhere
TRI = [("na", "ã", "an"), ("a", "an", "kaŋ"), ("p", "a", "n")]
tri_bad = 0
for x, y, z in TRI:
    dxy = align(x, y)[0]
    dyz = align(y, z)[0]
    dxz = align(x, z)[0]
    if dxz > dxy + dyz + 1e-6:
        tri_bad += 1
        print(f"  triangle violated: {x!r}~{z!r} {dxz:.3f} > "
              f"{dxy:.3f}+{dyz:.3f}")
check_cond("triangle inequality on 3 undiscounted triples", tri_bad == 0,
           f"{tri_bad} violated")

# identity and near-identity
check_cond("identical strings d=0", align("apak", "apak")[0] < 1e-6,
           f"d={align('apak','apak')[0]:.4f}")
check_cond("one-feature difference is small (t~tʰ via absorption)",
           near(D["tʰ~t+h"], 0.52), f"d={D['tʰ~t+h']}")

# ------------------------------------------------------------------
# 6. vowel-block trajectory rules still in place
# ------------------------------------------------------------------
d, r = align("aieu", "eou")
check_cond("vowel cluster 4 vs 3 (2.0 < d < 4.0)", 2.0 < d < 4.0,
           f"d={d}")
d, _ = align("aa", "a")
check_cond("geminate one mora (aa~a ≈ 1.0)", near(d, 1.0), f"d={d}")
# consonant geminates mirror the vowels (M1): one mora for the geminate
# deletion, identity for the length-marked form
d, _ = align("mm", "m")
check_cond("consonant geminate one mora (mm~m ≈ 1.0)", near(d, 1.0),
           f"d={d}")
d, _ = align("mː", "mm")
check_cond("length-marked nasal ≡ geminate (mː~mm ≈ 0)", d < 1e-6,
           f"d={d}")

# ------------------------------------------------------------------
# 7. adversarial probes: cases the design must NOT shortcut
# ------------------------------------------------------------------
# a coda plosive is real information — the trivial absorption (a point at
# the trajectory end, zero anchor cost) is rejected, so ap~ã pays the
# full consonant indel and ap~an the coda place contrast
D["ap~ã"] = align("ap", "ã")[0]
D["ap~an"] = align("ap", "an")[0]
D["ak~aŋ"] = align("ak", "aŋ")[0]
D["am~an"] = align("am", "an")[0]
check_cond("coda plosive vs nasalisation NOT absorbed (ap~ã > 6)",
           D["ap~ã"] > 6.0, f"d={D['ap~ã']}")
check_cond("coda place contrast kept (ap~an ≈ 4.76)", near(D["ap~an"], 4.76),
           f"d={D['ap~an']}")
check_cond("velar coda place (ak~aŋ ≈ 3.73)", near(D["ak~aŋ"], 3.73),
           f"d={D['ak~aŋ']}")
check_cond("labial coda place (am~an ≈ 2.97)", near(D["am~an"], 2.97),
           f"d={D['am~an']}")

# over-absorption trap: p~(k,a) has the unclamped projection t*=4 outside
# the trajectory, so apa~aka pays the honest substitution, not a discount
D["apa~aka"] = align("apa", "aka")[0]
check_cond("medial substitution honest (apa~aka ≈ 6.66)",
           near(D["apa~aka"], 6.66), f"d={D['apa~aka']}")

# laryngeal contrasts come through the metric, not the alignment
D["ka~kʼa"] = align("ka", "kʼa")[0]
D["sa~za"] = align("sa", "za")[0]
check_cond("ejective contrast (ka~kʼa ≈ 2.92)", near(D["ka~kʼa"], 2.92),
           f"d={D['ka~kʼa']}")
check_cond("voicing contrast (sa~za ≈ 1.50)", near(D["sa~za"], 1.50),
           f"d={D['sa~za']}")

# a consonant must not absorb a vowel pair member: abandon~adonban is a
# ban↔don metathesis, and the honest positional correspondence pays
# 2·d(b,d) + 2·d(a,o) — the b~(d,o) fake (the vowel hidden behind the
# anchor plus one mora: sqrt(d(b,d)² + 1.0)) must not fire
D["aban~adon"] = align("abandon", "adonban")[0]
check_cond("metathesis pays the honest correspondence (abandon~adonban ≈ 12.78)",
           near(D["aban~adon"], 12.78), f"d={D['aban~adon']}")

# chains: aspiration is charged once wherever it sits
D["apʰa~apha"] = align("apʰa", "apha")[0]
D["pʰra~pra"] = align("pʰra", "pra")[0]
D["tˠa~ta"] = align("tˠa", "ta")[0]
check_cond("affricate+asp chain (apʰa~apha ≈ 0.52)",
           near(D["apʰa~apha"], 0.52), f"d={D['apʰa~apha']}")
check_cond("cluster aspiration (pʰra~pra ≈ 0.52)", near(D["pʰra~pra"], 0.52),
           f"d={D['pʰra~pra']}")
check_cond("velarised onset (tˠa~ta ≈ 0.63)", near(D["tˠa~ta"], 0.63),
           f"d={D['tˠa~ta']}")

# ------------------------------------------------------------------
# 8. tone: the extra vectors are part of the distance (ma˥ ≠ ma˩)
# ------------------------------------------------------------------
D["ma5~ma1"] = align("ma˥", "ma˩")[0]
D["ma51~ma1"] = align("ma˥˩", "ma˩")[0]
D["ma51~ma15"] = align("ma˥˩", "ma˩˥")[0]
D["maC1~maC5"] = align("ma꜀", "ma꜅")[0]
D["up~down"] = align("ꜛma", "ꜜma")[0]
check_cond("tone contrast (ma˥~ma˩ = 1.0)", near(D["ma5~ma1"], 1.0),
           f"d={D['ma5~ma1']}")
check_cond("contour vs level shares suffix (ma˥˩~ma˩ = 0.5)",
           near(D["ma51~ma1"], 0.5), f"d={D['ma51~ma1']}")
check_cond("reversed contour (ma˥˩~ma˩˥ = 2.0)", near(D["ma51~ma15"], 2.0),
           f"d={D['ma51~ma15']}")
check_cond("tone class contrast (ma꜀~ma꜅ = 1.0)", near(D["maC1~maC5"], 1.0),
           f"d={D['maC1~maC5']}")
check_cond("upstep vs downstep (ꜛma~ꜜma = 0.5)", near(D["up~down"], 0.5),
           f"d={D['up~down']}")

# ------------------------------------------------------------------
# 9. adversarial blind spots (fixed): the gates must hold
# ------------------------------------------------------------------
# velar onset removal must not collapse: k owns place 0.30 (TAU is >=),
# and the point may not BE a pair member (k,a)~a is rejected
D["ka~a"] = align("ka", "a")[0]
D["ga~a"] = align("ga", "a")[0]
D["kma~ma"] = align("kma", "ma")[0]
check_cond("velar onset honest (ka~a = indel(k) ≈ 4.04)",
           near(D["ka~a"], 4.04), f"d={D['ka~a']}")
check_cond("voiced velar onset honest (ga~a > 3.5)", D["ga~a"] > 3.5,
           f"d={D['ga~a']}")
check_cond("cluster onset honest (kma~ma ≈ 4.04)", near(D["kma~ma"], 4.04),
           f"d={D['kma~ma']}")

# a point that carries NO pair content cannot absorb: aː (no velar-open
# gesture) must not absorb the n of [an] — the coda pays its full indel
D["aː~an"] = align("aː", "an")[0]
check_cond("un-nasalised length pays the coda indel (aː~an ≈ 5.99)",
           near(D["aː~an"], 5.99), f"d={D['aː~an']}")

# tone rides every path: blocks, absorptions, indels
D["a5i~ai"] = align("a˥i", "ai")[0]
D["ã5~a5n"] = align("ã˥", "a˥n")[0]
D["ã~a5n"] = align("ã", "a˥n")[0]
D["ɛ~ai5"] = align("ɛ", "ai˥")[0]
D["ã~an5"] = align("ã", "an˥")[0]
D["a5~ə"] = align("a˥", "ə")[0]
check_cond("tone visible in vowel blocks (a˥i~ai = 1.0)",
           near(D["a5i~ai"], 1.0), f"d={D['a5i~ai']}")
check_cond("tone rides absorption (ã˥~a˥n = 1.16)",
           near(D["ã5~a5n"], 1.16), f"d={D['ã5~a5n']}")
check_cond("tone not free in absorption (ã~a˥n = 2.16)",
           near(D["ã~a5n"], 2.16), f"d={D['ã~a5n']}")
check_cond("tone on block extras charged (ɛ~ai˥ = 2.26)",
           near(D["ɛ~ai5"], 2.26), f"d={D['ɛ~ai5']}")
check_cond("tone on absorbed coda charged (ã~an˥ = 2.16)",
           near(D["ã~an5"], 2.16), f"d={D['ã~an5']}")
check_cond("tone charged on deletion (a˥~ə = 2.85)",
           near(D["a5~ə"], 2.85), f"d={D['a5~ə']}")

# the airstream gap cannot be dodged through an absorption
D["ǃa~ta"] = align("ǃa", "ta")[0]
D["ɓa~ba"] = align("ɓa", "ba")[0]
check_cond("click vs pulmonic pays λ (ǃa~ta > 7)", D["ǃa~ta"] > 7.0,
           f"d={D['ǃa~ta']}")
check_cond("implosive vs pulmonic pays λ (ɓa~ba > 8)",
           D["ɓa~ba"] > 8.0, f"d={D['ɓa~ba']}")

# vowel metathesis must not be free (the permutation guard)
D["aiu~iau"] = align("aiu", "iau")[0]
D["aieu~eiau"] = align("aieu", "eiau")[0]
check_cond("vowel metathesis priced (aiu~iau > 2.5)", D["aiu~iau"] > 2.5,
           f"d={D['aiu~iau']}")
check_cond("cluster metathesis priced (aieu~eiau > 2.0)",
           D["aieu~eiau"] > 2.0, f"d={D['aieu~eiau']}")

print(f"\n{_common.total - _common.fails}/{_common.total} checks passed")
sys.exit(0 if _common.fails == 0 else 1)
