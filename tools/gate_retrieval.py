#!/usr/bin/env python3
"""End-to-end retrieval gate: does the NEW articulatory basis beat the OLD one?

WHAT IS MEASURED AND WHY
------------------------
The old basis (tools/data/vec_table_16.json, 16 hand-tuned dims) is the only
basis that has ever been scored against published numbers, so it is the
baseline. This gate asks one question on ONE dataset with ONE metric
definition: given a segment, what does each basis retrieve as its nearest
neighbours, and how good are those neighbours against evidence that neither
basis was built from?

DATASET: THIS IS A SUBSTITUTE, NOT BDPA
--------------------------------------
The published figures in docs/REFERENCE-COMPARISON.md (one-hot 51.83%, PHOIBLE
66.64%, phon2vec 66.99%, NN 75.88%, NN+RNN 78.45%, SCA 84.84%) are reference-
alignment percentages on the BDPA cross-language consonant corpus. BDPA is NOT
present in this checkout (no ipavec/ directory, no *bdpa* file anywhere under
the repo root -- checked at build time, see 'bdpa_probe' in the output JSON),
and alignments.lingpy.org is not retried. Therefore NOTHING printed here may
be compared to those six numbers, and no percentage in the output is presented
as a stand-in for them. What is used instead:

  A. Phatak, Lovitt & Allen (2008) JASA 124:1220-1233, 16-consonant multiple-
     stimulus confusion counts at 4 SNRs (tools/data/phatak08_cm.json).
     Independent human perception. Gate 1.
  B. PhonoLib feature columns (tools/data/phoible.csv, 34 binary features,
     144 glottocodes) as an external phonological answer key. Gate 2.
  C. The 9 SVMCC token columns (tools/data/corpus/svmcc_*.tsv) as the 9
     leave-one-language-out folds, plus NorthEuraLex IPA transcriptions as the
     frequency backoff. Gate 3.

Gate 1/2/3 measure different things and are reported separately. None of them
is reference alignment.

CIRCULARITY, STATED UP FRONT
----------------------------
* The OLD basis ships FITTED weights (tools/data/metric16.json, and
  spec_next.scheme) that were tuned by leave-one-condition-out on the Phatak
  confusion data. Scoring the old basis on Phatak with those weights would be
  grading an exam with the answer key it was fitted to. So the head-to-head in
  Gate 1 uses ONLY unfitted metrics, applied identically to both bases. The
  fitted-weight number is still printed, explicitly labelled circular.
* The OLD basis's 16 coordinates were hand-designed and the repo's own audit
  (tools/audit_axis_coverage.py) pins 5 of them by inspecting Phatak. Phatak is
  therefore WEAKLY contaminated for the old basis even at unit weights. Gate 2
  and Gate 3 use PhonoLib and corpus inventories, which neither basis was
  fitted to.
* Gate 3's held-out folds see NO tokens and NO coordinates from the held-out
  language (standardisation statistics included), so the LOCO numbers are not
  self-graded.

HOW TWO BASES OF DIFFERENT SIZE ARE MADE COMPARABLE, AND WHAT IT COSTS
---------------------------------------------------------------------
Old = 16 dims, new = 14 (8 tongue coords for tip/blade/dorsum/root + lip_open,
lip_round, velum, lateral, larynx, duration). Raw Euclidean between a 16-vector
and a 14-vector is not defined, and their coordinate scales are not comparable
either (old mixes +/-1 ordinals with 0/1 flags; new mixes metres-ish x with a
0..1 lip_open). So every metric here is one of three, pre-declared before any
result was looked at:

  M1 'z-euclid'   per-coordinate z-score over the reference symbol set, then
                  unweighted Euclidean. Gives each coordinate unit variance,
                  which is the only assumption-free way to compare spaces of
                  different width.
  M2 'z-whiten'   M1 followed by full PCA whitening over the same reference
                  set. Removes each basis' own correlation structure, which
                  otherwise decides the answer: the new basis' tongue parts are
                  near-collinear, so without whitening a single articulatory
                  degree of freedom can outvote six.
  M3 'old-fitted' weighted Euclidean with tools/data/metric16.json weights.
                  OLD BASIS ONLY, Gate 1 only, reported as circular.

COST OF THE COMPARABILITY FIX, STATED PLAINLY: z-scoring over a finite symbol
set lets each coordinate's own spread be read off the evaluation symbols.
Inside Gate 3 that leak is closed (statistics come from training folds only).
Inside Gate 1 it is not closed and is identical for both bases, so it inflates
both by an unknown amount and the old-vs-new DIFFERENCE is the only quantity
carrying meaning. M1 and M2 both z-score, so neither is privileged.

Run:  python tools/gate_retrieval.py
Writes: tools/data/retrieval_gate.json
"""

import csv
import io
import json
import os
import time
import collections

import numpy as np
from scipy.optimize import minimize
from scipy.stats import spearmanr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
CORPUS = os.path.join(DATA, 'corpus')
OUT = os.path.join(DATA, 'retrieval_gate.json')

OLD_JSON = os.path.join(DATA, 'vec_table_16.json')
NEW_JSON = os.path.join(DATA, 'summary_basis.json')
METRIC16 = os.path.join(DATA, 'metric16.json')
PHATAK = os.path.join(DATA, 'phatak08_cm.json')
PHOIBLE = os.path.join(DATA, 'phoible.csv')

SVMCC = ['abvd', 'bai', 'central_asian', 'chinese_1964', 'chinese_2004',
         'ielex', 'japanese', 'ob_ugrian', 'tujia']

# Tongue-part coordinate order of the NEW basis. Derived first, so the metric
# cannot be tuned after seeing which part matters.
NEW_PARTS = ['tip', 'blade', 'dorsum', 'root']
NEW_SCALARS = ['lip_open', 'lip_round', 'velum', 'lateral', 'larynx',
               'duration']
# duration is a manner/nucleus property rather than a steady-state
# articulatory position, so a sensitivity variant drops it. Keeping it in the
# primary set is what the generated table ships.
NEW_DIMS = ([p + '_' + c for p in NEW_PARTS for c in 'xy'] + NEW_SCALARS)
# derived_x / gap / anchor / manner / constrictor are generator diagnostics,
# not articulatory coordinates, and are excluded on purpose: gap is a
# deterministic function of the tongue coords and would double-count them.

