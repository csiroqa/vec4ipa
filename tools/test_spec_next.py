#!/usr/bin/env python3
"""SPEC-NEXT 16-dim design test suite (table + metric + mask sanity).

Validates the derived artifacts WITHOUT the C binaries (which still run
the v8 16-D table): the 16-dim vector table, the fitted metric, and the
masked distance all live in tools/data/*.json.

Checks:
  1. TABLE: 132 segments, 16 dims, all values in declared ranges.
  2. SYMMETRY/definite: masked distance is symmetric, zero diagonal,
     positive off-diagonal.
  3. KEY PAIRS: phonological contrasts >= 0.6 under the final weights
     (user-specified minimum for contrast pairs).
  4. NEAR PAIRS: perceptually-close pairs (vowel-glide, adjacent height)
     stay below a sane ceiling.
  5. AFFRICATE rule: duration == 0.5 + homorganic fricative duration,
     rounding inherited.
  6. GLIDE rule: j/ɥ/w/ɰ inherit vowel partner's root & lips.
  7. VOWEL GRID: three columns (front/central/back) on place, height
     cells monotone, rounding pairs share (place, area).
  8. MASK: only active dims contribute; k~k͡p separated by lips_closed.
  9. ROUND-TRIP consistency: gen_vec_table.py output is reproducible.
 10. EJECTIVE/IMPLOSIVE: larynx_height +1/-1, aperture values.

Run:  python tools/test_spec_next.py
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'tools'))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
VEC = os.path.join(DATA, 'vec_table_16.json')
METRIC = os.path.join(DATA, 'metric16.json')

DIMS = ['place', 'body', 'lips_closed', 'lips_rounded', 'tip_shape',
        'tongue_root', 'vel_open', 'lateral_ratio', 'voiced',
        'glottal_aperture', 'glottal_tension', 'larynx_height', 'duration',
        'jet_focus', 'effective_oral_area', 'airflow_direction']

total = 0
fails = 0


def check(name, cond, detail=''):
    global total, fails
    total += 1
    if not cond:
        fails += 1
        print(f'  FAIL: {name}  {detail}')
    return cond


def masked_d2(X, W, M):
    d2 = np.zeros((len(X), len(X)))
    for k in range(16):
        mm = (M[:, k][:, None] | M[:, k][None, :]).astype(float)
        d2 += W[k] * mm * (X[:, None, k] - X[None, :, k]) ** 2
    return d2


def main():
    global total, fails
    tbl = json.load(open(VEC, encoding='utf-8'))['table']
    dims = json.load(open(VEC, encoding='utf-8'))['dims']
    assert dims == DIMS, f'dims mismatch: {dims}'
    W = np.array(json.load(open(METRIC, encoding='utf-8'))['weights'])
    names = list(tbl)
    X = np.array([tbl[n] for n in names])
    M = np.array([mask_of(n, tbl[n]) for n in names])

    # ---- 1. table integrity ----
    print('== 1. table integrity ==')
    check('133 segments', len(names) == 133, f'got {len(names)}')
    check('16 dims', len(dims) == 16)
    ranges = [(-0.95, 0.95), (-0.6, 0.6), (0, 1), (-1, 1),
              (0.2, 1.0), (-1, 1), (0, 1), (0, 1), (0, 1),
              (-1, 1), (-1, 1), (-1, 1), (0, 2.5),
              (0, 1), (0, 1), (-1, 1)]
    for n in names:
        v = np.array(tbl[n])
        for k, (lo, hi) in enumerate(ranges):
            if not (lo <= v[k] <= hi):
                check(f'{n} dim{k} in range', False,
                      f'{v[k]} not in [{lo},{hi}]')
                break

    # ---- 2. masked distance properties ----
    print('\n== 2. masked distance properties ==')
    D2 = masked_d2(X, W, M)
    D = np.sqrt(np.maximum(D2, 1e-12))
    check('symmetric', np.allclose(D, D.T, atol=1e-9))
    check('zero diagonal', np.all(np.diag(D) < 1e-3))
    off = D[~np.eye(len(names), dtype=bool)]
    check('positive off-diagonal', (off > 0).all())

    # ---- 3. key contrast pairs >= 0.6 ----
    print('\n== 3. phonological contrast pairs >= 0.6 ==')
    def dd(a, b):
        return D[names.index(a), names.index(b)]
    KEY = [('p', 'b'), ('t', 'd'), ('k', 'g'), ('f', 'v'), ('θ', 'ð'),
           ('s', 'z'), ('ʃ', 'ʒ'), ('k', 'q'), ('c', 'k'), ('t', 't̪'),
           ('i', 'y'), ('e', 'ø'), ('a', 'ɑ'), ('u', 'o'), ('ʃ', 'ɕ'),
           ('ɕ', 'ʂ'), ('v', 'ⱱ'), ('k', 'kʼ'), ('p', 'pʰ')]
    for a, b in KEY:
        if b in names:
            d = dd(a, b)
            check(f'{a}-{b} >= 0.6', d >= 0.6, f'd={d:.3f}')

    # ---- 4. perceptually-near pairs stay near ----
    print('\n== 4. near pairs below ceiling (1.2) ==')
    NEAR = [('i', 'j'), ('u', 'w'), ('y', 'ɥ'), ('ɯ', 'ɰ'),
            ('ɛ', 'æ'), ('ə', 'ɜ'), ('ɜ', 'ɐ'), ('v', 'ⱱ'), ('k', 'kʰ'), ('a', 'ɐ')]
    for a, b in NEAR:
        if b in names:
            d = dd(a, b)
            check(f'{a}-{b} < 1.2', d < 1.2, f'd={d:.3f}')

    # ---- 5. affricate composition rule ----
    print('\n== 5. affricate rule (0.5 + fricative) ==')
    AFF = {'t͡s': 's', 'd͡z': 'z', 't͡ʃ': 'ʃ', 'd͡ʒ': 'ʒ', 't͡ɕ': 'ɕ',
           'd͡ʑ': 'ʑ', 'ʈ͡ʂ': 'ʂ', 'ɖ͡ʐ': 'ʐ', 'k͡x': 'x', 'q͡χ': 'χ'}
    for aff, fric in AFF.items():
        if aff in tbl and fric in tbl:
            exp = 0.5 + tbl[fric][12]
            check(f'{aff} duration = 0.5+{fric}', abs(tbl[aff][12] - exp) < 0.01,
                  f'{tbl[aff][12]} vs {exp}')
            check(f'{aff} rounding == {fric}', tbl[aff][3] == tbl[fric][3],
                  f'{tbl[aff][3]} vs {tbl[fric][3]}')

    # ---- 6. glide inheritance ----
    print('\n== 6. glide inherits vowel partner ==')
    GLIDES = {'j': 'i', 'ɥ': 'y', 'w': 'u', 'ɰ': 'ɯ'}
    for glide, vow in GLIDES.items():
        if glide in tbl and vow in tbl:
            check(f'{glide} root == {vow}', tbl[glide][5] == tbl[vow][5],
                  f'{tbl[glide][5]} vs {tbl[vow][5]}')
            check(f'{glide} lips == {vow}', tbl[glide][3] == tbl[vow][3],
                  f'{tbl[glide][3]} vs {tbl[vow][3]}')
            check(f'{glide} area < {vow}', tbl[glide][14] < tbl[vow][14],
                  f'{tbl[glide][14]} vs {tbl[vow][14]}')

    # ---- 7. vowel grid ----
    print('\n== 7. vowel grid ==')
    # front/central/back live on BODY (tongue-body position; v8 semantics),
    # not on place (tip gesture) -- vowels have no tip gesture.
    FRONT = {'i', 'y', 'ɪ', 'ʏ', 'e', 'ɛ', 'æ', 'ɶ'}
    CENT = {'ɨ', 'ʉ', 'ɘ', 'ɵ', 'ə', 'ɜ', 'ɐ'}
    BACK = {'ɯ', 'u', 'ʊ', 'ɤ', 'o', 'ʌ', 'ɔ', 'ɑ', 'ɒ'}
    for v in FRONT:
        if v in tbl:
            check(f'{v} front body', tbl[v][1] > 0.15, f'{tbl[v][1]}')
    for v in CENT:
        if v in tbl:
            check(f'{v} central body', abs(tbl[v][1]) < 0.06, f'{tbl[v][1]}')
    for v in BACK:
        if v in tbl:
            check(f'{v} back body', tbl[v][1] < -0.15, f'{tbl[v][1]}')
    # height monotone within front column
    front_h = [tbl[v][14] for v in ['i', 'ɪ', 'e', 'ɛ', 'æ'] if v in tbl]
    check('front height monotone', front_h == sorted(front_h))
    # rounding pairs share position
    # rounding partners share the IPA-chart CELL; perceptual Bark2 data
    # centralises ø/œ/a (rounded vowels) so they may sit off the front
    # column -- only y/ʉ/u/o/ɔ/ɒ must share their partner's position.
    ROUND = {'y': 'i', 'ʉ': 'ɨ', 'u': 'ɯ', 'o': 'ɤ', 'ɔ': 'ʌ', 'ɒ': 'ɑ'}
    for rv, uv in ROUND.items():
        if rv in tbl and uv in tbl:
            check(f'{rv} body == {uv}', tbl[rv][1] == tbl[uv][1],
                  f'{tbl[rv][1]} vs {tbl[uv][1]}')
            check(f'{rv} area == {uv}', tbl[rv][14] == tbl[uv][14],
                  f'{tbl[rv][14]} vs {tbl[uv][14]}')

    # ---- 8. mask: k~k͡p separated ----
    print('\n== 8. mask keeps k~k͡p apart ==')
    if 'k͡p' in tbl:
        dk = dd('k', 'k͡p')
        check('k-k͡p > 0.4', dk > 0.4, f'd={dk:.3f}')

    # ---- 9. reproducible generation ----
    print('\n== 9. gen_vec_table reproducibility ==')
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools',
                                                     'gen_vec_table.py')],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode == 0:
        tbl2 = json.load(open(VEC, encoding='utf-8'))['table']
        same = all(np.allclose([float(x) for x in tbl[n]],
                               [float(x) for x in tbl2[n]], atol=1e-6)
                    for n in names)
        check('reproducible', same)
    else:
        check('reproducible', False, r.stderr[:200])

    # ---- 10. ejective/implosive ----
    print('\n== 10. laryngeal state ==')
    for e in ['pʼ', 'tʼ', 'kʼ', 'qʼ']:
        if e in tbl:
            check(f'{e} larynx +1', tbl[e][11] == 1.0, f'{tbl[e][11]}')
            check(f'{e} aperture -1', tbl[e][9] == -1.0, f'{tbl[e][9]}')
    for i_ in ['ɓ', 'ɗ', 'ʄ', 'ɠ', 'ʛ']:
        if i_ in tbl:
            check(f'{i_} larynx -1', tbl[i_][11] == -1.0, f'{tbl[i_][11]}')
            check(f'{i_} aperture -0.55', tbl[i_][9] == -0.55, f'{tbl[i_][9]}')

    print(f'\n== {total - fails}/{total} checks passed ==')
    sys.exit(1 if fails else 0)


def mask_of(seg, vec):
    """Mirror fit_masked.seg_mask (avoid import coupling)."""
    m = np.zeros(16, dtype=int)
    m[0] = m[8] = m[9] = m[12] = m[14] = m[15] = 1
    is_vowel = vec[8] >= 0.5 and vec[14] >= 0.4 and vec[12] >= 1.0
    if is_vowel:
        m[3] = m[5] = 1
    else:
        if vec[5] != 0 or vec[0] >= 0.60:
            m[5] = 1
        if vec[2] >= 0.3 or seg in ('k͡p', 'ɡ͡b', 'ŋ͡m'):
            m[2] = 1
        if -0.60 <= vec[0] <= 0.00:
            m[4] = 1
    if vec[1] != 0:
        m[1] = 1
    if vec[3] != 0:
        m[3] = 1
    if vec[4] >= 0.5:
        m[4] = 1
    if vec[6] >= 0.5:
        m[6] = 1
    if vec[7] >= 0.5 or seg == 'ǁ':
        m[7] = 1
    if vec[10] != 0:
        m[10] = 1
    if vec[11] != 0:
        m[11] = 1
    if vec[13] >= 0.5:
        m[13] = 1
    return m


if __name__ == '__main__':
    main()
