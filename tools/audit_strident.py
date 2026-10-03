"""Is strident already encoded in the deployed basis, or does it need a new axis?

`strident` scores 0.000 on the current basis and 0.269 on the old one. The old
axis that carried it, jet_focus, is constant across all 33 vowels, so it is one
of the eleven class-conditional axes dropped in tools/audit_j6_axes.py -- the
old advantage was not information and cannot be borrowed back.

Two very different situations look identical from a single LOCO number:

  (a) stridents already sit apart on some existing axis and the fitted metric
      fails to find it. Then the fix is in the metric, and no new axis is
      justified.
  (b) stridents overlap the nonstrident fricatives on every axis. Then the
      basis genuinely lacks the quantity and a new axis would be needed -- but
      only one measured independently, because defining an axis from the
      PhonoLib label would be fitting the answer key.

This separates them by measuring, per axis, how well strident sibilants are
separated from nonstrident fricatives by a single coordinate. It uses the
PhonoLib label only to GROUP the symbols, never to build an axis.

Run: python tools/audit_strident.py
"""

import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_merged_basis as B          # noqa: E402
import gate_retrieval as G            # noqa: E402

DATA = B.DATA
OUT = os.path.join(DATA, 'strident_audit.json')

# Only fricatives are compared. A stop has no turbulence at all, so including
# them would inflate the separation and answer a different question.
NONSIBILANT_FRICATIVES = 'f v θ ð x ɣ χ ʁ ɦ ħ ʕ ɧ β ɸ'


def main():
    syms, bases = G.load_bases()
    wanted = set(syms)
    feat, feats, _, _ = G.load_phoible(wanted)
    if 'strident' not in feats:
        raise SystemExit('no strident column; phoible columns are %s' % feats)
    si = feats.index('strident')

    dims, X = bases['new']
    row = {s: i for i, s in enumerate(syms)}

    pos, neg = [], []
    for s in sorted(feat):
        if s not in row:
            continue
        is_sib = feat[s][si] > 0.5
        if is_sib:
            pos.append(s)
        elif s in NONSIBILANT_FRICATIVES:
            neg.append(s)
    print('strident sibilants     n=%d  %s' % (len(pos), ' '.join(pos)))
    print('nonstrident fricatives n=%d  %s\n' % (len(neg), ' '.join(neg)))

    A, Bv = X[[row[s] for s in pos]], X[[row[s] for s in neg]]

    # A single axis separates the two sets if its threshold midpoint misses
    # fewer than the best 5-NN would. Cohen's d is the standardised gap.
    print('  %-16s %8s %8s %8s %8s  %s'
          % ('axis', 'strid sd', 'other sd', "Cohen's d", '1-NN acc', ''))
    rows = []
    for j, d in enumerate(dims):
        a, b = A[:, j], Bv[:, j]
        sa, sb = a.std(), b.std()
        pooled = ((sa ** 2 + sb ** 2) / 2.0) ** 0.5
        dd = float((a.mean() - b.mean()) / pooled) if pooled > 1e-12 else 0.0

        # 1-NN over just these two groups, on this axis alone
        pts = [(v, 1) for v in a] + [(v, 0) for v in b]
        acc = 0
        for i, (v, y) in enumerate(pts):
            others = [p for j2, p in enumerate(pts) if j2 != i]
            nn = min(others, key=lambda p: abs(p[0] - v))
            acc += int(nn[1] == y)
        acc /= len(pts)
        rows.append({'axis': d, 'cohens_d': dd, 'nn_acc': acc,
                     'strid_mean': float(a.mean()), 'other_mean': float(b.mean())})
        print('  %-16s %8.4f %8.4f %8.3f %8.3f  %s'
              % (d, sa, sb, dd, acc,
                 '<< best' if acc == max(r['nn_acc'] for r in rows) else ''))

    best = max(rows, key=lambda r: (r['nn_acc'], abs(r['cohens_d'])))
    order = sorted(rows, key=lambda r: -abs(r['cohens_d']))
    print('\n  best single axis: %s  Cohen d=%.3f  1-NN acc=%.3f'
          % (best['axis'], best['cohens_d'], best['nn_acc']))
    print('  top by |d|: ' + ', '.join(
        '%s %.2f' % (r['axis'], r['cohens_d']) for r in order[:5]))

    # A full basis is only as good as the direction that separates; report what
    # the current metric actually retrieves rather than what an axis could.
    print('\n  what the deployed metric retrieves for each strident:')
    for s in pos:
        D = np.sqrt(np.maximum(((X - X[row[s]]) ** 2).sum(axis=1), 0.0))
        D[row[s]] = np.inf
        nb = np.argsort(D)[:5]
        got = [syms[i] for i in nb]
        hit = sum(1 for g in got if g in pos)
        print('    %-4s -> %-28s strident %d/5' % (s, ' '.join(got), hit))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'stridents': pos, 'others': neg,
                            'axes': rows,
                            'best': best['axis'],
                            'best_nn_acc': best['nn_acc']},
                           ensure_ascii=False, indent=1))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()