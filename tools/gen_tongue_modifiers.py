"""Modifier layer as physical displacement of the tongue surface.

The old scheme writes coarticulation as sign flips on shared axes: palatalized
is `body +0.24`, velarized is `body -0.12`, labialized is `body -0.12` too and
leans on `lips_rounded` to stay distinguishable. Nothing in that says what the
tongue does.

Here every modifier is a displacement of the contour -- how much each part
moves, and where. Two consequences are checked below rather than assumed:

  1. The conditionals vanish. `dental` used to branch on `lips_closed` and
     `advanced` used to branch on `place`, because a single scalar could not
     hold two situations. A displacement needs no branch.
  2. The displacement vectors must be mutually distinguishable, or two
     modifiers still collapse into one another -- the defect being fixed.

Run: python tools/gen_tongue_modifiers.py
"""

import collections
import io
import json
import os

import gen_tongue_model as tm
import gen_tongue_table as tt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'data', 'tongue_modifiers.json')

TONGUE = tm.TONGUE

# dx/dy are displacements in the same units as the contour. An `=` prefix means
# an absolute placement rather than a delta: it says where the part goes, not
# how far it travels. Which one is correct depends on whether the modifier
# names a target region (`dental`) or a direction (`retracted`).
DISPLACE = {
    # --- secondary constriction: a second gesture on top of the primary one ---
    'palatalized': {'blade': (0.08, 0.35), 'dorsum': (-0.05, 0.05)},
    'velarized':   {'dorsum': (-0.18, 0.05), 'root': (0.02, 0.08)},
    'labialized':  {'dorsum': (-0.10, 0.08), 'tip': (-0.02, 0.05),
                    'lip_round': ('+=', 0.30)},
    'pharyngeal':  {'root': (0.14, 0.30), 'dorsum': (0.0, -0.08)},
    # --- tongue root ---
    'atr':         {'root': (-0.10, -0.08)},
    'rtr':         {'root': (0.10, 0.08)},
    # --- whole-tongue movement: uniform in x, which is what "advanced" means ---
    'advanced':    {'_all_x': -0.06},
    'retracted':   {'_all_x': +0.06},
    # --- where the tongue tip sits: absolute targets, they name a region ---
    'dental':      {'blade': ('=', 0.10, None), 'tip': ('=', 0.10, None)},
    'laminal':     {'blade': ('=', 0.20, None), 'tip': ('=', 0.16, None)},
    'apical':      {'tip': ('=', 0.24, None), 'blade': ('=', 0.22, None)},
    # --- shapes, not places ---
    # `centralized` scales the dorsum toward the centre, `midcent` places the
    # tip. The old table had them too (body*0.5 vs tip_shape=0.5); writing both
    # as a dorsum placement collapsed them into one, which the collision check
    # below caught.
    'centralized': {'dorsum': ('~', 0.33, 0.5)},
    # Kept as the absolute assignment. Changing it to a scale-to-centre was
    # justified by audit_modifier_visibility.py reporting 0.0000 on every base,
    # but that audit cannot separate the two: no segment's constriction sits at
    # the tip (constrictor counts are dorsum 63, blade 46, lips/larynx 19,
    # root 5, tip 0), so tip-only modifiers are invisible under BOTH forms.
    'midcent':     {'tip': ('=', 0.16, None)},
}

# The old rules branched on these; record which ones so the removal is visible.
OLD_CONDITIONALS = {
    'dental': 'lips_closed <= 0.5 -> place -0.6 else place -0.75',
    'advanced': "place != 0 or tip_shape >= 0.5 -> place -0.15 else body +0.15",
    'retracted': "place != 0 or tip_shape >= 0.5 -> place +0.15 else body -0.15",
    'rnd_more': '0.3 < lips_rounded < 0.7 -> snap 0.95 else +0.25',
    'rnd_less': '0.3 < lips_rounded < 0.7 -> snap 0.0 else -0.25',
}

SCALAR = {   # modifiers that are not tongue displacement
    'nasal':       {'velum': ('=', 0.6)},
    'nasal_rel':   {'velum': ('=', 0.8), 'duration': ('+=', 0.3)},
    'lat_release': {'lateral': ('=', 1.0), 'duration': ('+=', 0.3)},
    'nasal_click': {'velum': ('=', 1.0), 'periodic': ('=', 1.0),
                    'duration': ('=', 1.0)},
    'raised':      {'lip_open': ('-=', 0.10)},
    'lowered':     {'lip_open': ('+=', 0.10)},
    'rnd_more':    {'lip_round': ('+=', 0.25)},
    'rnd_less':    {'lip_round': ('-=', 0.25)},
    'long':        {'duration': ('=', 2.0)},
    'half':        {'duration': ('=', 1.5)},
    'extra_short': {'duration': ('=', 0.5)},
    'syllabic':    {'duration': ('+=', 0.5)},
    'unrel':       {'duration': ('=', 0.1)},
}


