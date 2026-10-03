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
LIP_SITES = tm.LIP_SITES

# The old table gives these five `place = 0.00`, which is not their place --
# 0.00 is the neutral value the table uses for central vowels and for
# retroflex stops. Left uncorrected they were read as vowels (and then given
# schwa's coordinates by the VOWEL_CFG fallback), and with the vowel branch
# excluded they snapped to the retroflex anchor, whose place value is exactly
# 0.00, so all five shared one contour: achievable reconstruction fell 122 ->
# 119. The values below are the anchor places these segments actually have.
#
#   j  palatal, plain approximant            -> palatal
#   ɥ  labial-palatal, palatalised           -> palatal (same constrictor)
#   w  labial-velar                         -> velar
#   ɰ  velar, plain approximant             -> velar
#   ʍ  labial-velar fricative               -> velar
#
# Labial-palatal and labial-velar are coarticulated segments: the constrictor
# is the palatal or velar one respectively, and the labial element is a lip
# gesture, which LIP_GESTURES below applies separately.
PLACE_FIX = {'j': 'palatal', 'ɥ': 'palatal',
               'w': 'velar', 'ɰ': 'velar', 'ʍ': 'velar'}

# ɺ is the seventh transcription slip of the same kind: the old table gives it
# place = -0.450 and tip_shape = 0.90, both identical to ɾ, even though ɺ is
# the retroflex flap and ɾ the alveolar tap. The evidence is inside the same
# table -- every other retroflex segment (ʈ ɖ ɳ ʂ ʐ ɭ ɻ) sits at
# place = +0.000, so -0.450 is a slip rather than a different encoding.
# Routing it to retroflex separates the two because that anchor retracts the
# tip (0.30 vs alveolar 0.15) and raises the blade (0.28 vs 0.18) even though
# both anchors share a dorsum at (0.33, 0.28).
PLACE_FIX['ɺ'] = 'retroflex'

# ɽ is the same slip in the other direction. The place = +0.000 bucket holds
# the 28 central-ish vowels, the retroflex series, and -- among the consonants
# -- only this one. Every other alveolar consonant in the table (t d n s z ɬ ɮ
# t͡s d͡z ɹ l r ɾ ɗ) sits at -0.450, and r, which is the same sound, does
# too. So +0.000 here is not an alternative encoding of anything.
PLACE_FIX['ɽ'] = 'alveolar'

# ɧ is a third transcription slip, and the only fricative in the table that
# does not sit exactly on an anchor: every other one is 0.000 from its nearest
# anchor, this one is 0.075 from postalveolar. Its -0.225 is the midpoint
# between postalveolar (-0.300) and palatoalveolar (-0.150), and no other
# segment in the table uses that value. Its body is -0.400, the most posterior
# of the whole fricative series (χ -0.290, ɣ and x -0.200, ʃ 0.000, ħ ʕ -0.390),
# and its voiced pair ɣ is at +0.300 velar. So it routes to velar, which also
# separates it from ʃ -- at the cost recorded in §0.6.
PLACE_FIX['ɧ'] = 'velar'

# ɽ carries the flap's duration and oral area (0.30 / 0.00) while r, which is
# the same sound, carries the trill's (0.50 / 0.20). The old table therefore
# files ɽ as a flap and leaves it colliding with ɾ. The trill verdict is
# corrected here rather than in the profile table, because the evidence is the
# disagreement between two rows of the same table for the same segment.
#
# After this ɽ and r share a vector. That is CORRECT, not a lost distinction:
# they are the same phoneme, written with two characters. check 7 carries an
# explicit allowlist for it rather than being taught to ignore duplicates.
MANNER_FIX = {'ɽ': 'trill'}

# Anchor places come from tm.ANCHORS by name rather than being written out
# here: ANCHORS stores the place VALUE (palatal 0.15, velar 0.30), which is
# not the constriction x (0.36, 0.45) that ANCHOR_CFG carries. Hard-coding
# the wrong pair routed j to velar and w to uvular -- still wrong, just wrong
# in a way that looked plausible.
PLACE_FIX_VALUE = {n: v for n, v, _ in tm.ANCHORS}


def place_override(seg, vec, I):
    """Anchor place for a segment, corrected for the five glides."""
    a = PLACE_FIX.get(seg)
    return PLACE_FIX_VALUE[a] if a else vec[I['place']]


# Lip protrusion added for a secondary labialised segment. Same constant the
# `labialized` modifier adds in gen_tongue_modifiers.py.
LABIAL_LIP_ROUND = 0.30

# The labial element of ɥ (labial-palatal) and w / ʍ (labial-velar): not a lip
# closure, so lips_closed stays 0 and these need the protrusion added
# explicitly. It is a weaker gesture than primary rounding -- the same +0.30
# the `labialized` modifier applies -- because the coronal constriction is
# what makes the segment, and the lips only accompany it.
LIP_GESTURES = {'ɥ': LABIAL_LIP_ROUND, 'w': LABIAL_LIP_ROUND,
                'ʍ': LABIAL_LIP_ROUND}

