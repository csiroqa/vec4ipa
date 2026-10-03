"""Is the old basis's LOCO advantage bought with class-conditional axes?

The per-feature audit puts the old basis ahead on exactly the vowel features:
high +0.326, front +0.210, back +0.197, tense +0.276. The old 16-axis table
also carries axes whose variance is ZERO inside one class -- place, lips_closed
and tip_shape are constant across all 33 vowels; tongue_root is constant across
all 100 consonants; six more are constant for vowels.

A constant-within-a-class axis is a free per-class offset: it moves every
vowel together and discriminates nothing between them, but it lets the metric
separate vowels from consonants at zero cost. J6 rejects exactly this. The
question this settles is whether the old basis's 0.140 LOCO lead survives
removing those axes -- that is, whether the new basis is missing information or
merely refusing to cheat.

Run: python tools/audit_j6_axes.py
"""

import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_merged_basis as B              # noqa: E402
import gate_retrieval as G                # noqa: E402

DATA = B.DATA
OLD = os.path.join(DATA, 'vec_table_16.json')
OUT = os.path.join(DATA, 'j6_axis_audit.json')

# Coordinates stored rounded to 3 decimals; anything below this is one
# rounding step, not a real difference.
TOL = 1e-3


def class_variances(dims, table, vowels):
    """Within-class standard deviation of each axis, split by vowel/consonant."""
    out = {}
    for d in dims:
        col = np.array([table[s][dims.index(d)] for s in table], float)
        v = np.array([table[s][dims.index(d)] for s in vowels], float)
        c = np.array([table[s][dims.index(d)] for s in table
                      if s not in vowels], float)
        out[d] = {'vowel_sd': float(v.std()), 'consonant_sd': float(c.std()),
                  'dead_in': ('consonants' if c.std() < TOL else
                              'vowels' if v.std() < TOL else None)}
    return out


def main():
    old = json.load(io.open(OLD, encoding='utf-8'))
    tbl = json.load(io.open(os.path.join(DATA, 'tongue_table.json'),
                            encoding='utf-8'))
    vowels = {s for s, e in tbl.items() if e['anchor'] == 'vowel'}
    vars_ = class_variances(old['dims'], old['table'], vowels)

    dead = [d for d, v in vars_.items() if v['dead_in']]
    live = [d for d in old['dims'] if d not in dead]
    print('old basis, %d axes, of which %d are constant inside a class\n'
          % (len(old['dims']), len(dead)))
    print('  %-22s %9s %10s  %s'
          % ('axis', 'vowel sd', 'conson sd', 'constant in'))
    for d in old['dims']:
        v = vars_[d]
        print('  %-22s %9.4f %10.4f  %s'
              % (d, v['vowel_sd'], v['consonant_sd'], v['dead_in'] or '-'))
    print('\n  dropped (J6): %s' % ', '.join(dead))
    print('  kept   (J6): %s' % ', '.join(live))

    clean = {'dims': live,
             'table': {s: [r[old['dims'].index(d)] for d in live]
                       for s, r in old['table'].items()}}
    path = os.path.join(DATA, 'old_j6_clean.json')
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(clean, ensure_ascii=False, indent=1))
    print('\n  wrote %s (%d axes)' % (path, len(live)))

    print('\nLOCO act_prec on the J6-cleaned old basis:')
    syms, _ = G.load_bases()
    wanted = set(syms)
    feat, _, _, _ = G.load_phoible(wanted)
    per_lang, _ = G.load_svmcc_tokens(wanted)
    X = np.array([clean['table'][s] for s in sorted(clean['table'])], float)
    res = G.gate3(sorted(syms), {'j6_clean': (live, X)}, feat, per_lang)
    for k, v in sorted(res['summary'].items()):
        print('  %-34s %.4f' % (k, v['mean_excl_thin_folds']))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'axes': vars_, 'dropped': dead, 'kept': live,
                            # The vowel set decides the verdict for every axis
                            # that is constant across vowels, and it comes
                            # from a generated table that changes when the
                            # model changes. An earlier run left `voiced` and
                            # `glottal_aperture` in the kept list -- both are
                            # constant across all 33 vowels -- because the set
                            # it used was not recorded here and nobody could
                            # see that it had moved. Writing the set down
                            # makes the verdict checkable instead of trusted.
                            'vowel_set_size': len(vowels),
                            'vowel_set': sorted(vowels),
                            'loco_clean': {k: v['mean_excl_thin_folds']
                                           for k, v in res['summary'].items()}},
                           ensure_ascii=False, indent=1))
    print('wrote %s  (vowel set: %d symbols)' % (OUT, len(vowels)))


if __name__ == '__main__':
    main()