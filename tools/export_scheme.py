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

NOTE — two weight authorities, intentionally divergent:
  * tools/data/metric16.json  = fitted design weights (tip_shape 5,
    duration 25), validated by tools/test_spec_next.py;
  * tools/data/spec_next.scheme = hand-tuned runtime weights (tip_shape
    4, duration 5), compiled into the binaries, validated by
    tools/test_suite.py / test_metric_space.py.
  The committed scheme therefore differs from this script's output in
  the weight line (and any hand-tuned seg rows, e.g. vowel `body`
  values).  Keep the two authorities consistent on the airstream column
  (B3 fixed the polarity: ejectives/implosives/clicks/h).

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
    # airflow_direction < 0: ingressive — voiced = implosive, unvoiced = lingual
    if v[15] < 0:
        return 'glottalic-ingressive' if v[8] >= 0.5 else 'lingual'
    # ejective: constricted glottis (negative aperture) + raised larynx
    if v[9] <= -0.8 and v[11] > 0.5:
        return 'glottalic-egressive'
    return 'pulmonic'


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
    # newline='\n': byte-identical regeneration on Windows and Unix
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'wrote {OUT}: {len(dims)} dims, {len(tbl)} segments')


if __name__ == '__main__':
    main()
