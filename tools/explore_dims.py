#!/usr/bin/env python3
"""Exploration: over-complete dimension set + ablation (SPEC-NEXT draft).

Builds a deliberately over-complete feature set (base 16 dims + candidate
new dims: equal-spaced place axis, glottal_state merge, airstream one-hots,
manner one-hots, interactions), then ablates every candidate on three axes:

  1. perceptual quality  — LOCO NLL on the Phatak 08 16-consonant data
     (weight refit per subset; dims constant on the 16-consonant subset are
     fixed at weight 1, exactly like METRIC.md's no-signal dims)
  2. IPA-space quality   — nearest-neighbour floor + collision count on the
     full 132-segment table (weighted by the fitted metric)
  3. equal place support — fricative place-chain step CV on the full metric

Pipeline: baseline (v8 16 dims) -> marginal value of each candidate ->
greedy forward selection (train NLL, LOCO tracked per step) ->
leave-one-out ablation of the selected set.

Run from the repo root:  python tools/explore_dims.py
"""

import itertools
import json
import os
import re

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS_MD = os.path.join(ROOT, 'IPA_VECTORS.md')
DATA = os.path.join(ROOT, 'tools', 'data', 'phatak08_cm.json')

RHO = 0.1            # log-space reg strength (toward 1.0, neutral prior)
FRIC_CHAIN = 'ɸ f θ s ʃ ɕ ʂ ç x χ ħ ʜ h'.split()
CONS = ['p', 't', 'k', 'f', 'θ', 's', 'ʃ', 'b', 'd', 'g', 'v', 'ð', 'z', 'ʒ',
        'm', 'n']

BASE_DIMS = ['lips_closed', 'lips_rounded', 'tongue_tip_pos', 'tongue_tip_height',
             'tongue_body_pos', 'tongue_root', 'vel_open', 'lateral_ratio',
             'voiced', 'constricted_glottis', 'spread_glottis',
             'laryngeal_tension', 'duration', 'jet_focus',
             'effective_oral_area', 'airflow_direction']


# --------------------------------------------------------------------------
# data loading

def load_vectors():
    vecs = {}
    pat = re.compile(r"^`/([^/`]*)/`: `\((.*)\)`")
    for line in open(VECTORS_MD, encoding='utf-8'):
        m = pat.match(line.strip())
        if m and len(m.group(2).split(',')) == 16:
            vecs[m.group(1)] = np.array(
                [float(x.strip()) for x in m.group(2).replace('+', '').split(',')])
    return vecs


def load_counts():
    d = json.load(open(DATA, encoding='utf-8'))
    n = len(d['consonants'])
    counts = np.array([[d['counts'][snr][i][j]
                        for j in range(n)] for snr in d['snr_db']
                       for i in range(n)]).reshape(len(d['snr_db']), n, n)
    return d['consonants'], counts


# --------------------------------------------------------------------------
# candidate dimensions (over-complete)

PLACE_ANCHOR = {
    'p': 0.000, 'b': 0.000, 'm': 0.000, 'ɸ': 0.000, 'β': 0.000, 'ʙ': 0.000,
    'ɓ': 0.000, 'ʘ': 0.000, 'pʼ': 0.000,
    'f': 0.083, 'v': 0.083, 'ⱱ': 0.083, 'ɱ': 0.083, 'p̪': 0.083, 'fʼ': 0.083,
    'θ': 0.167, 'ð': 0.167, 't̪': 0.167, 'd̪': 0.167, 'n̪': 0.167, 'θʼ': 0.167,
    's': 0.250, 'z': 0.250, 't': 0.250, 'd': 0.250, 'n': 0.250, 'ɹ': 0.250,
    'r': 0.250, 'ɾ': 0.250, 'l': 0.250, 'ɺ': 0.250, 'ɬ': 0.250, 'ɮ': 0.250,
    'ǀ': 0.250, 'ǁ': 0.250, 'tʼ': 0.250, 'sʼ': 0.250, 'ɗ': 0.250,
    'ʃ': 0.333, 'ʒ': 0.333, 'ǃ': 0.333,
    'ɕ': 0.417, 'ʑ': 0.417,
    'ʂ': 0.500, 'ʐ': 0.500, 'ʈ': 0.500, 'ɖ': 0.500, 'ɳ': 0.500, 'ɻ': 0.500,
    'ɽ': 0.500, 'ɭ': 0.500, 'ʄ': 0.583,
    'ç': 0.583, 'ʝ': 0.583, 'c': 0.583, 'ɟ': 0.583, 'ɲ': 0.583, 'ʎ': 0.583,
    'j': 0.583, 'ǂ': 0.583, 'ɥ': 0.583,
    'x': 0.667, 'ɣ': 0.667, 'k': 0.667, 'ɡ': 0.667, 'ŋ': 0.667, 'ɰ': 0.667,
    'ʟ': 0.667, 'w': 0.667, 'ʍ': 0.667, 'kʼ': 0.667, 'xʼ': 0.667, 'ɠ': 0.667,
    'χ': 0.750, 'ʁ': 0.750, 'q': 0.750, 'ɢ': 0.750, 'ɴ': 0.750, 'ʀ': 0.750,
    'qʼ': 0.750, 'ʛ': 0.750,
    'ħ': 0.833, 'ʕ': 0.833,
    'ʜ': 0.917, 'ʢ': 0.917, 'ʡ': 0.917,
    'h': 1.000, 'ɦ': 1.000, 'ʔ': 1.000,
    't͡s': 0.250, 'd͡z': 0.250, 't͡ʃ': 0.333, 'd͡ʒ': 0.333,
    't͡ɕ': 0.417, 'd͡ʑ': 0.417, 'ʈ͡ʂ': 0.500, 'ɖ͡ʐ': 0.500,
    'k͡x': 0.667, 'q͡χ': 0.750, 'k͡p': 0.667, 'ɡ͡b': 0.667, 'ŋ͡m': 0.667,
    'ɧ': 0.375, 't͡ʃʼ': 0.333,
}

