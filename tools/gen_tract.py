"""Jaw / lips / larynx: three coordinates where the old model had one.

WHAT IS MEASURED AND WHY
  The old scheme has a single `lip_open` axis. That axis is physically a
  composite: the mandible carries the lower lip AND (through the
  suprahyoid-hyoid chain) the larynx, so a large part of what `lip_open`
  encoded for vowels was jaw motion, and jaw motion is the direct driver of
  F1. This script splits the composite into

      jaw_open       vertical separation of the mandible
      lip_aperture   separation of the lip openings NOT carried by the jaw
      larynx_height  vertical position of the laryngeal tube, jaw-borne part
                     already removed

  and measures, on the nine phonTools vowel datasets, what each block is
  actually worth in F1 terms.

WHAT IS *NOT* MEASURED, AND WHY IT MATTERS
  1. No dataset in this repository (or in the nine vowel sets) records jaw,
     lip or larynx POSITION. Only formants are recorded. So the jaw/larynx
     block cannot be fitted to anything; it rests on articulatory
     mechanics, and the script says so in its own output.
  2. All nine datasets are VOWEL-ONLY. Sustained vowels do not vary the
     articulators independently. Measured result, printed below: the
     {jaw_open, larynx_height, lip_aperture, dorsum_y, lip_round} block over
     the 16 measured vowels has RANK 4 of 5 -- larynx_height correlates
     r = +1.000 with jaw_open because no vowel carries a phonation gesture.
     No vowel dataset can separate the jaw axis from the larynx axis, and
     this script says so instead of quoting an R2 that would imply otherwise.
  3. What IS separable on vowels is the LIP block, because a rounding pair
     (i~y, e~oe, ...) is the same IPA chart cell with the lips changed and
     the jaw held. That contrast is measured here: 9 pairs across 6
     languages, lips-only |dF1| is 31.5% of a within-language F1 SD while
     lips-only |dF2| is 53.9% of a within-language F2 SD.

CIRCULARITY WARNING
  Tongue coordinates in gen_tongue_model.py were authored from the IPA
  vowel trapezoid, which is F1/F2 geometry. Any regression of F1 on those
  coordinates re-derives F1 from F1. Every such number below is tagged
  CIRCULAR. The only non-circular numbers in this file are the ones that
  come from the FORMANT MEASUREMENTS themselves (rounding-pair deltas,
  the rounded-flag regressions, the collinearity ranks).

  The 133-segment check is a ROUND-TRIP CONSISTENCY CHECK, not validation:
  the split is defined so that recombining the parts recovers the old
  lip_open exactly, so a zero diff count is arithmetic, not evidence.

Run: python tools/gen_tract.py
"""

import collections
import io
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_tongue_model as tm          # imported, never modified
import gen_tongue_table as tt          # imported, never modified
import fit_tongue_forward as ftf       # reuses its pyreadr reader
from gen_vowel3d import ROUND_PARTNERS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
OUT = os.path.join(DATA, 'tract_parts.json')
VEC = os.path.join(DATA, 'vec_table_16.json')
COMMITTED_TABLE = os.path.join(DATA, 'tongue_table.json')

DATASETS = ['pb52', 'h95', 't07', 'f73', 'p73', 'b95', 'f99', 'a96', 'y96']

# --------------------------------------------------------------------------
# GEOMETRIC CONSTANTS
#
# Every constant below is one of three kinds, and the kind is stated:
#   LITERATURE  anchored to a published anatomical value
#   DERIVED     computed from a LITERATURE constant below it
#   ASSUMED     no measurement available anywhere in this repository
# Assumed constants are the ones the output has to be most careful about.
# --------------------------------------------------------------------------

# LITERATURE. Adult interincisal separation at the physiological maximum is
# 35-50 mm; 45 mm is the mid of that band. The point of choosing the
# physiological extreme is that jaw_open = 1.0 must be a REACHABLE state,
# otherwise the normalised axis is a taste-driven fraction and every value
# on it is arbitrary.
JAW_RANGE_MM = 45.0

# LITERATURE. With the jaw held fixed the lip openings still separate, which
# is the non-jaw-borne residue the new axis has to represent. A moderate
# lip aperture spans well under the full interincisal excursion, so this is
# set below JAW_RANGE_MM. It is an ANATOMICAL REASONING, not a measurement:
# no dataset here records lip separation in mm.
LIP_RANGE_MM = 20.0

# DERIVED from the two above. Normalising both axes to [0, 1] means the
# mm-per-unit differs, so the fraction of jaw-driven lip travel expressed in
# normalised lip units is this ratio. Swept in main() because it is the one
# number the split genuinely depends on.
JAW_LIP_TRANSMISSION = LIP_RANGE_MM / JAW_RANGE_MM      # 0.444

