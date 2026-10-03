"""Leave-one-language-out with the class-constant axes dropped from the NEW basis.

Section 0.7 established that the old basis's LOCO advantage came from eleven
axes that are constant within one class -- `place` and `lips_closed` are the
same value for all 33 vowels, `tongue_root` for all 100 consonants. Such an
axis is a free category offset: it moves a whole class together, resolves
nothing inside it, and still lets the metric separate vowels from consonants at
no cost. Cleaning it dropped the old basis from 0.6488 to 0.5040.

The new basis has the same property on ten of its eighteen axes, all of them
constant across vowels (tip_x blade_x root_x root_y velum lateral larynx
periodic source_tilt duration). So "new 0.5788 vs j6_clean old 0.5040" compares
a basis that still carries the cheat against one that does not, and the
headline number is not a like-for-like comparison.

This drops the same axes from the new basis and reruns the same LOCO, so both
sides are measured under the same criterion. The difference between the two
cleaned numbers is the honest comparison.

Run: python tools/audit_j6_new_basis.py
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
OUT = os.path.join(DATA, 'j6_new_clean.json')


def main():
    basis = json.load(io.open(os.path.join(DATA, 'merged_basis.json'),
                              encoding='utf-8'))
    contour = json.load(io.open(os.path.join(DATA, 'tongue_table.json'),
                                encoding='utf-8'))
    dims, table = basis['dims'], basis['table']
    syms = sorted(table)

    vowels = {s for s in syms if contour[s]['manner'] == 'vowel'}
    cons = [s for s in syms if s not in vowels]

    keep, dropped = [], []
    for i, name in enumerate(dims):
        v = np.array([table[s][i] for s in sorted(vowels)], float)
        c = np.array([table[s][i] for s in cons], float)
        if v.std() < 1e-9 or c.std() < 1e-9:
            dropped.append((name, 'vowel' if v.std() < 1e-9 else 'consonant'))
        else:
            keep.append(i)

    X = np.array([[table[s][i] for i in keep] for s in syms], float)
    kept_dims = [dims[i] for i in keep]
    print('dropped %d class-constant axes, keeping %d: %s'
          % (len(dropped), len(keep), ' '.join(kept_dims)))
    for n, w in dropped:
        print('   %-20s constant across %s' % (n, w))

    wanted = set(syms)
    feats, _, _, _ = G.load_phoible(wanted)
    per_lang, _ = G.load_svmcc_tokens(wanted)
    res = G.gate3(syms, {'j6_new_clean': (len(keep), X)}, feats, per_lang)
    strict = res['summary']['j6_new_clean/strict/act_prec']

    old = json.load(io.open(os.path.join(DATA, 'old_j6_clean.json'),
                            encoding='utf-8'))
    osyms = sorted(old['table'])
    oX = np.array([old['table'][s] for s in osyms], float)
    ores = G.gate3(osyms, {'j6_clean': (len(old['dims']), oX)}, feats,
                   per_lang)
    old_act = ores['summary']['j6_clean/strict/act_prec']

    print('\n== LOCO, both bases stripped of class-constant axes ==')
    print('old basis, %d axes kept   %.4f'
          % (len(old['dims']), old_act['mean_excl_thin_folds']))
    print('new basis, %d axes kept   %.4f'
          % (len(keep), strict['mean_excl_thin_folds']))
    print('difference               %+.4f'
          % (strict['mean_excl_thin_folds'] - old_act['mean_excl_thin_folds']))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'kept_dims': kept_dims,
                   'dropped': dropped,
                   'loco': strict,
                   'old_clean_loco': old_act}, f, indent=1)
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()