AIRSTREAM = {'pulmonic', 'ejective', 'implosive', 'click'}


def airstream_of(v):
    if v[15] < 0:
        return 'implosive' if v[8] >= 0.5 else 'click'
    return 'ejective' if v[9] >= 0.9 else 'pulmonic'


def manner_of(v):
    """One-hot manner classes derived from the base vector."""
    if v[8] >= 0.5 and v[14] >= 0.4 and v[12] >= 1.0:
        return 'vowel'
    if v[6] >= 0.5:
        return 'nasal'
    if v[7] >= 0.9:
        return 'lateral'
    if 1.2 <= v[12] <= 1.6:
        return 'affricate'
    if 0.4 <= v[12] <= 1.0 and 0.01 <= v[14] <= 0.15:
        return 'fricative'
    if abs(v[12] - 0.5) < 0.05 and v[14] <= 0.3:
        return 'trill'
    if abs(v[12] - 0.3) < 0.05:
        return 'tap'
    if v[12] <= 0.1 and v[14] <= 0.05:
        return 'plosive'
    return 'approximant'


def build_candidates(vecs):
    """Over-complete feature set (>= 150 dims), every column derived by an
    explicit rule from the base 16-D table — no hand-picked values:
      16 linear  + 16 squares + 120 pairwise products (2nd-order polynomial
      expansion of the base table) + 4 airstream one-hots + 9 manner
      one-hots (rule-derived classes) + place / glottal_state / aspiration.
    Returns {name: np.array(132,)}; caller deduplicates identical columns."""
    names = list(vecs)
    X = np.array([vecs[n] for n in names])
    cand = {}

    for k, dname in enumerate(BASE_DIMS):
        cand[dname] = X[:, k].copy()
    for k, dname in enumerate(BASE_DIMS):
        cand[f'{dname}²'] = X[:, k] ** 2
    for a, b in itertools.combinations(range(len(BASE_DIMS)), 2):
        cand[f'{BASE_DIMS[a]}×{BASE_DIMS[b]}'] = X[:, a] * X[:, b]

    # airstream one-hots (4)
    for a in AIRSTREAM:
        cand[f'air_{a}'] = np.array([1.0 if airstream_of(X[i]) == a else 0.0
                                     for i in range(len(names))])

    # manner one-hots (9)
    for m in ['vowel', 'nasal', 'lateral', 'affricate', 'fricative',
              'trill', 'tap', 'plosive', 'approximant']:
        cand[f'mnr_{m}'] = np.array([1.0 if manner_of(X[i]) == m else 0.0
                                     for i in range(len(names))])

    # equal-spaced place axis (SPEC-NEXT §3): explicit anchor for
    # consonants, body_pos-derived for vowels
    def place_of(i):
        n, v = names[i], X[i]
        if n in PLACE_ANCHOR:
            return PLACE_ANCHOR[n]
        if v[8] >= 0.5 and v[14] >= 0.4 and v[12] >= 1.0:   # vowel
            b = v[4]
            return 0.500 + 0.083 * b if b >= 0 else 0.500 - 0.333 * b
        raise KeyError(f'no place anchor for {n!r}')
    cand['place'] = np.array([place_of(i) for i in range(len(names))])

    # glottal_state merge (SPEC-NEXT §4): gs = sg - cg
    cand['glottal_state'] = X[:, 10] - X[:, 9]
    # aspiration degree for voiceless
    cand['aspiration'] = np.clip(X[:, 10] - 0.4, 0.0, 1.0)
    return cand