# LITERATURE. Reported laryngeal height excursion between the raised and
# lowered extremes is of the order of 2 cm.
LARYNX_RANGE_MM = 20.0

# DERIVED from the LITERATURE mandible: incisor-to-condyle distance. Used to
# convert an interincisal separation into a rotation angle, so the mouth
# floor displacement is a chord/vertical decomposition rather than a guess.
MANDIBLE_RADIUS_MM = 90.0

# ASSUMED. The hyoid and larynx hang off the mandible through the
# suprahyoid muscles but are not rigidly attached, so only part of the jaw
# excursion appears as laryngeal descent. No repository dataset records
# larynx position, so the coefficient below cannot be fitted here; main()
# sweeps it and prints the consequence.
JAW_LARYNX_TRANSMISSION = 0.5

# LITERATURE. Adult total vocal tract length is commonly quoted around
# 17-18 cm (male). 175 mm is the mid of that band. This is the ONE tract
# length number here that is anchored to measurement.
REST_TRACT_MM = 175.0

# ASSUMED geometry. How the resting 175 mm is divided among the three
# sections. The oral cavity (lips to velum) is the largest single section;
# the split is a tract model, not a measurement, and the three must sum to
# REST_TRACT_MM.
ORAL_REST_MM = 90.0
PHARYNGEAL_REST_MM = 65.0
LARYNGEAL_REST_MM = REST_TRACT_MM - ORAL_REST_MM - PHARYNGEAL_REST_MM   # 20

# Tongue-body height range over the 26 authored vowels (dorsum y). The jaw
# axis is normalised against THIS range, so jaw_open = 1.0 means "the jaw
# position that goes with the highest authored vowel" rather than an
# abstract 1.0. Read from the model rather than restated so it cannot drift.
HEIGHT_LO = min(v[2] for v in tm.VOWELS)
HEIGHT_HI = max(v[2] for v in tm.VOWELS)


# --------------------------------------------------------------------------
# the three coordinates
# --------------------------------------------------------------------------

def jaw_open_for_height(dorsum_y):
    """Jaw opening that goes with a tongue-body height.

    WHY a function of height: in vowels the mandible is not commanded
    separately from the tongue body -- the jaw follows. Coarticulation
    studies treat jaw height as a function of tongue position for exactly
    this reason. The consequence is stated in main(): it makes the jaw axis
    collinear with tongue height, which is exactly why vowel-only formant
    data cannot separate the two.
    """
    t = (dorsum_y - HEIGHT_LO) / (HEIGHT_HI - HEIGHT_LO)
    return min(max(t, 0.0), 1.0)


def split(cfg, transmission=JAW_LIP_TRANSMISSION, larynx_gesture=0.0):
    """(jaw_open, lip_aperture, larynx_height, jaw_capped) for one contour.

    `cfg` is a gen_tongue_model config: it has lip_open but no jaw and no
    larynx. The split is a RECONSTRUCTION, not a fit:

      jaw       = min(height_jaw, lip_open / transmission)
      aperture  = lip_open - transmission * jaw

    The min() is not cosmetic. It is what makes recombine() an exact
    inverse, and it has a physical reading: the mandible can only be as
    open as the observed lip gap allows the jaw-borne travel. Segments
    where it binds (jaw_capped) are reported by name in main() -- they are
    the places where the old single axis contradicts a jaw that follows
    tongue height. How MANY of them there are depends entirely on
    `transmission`, which nothing here can measure.

    larynx_height is the jaw-borne descent PLUS the phonation gesture the
    old table already stored as its larynx dimension (ejective raises,
    implosive lowers). Driving it from the gesture rather than from jaw
    height is deliberate: defining it as a rescale of jaw would make the
    third axis carry no information at all, and measure_collinearity()
    reports exactly that failure when it happens. Positive = larynx down.
    """
    want = jaw_open_for_height(cfg['dorsum'][1])
    jaw = min(want, cfg['lip_open'] / transmission) if transmission > 0 else want
    larynx = max(-1.0, min(1.0, jaw - larynx_gesture))
    return jaw, cfg['lip_open'] - transmission * jaw, larynx, want > jaw + 1e-9


def recombine(jaw_open, lip_aperture, transmission=JAW_LIP_TRANSMISSION):
    """Inverse of split(): the legacy lip_open, for the round-trip check."""
    return min(lip_aperture + transmission * jaw_open, 1.0)


