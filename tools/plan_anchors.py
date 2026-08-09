#!/usr/bin/env python3
"""SPEC-NEXT anchor planner: assign 16-dim coordinates to all 132 segments
such that EVERY PAIR has weighted distance > 0.6 (hard constraint).

Design (per SPEC-NEXT v0.4, span-2 place axis):
  place weight 16  -> adjacent place cells must differ >= 0.15
  area   weight 16 -> adjacent height cells must differ >= 0.15
  lips   weight 8  -> rounding pairs separate on lips_rounded

Cells:
  CONSONANT place: 13 cells, step 0.15, span [-0.9, +0.9]
  VOWEL columns:   front +0.15, central 0.00, back +0.30
  VOWEL height:    6 cells, step 0.15: 0.40 0.55 0.70 0.85 0.95 1.00
  (a and æ share the open cell; æ gets place 0.10, a 0.05 -> still > 0.6)

Manner within a place cell is separated by area/duration/tip_shape/others:
  stop 0.00 / affricate 0.10 / fricative 0.08-0.12 / nasal 0.00+vel /
  approx 0.35-0.55 / trill 0.20 / tap 0.00 / lateral +lat
  -> within-cell pairs rely on NON-place dims (see table below).

This script PLANS the consonant anchor table; the vowel table is separate.

Run: python tools/plan_anchors.py  (prints the consonant plan)
"""

# consonant place cells (span-2, step 0.15)
PLACE_CELLS = {
    'bilabial':    -0.90,
    'labiodental': -0.75,
    'dental':      -0.60,
    'alveolar':    -0.45,
    'postalveolar':-0.30,
    'alveolopal':  -0.15,
    'retroflex':    0.00,
    'palatal':      0.15,
    'velar':        0.30,
    'uvular':       0.45,
    'pharyngeal':   0.60,
    'epiglottal':   0.75,
    'glottal':      0.90,
}

# manner cells WITHIN a place (non-place dims separate them):
#   stop:    area 0.00, duration 0.0
#   nasal:   area 0.00, vel 1.0
#   fric:    area 0.09, duration 0.5-1.0 (place-graded), jet if sibilant
#   affric:  area 0.10, duration 1.3
#   approx:  area 0.50
#   trill:   area 0.20, duration 0.5
#   tap:     area 0.00, duration 0.3
#   lateral: area 0.50, lat 1.0
# e.g. alveolar: t(0.00,0.0) s(0.09,0.8,jet0.95) n(0.00,vel1) l(0.50,lat1)
#   r(0.20,0.5) ɾ(0.00,0.3) ɹ(0.55) -- pairs differ in >= 2 dims

def main():
    print('== consonant place cells (span-2, step 0.15) ==')
    for name, val in PLACE_CELLS.items():
        print(f'  {name:<14} {val:+.2f}')
    print()
    print('adjacent cell distance = 0.15 * sqrt(16) = 0.60')
    print('(add +0.01-0.02 margin via manner dims where needed)')
    print()
    print('== within-cell manner separation (example: alveolar) ==')
    print(f'{"seg":<4}{"place":>7}{"area":>6}{"dur":>5}{"vel":>5}{"lat":>5}{"jet":>5}{"tip":>5}')
    alveolar = {
        't':  (-0.45, 0.00, 0.0, 0.0, 0.0, 0.00, 1.00),
        'd':  (-0.45, 0.00, 0.0, 0.0, 0.0, 0.00, 1.00),
        's':  (-0.45, 0.09, 0.8, 0.0, 0.0, 0.95, 0.60),
        'z':  (-0.45, 0.09, 0.7, 0.0, 0.0, 0.90, 0.60),
        'n':  (-0.45, 0.00, 1.0, 1.0, 0.0, 0.00, 1.00),
        'l':  (-0.45, 0.50, 1.0, 0.0, 1.0, 0.00, 0.70),
        'r':  (-0.45, 0.20, 0.5, 0.0, 0.0, 0.00, 0.90),
        'ɾ':  (-0.45, 0.00, 0.3, 0.0, 0.0, 0.00, 0.90),
        'ɹ':  (-0.45, 0.55, 1.0, 0.0, 0.0, 0.00, 0.60),
        'ɬ':  (-0.45, 0.09, 0.9, 0.0, 1.0, 0.50, 0.60),
        'ɺ':  (-0.45, 0.00, 0.3, 0.0, 1.0, 0.00, 0.90),
    }
    for seg, (p, a, d, v, l, j, t) in alveolar.items():
        print(f'{seg:<4}{p:>7.2f}{a:>6.2f}{d:>5.1f}{v:>5.1f}{l:>5.1f}{j:>5.2f}{t:>5.2f}')
    print()
    print('within-cell min distance (unit weights, dims a,d,v,l,j,t):')
    import numpy as np
    segs = list(alveolar)
    X = np.array([list(alveolar[s][1:]) for s in segs])
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(2))
    np.fill_diagonal(D, np.inf)
    nn = D.min(axis=1)
    for i in np.argsort(nn)[:5]:
        j = np.argmin(D[i])
        print(f'  {segs[i]}~{segs[j]}: {nn[i]:.3f} (unit) '
              f'-> weighted {nn[i]*4:.2f} (w=16)')


if __name__ == '__main__':
    main()
