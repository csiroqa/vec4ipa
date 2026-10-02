"""Assemble the COMPLETE new basis and check what it can still separate.

The retrieval gate built the new basis from 8 tongue coordinates plus 6
scalars = 14 dims. That basis has no periodicity coordinate, so p/b, t/d and
k/ɡ are the same point by construction -- the gate was scoring a basis that
structurally cannot do what the voicing cells ask. This script rebuilds the
basis with the source dimensions the old table carried and the contour model
dropped.

It also settles a claim from docs/DERIVATION.md P4 by measurement rather than
assertion: glottal_aperture and glottal_tension were proposed for merging into
one glottal axis. The correlation is computed here and the merge is only
applied if the data supports it; otherwise both are kept and the basis is 17
dims wide.

Run: python tools/gen_new_basis.py
"""

import io
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
OLD = os.path.join(DATA, 'vec_table_16.json')
CONTOUR = os.path.join(DATA, 'tongue_table.json')
OUT = os.path.join(DATA, 'new_basis.json')

PARTS = ['tip', 'blade', 'dorsum', 'root']


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def main():
    old = json.load(io.open(OLD, encoding='utf-8'))
    OI = {x: i for i, x in enumerate(old['dims'])}
    table = old['table']
    new = json.load(io.open(CONTOUR, encoding='utf-8'))
    syms = sorted(set(table) & set(new))

    ap = [table[s][OI['glottal_aperture']] for s in syms]
    tn = [table[s][OI['glottal_tension']] for s in syms]
    vd = [table[s][OI['voiced']] for s in syms]

    print('== can the two laryngeal axes merge? (DERIVATION P4, by measurement) ==')
    r = corr(ap, tn)
    print('  corr(glottal_aperture, glottal_tension) = %s over %d rows'
          % ('undefined (one is constant)' if r is None else '%.3f' % r, len(syms)))
    print('  aperture distinct values: %d   tension distinct values: %d'
          % (len(set(ap)), len(set(tn))))
    # If the two axes agree they can carry one coordinate. If they do not, a
    # mean would invent a value neither axis ever took.
    merge = r is not None and abs(r) > 0.6
    print('  verdict: %s' % ('MERGE into source_tilt' if merge
                             else 'KEEP BOTH -- they are not collinear'))
    src = [(a + t) / 2.0 for a, t in zip(ap, tn)] if merge else list(ap)

    dims = ([p + '_' + c for p in PARTS for c in ('x', 'y')]
            + ['lip_open', 'lip_round', 'velum', 'lateral', 'larynx',
               'periodic', 'source_tilt', 'duration']
            + ([] if merge else ['source_tension']))

    rows, prov = {}, {}
    for i, s in enumerate(syms):
        e = new[s]
        v = []
        for p in PARTS:
            v.extend(e['tongue'][p])
        v.extend([e['lip_open'], e['lip_round'], e['velum'], e['lateral'],
                  e['larynx'], vd[i], src[i], e['duration']])
        if not merge:
            v.append(tn[i])
        rows[s] = [round(x, 6) for x in v]
        prov[s] = {'periodic_from': 'old.voiced',
                   'source_from': 'mean(glottal_aperture, glottal_tension)'
                                  if merge else 'glottal_aperture'}

    X = np.array([rows[s] for s in syms], float)
    print('\n== basis shape ==')
    print('  segments %d   dimensions %d' % (len(syms), len(dims)))
    print('  rank of the matrix: %d of %d  %s'
          % (np.linalg.matrix_rank(X), len(dims),
             '<-- deficient' if np.linalg.matrix_rank(X) < len(dims) else ''))

    uniq = len({tuple(rows[s]) for s in syms})
    print('  distinct rows: %d of %d  (%d segments share a vector)'
          % (uniq, len(syms), len(syms) - uniq))

    print('\n== pairs the old basis separates and this one must too ==')
    for a, b in [('p', 'b'), ('t', 'd'), ('k', 'ɡ'), ('s', 'z'), ('ʃ', 'ʒ'),
                 ('m', 'n'), ('ɕ', 'ʃ'), ('θ', 'ð')]:
        if a in rows and b in rows:
            va, vb = np.array(rows[a]), np.array(rows[b])
            which = [dims[j] for j in range(len(dims)) if va[j] != vb[j]]
            print('  %-3s vs %-3s  differs on %d: %s'
                  % (a, b, len(which), ' '.join(which[:6]) or 'NOTHING'))

    out = {'dims': dims, 'table': rows, 'provenance': prov,
           'source_merge_applied': merge,
           'source_merge_corr': r}
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()
