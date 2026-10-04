"""How many within-base modifier distinctions survive in each candidate basis?

gen_tongue_modifiers.py reports 78 pairs with 0 exact collisions, but that
check runs on the tongue contour -- the geometry the forward model uses. The
distance a neighbour query actually sees is a basis file, and the two are not
the same: audit_modifier_visibility.py already showed tip-only modifiers move
the contour and cannot move the deployed basis at all.

Collisions are counted WITHIN one base segment. /t/+dental and /s/+dental
sharing a contour is correct -- they are the same sound. What matters is that
two DIFFERENT modifiers on the SAME base do not land on the same point, and
that the number is compared against what the contour still distinguishes.

Run: python tools/audit_modifier_collisions.py [basis.json ...]
"""

import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_merged_basis as B          # noqa: E402
import gen_tongue_modifiers as M      # noqa: E402

DATA = B.DATA
# The basis the runtime actually ships; the summary_* rows are discarded
# variants, kept in the table for comparison but not held to a threshold.
DEPLOYED = 'merged_basis.json'
CONTOUR = os.path.join(DATA, 'tongue_table.json')
PARTS = B.PARTS

_OLD = json.load(io.open(os.path.join(DATA, 'vec_table_16.json'),
                         encoding='utf-8'))
_OLDTAB, _OI = _OLD['table'], {x: i for i, x in enumerate(_OLD['dims'])}


def quantities(cfg, symbol, entry):
    """Every coordinate any candidate basis could ask for, from one contour."""
    anchor, manner = entry['anchor'], entry['manner']
    if anchor == 'vowel':
        site_x = cfg['dorsum'][0]
        gap = B.tm.roof(site_x) - cfg['dorsum'][1]
    elif anchor in B.LIP_SITES:
        site_x, gap = B.LIP_SITES[anchor]
    else:
        site_x, gap, _, _ = B.tt.derived_site(cfg, anchor, manner)
    q = {'constriction_pos': B.NO_CONSTRICTION if site_x is None else site_x,
         'constriction_gap': gap,
         'lip_open': cfg['lip_open'], 'lip_round': cfg['lip_round'],
         'velum': entry['velum'], 'lateral': entry['lateral'],
         'larynx': entry['larynx'], 'duration': entry['duration']}
    old = _OLDTAB[symbol]
    q['periodic'] = old[_OI['voiced']]
    q['source_tilt'] = (old[_OI['glottal_aperture']]
                        + old[_OI['glottal_tension']]) / 2.0
    for p in PARTS:
        q[p + '_x'], q[p + '_y'] = cfg[p]
    return q


def contour_sig(cfg):
    return tuple(cfg[p] for p in PARTS) + (round(cfg['lip_open'], 9),
                                           round(cfg['lip_round'], 9))


def colliding_pairs(keys):
    """Number of unordered pairs of modifier names landing on the same key."""
    seen, total = {}, 0
    for _name, k in keys:
        n = seen.get(k, 0)
        total += n
        seen[k] = n + 1
    return total


def audit(basis_name):
    basis = json.load(io.open(os.path.join(DATA, basis_name), encoding='utf-8'))
    dims = basis['dims']
    contour = json.load(io.open(CONTOUR, encoding='utf-8'))
    names = sorted(M.DISPLACE)

    c_keys, b_keys, affected = [], [], 0
    for s, e in sorted(contour.items()):
        cfg = {p: tuple(e['tongue'][p]) for p in PARTS}
        cfg['lip_open'], cfg['lip_round'] = e['lip_open'], e['lip_round']
        ck, bk = [], []
        for name in names:
            try:
                mod = M.apply_mod(dict(cfg), name)
            except Exception:                    # noqa: BLE001
                continue
            cs = contour_sig(mod)
            bv = tuple(np.round([quantities(mod, s, e)[d] for d in dims], 9))
            ck.append((name, cs))
            bk.append((name, bv))
        if colliding_pairs(bk) - colliding_pairs(ck) > 0:
            affected += 1
        c_keys += ck
        b_keys += bk

    return {'basis': basis_name, 'dims': len(dims),
            'contour_pairs': colliding_pairs(c_keys),
            'basis_pairs': colliding_pairs(b_keys),
            'lost': colliding_pairs(b_keys) - colliding_pairs(c_keys),
            'bases_affected': affected, 'n_bases': len(contour)}


def main():
    targets = sys.argv[1:] or ['merged_basis.json', 'summary_root.json',
                                'summary_basis.json']
    rows = [audit(t) for t in targets]
    print('within-base modifier collisions (%d modifier choices per base)\n'
          % len(M.DISPLACE))
    print('  %-24s %5s %9s %7s %7s %6s'
          % ('basis', 'dims', 'contour', 'basis', 'lost', 'hit'))
    for r in rows:
        print('  %-24s %5d %9d %7d %7d %6d'
              % (r['basis'], r['dims'], r['contour_pairs'], r['basis_pairs'],
                 r['lost'], r['bases_affected']))
    best = min(rows, key=lambda r: r['lost'])
    print('\n  fewest lost distinctions: %s (%d lost over %d of %d bases)'
          % (best['basis'], best['lost'], best['bases_affected'],
             best['n_bases']))
    out = os.path.join(DATA, 'modifier_collisions.json')
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'modifiers': sorted(M.DISPLACE), 'rows': rows},
                           ensure_ascii=False, indent=1))
    print('wrote %s' % out)

    # The deployed basis must lose nothing. It asks whether projecting the
    # contour onto the basis's axes merges two modifiers that the full contour
    # keeps apart -- two modifiers that land on the same vector for the same
    # base segment are indistinguishable to vec2ipa, and no metric separates
    # them afterwards.
    #
    # The threshold is `bases_affected`, not `lost`: `lost` is a difference
    # (negative means the basis separates MORE pairs than the flat contour
    # does), so it is not a count of lost distinctions.
    #
    # Three earlier attempts to prove this fires all used changes too weak to
    # trigger it, which is why it was briefly left unwired:
    #   - making two modifiers identical collapses BOTH the contour and the
    #     basis, so the difference stays 0. That defect is real but is not this
    #     one's job; it belongs in review of the rule table.
    #   - dropping one axis changed nothing, because no modifier pair differs
    #     only in that axis.
    #   - passing a different basis name changed nothing at all.
    # What does trigger it is a basis narrow enough that modifiers differ only
    # outside the kept axes, and the script's own table already shows both ends
    # of that: the deployed merged_basis.json reports 0 affected and the
    # discarded 12-dim summary_root.json and 10-dim summary_basis.json both
    # report 133.
    deployed = [r for r in rows if r['basis'] == DEPLOYED]
    if not deployed:
        print('\n  %s was not audited -- pass it as an argument' % DEPLOYED)
        return 1
    r = deployed[0]
    # `lost` is a difference (negative means the contour separates MORE pairs
    # than the flat basis does), so the threshold is bases_affected -- how many
    # base segments actually have a modifier pair that collapses onto one
    # vector. The deployed basis is 0.
    if r['bases_affected']:
        print('\n  FAIL: the deployed basis collapses a modifier pair on %d '
              'base segments' % r['bases_affected'])
        return 1
    print('\n  OK: %s loses 0 distinctions across all %d base segments'
          % (DEPLOYED, r['n_bases']))
    return 0


if __name__ == '__main__':
    sys.exit(main())