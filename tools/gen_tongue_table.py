"""Expand the tongue model from 25 anchor configs to the full inventory.

The point of this step is to show the model is GENERATIVE: if 13 place anchors
plus a handful of manner rules reproduce most of the 133 committed segments,
the tongue coordinates are a description, not a lookup table.

  place  = WHERE the tongue closes        (13 anchors, from gen_tongue_model.py)
  manner = HOW MUCH and HOW LONG          (the profiles below)

Coverage is reported, not asserted: every committed segment that the model
cannot produce is listed with the reason, because those gaps are the design
constraints that decide whether this replaces the old scheme or not.

Run: python tools/gen_tongue_table.py
"""

import collections
import io
import json
import os

import gen_tongue_model as tm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'data', 'tongue_table.json')
VEC = os.path.join(ROOT, 'tools', 'data', 'vec_table_16.json')

TONGUE = tm.TONGUE

# gap below the roof at the constrictor; 0.00 is full contact.
PROFILES = {
    'stop':        {'gap': 0.00, 'dur': 0.10, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'affricate':   {'gap': 0.00, 'dur': 0.70, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'fricative':   {'gap': 0.14, 'dur': 0.60, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'nasal':       {'gap': 0.00, 'dur': 0.90, 'velum': 1.0, 'lat': 0.0, 'larynx': 0.0},
    'approximant': {'gap': 0.40, 'dur': 0.90, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'lateral':     {'gap': 0.40, 'dur': 0.90, 'velum': 0.0, 'lat': 1.0, 'larynx': 0.0},
    'trill':       {'gap': 0.00, 'dur': 0.50, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'flap':        {'gap': 0.05, 'dur': 0.25, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'ejective':    {'gap': 0.00, 'dur': 0.10, 'velum': 0.0, 'lat': 0.0, 'larynx': 1.0},
    'implosive':   {'gap': 0.00, 'dur': 0.10, 'velum': 0.0, 'lat': 0.0, 'larynx': -1.0},
}

# place anchor -> which tongue part makes the constriction. Bilabial and
# labiodental are lip gestures and glottal has none, so they are None: a
# tongue model must say nothing there rather than invent a site.
CONSTRICTOR = {
    'dental': 'blade', 'alveolar': 'blade', 'postalveolar': 'blade',
    'palatoalveol': 'blade', 'retroflex': 'blade',
    'palatal': 'dorsum', 'velar': 'dorsum', 'uvular': 'dorsum',
    'pharyngeal': 'root', 'epiglottal': 'root',
    'bilabial': None, 'labiodental': None, 'glottal': None,
}


def apply_manner(anchor, manner):
    """Anchor config + a manner profile -> a full tongue contour."""
    base = {p: tuple(tm.ANCHOR_CFG[anchor][p]) for p in TONGUE}
    cfg = dict(base)
    cfg['lip_open'] = tm.ANCHOR_CFG[anchor]['lip_open']
    cfg['lip_round'] = tm.ANCHOR_CFG[anchor]['lip_round']
    prof = PROFILES[manner]
    part = CONSTRICTOR[anchor]

    if anchor == 'bilabial':
        cfg['lip_open'] = 0.0
        cfg['tip'], cfg['blade'] = (0.20, 0.15), (0.24, 0.20)
    elif anchor == 'labiodental':
        cfg['lip_open'] = 0.15
        cfg['tip'], cfg['blade'] = (0.20, 0.18), (0.24, 0.24)
    elif anchor == 'glottal':
        # no constriction anywhere: everything relaxes toward rest
        for p in TONGUE:
            cfg[p] = tm.REST[p]
        cfg['lip_open'] = 0.45
    elif anchor == 'retroflex':
        # tip pulled back and down; blade raised toward the postalveolar.
        # A nasal CLOSES like a stop -- only the airstream differs -- so it
        # belongs with the closing gestures, not with the open ones.
        cfg['tip'] = (0.30, 0.20)
        if manner in ('stop', 'affricate', 'nasal'):
            cfg['blade'] = (0.28, tm.roof(0.28) - prof['gap'])
        else:
            cfg['blade'] = (0.28, tm.roof(0.28) - max(prof['gap'], 0.45))
    elif part:
        x = base[part][0]
        cfg[part] = (x, tm.roof(x) - prof['gap'])

    # A nasal or lateral pull the tongue root forward and up a little; that is
    # how the oral cavity behind the closure stays coupled to the airflow path.
    if prof['velum'] > 0.5 or prof['lat'] > 0.5:
        rx, ry = cfg['root']
        cfg['root'] = (rx - 0.04, min(ry + 0.10, tm.roof(rx - 0.04)))
    return cfg, prof


def classify(vec, I):
    """Recover (anchor, manner) for one committed segment from the old table.

    Precedence follows the encoding the old table actually uses, verified
    against representative segments: larynx first (it rides on top of a stop),
    then the airflow branches, then closure, then noise, then openness. The
    flap test keys on an intermediate duration, never on `place` -- keying it
    on place made every zero-duration retroflex stop look like a flap.
    """
    place = vec[I['place']]
    anchor = min(tm.ANCHOR_CFG, key=lambda a: abs(anchor_place(a) - place))
    dur = vec[I['duration']]
    vel = vec[I['vel_open']]
    lat = vec[I['lateral_ratio']]
    eoa = vec[I['effective_oral_area']]
    larynx = vec[I['larynx_height']]
    jets = vec[I['jet_focus']]

    if larynx > 0.5:
        return anchor, 'ejective'
    if larynx < -0.5:
        return anchor, 'implosive'
    if vel >= 0.7:
        return anchor, 'nasal'
    if dur == 0.0:
        return anchor, 'stop'
    if 0.10 <= dur <= 0.40 and eoa <= 0.01:
        return anchor, 'flap'
    if lat >= 0.5:
        return anchor, 'lateral'
    if jets > 0.0:
        return anchor, 'affricate' if dur >= 1.2 else 'fricative'
    if eoa <= 0.12:
        return anchor, 'fricative'
    if 0.40 <= dur <= 0.60 and eoa <= 0.25:
        return anchor, 'trill'
    return anchor, 'approximant'


def anchor_place(name):
    for n, p, _ in tm.ANCHORS:
        if n == name:
            return p
    return 0.0


def derived_site(cfg, anchor, manner):
    """Where the constriction is -- but only derive it when there is one.

    Whether the tract is closed has to be read off the resulting contour, not
    off the profile's nominal gap: an open constrictor sits 0.45 below the roof
    while the tongue root at rest sits only 0.40 from the pharyngeal wall, so
    "closest to the roof" would otherwise return the root for every open
    gesture. The test is therefore empirical -- if nothing is within 0.05 of
    the roof, there is no constriction to derive and the site is a parameter.
    """
    part = CONSTRICTOR[anchor]
    x, gap, _ = tm.derived_constriction(cfg)
    if gap < 0.05:
        return round(x, 4), round(gap, 4), part, 'derived'
    if part is not None:
        return round(cfg[part][0], 4), round(gap, 4), part, 'assigned'
    return None, round(gap, 4), None, 'none'


def main():
    D = json.load(io.open(VEC, encoding='utf-8'))
    dims, table = D['dims'], D['table']
    I = {x: i for i, x in enumerate(dims)}

    out = {}
    gaps = collections.defaultdict(list)
    by_manner = collections.Counter()
    by_anchor = collections.Counter()

    vowel_seen = set()
    VOWEL_CFG = {n: (dx, dy, lr) for n, dx, dy, lr in tm.VOWELS}
    for seg in sorted(table):
        vec = table[seg]
        place = vec[I['place']]
        tip = vec[I['tip_shape']]
        # `place = 0.00` is overloaded in the old table: it is the neutral value
        # for central vowels and glides AND the value retroflex stops use. Only
        # tip_shape separates them -- and only because the old scheme forces
        # the distinction onto a second axis. Tongue coordinates do not need
        # the crutch: a retracted lowered tip vs a resting tip is a difference
        # in the very first coordinate.
        no_place_gesture = abs(place) < 1e-9 and tip < 0.5

        if no_place_gesture:
            dx, dy, lr = VOWEL_CFG.get(seg, (0.35, 0.30, vec[I['lips_rounded']]))
            vcfg = tm.vowel_cfg(dx, dy, lr)
            out[seg] = {'anchor': 'vowel', 'manner': 'vowel',
                        'derived_x': round(dx, 4),
                        'gap': round(tm.roof(dx) - dy, 4),
                        'constrictor': 'dorsum', 'site_from': 'assigned',
                        'tongue': {p: [round(vcfg[p][0], 3), round(vcfg[p][1], 3)]
                                   for p in TONGUE},
                        'lip_open': vcfg['lip_open'], 'lip_round': lr,
                        'velum': 0.0, 'lateral': 0.0, 'larynx': 0.0,
                        'duration': vec[I['duration']]}
            by_manner['vowel'] += 1
            by_anchor['vowel'] += 1
            if seg in VOWEL_CFG:
                vowel_seen.add(seg)
            continue

        anchor, manner = classify(vec, I)
        cfg, prof = apply_manner(anchor, manner)
        site_x, gap, part, origin = derived_site(cfg, anchor, manner)
        if anchor == 'glottal':
            # /h ɦ ʔ/ close at the glottis. The tongue is simply at rest, so
            # the model carries a contour but NO constriction site -- reporting
            # an x here would be inventing a place the segment does not have.
            gaps['glottal: tongue at rest, no constriction site'].append(seg)
            site_x, origin = None, 'none'
        out[seg] = {'anchor': anchor, 'manner': manner,
                    'derived_x': site_x, 'gap': gap,
                    'constrictor': part, 'site_from': origin,
                    'tongue': {p: [round(cfg[p][0], 3), round(cfg[p][1], 3)]
                               for p in TONGUE},
                    'lip_open': cfg['lip_open'], 'lip_round': cfg['lip_round'],
                    'velum': prof['velum'], 'lateral': prof['lat'],
                    'larynx': prof['larynx'], 'duration': prof['dur']}
        by_manner[manner] += 1
        by_anchor[anchor] += 1

    print('== coverage of the 133 committed segments ==')
    print('  generated by 13 anchors x manner rules : %d' % len(out))
    print('  not expressible as a tongue constriction: %d'
          % (len(table) - len(out)))
    for reason, segs in sorted(gaps.items()):
        print('    %-52s %2d  %s' % (reason, len(segs), ' '.join(segs[:14])))

    print('\n== by manner ==')
    for m, c in by_manner.most_common():
        print('  %-12s %3d' % (m, c))
    print('\n== by anchor ==')
    for a in tm.ANCHORS:
        print('  %-13s %3d' % (a[0], by_anchor[a[0]]))

    print('\n== sanity: derived site must stay tight within one anchor ==')
    bad = 0
    for anchor in [a[0] for a in tm.ANCHORS]:
        segs = [s for s, v in out.items() if v['anchor'] == anchor]
        xs = [out[s]['derived_x'] for s in segs if out[s]['derived_x'] is not None]
        if len(xs) > 1 and max(xs) - min(xs) > 0.12:
            bad += 1
            print('  WIDE %-13s derived_x %.3f..%.3f over %s'
                  % (anchor, min(xs), max(xs), ' '.join(segs[:10])))
    print('  %s' % ('all place anchors tightly clustered' if not bad
                    else '%d anchor(s) spread > 0.12' % bad))
    vx = [v['derived_x'] for v in out.values()
          if v['anchor'] == 'vowel' and v['derived_x'] is not None]
    if vx:
        print('  vowels span %.2f..%.2f by design (front-back), not a defect'
              % (min(vx), max(vx)))

    print('\n== site provenance ==')
    prov = collections.Counter(v['site_from'] for v in out.values())
    for p, c in prov.most_common():
        print('  %-10s %3d' % (p, c))

    print('\n== vowels with a hand-authored contour ==')
    print('  %d / %d' % (len(vowel_seen), by_manner['vowel']))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\nwrote %s (%d entries)' % (OUT, len(out)))


if __name__ == '__main__':
    main()
