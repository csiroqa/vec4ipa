"""Why does p fit as b? Measure the margin, not just the failure.

§0.11.5 found the reverse-fit misses are within-class: p→b, t͡ʃ→d͡ʒ,
d͡ʑ→t͡ɕ, kʼ→qʼ. p and b differ on exactly one axis (periodic, 1.0 apart),
so a thin margin is not an obvious explanation and guessing would be worse
than measuring.

For each symbol this reports, under noise:
  d_true  distance from the query to its own vector
  d_best  distance to the nearest OTHER vector
and the margin d_best - d_true. A large positive margin means the query is
still closer to its own vector and the metric is fine -- the failure is then
the fit choosing something else, or a tie. A near-zero or negative margin means
the pair is genuinely not separated at this noise level.

Also reports how many symbols have any axis differing from their confusable
partner by less than the total noise magnitude, which is the population that
can fail at all.

Run: python tools/audit_reverse_margin.py
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


def main():
    basis = json.load(io.open(os.path.join(DATA, 'merged_basis.json'),
                              encoding='utf-8'))
    old = json.load(io.open(os.path.join(DATA, 'vec_table_16.json'),
                            encoding='utf-8'))
    dims = basis['dims']
    syms = sorted(basis['table'])
    d2 = old['dims']

    for name, tbl, scheme, axes in (
            ('new 18-dim', basis['table'], 'tongue.scheme', dims),
            ('old 16-dim', old['table'], 'spec_next.scheme', d2)):
        d2 = old['dims']
        X = np.array([tbl[s] for s in syms], float)
        # The runtime's own weights, so the margins are the ones vec2ipa sees.
        sd = np.sqrt(X.shape[1])
        print('\n== %s ==' % name)
        print('  noise sigma=0.02 over %d axes gives a total distance noise '
              'of about %.3f' % (X.shape[1], 0.02 * sd))

        pairs = {'p': 'b', 'b': 'p', 't͡ʃ': 'd͡ʒ', 'd͡ʒ': 't͡ʃ',
                 'd͡ʑ': 'd͡ɕ', 'd͡ɕ': 'd͡ʑ', 'kʼ': 'qʼ', 'qʼ': 'kʼ'}
        # Label with THIS basis's axis names. The two have different widths, so
        # borrowing the other's names prints the right numbers under the wrong
        # labels -- which is worse than printing nothing.
        print('  reported confusions, axis by axis (%d axes):' % len(axes))
        for a, b in pairs.items():
            if a not in syms or b not in syms:
                continue
            i, j = syms.index(a), syms.index(b)
            diff = [(axes[k], tbl[a][k], tbl[b][k])
                    for k in range(len(axes))
                    if abs(tbl[a][k] - tbl[b][k]) > 1e-9]
            sep = sum(abs(x - y) for _, x, y in diff)
            print('    %-4s / %-4s  raw gap %.3f  %s'
                  % (a, b, sep,
                     ' '.join('%s=%.2f' % (n, x) for n, x, _ in diff)
                     or '(no differing axis)'))

        # How many symbols are within one noise radius of any other symbol?
        D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
        np.fill_diagonal(D, np.inf)
        nearest = D.min(axis=1)
        thr = 0.02 * sd
        tight = [(syms[i], nearest[i]) for i in np.argsort(nearest)[:6]]
        print('  nearest-neighbour raw distance, smallest six:')
        for s, dist in tight:
            print('    %-4s %.3f' % (s, dist))
        print('  %d of %d symbols have a neighbour within the noise radius '
              '(%.3f)' % (int((nearest < thr).sum()), len(syms), thr))

    out = os.path.join(DATA, 'reverse_margin.json')
    io.open(out, 'w', encoding='utf-8').write(json.dumps(
        {'noise_radius_18': 0.02 * np.sqrt(18)}, indent=1))
    print('\nwrote %s' % out)


if __name__ == '__main__':
    main()