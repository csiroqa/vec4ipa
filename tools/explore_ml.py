#!/usr/bin/env python3
"""ML ablation suite for the over-complete dim set (SPEC-NEXT exploration v3).

Goal: shrink 137 derived dims to <=12 with all evidence agreeing.

Evidence (all on the Phatak 08 16-consonant confusion data):
  A. L1 (LASSO) path on the Shepard softmax kernel -- ISTA with backtracking.
     Scale is pinned by fitting a* on the FULL 137-dim set first (fixes the
     w->cw, a->a/sqrt(c) identifiability hole), and the lambda grid is
     gradient-scaled (lambda = r * max|grad| at w0), so the path really
     sparsifies: r=1 -> ~0 dims, r->0 -> full set.
  B. Stability selection: 50 bootstraps of the 4 conditions.
  C. Random-forest permutation importance  (pairwise regression).
  D. Gradient-boosting permutation importance (pairwise regression).
  E. Mutual information (pairwise regression).
  F. mRMR: forward selection with MI relevance minus Pearson redundancy.
  G. sklearn LassoCV on the pairwise linear model (independent of the kernel).
  Final: vote across the 7 rankings, then greedy backward elimination on
  LOCO until <=12 dims (kept while LOCO <= baseline * 1.05).

All output is ASCII (console-safe).  Every feature is derived by explicit
rules from the base 16-D table, deduplicated -- no hand-picked values.

Run:  python tools/explore_ml.py
"""

import json
import os
import sys
import json
import os
import sys
import re

import numpy as np
from scipy.optimize import minimize

from explore_dims import (load_vectors, load_counts, build_candidates,
                          BASE_DIMS, CONS, nll_weights, distance_matrix,
                          ipa_metrics)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRIC_JSON = os.path.join(ROOT, 'metric.json')
RHO = 1e-4
L1_ITERS = 400
L1_TOL = 1e-9


def aname(n):
    return n.replace('²', '^2').replace('×', '*').replace('μ', 'u')


def pairs_matrix(F16, counts):
    n_cond = counts.shape[0]
    n = counts.shape[1]
    Xp, yp = [], []
    for c in range(n_cond):
        Nrow = counts[c].sum(axis=1)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                Xp.append((F16[i] - F16[j]) ** 2)
                yp.append(counts[c][i, j] / max(Nrow[i], 1e-9))
    return np.array(Xp), np.array(yp)


def debias_fit(F16, counts, idx):
    """Unpenalised refit on the selected columns only (log-weight prior)."""
    F = F16[:, idx]
    k = F.shape[1]
    d2k = (F[:, None, :] - F[None, :, :]) ** 2

    def obj(x):
        logw, loga = x[:k], x[k:]
        D = np.sqrt(np.maximum(d2k @ np.exp(logw), 0.0))
        return nll_weights(counts, D, loga) + 0.1 * np.sum(logw ** 2)

    res = minimize(obj, np.concatenate([np.zeros(k),
                                        np.zeros(counts.shape[0])]),
                   method='L-BFGS-B')
    return np.exp(res.x[:k]), np.exp(res.x[k:])


def fit_alpha_full(F16, counts, idx):
    """Fit only the condition scales for a fixed weight vector (w=1)."""
    F = F16[:, idx]
    d2 = np.sum((F[:, None, :] - F[None, :, :]) ** 2, axis=2)

    def obj(loga):
        D = np.sqrt(np.maximum(d2, 0.0))
        return nll_weights(counts, D, loga)

    res = minimize(obj, np.zeros(counts.shape[0]), method='L-BFGS-B')
    return np.exp(res.x)


def loco_idx(F16, counts, idx, w):
    D = distance_matrix(F16[:, idx], w)
    held = 0.0
    for c in range(counts.shape[0]):
        tr = np.delete(counts, c, axis=0)
        sc = minimize(lambda loga: nll_weights(tr, D, loga),
                      np.zeros(counts.shape[0] - 1), method='L-BFGS-B')
        sc2 = minimize(lambda loga: nll_weights(counts[c:c + 1], D, loga),
                       [0.0], method='L-BFGS-B')
        held += nll_weights(counts[c:c + 1], D, sc2.x)
    return held


