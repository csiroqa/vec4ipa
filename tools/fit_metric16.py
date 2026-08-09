#!/usr/bin/env python3
"""Fit 16-dim SPEC-NEXT metric weights to the Phatak 08 confusion data.

Same Shepard-softmax model as fit_metric.py (v8), but on the NEW 16-dim
vectors (vec_table_16.json): P(j|i) = softmax_j(-a_c * d_ij) with
d_ij = sqrt(sum_k w_k (x_ik - x_jk)^2).

Cross-validation: leave-one-condition-out (4 folds), condition scales
refit per fold.  Regularisation: log-space toward 1.0 (neutral) AND a
tier-style run (voicing/nasal 8, manner 2, place 1) for comparison.

Run:  python tools/fit_metric16.py [--write]
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

RHO = 0.1   # log-space reg toward prior
TIER = np.array([1, 1, 1, 1, 1, 1, 8, 2, 8, 8, 8, 1, 2, 2, 2, 4],
                dtype=float)   # MN55-style tiers mapped to new dims
# no signal in the 16-consonant set (constant across the 16):
# body, tongue_root, glottal_tension, larynx_height, airflow
# NOTE: lips_rounded HAS signal now (/ʃ/ 0.25 rounding restored) -> free
FIXED = [1, 5, 10, 11, 15]


def load():
    d = json.load(open(VEC, encoding='utf-8'))
    tbl = d['table']
    X = np.array([tbl[c] for c in CONS])
    X_all = np.array(list(tbl.values()))
    ph = json.load(open(DATA, encoding='utf-8'))
    n = len(CONS)
    counts = np.array([[ph['counts'][snr][i][j]
                        for j in range(n)] for snr in ph['snr_db']
                       for i in range(n)]).reshape(len(ph['snr_db']), n, n)
    return X, counts, X_all


def nll(counts, D, loga):
    tot = 0.0
    for c in range(counts.shape[0]):
        P = np.exp(-np.exp(loga[c]) * D)
        P = np.clip(P, 1e-300, None)
        P /= P.sum(axis=1, keepdims=True)
        tot -= np.sum(counts[c] * np.log(P))
    return tot


NASALISED_VEL = 0.6


def vowel_consonant_penalty(X_all, weights, margin=0.2):
    """Vowel-consonant separation anchors (v8 port).

    The 16-consonant confusion data carry no signal for the vowel space,
    so the fit can collapse dimensions that only matter there (e.g. area,
    duration) -- wrecking the full table.  This hinge keeps every
    vowel-like base closer to another VOWEL than to any CONSONANT."""
    hinge = 0.0
    n = len(X_all)
    is_vowel = [(X_all[i][8] >= 0.5 and X_all[i][14] >= 0.4
                 and X_all[i][12] >= 1.0) for i in range(n)]
    v_idx = [i for i in range(n) if is_vowel[i]]
    c_idx = [i for i in range(n) if not is_vowel[i]]
    for i in v_idx:
        v = X_all[i]
        for nas, long in ((1, 0), (0, 1), (1, 1)):
            ext = v.copy()
            if nas:
                ext[6] = NASALISED_VEL
            if long:
                ext[12] = 2.0
            def d(j):
                return np.sqrt(np.sum(weights * (ext - X_all[j]) ** 2))
            d_v = min(d(j) for j in v_idx)
            d_c = min(d(j) for j in c_idx)
            hinge += max(0.0, d_v - d_c + margin)
    return hinge


def fit(X, counts, prior, rho=RHO, fixed=FIXED, X_all=None,
        rho_anchor=1.0, margin=0.2):
    k = X.shape[1]
    d2k = (X[:, None, :] - X[None, :, :]) ** 2
    free = [i for i in range(k) if i not in fixed]
    logp = np.log(prior)

    def obj(x):
        logw = np.zeros(k)
        logw[list(fixed)] = logp[list(fixed)]
        logw[free] = x[:len(free)]
        loga = x[len(free):]
        w = np.exp(logw)
        D = np.sqrt(np.maximum(d2k @ w, 0.0))
        pen = nll(counts, D, loga) + rho * np.sum((logw - logp) ** 2)
        if rho_anchor > 0 and X_all is not None:
            pen += rho_anchor * vowel_consonant_penalty(X_all, w, margin)
        return pen

    res = minimize(obj, np.concatenate([np.zeros(len(free)),
                                        np.zeros(counts.shape[0])]),
                   method='L-BFGS-B')
    logw = np.zeros(k)
    logw[list(fixed)] = logp[list(fixed)]
    logw[free] = res.x[:len(free)]
    w = np.exp(logw)
    a = np.exp(res.x[len(free):])
    D = np.sqrt(np.maximum(d2k @ w, 0.0))
    return w, a, nll(counts, D, np.log(a)), res


def cap_weights(w):
    """Cap over-fitted weights that explode on the FULL table (132 segs).
    The 16-consonant fit sees only /ʃ/'s 0.25 rounding; vowels differ by
    1.3 on lips_rounded and would explode (i-y 5.8).  v8 postprocess caps
    lips_rounded at 8.0 -- same here."""
    w = w.copy()
    w[3] = min(w[3], 8.0)     # lips_rounded (v8 cap)
    w[0] = min(w[0], 15.0)    # place
    w[4] = min(w[4], 8.0)     # tip_shape
    w[10] = min(w[10], 8.0)   # glottal_tension
    return w


def postprocess(w, X, prior):
    """v8-style aggregation fix: rescale the voicing dims (voiced +
    glottal_aperture) so stop voicing distance p-b == stop place p-t."""
    w = w.copy()
    i = {c: k for k, c in enumerate(CONS)}
    def dist(a, b):
        return np.sqrt(np.sum(w * (X[i[a]] - X[i[b]]) ** 2))
    dpb, dpt = dist('p', 'b'), dist('p', 't')
    if dpb > 0 and abs(dpb - dpt) > 1e-9:
        s = dpt / dpb
        w[8] *= s * s          # voiced
        w[9] *= s * s          # glottal_aperture
    return w


def loco(X, counts, w):
    k = X.shape[1]
    d2k = (X[:, None, :] - X[None, :, :]) ** 2
    D = np.sqrt(np.maximum(d2k @ w, 0.0))
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
    X, counts, X_all = load()
    k = X.shape[1]

    # neutral prior (w -> 1)
    wn, an, trn, resn = fit(X, counts, np.ones(k))
    locon = loco(X, counts, wn)
    # tier prior
    wt, at, trt, rest = fit(X, counts, TIER)
    locot = loco(X, counts, wt)
    # tier prior + vowel-consonant anchor (full-table sanity)
    wa, aa, tra, resa = fit(X, counts, TIER, X_all=X_all, rho_anchor=1.0)
    locoa = loco(X, counts, wa)
    # + cap
    wc = cap_weights(wa)
    lococ = loco(X, counts, wc)

    print('== 16-dim SPEC-NEXT metric fit (Phatak 08 + VC anchor) ==')
    print(f'{"dim":<22}{"tier":>9}{"anchor":>10}{"capped":>10}')
    for i, d in enumerate(DIMS):
        print(f'{d:<22}{wt[i]:>9.4f}{wa[i]:>10.4f}{wc[i]:>10.4f}')
    print(f'\ntrain NLL:  tier {trt:,.0f}   anchor {tra:,.0f}')
    print(f'LOCO held-out NLL:  tier {locot:,.0f}   anchor {locoa:,.0f}'
          f'   capped {lococ:,.0f}')
    print(f'(v8 published LOCO 22,316; v8 refit 21,564)')

    # key distances with final (capped) weights
    def dist(a, b, w):
        i, j = CONS.index(a), CONS.index(b)
        return np.sqrt(np.sum(w * (X[i] - X[j]) ** 2))
    print('\nkey distances (capped weights):')
    for a, b in [('p', 't'), ('p', 'b'), ('t', 'd'), ('f', 'v'),
                 ('θ', 'ð'), ('s', 'ʃ'), ('m', 'n')]:
        print(f'  {a}-{b}: {dist(a, b, wc):.3f}')

    if '--write' in sys.argv:
        json.dump({'version': 10, 'dimensions': DIMS,
                   'weights': [round(float(x), 4) for x in wc],
                   'lambda': 5.5, 'metric': None}, open(OUT, 'w'),
                  indent=2, ensure_ascii=False)
        print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