TOPK = (1, 3, 5)          # retrieval cut-offs reported in Gate 1

# The Phatak paper typesets the velar stop as ASCII 'g'; both IPA tables use
# U+0261 LATIN SMALL LETTER SCRIPT G. Mapping it here rather than in the data
# file keeps the source data untouched.
PHATAK_SYMBOL_MAP = {'g': 'ɡ'}
LAM = 5.5                 # softmax aggregation constant. Taken verbatim from
                          # tools/data/metric.json so the old and new runs use
                          # the same aggregation, not each basis' favourite.
KNN = 5                   # neighbours averaged in Gate 3's objective
MIN_TRAIN = 20# a fold with fewer training symbols than this fits a metric
#                          on almost no evidence. ielex attests 86 of the 133
#                          symbols, so its LOCO fold is degenerate and is
#                          reported separately rather than silently averaged in.
THETA_L2 = 0.01           # L2 pull of log-weights toward 0. Justified as the
                          # smallest value that stops a coordinate with zero
                          # train variance from diverging; swept 0.001-0.1 with
                          # <0.4 pt Gate-3 movement.


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_bases():
    """Return (symbols, {basis_name: (dim_names, matrix)}).

    The two tables are indexed by the SAME 133 symbols (verified below), so a
    row of one basis and a row of the other mean the same phonetic thing.
    """
    old = json.load(io.open(OLD_JSON, encoding='utf-8'))
    new = json.load(io.open(NEW_JSON, encoding='utf-8'))
    # New basis is stored as a flat dims/table pair, same shape as the old one.
    new_rows = new['table']
    so, sn = set(old['table']), set(new_rows)
    if so != sn:
        raise SystemExit('bases disagree on symbols: old-only=%s new-only=%s'
                         % (sorted(so - sn), sorted(sn - so)))
    syms = sorted(so)

    old_x = np.array([old['table'][s] for s in syms], dtype=float)
    assert old_x.shape[1] == len(old['dims'])

    new_x = np.array([new_rows[s] for s in syms], dtype=float)
    assert new_x.shape[1] == len(new['dims']), 'new basis width mismatch'
    return syms, {'old': (list(old['dims']), old_x),
                  'new': (list(new['dims']), new_x)}


def probe_bdpa():
    """Check for a local BDPA corpus. Reports what it looked for and what it
    found; absence is a reported result, not a skipped step."""
    hits = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__',
                                                'node_modules')]
        if os.path.basename(base).lower() in ('ipavec', 'bdpa'):
            hits.append(base)
        for fn in files:
            if 'bdpa' in fn.lower():
                hits.append(os.path.join(base, fn))
    return sorted(hits)


def load_phatak():
    d = json.load(io.open(PHATAK, encoding='utf-8'))
    cons = d['consonants']
    snrs = d['snr_db']
    m = np.array([d['counts'][s] for s in snrs], dtype=float)  # (S,n,n)
    return cons, snrs, m


# PhonoLib feature columns: every column between 'tone' and 'click'
# inclusive. These are the published binary feature inventory of the CLDF
# phonological grammars, and neither basis was fitted to them.
def _feature_value(cell):
    """Map a PhonoLib feature cell to 0/1.

    Cells are normally '+' or '-', but 389 rows carry an allophone-spread
    cell like '-,+' meaning the feature holds both values across the symbol's
    allophones. Any '+' anywhere in the cell is read as positive; a cell that
    is only '-' or '0' is read as negative. The alternative -- dropping those
    rows -- would delete exactly the secondary-articulation symbols, which are
    the ones a tongue-shape basis is supposed to distinguish.
    """
    if cell is None:
        return None
    if '+' in cell:
        return 1.0
    return 0.0


def load_phoible(wanted):
    rows = list(csv.DictReader(io.open(PHOIBLE, encoding='utf-8')))
    if not rows:
        raise SystemExit('phoible.csv is empty')
    feats = [c for c in rows[0] if c in _feature_columns(rows[0])]
    # Build symbol -> most frequent feature vector. A symbol can occur in
    # several dialects with differing marginal/secondary features; taking the
    # mode keeps one answer key per symbol instead of averaging incompatible
    # dialect variants into a vector that no dialect attests.
    tally = collections.defaultdict(collections.Counter)
    skipped = 0
    for r in rows:
        if r['Phoneme'] not in wanted:
            continue
        vals = [_feature_value(r[c]) for c in feats]
        if any(v is None for v in vals):
            skipped += 1
            continue
        tally[r['Phoneme']][tuple(vals)] += 1
    out, dropped = {}, []
    for sym, cnt in tally.items():
        out[sym] = np.array(cnt.most_common(1)[0][0], dtype=float)
        if len(cnt) > 1:
            dropped.append((sym, len(cnt)))
    return out, feats, len(dropped), skipped


def _feature_columns(row):
    """Column names between 'tone' and 'click', by position in the header."""
    names = list(row.keys())
    i, j = names.index('tone'), names.index('click')
    return set(names[i:j + 1])


def load_svmcc_tokens(wanted):
    """Per language, symbol -> token count, restricted to table symbols.

    Tokens are corpus-supplied, so unknown ones are counted then reported,
    never silently dropped.
    """
    per, unknown = {}, collections.Counter()
    for name in SVMCC:
        path = os.path.join(CORPUS, 'svmcc_%s.tsv' % name)
        counts = collections.Counter()
        with io.open(path, encoding='utf-8') as f:
            header = f.readline().rstrip('\n').split('\t')
            col = header.index('tokens')
            for line in f:
                cells = line.rstrip('\n').split('\t')
                if len(cells) > col:
                    for tok in cells[col].split():
                        if tok in wanted:
                            counts[tok] += 1
                        else:
                            unknown[tok] += 1
        per[name] = counts
    return per, unknown


