#!/usr/bin/env python3
"""Optimise vowel anchor coordinates (place, area) under the hard
min-distance constraint (all vowel pairs >= 0.6) while matching the
perceptual (Bark3) distance ranking.

Variables: 27 vowels x 2 coords (place, area).  Objective:
    min  sum over pairs |dist_anchor - target_dist|^2
    s.t. all anchor pair distances >= 0.6
where target_dist = monotone compression of Bark3 perceptual distance.

Weights: place 20, area 16 (current); lips_rounded 8 fixed (rounding
pairs separate on lips: i-y = 1.3*sqrt(8) = 3.68 > 0.6 automatically).
Only non-rounding-pair distances matter; rounding partners share coords.

Run: python tools/opt_vowels.py
"""

import json
import os
import sys

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
BARK = os.path.join(DATA, 'vowel_bark_anchors.json')
OUT = os.path.join(DATA, 'vowel_opt.json')

W_PLACE = 20.0
W_AREA = 16.0
MIN_D = 0.6
# all 27 IPA vowels (rounding partners share (place, area))
VOWELS = ['i', 'y', 'ɪ', 'ʏ', 'e', 'ø', 'ɛ', 'œ', 'æ', 'ɶ', 'a',
          'ɨ', 'ʉ', 'ɘ', 'ɵ', 'ə', 'ɜ', 'ɞ', 'ɐ',
          'ɯ', 'u', 'ʊ', 'ɤ', 'o', 'ʌ', 'ɔ', 'ɑ', 'ɒ']
ROUND_PARTNER = {'y': 'i', 'ʏ': 'ɪ', 'ø': 'e', 'œ': 'ɛ', 'ɶ': 'æ',
                 'ʉ': 'ɨ', 'ɵ': 'ɘ', 'ɞ': 'ɜ', 'u': 'ɯ', 'ʊ': 'ɯ',
                 'o': 'ɤ', 'ɔ': 'ʌ', 'ɒ': 'ɑ'}
# independent positions (unrounded + ʊ which has no partner measured)
POS = ['i', 'ɪ', 'e', 'ɛ', 'æ', 'a', 'ɨ', 'ɘ', 'ə', 'ɜ', 'ɐ',
       'ɯ', 'ʊ', 'ɤ', 'ʌ', 'ɑ']


def main():
    bark = json.load(open(BARK, encoding='utf-8'))
    # perceptual distance among POS (only those in bark data)
    mds = bark['mds']
    pos = [p for p in POS if p in mds]
    n = len(pos)
    Xp = np.array([mds[p] for p in pos])
    Dp = np.sqrt(((Xp[:, None, :] - Xp[None, :, :]) ** 2).sum(2))
    # target: compress perceptual to [MIN_D, 2.5]
    target = MIN_D + (2.5 - MIN_D) * (Dp / Dp.max())
    np.fill_diagonal(target, 0)

    # variables: 2*n coords; init from current table (place/area grid)
    tbl = json.load(open(os.path.join(DATA, 'vec_table_16.json'),
                         encoding='utf-8'))['table']
    x0 = np.zeros(2 * n)
    for i, p in enumerate(pos):
        x0[2 * i] = tbl[p][0]
        x0[2 * i + 1] = tbl[p][14]

    def dist_ij(y, i, j):
        dp = y[2 * i] - y[2 * j]
        da = y[2 * i + 1] - y[2 * j + 1]
        return np.sqrt(W_PLACE * dp ** 2 + W_AREA * da ** 2)

    def obj(y):
        s = 0.0
        pen = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                d = dist_ij(y, i, j)
                s += (d - target[i, j]) ** 2
                if d < MIN_D:
                    pen += (MIN_D - d) ** 2 * 100.0
        # keep within domain
        pen += 1.0 * np.sum(np.maximum(0, y[0::2] - 0.30) ** 2)
        pen += 1.0 * np.sum(np.maximum(0, -0.15 - y[0::2]) ** 2)
        pen += 1.0 * np.sum(np.maximum(0, y[1::2] - 1.0) ** 2)
        pen += 1.0 * np.sum(np.maximum(0, 0.30 - y[1::2]) ** 2)
        return s + pen

    r = minimize(obj, x0, method='L-BFGS-B', options={'maxiter': 2000})
    y = r.x
    print(f'objective = {r.fun:.3f}')
    print(f'{"v":<4}{"place":>8}{"area":>8}')
    for i, p in enumerate(pos):
        print(f'{p:<4}{y[2*i]:>8.3f}{y[2*i+1]:>8.3f}')

    # verify all pairs
    print('\n== pair verification (all POS pairs) ==')
    bad = 0
    for i in range(n):
        for j in range(i + 1, n):
            d = dist_ij(y, i, j)
            if d < MIN_D:
                bad += 1
                print(f'  {pos[i]}-{pos[j]}: {d:.3f}')
    print(f'pairs < {MIN_D}: {bad}')

    if '--write' in sys.argv:
        coords = {p: [round(float(y[2 * i]), 3), round(float(y[2 * i + 1]), 3)]
                  for i, p in enumerate(pos)}
        for rv, uv in ROUND_PARTNER.items():
            if uv in coords:
                coords[rv] = list(coords[uv])
        json.dump({'pos': coords, 'objective': r.fun}, open(OUT, 'w'),
                  indent=2, ensure_ascii=False)
        print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