# --------------------------------------------------------------------------
# fitting & metrics (mirror fit_metric.py structure, generalized to F)

def distance_matrix(F, w):
    d2 = np.sum(((F[:, None, :] - F[None, :, :]) ** 2) * w, axis=2)
    return np.sqrt(np.maximum(d2, 0.0))


def nll_weights(counts, D, loga):
    tot = 0.0
    for c in range(counts.shape[0]):
        P = np.exp(-np.exp(loga[c]) * D)
        P = np.clip(P, 1e-300, None)
        P /= P.sum(axis=1, keepdims=True)
        tot -= np.sum(counts[c] * np.log(P))
    return tot


def fit_subset(F16, counts, free_idx, x0=None):
    """Fit log-weights for free dims + 4 log scales; fixed dims stay at 1.0."""
    n_cond = counts.shape[0]
    fixed = [i for i in range(F16.shape[1]) if i not in free_idx]

    def obj(x):
        u = np.zeros(F16.shape[1])
        u[list(fixed)] = 0.0            # log(1)
        u[free_idx] = x[:len(free_idx)]
        loga = x[len(free_idx):]
        w = np.exp(u)
        D = distance_matrix(F16, w)
        nll = nll_weights(counts, D, loga)
        reg = RHO * np.sum((u[free_idx]) ** 2)
        return nll + reg

    if x0 is None:
        x0 = np.concatenate([np.zeros(len(free_idx)), np.zeros(n_cond)])
    res = minimize(obj, x0, method='L-BFGS-B')
    w = np.ones(F16.shape[1])
    w[free_idx] = np.exp(res.x[:len(free_idx)])
    a = np.exp(res.x[len(free_idx):])
    return w, a, res


def loco(F16, counts, w):
    D = distance_matrix(F16, w)
    held = 0.0
    for c in range(counts.shape[0]):
        tr = np.delete(counts, c, axis=0)
        sc = minimize(lambda loga: nll_weights(tr, D, loga),
                      np.zeros(counts.shape[0] - 1), method='L-BFGS-B')
        sc2 = minimize(lambda loga: nll_weights(counts[c:c + 1], D, loga),
                       [0.0], method='L-BFGS-B')
        held += nll_weights(counts[c:c + 1], D, sc2.x)
    return held