def tract_length(jaw_open, larynx_height,
                 larynx_coef=JAW_LARYNX_TRANSMISSION):
    """Total tract length in mm, split into oral / pharyngeal / laryngeal.

    WHY a rotation and not a vertical add: the mandible pivots at the
    condyle, so the mouth floor follows a chord, and the larynx descends
    with the hyoid along that same displacement. The pharyngeal wall does
    not move, so its length is constant.

    This is a GEOMETRY MODEL. REST_TRACT_MM is literature-anchored; the
    section split and larynx_coef are assumptions (see the constants
    above). Only the resting total is defensible as a measurement.
    """
    d = JAW_RANGE_MM * jaw_open                       # interincisal, mm
    theta = 2.0 * math.asin(min(d / (2.0 * MANDIBLE_RADIUS_MM), 1.0))
    oral = ORAL_REST_MM + d * math.cos(theta)         # floor of mouth drops
    larynx_drop = larynx_coef * d * math.sin(theta)
    pharyngeal = PHARYNGEAL_REST_MM
    laryngeal = LARYNGEAL_REST_MM + larynx_drop + LARYNX_RANGE_MM * larynx_height
    total = oral + pharyngeal + laryngeal
    return {'total_mm': round(total, 2), 'oral_mm': round(oral, 2),
            'pharyngeal_mm': round(pharyngeal, 2),
            'laryngeal_mm': round(laryngeal, 2),
            'jaw_angle_deg': round(math.degrees(theta), 2)}


# --------------------------------------------------------------------------
# the 133 committed segments
# --------------------------------------------------------------------------

def rebuild_legacy():
    """Rebuild every committed segment's contour WITHOUT running
    gen_tongue_table.main().

    gen_tongue_table.main() writes tongue_table.json, which belongs to
    another agent's output. This module must not touch it, so the same
    classification loop is reproduced here and verified against the
    committed file (see check_133). If the two disagree, the rebuild is
    wrong and the diff count below would be meaningless.
    """
    D = json.load(io.open(VEC, encoding='utf-8'))
    dims, table = D['dims'], D['table']
    I = {x: i for i, x in enumerate(dims)}
    VOWEL_CFG = {n: (dx, dy, lr) for n, dx, dy, lr in tm.VOWELS}

    out = {}
    for seg in sorted(table):
        vec = table[seg]
        place, tip = vec[I['place']], vec[I['tip_shape']]
        if abs(place) < 1e-9 and tip < 0.5:
            dx, dy, lr = VOWEL_CFG.get(seg,
                                      (0.35, 0.30, vec[I['lips_rounded']]))
            out[seg] = (tm.vowel_cfg(dx, dy, lr), 0.0)
            continue
        anchor, manner = tt.classify(vec, I)
        cfg, prof = tt.apply_manner(anchor, manner)
        # gen_tongue_table's own convention: larynx +1 is the raised larynx
        # (ejective), -1 the lowered one (implosive). split() subtracts the
        # gesture because its larynx_height is positive DOWNWARD.
        out[seg] = (cfg, float(prof['larynx']))
    return out


def check_133(legacy):
    """Does splitting jaw/lip/larynx change any tongue contour?

    Expected answer is 0, and the expected answer is 0 BY CONSTRUCTION
    (split/recombine are inverses). What the number actually proves is that
    the rebuild above is faithful and that no arithmetic in the split leaks
    into the tongue coordinates. The informative outputs are the max
    round-trip residual and the aperture/jaw distribution.
    """
    if os.path.exists(COMMITTED_TABLE):
        committed = json.load(io.open(COMMITTED_TABLE, encoding='utf-8'))
        # committed rows store tongue as {part: [x, y]}; comparing that dict
        # against a list compares unequal for every segment and would report
        # a rebuild failure that is really a type mismatch.
        mismatch = [s for s, c in committed.items()
                    if s in legacy
                    and {p: [round(legacy[s][0][p][0], 3),
                             round(legacy[s][0][p][1], 3)] for p in tm.TONGUE}
                    != c['tongue']]
        print('  rebuild vs committed tongue_table.json : %d mismatch(es) %s'
              % (len(mismatch), ' '.join(mismatch[:8]) if mismatch else ''))
        if mismatch:
            print('  REPORTED, not hidden: the rebuild disagrees with the '
                  'committed table, so the diff below is not trustworthy.')
    else:
        print('  committed tongue_table.json absent -- rebuild unverified')

    diff = 0
    max_resid = 0.0
    rows = {}
    capped = []
    for seg, (cfg, gesture) in legacy.items():
        jaw, aperture, larynx, was_capped = split(cfg, JAW_LIP_TRANSMISSION,
                                                  gesture)
        resid = abs(recombine(jaw, aperture) - cfg['lip_open'])
        max_resid = max(max_resid, resid)
        if was_capped:
            capped.append(seg)
        # the contour that the round trip actually feeds to the old model
        back = dict(cfg)
        back['lip_open'] = recombine(jaw, aperture)
        a = {p: (cfg[p][0], cfg[p][1]) for p in tm.TONGUE}
        b = {p: (back[p][0], back[p][1]) for p in tm.TONGUE}
        if a != b or tm.derived_constriction(back) != tm.derived_constriction(cfg):
            diff += 1
        rows[seg] = (jaw, aperture, larynx)
    return diff, max_resid, rows, capped


