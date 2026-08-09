#!/usr/bin/env python3
"""Masked-distance fit & validation for the 16-dim SPEC-NEXT space.

Motivation: the full-connection distance counts EVERY dimension, but a
segment only ACTIVELY controls the articulators it recruits (v8 SPEC.md
§7 "Notes on Masking").  E.g. /ʃ/ and /m/ differ on place, but /m/'s
jet_focus is physically undefined; counting it inflates distance.
Masking keeps the Phatak fit (confusion data first) while making the
full-table distances physically grounded.

Distance with masks:
    d²(x,y) = Σ_k w_k · mask_k(x) · mask_k(y) · (x_k − y_k)²
Only dimensions BOTH segments actively control contribute.

Mask rules (which dims a segment class ACTIVELY controls):
  place           all segments (primary constriction location always)
  body            coarticulated only (ɧ, clicks, palatalised/velarised)
  lips_closed     bilabial/labiodental closure
  lips_rounded    vowels + rounded consonants (ɥ w ʍ ʃ ʒ)
  tip_shape       coronal segments (dental..retroflex + sibilants + /l r/)
  tongue_root     vowels (ATR/RTR) + pharyngealised
  vel_open        nasals + nasalised
  lateral_ratio   laterals + lateral fricatives
  voiced          all (voicing contrast is global)
  glottal_aperture all (phonation is global)
  glottal_tension fortis/lenis/creaky/ejective only
  larynx_height   ejective/implosive only
  duration        all
  jet_focus       sibilants only
  effective_oral_area all (manner/height is global)
  airflow_direction all

Run: python tools/fit_masked.py
"""

import json
import os
import sys

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC = os.path.join(ROOT, 'tools', 'data', 'vec_table_16.json')
DATA = os.path.join(ROOT, 'tools', 'data', 'phatak08_cm.json')
OUT = os.path.join(ROOT, 'tools', 'data', 'metric16.json')

DIMS = ['place', 'body', 'lips_closed', 'lips_rounded', 'tip_shape',
        'tongue_root', 'vel_open', 'lateral_ratio', 'voiced',
        'glottal_aperture', 'glottal_tension', 'larynx_height', 'duration',
        'jet_focus', 'effective_oral_area', 'airflow_direction']
CONS = ['p', 't', 'k', 'f', 'θ', 's', 'ʃ', 'b', 'd', 'ɡ', 'v', 'ð', 'z',
        'ʒ', 'm', 'n']

# place-cell membership for coronal mask (place value -> is coronal)
CORONAL = {'-0.45', '-0.30', '-0.15', '0.00'}  # dental..retroflex


def seg_mask(seg, vec):
    """16-dim binary mask for one segment."""
    m = np.zeros(16, dtype=int)
    m[0] = 1                                # place: always
    m[8] = 1                                # voiced: always
    m[9] = 1                                # aperture: always
    m[12] = 1                               # duration: always
    m[14] = 1                               # area: always
    m[15] = 1                               # airflow: always
    is_vowel = vec[8] >= 0.5 and vec[14] >= 0.4 and vec[12] >= 1.0
    if is_vowel:
        m[3] = 1                            # lips_rounded
        m[5] = 1                            # tongue_root (ATR)
    else:
        if vec[5] != 0 or vec[0] >= 0.60:
            m[5] = 1                        # RTR / pharyngealised
        if vec[2] >= 0.3 or seg in ('k͡p', 'ɡ͡b', 'ŋ͡m'):
            m[2] = 1                        # lip closure (incl. labio-velar)
        if -0.60 <= vec[0] <= 0.00:
            m[4] = 1                        # tip_shape (dental..retroflex)
    if vec[1] != 0:
        m[1] = 1                            # body (coarticulated)
    if vec[3] != 0:
        m[3] = 1                            # rounded consonant
    if vec[4] >= 0.5:
        m[4] = 1                            # tip gesture strong
    if vec[6] >= 0.5:
        m[6] = 1                            # vel_open (nasal)
    if vec[7] >= 0.5 or seg in ('ǁ',):
        m[7] = 1                            # lateral (incl. lateral click)
    if vec[10] != 0:
        m[10] = 1                           # tension
    if vec[11] != 0:
        m[11] = 1                           # larynx_height
    if vec[13] >= 0.5:
        m[13] = 1                           # jet_focus (sibilant)
    return m


def masked_d2(X, W, M):
    """X: (n,16), W: (16,), M: (n,16) masks -> (n,n) squared distance.

    OR semantics: a dimension contributes if EITHER segment actively
    controls it (its value is then meaningful).  The inactive partner's
    resting value (0 or neutral) still differs, which is physical:
    k~k͡p differ in lips_closed (k͡p has lip closure, k does not) and the
    distance MUST count it.  (Intersection semantics fails here: k's
    lips_closed is inactive -> dimension dropped -> distance 0.)
    """
    d2 = np.zeros((len(X), len(X)))
    for k in range(16):
        mm = (M[:, k][:, None] | M[:, k][None, :]).astype(float)
        dk = (X[:, None, k] - X[None, :, k]) ** 2
        d2 += W[k] * mm * dk
    return d2


