#!/usr/bin/env python3
"""Bark-scale perceptual vowel anchors (F1/F2/F3 -> Bark -> MDS).

Rationale (user): raw F1/F2 under-separate rounded/central vowels; the
perceptual distance grows with F3 (i~y: Bark3 1.04 vs Bark2 0.39) and
with the Bark scale (critical-band spacing).  We derive vowel anchors
from a perceptual distance matrix:

  1. Collect F1/F2/F3 means per vowel per language (phonTools rda).
  2. Convert to Bark (Zwicker & Terhardt 1980).
  3. Perceptual distance = Euclidean in Bark(F1,F2,F3).
  4. MDS (2-D: height x frontness) fit to the pooled distance matrix.
  5. Map the MDS axes onto the SPEC-NEXT place (front/central/back) and
     area (height) anchors, stretching to the 0.6-margin grid.

Run: python tools/gen_bark_anchors.py
"""

import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
OUT = os.path.join(DATA, 'vowel_bark_anchors.json')

DATASETS = ['pb52', 'h95', 't07', 'f73', 'p73', 'b95', 'f99', 'a96', 'y96']
XS = {'i': 'i', 'I': 'ɪ', 'E': 'ɛ', '{': 'æ', 'a': 'a', 'V': 'ʌ', 'A': 'ɑ',
      'O': 'ɔ', 'o': 'o', 'U': 'ʊ', 'u': 'u', 'y': 'y', '9': 'œ', '2': 'ø',
      '}': 'ʉ', '1': 'ɨ', "3'": 'ɝ', 'e': 'e'}


def hz2bark(f):
    f = np.asarray(f, dtype=float)
    return 13 * np.arctan(0.00076 * f) + 3.5 * np.arctan((f / 7500.0) ** 2)


def load_means():
    import pyreadr
    means = {}   # vowel -> list of [bark1, bark2, bark3]
    for ds in DATASETS:
        try:
            df = pyreadr.read_r(os.path.join(DATA, ds + '.rda'))[ds]
        except Exception:
            continue
        if 'f3' not in df.columns:
            continue
        for _, r in df.iterrows():
            v = XS.get(str(r['vowel']))
            if v is None:
                continue
            means.setdefault(v, []).append(
                hz2bark([float(r['f1']), float(r['f2']), float(r['f3'])]))
    return {v: np.mean(np.array(x), axis=0) for v, x in means.items()}


def main():
    means = load_means()
    vowels = sorted(means)
    X = np.array([means[v] for v in vowels])
    print(f'vowels with F1/F2/F3: {len(vowels)}')
    print(f'{"v":<4}{"Bark1":>7}{"Bark2":>7}{"Bark3":>7}')
    for v in vowels:
        print(f'{v:<4}{X[vowels.index(v)][0]:>7.2f}{X[vowels.index(v)][1]:>7.2f}'
              f'{X[vowels.index(v)][2]:>7.2f}')

    # perceptual distance matrix (Bark3 Euclidean)
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(2))

    # MDS 2-D via classical scaling
    n = len(vowels)
    H = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * H @ (D ** 2) @ H
    evals, evecs = np.linalg.eigh(B)
    idx = np.argsort(evals)[::-1][:2]
    Y = evecs[:, idx] * np.sqrt(np.maximum(evals[idx], 0))

    print('\n== MDS 2-D coordinates (Bark3 perceptual space) ==')
    for i, v in enumerate(vowels):
        print(f'  {v}: x={Y[i, 0]:+.3f} y={Y[i, 1]:+.3f}')

    # map MDS -> SPEC-NEXT axes:
    #   dim0 = height (F1-ish): high vowels have SMALL Bark1
    #   dim1 = frontness: front vowels have LARGE Bark2
    # verify orientation with known vowels
    print('\n== orientation check ==')
    print(f'  i (high/front): y={Y[vowels.index("i"), 1]:+.3f} '
          f'x={Y[vowels.index("i"), 0]:+.3f}')
    print(f'  a (low):        x={Y[vowels.index("a"), 0]:+.3f}')
    print(f'  u (back):       y={Y[vowels.index("u"), 1]:+.3f}')
    print(f'  y (round i):    x={Y[vowels.index("y"), 0]:+.3f} '
          f'y={Y[vowels.index("y"), 1]:+.3f}')

    if '--write' in sys.argv:
        json.dump({'bark_means': {v: list(map(float, means[v]))
                                  for v in vowels},
                   'mds': {v: [float(Y[i, 0]), float(Y[i, 1])]
                           for i, v in enumerate(vowels)},
                   'source': 'phonTools F1/F2/F3 -> Bark (Zwicker & Terhardt'
                             ' 1980) -> classical MDS'},
                  open(OUT, 'w'), indent=2, ensure_ascii=False)
        print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
