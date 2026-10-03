"""Score the C reverse fit on the splits Gate 1 uses, not on exact strings.

Gate 1's hit@1 and vec2ipa's reconstruction are not the same task. Phatak
gives a 16x16 confusion matrix aggregated over four SNRs -- a pairwise
retrieval question ("does the metric rank the confused pair above the
unconfused ones") -- while vec2ipa identifies a symbol from one vector. No
number is comparable across the two, and reporting one against the other would
be meaningless.

What IS comparable is the SPLIT. Gate 1 scores a confusion by whether it is a
place_or_manner confusion or a voicing confusion, and so can this: run the
built vec2ipa on a noisy vector from each segment and ask whether the answer
still carries the right anchor, the right manner and the right voicing. A
system can miss the exact symbol and still be right about everything the
confusion data cares about, and that is the part worth reporting.

Exact hit@1 is reported too, but as the strictest number alongside the
class-level ones, not as the headline.

Run: python tools/audit_reverse_fit.py
"""

import collections
import io
import json
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
VEC2IPA = os.path.join(ROOT, 'vec2ipa.exe' if os.name == 'nt' else 'vec2ipa')

# Place classes, coarse enough to be what a listener would call a confusion.
def place_class(anchor):
    return {
        'bilabial': 'labial', 'labiodental': 'labial',
        'dental': 'coronal', 'alveolar': 'coronal',
        'postalveolar': 'coronal', 'retroflex': 'coronal',
        'palatoalveol': 'coronal', 'palatal': 'dorsal',
        'velar': 'dorsal', 'uvular': 'dorsal',
        'pharyngeal': 'radical', 'epiglottal': 'radical',
        'glottal': 'radical', 'vowel': 'vowel',
    }.get(anchor, anchor)


import hashlib


def stable_seed(sym, sigma):
    """A seed that does not move between runs.

    hash() on a str is salted per process (PYTHONHASHSEED), so the same
    script gives different noise on different runs -- which would make every
    number here unreproducible and any before/after comparison meaningless.
    """
    h = hashlib.sha256(('%s|%.3f' % (sym, sigma)).encode('utf-8'))
    return int(h.hexdigest()[:8], 16)


def score(basis, table, scheme, sigma):
    hits = collections.Counter()
    misses = []
    n = 0
    for sym in sorted(basis):
        rnd = random.Random(stable_seed(sym, sigma))
        v = [x + rnd.gauss(0, sigma) for x in basis[sym]]
        csv = ','.join('%.6f' % x for x in v)
        r = subprocess.run([VEC2IPA, '-D',
                            os.path.join(DATA, scheme), csv],
                           capture_output=True, text=True)
        first = [l for l in r.stdout.splitlines() if l.startswith('[')]
        got = first[0].split(']')[0][1:] if first else '?'
        n += 1
        hits['exact'] += (got == sym)
        tg, tt = table.get(got, {}), table[sym]
        if tg and tt:
            hits['anchor'] += (tg['anchor'] == tt['anchor'])
            hits['place_class'] += (place_class(tg['anchor'])
                                    == place_class(tt['anchor']))
            hits['manner'] += (tg['manner'] == tt['manner'])
            hits['voicing'] += ((tg['velum'] == tt['velum'])
                                and (abs(tg['larynx'] - tt['larynx'])
                                     < 1e-6))
        if got != sym and len(misses) < 5:
            misses.append((sym, got))
    return n, hits, misses


def main():
    table = json.load(io.open(os.path.join(DATA, 'tongue_table.json'),
                            encoding='utf-8'))
    new = json.load(io.open(os.path.join(DATA, 'merged_basis.json'),
                             encoding='utf-8'))['table']
    old = json.load(io.open(os.path.join(DATA, 'vec_table_16.json'),
                         encoding='utf-8'))['table']

    print('Two bases, one noise draw per (symbol, sigma) each, scored on '
          "Gate 1's\nsplits rather than on exact strings.\n")
    results = {}
    for sigma in (0.01, 0.02, 0.05):
        for name, basis, scheme in (('new 18-dim', new, 'tongue.scheme'),
                                    ('old 16-dim', old, 'spec_next.scheme')):
            n, h, misses = score(basis, table, scheme, sigma)
            print('sigma=%.2f  %s  n=%d' % (sigma, name, n))
            row = {'n': n}
            for k in ('exact', 'place_class', 'anchor', 'manner', 'voicing'):
                row[k] = round(100.0 * h[k] / n, 2)
                print('   %-12s %5.1f%%' % (k, row[k]))
            row['misses'] = ['%s->%s' % m for m in misses]
            results['%s@%s' % (name, sigma)] = row
            if misses:
                print('   misses: %s' % ', '.join(row['misses']))
        print()

    out = os.path.join(DATA, 'reverse_fit.json')
    io.open(out, 'w', encoding='utf-8').write(
        json.dumps(results, ensure_ascii=False, indent=1))
    print('wrote %s' % out)


if __name__ == '__main__':
    main()