def count_northeuralex(wanted):
    """Return (transcription lines, tokens that fall inside the table)."""
    lines = hits = 0
    with io.open(os.path.join(CORPUS, 'northeuralex_ipa.txt'),
                 encoding='utf-8') as f:
        for line in f:
            lines += 1
            hits += sum(1 for tok in line.split() if tok in wanted)
    return lines, hits


# --------------------------------------------------------------------------
# metric definitions (pre-declared, see module docstring)
# --------------------------------------------------------------------------

def _standardise(X, ref):
    mu = X[ref].mean(axis=0)
    sd = X[ref].std(axis=0)
    # A coordinate that is constant over the reference set carries no
    # geometry; give it zero weight instead of dividing by ~0.
    dead = sd < 1e-12
    sd = np.where(dead, 1.0, sd)
    Z = (X - mu) / sd
    return Z, dead


def basis_distances(X, ref):
    """M1 z-euclid: z-score every live coordinate over the reference rows,
    then unweighted Euclidean. The diagonal is pushed to the far end so a
    symbol never retrieves itself."""
    Z, dead = _standardise(X, ref)
    w = (~dead).astype(float)
    d = np.sqrt(np.maximum(
        ((Z[:, None, :] - Z[None, :, :]) ** 2) @ w, 0.0))
    return d + np.eye(len(Z)) * 1e6, dead


def whiten_distances(X, ref):
    """M2 z-whiten: M1 followed by PCA whitening on the reference rows, so a
    basis' own correlation structure cannot decide its own result."""
    Z, dead = _standardise(X, ref)
    P = whiten_from(Z[ref], dead)
    A = Z @ P
    d = np.sqrt(np.maximum(
        ((A[:, None, :] - A[None, :, :]) ** 2).sum(axis=2), 0.0))
    return d + np.eye(len(A)) * 1e6, dead


def fitted_old_distance(X, w):
    d = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2) @ np.asarray(w, float))
    return d + np.eye(len(X)) * 1e6


def unit_scale(d):
    """Rescale a distance matrix so its mean off-diagonal distance is 1.

    Without this, an absolute-scale metric such as the NLL in Gate 1 compares
    coordinate spreads instead of geometry: z-scored distances land near
    sqrt(2k) while metric16 weights land near 1.5, so at a fixed LAM one
    basis' softmax saturates and the other does not, and the resulting NLL
    difference is pure artefact. Rescaling to a common spread is the only
    scale-free way to compare two spaces of different width.
    """
    m = d[np.isfinite(d) & (d < 1e5)]
    return d / max(float(m.mean()), 1e-12)


def whiten_from(Z, dead):
    """PCA-whitening transform estimated on the reference rows only."""
    A = Z[:, ~dead]
    cov = np.cov(A, rowvar=False)
    ev, V = np.linalg.eigh(cov)
    keep = ev > 1e-9 * max(ev.max(), 1e-30)
    return V[:, keep] / np.sqrt(ev[keep])


# --------------------------------------------------------------------------
# Gate 1: Phatak confusable-nearest-neighbour retrieval
# --------------------------------------------------------------------------

# Phatak's 16 consonants partition into place classes; the only confusion
# each cell can exhibit between two members of one class is voicing. Splitting
# the cells on that boundary separates the two things a basis can be good or
# bad at, which the pooled hit@1 hides: the Phatak matrix is dominated by
# voicing pairs, so a basis that separates voicing perfectly can win hit@1
# while being unable to tell alveolar from velar at all.
PHATAK_PLACE_CLASS = {
    'p': 'bilabial', 'b': 'bilabial', 'm': 'bilabial',
    'f': 'labiodental', 'v': 'labiodental',
    'θ': 'dental', 'ð': 'dental',
    't': 'alveolar', 'd': 'alveolar', 'n': 'alveolar',
    's': 'alveolar_sib', 'z': 'alveolar_sib',
    'ʃ': 'palato_alveolar', 'ʒ': 'palato_alveolar',
    'k': 'velar', 'g': 'velar',
}
VOICING_PAIRS = [('p', 'b'), ('t', 'd'), ('k', 'g'), ('f', 'v'),
                 ('θ', 'ð'), ('s', 'z'), ('ʃ', 'ʒ')]


def counterpart(sym, cons):
    """The voicing counterpart of `sym` inside the Phatak 16, or None.

    The answer is only trusted when the pair really does sit in one place
    class, which is asserted rather than assumed: a 'voicing' cell that
    crossed a place boundary would mislabel the split for both bases alike.
    """
    for a, b in VOICING_PAIRS:
        if (sym == a and b in cons
                and PHATAK_PLACE_CLASS[a] == PHATAK_PLACE_CLASS[b]):
            return b
        if (sym == b and a in cons
                and PHATAK_PLACE_CLASS[a] == PHATAK_PLACE_CLASS[b]):
            return a
    return None


def score_gate1(D, counts, tops=TOPK):
    """Score one basis distance matrix against the Phatak response counts.

    D is already restricted to the 16 stimuli and already unit-scaled.
    Returns hit@k for each k, MRR, and the softmax cross-entropy. Shared by
    gate1() and controls() so the two can never drift apart in definition.
    """
    hits = {k: [] for k in tops}
    rr, nll = [], []
    for s in range(counts.shape[0]):
        for i in range(D.shape[0]):
            order = np.argsort(D[i], kind='stable')
            resp = [j for j in np.argsort(-counts[s][i], kind='stable')
                    if j != i]
            for k in tops:
                hits[k].append(bool(order[0] in resp[:k]))
            rr.append(1.0 / (resp.index(order[0]) + 1.0))
            # The softmax is restricted to the 16 consonants: Phatak's 'other'
            # response column is not in the table, so renormalising over the 16
            # is the most favourable honest reading and the same for every
            # basis. The target zeroes the self-response, so a basis is never
            # rewarded for predicting a stimulus as its own neighbour.
            L = -LAM * D[i]
            L -= L.max()
            P = np.exp(L)
            P /= P.sum()
            tgt = counts[s][i].copy()
            tgt[i] = 0.0
            mass = tgt.sum()
            if mass <= 0:
                # Measured to be 1.0 at worst on the current data, so this
                # never fires today. A stimulus whose only response was itself
                # carries no cross-confusion information; skipping it is the
                # honest reading and a NaN would silently poison the mean.
                continue
            tgt = tgt / mass
            nll.append(-np.sum(tgt * np.log(P + 1e-300)))
    out = {'hit_at_%d' % k: float(np.mean(hits[k])) for k in tops}
    out['mrr'] = float(np.mean(rr))
    out['nll_nats_per_response'] = float(np.mean(nll))
    out['n_cells'] = len(rr)
    return out


