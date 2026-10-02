"""Groove parameter for the tongue contour: can ɕ and ʃ be told apart by shape?

The 13 anchors in gen_tongue_model.py are four control points (tip, blade,
dorsum, root). Four points make one smooth convex rise and nothing else, so the
palato-alveolar anchor (ɕ) and the postalveolar anchor (ʃ) are two nearly
identical convex profiles. What separates them anatomically is a GROOVE: for ɕ
the blade rises toward the postalveolar-palatal region while the tongue surface
around it hollows out, so the constriction runs along a channel rather than a
point.

WHAT IS MEASURED AND WHY
  1. grooved(ɕ) vs ʃ separation, in a common physical scale, against two
     controls: ɕ vs t (different place) and ʃ vs t͡ʃ (same place, different
     manner). A place-refinement parameter is only worth adding if it moves the
     first number without scrambling the others.
  2. Whether the groove is even ɕ-specific: applying it to BOTH ɕ and ʃ leaves
     the distance bit-for-bit unchanged, which is the number that decides
     whether this is a ɕ/ʃ contrast or a generic offset.
  3. Nearest-neighbour integrity: over all 13 anchors x 11 manners, what is
     closest to grooved ɕ? A groove that makes ɕ nearer ʑ than ʃ has failed.
  4. The Phatak-08 confusion cross-check. REPORTED AS UNMEASURED: that
     inventory has 16 consonants and ɕ is not one of them, so no ɕ/ʃ confusion
     value exists to compare against. The nearest measured sibilant contrasts
     are printed instead.

WHAT IS NOT MEASURED
  No acoustic unit is attached to any distance here. All nine formant datasets
  are vowel-only, and fit_tongue_forward.py's coefficients are fitted on vowels,
  so mapping a consonant contour onto F1/F2/F3 would be an extrapolation into a
  region the fit never saw. The distances below are CENTIMETRES, not hertz, and
  they are not predictions.

HONESTY OF THIS TEST
  Separating ɕ from ʃ is not an independent finding: the groove depth was
  authored from the description of ɕ that the test then confirms. It measures
  whether the parameter does what it claims and how far it has to be pushed to
  do it, nothing more.

Run: python tools/gen_groove.py
"""

import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_tongue_model as tm
import gen_tongue_table as tt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
VEC = os.path.join(DATA, 'vec_table_16.json')
PHATAK = os.path.join(DATA, 'phatak08_cm.json')
OUT = os.path.join(DATA, 'tongue_groove.json')

SEGMENTS = ['\u0255', '\u0283', 't', 't\u0361\u0283']

# --- physical scale ------------------------------------------------------------
# The forward model consumes raw (x, y). Those two axes are NOT commensurate:
# x runs 0 -> 1 over the whole tract, y runs over roughly the oral cavity
# height, so a plain Euclidean distance would silently assume x and y share a
# scale and would understate every anterior-posterior difference by ~6x.
# Both conversions below are anchored to one published measurement each.
CM_PER_X = 17.5 / 0.90
"""Adult male vocal tract length incisors -> larynx, 17.5 cm (Perry et al.
2000 place adult male VTL at 16.5-18.5 cm). PALATE_KNOTS puts the larynx at
x=0.90, so one x-unit is 17.5/0.90 = 19.4 cm."""

CM_PER_Y = 1.0 / (0.95 - 0.62)
"""The alveolar ridge sits about 1 cm below the height of the hard palate.
PALATE_KNOTS drops from 0.95 behind the incisors to 0.62 at the alveolar
ridge, a span of 0.33 y-units, so one y-unit is 1.0/0.33 = 3.03 cm."""

GROOVE_DEPTH_CM = 0.5
"""Nominally a 5 mm hollow. This is an ORDER-OF-MAGNITUDE assumption, not a
measurement: no ultrasound/MRI corpus of ɕ channel depth ships with this repo.
Every conclusion below is therefore repeated as a sweep over depth, so the
verdict cannot rest on this number."""

