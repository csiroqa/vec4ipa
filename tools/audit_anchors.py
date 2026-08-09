#!/usr/bin/env python3
"""SPEC-NEXT 16-D anchor-space audit: detect ANOMALOUS / counter-intuitive distances.

Rebuilds the 16-dim vector table from the generated src/vectors.h (133
base segments, produced by gen_vectors_h.py from spec_next.scheme) plus
the 13 extIPA EXTRA_BASE entries (kept in sync with ipa2vec_core.h), plus
the few derived segments the checks need (e̞ = e+lowered, aː = a+long,
ã = a+nasal, mirroring the modifier functions in ipa2vec_core.h), then
flags:

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

Distances use the scheme's own 16-dim weights (spec_next.scheme weight
line).  Run:  python tools/audit_anchors.py
"""

import os
import re
import json

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS_H = os.path.join(ROOT, 'src', 'vectors.h')
PHATAK = os.path.join(ROOT, 'tools', 'data', 'phatak08_cm.json')

# spec_next.scheme dim order and weights (weight line, 16 numbers).
NDIM = 16
DIMS = ['place', 'body', 'lips_closed', 'lips_rounded', 'tip_shape',
        'tongue_root', 'vel_open', 'lateral_ratio', 'voiced',
        'glottal_aperture', 'glottal_tension', 'larynx_height', 'duration',
        'jet_focus', 'effective_oral_area', 'airflow_direction']
W = np.array([30.0, 1.0, 0.5, 8.0, 5.0, 2.0, 6.7, 1.0, 2.0, 1.1,
              1.0, 1.0, 25.0, 8.0, 16.0, 1.0])

FRIC_CHAIN = 'ɸ f θ s ʃ ɕ ʂ ç x χ ħ ʜ h'.split()

# extIPA / IPA2018 EXTRA_BASE: (name, 16-D vector) from ipa2vec_core.h.
# Order: place, body, lips_closed, lips_rounded, tip_shape, tongue_root,
# vel_open, lateral_ratio, voiced, glottal_aperture, glottal_tension,
# larynx_height, duration, jet_focus, effective_oral_area, airflow_direction.
EXTRA = {
    'ᴇ':  [0.15, 0.0, 0.0, 0.0, 0.25, -0.2, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.7, 1.0],
    'ɚ':  [0.0, 0.0, 0.0, 0.0, 0.45, 0.0, 0.0, 0.0, 1.0, 0.0, 0.3, 0.0, 1.0, 0.0, 0.65, 1.0],
    'ɞ':  [0.0, 0.0, 0.0, 1.0, 0.25, 0.1, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.8, 1.0],
    'ɝ':  [0.0, 0.0, 0.0, 0.0, 0.35, 0.1, 0.0, 0.0, 1.0, 0.0, 0.5, 0.0, 1.0, 0.0, 0.8, 1.0],
    'ʬ':  [-0.9, 0.0, 1.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0],
    'ʭ':  [-0.6, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0],
    'ʩ':  [0.3, -0.5, 0.0, 0.0, 0.25, 0.0, 1.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.6, 0.0, 0.09, 1.0],
    'ꞎ':  [0.0, 0.0, 0.0, 0.0, 0.8, 0.0, 0.0, 1.0, 0.0, 0.4, 0.0, 0.0, 0.9, 0.5, 0.08, 1.0],
    'ᶑ':  [0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 1.0, -0.55, 0.0, -1.0, 0.0, 0.0, 0.0, -1.0],
    'ȶ':  [-0.40, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    'ȡ':  [-0.40, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    'ȵ':  [-0.40, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
    'ȴ':  [-0.40, 0.0, 0.0, 0.0, 0.7, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.5, 1.0],
}


def _parse_vectors_h():
    """All base rows from the generated table: {ipa: 16-list}."""
    rows = {}
    for line in open(VECTORS_H, encoding='utf-8'):
        m = re.search(r'\{ "([^"]+)", \{([^}]+)\}, 0 \}', line)
        if m:
            rows[m.group(1)] = [float(x) for x in m.group(2).split(',')]
    return rows


def _derived(rows):
    """Derived segments used by the checks, mirroring ipa2vec_core.h
    modifier functions (mod_lowered: eoa+0.1 capped; mod_long: dur 1.0-1.2
    -> 2.0; mod_nasal: vel_open 0.6)."""
    EOA, VEL, DUR = 14, 6, 12
    out = {}
    v = list(rows['e']); v[EOA] = min(1.0, v[EOA] + 0.1); out['e̞'] = v
    v = list(rows['a']); v[DUR] = 2.0; out['aː'] = v
    v = list(rows['a']); v[VEL] = 0.6; out['ã'] = v
    return out


def rebuild():
    rows = _parse_vectors_h()
    rows.update(_derived(rows))
    for seg, v in EXTRA.items():
        rows[seg] = list(v)
    return rows


def main():
    vecs = rebuild()
    names = list(vecs)
    X = np.array([vecs[n] for n in names])
    d2 = ((X[:, None, :] - X[None, :, :]) ** 2) * W
    D = np.sqrt(d2.sum(axis=2))
    np.fill_diagonal(D, np.inf)

    print(f'SPEC-NEXT anchor audit: {len(names)} segments '
          f'({len(names)-len(EXTRA)} base + {len(EXTRA)} extIPA), '
          f'{NDIM} dims (spec_next weights)\n')

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
