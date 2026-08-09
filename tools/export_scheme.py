#!/usr/bin/env python3
"""Export the SPEC-NEXT 16-dim scheme to the C-runtime scheme format.

Format (line-based, no JSON needed by the C loader):
  ndim N
  dim <name>            (N lines, in vector order)
  weight <w0> <w1> ...  (N floats)
  lambda <l>
  seg <ipa> <v0> ... <vN-1> <airstream>
  (one seg line per base segment; airstream in
   {pulmonic,glottalic-egressive,glottalic-ingressive,lingual,percussive})

Output: tools/data/spec_next.scheme (loadable with `ipa2vec --scheme FILE`
after the C runtime supports it).

Run: python tools/export_scheme.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
VEC = os.path.join(DATA, 'vec_table_16.json')
METRIC = os.path.join(DATA, 'metric16.json')
OUT = os.path.join(DATA, 'spec_next.scheme')

AIR = {'pulmonic': 'pulmonic',
       'glottalic egressive': 'glottalic-egressive',
       'glottalic ingressive': 'glottalic-ingressive',
       'lingual': 'lingual'}


def airstream_of(v):
    if v[15] < 0:
        return 'glottalic-ingressive' if v[8] >= 0.5 else 'lingual'
    return 'glottalic-egressive' if v[9] >= 0.9 else 'pulmonic'


def main():
    tbl = json.load(open(VEC, encoding='utf-8'))['table']
    dims = json.load(open(VEC, encoding='utf-8'))['dims']
    m = json.load(open(METRIC, encoding='utf-8'))
    w = m['weights']
    lam = m['lambda']

    lines = [f'ndim {len(dims)}']
    for d in dims:
        lines.append(f'dim {d}')
    lines.append('weight ' + ' '.join(f'{x:.6g}' for x in w))
    lines.append(f'lambda {lam:.6g}')
    for seg in sorted(tbl):
        v = tbl[seg]
        air = airstream_of(v)
        lines.append('seg ' + seg + ' ' +
                     ' '.join(f'{x:.6g}' for x in v) + ' ' + air)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'wrote {OUT}: {len(dims)} dims, {len(tbl)} segments')


if __name__ == '__main__':
    main()
