"""Forward model: tongue contour -> measured formants.

The tongue coordinates in gen_tongue_model.py were authored from the IPA vowel
trapezoid, and that trapezoid IS F1/F2 geometry. So fitting F1 and F2 against
them is CIRCULAR and its R2 proves nothing -- it is reported here only so the
number is not mistaken for validation later.

F3 is the real test. Nothing in the contour was tuned to F3: the coordinates
encode where the tongue sits and how high, which is F1/F2 information. If F3
is predicted anyway, the representation carries vowel-quality information it
was never given.

Two things are being measured:
  1. does the contour predict a formant nobody used to build it (F3)?
  2. do any tongue coordinates drop out entirely? Those are the new scheme's
     version of the dead axes the P0 audit found in the old one.

Regressions are within-language (formants demeaned per language) so that
differences in speaker vocal-tract length between the nine languages are not
read as tongue movement.

Run: python tools/fit_tongue_forward.py
"""

import io
import json
import os

import numpy as np

import gen_tongue_model as tm
from gen_vowel3d import XS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
DATASETS = ['pb52', 'h95', 't07', 'f73', 'p73', 'b95', 'f99', 'a96', 'y96']

FEATURES = [p + '_' + c for p in tm.TONGUE for c in ('x', 'y')] + ['lip_round']


def coords_for(ipa):
    for n, dx, dy, lr in tm.VOWELS:
        if n == ipa:
            cfg = tm.vowel_cfg(dx, dy, lr)
            # Interleave (x, y) per part. Returning all x then all y produced a
            # design matrix that did not match FEATURES, so every coefficient
            # was reported under another coordinate's name.
            return [v for p in tm.TONGUE
                    for v in (cfg[p][0], cfg[p][1])] + [lr]
    return None


def load():
    import pyreadr
    acc = {}
    for ds in DATASETS:
        path = os.path.join(DATA, ds + '.rda')
        if not os.path.exists(path):
            continue
        try:
            df = pyreadr.read_r(path)[ds]
        except Exception:
            continue
        cols = set(df.columns)
        for _, r in df.iterrows():
            ipa = XS.get(str(r['vowel']))
            if ipa is None or coords_for(ipa) is None:
                continue
            for f in ('f1', 'f2', 'f3'):
                if f not in cols or f not in r or r[f] is None:
                    continue
                v = float(r[f])
                if 100.0 < v < 5000.0:
                    acc.setdefault((ds, ipa, f), []).append(v)
    return acc


def within_language_fit(feats, ys, langs):
    """Ridge-free OLS with a language dummy and an intercept, on demeaned y."""
    groups = sorted(set(langs))
    dummies = [[1.0 if l == g else 0.0 for g in groups] for l in langs]
    X = np.column_stack([np.asarray(feats, float), np.asarray(dummies, float)])
    y = np.asarray(ys, float)
    ybar = {L: y[[i for i, l in enumerate(langs) if l == L]].mean()
            for L in set(langs)}
    yd = np.array([y[i] - ybar[l] for i, l in enumerate(langs)])
    beta, *_ = np.linalg.lstsq(X, yd, rcond=None)
    pred = X @ beta
    ss_res = float(((yd - pred) ** 2).sum())
    ss_tot = float(((yd - yd.mean()) ** 2).sum())
    return beta, 1.0 - ss_res / ss_tot, float(np.sqrt(ss_res / len(yd))), yd, pred


