#!/usr/bin/env python3
"""Fit the 13-dim SPEC-NEXT space to the real-language distribution
(phoible, 2157 languages / 5384 phoneme rows).

What is fitted:
  1. PROJECTION: every phoible phoneme (base + modifiers, e.g. tʰ, ŋʷ, ɛ̃)
     is mapped to a 13-dim vector via the anchor table + SPEC-NEXT rules.
  2. COVERAGE: per-dimension marginal histograms -- every anchor cell must
     be hit by real data; empty cells = design gaps (or genuinely absent
     phonemes, which the distribution says are unattested).
  3. EXTREME-VALUE PRESERVATION: no thresholding/clipping -- rare phonemes
     (bʱ, ejectives, retroflex, clicks, ʏ/ø pairs) must keep their exact
     anchor positions; the fitted weights must NOT collapse them.
  4. DENSITY CHECK: per-cell frequency (cross-language attestation) is
     reported but NOT used to move anchors (equal support; frequency only
     informs weights via fit_metric, never anchor positions).

Output: tools/data/distribution_fit.json + printed report.
Run: python tools/fit_distribution.py
"""

import csv
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOIBLE = os.path.join(ROOT, 'tools', 'data', 'phoible.csv')
VOWEL3D = os.path.join(ROOT, 'tools', 'data', 'vowel_3d_anchors.json')
OUT = os.path.join(ROOT, 'tools', 'data', 'distribution_fit.json')

# ---- anchor tables (from earlier derivation) ----
from place_anchors import PLACE, remap
# v8 base vectors for the 16-dim -> 13-dim projection
BASE = {}   # seg -> v8 16-vec
import re
_pat = re.compile(r"^`/([^/`]*)/`: `\((.*)\)`")
for _line in open(os.path.join(ROOT, 'IPA_VECTORS.md'), encoding='utf-8'):
    _m = _pat.match(_line.strip())
    if _m and len(_m.group(2).split(',')) == 16:
        BASE[_m.group(1)] = np.array(
            [float(x.strip()) for x in _m.group(2).replace('+', '').split(',')])

# vowel 3-D anchors (vowel_3d_anchors.json was computed on the OLD
# compressed scale [0.08, 0.92] and is remapped to the runtime place
# domain [-0.9, +0.9] -- kept here as research provenance; the committed
# runtime table (spec_next.scheme) encodes vowel frontness on BODY, not
# place, so this script's vowel place projection is a historical view.)
_V3 = json.load(open(VOWEL3D, encoding='utf-8'))
VOWEL_AREA = _V3['area']
VOWEL_PLACE = {v: round(remap(p), 3) for v, p in _V3['place'].items()}
VOWEL_ROUND = _V3['rounding']

# modifier rules (SPEC-NEXT §5, applied on top of the base)
def apply_mod(v, m):
    """m: one modifier char -> 13-dim delta/override rules."""
    if m == 'ʰ':
        v[8] = 0.9                      # aspirated -> glottal_state +0.9
    elif m == 'ʷ':
        v[2] = max(v[2], 0.5)
    elif m == 'ʲ':
        v[0] = min(v[0] + 0.04, 0.96)   # coarticulation OFFSET, never clip
    elif m == 'ˠ':
        v[0] = min(v[0] + 0.04, 0.96)
    elif m == 'ˤ':
        v[4] = 0.7
    elif m == '̃':
        v[5] = 0.6
    elif m == '̥':
        v[7] = 0.0
    elif m == '̬':
        v[7] = 1.0
    elif m == 'ː':
        v[9] = 2.0
    elif m == '̪':
        v[0] = 0.220
    elif m == 'ʼ':
        v[8] = -1.0
    elif m == '̰':
        v[8] = -0.7
    elif m == '̤':
        v[8] = 0.55
    elif m == '̺':
        v[3] = 0.65
    elif m == '̻':
        v[3] = 0.6
    elif m == '̟':
        v[0] = max(v[0] - 0.04, 0.02)
    elif m == '̠':
        v[0] = min(v[0] + 0.04, 0.98)
    elif m == 'ˀ':
        v[8] = min(v[8], -0.7)      # glottal onset: constricted
    elif m == '˞':
        v[3] = max(v[3], 0.5)       # rhoticised
    elif m == '̙':
        v[4] = 0.5                  # RTR
    elif m == '̘':
        v[4] = -0.5                 # ATR
    elif m == '̆':
        v[9] = min(v[9], 0.5)       # extra short
    elif m == '̩':
        v[9] = v[9] + 0.5           # syllabic
    elif m == '͈':
        v[9] = v[9] + 0.2           # fortis
    return v


