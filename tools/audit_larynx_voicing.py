"""Does putting voicing on the larynx axis survive the class-constant strip?

The raw reconstruction score improves from 117/133 to 124/133 when voicing is
written to `larynx` at 0.5 instead of being squeezed into 0.2 of
`source_tilt`. That looks like a free win, but `larynx` is already constant
across all 33 vowels, so writing voicing there may just be adding another
category offset -- the thing section 0.7 identified as cheating.

The test is section 0.7's own: drop every class-constant axis from both the
baseline and the variant, rerun LOCO on each, and compare. A geometric change
that only helps before the strip was never information.

Run: python tools/audit_larynx_voicing.py
"""

import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate_retrieval as G            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
OUT = os.path.join(DATA, 'larynx_voicing_audit.json')

VOICING_ON_LARYNX = 0.5


def keep_indices(dims, table, syms, vowels, cons):
    keep = []
    for i in range(len(dims)):
        v = np.array([table[s][i] for s in vowels], float)
        c = np.array([table[s][i] for s in cons], float)
        if v.std() >= 1e-9 and c.std() >= 1e-9:
            keep.append(i)
    return keep


def loco(syms, table, keep, feats, per_lang, label):
    X = np.array([[table[s][i] for i in keep] for s in syms], float)
    res = G.gate3(syms, {label: (len(keep), X)}, feats, per_lang)
    return res['summary']['%s/strict/act_prec' % label]['mean_excl_thin_folds']


def main():
    basis = json.load(io.open(os.path.join(DATA, 'merged_basis.json'),
                              encoding='utf-8'))
    old = json.load(io.open(os.path.join(DATA, 'vec_table_16.json'),
                            encoding='utf-8'))
    dims, table = basis['dims'], basis['table']
    li = dims.index('larynx')
    oi = {n: i for i, n in enumerate(old['dims'])}
    syms = sorted(set(table) & set(old['table']))

    contour = json.load(io.open(os.path.join(DATA, 'tongue_table.json'),
                                encoding='utf-8'))
    vowels = sorted(s for s in syms if contour[s]['manner'] == 'vowel')
    cons = [s for s in syms if s not in set(vowels)]

    variant = {s: list(table[s]) for s in syms}
    for s in syms:
        if variant[s][li] == 0.0 and old['table'][s][oi['voiced']] > 0.5:
            variant[s][li] = VOICING_ON_LARYNX

    k_base = keep_indices(dims, table, syms, vowels, cons)
    k_var = keep_indices(dims, variant, syms, vowels, cons)
    print('class-constant axes: baseline %d dropped, variant %d dropped'
          % (len(dims) - len(k_base), len(dims) - len(k_var)))
    print('axes kept: baseline %s' % ' '.join(dims[i] for i in k_base))
    print('axes kept: variant  %s' % ' '.join(dims[i] for i in k_var))

    feats, _, _, _ = G.load_phoible(set(syms))
    per_lang, _ = G.load_svmcc_tokens(set(syms))

    raw_b = loco(syms, table, k_base, feats, per_lang, 'raw')
    raw_v = loco(syms, variant, k_var, feats, per_lang, 'var')
    print('\n== LOCO on the axes that survive the strip ==')
    print('baseline            %.4f' % raw_b)
    print('voicing on larynx   %.4f' % raw_v)
    print('difference          %+.4f' % (raw_v - raw_b))

    verdict = ('survives -- it is information, not a category offset'
               if raw_v > raw_b else
               'does NOT survive -- the raw gain was a category offset')
    print('\nverdict: %s' % verdict)

    with io.open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'kept_baseline': [dims[i] for i in k_base],
                   'kept_variant': [dims[i] for i in k_var],
                   'loco_baseline': raw_b, 'loco_variant': raw_v,
                   'difference': raw_v - raw_b, 'verdict': verdict}, f,
                  indent=1)
    print('wrote %s' % OUT)


if __name__ == '__main__':
    main()