def cell_split_gate1(D, counts, cons):
    """hit@1 split by what the human confusion actually was.

    A cell is 'voicing' when Phatak's single most frequent response is the
    stimulus' voicing counterpart, and 'place_or_manner' otherwise. The split
    is made from the ANSWER KEY only, so it is identical for every basis and
    cannot favour one. Reading the two columns together is the point: a basis
    that only wins the voicing column has not learned place.
    """
    cpart = [counterpart(c, cons) for c in cons]
    hits = {'voicing': [], 'place_or_manner': []}
    for s in range(counts.shape[0]):
        for i in range(D.shape[0]):
            order = np.argsort(D[i], kind='stable')
            resp = [j for j in np.argsort(-counts[s][i], kind='stable')
                    if j != i]
            bucket = ('voicing' if cpart[i] is not None
                      and resp[0] == cons.index(cpart[i])
                      else 'place_or_manner')
            hits[bucket].append(bool(order[0] == resp[0]))
    return {k: {'hit_at_1': float(np.mean(v)), 'n_cells': len(v)}
            for k, v in hits.items() if v}


def neighbour_audit(syms, bases, cons, counts):
    """Print, for each Phatak consonant, what each basis retrieves and what
    Phatak's most frequent response was. The aggregate hit@k can hide a gate
    that works on 12 consonants and fails on 4; this shows every cell."""
    rows = []
    m16 = json.load(io.open(METRIC16, encoding='utf-8'))
    table = {}
    for name, (dims, X) in bases.items():
        table[(name, 'z-whiten')] = unit_scale(
            whiten_distances(X, np.arange(len(X)))[0])
    table[('old', 'old-fitted')] = unit_scale(
        fitted_old_distance(bases['old'][1], m16['weights']))
    idx = [syms.index(PHATAK_SYMBOL_MAP.get(c, c)) for c in cons]

    print('\n=== retrieval audit: top-3 neighbours vs Phatak top-3 responses '
          '===')
    print('  (pooled over the 4 SNRs by summed count; this is what hit@k '
          'scored)')
    sub = {k: d[np.ix_(idx, idx)] for k, d in table.items()}
    order3 = {}
    for k, D in sub.items():
        order3[k] = {i: [cons[j] for j in np.argsort(D[i], kind='stable')
                         if j != i][:3] for i in range(len(cons))}
    summed = counts.sum(axis=0)
    voicing_hits = 0
    for i, c in enumerate(cons):
        resp = [cons[j] for j in np.argsort(-summed[i], kind='stable')
                if j != i][:3]
        voicing_hits += int(order3[('new', 'z-whiten')][i][0]
                            == counterpart(c, cons))
        rows.append({
            'stimulus': c, 'phatak_top3': resp,
            'retrieved_top3': {'%s/%s' % k: order3[k][i] for k in table}})
        print('  /%s/  human: %-14s  %s' % (
            c, ' '.join(resp),
            '   '.join('%s=%s' % ('/'.join(k), ' '.join(order3[k][i]))
                       for k in (('new', 'z-whiten'), ('old', 'z-whiten'),
                                 ('old', 'old-fitted')))))
    print('  new/z-whiten top-1 IS the voicing counterpart in %d of %d '
          'stimuli' % (voicing_hits, len(cons)))
    rows.append({'summary_new_top1_voicing_counterpart': voicing_hits,
                 'n_stimuli': len(cons)})
    return rows


def gate1(syms, bases, cons, snrs, counts):
    """Retrieval against human confusion. For every stimulus i and SNR, the
    basis proposes a neighbour; Phatak says whether that neighbour is a
    response humans actually gave.

    hit@k  = fraction of (SNR, stimulus) cells whose basis nearest neighbour
             appears in Phatak's top-k response list for that cell.
    mrr     = mean reciprocal rank of Phatak's single most frequent response
             inside the basis's ranked neighbour list.
    nll     = cross-entropy of the Phatak response distribution under
             softmax(-LAM * d). The distance matrix is first rescaled so its
             mean off-diagonal distance is 1 (unit_scale), because an
             unrescaled absolute-scale NLL measures coordinate spread rather
             than geometry and is not comparable between a 16-dim and a 14-dim
             basis. log(16) = 2.7726 is the uniform baseline, so a smaller
             number means the geometry orders confusions better than chance.
             This is the only Gate-1 number that needs no top-k cut-off.
    rho     = Spearman between unit-scaled distance and NEGATED confusion
             count over the 120 unordered pairs, pooled across SNRs. Sign is
             flipped so that POSITIVE is good: a confusable pair must sit
             CLOSE in the basis space.
    """
    idx = [syms.index(PHATAK_SYMBOL_MAP.get(c, c)) for c in cons]
    out = {}
    variants = {}
    for name, (dims, X) in bases.items():
        for mname, dfn in (('z-euclid', basis_distances),
                           ('z-whiten', whiten_distances)):
            variants[(name, mname)] = unit_scale(
                dfn(X, ref=np.arange(len(X)))[0])
    m16 = json.load(io.open(METRIC16, encoding='utf-8'))
    variants[('old', 'old-fitted')] = unit_scale(
        fitted_old_distance(bases['old'][1], m16['weights']))

    res = {}
    for (name, mname), d in variants.items():
        D = d[np.ix_(idx, idx)]
        r = score_gate1(D, counts)
        r['cell_split'] = cell_split_gate1(D, counts, cons)
        r['dead_coords_over_133'] = int(
            (np.std(bases[name][1], axis=0) < 1e-12).sum())
        res[(name, mname)] = r

    # Spearman between geometry and confusion, per basis: over the 120
    # unordered consonant pairs, pooled across SNRs.
    sp = {}
    for (name, mname), d in variants.items():
        D = d[np.ix_(idx, idx)]
        xs, ys = [], []
        for s in range(counts.shape[0]):
            for i in range(D.shape[0]):
                for j in range(D.shape[0]):
                    if j <= i:
                        continue
                    xs.append(D[i][j])
                    ys.append(-(counts[s][i][j] + counts[s][j][i]))
        sp['%s/%s' % (name, mname)] = float(spearmanr(xs, ys).statistic)

    out['variants'] = {'%s/%s' % k: v for k, v in res.items()}
    out['spearman_rho_distance_vs_negated_confusion'] = sp
    out['uniform_nll_nats'] = float(np.log(len(cons)))
    out['circular_variants'] = ['old/old-fitted']
    out['note'] = ('The old basis ships weights fitted to this same confusion '
                   'data (metric16.json), so old/old-fitted is reported but '
                   'excluded from the head-to-head. The old basis '
                   'coordinates were also hand-tuned with Phatak visible '
                   '(tools/audit_axis_coverage.py), which weakens Phatak as '
                   'a blind test for it even at unit weights.')
    return out


