"""Locate the `tense` deficit: which segments carry it and can each basis see it.

audit_loco_features.py put `tense` at the top of the old basis's advantage
(+0.421, old 0.921 vs new 0.487) and keeping both glottal axes did not recover
it, so the cause is not the aperture/tension merge. The remaining candidate is
that the tense segments are pulled into a cluster by some OTHER axis in the old
basis, so retrieving any member of that cluster carries `tense` -- a
clustering explanation rather than a glottal one.

This lists the segments PhonoLib marks tense, prints their glottal values and
their nearest neighbours under each basis, and reports whether tense segments
are closer to each other than to the nearest non-tense segment. If they are
not, no metric over these coordinates can recover them and the deficit is not a
representation defect at all.

Run: python tools/diagnose_tense.py
"""

import io
import json
import os

import numpy as np

import gate_retrieval as G

DATA = G.DATA
OUT = os.path.join(DATA, 'tense_diagnosis.json')


def neighbours(D, row, k=5):
    order = np.argsort(D[row], kind='stable')
    return [int(i) for i in order if i != row][:k]


def main():
    syms, bases = G.load_bases()
    wanted = set(syms)
    feat, feats, _, _ = G.load_phoible(wanted)
    order = {s: i for i, s in enumerate(syms)}
    n = len(syms)
    nf = len(next(iter(feat.values())))
    F = np.zeros((n, nf))
    for s, v in feat.items():
        F[order[s]] = v
    j_tense = list(feats).index('tense')

    tense = [s for s in syms if s in feat and F[order[s], j_tense] > 0.5]
    print('PhonoLib marks %d of %d segments tense: %s'
          % (len(tense), len(syms), ' '.join(tense)))
    print('these carry them: %s\n'
          % ', '.join(sorted({f for s in tense for f, v in
                               zip(feats, F[order[s]]) if v > 0.5})))

    old_tab = json.load(io.open(os.path.join(DATA, 'vec_table_16.json'),
                                encoding='utf-8'))
    OI = {x: i for i, x in enumerate(old_tab['dims'])}

    report = {}
    for bname, (dims, X) in bases.items():
        # unit-scaled geometry, unfitted: this isolates the representation from
        # the metric, which is the question being asked here.
        Z, dead = G._standardise(X, np.arange(n))
        Zr = Z[:, ~dead]
        D = np.sqrt(((Zr[:, None, :] - Zr[None, :, :]) ** 2).sum(-1))
        np.fill_diagonal(D, np.inf)
        live = [d for d, dd in zip(dims, dead) if not dd]

        trows = [order[s] for s in tense]
        rest = [i for i in range(n) if i not in trows]
        within = [D[a, b] for ix, a in enumerate(trows) for b in trows[ix + 1:]]
        to_out = [D[a, b] for a in trows for b in rest
                  if b in order.values() and F[b, j_tense] <= 0.5]
        print('== %s (%d dims) ==' % (bname, len(live)))
        print('  mean tense-tense distance    %.3f' % np.mean(within))
        print('  mean tense-nontense distance %.3f' % np.mean(to_out))
        separable = np.mean(within) < np.mean(to_out)
        print('  tense forms its own cluster: %s' % ('YES' if separable else
                                                     'NO'))
        for s in tense[:6]:
            r = order[s]
            ap = old_tab['table'][s][OI['glottal_aperture']]
            tn = old_tab['table'][s][OI['glottal_tension']]
            nb = ['%s%s' % (syms[i], '+' if F[i, j_tense] > 0.5 else '-')
                  for i in neighbours(D, r)]
            print('  %-3s aperture=%+.2f tension=%+.2f  nearest: %s'
                  % (s, ap, tn, ' '.join(nb)))
        report[bname] = {'separable': bool(separable),
                         'mean_within': float(np.mean(within)),
                         'mean_to_outside': float(np.mean(to_out)),
                         'live_coords': live}
        print()

    print('== verdict ==')
    sep = {b: report[b]['separable'] for b in bases}
    if all(sep.values()):
        print('both bases keep the tense segments apart, so the loss is in the '
              'METRIC or in the feature convention, not the geometry.')
    elif sep.get('old') and not sep.get('new'):
        print('the old basis clusters the tense segments and the new one does '
              'NOT: this is a real representation defect, and the clustering '
              'axis is whatever the old basis uses that the summary lacks.')
    else:
        print('NEITHER basis clusters the tense segments. No metric over these '
              'coordinates can recover `tense`; the deficit is in the feature '
              'convention or in segments the table lacks, not in the basis.')

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'tense_symbols': tense, 'bases': report},
                           ensure_ascii=False, indent=1))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()