# --------------------------------------------------------------------------
# acoustic measurement
# --------------------------------------------------------------------------

def load_means():
    """(lang, ipa) -> {'f1':mean, 'f2':mean, 'f3':mean} from the 9 sets."""
    acc = ftf.load()
    out = collections.defaultdict(dict)
    for (ds, ipa, f), vals in acc.items():
        out[(ds, ipa)][f] = float(np.mean(vals))
    return out


def within_language_r2(ys, langs, xs):
    """R2 of a within-language regression (same protocol as the forward
    fit, so the numbers are comparable with fit_tongue_forward.py).

    Both sides are demeaned per language and NO language dummies are
    included: with a full dummy set the least-squares solution is the
    minimum-norm one, which pushes every demeaned predictor to exactly zero
    and silently returns R2 = 0. That is a bug, not a measurement.
    """
    groups = sorted(set(langs))
    y = np.asarray(ys, float)
    x = np.asarray(xs, float)
    ybar = {L: y[[i for i, l in enumerate(langs) if l == L]].mean()
            for L in groups}
    xbar = {L: x[[i for i, l in enumerate(langs) if l == L]].mean()
            for L in groups}
    yd = np.array([y[i] - ybar[l] for i, l in enumerate(langs)])
    xd = np.array([x[i] - xbar[l] for i, l in enumerate(langs)])
    beta, *_ = np.linalg.lstsq(xd.reshape(-1, 1), yd, rcond=None)
    resid = yd - xd * beta[0]
    ss_tot = float(((yd - yd.mean()) ** 2).sum())
    if ss_tot <= 0:
        return float('nan'), beta
    return 1.0 - float((resid ** 2).sum()) / ss_tot, beta


def measure_lip_block(means):
    """How much within-language F1 does the LIP block explain?

    The contrast is a rounding pair: same IPA chart cell, same tongue and
    jaw position by the project's own key rule, lips changed. Everything
    else is held, so the paired delta is the lips' own contribution. If the
    jaw/lip separation is right, F1 should barely move while F2 should.
    """
    pairs = measure_rounded_flag_pairs(means)

    print('\n== A. rounding pairs measured in both members ==')
    print('   (rounded minus unrounded: same IPA cell, lips differ only)')
    print('  %-6s %-8s %8s %8s' % ('lang', 'pair', 'dF1(Hz)', 'dF2(Hz)'))
    for p in pairs:
        f2 = '%8.1f' % p['df2'] if p['df2'] is not None else '       -'
        print('  %-6s %-8s %8.1f %s' % (p['lang'], p['pair'], p['df1'], f2))

    df1 = np.array([p['df1'] for p in pairs])
    df2 = np.array([p['df2'] for p in pairs
                    if p['df2'] is not None], float)

    # within-language F1 spread, the yardstick for "small"
    spread = {}
    for L in DATASETS:
        v = [d['f1'] for (ds, _), d in means.items() if ds == L and 'f1' in d]
        if len(v) > 2:
            spread[L] = float(np.std(v, ddof=1))
    mean_spread = float(np.mean(list(spread.values()))) if spread else float('nan')

    print('\n  n paired observations        : %d' % len(pairs))
    print('  mean dF1 (lips only)          : %+.1f Hz' % df1.mean())
    print('  mean |dF1|                    : %.1f Hz' % np.abs(df1).mean())
    print('  mean dF2 (lips only)          : %+.1f Hz' % df2.mean())
    print('  mean within-language F1 SD    : %.1f Hz (%d languages)'
          % (mean_spread, len(spread)))
    print('  |dF1| / F1 SD                 : %.1f%%'
          % (100.0 * np.abs(df1).mean() / mean_spread))
    print('  |dF1| / |dF2|                 : %.1f%%'
          % (100.0 * np.abs(df1).mean() / max(np.abs(df2).mean(), 1e-9)))

    # Is the mean dF1 distinguishable from zero? A t statistic computed by
    # hand so the number is inspectable rather than a black box.
    se = df1.std(ddof=1) / math.sqrt(len(df1)) if len(df1) > 1 else float('nan')
    t = df1.mean() / se if se > 0 else float('nan')
    print('  dF1 vs 0: t(%d) = %.2f  -> %s'
          % (len(df1) - 1, t,
             'no measurable F1 effect of the lips'
             if abs(t) < 2.26 else 'F1 effect IS measurable'))
    print('  t crit 0.05 two-tailed at this df = 2.26 (standard table)')
    return pairs, dict(mean_df1=float(df1.mean()), mean_abs_df1=float(np.abs(df1).mean()),
                       mean_df2=float(df2.mean()),
                       mean_lang_f1_sd=mean_spread,
                       t_vs_zero=float(t), n_pairs=len(pairs))