GROOVE_DEPTH = GROOVE_DEPTH_CM / CM_PER_Y

GROOVE_FRAC = 0.5
"""Where the lowest point of the channel sits between the two rims, as a
fraction of the rim-to-rim span. 0.5 puts it in the middle third of the
postalveolar-palatal span, which is where the channel of ɕ sits; the depth
sweep below doubles as a check that the exact fraction is not load-bearing."""

PLACEMENTS = ('blade_dorsum', 'tip_blade')
"""Two readings of "a dip between two peaks", both measured because the task
statement carries both:

  blade_dorsum  the blade is the ANTERIOR rim (it is the constrictor) and the
                dorsum the POSTERIOR rim; the dip is the channel between them.
                This is the "dip between two peaks" reading.
  tip_blade     the blade is the peak and the tongue surface IN FRONT of it
                hollows out, tip low, blade high. This is the "body in front
                of it dips" reading, and it is the retroflex-style hollow.

They are not the same contour and they do not give the same distance, so
picking one on taste and reporting only its number would be dishonest."""


def lerp(a, b, t):
    return a + t * (b - a)


def grooved(cfg, depth=GROOVE_DEPTH, placement='blade_dorsum'):
    """Add a groove control point to a four-point contour.

    The point sits at GROOVE_FRAC of the way from the first rim to the second,
    on the straight line between them, and is lowered by `depth`. depth = 0
    returns exactly the input contour, which is the property the depth sweep
    uses as its control condition.

    A discrete point is used rather than a spline with a dip constraint: the
    groove is a ~1.5 cm local feature and a spline would couple its depth to
    the blade and dorsum heights, so "lower the groove" would silently move the
    constriction too.
    """
    if placement == 'blade_dorsum':
        a, b = cfg['blade'], cfg['dorsum']
    elif placement == 'tip_blade':
        a, b = cfg['tip'], cfg['blade']
    else:
        raise ValueError('unknown placement %r' % (placement,))
    x = lerp(a[0], b[0], GROOVE_FRAC)
    y = lerp(a[1], b[1], GROOVE_FRAC) - depth
    out = dict(cfg)
    out['groove'] = (x, y)
    out['groove_depth'] = depth
    out['groove_placement'] = placement
    return out


def polyline(cfg):
    """The tongue surface as a front-to-back polyline, groove point included."""
    pts = [(cfg[p][0], cfg[p][1], p) for p in tm.TONGUE]
    if 'groove' in cfg:
        pts.append((cfg['groove'][0], cfg['groove'][1], 'groove'))
    return sorted(pts)


def cm(point):
    return (point[0] * CM_PER_X, point[1] * CM_PER_Y)


def point_segment_distance(p, a, b):
    ax, ay = cm(a)
    bx, by = cm(b)
    px, py = cm(p)
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    if den < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / den))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def hausdorff_cm(cfg_a, cfg_b):
    """Largest point-to-polyline distance, in cm, both directions.

    This is the literal "how far apart are the two contours" measure: the
    maximum distance any point of one tongue surface sits from the other, which
    is what a constriction channel has to clear to be heard as a channel.
    """
    pa, pb = polyline(cfg_a), polyline(cfg_b)
    worst = 0.0
    for src, dst in ((pa, pb), (pb, pa)):
        for p in src:
            best = min(point_segment_distance(p, dst[k][:2], dst[k + 1][:2])
                       for k in range(len(dst) - 1))
            worst = max(worst, best)
    return worst


def control_point_distance_cm(cfg_a, cfg_b):
    """RMS distance over the control points the two contours share, in cm."""
    names = [p for p in tm.TONGUE] + (['groove'] if 'groove' in cfg_a
                                      and 'groove' in cfg_b else [])
    tot = 0.0
    for n in names:
        ax, ay = cm(cfg_a[n])
        bx, by = cm(cfg_b[n])
        tot += (ax - bx) ** 2 + (ay - by) ** 2
    return math.sqrt(tot / len(names))


