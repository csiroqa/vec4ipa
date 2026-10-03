"""Which multi-articulation modifiers actually move the deployed distance basis?

The base table holds 133 segments with no modifier field: secondary
articulation is applied at query time by gen_tongue_modifiers.py. A modifier
that displaces the tongue somewhere the basis does not measure is not merely
imprecise -- apply_mod leaves the vector bit-identical and the symbol
collapses onto its base. ATR and RTR did exactly that before root_x/root_y
were added back; this measures every modifier under the CURRENT basis so the
next collapse is found here rather than in a neighbour query.

The vector is rebuilt from a modified contour with the same code path the
basis uses, so the number is the deployed one, not an approximation.

Run: python tools/audit_modifier_visibility.py
"""

import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_merged_basis as B          # noqa: E402
import gen_tongue_modifiers as M             # noqa: E402
import gen_tongue_table as T                 # noqa: E402

DATA = B.DATA
BASIS = os.path.join(DATA, 'summary_root.json')
OUT = os.path.join(DATA, 'modifier_visibility.json')

PARTS = B.PARTS
LIP_SITES = B.LIP_SITES
NO_CONSTRICTION = B.NO_CONSTRICTION

# Below this the modifier is invisible: the symbol is the same point in the
# metric space, so a nearest-neighbour query cannot tell it from its base.
# 1e-6 is exact-equality tolerance, not a tuned threshold.
INVISIBLE = 1e-6

BASES = ['k', 't', 'l', 'i', 's', 'm']


def vector_for(cfg, anchor, manner):
    """Rebuild the deployed summary vector from a contour, exactly as
    gen_merged_basis.py does."""
    if anchor == 'vowel':
        part, origin = 'dorsum', 'assigned'
        site_x = cfg['dorsum'][0]
        gap = B.tm.roof(site_x) - cfg['dorsum'][1]
    elif anchor in LIP_SITES:
        part, origin = 'lips', 'assigned'
        site_x, gap = LIP_SITES[anchor]
    else:
        site_x, gap, part, origin = T.derived_site(cfg, anchor, manner)
    pos = NO_CONSTRICTION if site_x is None else site_x
    return np.array([pos, gap, cfg['lip_open'], cfg['lip_round']], float)


def base_cfg(entry):
    cfg = {p: tuple(entry['tongue'][p]) for p in PARTS}
    cfg['lip_open'] = entry['lip_open']
    cfg['lip_round'] = entry['lip_round']
    return cfg


def main():
    basis = json.load(io.open(BASIS, encoding='utf-8'))
    contour = json.load(io.open(os.path.join(DATA, 'tongue_table.json'),
                                encoding='utf-8'))
    dims = basis['dims']
    ip, ig = dims.index('constriction_pos'), dims.index('constriction_gap')
    iro_x = dims.index('root_x')
    iro_y = dims.index('root_y')

    def full(cfg, anchor, manner):
        v = vector_for(cfg, anchor, manner)
        return np.concatenate([v, [cfg['root'][0], cfg['root'][1]]])

    rows = []
    for name in sorted(M.DISPLACE):
        per = {}
        for base in BASES:
            e = contour[base]
            cfg = base_cfg(e)
            try:
                mod = M.apply_mod(dict(cfg), name)
            except Exception as exc:                     # noqa: BLE001
                per[base] = {'error': str(exc)}
                continue
            d = float(np.linalg.norm(full(mod, e['anchor'], e['manner'])
                                     - full(cfg, e['anchor'], e['manner'])))
            per[base] = {'distance': d, 'invisible': bool(d < INVISIBLE)}
        dists = [v['distance'] for v in per.values() if 'distance' in v]
        rows.append({'modifier': name,
                     'min_distance': min(dists) if dists else None,
                     'max_distance': max(dists) if dists else None,
                     'invisible_on': [b for b, v in per.items()
                                      if v.get('invisible')],
                     'per_base': per})

    rows.sort(key=lambda r: (r['min_distance'] is None,
                             r['min_distance']))
    print('deployed basis: %s (%d dims)' % (os.path.basename(BASIS), len(dims)))
    print('modifier visibility across bases %s\n' % ' '.join(BASES))
    print('  %-13s %8s %8s  %s' % ('modifier', 'min d', 'max d', 'invisible on'))
    for r in rows:
        if r['min_distance'] is None:
            print('  %-13s %8s %8s  %s'
                  % (r['modifier'], '-', '-', 'ERROR on every base'))
            continue
        print('  %-13s %8.4f %8.4f  %s'
              % (r['modifier'], r['min_distance'], r['max_distance'],
                 ', '.join(r['invisible_on']) or '-'))

    dead = [r['modifier'] for r in rows if r['invisible_on']]
    print('\n%s' % ('modifiers that collapse onto their base somewhere: %s'
                    % ', '.join(dead) if dead else
                    'every modifier moves the deployed basis on every base'))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'basis': os.path.basename(BASIS),
                            'bases': BASES, 'invisible_tol': INVISIBLE,
                            'modifiers': rows}, ensure_ascii=False, indent=1))
    print('wrote %s' % OUT)


if __name__ == '__main__':
    main()