def main():
    acc = load()
    # Per-formant parallel lists: the three formants are missing from different
    # subsets of the datasets (a96 has F4 but no f2 for some rows), so they
    # cannot share one index space.
    parts = {f: {'langs': [], 'feats': [], 'y': []} for f in ('f1', 'f2', 'f3')}
    for (ds, ipa, f), vals in sorted(acc.items()):
        parts[f]['langs'].append(ds)
        parts[f]['feats'].append(coords_for(ipa))
        parts[f]['y'].append(float(np.mean(vals)))

    langs = parts['f1']['langs']
    print('== data ==')
    print('  language x vowel cells (f1) : %d across %d languages'
          % (len(langs), len(set(langs))))
    print('  IPA symbols covered         : %d  %s'
          % (len(set(a[1] for a in acc)),
             ' '.join(sorted(set(a[1] for a in acc)))))
    for f in ('f1', 'f2', 'f3'):
        print('  %s cells: %d' % (f.upper(), len(parts[f]['y'])))

    print('\n== per-language mean of each formant (Hz) ==')
    for L in sorted(set(langs)):
        row = []
        for f in ('f1', 'f2', 'f3'):
            vs = [v for l, v in zip(parts[f]['langs'], parts[f]['y']) if l == L]
            row.append('%s %5.0f' % (f.upper(), np.mean(vs)) if vs
                       else '%s   -' % f.upper())
        print('  %-5s %s' % (L, '  '.join(row)))

    print('\n== within-language fit ==')
    print('   F1/F2 are CIRCULAR: the contour was authored from the IPA')
    print('   trapezoid, which is F1/F2 geometry. F3 is the honest number.')
    results = {}
    for f in ('f1', 'f2', 'f3'):
        beta, r2, rmse, yd, pred = within_language_fit(
            parts[f]['feats'], parts[f]['y'], parts[f]['langs'])
        results[f] = (beta, r2, rmse)
        tag = '  <- circular' if f in ('f1', 'f2') else '  <- the real test'
        print('  %s  n=%3d  R2 = %.3f   RMSE = %5.1f Hz%s'
              % (f.upper(), len(parts[f]['y']), r2, rmse, tag))

    print('\n== coefficient per tongue coordinate (Hz, F3 model) ==')
    beta = results['f3'][0]
    fx = np.asarray(parts['f3']['feats'], float)
    sds = fx.std(axis=0)
    # A feature that never varies gets an arbitrary coefficient out of the
    # minimum-norm solution: reporting it as influence would be a fiction.
    # vowel_cfg leaves root untouched, so root_x and root_y are constant.
    live = [i for i, sd in enumerate(sds) if sd > 1e-9]
    for i, (name, b, sd) in enumerate(zip(FEATURES, beta, sds)):
        if i in live:
            bar = '#' * int(min(abs(b) / 4.0, 40))
            print('  %-12s %7.2f Hz  sd=%.3f  %s' % (name, b, sd, bar))
        else:
            print('  %-12s %7.2f Hz  sd=%.3f  CONSTANT -- coefficient is '
                  'meaningless' % (name, b, sd))

    dead = [FEATURES[i] for i, sd in enumerate(sds) if sd <= 1e-9]
    print('\n  %d of %d coordinates are constant across the vowel set'
          % (len(dead), len(FEATURES)))
    if dead:
        print('  %s' % ', '.join(dead))
        print('  That is a property of the VOWEL SUBSET: a vowel makes no tip')
        print('  or root gesture, so those coordinates cannot vary here. It is')
        print('  NOT evidence the coordinates are dead -- consonant data is')
        print('  required to settle that, and none of the nine vowel datasets')
        print('  contain consonants.')

    print('\n== refit on the varying coordinates only ==')
    keep = None
    Xk = fx[:, live]
    b2, r2b, rmseb, yd2, _ = within_language_fit(
        Xk.tolist(), parts['f3']['y'], parts['f3']['langs'])
    print('  n features %d -> %d   R2 = %.3f   RMSE = %.1f Hz'
          % (len(FEATURES), len(live), r2b, rmseb))

    out = {'features': FEATURES,
           'r2': {f: round(results[f][1], 4) for f in results},
           'rmse_hz': {f: round(results[f][2], 1) for f in results},
           'f3_coefficients': {n: round(b, 3)
                               for n, b in zip(FEATURES, beta)}}
    with io.open(os.path.join(DATA, 'tongue_forward.json'), 'w',
                 encoding='utf-8') as f_:
        f_.write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\nwrote tools/data/tongue_forward.json')


if __name__ == '__main__':
    main()