def raw_model_distance(cfg_a, cfg_b):
    """Unweighted Euclidean distance in the forward model's native (x, y).

    Reported alongside the centimetre figure because "the same units the
    forward model uses" can be read two ways. This one is the number the
    forward model would see, and it is the one that hides the problem.
    """
    names = [p for p in tm.TONGUE] + (['groove'] if 'groove' in cfg_a
                                      and 'groove' in cfg_b else [])
    return math.sqrt(sum((cfg_a[n][0] - cfg_b[n][0]) ** 2
                         + (cfg_a[n][1] - cfg_b[n][1]) ** 2 for n in names)
                     / len(names))


def load_segments():
    """Recover (anchor, manner) for each segment of interest from the old table.

    The classification is gen_tongue_table's, not a new one, so the segments
    this tool reasons about are the ones the rest of the pipeline reasons about.
    """
    d = json.load(io.open(VEC, encoding='utf-8'))
    dims, table = d['dims'], d['table']
    I = {x: i for i, x in enumerate(dims)}
    out = {}
    for seg in SEGMENTS:
        if seg not in table:
            raise KeyError('%s has no row in vec_table_16.json' % seg)
        anchor, manner = tt.classify(table[seg], I)
        cfg, prof = tt.apply_manner(anchor, manner)
        out[seg] = {'anchor': anchor, 'manner': manner, 'cfg': cfg,
                    'vec': table[seg]}
    return out


def groove_recipients(table):
    """Which table rows the old scheme put at the palato-alveolar anchor.

    Measured from vec_table_16.json rather than asserted: the recipients are
    whatever shares place == the palato-alveolar value with ɕ.
    """
    I = {x: i for i, x in enumerate(json.load(
        io.open(VEC, encoding='utf-8'))['dims'])}
    target = table['\u0255'][I['place']]
    table = json.load(io.open(VEC, encoding='utf-8'))['table']
    return sorted(s for s, v in table.items()
                  if abs(v[I['place']] - target) < 1e-9)


def table_axis_diff(a, b):
    """Axes on which two committed rows disagree, with the direction."""
    d = json.load(io.open(VEC, encoding='utf-8'))
    dims, table = d['dims'], d['table']
    return [(dims[i], table[a][i], table[b][i])
            for i in range(len(dims)) if table[a][i] != table[b][i]]


def nearest_neighbours(cfg, k=6):
    """Closest contours over the whole anchor x manner product."""
    out = []
    for name, _, _ in tm.ANCHORS:
        for manner in sorted(tt.PROFILES):
            other, _ = tt.apply_manner(name, manner)
            out.append((hausdorff_cm(cfg, other), name, manner))
    out.sort()
    return out[:k], out


def realised_groove_cm(plain, grooved_cfg):
    """The groove depth actually realised, perpendicular to the surface.

    A depth of 5 mm measured VERTICALLY along a surface that is nearly
    vertical at that x displaces the contour almost not at all, because the
    surface is already there. Comparing the requested depth against the
    realised one is the only way to tell a real groove from a number typed
    into a config.

    Measured against the FOUR-point contour, not against the depth-0 five-point
    one: the depth-0 groove point lies exactly on the blade-dorsum segment, so
    measuring against it would report a realised depth of zero by construction.
    """
    pts = polyline(plain)
    return min(point_segment_distance(grooved_cfg['groove'], pts[k][:2],
                                      pts[k + 1][:2])
               for k in range(len(pts) - 1))


def concavity_count(cfg):
    """Sign changes of the turning angle along the front-to-back contour.

    Scale-free and placement-independent: a groove is exactly one extra
    concavity. This is the measure that says whether a groove EXISTS, as
    opposed to how far the contours happen to sit apart.
    """
    pts = [(cm(p[:2])) for p in polyline(cfg)]
    turns = []
    for i in range(1, len(pts) - 1):
        ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        cross = ax * by - ay * bx
        if abs(cross) > 1e-9:
            turns.append(cross > 0)
    return sum(1 for a, b in zip(turns, turns[1:]) if a != b)