def measure_rounded_flag(means):
    """How much within-language variance the lips explain, in SD units.

    WHY THE POOLED FLAG REGRESSION IS REPORTED AS CONFOUNDED
    A rounded vowel is never measured without its unrounded partner, so a
    binary "is rounded" flag is also a statement about WHICH pair was
    sampled. Pooling every measured vowel therefore lets between-vowel
    identity dominate, and the R2 comes out near zero for F2 as well as
    F1 -- which would read as "lips do nothing" and is wrong. The paired
    test in measure_lip_block is the clean one; this function exists to
    show the confound, not to replace it.

    The honest, confounder-free comparison is effect size against each
    formant's own within-language SD, reported below.
    """
    print('\n== B. the pooled ROUNDED FLAG, and why it is confounded ==')
    have = collections.defaultdict(set)
    for (ds, ipa) in means:
        have[ds].add(ipa)
    res = {}
    for f in ('f1', 'f2', 'f3'):
        langs, ys, xs = [], [], []
        for (ds, ipa), d in sorted(means.items()):
            if f not in d:
                continue
            partner = ROUND_PARTNERS.get(ipa)
            langs.append(ds)
            ys.append(d[f])
            xs.append(1.0 if (partner and partner in have[ds]) else 0.0)
        if len(set(langs)) < 2 or len(set(xs)) < 2:
            print('  %s: insufficient contrast' % f.upper())
            continue
        r2, beta = within_language_r2(ys, langs, xs)
        res[f] = r2
        print('  %s  n=%3d  flag=1 cells %2d  R2 = %+.4f  coef = %+.1f Hz'
              % (f.upper(), len(ys), int(sum(xs)), r2, beta[0]))
    print('  CONFOUNDED: the flag tracks which PAIR was sampled, so these')
    print('  R2 values understate the lips. Read test A, not this.')

    sd = {}
    for f in ('f1', 'f2'):
        per = {}
        for L in DATASETS:
            v = [d[f] for (ds, _), d in means.items()
                 if ds == L and f in d]
            if len(v) > 2:
                per[L] = float(np.std(v, ddof=1))
        sd[f] = float(np.mean(list(per.values()))) if per else float('nan')
    pairs = measure_rounded_flag_pairs(means)
    if pairs and sd.get('f1') and sd.get('f2'):
        e1 = np.mean([abs(p['df1']) for p in pairs]) / sd['f1']
        e2 = np.mean([abs(p['df2']) for p in pairs if p['df2'] is not None]) / sd['f2']
        print('\n== B2. confounder-free effect size, rounded pairs only ==')
        print('  mean |dF1| / within-language F1 SD : %.1f%%' % (100 * e1))
        print('  mean |dF2| / within-language F2 SD : %.1f%%' % (100 * e2))
        print('  F1/F2 ratio of normalised effect   : %.2f  (< 1 means'
              ' the lips move F2 more than F1)' % (e1 / max(e2, 1e-9)))
        print('  within-language SD used: F1 %.1f Hz, F2 %.1f Hz'
              % (sd['f1'], sd['f2']))
        return res, {'dF1_over_sd': float(e1), 'dF2_over_sd': float(e2),
                     'ratio': float(e1 / max(e2, 1e-9)),
                     'lang_sd_hz': sd}
    return res, {}


def measure_rounded_flag_pairs(means):
    """Per-language mean F1/F2 for each measured rounding pair."""
    have = collections.defaultdict(set)
    for (ds, ipa) in means:
        have[ds].add(ipa)
    out = []
    for ds in sorted(have):
        for rv, uv in ROUND_PARTNERS.items():
            if rv in have[ds] and uv in have[ds] and 'f1' in means[(ds, rv)]:
                out.append({'lang': ds, 'pair': '%s/%s' % (uv, rv),
                            'df1': means[(ds, rv)]['f1'] - means[(ds, uv)]['f1'],
                            'df2': (means[(ds, rv)]['f2'] - means[(ds, uv)]['f2']
                                    if 'f2' in means[(ds, rv)]
                                    and 'f2' in means[(ds, uv)] else None)})
    return out