def load():
    d = json.load(open(VEC, encoding='utf-8'))
    tbl = d['table']
    names = list(tbl)
    X = np.array([tbl[n] for n in names])
    M = np.array([seg_mask(n, tbl[n]) for n in names])
    X16 = np.array([tbl[c] for c in CONS])
    M16 = np.array([seg_mask(c, tbl[c]) for c in CONS])
    ph = json.load(open(DATA, encoding='utf-8'))
    n = len(CONS)
    counts = np.array([[ph['counts'][snr][i][j]
                        for j in range(n)] for snr in ph['snr_db']
                       for i in range(n)]).reshape(len(ph['snr_db']), n, n)
    return names, X, M, X16, M16, counts


def nll(counts, D, loga):
    tot = 0.0
    for c in range(counts.shape[0]):
        P = np.exp(-np.exp(loga[c]) * D)
        P = np.clip(P, 1e-300, None)
        P /= P.sum(axis=1, keepdims=True)
        tot -= np.sum(counts[c] * np.log(P))
    return tot


def loco(counts, D):
    held = 0.0
    for c in range(counts.shape[0]):
        tr = np.delete(counts, c, axis=0)
        sc = minimize(lambda la: nll(tr, D, la),
                      np.zeros(counts.shape[0] - 1), method='L-BFGS-B')
        sc2 = minimize(lambda la: nll(counts[c:c + 1], D, la),
                       [0.0], method='L-BFGS-B')
        held += nll(counts[c:c + 1], D, sc2.x)
    return held


def main():
    names, X, M, X16, M16, counts = load()
    k = 16
    TIER = np.array([1, 1, 1, 1, 1, 1, 8, 2, 8, 8, 8, 1, 2, 2, 2, 4],
                    dtype=float)
    fixed = [1, 5, 10, 11, 15]
    free = [i for i in range(k) if i not in fixed]

    # fit masked weights on the 16 Phatak consonants, with FLOORS on
    # key dims (user decision): place>=4, area>=4, lips_rounded>=8.
    # The 16-consonant confusion data alone collapse these (they only
    # matter for the full IPA space); floors keep the space sane.
    FLOOR = np.zeros(k)
    FLOOR[0] = 8.0     # place (0.15*√8 = 0.42 between adjacent cells)
    FLOOR[2] = 0.5     # lips_closed (k~k͡p needs it)
    FLOOR[3] = 8.0     # lips_rounded
    FLOOR[14] = 16.0   # effective_oral_area (vowel height; no 16-cons signal)

    def obj(x):
        logw = np.zeros(k)
        logw[list(fixed)] = 0.0
        logw[free] = x[:len(free)]
        loga = x[len(free):]
        W = np.exp(logw)
        W = np.maximum(W, FLOOR)   # key-dim floors
        D2 = masked_d2(X16, W, M16)
        D = np.sqrt(np.maximum(D2, 1e-12))
        return nll(counts, D, loga) + 0.1 * np.sum(logw[free] ** 2)

    r = minimize(obj, np.zeros(len(free) + 4), method='L-BFGS-B')
    logw = np.zeros(k)
    logw[list(fixed)] = 0.0
    logw[free] = r.x[:len(free)]
    W = np.exp(logw)
    W = np.maximum(W, FLOOR)   # key-dim floors
    # cap over-fitted dims (masked fit sees only sibilant pairs on jet)
    W[13] = min(W[13], 8.0)     # jet_focus
    W[4] = min(W[4], 8.0)       # tip_shape
    W[0] = min(W[0], 15.0)      # place
    D2 = masked_d2(X16, W, M16)
    D16m = np.sqrt(np.maximum(D2, 1e-12))
    lo = loco(counts, D16m)

    print('== masked-distance fit ==')
    print(f'LOCO (masked): {lo:,.0f}  (v8 21,564, unmasked-16d 22,047)')
    for i, n in enumerate(DIMS):
        print(f'  {n:<22} {W[i]:>10.4f}')

    # full table minNN under masked distance
    D2a = masked_d2(X, W, M)
    Da = np.sqrt(np.maximum(D2a, 1e-12))
    np.fill_diagonal(Da, np.inf)
    nn = Da.min(axis=1)
    n_bad = int((Da < 0.6).sum() // 2)
    print(f'\nfull table masked minNN = {nn.min():.3f}, <0.6: {n_bad} pairs')
    print('closest pairs:')
    for i in np.argsort(nn)[:12]:
        j = np.argmin(Da[i])
        print(f'  {names[i]}~{names[j]}: {nn[i]:.3f}')

    if '--write' in sys.argv:
        json.dump({'version': 10, 'dimensions': DIMS,
                   'weights': [round(float(x), 4) for x in W],
                   'lambda': 5.5, 'metric': None, 'masked': True},
                  open(OUT, 'w'), indent=2, ensure_ascii=False)
        print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
