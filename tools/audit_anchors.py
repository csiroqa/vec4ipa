#!/usr/bin/env python3
"""SPEC-NEXT anchor-space audit: detect ANOMALOUS / counter-intuitive distances.

Rebuilds the 13-dim SPEC-NEXT vector table from the v8 base table + the
13 extIPA EXTRA_BASE entries (place axis + glottal_state merge + chain-
neutral lip/tip fixes), then flags:

  1. near-collisions            -- pairs below the resolvability floor (0.6)
  2. counter-intuitive distances -- pairs whose ORDER contradicts
       (a) Phatak 08 confusion data: high-confusion pairs must be CLOSER
           than low-confusion pairs of the same family;
       (b) vowel-glide families: i~j~ɥ~y, u~w~ʍ, a~aː~ã must be close;
       (c) intra-class spreads: same-place / same-manner families should
           have comparable internal distances (no stragglers);
       (d) extIPA points: percussives (airflow endpoint 0!) and
           velopharyngeal ʩ must sit sensibly vs their nearest neighbours.
  3. chain-step distortions     -- fricative place chain uniformity.

Fixes are suggested per finding.  Run:  python tools/audit_anchors.py
"""

import os
import re
import json

import numpy as np

from explore_dims import PLACE_ANCHOR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS_MD = os.path.join(ROOT, 'IPA_VECTORS.md')
PHATAK = os.path.join(ROOT, 'tools', 'data', 'phatak08_cm.json')

NDIM = 13
DIMS = ['place', 'lips_closed', 'lips_rounded', 'tip_shape', 'tongue_root',
        'vel_open', 'lateral_ratio', 'voiced', 'glottal_state', 'duration',
        'jet_focus', 'effective_oral_area', 'airflow_direction']

PROV_W = np.array([25.0, 1.5, 3.0, 1.7, 3.0, 3.7, 2.0, 1.5, 8.0,
                   2.9, 2.7, 4.6, 4.0])

FRIC_CHAIN = 'ɸ f θ s ʃ ɕ ʂ ç x χ ħ ʜ h'.split()

# vowel place derived by RULE from v8 body_pos (SPEC-NEXT §3):
#   body >= 0: place = 0.500 + 0.083*body
#   body <  0: place = 0.500 - 0.333*body
# computed at rebuild time -- no hand-picked values.
VOWEL_BACK = None  # filled in rebuild()