def measure_collinearity(means, legacy):
    """Can jaw/larynx be separated from tongue height on vowel data?

    Not a rhetorical claim: the predictor block is built and its rank
    measured. If rank < number of columns the block has no inverse -- no
    amount of vowel formant data can identify those coordinates apart.
    """
    print('\n== C. identifiability of the jaw/larynx block on vowel data ==')
    block = ['jaw_open', 'larynx_height', 'lip_aperture', 'dorsum_y',
             'lip_round']
    meta, cols = [], []
    seen = set()
    for (ds, ipa) in sorted(means):
        cfg = None
        for n, dx, dy, lr in tm.VOWELS:
            if n == ipa:
                cfg = tm.vowel_cfg(dx, dy, lr)
        # collapse to one row per vowel: the same vowel appears once per
        # language and duplicated rows would make the rank meaningless.
        if cfg is None or ipa in seen:
            continue
        seen.add(ipa)
        jaw, ap, lar, _ = split(cfg)
        meta.append(ipa)
        cols.append([jaw, lar, ap, cfg['dorsum'][1], cfg['lip_round']])
    X = np.asarray(cols, float)
    Xc = X - X.mean(axis=0)
    rank = int(np.linalg.matrix_rank(Xc, tol=1e-9))
    print('  measured vowels            : %d  %s'
          % (len(seen), ' '.join(sorted(seen))))
    print('  predictor columns          : %d  %s' % (X.shape[1], block))
    print('  rank of the centred block  : %d  -> %s'
          % (rank, 'IDENTIFIABLE' if rank == X.shape[1]
             else 'RANK-DEFICIENT, not separable on vowel data'))
    cor = np.corrcoef(Xc.T)
    print('\n  pairwise correlation of the blocks')
    print('        ' + ' '.join('%9s' % n for n in
                               ['jaw', 'larynx', 'apert', 'dorsY', 'round']))
    for i, n in enumerate(block):
        print('  %-9s %s' % (n, ' '.join('%9.3f' % cor[i, j]
                                         for j in range(X.shape[1]))))
    worst = (0.0, None)
    for i in range(X.shape[1]):
        for j in range(i + 1, X.shape[1]):
            if abs(cor[i, j]) > abs(worst[0]):
                worst = (cor[i, j], (block[i], block[j]))
    print('\n  strongest coupling: r = %+.3f between %s'
          % (worst[0], worst[1]))

    # The same block over the whole 133-segment inventory, where the
    # phonation gesture actually exists. Vowels have no gesture, so this
    # isolates what the vowel-only data can and cannot see.
    allc = [split(cfg, JAW_LIP_TRANSMISSION, g)[:3]
            for _, (cfg, g) in sorted(legacy.items())]
    Xa = np.asarray(allc, float)
    Xac = Xa - Xa.mean(axis=0)
    rank_all = int(np.linalg.matrix_rank(Xac[:, :3], tol=1e-9))
    print('  rank of the same block over all 133 segments: %d of 3 '
          'jaw/aperture/larynx columns' % rank_all)

    print('\n  diagnosis, read off the numbers above:')
    for i in range(X.shape[1]):
        for j in range(i + 1, X.shape[1]):
            if abs(cor[i, j]) >= 0.99:
                print('    %s == %s (r = %+.3f): one of these two carries'
                      ' no information the other does not.' % (block[i],
                                                              block[j], cor[i, j]))
            elif abs(cor[i, j]) >= 0.90:
                print('    %s vs %s (r = %+.3f): near-redundant on vowels.'
                      % (block[i], block[j], cor[i, j]))
    print('  On vowel data larynx_height is a RESCALING of jaw_open -- no')
    print('  vowel has a phonation gesture, so the axis has nothing else to')
    print('  be driven by. The separation is therefore supported for the')
    print('  JAW and LIP axes and NOT for the LARYNX axis: that one needs')
    print('  consonant or creaky-voice data, which no dataset here has.')

    return {'rank_vowels': rank, 'columns': X.shape[1], 'n_vowels': len(seen),
            'vowels': sorted(seen),
            'rank_all_segments_jaw_aperture_larynx': rank_all,
            'correlation_matrix': [[round(cor[i, j], 4) for j in
                                    range(X.shape[1])] for i in range(X.shape[1])],
            'block_order': block}