def ipa_metrics(F_all, w, names):
    D = distance_matrix(F_all, w)
    np.fill_diagonal(D, np.inf)
    nn = D.min(axis=1)
    minnn = nn.min()
    collide = int((D < 0.35).sum() // 2)
    steps = np.array([D[names.index(FRIC_CHAIN[k]), names.index(FRIC_CHAIN[k + 1])]
                      for k in range(len(FRIC_CHAIN) - 1)])
    return minnn, collide, steps.std() / steps.mean(), steps.mean()


def summarize(tag, F16, F_all, counts, names, free_idx):
    w, a, res = fit_subset(F16, counts, free_idx)
    train = res.fun
    held = loco(F16, counts, w)
    minnn, collide, chaincv, chainmean = ipa_metrics(F_all, w, names)
    print(f'{tag:<38} train {train:>9,.0f}  LOCO {held:>9,.0f}  '
          f'minNN {minnn:>5.3f}  coll<.35 {collide:>3d}  chainCV {chaincv:>5.2f}  chainμ {chainmean:>5.2f}')
    return dict(train=train, loco=held, minnn=minnn, collide=collide,
                chaincv=chaincv, chainmean=chainmean)


# --------------------------------------------------------------------------

def main():
    vecs = load_vectors()
    _, counts = load_counts()
    names = list(vecs)
    cand = build_candidates(vecs)
    allnames = list(cand)

    # deduplicate identical columns (keep first occurrence)
    M = np.array([cand[n] for n in allnames]).T
    _, first = np.unique(M, axis=1, return_index=True)
    keep = sorted(first)
    allnames = [allnames[i] for i in keep]
    F_all = np.array([cand[n] for n in allnames]).T    # 132 × K
    cons = CONS + []                                    # g -> ɡ handled below
    cons_idx = [names.index('ɡ' if c == 'g' else c) for c in cons]
    F16 = F_all[cons_idx]                               # 16 × K

    print(f'segments {len(names)}   raw candidates {len(cand)}   '
          f'after dedup {len(allnames)}\n')

    # per-dim zero-variance on the 16-consonant subset
    var16 = F16.var(axis=0)
    zvar = [allnames[i] for i in range(F16.shape[1]) if var16[i] < 1e-12]
    print('zero-variance on the 16-consonant subset (no signal there):')
    print('  ' + ', '.join(zvar) + '\n')

    # ---- baseline: v8's 16 base dims ----
    base_idx = [allnames.index(d) for d in BASE_DIMS]
    print('--- baseline ---')
    s0 = summarize('v8 base 16 dims', F16, F_all, counts, names, base_idx)

    # ---- marginal: each candidate alone ----
    print('\n--- marginal value (each dim alone, fitted) ---')
    marg = []
    for i, n in enumerate(allnames):
        s = summarize(f'alone: {n}', F16, F_all, counts, names, [i])
        marg.append((n, s['loco'], s['train']))
    marg.sort(key=lambda t: t[1])
    print('\nbest marginal LOCO:')
    for n, lo, tr in marg[:15]:
        print(f'  {n:<24} LOCO {lo:>9,.0f}  train {tr:>9,.0f}')
    print('worst marginal LOCO:')
    for n, lo, tr in marg[-8:]:
        print(f'  {n:<24} LOCO {lo:>9,.0f}  train {tr:>9,.0f}')

    # ---- greedy forward selection (train NLL), LOCO tracked ----
    # Fast step: fix the weights of already-selected dims, optimise only the
    # candidate's weight + the 4 condition scales; full refit every 4 steps.
    print('\n--- greedy forward selection ---')
    print(f'{"step":<5}{"added":<26}{"LOCO":>10}{"train":>10}{"minNN":>8}{"coll":>6}{"CV":>7}')
    selected = []
    rest = list(range(len(allnames)))
    w = np.ones(F16.shape[1])          # running weights (reused across steps)
    loga = np.zeros(counts.shape[0])
    best = None

    def nll_of(w, loga):
        return nll_weights(counts, distance_matrix(F16, w), loga)

    for step in range(1, 21):
        cand_scores = []
        for i in rest:
            trial = sorted(selected + [i])
            fixed_idx = [j for j in trial if j != i]
            free_sel = trial
            def obj_cand(x, i=i, fixed_idx=fixed_idx):
                u = np.zeros(F16.shape[1])
                u[fixed_idx] = np.log(np.clip(w[fixed_idx], 1e-9, None))
                u[i] = x[0]
                loga2 = x[1:]
                ww = np.exp(u)
                return nll_weights(counts, distance_matrix(F16, ww), loga2) \
                    + RHO * np.sum(u[trial] ** 2)
            x0 = np.concatenate([np.zeros(1), loga])
            r = minimize(obj_cand, x0, method='L-BFGS-B')
            cand_scores.append((r.fun, i))
        cand_scores.sort(key=lambda t: t[0])
        add = cand_scores[0][1]
        selected.append(add)
        rest.remove(add)
        if step % 4 == 0 or step == 1:
            w, a, res = fit_subset(F16, counts, selected)
            loga = np.log(a)
        else:
            w, a, res = fit_subset(F16, counts, selected, x0=None)
            loga = np.log(a)
        held = loco(F16, counts, w)
        minnn, collide, chaincv, _ = ipa_metrics(F_all, w, names)
        print(f'{step:<5}{allnames[add]:<26}{held:>10,.0f}{res.fun:>10,.0f}'
              f'{minnn:>8.3f}{collide:>6d}{chaincv:>7.2f}')
        if best is None or held < best[0]:
            best = (held, list(selected))
    print(f'\nbest LOCO set ({best[0]:,.0f}, n={len(best[1])}):\n  '
          + ', '.join(allnames[i] for i in best[1]))

    # ---- leave-one-out ablation of the best set ----
    print('\n--- leave-one-out ablation of best set ---')
    best_idx = best[1]
    for i in best_idx:
        leave = [j for j in best_idx if j != i]
        s = summarize(f'drop {allnames[i]}', F16, F_all, counts, names, leave)
        d = s['loco'] - best[0]
        print(f'     -> LOCO delta {d:+,.0f}')

    print('\n--- reference: full candidate set ---')
    summarize('all candidates', F16, F_all, counts, names,
              list(range(F16.shape[1])))


if __name__ == '__main__':
    main()
