"""Tongue-contour model, step 1: 13 place anchors + vowel quadrilateral.

Replaces the hand-set `place` chain with a sagittal tongue contour: four parts
(tip, blade, dorsum, root), each with a front/back position and a height. The
constriction is no longer stored -- it is derived, as the point where the
tongue comes closest to the roof of the mouth.

Frame
  x  anterior -> posterior, 0 = behind the upper incisors, 1 = pharyngeal wall
  y  height, 0 = resting tongue, 1 = contact with the roof

What this script actually tests
  Authoring the 13 anchors from tongue anatomy guarantees the derived ORDER is
  right -- that part is not a test. The falsifiable claim is EQUAL STEPS: a
  chain-neutral place axis requires adjacent anchors to sit at even distance
  apart. That depends on the palate reference curve, not on authoring, so it
  can fail.

Run: python tools/gen_tongue_model.py
"""

import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'data', 'tongue_model.json')

TONGUE = ['tip', 'blade', 'dorsum', 'root']

# Roof of the mouth and pharyngeal wall, sampled at the knots below. This is
# the anatomical input the whole test rests on: without it a "derived place" is
# just a restatement of the coordinates we authored.
PALATE_KNOTS = [
    (0.00, 0.95),   # just behind the upper incisors
    (0.10, 0.62),   # alveolar ridge: the roof drops toward the teeth
    (0.18, 0.85),   # post-alveolar
    (0.32, 1.00),   # hard palate peak
    (0.45, 0.86),   # soft palate
    (0.55, 0.60),   # uvula
    (0.62, 0.15),   # velopharyngeal port: no roof at all
    (0.70, 0.62),   # pharyngeal wall
    (0.80, 0.78),   # lower pharynx
    (0.90, 0.45),   # larynx
]

REST = {'tip': (0.20, 0.15), 'blade': (0.24, 0.20), 'dorsum': (0.33, 0.28),
        'root': (0.72, 0.25), 'lip_open': 0.50, 'lip_round': 0.0}