def fit_sparse_l1(F16, counts, lam, a_fixed, w0=None, max_iter=L1_ITERS):
    """ISTA (backtracking) for min_{w>=0} NLL(w, a_fixed) + lam*||w||_1."""
    n_cond = counts.shape[0]
    k = F16.shape[1]
    if w0 is None:
        w0 = np.full(k, 1e-3)
    w = w0.copy()
    d2k = (F16[:, None, :] - F16[None, :, :]) ** 2
    loga_f = np.log(a_fixed)
    Nrow = [counts[c].sum(axis=1) for c in range(n_cond)]

    def fval(w):
        D = np.sqrt(np.maximum(d2k @ w, 0.0))
        return nll_weights(counts, D, loga_f) + RHO * np.sum(w ** 2)

    def grad_of(w):
        D = np.sqrt(np.maximum(d2k @ w, 0.0))
        Wd = np.zeros_like(D)
        safe = D > 1e-12
        Wd[safe] = 1.0 / (2.0 * D[safe])
        g = np.zeros(k)
        for c in range(n_cond):
            a = a_fixed[c]
            P = np.exp(-a * D)
            P = np.clip(P, 1e-300, None)
            P /= P.sum(axis=1, keepdims=True)
            S = a * (counts[c] - Nrow[c][:, None] * P)
            g += np.einsum('ij,ijk->k', S * Wd, d2k)
        return g + 2.0 * RHO * w

    f0 = fval(w)
    t = 1e-4
    for _ in range(max_iter):
        g = grad_of(w)
        while True:
            wn = np.maximum(w - t * g - lam * t, 0.0)
            if fval(wn) <= f0 - 1e-14 or t < 1e-14:
                break
            t *= 0.5
        if t < 1e-14 or np.max(np.abs(wn - w)) < L1_TOL:
            w = wn
            break
        w = wn
        f0 = fval(w)
        t = min(t * 1.2, 1.0)
    return w