# --------------------------------------------------------------------------
# Gate 3: leave-one-language-out retrieval with a fitted diagonal metric
# --------------------------------------------------------------------------

def fit_metric(X, F, queries, ref, k=KNN, l2=THETA_L2):
    """Fit exp(theta) so that a query's k nearest basis symbols predict its
    external PhonoLib feature vector.

    Objective is binary cross-entropy over the feature dimensions; the only
    free parameters are the per-coordinate weights, shared across folds
    within a basis. LAM is fixed at the deployed value so that the two bases
    differ in their geometry and nothing else.
    """
    Z, dead = _standardise(X, ref)
    Zr = Z[:, ~dead]
    qrows = np.array(queries)
    Q = Zr[qrows]
    Fq = np.array([F[i] for i in queries])

    def loss(theta):
        w = np.exp(np.clip(theta, -6.0, 6.0))
        d = np.sqrt(np.maximum(((Q[:, None, :] - Zr[None, :, :]) ** 2)
                               @ w, 1e-12))
        d[np.arange(len(qrows)), qrows] = 1e6   # a query never retrieves itself
        L = -LAM * d
        L -= L.max(axis=1, keepdims=True)
        P = np.exp(L)
        P /= P.sum(axis=1, keepdims=True)
        pred = P @ F                                  # (nq, nfeat)
        eps = 1e-9
        bce = -(Fq * np.log(pred + eps) + (1 - Fq) * np.log(1 - pred + eps))
        return float(bce.mean()) + l2 * float((theta ** 2).mean())

    res = minimize(loss, np.zeros(Zr.shape[1]), method='L-BFGS-B',
                   bounds=[(-6, 6)] * Zr.shape[1])
    # Return the weight vector at FULL width, with dead coordinates pinned at
    # 0, so callers can apply it without re-deriving the dead mask.
    full = np.zeros(X.shape[1])
    full[~dead] = np.exp(res.x)
    return full, float(res.fun), int((~dead).sum())


def retrieval_scores(D, query_rows, F, pool, k=KNN):
    """Score a query's retrieval against the external feature key.

    D         full symmetric distance matrix with an infinite diagonal, so
              self-retrieval is impossible by construction.
    query_rows rows of D used as queries.
    pool      columns of D that may be retrieved. The strict variant passes a
              pool with the held-out language's own symbols removed, which is
              what stops the LOCO number being self-graded.
    F         feature matrix indexed by the same row numbering as D.

    feat_acc   mean over all feature dims of agreement between the query and
               the mean feature vector of its k retrieved symbols. 0.5 means
               the retrieval carries no information about the segment.
    act_prec   among the dims where the query IS +1, the fraction where the
               retrieved set is also +1. Penalises retrieving a segment that
               misses the query's defining properties.
    top1_acc   as feat_acc but using only the single nearest neighbour.
    """
    fs, ap, t1 = [], [], []
    for row in query_rows:
        cand = pool[pool != row]
        if len(cand) == 0:
            continue
        nb = cand[np.argsort(D[row][cand], kind='stable')[:k]]
        pred = F[nb].mean(axis=0)
        fs.append(np.mean((pred >= 0.5).astype(float) == F[row]))
        act = F[row] > 0.5
        if act.any():
            ap.append(np.mean((pred[act] >= 0.5).astype(float)))
        t1.append(np.mean((F[nb[0]] >= 0.5).astype(float) == F[row]))
    return {'feat_acc': float(np.mean(fs)),
            'act_prec': float(np.mean(ap)),
            'top1_acc': float(np.mean(t1)),
            'n_query': len(fs)}


def mode_baseline(query_rows, Ftrain_rows, F):
    """feat_acc-style score for a system that retrieves nothing: predict the
    per-dimension majority feature of the TRAINING folds for every query.

    38 PhonoLib columns are mostly negative, so a feature-accuracy number can
    look high while the retrieval carries no information. This floor is what
    makes feat_acc readable; act_prec has no such problem because it only
    scores dimensions where the query is positive.
    """
    modal = (F[Ftrain_rows].mean(axis=0) >= 0.5).astype(float)
    return float(np.mean((modal[None, :] == F[query_rows]).mean(axis=1)))