def clamp_cfg(cfg):
    """Keep the contour physical: no part above the roof, nothing off the tract.

    The scalar modifiers write velum, lateral, periodic, larynx, source_tilt and
    duration. This rebuilt the dict from the tongue points and the two lip
    fields alone, so every one of those writes was discarded on the way out and
    all 13 scalar modifiers were silent no-ops -- `nasal` set velum=0.6 and the
    result had no velum key at all. Carrying the non-tongue fields through is
    the fix; they are passed through unclamped because they are states, not
    coordinates, and clamping them here would be a second, different
    normalisation nobody asked for.
    """
    fixed = {k: v for k, v in cfg.items() if k not in TONGUE}
    for p in TONGUE:
        x, y = cfg[p]
        x = min(max(x, 0.02), 0.90)
        y = min(max(y, 0.0), tm.roof(x))
        fixed[p] = (x, y)
    fixed['lip_open'] = min(max(cfg['lip_open'], 0.0), 1.0)
    fixed['lip_round'] = min(max(cfg['lip_round'], -0.5), 1.0)
    return fixed


def base_config(seg='t'):
    row = json.load(io.open(tt.OUT, encoding='utf-8'))[seg]
    cfg = {p: tuple(row['tongue'][p]) for p in TONGUE}
    cfg['lip_open'] = row['lip_open']
    cfg['lip_round'] = row['lip_round']
    return cfg


def apply_mod(cfg, name):
    """Apply one modifier to a contour. Returns a new config."""
    out = dict(cfg)
    if name in SCALAR:
        for k, spec in SCALAR[name].items():
            if spec[0] == '=':
                out[k] = spec[1]
            elif spec[0] == '+=':
                out[k] = out[k] + spec[1]
            else:
                out[k] = out[k] - spec[1]
        return clamp_cfg(out)

    rule = DISPLACE[name]
    if '_all_x' in rule:
        dx = rule['_all_x']
        for p in TONGUE:
            out[p] = (out[p][0] + dx, out[p][1])
    for key, val in rule.items():
        if key.startswith('_') or key == 'lip_round':
            if key == 'lip_round' and val[0] == '+=':
                out['lip_round'] = out['lip_round'] + val[1]
            continue
        if val[0] == '=':
            x_new = val[1]
            y_new = val[2] if val[2] is not None else out[key][1]
            out[key] = (x_new, y_new)
        elif val[0] == '~':
            centre, k = val[1], val[2]
            x, y = out[key]
            out[key] = (centre + (x - centre) * k, y)
        else:
            dx, dy = val
            out[key] = (out[key][0] + dx, out[key][1] + dy)
    return clamp_cfg(out)


def dist(a, b):
    return sum((a[p][0] - b[p][0]) ** 2 + (a[p][1] - b[p][1]) ** 2
               for p in TONGUE) ** 0.5


def main():
    print('== conditionals in the old scheme that disappear ==')
    for m, why in OLD_CONDITIONALS.items():
        keep = m in DISPLACE or m in SCALAR
        note = ('DISPLACE needs no branch: it names a displacement'
                if m in DISPLACE else 'SCALAR is a monotone +/- on one field')
        print('  %-11s %-56s -> %s' % (m, why, note))

    print('\n== are the 14 displacement vectors mutually distinguishable? ==')
    base = base_config('t')
    names = sorted(DISPLACE)
    vecs = {n: apply_mod(base, n) for n in names}
    pairs = sorted(((dist(vecs[a], vecs[b]), a, b)
                    for i, a in enumerate(names) for b in names[i + 1:]))
    collisions = [(a, b) for d, a, b in pairs if d < 1e-6]
    for d, a, b in pairs[:5]:
        print('  closest: %-12s %-12s d = %.4f' % (a, b, d))
    print('  %d pairs total, %d exact collisions' % (len(pairs), len(collisions)))
    if collisions:
        print('  COLLIDING: %s' % ', '.join('%s/%s' % c for c in collisions[:6]))

    print('\n== does the same modifier stay distinct on a different base? ==')
    for base_seg in ['t', 'k', 'ʈ', 's']:
        b = base_config(base_seg)
        v = {n: apply_mod(b, n) for n in names}
        worst = min((dist(v[a], v[c]), a, c)
                    for i, a in enumerate(names) for c in names[i + 1:])
        print('  base %-3s  min pairwise d = %.4f  (%s/%s)'
              % (base_seg, worst[0], worst[1], worst[2]))

    print('\n== do double articulations fall out of two modifiers? ==')
    for label, mods in [('k͡p  velar + labialized', ['labialized']),
                        ('ŋ͡m  velar + nasal', ['nasal']),
                        ('tʲ  alveolar + palatalized', ['palatalized']),
                        ('ɧ   postalveolar + velarized', ['velarized'])]:
        cfg = base_config('k' if 'velar' in label else 't')
        for m in mods:
            cfg = apply_mod(cfg, m)
        print('  %-32s blade=(%.2f,%.2f) dorsum=(%.2f,%.2f)'
              % (label, cfg['blade'][0], cfg['blade'][1],
                 cfg['dorsum'][0], cfg['dorsum'][1]))

    def pack(v):
        if isinstance(v, (int, float, str)):
            return v
        return list(v)

    out = {'displacements': {n: {k: pack(v) for k, v in DISPLACE[n].items()}
                             for n in DISPLACE},
           'scalar': {n: {k: pack(v) for k, v in SCALAR[n].items()}
                      for n in SCALAR}}
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()