def roof(x):
    """Roof height at x, linear between knots."""
    if x <= PALATE_KNOTS[0][0]:
        return PALATE_KNOTS[0][1]
    for (x0, y0), (x1, y1) in zip(PALATE_KNOTS, PALATE_KNOTS[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return PALATE_KNOTS[-1][1]


def derived_constriction(cfg):
    """Where the tract is most closed, and how much.

    Closeness is the GAP to the local roof, roof(x) - h, in the same absolute
    units as h. The roof is not flat: contact at the alveolar ridge sits at
    h=0.62, contact at the hard palate peak at h=1.00, so heights must be
    authored against the curve rather than as fractions of it.

    Returns (x, gap, part). gap = 0 is contact. Nothing in the input names the
    constriction -- it falls out of the geometry.
    """
    best = None
    for part in TONGUE:
        x, h = cfg[part]
        gap = roof(x) - h
        if best is None or gap < best[1]:
            best = (x, gap, part)
    # A closed lip outranks any tongue part: bilabial closure is the most
    # closed event in the tract and it is not a tongue gesture at all.
    if cfg['lip_open'] <= 0.05 and (best is None or 0.0 < best[1]):
        best = (0.0, 0.0, 'lips')
    return best


def chain(c):
    """Every (part, x, y) sample of the tongue surface, front to back."""
    return sorted((cfg[p], p) for p in TONGUE)


# --- the 13 place anchors, authored from articulation, not from place values ---
ANCHORS = [
    # name,          place,  constrictor description
    ('bilabial',     -0.90, 'lips close; tongue at rest'),
    ('labiodental',  -0.75, 'lower lip to upper teeth; tongue at rest'),
    ('dental',       -0.60, 'blade against the back of the upper teeth'),
    ('alveolar',     -0.45, 'blade at the alveolar ridge'),
    ('postalveolar', -0.30, 'blade just behind the ridge'),
    ('palatoalveol', -0.15, 'blade at the front of the hard palate'),
    ('retroflex',     0.00, 'tip retracted and lowered; blade raised behind it'),
    ('palatal',       0.15, 'front of the dorsum raised to the hard palate'),
    ('velar',         0.30, 'back of the dorsum raised to the velum'),
    ('uvular',        0.45, 'dorsum raised and retracted past the velum'),
    ('pharyngeal',    0.60, 'tongue root raised to the pharyngeal wall'),
    ('epiglottal',    0.75, 'root retracted and raised onto the epiglottis'),
    ('glottal',       0.90, 'no tongue constriction; root retracted, no contact'),
]

# Contact heights are roof(x) at the author's x -- written out so the curve is
# load-bearing rather than assumed. Every non-contacting part sits below it.
ANCHOR_CFG = {
    'bilabial':     {'tip': (0.20, 0.15), 'blade': (0.24, 0.20), 'dorsum': (0.33, 0.28), 'root': (0.72, 0.25), 'lip_open': 0.00, 'lip_round': 0.0},
    'labiodental':  {'tip': (0.20, 0.18), 'blade': (0.24, 0.24), 'dorsum': (0.33, 0.28), 'root': (0.72, 0.25), 'lip_open': 0.15, 'lip_round': 0.0},
    'dental':       {'tip': (0.10, 0.30), 'blade': (0.10, 0.62), 'dorsum': (0.33, 0.28), 'root': (0.72, 0.25), 'lip_open': 0.30, 'lip_round': 0.0},
    'alveolar':     {'tip': (0.15, 0.28), 'blade': (0.18, 0.85), 'dorsum': (0.33, 0.28), 'root': (0.72, 0.25), 'lip_open': 0.35, 'lip_round': 0.0},
    'postalveolar': {'tip': (0.19, 0.25), 'blade': (0.25, 0.925), 'dorsum': (0.33, 0.30), 'root': (0.72, 0.25), 'lip_open': 0.35, 'lip_round': 0.0},
    'palatoalveol': {'tip': (0.20, 0.22), 'blade': (0.30, 0.979), 'dorsum': (0.33, 0.35), 'root': (0.72, 0.25), 'lip_open': 0.32, 'lip_round': 0.0},
    'retroflex':    {'tip': (0.30, 0.20), 'blade': (0.28, 0.60), 'dorsum': (0.33, 0.28), 'root': (0.72, 0.25), 'lip_open': 0.35, 'lip_round': 0.0},
    'palatal':      {'tip': (0.18, 0.22), 'blade': (0.30, 0.55), 'dorsum': (0.36, roof(0.36)), 'root': (0.72, 0.25), 'lip_open': 0.32, 'lip_round': 0.0},
    'velar':        {'tip': (0.20, 0.12), 'blade': (0.24, 0.15), 'dorsum': (0.45, 0.86), 'root': (0.72, 0.28), 'lip_open': 0.35, 'lip_round': 0.0},
    'uvular':       {'tip': (0.20, 0.12), 'blade': (0.24, 0.15), 'dorsum': (0.52, 0.678), 'root': (0.72, 0.30), 'lip_open': 0.35, 'lip_round': 0.0},
    'pharyngeal':   {'tip': (0.20, 0.12), 'blade': (0.24, 0.15), 'dorsum': (0.40, 0.30), 'root': (0.70, 0.62), 'lip_open': 0.40, 'lip_round': 0.0},
    'epiglottal':   {'tip': (0.20, 0.12), 'blade': (0.24, 0.15), 'dorsum': (0.40, 0.30), 'root': (0.80, 0.78), 'lip_open': 0.42, 'lip_round': 0.0},
    'glottal':      {'tip': (0.22, 0.12), 'blade': (0.26, 0.15), 'dorsum': (0.40, 0.28), 'root': (0.66, 0.35), 'lip_open': 0.45, 'lip_round': 0.0},
}

# Anchors whose constriction is made by the tongue. Bilabial and labiodental
# are lip gestures and glottal has no constriction at all, so a tongue model
# legitimately says nothing about them -- that is a result, not a gap.
TONGUE_ANCHORS = ['dental', 'alveolar', 'postalveolar', 'palatoalveol',
                  'palatal', 'velar', 'uvular', 'pharyngeal', 'epiglottal']

# Where the LIP constricts, for the two lip anchors. The tongue contour cannot
# carry this: with the tongue at rest the nearest point to the roof is the
# tongue ROOT at x=0.72, so scanning the contour for a lip segment reported the
# pharyngeal wall as the constriction site and a 0.402 aperture for every
# labiodental -- including the stop /p̪/, which then had no closure at all.
# /f/ measured 0.402 against the fricative profile's 0.14 for the same reason.
LIP_SITES = {'bilabial': (0.00, 0.00), 'labiodental': (0.05, 0.10)}

VOWELS = [
    # name, dorsum x, dorsum y, lip_round   (blade/tip/root stay near rest)
    ('i', 0.22, 0.62, -0.50), ('y', 0.22, 0.58, 1.00),
    ('e', 0.23, 0.50, 0.00), ('ø', 0.23, 0.48, 0.95),
    ('ɛ', 0.24, 0.34, 0.00), ('œ', 0.24, 0.32, 0.95),
    ('æ', 0.25, 0.22, 0.00), ('ɶ', 0.25, 0.20, 0.90),
    ('ɨ', 0.30, 0.58, 0.00), ('ʉ', 0.30, 0.56, 0.80),
    ('ɘ', 0.33, 0.46, 0.00), ('ɵ', 0.33, 0.44, 0.90),
    ('ɜ', 0.33, 0.32, 0.00), ('ɞ', 0.33, 0.30, 0.90),
    ('ɐ', 0.36, 0.17, 0.00),
    ('a', 0.38, 0.18, 0.00), ('ɒ', 0.38, 0.16, 0.80),
    ('ɑ', 0.42, 0.16, 0.00),
    ('ɯ', 0.44, 0.58, 0.00), ('ʊ', 0.44, 0.56, 0.70),
    ('ɤ', 0.38, 0.50, 0.00), ('o', 0.42, 0.48, 0.90),
    # ɔ was authored with lip_round 0.00, identical to ʌ, which made the two
    # share a contour and therefore a vector. Every other pair in this table
    # follows unrounded 0.00 / rounded 0.80-0.95 (i/y, e/ø, ɛ/œ, æ/ɶ, a/ɒ,
    # ɤ/o, ɘ/ɵ, ɜ/ɞ); this one line broke the pattern. 0.90 matches its
    # rounded neighbours o, ɵ and ɞ.
    ('ʌ', 0.42, 0.30, 0.00), ('ɔ', 0.42, 0.30, 0.90),
    ('u', 0.42, 0.60, 1.00),
    # ə, ɪ and ʏ were missing entirely, so they hit the caller's fallback --
    # which happens to be schwa's own coordinates -- and all three came out as
    # central unrounded vowels. They are authored here from the old table
    # rather than invented: lips_rounded gives the third column directly
    # (ə 0.500, ɪ -0.200, ʏ 0.900) and body places ə centrally (0.000) and
    # ɪ / ʏ at the near-front of the i-e line, which is where near-close sits
    # between i (0.22, 0.62) and e (0.23, 0.50).
    ('ɪ', 0.225, 0.56, -0.20), ('ʏ', 0.225, 0.56, 0.90),
    ('ə', 0.35, 0.46, 0.50),
]


def vowel_cfg(dx, dy, lr):
    cfg = dict(REST)
    cfg['dorsum'] = (dx, dy)
    cfg['tip'] = (0.20, 0.15 if dy < 0.30 else 0.22)
    cfg['blade'] = (0.24, 0.20 if dy < 0.30 else 0.30)
    cfg['lip_open'] = 0.15 if dy > 0.45 else 0.85
    cfg['lip_round'] = lr
    return cfg


def main():
    rows = []
    print('%-13s %6s %6s %8s  %s' % ('anchor', 'want', 'x_der', 'gap', 'via'))
    for name, place, note in ANCHORS:
        cfg = ANCHOR_CFG[name]
        x, gap, part = derived_constriction(cfg)
        rows.append({'name': name, 'want_place': place, 'derived_x': round(x, 4),
                     'gap': round(gap, 4), 'part': part, 'note': note,
                     'tongue_constricted': name in TONGUE_ANCHORS,
                     'coords': {p: list(cfg[p]) for p in TONGUE}})
        print('%-13s %6.2f %6.3f %8.3f  %s' % (name, place, x, gap, part))

    print('\n== derived step lengths, tongue-constricted anchors only ==')
    print('   (bilabial/labiodental are lip gestures; glottal has no '
          'constriction -- the tongue model is silent on all three)')
    by_name = {r['name']: r for r in rows}
    chain_order = sorted(TONGUE_ANCHORS,
                         key=lambda n: by_name[n]['want_place'])
    steps = []
    for a, b in zip(chain_order, chain_order[1:]):
        d = abs(by_name[b]['derived_x'] - by_name[a]['derived_x'])
        steps.append(d)
        print('  %-13s -> %-13s dx = %.4f' % (a, b, d))
    mn, mx = min(steps), max(steps)
    mean = sum(steps) / len(steps)
    print('\n  min %.4f  max %.4f  mean %.4f  ratio %.2f'
          % (mn, mx, mean, mx / mn))
    print('  chain-neutral requires ratio 1.00; v8 was 12.5')

    print('\n== does the derived order match the stored place order? ==')
    ok = all(by_name[a]['derived_x'] < by_name[b]['derived_x']
             for a, b in zip(chain_order, chain_order[1:]))
    print('  %s' % ('yes' if ok else 'NO'))

    print('\n== does the derived position order match the stored place order? ==')
    by_x = sorted(rows, key=lambda r: r['derived_x'])
    ok = [r['want_place'] for r in by_x] == sorted(r['want_place'] for r in rows)
    print('  %s' % ('yes' if ok else 'NO'))
    if not ok:
        print('  by derived x: %s' % [(r['name'], r['want_place']) for r in by_x])

    out = {
        'model': 'tongue-contour-15',
        'dims': ([p + '_' + c for p in TONGUE for c in ('x', 'y')]
                 + ['lip_open', 'lip_round']),
        'rest': {p: list(REST[p]) for p in TONGUE},
        'palate_knots': PALATE_KNOTS,
        'place_anchors': rows,
        'vowels': [{'name': n, 'coords': {p: list(vowel_cfg(dx, dy, lr)[p])
                                          for p in TONGUE},
                    'lip_open': vowel_cfg(dx, dy, lr)['lip_open'],
                    'lip_round': lr}
                   for n, dx, dy, lr in VOWELS],
    }
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()