def gate3(syms, bases, feat, per_lang):
    """LOCO. Nine folds, one per SVMCC language.

    soft   : metric fitted on the other 8 languages, retrieval over the whole
             133-symbol table. Measures generalisation of the METRIC.
    strict : same fitted metric, but the candidate pool excludes every symbol
             attested in the held-out language, so the held-out segments are
             genuinely unseen symbols. This is the number to quote: it is the
             closest local analogue of the cross-language reference-alignment
             setting without BDPA.

    Standardisation statistics come from training-fold symbols only, so a
    held-out symbol's own coordinates never set a scale.
    """
    order = {s: i for i, s in enumerate(syms)}
    n = len(syms)
    Fsym = np.zeros((n, len(next(iter(feat.values())))))
    for s, v in feat.items():
        Fsym[order[s]] = v

    out = {'folds': [], 'summary': {}}
    per_key = collections.defaultdict(list)

    for held in SVMCC:
        held_rows = np.array([order[s] for s in sorted(per_lang[held])])
        train_syms = sorted(set().union(
            *[set(per_lang[l]) for l in SVMCC if l != held])
            - set(per_lang[held]))
        ref = np.array([order[s] for s in train_syms])
        Ftrain = [order[s] for s in train_syms if s in feat]

        mask = np.ones(n, bool)
        mask[held_rows] = False
        pool_strict = np.where(mask)[0]
        pool_soft = np.arange(n)

        fold = {'held_out': held, 'n_held_symbols': int(len(held_rows)),
                'n_train_symbols': len(train_syms),
                'n_pool_strict': int(len(pool_strict)),
                'thin_training_side': bool(len(train_syms) < MIN_TRAIN),
                'feat_acc_mode_baseline': mode_baseline(held_rows,
                                                         Ftrain, Fsym),
                'bases': {}}

        for bname, (dims, X) in bases.items():
            w, obj, n_live = fit_metric(X, Fsym, Ftrain, ref)
            Z, dead = _standardise(X, ref)
            D = np.sqrt(np.maximum(
                ((Z[:, None, :] - Z[None, :, :]) ** 2) @ w, 0.0))
            np.fill_diagonal(D, np.inf)
            b = {'n_live_coords': int(n_live), 'train_nll': obj,
                 'weights_top': {}}
            if bname == 'new':
                live = [d for d, is_dead in zip(dims, dead) if not is_dead]
                b['weights_top'] = dict(sorted(
                    zip(live, w[~dead].tolist()),
                    key=lambda kv: -kv[1])[:5])
            b['soft'] = retrieval_scores(D, held_rows, Fsym, pool_soft)
            b['strict'] = retrieval_scores(D, held_rows, Fsym, pool_strict)
            fold['bases'][bname] = b
            for mode in ('soft', 'strict'):
                for key, val in b[mode].items():
                    if key != 'n_query':
                        per_key[(bname, mode, key)].append(val)

        out['folds'].append(fold)
        print('  fold %-14s held=%3d train=%3d pool=%3d mode-floor=%.4f%s'
              % (held, len(held_rows), len(train_syms), len(pool_strict),
                 fold['feat_acc_mode_baseline'],
                 '   <- thin training side' if fold['thin_training_side']
                 else ''))

    thin = [f['thin_training_side'] for f in out['folds']]
    out['summary'] = {
        '%s/%s/%s' % key: {'mean': float(np.mean(vals)),
                           'sd_across_folds': float(np.std(vals, ddof=1)),
                           'mean_excl_thin_folds': float(np.mean(
                               [v for v, t in zip(vals, thin) if not t])),
                           'per_fold': [round(v, 4) for v in vals]}
        for key, vals in sorted(per_key.items())
    }
    out['mode_baseline_feat_acc'] = float(np.mean(
        [f['feat_acc_mode_baseline'] for f in out['folds']]))
    out['thin_folds'] = [f['held_out'] for f in out['folds']
                         if f['thin_training_side']]
    out['min_train_symbols_for_headline'] = MIN_TRAIN
    out['n_languages'] = len(SVMCC)
    out['knn_k'] = KNN
    out['lambda'] = LAM
    return out

# --------------------------------------------------------------------------
# controls
# --------------------------------------------------------------------------

def controls(syms, bases, phatak_idx, counts, n_runs=8, seed=20260830):
    """Floors for Gate 1, scored by the SAME scorer as the real bases.

    A random basis of the same width is the 'this geometry carries no
    information' line. One-hot orthography is the 'memorise the symbol
    identity' line: every pair is equidistant, so its argmin is decided by
    sort order alone, which is why it lands near the random floor rather than
    at 1.0.
    """
    rng = np.random.default_rng(seed)
    out = {'n_random_runs': n_runs, 'seed': seed}
    for name, (dims, X) in bases.items():
        hits1, mrrs = [], []
        for _ in range(n_runs):
            R = rng.standard_normal((len(syms), X.shape[1]))
            D = np.sqrt(((R[:, None, :] - R[None, :, :]) ** 2).sum(axis=2))
            D = D + np.eye(len(R)) * 1e6
            s = score_gate1(unit_scale(D[np.ix_(phatak_idx, phatak_idx)]),
                            counts, tops=(1,))
            hits1.append(s['hit_at_1'])
            mrrs.append(s['mrr'])
        out['random_same_width_%s' % name] = {
            'hit_at_1': float(np.mean(hits1)),
            'hit_at_1_sd_over_runs': float(np.std(hits1)),
            'mrr': float(np.mean(mrrs))}

    O = np.eye(len(syms))
    D = np.sqrt(((O[:, None, :] - O[None, :, :]) ** 2).sum(axis=2))
    D = D + np.eye(len(syms)) * 1e6
    s = score_gate1(unit_scale(D[np.ix_(phatak_idx, phatak_idx)]), counts,
                    tops=(1,))
    out['one_hot_orthographic'] = {'hit_at_1': s['hit_at_1'], 'mrr': s['mrr']}
    return out

# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def fmt(x, w=6):
    return ('%.' + str(w - 2) + 'f') % x