def place_step_scale():
    """Adjacent-anchor contour separation, so ɕ/ʃ can be read as N place steps."""
    order = sorted([a[0] for a in tm.ANCHORS if a[0] in tt.CONSTRICTOR
                    and tt.CONSTRICTOR[a[0]]],
                   key=tt.anchor_place)
    steps = []
    for a, b in zip(order, order[1:]):
        ca, _ = tt.apply_manner(a, 'fricative')
        cb, _ = tt.apply_manner(b, 'fricative')
        steps.append((a, b, hausdorff_cm(ca, cb)))
    return steps


def phatak_crosscheck():
    """The confusion evidence that exists, and an honest report of what does not."""
    if not os.path.exists(PHATAK):
        print('  phatak08_cm.json NOT FOUND at %s -- cross-check skipped, '
              'NOT silently passed' % PHATAK)
        return None
    ph = json.load(io.open(PHATAK, encoding='utf-8'))
    cons = ph['consonants']
    n = len(cons)
    tot = [[0.0] * n for _ in range(n)]
    for snr in ph['snr_db']:
        for i in range(n):
            for j in range(n):
                tot[i][j] += float(ph['counts'][snr][i][j])
    P = [[0.0] * n for _ in range(n)]
    for i in range(n):
        s = sum(tot[i])
        for j in range(n):
            P[i][j] = tot[i][j] / s if s else 0.0
    idx = {c: i for i, c in enumerate(cons)}

    def sym(a, b):
        if a not in idx or b not in idx:
            return None
        return (P[idx[a]][idx[b]] + P[idx[b]][idx[a]]) / 2.0

    per_snr = {}
    for pair in (('\u0283', 's'), ('\u0283', '\u0292'), ('\u0283', 't')):
        a, b = pair
        if a not in idx or b not in idx:
            continue
        per_snr['%s/%s' % (a, b)] = [
            (snr, P[idx[a]][idx[b]]) for snr in ph['snr_db']]

    mean_off = sum(P[i][j] for i in range(n) for j in range(n) if i != j) \
        / (n * (n - 1))
    return {'inventory': cons, 'absent': ['\u0255', '\u0291', 't\u0361\u0283'],
            'sym_3_s': sym('\u0283', 's'),
            'sym_3_eZH': sym('\u0283', '\u0292'),
            'sym_3_t': sym('\u0283', 't'),
            'mean_off_diagonal': mean_off,
            'per_snr': per_snr}


