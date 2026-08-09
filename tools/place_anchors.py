#!/usr/bin/env python3
"""Shared SPEC-NEXT place anchors (v8-consistent scale, span 2).

place axis spans [-0.9, +0.9] (span 1.8, NOT 0.08-0.92): the earlier
version compressed v8's -1..+1 (span 2) to 0.08..0.92 (span 0.84), which
shrank unit-weight distances ~2.4x and forced the metric fit to inflate
place weights.  Restoring the v8 scale: 13 anchors, equal step 0.15,
0.1 margin at each end for coarticulation shifts (palatalisation etc.).

All other axes are physical limits or span-2 bipolar (as v8).

Transform from the old compressed table: new = -0.9 + 1.8*(old-0.08)/0.84.
"""

PLACE = {
    'p': -0.900, 'b': -0.900, 'm': -0.900, 'ɸ': -0.900, 'β': -0.900,
    'ʙ': -0.900, 'ɓ': -0.900, 'ʘ': -0.900, 'pʼ': -0.900,
    'f': -0.750, 'v': -0.750, 'ⱱ': -0.750, 'ɱ': -0.750, 'p̪': -0.750,
    'fʼ': -0.750, 'ʋ': -0.750,
    'θ': -0.600, 'ð': -0.600, 't̪': -0.600, 'd̪': -0.600, 'n̪': -0.600,
    'θʼ': -0.600,
    's': -0.450, 'z': -0.450, 't': -0.450, 'd': -0.450, 'n': -0.450,
    'ɹ': -0.450, 'r': -0.450, 'ɾ': -0.450, 'l': -0.450, 'ɺ': -0.450,
    'ɬ': -0.450, 'ɮ': -0.450, 'ǀ': -0.450, 'ǁ': -0.450, 'tʼ': -0.450,
    'sʼ': -0.450, 'ɗ': -0.450, 't͡s': -0.450, 'd͡z': -0.450,
    'ʃ': -0.300, 'ʒ': -0.300, 'ǃ': -0.300, 't͡ʃ': -0.300, 'd͡ʒ': -0.300,
    't͡ʃʼ': -0.300, 'ɕ': -0.150, 'ʑ': -0.150, 't͡ɕ': -0.150, 'd͡ʑ': -0.150,
    'ʂ': 0.000, 'ʐ': 0.000, 'ʈ': 0.000, 'ɖ': 0.000, 'ɳ': 0.000, 'ɻ': 0.000,
    'ɽ': 0.000, 'ɭ': 0.000, 'ʈ͡ʂ': 0.000, 'ɖ͡ʐ': 0.000,
    'ç': 0.150, 'ʝ': 0.150, 'c': 0.150, 'ɟ': 0.150, 'ɲ': 0.150, 'ʎ': 0.150,
    'j': 0.150, 'ǂ': 0.150, 'ɥ': 0.150, 'ʄ': 0.150,
    'x': 0.300, 'ɣ': 0.300, 'k': 0.300, 'ɡ': 0.300, 'ŋ': 0.300, 'ɰ': 0.300,
    'ʟ': 0.300, 'w': 0.300, 'ʍ': 0.300, 'kʼ': 0.300, 'xʼ': 0.300,
    'ɠ': 0.300, 'k͡p': 0.300, 'ɡ͡b': 0.300, 'ŋ͡m': 0.300, 'k͡x': 0.300,
    'χ': 0.450, 'ʁ': 0.450, 'q': 0.450, 'ɢ': 0.450, 'ɴ': 0.450, 'ʀ': 0.450,
    'qʼ': 0.450, 'ʛ': 0.450, 'q͡χ': 0.450,
    'ħ': 0.600, 'ʕ': 0.600,
    'ʜ': 0.750, 'ʢ': 0.750, 'ʡ': 0.750,
    'h': 0.900, 'ɦ': 0.900, 'ʔ': 0.900,
    'ɧ': -0.225,
}

# vowel place classes (same span-2 domain): front +0.15..+0.35,
# central 0.0, back +0.30..+0.45 -- derived per-vowel anchors in
# vowel_3d_anchors.json are on the OLD compressed scale; remap:
def remap(old):
    return -0.9 + 1.8 * (old - 0.08) / 0.84
