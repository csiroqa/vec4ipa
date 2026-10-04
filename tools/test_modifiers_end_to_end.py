"""Modifiers must move the vector the built binary emits, not just the C port.

Two unit-level guards already cover this and neither is the same thing:

  test_tongue_contour.py  the C contour code equals the Python model
  test_winui_core.py      Core.cs and the wrapper agree with the CLI

Both sit above or below the layer that actually matters for a user: nothing
checked that `ipa2vec tʲ` differs from `ipa2vec t`, or that the axis which
moves is the one the modifier names. Wiring the contour path in ipa2vec_core.h
is a separate edit from the C code being correct, and a regression there would
pass every existing check.

This drives the built binary and asserts the direction, not merely that
something changed. ʲ must raise the blade and dorsum; ː must set duration; ʼ
must raise the larynx; a dental must move the constriction site. The last one
also pins the derived-axis behaviour: applying a modifier recomputes
constriction_pos, so it has to track the tongue.

Run: python tools/test_modifiers_end_to_end.py
"""

import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
EXE = '.exe' if os.name == 'nt' else ''
IPA2VEC = os.path.join(ROOT, 'ipa2vec' + EXE)
SCHEME = os.path.join(DATA, 'tongue.scheme')

# (base, modifier, axis, direction). direction is the sign the base->modified
# delta must have, which is what makes this a check rather than a diff.
CASES = [
    ('t', 'tʲ', 'blade_x', +1),      # palatalised: blade moves front/raised
    ('t', 'tʲ', 'dorsum_x', -1),
    ('t', 'tː', 'duration', +1),     # long
    ('t', 'tʼ', 'larynx', +1),       # ejective
    ('t', 't̪', 'constriction_pos', -1),   # dental: site moves forward
]

# Aspiration is a documented gap, not a regression: the tongue basis has no
# coordinate for glottal raising (see docs §0.8.3), so under the tongue scheme
# mod_asp writes to axes that do not exist and the vector comes back unchanged.
# It does warn, which is the point -- asserting it MOVES would be asserting a
# feature the model does not have, and asserting it silently does nothing
# would let the warning be dropped later without anything failing.
GAP = [('t', 'tʰ', 'aspiration')]


def values(ipa):
    r = subprocess.run([IPA2VEC, '-D', SCHEME, '-j', ipa],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('ipa2vec failed on %r: %s' % (ipa, r.stderr[-200:]))
    d = json.loads(r.stdout)
    return d['segments'][0]['values']


def main():
    bad = []
    for base, mod, axis, direction in CASES:
        b, m = values(base), values(mod)
        if axis not in b:
            bad.append('%s: axis %s not in the output' % (mod, axis))
            continue
        delta = m[axis] - b[axis]
        if delta == 0:
            bad.append('%s: %s did not move at all' % (mod, axis))
        elif delta * direction < 0:
            bad.append('%s: %s moved %.4f, expected the opposite sign'
                       % (mod, axis, delta))
        else:
            print('  %-4s %-18s %+.4f  ok' % (mod, axis, delta))

    # The derived site must track the tongue: a modifier that moves the blade
    # without moving constriction_pos would leave the two disagreeing, and
    # nothing else checks that pair.
    b, m = values('t'), values('t̪')
    if b['constriction_pos'] == m['constriction_pos']:
        bad.append('t vs t̪: the derived site did not follow the tongue')

    # Known gaps must keep warning. If the warning is ever silenced, this is
    # the only thing that notices.
    for base, mod, name in GAP:
        r = subprocess.run([IPA2VEC, '-D', SCHEME, '-j', mod],
                           capture_output=True, text=True)
        if 'not in the loaded scheme' not in r.stderr:
            bad.append('%s: the documented gap no longer warns, so it is now '
                       'a silent no-op' % name)

    if bad:
        print('\nmodifier end-to-end check FAILED:')
        for x in bad:
            print('  - %s' % x)
        return 1
    print('\n%d modifier cases move the expected axis in the expected '
          'direction,\nthe derived site follows the tongue, and %d known gap '
          'still warns' % (len(CASES), len(GAP)))
    return 0


if __name__ == '__main__':
    sys.exit(main())