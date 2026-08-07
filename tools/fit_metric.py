#!/usr/bin/env python3
"""Refit the metric weights per METRIC.md §2.

Fits the 16-D diagonal metric weights w_k to the Phatak, Lovitt & Allen
(2008) white-noise consonant confusion matrices (tools/data/phatak08_cm.json,
the four mid-SNR conditions +12/+6/0/−6 dB, "other" responses excluded):

    P(j|i) = softmax_j(−a_c · d_ij),   d_ij = √(Σ_k w_k (x_ik − x_jk)²)

with a per-condition scale a_c (Shepard kernel).  L-BFGS-B on log(w) and
log(a); ℓ2 regularisation in log space pulls the weights toward the MN55
qualitative tiers (voicing/nasality 8, manner/duration 2, place 1), which
pins the otherwise degenerate global scale (w→c·w, a→a/√c).

Cross-validation (as reported in METRIC.md §2): leave-one-condition-out,
per-fold refit of the condition scales, held-out NLL.

Post-processing documented in METRIC.md §2:
  * no-signal dimensions stay at tier defaults (tongue_root 1.0,
    lateral_ratio 2.0, laryngeal_tension 8.0, airflow_direction 4.0);
  * lips_rounded is capped at 8.0;
  * the voiced/cg/sg voicing triplet is rescaled so the stop voicing
    distance equals the stop place distance (p–b = p–t);
  * λ is not part of this fit and stays at 5.0.

Run:  python tools/fit_metric.py            # report fit + LOCO, compare
      python tools/fit_metric.py --write    # also overwrite metric.json
"""

import json
import os
import sys

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data', 'phatak08_cm.json')
VECTORS_MD = os.path.join(ROOT, 'IPA_VECTORS.md')
METRIC_JSON = os.path.join(ROOT, 'metric.json')

RHO = 0.1   # log-space regulariser strength (see METRIC.md §2 discussion)

DIMS = ['lips_closed', 'lips_rounded', 'tt_pos', 'tt_height', 'tb_pos',
        'tongue_root', 'vel_open', 'lateral_ratio', 'voiced', 'cg', 'sg',
        'laryngeal_tension', 'duration', 'jet_focus',
        'effective_oral_area', 'airflow_direction']

TIER_INIT = np.array([1, 1, 1, 1, 1, 1, 8, 2, 8, 8, 8, 8, 2, 2, 2, 4],
                     dtype=float)

# ------------------------------------------------------------------
def load_vectors():
    vecs = {}
    for line in open(VECTORS_MD, encoding='utf-8'):
        t = line.strip()
        if t.startswith('`/') and '`: `(' in t:
            head, vec = t.split('`: `(')
            ipa = head[1:].rsplit('`', 1)[0].strip()
            if ipa.startswith('/') and ipa.endswith('/'):
                ipa = ipa[1:-1]
            elif ipa.startswith('/'):
                ipa = ipa[1:].split(' ')[0]
            vecs[ipa] = [float(x.strip()) for x in vec.rstrip(')`').split(',')]
    return vecs

def load_counts():
    d = json.load(open(DATA, encoding='utf-8'))
    n = len(d['consonants'])
    counts = np.array([[d['counts'][snr][i][j]
                        for j in range(n)] for snr in d['snr_db']
                       for i in range(n)]).reshape(len(d['snr_db']), n, n)
    return d['consonants'], counts

def distance_matrix(X, w):
    n = X.shape[0]
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            D[i, j] = np.sqrt(np.sum(w * (X[i] - X[j]) ** 2))
    return D

def nll_weights(counts, D, loga):
    """NLL of the counts given distance matrix D and per-condition log scales."""
    tot = 0.0
    for c in range(counts.shape[0]):
        P = np.exp(-np.exp(loga[c]) * D)
        P /= P.sum(axis=1, keepdims=True)
        P = np.clip(P, 1e-300, None)
        tot -= np.sum(counts[c] * np.log(P))
    return tot

def objective(x, X, counts, rho):
    u, loga = x[:16], x[16:]
    w = np.exp(u)
    D = distance_matrix(X, w)
    nll = nll_weights(counts, D, loga)
    reg = rho * np.sum((u - np.log(TIER_INIT)) ** 2)
    return nll + reg