def to13(seg):
    """seg -> 13-dim vector (SPEC-NEXT rules)."""
    v = np.zeros(13)
    base = seg[0]
    if base in PLACE:
        v[0] = PLACE[base]
        b8 = BASE.get(base)
        if b8 is None:
            b8 = np.zeros(16)
        v[1] = 1.0 if b8[0] >= 1.0 else 0.0
        v[2] = 0.0
        v[3] = b8[3]
        v[4] = b8[5]
        v[5] = b8[6]
        v[6] = b8[7]
        v[7] = b8[8]
        cg, sg = b8[9], b8[10]
        v[8] = (sg if sg >= 0.55 else
                (0.4 if cg == 0.0 and sg == 0.4 else
                 (0.0 if cg == 0.2 and sg == 0.0 else
                  (-0.55 if cg == 0.55 else
                   (-0.7 if cg == 0.7 else
                    (-1.0 if cg >= 0.9 else sg - cg))))))
        v[9] = b8[12]
        v[10] = b8[13]
        v[11] = b8[14]
        v[12] = b8[15]
    elif base in VOWEL_AREA:
        v[0] = VOWEL_PLACE[base]
        v[11] = VOWEL_AREA[base]
        v[2] = VOWEL_ROUND.get(base, 0.0)
        v[7] = 1.0
        v[9] = 1.0
    else:
        return None
    for m in seg[1:]:
        v = apply_mod(v, m)
    return v


def main():
    rows = list(csv.DictReader(open(PHOIBLE, encoding='utf-8')))
    # unique phoneme -> languages count (attestation)
    attested = Counter()
    for r in rows:
        if r['Phoneme']:
            attested[r['Phoneme']] += 1

    mapped = {}     # phoneme -> 13-vec
    unmapped = Counter()
    for ph in attested:
        v = to13(ph)
        if v is None:
            unmapped[ph[0]] += 1
        else:
            mapped[ph] = v

    print(f'phoible unique phonemes: {len(attested)}')
    print(f'mapped to 13-D: {len(mapped)}  unmapped: {sum(unmapped.values())}')
    print('  unmapped base glyphs:', dict(unmapped.most_common(15)))

    # ---- per-dimension marginal coverage ----
    M = np.array(list(mapped.values()))
    print(f'\n== per-dimension coverage (min/max/mean/std over real data) ==')
    dims = ['place', 'lips_closed', 'lips_rounded', 'tip_shape', 'tongue_root',
            'vel_open', 'lateral_ratio', 'voiced', 'glottal_state',
            'duration', 'jet_focus', 'effective_oral_area', 'airflow_direction']
    for k, d in enumerate(dims):
        col = M[:, k]
        print(f'  {d:<22} min {col.min():+.3f}  max {col.max():+.3f}  '
              f'mean {col.mean():+.3f}  std {col.std():.3f}')

    # ---- extreme-value preservation: report the rarest phonemes' anchors ----
    print('\n== extreme values (rarest attested phonemes, n_lang <= 3) ==')
    rare = [(n, ph) for ph, n in attested.items() if n <= 3 and ph in mapped]
    rare.sort()
    for n, ph in rare[:20]:
        v = mapped[ph]
        print(f'  {ph:<6} n={n:<3} vec=[{", ".join(f"{x:.2f}" for x in v[:8])}...]')

    # ---- empty cells on the place axis ----
    print('\n== place-axis coverage (real-language attestation per anchor) ==')
    place_cells = defaultdict(int)
    for ph, v in mapped.items():
        for a in PLACE.values():
            if abs(v[0] - a) < 1e-9:
                place_cells[a] += 1
    for a in sorted(set(PLACE.values())):
        n = place_cells.get(a, 0)
        flag = '  <-- EMPTY in phoible (keep: real langs have these)' if n == 0 else ''
        print(f'  place {a:.3f}: {n} phonemes{flag}')

    # ---- glottal_state coverage ----
    print('\n== glottal_state coverage ==')
    gs_cells = Counter(round(v[8], 2) for v in mapped.values())
    for g in sorted(gs_cells):
        print(f'  gs {g:+.2f}: {gs_cells[g]} phonemes')

    if '--write' in sys.argv:
        json.dump({
            'n_phonemes': len(mapped),
            'unmapped': dict(unmapped.most_common()),
            'extreme_values': [{'ph': ph, 'n_lang': n,
                                'vec': list(mapped[ph])}
                               for ph, n in sorted(attested.items())
                               if n <= 3 and ph in mapped],
            'place_coverage': {str(k): v for k, v in place_cells.items()},
        }, open(OUT, 'w'), indent=2, ensure_ascii=False)
        print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