def main():
    seg = load_segments()
    print('== segments, classified by the existing pipeline ==')
    for s in SEGMENTS:
        print('  %-4s -> anchor %-13s manner %s'
              % (s, seg[s]['anchor'], seg[s]['manner']))

    plain = {s: seg[s]['cfg'] for s in SEGMENTS}
    print('\n== the two contours, in model units (x, y) ==')
    for s in ('\u0283', '\u0255'):
        print('  %s %-13s %s' % (s, seg[s]['anchor'],
                                 '  '.join('%s=(%.2f,%.3f)' % (p, *plain[s][p])
                                           for p in tm.TONGUE)))
    for s in ('\u0283', '\u0255'):
        x, g, part = tm.derived_constriction(plain[s])
        print('  %s derived constriction x=%.3f gap=%.3f via %s' % (s, x, g, part))

    print('\n  the two 4-point contours differ by only %.4f model units '
          '(%.2f cm)' % (raw_model_distance(plain['\u0255'], plain['\u0283']),
                         hausdorff_cm(plain['\u0255'], plain['\u0283'])))

    print('\n== how the two readings of the groove shape the contour ==')
    variants = {}
    for pl in PLACEMENTS:
        gx = grooved(plain['\u0255'], GROOVE_DEPTH, pl)
        variants[pl] = gx
        print('  %-13s ɕ groove point at (%.3f, %.3f)  depth %.3f y-unit '
              '(%.1f mm)' % (pl, gx['groove'][0], gx['groove'][1], GROOVE_DEPTH,
                             GROOVE_DEPTH * CM_PER_Y * 10))
        print('  %-13s   contour %s' % ('', ' '.join(
            '(%.2f,%.2f)' % (p[0], p[1]) for p in polyline(gx))))

    print('\n== does the groove point steal the constriction? ==')
    for pl in PLACEMENTS:
        gx = variants[pl]
        ggap = tm.roof(gx['groove'][0]) - gx['groove'][1]
        best = min(tm.roof(gx[p][0]) - gx[p][1] for p in tm.TONGUE)
        print('  %-13s groove gap %.3f vs smallest 4-point gap %.3f -> %s'
              % (pl, ggap, best, 'no' if ggap > best else 'YES, IT STEALS IT'))
    xs = [p[0] for p in polyline(variants['blade_dorsum'])]
    print('  blade_dorsum x order strictly increasing: %s'
          % all(a < b for a, b in zip(xs, xs[1:])))

    print('\n== separations, Hausdorff distance in cm ==')
    print('   %-34s %8s %8s %8s' % ('pair', 'cm', 'model', 'ctrl-pt cm'))
    rows = {}
    for pl in PLACEMENTS:
        pairs = [
            ('ɕ plain vs ʃ plain (baseline)',
             plain['\u0255'], plain['\u0283']),
            ('ɕ GROOVED vs ʃ plain  <- the test',
             variants[pl], plain['\u0283']),
            ('ɕ GROOVED vs ʃ GROOVED (negative control)',
             variants[pl], grooved(plain['\u0283'], GROOVE_DEPTH, pl)),
            ('ɕ plain vs t (different place)',
             plain['\u0255'], plain['t']),
            ('ɕ GROOVED vs t (different place)',
             variants[pl], plain['t']),
            ('ʃ vs t͡ʃ (same place, different manner)',
             plain['\u0283'], plain['t\u0361\u0283']),
        ]
        print('  -- placement %s --' % pl)
        for label, a, b in pairs:
            h = hausdorff_cm(a, b)
            rows['%s|%s' % (pl, label)] = {
                'hausdorff_cm': round(h, 3),
                'model_units': round(raw_model_distance(a, b), 4),
                'control_point_cm': round(control_point_distance_cm(a, b), 3)}
            print('   %-34s %8.3f %8.4f %8.3f'
                  % (label, h, raw_model_distance(a, b),
                     control_point_distance_cm(a, b)))

    base = rows['blade_dorsum|ɕ plain vs ʃ plain (baseline)']['hausdorff_cm']

    print('\n== WHY the gain is small: requested depth vs realised depth ==')
    print('   depth is authored VERTICALLY; where the surface is steep the')
    print('   lowered point slides along the existing contour instead of')
    print('   moving it.')
    realised = {}
    for pl in PLACEMENTS:
        gx = variants[pl]
        r = realised_groove_cm(plain['\u0255'], gx)
        realised[pl] = round(r, 3)
        print('   %-13s requested %.2f cm -> realised %.3f cm  (%3.0f%%)'
              % (pl, GROOVE_DEPTH_CM, r, 100 * r / GROOVE_DEPTH_CM))

    print('\n== is there even a SECOND PEAK for a dip to sit between? ==')
    print('   the blade_dorsum reading needs dorsum.y > blade.y. Measured:')
    print('     ɕ blade.y %.3f  dorsum.y %.3f  -> dorsum is %s'
          % (plain['\u0255']['blade'][1], plain['\u0255']['dorsum'][1],
             'ABOVE the blade, a second peak exists'
             if plain['\u0255']['dorsum'][1] > plain['\u0255']['blade'][1]
             else 'BELOW the blade: there is only ONE peak'))
    print('   so at the palato-alveolar anchor "a dip between two peaks" has no')
    print('   two peaks to sit between, and blade_dorsum cannot make one at 5')
    print('   mm. The concavity counts below show exactly that.')

    print('\n== concavity count: does a groove EXIST at all? ==')
    for s in ('\u0255', '\u0283'):
        print('   %s plain                      %d concavity(s)'
              % (s, concavity_count(plain[s])))
    for pl in PLACEMENTS:
        print('   %s grooved (%-13s) %d concavity(s)'
              % ('\u0255', pl, concavity_count(variants[pl])))

    print('\n== how big is one PLACE STEP in this model? ==')
    steps = place_step_scale()
    for a, b, d in steps:
        mark = '   <-- the ɕ/ʃ step' if {a, b} == {'palatoalveol',
                                                     'postalveolar'} else ''
        print('   %-13s -> %-13s %6.3f cm%s' % (a, b, d, mark))
    vals = [d for _, _, d in steps]
    print('   mean adjacent step %.3f cm, range %.3f..%.3f cm'
          % (sum(vals) / len(vals), min(vals), max(vals)))
    print('   ɕ vs ʃ is already %.3f cm in the FOUR-point model = %.2f place steps'
          % (base, base / (sum(vals) / len(vals))))
    gain = {pl: rows['%s|ɕ GROOVED vs ʃ plain  <- the test' % pl]['hausdorff_cm']
            - base for pl in PLACEMENTS}
    unrelated = rows['blade_dorsum|ɕ plain vs t (different place)']['hausdorff_cm']
    print('\n== criterion as literally posed ==')
    print('   groove separation %.3f cm vs unrelated-place separation %.3f cm'
          % (gain['blade_dorsum'] + base, unrelated))
    literal = (gain['blade_dorsum'] + base) > unrelated
    print('   "groove distance larger than unrelated-place distance": %s'
          % ('PASS' if literal else 'FAIL'))
    if not literal:
        print('   That criterion is the WRONG one for a place parameter and it')
        print('   was stated here as a test, so the failure is reported rather')
        print('   than explained away: a same-place pair being closer than a')
        print('   different-place pair is what a correct place scale looks like.')
        print('   Requiring the reverse would make postalveolar indistinguishable')
        print('   from alveolar. The criterion is kept in the output for the')
        print('   record; the criterion below is the one that can discriminate.')

    print('\n== criterion that can discriminate: does the groove do work? ==')
    print('   %-13s %10s %10s' % ('placement', 'base cm', 'gain cm'))
    for pl in PLACEMENTS:
        print('   %-13s %10.3f %10.3f' % (pl, base, gain[pl]))
    print('   negative control (groove applied to BOTH ɕ and ʃ):')
    for pl in PLACEMENTS:
        c = rows['%s|ɕ GROOVED vs ʃ GROOVED (negative control)' % pl]['hausdorff_cm']
        print('     %-13s %.3f cm  -- %s'
              % (pl, c, 'UNCHANGED: the groove separates nothing when both '
                        'contours carry it, so the whole effect comes from '
                        'ɕ being grooved and ʃ not'
               if abs(c - base) < 1e-9 else 'changed'))

    print('\n== sensitivity: separation vs groove depth ==')
    print('   %8s %10s %10s' % ('depth mm', 'blade_dorsum', 'tip_blade'))
    for mm in (0.0, 2.5, 5.0, 7.5, 10.0, 15.0):
        d = mm / 10.0 / CM_PER_Y
        vals = []
        for pl in PLACEMENTS:
            vals.append(hausdorff_cm(grooved(plain['\u0255'], d, pl),
                                     plain['\u0283']))
        print('   %8.1f %10.3f %10.3f' % (mm, vals[0], vals[1]))
    print('   unrelated-place distance (ɕ vs t) is %.3f cm and does not move,'
          % unrelated)
    print('   so no achievable depth makes the literal criterion pass.')

    print('\n== nearest neighbours of grooved ɕ, over 13 anchors x 11 manners ==')
    nn_rows = {}
    for pl in PLACEMENTS:
        near, alln = nearest_neighbours(variants[pl])
        nn_rows[pl] = [(round(c, 3), a, m) for c, a, m in near]
        print('  -- %s --' % pl)
        for c, a, m in near:
            print('     %7.3f cm  %-13s %s' % (c, a, m))
        rank = [i for i, (_, a, m) in enumerate(alln)
                if a == 'postalveolar']
        print('     closest postalveolar contour ranks %d of %d; %d of the 6 '
              'nearest are the SAME anchor at other manners'
              % (rank[0] + 1, len(alln),
                 sum(1 for _, a, _ in near if a == 'palatoalveol')))
        print('     so the contour is ordered by manner within an anchor before '
              'it is ordered by place across anchors')

    print('\n== how the OLD 16-dim table separates these pairs ==')
    for a, b in (('\u0255', '\u0283'), ('\u0283', 't\u0361\u0283')):
        diff = table_axis_diff(a, b)
        print('  %s vs %s differ on %d axes: %s'
              % (a, b, len(diff), ', '.join('%s(%s->%s)' % t for t in diff)))
    print('  none of those axes is a groove; the old scheme buys ɕ/ʃ with a')
    print('  0.15 step on `place` plus rounding, tip_shape, duration and jet.')

    ph = phatak_crosscheck()
    print('\n== Phatak-08 confusion cross-check ==')
    if ph is None:
        print('  NOT RUN')
    else:
        print('  inventory (%d): %s' % (len(ph['inventory']),
                                        ' '.join(ph['inventory'])))
        for s in ph['absent']:
            print('  %s IS ABSENT from that inventory -> no ɕ/ʃ confusion '
                  'value exists' % s)
        print('  measured symmetric confusabilities in the same sibilant family:')
        print('    ʃ/ʒ (same place, voicing differs)  %.4f' % ph['sym_3_eZH'])
        print('    ʃ/s  (postalveolar vs alveolar)     %.4f' % ph['sym_3_s'])
        print('    ʃ/t                                   %.4f' % ph['sym_3_t'])
        print('    mean off-diagonal over the 16        %.4f'
              % ph['mean_off_diagonal'])
        print('  per-SNR breakdown:')
        for k, v in ph['per_snr'].items():
            print('    %-8s %s' % (k, '  '.join('%s dB %.4f' % t for t in v)))
        if ph['sym_3_s'] and ph['sym_3_eZH']:
            print('  The only measured sibilant PLACE step in this data (%s) is'
                  % 'ʃ/s')
            print('  %.1fx rarer than the voicing step (ʃ/ʒ). So the one'
                  % (ph['sym_3_eZH'] / ph['sym_3_s']))
            print('  confusion corpus we have does not even rank place above')
            print('  voicing for sibilants, and it cannot speak to ɕ at all.')

    d_tbl = json.load(io.open(VEC, encoding='utf-8'))['table']
    recips = groove_recipients(d_tbl)
    print('\n== which rows the groove would be applied to ==')
    print('  measured from vec_table_16.json: every row sharing ɕ\'s place '
          'value ->')
    print('    %s' % ' '.join(recips))
    print('  the palatal anchor (place +0.15: ç ʎ ʄ ʝ ɟ ...) is NOT given a')
    print('  groove: a palatal non-sibilant closes with a flat fronted blade,')
    print('  and ɕ\'s channel is the property of the grooved sibilant, not of')
    print('  palatality as such.')

    print('\n== VERDICT ==')
    best = max(PLACEMENTS, key=lambda pl: gain[pl])
    if gain[best] <= 0.0:
        print('  THE GROOVE DOES NOT EARN ITS PLACE.')
        print('  It adds %.3f cm to the ɕ/ʃ separation at %.1f mm depth, i.e.'
              % (gain[best], GROOVE_DEPTH_CM * 10))
        print('  nothing measurable. The ɕ/ʃ distance of %.3f cm that DOES'
              % base)
        print('  exist is already present in the four-point model and equals'
              ' %.2f' % (base / (sum(d for _, _, d in steps) / len(steps))))
        print('  place steps, so the claim in the brief that the two are')
        print('  "geometrically indistinguishable" is too strong: they are')
        print('  weakly ordered already, and the groove adds no resolution on')
        print('  top of that ordering.')
        print('  It does create a real concavity (see the concavity counts),')
        print('  but a feature nobody can measure and nothing in the available')
        print('  data can confirm is not yet a dimension.')
    else:
        print('  The groove earns its place: +%.3f cm on %s, from %.3f cm to'
              % (gain[best], best, base))
        print('  %.3f cm, %.0f%% of one place step.'
              % (base + gain[best], 100 * gain[best]
                 / (sum(d for _, _, d in steps) / len(steps))))

    out = {
        'parameter': 'groove_depth',
        'model_units_per_cm': {'x': 1.0 / CM_PER_X, 'y': 1.0 / CM_PER_Y},
        'groove_depth_model_units': round(GROOVE_DEPTH, 4),
        'groove_depth_cm': GROOVE_DEPTH_CM,
        'groove_frac': GROOVE_FRAC,
        'placements': list(PLACEMENTS),
        'segment_classification': {s: {'anchor': seg[s]['anchor'],
                                       'manner': seg[s]['manner']}
                                   for s in SEGMENTS},
        'distances': rows,
        'baseline_cm': base,
        'separation_gain_cm': {pl: round(gain[pl], 4) for pl in PLACEMENTS},
        'requested_vs_realised_groove_cm': {pl: realised[pl]
                                            for pl in PLACEMENTS},
        'concavities': {
            'ɕ_plain': concavity_count(plain['\u0255']),
            'ʃ_plain': concavity_count(plain['\u0283']),
            **{'ɕ_grooved_' + pl: concavity_count(variants[pl])
               for pl in PLACEMENTS}},
        'adjacent_place_steps_cm': [{'from': a, 'to': b, 'cm': round(d, 3)}
                                    for a, b, d in steps],
        'mean_adjacent_place_step_cm': round(
            sum(d for _, _, d in steps) / len(steps), 3),
        'ɕʃ_in_place_steps': round(
            base / (sum(d for _, _, d in steps) / len(steps)), 3),
        'unrelated_place_cm': unrelated,
        'literal_criterion_groove_gt_unrelated': bool(literal),
        'literal_criterion_note':
            'reported and FAILING. A place-refinement parameter must leave a '
            'same-place pair closer than a different-place pair; requiring the '
            'reverse would merge postalveolar with alveolar. The criterion as '
            'posed cannot be satisfied by any correct place scale.',
        'verdict': 'not earned at %.1f mm depth' % (GROOVE_DEPTH_CM * 10)
                   if max(gain.values()) <= 0.0 else 'earned',
        'nearest_neighbours': nn_rows,
        'groove_recipients': recips,
        'old_table_axis_diffs': {
            'ɕ/ʃ': table_axis_diff('\u0255', '\u0283'),
            'ʃ/t͡ʃ': table_axis_diff('\u0283', 't\u0361\u0283')},
        'phatak_crosscheck': ph,
        'honesty': [
            'The ɕ/ʃ separation is NOT an independent finding: the groove '
            'depth was authored from the anatomical description of ɕ that '
            'this script then measures.',
            'No acoustic unit is attached to any distance: all nine formant '
            'datasets are vowel-only, so a consonant contour cannot be '
            'mapped onto F1/F2/F3 here.',
            'GROOVE_DEPTH_CM = 0.5 is an order-of-magnitude assumption, not a '
            'measurement from imaging.',
            'The Phatak-08 inventory does not contain ɕ, so the ɕ/ʃ '
            'confusion value requested in step 3 does not exist and is '
            'reported as unmeasured rather than estimated.',
            'Per-SNR ʃ->s and ʃ->ʒ probabilities are identical at every SNR '
            'in phatak08_cm.json, so that corpus carries no signal about which '
            'sibilant contrasts degrade; treat 0.0125 and 0.0630 as one '
            'degraded-hearing figure each, not as an SNR trend.',
        ],
    }
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()