# gap below the roof at the constrictor; 0.00 is full contact.
PROFILES = {
    'stop':        {'gap': 0.00, 'dur': 0.10, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'affricate':   {'gap': 0.00, 'dur': 0.70, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'fricative':   {'gap': 0.14, 'dur': 0.60, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'nasal':       {'gap': 0.00, 'dur': 0.90, 'velum': 1.0, 'lat': 0.0, 'larynx': 0.0},
    'approximant': {'gap': 0.40, 'dur': 0.90, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'lateral':     {'gap': 0.40, 'dur': 0.90, 'velum': 0.0, 'lat': 1.0, 'larynx': 0.0},
    'lateral_fricative': {'gap': 0.14, 'dur': 0.90, 'velum': 0.0, 'lat': 1.0, 'larynx': 0.0},
    'trill':       {'gap': 0.00, 'dur': 0.50, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'flap':        {'gap': 0.05, 'dur': 0.25, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    # A click closes like a stop and then releases a rarefied intraoral air
    # impulse. Same closure geometry as a stop; it is `periodic` in the merged
    # basis that separates them, because the airflow event is the difference,
    # not the tongue shape. Duration is short -- a click is brief by nature.
    'click':       {'gap': 0.00, 'dur': 0.15, 'velum': 0.0, 'lat': 0.0, 'larynx': 0.0},
    'ejective':    {'gap': 0.00, 'dur': 0.10, 'velum': 0.0, 'lat': 0.0, 'larynx': 1.0},
    # The ejective branch used to return one profile for every glottalic
    # stop, which swallowed the manner underneath: sʼ (jet_focus 0.95, an
    # affricate) and tʼ (a plain stop) came out identical, as did kʼ
    # (effective_oral_area 0.00, dur 0.00 -- exactly k) and xʼ (0.09, 0.85
    # -- exactly x). The glottal event rides on top of a closure class, so the
    # class is decided first and the larynx value rides along with it.
    'ejective_affricate': {'gap': 0.00, 'dur': 0.70, 'velum': 0.0, 'lat': 0.0, 'larynx': 1.0},
    'ejective_fricative': {'gap': 0.14, 'dur': 0.60, 'velum': 0.0, 'lat': 0.0, 'larynx': 1.0},
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


def classify(vec, I, seg=None):
    """Recover (anchor, manner) for one committed segment from the old table.

    Precedence follows the encoding the old table actually uses, verified
    against representative segments: larynx first (it rides on top of a stop),
    then the airflow branches, then closure, then noise, then openness. The
    flap test keys on an intermediate duration, never on `place` -- keying it
    on place made every zero-duration retroflex stop look like a flap.
    """
    place = vec[I['place']] if seg is None else place_override(seg, vec, I)
    anchor = min(tm.ANCHOR_CFG, key=lambda a: abs(anchor_place(a) - place))
    dur = vec[I['duration']]
    vel = vec[I['vel_open']]
    lat = vec[I['lateral_ratio']]
    eoa = vec[I['effective_oral_area']]
    larynx = vec[I['larynx_height']]
    jets = vec[I['jet_focus']]
    flow = vec[I['airflow_direction']]

    if larynx > 0.5:
        return anchor, ('ejective_affricate' if (jets > 0.0 or dur >= 1.2)
                        else 'ejective_fricative' if eoa > 0.01
                        else 'ejective')
    if larynx < -0.5:
        return anchor, 'implosive'
    if vel >= 0.7:
        return anchor, 'nasal'
    # A click is a closure plus a rarefied intraoral air impulse. It was being
    # read as a plain stop: airflow_direction was never consulted, so ǀ ǁ ǃ ǂ ʘ
    # all fell through to the dur==0 branch below and came out identical to an
    # oral stop at the same place.
    if flow < 0.0:
        return anchor, 'click'
    # Flap before lateral. ɺ is the only lateral_ratio >= 0.5 segment whose
    # duration and oral area put it in the flap range (0.30, 0.00) -- every
    # other lateral sits at 0.80-1.00 duration or 0.08 area. Its
    # lateral_ratio = 1.0 is an old-table mislabel; testing first means the
    # mislabel no longer decides the manner and ɺ stops sharing a vector with
    # l and ɮ. ǁ, the lateral click, is caught by the airflow branch above.
    if 0.10 <= dur <= 0.40 and eoa <= 0.01:
        return anchor, 'flap'
    # Lateral before the jet test: a lateral fricative (ɬ ɮ) carries BOTH a
    # lateral airflow and frication, so testing jets first would file ɬ
    # alongside s and ɮ alongside z and make those pairs identical.
    if lat >= 0.5:
        # A lateral fricative (ɬ ɮ) is a different gesture from a lateral
        # approximant (l ɭ ʎ ʟ): the approximants sit at effective_oral_area
        # 0.50, the fricatives at 0.08. Sharing one profile made l and ɮ
        # identical even though the old table separates them on two axes.
        return anchor, 'lateral_fricative' if eoa <= 0.12 else 'lateral'
    # This must come AFTER the lateral test but BEFORE the dur==0 stop test.
    # An affricate has duration 0 in the old table -- the table records only
    # the closure -- and took the stop branch, so k͡p and ɡ͡b were generated
    # as stops and ended up with vectors identical to k and ɡ.
    #
    # `or dur >= 1.2` catches the two affricates the old table records with
    # jet_focus = 0: ǂ's neighbours k͡x (1.35) and q͡χ (1.50). A fricative
    # tops out at 0.60, so across the whole table these are the only two
    # segments with jets = 0 and dur >= 1.2 -- the duration alone identifies
    # them, which is what they were generated as stops without.
    if jets > 0.0 or dur >= 1.2:
        return anchor, 'affricate' if dur >= 1.2 else 'fricative'
    if dur == 0.0:
        return anchor, 'stop'
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
    if part is None:
        # No tongue makes this constriction. Reporting the resting tongue's
        # closest approach instead would name the pharyngeal wall as the site:
        # the root sits 0.402 from the roof at rest, which is neither a lip
        # aperture nor a closure, and it gave the stop /p̪/ a 0.402 gap.
        if anchor in LIP_SITES:
            return LIP_SITES[anchor][0], PROFILES[manner]['gap'], None, 'assigned'
        # Glottal: no constriction anywhere. The profile gap still describes the
        # glottis, so /ʔ/ closes at 0.0 while /h/ stays open.
        return None, PROFILES[manner]['gap'], None, 'none'

    x, gap, _ = tm.derived_constriction(cfg)
    if gap < 0.05:
        return round(x, 4), round(gap, 4), part, 'derived'
    # The gap MUST be read at the assigned part. Taking it from the argmin gave
    # /ʐ/ a site of x=0.28 (its blade) paired with the gap of the resting root,
    # so the two fields described two different organs.
    return round(cfg[part][0], 4), round(tm.roof(cfg[part][0]) - cfg[part][1],
                                         4), part, 'assigned'


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
        place = place_override(seg, vec, I)
        tip = vec[I['tip_shape']]
        # `place = 0.00` is overloaded in the old table: it is the neutral value
        # for central vowels and glides AND the value retroflex stops use. Only
        # tip_shape separates them -- and only because the old scheme forces
        # the distinction onto a second axis. Tongue coordinates do not need
        # the crutch: a retracted lowered tip vs a resting tip is a difference
        # in the very first coordinate.
        #
        # An effective_oral_area guard was tried here to keep the glides
        # (j w ɥ ɰ ʍ) out of this branch. It works -- they are correctly
        # classified as approximants rather than vowels -- and it makes the
        # basis WORSE, because `place = 0.00` then snaps them to the retroflex
        # anchor (whose place value is exactly 0.00) and all five share one
        # contour: achievable reconstruction drops 122 -> 119. The old table
        # does not merely overload place=0 against vowels, it assigns it to
        # five consonants whose real places are palatal (j ɥ) and velar
        # (w ɰ ʍ). Until those places are authored there is no correct place
        # to route them to, so the guard stays out; see docs §0.9.9.
        no_place_gesture = (abs(place) < 1e-9 and tip < 0.5
                            and seg not in PLACE_FIX)

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

        anchor, manner = classify(vec, I, seg)
        manner = MANNER_FIX.get(seg, manner)
        cfg, prof = apply_manner(anchor, manner)

        # Lip gestures on top of the closure: labialised consonants, and the
        # labial element of the five glides (ɥ w ʍ). Neither closes the lips,
        # so neither is visible in lips_closed.
        labial = vec[I['lips_closed']] > 0.5 and anchor != 'bilabial'
        if labial or seg in LIP_GESTURES:
            cfg = dict(cfg)
            add = LABIAL_LIP_ROUND if labial else LIP_GESTURES[seg]
            cfg['lip_round'] = min(cfg['lip_round'] + add, 1.0)

        # Secondary labialisation is not a manner: it is a lip gesture on top of
        # whatever closure the segment already has. The old table records it on
        # lips_closed = 1.0, the same value a genuinely bilabial segment gets,
        # so the two were indistinguishable and k͡p came out identical to k,
        # ɡ͡b to ɡ and ŋ͡m to ŋ. The anchor is already known here, and it
        # separates them exactly: lips_closed > 0.5 with a bilabial anchor is
        # b m p pʼ ɓ ʘ ʙ, lips_closed > 0.5 with any other anchor is labialised.
        # lips_rounded is 0.000 on all three, so the old table carries no
        # magnitude either; 0.30 is the value gen_tongue_modifiers.py already
        # uses for its `labialized` rule, reused rather than newly invented.
        labial = vec[I['lips_closed']] > 0.5 and anchor != 'bilabial'
        if labial:
            cfg = dict(cfg)
            cfg['lip_round'] = min(cfg['lip_round'] + LABIAL_LIP_ROUND, 1.0)

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