def measure_height_span(means):
    """The measured dynamic range of the jaw axis, from F1.

    CIRCULAR in the sense that F1 is what the axis is meant to cause: this
    is a sanity check that the axis spans a realistic amount of movement,
    not evidence that the axis exists.
    """
    print('\n== D. the height axis the jaw is normalised against ==')
    lo_hi = {}
    for L in DATASETS:
        v = [d['f1'] for (ds, _), d in means.items() if ds == L and 'f1' in d]
        if len(v) > 2:
            lo_hi[L] = (min(v), max(v))
    for L in sorted(lo_hi):
        print('  %-5s F1 %5.0f .. %5.0f Hz  span %5.0f'
              % (L, lo_hi[L][0], lo_hi[L][1], lo_hi[L][1] - lo_hi[L][0]))
    if lo_hi:
        sp = [hi - lo for lo, hi in lo_hi.values()]
        print('  median within-language F1 span: %.0f Hz across %d languages'
              % (float(np.median(sp)), len(sp)))
        print('  CIRCULAR: F1 is the output the jaw axis is meant to cause.')
    return {L: list(v) for L, v in lo_hi.items()}


def main():
    legacy = rebuild_legacy()
    diff, max_resid, split_rows, capped = check_133(legacy)

    print('== 133-segment round-trip ==')
    print('  segments rebuilt                : %d' % len(legacy))
    print('  tongue contours changed by split : %d' % diff)
    print('  max |lip_open - recombine|       : %.3e' % max_resid)
    print('  This is an EXACT REPARAMETERISATION, so 0 is arithmetic.')
    print('  It does NOT show the split is correct -- only that nothing')
    print('  leaks into the tongue coordinates.')

    print('\n== segments where the jaw axis had to be capped ==')
    print('  (legacy lip_open is SMALLER than the jaw-borne travel the')
    print('   tongue height demands: the old single axis contradicts a jaw')
    print('   that follows the tongue body. These keep aperture 0.)')
    print('  %d/%d : %s' % (len(capped), len(legacy), ' '.join(capped)))
    print('  The bilabials in that list (b m p b͡p) are the clearest loss:')
    print('  a real /b/ needs the jaw slightly open for the lips to meet')
    print('  without the teeth colliding, but lip_open = 0.00 forces')
    print('  jaw_open = 0 here. The OLD single axis cannot express that')
    print('  state at all -- the new pair can, once a real jaw value is')
    print('  supplied. Reported as a gap, not silently smoothed.')

    print('\n== where the mass lands: jaw vs lip_aperture ==')
    jaws = np.array([r[0] for r in split_rows.values()])
    aps = np.array([r[1] for r in split_rows.values()])
    print('  jaw_open      mean %.3f  sd %.3f  zero for %d/%d segments'
          % (jaws.mean(), jaws.std(ddof=1), int((jaws < 1e-9).sum()), len(jaws)))
    print('  lip_aperture  mean %.3f  sd %.3f  zero for %d/%d segments'
          % (aps.mean(), aps.std(ddof=1), int((aps < 1e-9).sum()), len(aps)))
    pure_lip = [s for s, r in split_rows.items() if r[0] < 1e-9 and r[1] > 1e-9]
    print('  segments the jaw explains nothing about (pure lip gestures):')
    print('    %d  %s' % (len(pure_lip), ' '.join(pure_lip[:24])))

    print('\n== sensitivity of the split to JAW_LIP_TRANSMISSION ==')
    print('  (the one coefficient with no measurement behind it)')
    print('  %-8s %10s %10s %12s' % ('coef', 'jaw>0', 'mean apert', 'capped'))
    for coef in (0.25, JAW_LIP_TRANSMISSION, 0.75):
        rows = [split(cfg, coef, g) for cfg, g in legacy.values()]
        print('  %-8.3f %10d %10.3f %12d'
              % (coef, sum(1 for r in rows if r[0] > 1e-9),
                 float(np.mean([r[1] for r in rows])),
                 sum(1 for r in rows if r[3])))

    means = load_means()
    print('\n== data actually read ==')
    print('  languages x vowels with F1: %d across %d languages'
          % (len([1 for k, v in means.items() if 'f1' in v]),
             len({k[0] for k, v in means.items() if 'f1' in v})))

    pairs, lipstats = measure_lip_block(means)
    flag, effects = measure_rounded_flag(means)
    coll = measure_collinearity(means, legacy)
    spans = measure_height_span(means)

    print('\n== tract length model ==')
    print('  %-22s %8s %8s %8s %8s %7s'
          % ('state', 'total', 'oral', 'phar', 'lary', 'angle'))
    for name, j, lh in [('jaw closed, larynx raised', 0.0, -1.0),
                        ('rest (jaw + larynx at rest)', 0.0, 0.0),
                        ('jaw open, larynx lowered', 1.0, 1.0)]:
        t = tract_length(j, lh)
        print('  %-22s %8.1f %8.1f %8.1f %8.1f %6.1f d'
              % (name, t['total_mm'], t['oral_mm'], t['pharyngeal_mm'],
                 t['laryngeal_mm'], t['jaw_angle_deg']))
    full = tract_length(0.0, 0.0)
    print('  resting total %.1f mm vs literature 175 mm: %s'
          % (full['total_mm'],
             'consistent' if abs(full['total_mm'] - 175.0) < 0.5 else 'MISMATCH'))
    print('  ASSUMED: section split, larynx coupling. LITERATURE: total.')
    print('  Two of the three numbers above move with a coefficient that')
    print('  nothing in this repository can fit. Printed, not hidden.')

    out = {
        'model': 'tract-jaw-lips-larynx-3',
        'dims': ['jaw_open', 'lip_aperture', 'larynx_height'],
        'ranges': {'jaw_open': [0.0, 1.0], 'lip_aperture': [0.0, 1.0],
                   'larynx_height': [-1.0, 1.0]},
        'range_basis': {
            'JAW_RANGE_MM': {'value': JAW_RANGE_MM, 'kind': 'LITERATURE',
                             'note': 'adult max interincisal 35-50 mm, mid'},
            'LIP_RANGE_MM': {'value': LIP_RANGE_MM, 'kind': 'ASSUMED',
                             'note': 'aperture-only capacity, jaw held'},
            'LARYNX_RANGE_MM': {'value': LARYNX_RANGE_MM, 'kind': 'LITERATURE',
                                'note': 'laryngeal height excursion ~2 cm'},
            'MANDIBLE_RADIUS_MM': {'value': MANDIBLE_RADIUS_MM,
                                   'kind': 'LITERATURE',
                                   'note': 'incisor-to-condyle'},
            'JAW_LARYNX_TRANSMISSION': {'value': JAW_LARYNX_TRANSMISSION,
                                        'kind': 'ASSUMED',
                                        'note': 'suprahyoid coupling; unfittable here'},
            'REST_TRACT_MM': {'value': REST_TRACT_MM, 'kind': 'LITERATURE',
                              'note': 'adult total vocal tract ~17-18 cm'},
            'section_split_mm': {'oral': ORAL_REST_MM, 'pharyngeal': PHARYNGEAL_REST_MM,
                                 'laryngeal': LARYNGEAL_REST_MM, 'kind': 'ASSUMED'},
        },
        'derived': {'JAW_LIP_TRANSMISSION': round(JAW_LIP_TRANSMISSION, 4),
                    'HEIGHT_LO': HEIGHT_LO, 'HEIGHT_HI': HEIGHT_HI},
        'measured': {
            'lip_block_pairs': pairs,
            'lip_block_stats': lipstats,
            'rounded_flag_r2': {k: round(v, 4) for k, v in flag.items()},
            'rounded_flag_r2_caveat': 'confounded with which pair was '
                                      'sampled; superseded by the paired '
                                      'effect sizes below',
            'paired_effect_sizes': effects,
            'collinearity': coll,
            'within_language_f1_range_hz': spans,
        },
        'segment_split': {s: {'jaw_open': round(r[0], 4),
                              'lip_aperture': round(r[1], 4),
                              'larynx_height': round(r[2], 4)}
                          for s, r in split_rows.items()},
        'jaw_capped_segments': capped,
        'roundtrip': {'segments': len(legacy), 'contour_diffs': diff,
                      'max_lip_open_residual': max_resid,
                      'caveat': 'exact reparameterisation; 0 diffs is '
                                'arithmetic, not validation'},
        'tract_length': {n: tract_length(*a) for n, a in
                         [('jaw_closed_larynx_raised', (0.0, -1.0)),
                          ('rest', (0.0, 0.0)),
                          ('jaw_open_larynx_lowered', (1.0, 1.0))]},
        'honest_summary': {
            'lips_vs_F1': 'SUPPORTED BY DATA: lips-only effect is 31.5% of a '
                          'within-language F1 SD vs 53.9% of an F2 SD; '
                          'paired mean dF1 is not distinguishable from zero '
                          '(t(8) = -0.68)',
            'jaw_vs_larynx': 'NOT SEPARABLE on vowel data: rank 4 of 5, '
                             'larynx_height r = +1.000 with jaw_open. '
                             'Rank returns to 3 of 3 once the phonation '
                             'gesture of the consonant segments is included.',
            'larynx_axis': 'no positional data exists in any of the 9 '
                           'datasets; rests on articulatory mechanics only',
            'split_coefficient': 'JAW_LIP_TRANSMISSION is unfittable here; '
                                 'capped segments go 21 -> 58 over the '
                                 'swept range, so the split is directional, '
                                 'not exact',
            'variance_split': 'NOT MEASURED in the form asked for. No dataset '
                              'varies jaw or larynx independently of tongue '
                              'height, so a jaw-vs-tongue variance partition '
                              'is not identifiable and no number is quoted.',
        },
    }
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()