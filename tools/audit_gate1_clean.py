"""Gate 1 on both bases stripped of class-constant axes.

§0.11.6 found the J6-cleaned old LOCO baseline was wrong: the audit left
`voiced` and `glottal_aperture` in the kept list although both are constant
across all 33 vowels, which inflated the new basis apparent LOCO lead from
+0.008 to +0.075. Gate 1 headline -- new 0.3906 against old 0.0938 -- was
never re-checked under that cleaning. Same shape of claim, same test.

Calling convention, read from gate_retrieval.gate1() rather than guessed:

  syms   the shared symbol list; X rows are indexed by position in it
  cons   Phatak consonant list, in Phatak order
  bases  BOTH bases in ONE call, keyed new and old

gate1 maps cons through PHATAK_SYMBOL_MAP before looking up rows, so handing
it Phatak list as syms loses the IPA g and dies with "not in list". It also
computes the old-fitted variant from bases[old] unconditionally, so passing
the bases one call at a time dies with KeyError: old.

The old-fitted variant is skipped when the old basis is not 16 axes wide,
because its metric weights are 16-long; that guard was added to
gate_retrieval.py so this comparison is possible at all.

Run: python tools/audit_gate1_clean.py
"""

import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate_retrieval as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')


def keep_indices(dims, table, vowels):
    """Indices that vary inside BOTH classes -- the 0.7 rule, applied anew."""
    keep = []
    for i in range(len(dims)):
        v = np.array([table[s][i] for s in vowels], float)
        c = np.array([table[s][i] for s in table if s not in vowels], float)
        if v.std() >= 1e-9 and c.std() >= 1e-9:
            keep.append(i)
    return keep


def build(tbl, shared, idx):
    return (len(idx), np.array([[tbl[s][i] for i in idx] for s in shared],
                               float))


def main():
    basis = json.load(io.open(os.path.join(DATA, 'merged_basis.json'),
                              encoding='utf-8'))
    old = json.load(io.open(os.path.join(DATA, 'vec_table_16.json'),
                            encoding='utf-8'))
    table = json.load(io.open(os.path.join(DATA, 'tongue_table.json'),
                              encoding='utf-8'))
    vowels = set(s for s, e in table.items() if e['anchor'] == 'vowel')

    cons, snrs, M_ph = G.load_phatak()
    shared = sorted(set(basis['table']) & set(old['table']))
    missing = [c for c in cons
               if G.PHATAK_SYMBOL_MAP.get(c, c) not in shared]
    if missing:
        raise SystemExit('shared symbol list is missing %s' % missing)

    kept, clean, full = {}, {}, {}
    for key, dims, tbl in (('new', basis['dims'], basis['table']),
                           ('old', old['dims'], old['table'])):
        idx = keep_indices(dims, tbl, vowels)
        kept[key] = [dims[i] for i in idx]
        clean[key] = build(tbl, shared, idx)
        full[key] = build(tbl, shared, list(range(len(dims))))
        print('== %-4s dropped %d class-constant axes, keeping %d: %s'
              % (key, len(dims) - len(idx), len(idx), ' '.join(kept[key])))

    out = {'kept': kept, 'hit1_clean': {}, 'hit1_full': {}}
    for title, bb, slot in (('cleaned axes', clean, 'hit1_clean'),
                            ('all axes', full, 'hit1_full')):
        g1 = G.gate1(shared, bb, cons, snrs, M_ph)

        print('\nhit@1 on %s:' % title)
        # keys are strings like 'new/z-euclid', not (name, metric) tuples.
        # Filtering on a tuple shape silently produced an empty result, which
        # is why two earlier runs printed a header and no numbers at all.
        for key in sorted(g1['variants']):
            if key not in ('new/z-euclid', 'old/z-euclid'):
                continue
            v = g1['variants'][key]
            print('  %-16s hit@1=%.4f  hit@3=%.4f  mrr=%.4f'
                  % (key, v['hit_at_1'], v['hit_at_3'], v['mrr']))
            out[slot][key] = round(v['hit_at_1'], 4)

    p = os.path.join(DATA, 'gate1_clean.json')
    io.open(p, 'w', encoding='utf-8').write(
        json.dumps(out, ensure_ascii=False, indent=1))
    print('\nwrote %s' % p)


if __name__ == '__main__':
    main()