# extIPA / IPA2018 EXTRA_BASE: (name, v8-16d vector) from ipa2vec_core.h
EXTRA = {
    'ᴇ':  [0.0, 0.0, 0.55, 0.1, 1.0, -0.2, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.7, 1.0],
    'ɚ':  [0.0, 0.0, 0.55, 0.45, 0.0, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0, 0.3, 1.0, 0.0, 0.65, 1.0],
    'ɞ':  [0.0, 1.0, 0.55, 0.25, 0.0, 0.1, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.85, 1.0],
    'ɝ':  [0.0, 0.0, 0.55, 0.35, 0.0, 0.1, 0.0, 0.0, 1.0, 0.2, 0.0, 0.5, 1.0, 0.0, 0.85, 1.0],
    'ʬ':  [1.0, 0.0, 0.55, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.1, 0.0, 0.0, 0.0],
    'ʭ':  [0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.1, 0.0, 0.0, 0.0],
    'ʩ':  [0.0, 0.0, 0.55, 0.25, -0.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.6, 0.0, 0.09, 1.0],
    'ꞎ':  [0.0, 0.0, 0.1, 0.8, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.4, 0.0, 0.9, 0.5, 0.08, 1.0],
    'ᶑ':  [0.0, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0, 1.0, 0.55, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0],
    'ȶ':  [0.0, 0.0, 0.35, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, 1.0],
    'ȡ':  [0.0, 0.0, 0.35, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    'ȵ':  [0.0, 0.0, 0.35, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
    'ȴ':  [0.0, 0.0, 0.35, 0.7, 0.0, 0.0, 0.0, 1.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.5, 1.0],
}
EXTRA_PLACE = {'ᴇ': 0.583, 'ɚ': 0.500, 'ɞ': 0.500, 'ɝ': 0.500,
               'ʬ': 0.000, 'ʭ': 0.167, 'ʩ': 0.667, 'ꞎ': 0.500,
               'ᶑ': 0.500,
               # ȶ ȡ ȵ ȴ: code comment pins tip_pos 0.35 so the standard
               # fallback lands on /t/ (0.250), not the retroflex /ʈ/;
               # mirror that intent (dental-alveolar edge, not 龈齶 0.417)
               'ȶ': 0.250, 'ȡ': 0.250, 'ȵ': 0.250, 'ȴ': 0.250}


def gs_of(v):
    """SPEC-NEXT §4 glottal_state lookup from v8 (cg, sg) -- NOT sg-cg.
    Exact anchors from §4; intermediates by region."""
    cg, sg = v[9], v[10]
    if sg >= 0.55:
        return sg                      # breathy/aspirated side: 0.55/0.7/0.9/1.0
    if cg == 0.0 and sg == 0.4:
        return 0.4                     # voiceless unaspirated
    if cg == 0.2 and sg == 0.0:
        return 0.0                     # modal voiced
    if cg == 0.55:
        return -0.55                   # implosive constriction
    if cg == 0.7:
        return -0.7                    # creaky
    if cg >= 0.9:
        return -1.0                    # glottal stop / ejective hold
    return sg - cg                     # fallback (unlisted combinations)


def to13(v8):
    """v8 16-D row -> SPEC-NEXT 13-D row.
    Chain-neutral fixes: lip closure ONLY for bilabials (labiodental
    f/v/p̪/ɱ/ⱱ get lips_closed=0); the SIBILANT rounding that v8 used to
    encode s-vs-ʃ is removed (SPEC-NEXT §3 moves it to the place axis) --
    but VOWEL rounding (i-vs-y, u-vs-ɯ) is a core vowel feature and kept.
    glottal_state by the §4 lookup table."""
    v = [float(x) for x in v8]
    x = np.zeros(NDIM)
    x[1] = 0.0 if v[0] < 1.0 else 1.0      # lip closure only for bilabial
    is_vowel = v[8] >= 0.5 and v[14] >= 0.4 and v[12] >= 1.0
    is_sibilant = v[13] >= 0.5              # jet_focus marks sibilants
    x[2] = v[1] if is_vowel else 0.0        # keep vowel rounding, drop sibilant
    x[3] = v[3]
    x[4] = v[5]
    x[5] = v[6]
    x[6] = v[7]
    x[7] = v[8]
    x[8] = gs_of(v)                         # §4 lookup, not sg - cg
    x[9] = v[12]
    x[10] = v[13]
    x[11] = v[14]
    x[12] = v[15]
    return x


def rebuild():
    rows = {}
    pat = re.compile(r"^`/([^/`]*)/`: `\((.*)\)`")
    for line in open(VECTORS_MD, encoding='utf-8'):
        m = pat.match(line.strip())
        if m and len(m.group(2).split(',')) == 16:
            rows[m.group(1)] = [float(x.strip())
                                for x in m.group(2).replace('+', '').split(',')]
    # vowel place from the v8 body_pos rule (SPEC-NEXT §3)
    def vplace(body):
        return 0.500 + 0.083 * body if body >= 0 else 0.500 - 0.333 * body
    global VOWEL_BACK
    VOWEL_BACK = {}
    for seg, v in rows.items():
        if v[8] >= 0.5 and v[14] >= 0.4 and v[12] >= 1.0 and seg not in PLACE_ANCHOR:
            VOWEL_BACK[seg] = vplace(v[4])
    out = {}
    for seg, v in rows.items():
        x = to13(v)
        if seg in PLACE_ANCHOR:
            x[0] = PLACE_ANCHOR[seg]
        elif seg in VOWEL_BACK:
            x[0] = VOWEL_BACK[seg]
        elif seg == 'ʋ':
            x[0] = 0.083
        else:
            raise KeyError(f'no place for {seg!r}')
        out[seg] = x
    for seg, v in EXTRA.items():
        x = to13(v)
        x[0] = EXTRA_PLACE[seg]
        out[seg] = x
    return out


def is_vowel(seg):
    return seg in VOWEL_BACK or seg in ('ᴇ', 'ɚ', 'ɞ', 'ɝ')


def main():
    vecs = rebuild()
    names = list(vecs)
    X = np.array([vecs[n] for n in names])
    d2 = ((X[:, None, :] - X[None, :, :]) ** 2) * PROV_W
    D = np.sqrt(d2.sum(axis=2))
    np.fill_diagonal(D, np.inf)

    print(f'SPEC-NEXT anchor audit: {len(names)} segments '
          f'({len(names)-len(EXTRA)} IPA + {len(EXTRA)} extIPA), {NDIM} dims\n')

    # ---- 1. near collisions ----
    print('=== 1. near-collisions (d < 0.6) ===')
    flagged = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if D[i, j] < 0.6:
                flagged.append((D[i, j], names[i], names[j]))
    flagged.sort()
    for d, a, b in flagged[:25]:
        ex = ' [extIPA]' if a in EXTRA or b in EXTRA else ''
        print(f'  {a:<6}~{b:<6}  d={d:.3f}{ex}')
    print(f'  ({len(flagged)} pairs total)\n')

    # ---- 2. counter-intuitive distances ----
    print('=== 2. counter-intuitive distances ===')

    # (a) confusion-order: Phatak high-confusion pairs must be closer than
    # low-confusion pairs WITHIN the same family.  Report BOTH pooled and
    # 0 dB (METRIC.md uses 0 dB as the reference condition).
    ph = json.load(open(PHATAK, encoding='utf-8'))
    cons = ['ɡ' if c == 'g' else c for c in ph['consonants']]
    counts = np.array([[ph['counts'][snr][i][j]
                        for j in range(len(cons))]
                       for snr in ph['snr_db'] for i in range(len(cons))]
                      ).reshape(len(ph['snr_db']), len(cons), len(cons))
    N = counts.sum(axis=0)
    P = N / N.sum(axis=1, keepdims=True)
    P0 = None
    if '0' in ph['counts']:
        P0 = np.array(ph['counts']['0'])
        P0 = P0 / P0.sum(axis=1, keepdims=True)
    conf = {}
    conf0 = {}
    for a in cons:
        for b in cons:
            if a != b:
                key = tuple(sorted((a, b)))
                conf[key] = conf.get(key, 0.0) + P[cons.index(a), cons.index(b)] \
                    + P[cons.index(b), cons.index(a)]
                if P0 is not None:
                    conf0[key] = conf0.get(key, 0.0) + P0[cons.index(a), cons.index(b)] \
                        + P0[cons.index(b), cons.index(a)]
    print('  (a) Phatak confusion order vs distance (same-family pairs):')
    fam = {'place': [('p', 't'), ('t', 'k'), ('p', 'k'), ('f', 'θ'), ('s', 'ʃ')],
           'voicing': [('p', 'b'), ('t', 'd'), ('k', 'ɡ'), ('f', 'v'),
                       ('θ', 'ð'), ('s', 'z'), ('ʃ', 'ʒ')]}
    for fn, plist in fam.items():
        for a, b in plist:
            if a not in names or b not in names:
                continue
            i, j = names.index(a), names.index(b)
            d = D[i, j]
            c = conf.get(tuple(sorted((a, b))), 0.0)
            c0 = conf0.get(tuple(sorted((a, b))), 0.0)
            print(f'    {a}-{b}: d={d:.3f}  conf_pooled={c:.1%}  conf_0dB={c0:.1%}')
    print()

    # (b) vowel-glide families
    print('  (b) vowel-glide family closeness:')
    fams = [('i', ['j', 'ɥ', 'y']), ('u', ['w', 'ʍ', 'ɰ']),
            ('a', ['aː', 'ã']), ('ə', ['ɚ']), ('e', ['e̞', 'ᴇ'])]
    for base, kin in fams:
        if base not in names:
            continue
        for k in kin:
            if k in names:
                print(f'    {base}~{k}: d={D[names.index(base), names.index(k)]:.3f}')
    print()

    # (c) intra-class stragglers: same-place family spreads
    print('  (c) intra-class spread (same place, all manners):')
    places = {'bilabial': ['p', 'b', 'm', 'ɸ', 'β', 'ʙ', 'ɓ', 'ʘ'],
              'alveolar': ['t', 'd', 'n', 's', 'z', 'ɹ', 'r', 'ɾ', 'l', 'ɺ'],
              'velar': ['k', 'ɡ', 'ŋ', 'x', 'ɣ', 'ɰ', 'ʟ', 'w', 'ʍ'],
              'postalv': ['ʃ', 'ʒ', 't͡ʃ', 'd͡ʒ']}
    for pn, segs in places.items():
        idx = [names.index(s) for s in segs if s in names]
        sub = D[np.ix_(idx, idx)]
        np.fill_diagonal(sub, np.inf)
        m = sub[sub < np.inf]
        print(f'    {pn:<9} n={len(idx)}  mean intra {m.mean():.3f}  '
              f'min {m.min():.3f}  max {m.max():.3f}')
    print()

    # (d) extIPA sanity
    print('  (d) extIPA points vs nearest neighbours:')
    for s in ('ʬ', 'ʭ', 'ʩ', 'ꞎ', 'ᶑ', 'ȶ', 'ȵ'):
        i = names.index(s)
        nn = np.argsort(D[i])[:4]
        row = ', '.join(f'{names[j]}:{D[i, j]:.2f}' for j in nn)
        print(f'    {s}: {row}')

    # ---- 3. chain steps ----
    print('\n=== 3. fricative place-chain steps ===')
    steps = np.array([D[names.index(FRIC_CHAIN[k]), names.index(FRIC_CHAIN[k + 1])]
                      for k in range(len(FRIC_CHAIN) - 1)])
    med = np.median(steps)
    for k, s in enumerate(steps):
        a, b = FRIC_CHAIN[k], FRIC_CHAIN[k + 1]
        ok = 'ok ' if 0.6 * med <= s <= 1.8 * med else 'ANOM'
        print(f'  {a}->{b}: {s:.3f}  [{ok}]')
    print(f'  median {med:.3f}, CV {steps.std()/np.mean(steps):.2f}')


if __name__ == '__main__':
    main()
