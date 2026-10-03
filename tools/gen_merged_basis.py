"""Merge the two bases into one, with the constriction axis derived not typed.

The two bases disagree and the measurements say why. The old basis wins place
retrieval (LOCO act_prec 0.649 vs 0.484); the new contour basis wins voicing
(1.000 vs 0.111) and is the only one with a forward model (F3 R2 = 0.690).
A full metric cannot bridge the gap, so it is the geometry, not the weighting.

The elegant merge is not to go back to a hand-set place chain. The contour
already produces a constriction site as GEOMETRY -- derived_constriction finds
where the tongue is nearest the roof. That site was being computed and then
discarded, with site_from marking how many of the 133 rows had it derived
(57) versus assigned (66).

So: carry the derived site as a first-class coordinate. It is the old
effective_oral_area plus place, but computed from the contour instead of typed,
which means it cannot drift out of sync with the geometry it claims to describe.

This file assembles that basis and the gate then scores it against the old one.
If a derived place axis recovers the gap, the two designs were never rivals.

Run: python tools/gen_merged_basis.py
"""

import io
import json
import os

import numpy as np

import gen_tongue_model as tm
import gen_tongue_table as tt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
OLD = os.path.join(DATA, 'vec_table_16.json')
CONTOUR = os.path.join(DATA, 'tongue_table.json')
BASIS = os.path.join(DATA, 'merged_basis.json')

PARTS = tm.TONGUE

# A segment with no constriction at all (/h ɦ ʔ/) is not "at place 0" -- that
# collides with the central vowels, which is the old scheme's place=0.00
# overload. But a sentinel far outside the anchored range inflates this
# coordinate's variance, and after z-scoring that flattens every real place
# difference. 0.95 sits just past the most posterior anchored site (0.80) so it
# still separates without dominating the scale.
NO_CONSTRICTION = 0.95

# Lip and labiodental closures ARE constrictions, they just have no tongue part
# to name them. Marking them "no constriction" put /f v/ in the same sentinel
# slot as /h ɦ ʔ/ and collapsed the voicing cells, so the site is named here.
LIP_SITES = {
    'bilabial':    (0.00, 0.00),   # lips meeting
    'labiodental': (0.05, 0.10),   # lower lip against the upper teeth, narrow
}