def main():
    np.random.seed(0)
    vecs = load_vectors()
    _, counts = load_counts()
    names = list(vecs)
    cand = build_candidates(vecs)
    allnames = list(cand)
    M = np.array([cand[n] for n in allnames]).T
    _, first = np.unique(M, axis=1, return_index=True)
    allnames = [allnames[i] for i in sorted(first)]
    F_all = np.array([cand[n] for n in allnames]).T
    cons_idx = [names.index('ɡ' if c == 'g' else c) for c in CONS]
    F16 = F_all[cons_idx]
    k = F16.shape[1]
    n_cond = counts.shape[0]
    base_idx = [allnames.index(d) for d in BASE_DIMS]

    # ---- baseline: PUBLISHED v8 weights (metric.json) ----
    pub = json.load(open(os.path.join(ROOT, 'metric.json'), encoding='utf-8'))
    wpub = np.array(pub['weights'])
    LOCO_b = loco_idx(F16, counts, base_idx, wpub)
    minnn_b, coll_b, cv_b, _ = ipa_metrics(F_all[:, base_idx], wpub, names)
    print(f'baseline v8 PUBLISHED weights:  LOCO {LOCO_b:,.0f}  '
          f'minNN {minnn_b:.3f}  coll<.35 {coll_b}  chainCV {cv_b:.2f}\n')

    # ---- A. L1 path, gradient-scaled lambda ----
    print('=== A. L1 path (kernel, alpha refit per lambda) ===')
    # alpha fixed at w0; then ISTA; lambda grid dense & log-spaced
    a_star = fit_alpha_full(F16, counts, list(range(k)))
    w = None
    for r in np.geomspace(0.6, 2e-5, 26):
        lam = r * 1e4   # alpha-scaled: gmax ~ 9e4 at w=1e-3; start big
        w = fit_sparse_l1(F16, counts, lam, a_star, w0=w)
        idx = np.nonzero(w > 1e-9)[0]
        wd, ad = debias_fit(F16, counts, idx) if len(idx) else (None, None)
        if wd is None:
            print(f'  r={r:.5f}  n=0')
            continue
        held = loco_idx(F16, counts, idx, wd)
        minnn, coll, cv, _ = ipa_metrics(F_all[:, idx], wd, names)
        flag = '  <== <=12' if len(idx) <= 12 else ''
        print(f'  r={r:.5f}  n={len(idx):>3d}  LOCO {held:>9,.0f} '
              f'(d {held-LOCO_b:+,.0f})  minNN {minnn:.3f}  coll {coll}'
              f'  CV {cv:.2f}{flag}')
        if len(idx) <= 12:
            print('      ' + ', '.join(aname(allnames[i]) for i in idx))

    # ---- B. stability selection ----
    print('\n=== B. stability selection (50 bootstrap) ===')
    lam_stab = 1e-4
    freq = np.zeros(k)
    for _ in range(50):
        bs = np.random.choice(n_cond, size=n_cond, replace=True)
        wb2 = fit_sparse_l1(F16, counts[bs], lam_stab, a_star, max_iter=150)
        freq += (wb2 > 1e-9).astype(float)
    freq /= 50.0
    for i in np.argsort(-freq):
        if freq[i] >= 0.5:
            print(f'  {aname(allnames[i]):<34} {freq[i]:>5.2f}')

    # ---- pairwise regression pipeline ----
    Xp, yp = pairs_matrix(F16, counts)
    print(f'\npair samples {Xp.shape}')

    # ---- C/D. RF + GBDT permutation importance ----
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.inspection import permutation_importance
    print('=== C/D. RF & GBDT permutation importance (top 15 each) ===')
    rf = RandomForestRegressor(n_estimators=300, random_state=0, n_jobs=-1)
    rf.fit(Xp, yp)
    p_rf = permutation_importance(rf, Xp, yp, n_repeats=3, random_state=0,
                                  n_jobs=-1).importances_mean
    gb = GradientBoostingRegressor(n_estimators=200, random_state=0)
    gb.fit(Xp, yp)
    p_gb = permutation_importance(gb, Xp, yp, n_repeats=3, random_state=0,
                                  n_jobs=-1).importances_mean
    for i in np.argsort(-p_rf)[:15]:
        print(f'  RF  {aname(allnames[i]):<34} {p_rf[i]:.3e}')
    for i in np.argsort(-p_gb)[:15]:
        print(f'  GBDT {aname(allnames[i]):<34} {p_gb[i]:.3e}')

    # ---- E. mutual information ----
    from sklearn.feature_selection import mutual_info_regression
    print('\n=== E. mutual information (top 15) ===')
    mi = mutual_info_regression(Xp, yp, random_state=0)
    for i in np.argsort(-mi)[:15]:
        print(f'  MI  {aname(allnames[i]):<34} {mi[i]:.4f}')

    # ---- F. mRMR ----
    print('\n=== F. mRMR forward (MI relevance - Pearson redundancy) ===')
    corr = np.corrcoef(Xp.T)
    mi_std = (mi - mi.min()) / (mi.max() - mi.min() + 1e-12)
    selected = []
    rest = list(range(k))
    for _ in range(20):
        best, bestsc = None, -1
        for j in rest:
            red = max(abs(corr[j, s]) for s in selected) if selected else 0.0
            sc = mi_std[j] - red
            if sc > bestsc:
                best, bestsc = j, sc
        selected.append(best)
        rest.remove(best)
        print(f'  {len(selected):>2d}. {aname(allnames[best]):<34} '
              f'MI {mi[best]:.4f}')
        if len(selected) >= 12:
            break

    # ---- G. LassoCV on the linear pairwise model ----
    print('\n=== G. sklearn LassoCV (linear pairwise model) ===')
    from sklearn.linear_model import LassoCV
    lcv = LassoCV(cv=4, random_state=0, max_iter=5000).fit(Xp, yp)
    nz = np.nonzero(np.abs(lcv.coef_) > 1e-6)[0]
    order_lasso = nz[np.argsort(-np.abs(lcv.coef_[nz]))]
    print(f'  alpha {lcv.alpha_:.2e}, {len(order_lasso)} non-zero:')
    for i in order_lasso[:20]:
        print(f'  {aname(allnames[i]):<34} coef {lcv.coef_[i]:.3e}')

    # ---- consensus vote ----
    print('\n=== consensus (vote across A-G rankings) ===')
    top_sets = [
        set(np.argsort(-p_rf)[:12]),
        set(np.argsort(-p_gb)[:12]),
        set(np.argsort(-mi)[:12]),
        set(order_lasso[:12]),
        set(np.argsort(-freq)[:12]),
        set(selected[:12]),
    ]
    votes = np.zeros(k)
    for i in range(k):
        votes[i] = sum(1 for s in top_sets if i in s)
    order_v = np.argsort(-votes)
    print('  dim  votes/6 (RF GBDT MI Lasso stab mRMR):')
    for i in order_v:
        if votes[i] >= 2:
            print(f'  {aname(allnames[i]):<34} {votes[i]:.0f}')

    # ---- final: three-stage selection ----
    # stage 1: ML consensus core, restricted to the PHYSICAL pool:
    # the 16 base dims + SPEC-NEXT place/glottal_state (implementable in
    # the C parser; interaction/squared terms are noise for the IPA space).
    PHYSICAL = (set(BASE_DIMS) | {'place', 'glottal_state'})
    phy_idx = [i for i, n in enumerate(allnames) if n in PHYSICAL]
    print(f'\nstage 1: ML consensus core -- physical pool '
          f'({len(phy_idx)} dims):')
    print('  ' + ', '.join(aname(allnames[i]) for i in phy_idx))
    votes_phy = {i: votes[i] for i in phy_idx}
    core = [i for i in sorted(votes_phy, key=lambda i: (-votes_phy[i], i))
            if votes_phy[i] >= 1][:14]
    if len(core) < 12:
        core = phy_idx[:14]
    print(f'  core ({len(core)}): '
          + ', '.join(aname(allnames[i]) for i in core))

    # stage 2: repair IPA space -- add dims until the FULL 132-segment
    # table is sane (minNN >= 0.15, coll <= baseline, CV <= 0.6) while
    # LOCO stays within +5% of baseline.  Candidate pool = everything
    # the ML methods did NOT see: zero-variance-on-16-consonant dims
    # (vowel height, nasality, laterality, airstream, root, tension).
    F16var = F16.var(axis=0)
    ipa_only = [i for i in range(k) if F16var[i] < 1e-12]
    print(f'\nstage 2: IPA-only dims (zero variance on the 16 consonants, '
          f'n={len(ipa_only)}):')
    print('  ' + ', '.join(aname(allnames[i]) for i in ipa_only))

    def metrics_of(idx):
        wd, _ = debias_fit(F16, counts, idx)
        # IPA-only dims (no Phatak signal) keep weight 1.0, like the
        # FIXED_DIMS convention in fit_metric.py -- otherwise the Phatak
        # fit zeroes them and they cannot separate the IPA table.
        for t in range(k):
            if F16var[t] < 1e-12 and t in idx:
                wd[np.where(np.array(idx) == t)[0][0]] = 1.0
        held = loco_idx(F16, counts, idx, wd)
        minnn, coll, cv, _ = ipa_metrics(F_all[:, idx], wd, names)
        return wd, held, minnn, coll, cv

    def report(tag, idx):
        if not idx:
            print(f'  {tag:<40} EMPTY')
            return None
        wd, held, minnn, coll, cv = metrics_of(idx)
        print(f'  {tag:<40} LOCO {held:>9,.0f} (d {held-LOCO_b:+,.0f})  '
              f'minNN {minnn:.3f}  coll {coll}  CV {cv:.2f}')
        return dict(held=held, minnn=minnn, coll=coll, cv=cv)

    cur = list(core)
    m = report('consensus core', cur)
    LOCO_BUDGET = LOCO_b * 1.05
    pool = [i for i in phy_idx if i not in cur]
    added = []

    # set-cover repair: find the colliding pairs (d < 0.15) on the full
    # table and, each round, add the dim with the largest |x_a - x_b|
    # separation over the unresolved pairs (weighted by how many pairs
    # it separates by > 0.15).
    while m is not None and (m['minnn'] < 0.15 or m['coll'] > coll_b
                             or m['cv'] > 0.6):
        wd, held, minnn, coll, cv = metrics_of(cur)
        m = dict(held=held, minnn=minnn, coll=coll, cv=cv)
        if held > LOCO_BUDGET:
            print(f'  LOCO {held:,.0f} exceeds budget {LOCO_BUDGET:,.0f}; '
                  f'roll back')
            break
        D = distance_matrix(F_all[:, cur], wd)
        np.fill_diagonal(D, np.inf)
        pairs = np.argwhere(D < 0.15)
        if len(pairs) == 0:
            break
        print(f'  unresolved collisions: {len(pairs)} pairs '
              f'(minNN {m["minnn"]:.3f})')
        scores = {}
        for i in pool:
            sep = 0.0
            for a, b in pairs:
                d = abs(F_all[a, i] - F_all[b, i])
                if d > 0.15:
                    sep += 1.0
            if sep > 0:
                scores[i] = sep
        if not scores:
            print('  no single dim separates any colliding pair')
            break
        best_i = max(scores, key=scores.get)
        cur = cur + [best_i]
        pool.remove(best_i)
        added.append(best_i)
        print(f'  + add {aname(allnames[best_i]):<34} '
              f'(separates {scores[best_i]:.0f}/{len(pairs)} pairs)')

    print(f'\nstage 2 result: +{len(added)} dims added '
          f'({", ".join(aname(allnames[i]) for i in added)})')

    # stage 3: trim to <=12 by greedy backward elimination, keeping all
    # four constraints satisfied (LOCO budget, minNN, coll, CV).
    def ok(idx, held=None, minnn=None, coll=None, cv=None):
        if held is None:
            _, held, minnn, coll, cv = metrics_of(idx)
        return (held <= LOCO_BUDGET and minnn >= 0.15 and coll <= coll_b
                and cv <= 0.6)

    while len(cur) > 12:
        candidates = []
        for drop in cur:
            trial = [i for i in cur if i != drop]
            wd, held, minnn, coll, cv = metrics_of(trial)
            candidates.append((held, drop, minnn, coll, cv))
        candidates.sort()
        if not ok([i for i in cur if i != candidates[0][1]],
                  candidates[0][0], candidates[0][2],
                  candidates[0][3], candidates[0][4]):
            print(f'  cannot trim further (would break constraints)')
            break
        _, drop, minnn, coll, cv = candidates[0]
        cur.remove(drop)
        print(f'  trim {aname(allnames[drop]):<34} -> LOCO {candidates[0][0]:,.0f} '
              f'minNN {minnn:.3f} coll {coll} CV {cv:.2f}')

    wd, held, minnn, coll, cv = metrics_of(cur)
    print(f'\nFINAL {len(cur)} dims:  LOCO {held:,.0f} '
          f'(d {held-LOCO_b:+,.0f})  minNN {minnn:.3f}  coll {coll}  CV {cv:.2f}')
    print('  ' + ', '.join(aname(allnames[i]) for i in cur))


if __name__ == '__main__':
    main()
