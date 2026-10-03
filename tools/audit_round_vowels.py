"""Does the formant data say ɔ is rounded relative to ʌ?

The table says ɔ is a rounded vowel and ʌ is not; IPA agrees. Giving ɔ
lip_round = 0.90 rather than 0.00 costs 0.074 R2 in the F3 forward fit, because
the fitted lip_round coefficient is -269 Hz and that is a 242 Hz shift in its
prediction.

So either the acoustic data disagrees with the transcription, or the data is
too thin to settle it. This prints, per dataset, the mean F3 of every vowel
with its lip_round value, and pairs each rounded vowel with its unrounded
partner. Round vowels sit BELOW their partners in F3 if rounding lowers it,
so the table says directly whether ɔ behaves like the other rounded vowels.

Run: python tools/audit_round_vowels.py
"""

import collections
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import gen_tongue_model as tm              # noqa: E402
import fit_tongue_forward as F              # noqa: E402


def main():
    lr = {n: r for n, _, _, r in tm.VOWELS}
    per = collections.defaultdict(list)
    for (ds, ipa, f), vals in F.load().items():
        if f == 'f3' and ipa in lr:
            per[(ds, ipa)].extend(vals)

    print('%-8s %-5s %8s %10s' % ('dataset', 'vowel', 'F3 Hz', 'lip_round'))
    print('-' * 36)
    tally = collections.defaultdict(dict)
    for (ds, sym), vals in sorted(per.items()):
        mean = sum(vals) / len(vals)
        tally[sym][ds] = mean
        print('%-8s %-5s %8.0f %10.2f' % (ds, sym, mean, lr[sym]))

    print('\n== rounded vs unrounded partner, per dataset ==')
    print('A negative delta means the rounded vowel HAS the lower F3, which is'
          ' what\nrounding is supposed to do.  Compare ɔ against the other'
          ' rounded rows.\n')
    pairs = [('ɔ', 'ʌ'), ('ɒ', 'ɑ'), ('ʊ', 'u'), ('o', 'ɤ'), ('ø', 'e'),
             ('œ', 'ɛ'), ('y', 'i'), ('ʉ', 'ɨ'), ('ɶ', 'æ')]
    print('%-4s %-4s %8s %9s %6s' % ('rnd', 'unr', 'mean dF3', 'datasets',
                                    'signs'))
    for rnd, unr in pairs:
        if rnd not in tally or unr not in tally:
            continue
        shared = sorted(set(tally[rnd]) & set(tally[unr]))
        if not shared:
            print('%-4s %-4s   (no shared dataset)' % (rnd, unr))
            continue
        d = [tally[rnd][k] - tally[unr][k] for k in shared]
        mean_d = sum(d) / len(d)
        neg = sum(1 for x in d if x < 0)
        print('%-4s %-4s %8.0f %9d %6s'
              % (rnd, unr, mean_d, len(shared),
                 '%d/%d neg' % (neg, len(d))))

    out = os.path.join(ROOT, 'tools', 'data', 'round_vowels.json')
    io.open(out, 'w', encoding='utf-8').write(json.dumps(
        {k: dict(v) for k, v in tally.items()}, indent=1))
    print('\nwrote %s' % out)


if __name__ == '__main__':
    main()