def main():
    old = json.load(io.open(OLD, encoding='utf-8'))
    OI = {x: i for i, x in enumerate(old['dims'])}
    table = old['table']
    contour = json.load(io.open(CONTOUR, encoding='utf-8'))
    syms = sorted(set(table) & set(contour))

    ap = [table[s][OI['glottal_aperture']] for s in syms]
    tn = [table[s][OI['glottal_tension']] for s in syms]
    vd = [table[s][OI['voiced']] for s in syms]
    merge_src = bool(np.corrcoef(ap, tn)[0, 1] < -0.6)

    dims = ([p + '_' + c for p in PARTS for c in ('x', 'y')]
            + ['lip_open', 'lip_round', 'velum', 'lateral', 'larynx',
               'periodic', 'source_tilt', 'duration',
               'constriction_pos', 'constriction_gap']
            + ([] if merge_src else ['source_tension']))

    rows, prov = {}, {}
    derived_n = assigned_n = none_n = 0
    for i, s in enumerate(syms):
        e = contour[s]
        cfg = {p: tuple(e['tongue'][p]) for p in PARTS}
        cfg['lip_open'] = e['lip_open']
        cfg['lip_round'] = e['lip_round']
        if e['anchor'] == 'vowel':
            # A vowel has no constriction gesture; its site is the dorsum and
            # its gap is the real distance to the roof, which is exactly what
            # makes /i/ (narrow) and /a/ (wide) differ on this axis.
            part, origin = 'dorsum', 'assigned'
            site_x, gap = cfg['dorsum'][0], tm.roof(cfg['dorsum'][0]) - cfg['dorsum'][1]
        elif e['anchor'] in LIP_SITES:
            part, origin = 'lips', 'assigned'
            site_x, gap = LIP_SITES[e['anchor']]
        else:
            site_x, gap, part, origin = tt.derived_site(
                cfg, e['anchor'], e['manner'])
        if site_x is None:
            pos, cg = NO_CONSTRICTION, gap
            none_n += 1
        else:
            pos, cg = site_x, gap
            if origin == 'derived':
                derived_n += 1
            else:
                assigned_n += 1

        v = []
        for p in PARTS:
            v.extend(e['tongue'][p])
        v.extend([e['lip_open'], e['lip_round'], e['velum'], e['lateral'],
                  e['larynx'], vd[i],
                  (ap[i] + tn[i]) / 2.0 if merge_src else ap[i],
                  e['duration'], pos, cg])
        if not merge_src:
            v.append(tn[i])
        rows[s] = [round(x, 6) for x in v]
        prov[s] = {'site_from': origin, 'anchor': e['anchor'],
                   'manner': e['manner'], 'constrictor': part}

    X = np.array([rows[s] for s in syms], float)
    i_pos, i_gap = dims.index('constriction_pos'), dims.index('constriction_gap')

    print('== merged basis ==')
    print('  segments %d   dimensions %d   rank %d'
          % (len(syms), len(dims), np.linalg.matrix_rank(X)))
    print('  distinct rows %d of %d' % (len({tuple(rows[s]) for s in syms}),
                                        len(syms)))
    print('  constriction site provenance: derived %d, assigned %d, none %d'
          % (derived_n, assigned_n, none_n))

    print('\n== is the derived place axis ordered? (vowels must not collide '
          'with retroflex) ==')
    old_place = [table[s][OI['place']] for s in syms]
    print('  corr(old place, derived constriction_pos) = %.3f'
          % np.corrcoef(old_place, X[:, i_pos])[0, 1])
    rf = [X[syms.index(s), i_pos] for s in syms if s in ('ʈ', 'ʂ', 'ɖ')]
    cv = [X[syms.index(s), i_pos] for s in syms
          if s in ('i', 'a', 'u', 'ɯ', 'ɨ')]
    print('  retroflex constriction_pos %s   central vowels %s'
          % (sorted(set(rf)), sorted(set(cv))))
    print('  shared values: %d' % len(set(rf) & set(cv)))

    print('\n== does it separate what the contour alone could not? ==')
    for a, b in [('p', 'b'), ('t', 'd'), ('k', 'ɡ'), ('s', 'z'),
                 ('ɕ', 'ʃ'), ('ʈ', 't'), ('k', 't'), ('i', 'ʈ')]:
        if a in rows and b in rows:
            d = [dims[j] for j in range(len(dims)) if rows[a][j] != rows[b][j]]
            print('  %-3s vs %-3s  %d axes: %s'
                  % (a, b, len(d), ' '.join(d[:5])))

    out = {'dims': dims, 'table': rows, 'provenance': prov,
           'site_provenance': {'derived': derived_n, 'assigned': assigned_n,
                               'none': none_n},
           'no_constriction_sentinel': NO_CONSTRICTION}
    with io.open(BASIS, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\nwrote %s' % BASIS)

    # --- summary basis: the same rows, geometry left out -------------------
    # The fitted metric never gave constriction_pos real weight, because it is
    # a FUNCTION of the tongue coordinates sitting beside it in the same
    # vector -- collinear by construction, so it cannot add information and the
    # optimiser routes around it. That is not a reason to drop the axis; it is
    # a reason to stop measuring on the primitives. Geometry explains and
    # drives the forward model; the summary is what distance runs on.
    keep = ['constriction_pos', 'constriction_gap', 'lip_open', 'lip_round',
            'velum', 'lateral', 'larynx', 'periodic', 'source_tilt',
            'duration']
    idx = [dims.index(k) for k in keep]
    srows = {s: [rows[s][j] for j in idx] for s in syms}
    S = np.array([srows[s] for s in syms], float)
    print('\n== summary basis (geometry excluded) ==')
    print('  dimensions %d   rank %d   distinct rows %d of %d'
          % (len(keep), np.linalg.matrix_rank(S),
             len({tuple(srows[s]) for s in syms}), len(syms)))
    for a, b in [('p', 'b'), ('t', 'd'), ('k', 'ɡ'), ('s', 'z'),
                 ('ɕ', 'ʃ'), ('ʈ', 't'), ('k', 't'), ('i', 'ʈ')]:
        if a in srows and b in srows:
            d = [keep[j] for j in range(len(keep)) if srows[a][j] != srows[b][j]]
            print('  %-3s vs %-3s  %d axes: %s'
                  % (a, b, len(d), ' '.join(d[:4])))
    sout = {'dims': keep, 'table': srows, 'derived_from': 'merged_basis.json'}
    spath = os.path.join(DATA, 'summary_basis.json')
    with io.open(spath, 'w', encoding='utf-8') as f:
        f.write(json.dumps(sout, ensure_ascii=False, indent=1))
    print('\nwrote %s' % spath)


if __name__ == '__main__':
    main()