def fit_weights(X, counts, rho=RHO, x0=None):
    n_cond = counts.shape[0]
    if x0 is None:
        x0 = np.concatenate([np.log(TIER_INIT), np.zeros(n_cond)])
    res = minimize(objective, x0, args=(X, counts, rho), method='L-BFGS-B')
    return np.exp(res.x[:16]), np.exp(res.x[16:]), res

def postprocess(w, X):
    w = w.copy()
    w[5] = 1.0    # tongue_root — no signal, tier default
    w[7] = 2.0    # lateral_ratio
    w[11] = 8.0   # laryngeal_tension
    w[15] = 4.0   # airflow_direction
    w[1] = min(w[1], 8.0)          # lips_rounded cap
    i = {c: k for k, c in enumerate(['p', 't', 'b', 'g', 'v', 'ð', 'z', 'ʒ'])}
    def dist(a, b):
        return np.sqrt(np.sum(w * (X[a] - X[b]) ** 2))
    dpb, dpt = dist(i['p'], i['b']), dist(i['p'], i['t'])
    if dpb > 0 and dpb != dpt:
        s = dpt / dpb
        for k in (8, 9, 10):        # voiced, cg, sg
            w[k] *= s * s
    return w

def loco(X, counts, weights):
    """leave-one-condition-out held-out NLL for a FIXED weight vector:
    per fold, fit the condition scales on the training conditions, then
    the held-out scale on the held-out condition."""
    n_cond = counts.shape[0]
    u = np.log(np.clip(weights, 1e-9, None))
    D = distance_matrix(X, weights)
    held = 0.0
    for c in range(n_cond):
        tr = np.delete(counts, c, axis=0)
        def scale_obj(loga):
            tot = 0.0
            for t in range(n_cond - 1):
                P = np.exp(-np.exp(loga[t]) * D)
                P /= P.sum(axis=1, keepdims=True)
                P = np.clip(P, 1e-300, None)
                tot -= np.sum(tr[t] * np.log(P))
            return tot
        sc = minimize(scale_obj, np.zeros(n_cond - 1), method='L-BFGS-B')
        def held_scale(loga):
            P = np.exp(-np.exp(loga[0]) * D)
            P /= P.sum(axis=1, keepdims=True)
            P = np.clip(P, 1e-300, None)
            return -np.sum(counts[c] * np.log(P))
        sc2 = minimize(held_scale, [0.0], method='L-BFGS-B')
        P = np.exp(-np.exp(sc2.x[0]) * D)
        P /= P.sum(axis=1, keepdims=True)
        P = np.clip(P, 1e-300, None)
        held -= np.sum(counts[c] * np.log(P))
    return held

def main():
    write = '--write' in sys.argv
    cons, counts = load_counts()
    vecs = load_vectors()
    X = np.array([vecs['ɡ' if c == 'g' else c] for c in cons])

    w_raw, a, res = fit_weights(X, counts)
    w = postprocess(w_raw, X)

    published = np.array(json.load(open(METRIC_JSON, encoding='utf-8'))['weights'])
    loco_fit = loco(X, counts, w)
    loco_tier = loco(X, counts, TIER_INIT)
    loco_pub = loco(X, counts, published)

    print(f'fit: nll+reg = {res.fun:.1f}  a_c = {np.round(a, 3).tolist()}')
    print()
    print(f'{"dim":<22}{"raw":>9}{"final":>9}{"published":>11}')
    for k, name in enumerate(DIMS):
        print(f'{name:<22}{w_raw[k]:>9.3f}{w[k]:>9.3f}{published[k]:>11.3f}')
    print()
    print(f'LOCO held-out NLL: fitted {loco_fit:,.0f} | tiers {loco_tier:,.0f} '
          f'| published {loco_pub:,.0f}')

    if write:
        m = json.load(open(METRIC_JSON, encoding='utf-8'))
        m['weights'] = [round(float(v), 4) for v in w]
        m['version'] = 4
        json.dump(m, open(METRIC_JSON, 'w', encoding='utf-8'), indent=2)
        print(f'\nwrote {METRIC_JSON}')

if __name__ == '__main__':
    main()
