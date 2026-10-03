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
import gen_tongue_modifiers as M

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

    # --- summary + height: the collapse was one step too far ----------------
    # Dropping the tongue coordinates also dropped vowel HEIGHT, which is not
    # redundant with constriction_pos. constriction_gap mixes height with the
    # roof slope (roof(x) falls toward the pharynx), so /i/ and /u/ -- both
    # close -- land far apart on it. One coordinate that is height alone is
    # not fitted to any feature key; it is read straight off the contour.
    hk = keep + ['height']
    hrows = {s: srows[s] + [contour[s]['tongue']['dorsum'][1]] for s in syms}
    H = np.array([hrows[s] for s in syms], float)
    print('\n== summary + height ==')
    print('  dimensions %d   rank %d   distinct rows %d of %d'
          % (len(hk), np.linalg.matrix_rank(H),
             len({tuple(hrows[s]) for s in syms}), len(syms)))
    # Height must order the vowel triangle; check it does rather than assume.
    for a, b in [('i', 'a'), ('u', 'a'), ('i', 'u'), ('ɨ', 'a')]:
        if a in hrows and b in hrows:
            print('  height %-2s %.3f   %-2s %.3f   %s'
                  % (a, hrows[a][-1], b, hrows[b][-1],
                     'higher' if hrows[a][-1] > hrows[b][-1] else 'lower'))
    hout = {'dims': hk, 'table': hrows,
            'derived_from': 'merged_basis.json',
            'note': 'height is dorsum_y from the contour, not fitted'}
    hpath = os.path.join(DATA, 'summary_height.json')
    with io.open(hpath, 'w', encoding='utf-8') as f:
        f.write(json.dumps(hout, ensure_ascii=False, indent=1))
    print('\nwrote %s' % hpath)

    # --- summary with BOTH glottal axes kept ------------------------------
    # Merging glottal_aperture and glottal_tension into one source_tilt was
    # justified by r = -0.775, but a correlation that is strong and NEGATIVE
    # means the two axes carry the same information with opposite sign, so
    # averaging cancels whatever the pair does not agree on. That residual is
    # not noise: it is where creaky and tense phonation live, and it is the
    # single largest feature-recall deficit in the audit (tense, +0.421).
    gk = keep + ['source_tension']
    grows = {s: srows[s] + [table[s][OI['glottal_tension']]] for s in syms}
    Gr = np.array([grows[s] for s in syms], float)
    print('\n== summary with both glottal axes ==')
    print('  dimensions %d   rank %d   distinct rows %d of %d'
          % (len(gk), np.linalg.matrix_rank(Gr),
             len({tuple(grows[s]) for s in syms}), len(syms)))
    print('  source_tilt vs source_tension r = %.3f (the cancelled residual)'
          % np.corrcoef(Gr[:, gk.index('source_tilt')],
                        Gr[:, gk.index('source_tension')])[0, 1])
    gout = {'dims': gk, 'table': grows,
            'derived_from': 'merged_basis.json',
            'note': 'keeps glottal_aperture and glottal_tension separate'}
    gpath = os.path.join(DATA, 'summary_both_glottal.json')
    with io.open(gpath, 'w', encoding='utf-8') as f:
        f.write(json.dumps(gout, ensure_ascii=False, indent=1))
    print('\nwrote %s' % gpath)

    # --- vowel-only height --------------------------------------------------
    # diagnose_tense.py: the 17 segments PhonoLib marks `tense` are all
    # close VOWELS, and both bases already keep them clustered, so the deficit
    # is in the metric's view of vowel height, not in the glottal axes.
    # constriction_gap = roof(dorsum_x) - dorsum_y mixes tongue height with the
    # roof slope, so /i/ and /u/ -- both close -- land far apart on it.
    #
    # Adding dorsum_y outright FAILED: for a consonant that height IS the roof,
    # so it re-injects place and Gate 1 collapsed from 0.522 to 0.304. A
    # consonant has no independent height to record -- its vertical position is
    # determined by place. A vowel does. So this coordinate carries the mean of
    # the four control-point heights for vowels and a single constant for every
    # consonant, which after standardisation contributes exactly zero to
    # consonant-to-consonant distance and cannot reintroduce place noise.
    parts_y = [[contour[s]['tongue'][p][1] for p in PARTS] for s in syms]
    raw = {s: float(np.mean(ys)) for s, ys in zip(syms, parts_y)}
    floor = float(np.mean(list(raw.values())))
    vk = keep + ['vowel_height']
    vrows = {s: srows[s] + [raw[s] if contour[s]['anchor'] == 'vowel' else floor]
             for s in syms}
    V = np.array([vrows[s] for s in syms], float)
    print('\n== summary + vowel-only height ==')
    print('  dimensions %d   rank %d   distinct rows %d of %d'
          % (len(vk), np.linalg.matrix_rank(V),
             len({tuple(vrows[s]) for s in syms}), len(syms)))
    con = {vrows[s][-1] for s in syms if contour[s]['anchor'] != 'vowel'}
    print('  consonant values taken: %d (must be 1)' % len(con))
    print('  vowel range %.3f to %.3f' % (min(raw[s] for s in syms
                                             if contour[s]['anchor'] == 'vowel'),
                                         max(raw[s] for s in syms
                                             if contour[s]['anchor'] == 'vowel')))
    for a, b in [('i', 'a'), ('u', 'a'), ('e', 'ɐ'), ('ɤ', 'ɑ')]:
        if a in vrows and b in vrows and contour[a]['anchor'] == 'vowel' \
                and contour[b]['anchor'] == 'vowel':
            print('  %-2s %.3f  vs %-2s %.3f  -> %s higher'
                  % (a, vrows[a][-1], b, vrows[b][-1],
                     a if vrows[a][-1] > vrows[b][-1] else b))
    vout = {'dims': vk, 'table': vrows,
            'derived_from': 'merged_basis.json',
            'consonant_floor': floor,
            'note': 'mean control-point height for vowels, constant elsewhere'}
    vpath = os.path.join(DATA, 'summary_vheight.json')
    with io.open(vpath, 'w', encoding='utf-8') as f:
        f.write(json.dumps(vout, ensure_ascii=False, indent=1))
    print('\nwrote %s' % vpath)

    # --- one coordinate, mode-appropriate definition ------------------------
    # A vowel has no constriction, so "how far the tongue is from the roof" is
    # not a quantity it has: for /i/ the whole tract is narrow, for /a/ it is
    # wide, and roof(x) - dorsum_y mixes the two. So constriction_gap is defined
    # for consonants (closure degree) and for vowels as openness, which is the
    # same perceptual axis the height coordinate carries. One coordinate, not
    # two, and no constant-valued axis.
    j = keep.index('constriction_gap')
    ugap = {s: (raw[s] if contour[s]['anchor'] == 'vowel'
                else srows[s][j]) for s in syms}
    urows = {s: (srows[s][:j] + [ugap[s]] + srows[s][j + 1:]) for s in syms}
    U = np.array([urows[s] for s in syms], float)
    print('\n== summary with mode-appropriate constriction_gap (%d dims) =='
          % len(keep))
    print('  rank %d   distinct rows %d of %d'
          % (np.linalg.matrix_rank(U),
             len({tuple(urows[s]) for s in syms}), len(syms)))
    for a, b in [('i', 'a'), ('u', 'a'), ('i', 'u')]:
        print('  gap %-2s %.3f  vs %-2s %.3f  -> %s wider'
              % (a, urows[a][j], b, urows[b][j],
                 b if urows[a][j] > urows[b][j] else a))
    uout = {'dims': keep, 'table': urows,
            'derived_from': 'merged_basis.json',
            'note': 'constriction_gap is closure for consonants, openness '
                    '(mean control-point height) for vowels'}
    upath = os.path.join(DATA, 'summary_vgap.json')
    with io.open(upath, 'w', encoding='utf-8') as f:
        f.write(json.dumps(uout, ensure_ascii=False, indent=1))
    print('\nwrote %s' % upath)

    # --- uniform tongue-body height ----------------------------------------
    # summary_height used dorsum_y and collapsed Gate 1 to 0.304; that axis IS
    # the contact height, so it moves with place. The MEAN of the four
    # control-point heights is not: measured r = -0.098 against constriction_pos
    # overall and -0.065 on consonants. And 48 of 100 consonants fall inside
    # the vowel height range, so consonants really do have a height here --
    # summary_vheight denied that by pinning them to a constant, which is why
    # it violated J6. This is the uniform version J6 actually asks for.
    uk = keep + ['tongue_height']
    urows2 = {s: srows[s] + [raw[s]] for s in syms}
    U2 = np.array([urows2[s] for s in syms], float)
    print('\n== summary + uniform tongue height (%d dims) ==' % len(uk))
    print('  rank %d   distinct rows %d of %d'
          % (np.linalg.matrix_rank(U2),
             len({tuple(urows2[s]) for s in syms}), len(syms)))
    print('  every segment gets its own value: %d distinct over %d segments'
          % (len({round(raw[s], 6) for s in syms}), len(syms)))
    hp = os.path.join(DATA, 'summary_uheight.json')
    with io.open(hp, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'dims': uk, 'table': urows2,
                            'derived_from': 'merged_basis.json',
                            'note': 'mean of the four control-point heights, '
                                    'same definition for every segment'},
                           ensure_ascii=False, indent=1))
    print('\nwrote %s' % hp)

    # --- summary + tongue ROOT ---------------------------------------------
    # ATR and RTR displace the root and nothing else. With no root coordinate
    # in the summary, apply_mod left the 10-dim vector BIT-IDENTICAL, so /k/,
    # /k'+ATR and /k'+RTR were one point. That is not precision loss, it is
    # information set to zero, and IPA's most common secondary articulation was
    # invisible. The 8 tongue coordinates are near-orthogonal to the
    # constriction summary (|r| <= 0.482), so they are not a duplicate of it.
    rk = keep + ['root_x', 'root_y']
    rrows = {s: srows[s] + [contour[s]['tongue']['root'][0],
                           contour[s]['tongue']['root'][1]] for s in syms}
    R = np.array([rrows[s] for s in syms], float)
    print('\n== summary + tongue root (%d dims) ==' % len(rk))
    print('  rank %d   distinct rows %d of %d'
          % (np.linalg.matrix_rank(R),
             len({tuple(rrows[s]) for s in syms}), len(syms)))
    for mod, op in (('atr', M.DISPLACE['atr']), ('rtr', M.DISPLACE['rtr'])):
        vis = []
        for s in syms:
            if contour[s]['anchor'] != 'velar':
                continue
            cfg = {p: tuple(contour[s]['tongue'][p]) for p in PARTS}
            cfg['lip_open'] = contour[s]['lip_open']
            cfg['lip_round'] = contour[s]['lip_round']
            c2 = M.apply_mod(dict(cfg), mod)
            moved = sum(1 for j in range(len(keep))
                        if abs(float(np.mean([c2[p][1] for p in PARTS]))
                               - srows[s][j]) > 1e-9)
            vis.append(moved)
            break
        print('  %s applied to /k/: changes %d of %d summary dims'
              % (mod, vis[0] if vis else 0, len(keep)))
    rp = os.path.join(DATA, 'summary_root.json')
    with io.open(rp, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'dims': rk, 'table': rrows,
                            'derived_from': 'merged_basis.json',
                            'note': 'adds the tongue root, the only carrier of '
                                    'ATR and RTR'},
                           ensure_ascii=False, indent=1))
    print('\nwrote %s' % rp)


if __name__ == '__main__':
    main()