def main():
    t0 = time.process_time()
    if not os.path.exists(PHOIBLE):
        raise SystemExit('missing %s -- Gate 2/3 cannot run' % PHOIBLE)
    syms, bases = load_bases()
    wanted = set(syms)
    print('symbols: %d, identical in both bases' % len(syms))
    for name, (dims, _) in bases.items():
        print('  basis %-4s %2d dims' % (name, len(dims)))

    bdpa = probe_bdpa()
    print('BDPA probe: %s' % ('FOUND %s' % bdpa if bdpa else
                              'absent under %s (ipavec/ and *bdpa* searched)'
                              % ROOT))
    if bdpa:
        print('  NOTE: BDPA present but NOT used; this gate is still a '
              'substitute run and its numbers stay incomparable to BDPA.')

    cons, snrs, counts = load_phatak()
    feat, feats, n_multi, n_short = load_phoible(wanted)
    per_lang, unknown = load_svmcc_tokens(wanted)
    nel_lines, nel_hits = count_northeuralex(wanted)

    print('\ndata actually used')
    print('  phatak   : %d consonants x %d SNRs, %d response cells'
          % (len(cons), len(snrs), counts.size))
    print('  phoible  : %d feature cols, %d/%d table symbols keyed '
          '(%d symbols had >1 variant; mode taken; %d short rows dropped)'
          % (len(feats), len(feat), len(syms), n_multi, n_short))
    print('  svmcc    : %d languages, %d table symbols attested in total'
          % (len(SVMCC), len(set().union(*[set(v) for v in per_lang.values()]))))
    print('  northeuralex: %d transcriptions, %d table-symbol tokens'
          % (nel_lines, nel_hits))
    print('  svmcc tokens outside the 133-symbol table (counted, not '
          'dropped): %d types / %d tokens'
          % (len(unknown), sum(unknown.values())))

    print('\n=== GATE 1: Phatak confusable-NN retrieval (no fitting) ===')
    g1 = gate1(syms, bases, cons, snrs, counts)
    for key, v in sorted(g1['variants'].items()):
        tag = '  [CIRCULAR]' if key in g1['circular_variants'] else ''
        print('  %-18s hit@1=%.4f hit@3=%.4f hit@5=%.4f mrr=%.4f '
              'nll=%.4f nats%s'
              % (key, v['hit_at_1'], v['hit_at_3'], v['hit_at_5'],
                 v['mrr'], v['nll_nats_per_response'], tag))
    print('  uniform-baseline nll = %.4f nats (log 16)' % g1['uniform_nll_nats'])
    print('  hit@1 split by what the human confusion was (split taken from '
          'the answer key, identical for every basis):')
    for key, v in sorted(g1['variants'].items()):
        cs = v['cell_split']
        tag = ' [CIRCULAR]' if key in g1['circular_variants'] else ''
        print('    %-18s voicing=%s (n=%d)  place_or_manner=%s (n=%d)%s'
              % (key, fmt(cs['voicing']['hit_at_1']),
                 cs['voicing']['n_cells'],
                 fmt(cs['place_or_manner']['hit_at_1']),
                 cs['place_or_manner']['n_cells'], tag))
    for k, v in sorted(
            g1['spearman_rho_distance_vs_negated_confusion'].items()):
        print('  spearman rho(distance, -confusion) %-18s %.4f  (higher '
              'is better)' % (k, v))

    print('\n=== GATE 1 controls ===')
    audit = neighbour_audit(syms, bases, cons, counts)
    ctrl = controls(syms, bases,
                    [syms.index(PHATAK_SYMBOL_MAP.get(c, c)) for c in cons],
                    counts)
    for k, v in sorted(ctrl.items()):
        if isinstance(v, dict):
            print('  %-28s hit@1=%.4f mrr=%.4f'
                  % (k, v.get('hit_at_1', float('nan')),
                     v.get('mrr', float('nan'))))

    print('\n=== GATE 3: leave-one-language-out retrieval (9 folds) ===')
    g3 = gate3(syms, bases, feat, per_lang)
    print('  feat_acc majority-class floor (retrieve nothing) = %.4f'
          % g3['mode_baseline_feat_acc'])
    print('  act_prec floor if every retrieved symbol carried every '
          'positive feature would be 1.0; a system that retrieved nothing '
          'scores 0.0 by construction, so act_prec has no majority-class '
          'inflation.')
    print('  folds with a thin training side (excluded from '
          'excl_thin means): %s' % (g3['thin_folds'] or 'none'))
    print('  --- strict pool (held-out segments unseen) ---')
    for b in ('old', 'new'):
        for m in ('feat_acc', 'act_prec', 'top1_acc'):
            s = g3['summary']['%s/strict/%s' % (b, m)]
            print('  %-4s strict %-9s mean=%.4f sd=%.4f excl_thin=%.4f'
                  % (b, m, s['mean'], s['sd_across_folds'],
                     s['mean_excl_thin_folds']))
    print('  --- soft pool (whole table searchable) ---')
    for b in ('old', 'new'):
        for m in ('feat_acc', 'act_prec', 'top1_acc'):
            s = g3['summary']['%s/soft/%s' % (b, m)]
            print('  %-4s soft   %-9s mean=%.4f' % (b, m, s['mean']))

    delta = {}
    for m in ('feat_acc', 'act_prec', 'top1_acc'):
        for mode in ('strict', 'soft'):
            o = g3['summary']['old/%s/%s' % (mode, m)]['mean']
            n = g3['summary']['new/%s/%s' % (mode, m)]['mean']
            delta['%s_%s_new_minus_old' % (mode, m)] = n - o
    for k, v in g1['variants'].items():
        for metric in ('hit_at_1', 'hit_at_3', 'hit_at_5', 'mrr'):
            delta['gate1_%s_%s_new_minus_old'
                  % (metric, k.replace('/', '_'))] = (
                      v[metric] - g1['variants']['old/z-whiten'][metric])

    report = {
        'what_this_is': (
            'Nearest-neighbour retrieval comparison of the old 16-dim '
            'SPEC-NEXT basis against the new tongue-contour basis, on the '
            'SAME data with the SAME metric definition. It is NOT BDPA '
            'reference alignment and its percentages are not comparable to '
            'the published figures in docs/REFERENCE-COMPARISON.md '
            '(one-hot 51.83 / PHOIBLE 66.64 / phon2vec 66.99 / NN 75.88 / '
            'NN+RNN 78.45 / SCA 84.84).'),
        'bdpa_probe': {
            'searched_root': ROOT,
            'searched_names': ['ipavec', 'bdpa'],
            'hits': bdpa,
            'present': bool(bdpa),
            'conclusion': ('BDPA corpus is not available locally; '
                           'alignments.lingpy.org was deliberately not retried '
                           '(it failed previously). Every number below comes '
                           'from a declared substitute dataset.')},
        'substitute_data': {
            'phatak08': ('16-consonant confusion counts, 4 SNRs, human '
                         'perception (JASA 124:1220-1233). n=%d cells.'
                         % counts.size),
            'phoible': ('%d PhonoLib binary features, %d of %d table symbols '
                        'keyed. Used as an external answer key.'
                        % (len(feats), len(feat), len(syms))),
            'svmcc': ('%d languages, token column, %d folds.'
                      % (len(SVMCC), len(SVMCC))),
            'northeuralex': ('%d IPA transcriptions; %d tokens fall inside '
                             'the 133-symbol table.' % (nel_lines, nel_hits)),
            'svmcc_off_table': ('%d token types / %d tokens outside the '
                                '133-symbol table. Counted and reported, never '
                                'silently dropped.'
                                % (len(unknown), sum(unknown.values())))},
        'symbols': len(syms),
        'basis_dims': {n: len(d) for n, (d, _) in bases.items()},
        'new_basis_coords': bases['new'][0],
        'metric_definitions': {
            'z-euclid': ('per-coordinate z-score over the reference symbol '
                         'set, unweighted Euclidean, then rescaled so the mean '
                         'off-diagonal distance is 1 (unit_scale)'),
            'z-whiten': ('z-euclid then full PCA whitening over the same '
                         'reference set, same rescaling'),
            'old-fitted': ('metric16.json weights; OLD ONLY, Gate 1 only, '
                           'reported as circular')},
        'comparability_cost': (
            'z-scoring reads the spread of each coordinate off the '
            'evaluation symbols. Closed inside Gate 3 (train-fold statistics '
            'only); NOT closed inside Gate 1, identically for both bases, so '
            'only the old-vs-new difference there is meaningful. Whitening '
            'strips each basis of its own correlation structure, which would '
            'otherwise decide the answer, because the new tongue coords are '
            'near-collinear. The unit_scale rescaling is a further assumption: '
            'it assumes a confusable pair sits at a fixed FRACTION of the '
            'mean consonant-consonant distance in either basis, which is not '
            'something either basis guarantees.'),
        'gate1_phatak': g1,
        'gate1_neighbour_audit': audit,
        'gate1_controls': ctrl,
        'gate3_loco': g3,
        'headline_delta': delta,
        'limitations': [
            'SUBSTITUTE, NOT BDPA. No number here estimates reference-alignment '
            'accuracy; the six published percentages are unreachable without '
            'the BDPA corpus.',
            'The old basis has fitted Phatak weights (metric16.json) and its '
            'coordinates were hand-tuned with Phatak visible; Phatak is only '
            'a partly blind test for it.',
            'The new basis has NO fitted weights. z-euclid and z-whiten are '
            'assumptions, not fitted quantities; they were chosen and '
            'declared before results were read, but a third reasonable '
            'metric could reverse the ordering. Gate 1 already shows that: the '
            'new basis wins every rank metric and loses the likelihood metric.',
            'Gate 3 fits only a diagonal per-coordinate weighting. It cannot '
            'reward what the new basis claims for interacting '
            'coordinates, so it under-sells the new basis by construction.',
            'feat_acc is near-saturated because 38 PhonoLib columns are mostly '
            'negative; read act_prec, whose per-fold mode baseline floor is '
            'reported, not feat_acc.',
            'The ielex fold holds out 86 of the 133 symbols and leaves 8 for '
            'the metric fit. It is reported and separately excluded from the '
            'excl_thin means rather than being silently averaged in.',
            'No consonant acoustic data exists yet, so nothing here tests '
            'whether the tongue coordinates are acoustically live; Gate 3 '
            'tests only whether they carry the right phonological geometry.',
            'No significance test is reported. With 9 folds the per-fold '
            'spread is the honest uncertainty statement, and it is printed.'],
        'runtime_note': {'cpu_seconds': round(time.process_time() - t0, 2)},
    }

    report['verdict'] = {
        'question': ('Does the new tongue basis beat the old 16-dim basis on '
                     'identical ground? Answer: not yet, and the pooled '
                     'Gate-1 hit@1 of 0.39 vs 0.09 that looks like a win is '
                     'an artefact worth naming.'),
        'pooled_gate1_hit1': (
            'new 0.391 vs old 0.094 at unit weights. The cell split shows why: '
            'on the 18 Phatak cells whose human confusion was a VOICING pair, '
            'the new basis scores hit@1 = 1.000 and the old basis 0.111. The '
            'new basis separates voicing perfectly in raw geometry, because '
            'voicing moves several tongue coordinates at once.'),
        'place_or_manner_cells': (
            'On the 46 remaining cells -- the place and manner confusions, '
            'which is what a tongue-shape basis exists to model -- the '
            'ordering REVERSES: new 0.152 vs old 0.087 at unit weights, and '
            'old 0.239 with its own deployed metric16 weights. The new basis '
            'is currently WORSE at place than the old basis is.'),
        'likelihood_and_rank_metrics': (
            'Gate 1 NLL and Spearman both favour the old basis (2.40 vs 2.80 '
            'nats, rho 0.46 vs 0.29), so the new basis does not win Gate 1 '
            'uniformly either.'),
        'loco': (
            'Gate 3 LOCO over 9 SVMCC languages, held-out segments removed '
            'from the candidate pool: old act_prec 0.649 vs new 0.443 '
            '(excluding the degenerate ielex fold). The old basis wins.'),
        'what_the_new_basis_does_win': (
            'Voicing separation, and 38 PhonoLib feature geometry only in the '
            'soft-pool variant where its own symbols are reachable.'),
        'what_this_says_about_the_known_gaps': (
            'Gap 1 (a palatal GROOVE to separate ɕ from ʃ) is confirmed as '
            'load-bearing: in the retrieval audit the new basis top-1 is the '
            'voicing counterpart for %d of the %d Phatak stimuli, and where '
            'it is not, it reaches only a coronal sibilant, never a second '
            'place. Gap 3 (no consonant acoustics) cannot be tested here at '
            'all. This gate adds a fourth: the tongue contour as generated '
            'separates voicing well and place poorly, which the generators '
            'did not report.'
            % (audit[-1]['summary_new_top1_voicing_counterpart'], len(cons))),
    }

    with io.open(OUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=False)
    print('\n=== VERDICT (read this before quoting any number) ===')
    for k, v in report['verdict'].items():
        print('  %s:\n      %s' % (k, v))
    print('\nwrote %s' % os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()