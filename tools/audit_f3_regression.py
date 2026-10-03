"""Attribute the F3 forward-fit regression to this round's vowel-table edits.

The document recorded F3 R2 = 0.690 / RMSE 108.0 Hz at n=63. After this round's
vowel corrections it is 0.601 / 120.4 Hz at n=67. Those corrections rest on
evidence that is not in doubt -- ɔ had lip_round 0.00, identical to ʌ, and
ə ɪ ʏ were absent from VOWELS and fell through to the caller's fallback, which
happens to be schwa's coordinates -- so the question is not whether they were
right but what they cost.

This re-runs the fit with each edit reverted in isolation. It edits the real
generator in place rather than shadowing it with PYTHONPATH: fit_tongue_forward
puts tools/ at the front of sys.path itself, so a copy elsewhere is never
imported and the experiment would silently measure the committed file four
times. try/finally restores it whatever happens.

Run: python tools/audit_f3_regression.py
"""

import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, 'tools', 'gen_tongue_model.py')
FIT = os.path.join(ROOT, 'tools', 'fit_tongue_forward.py')

RE_O = (r"\('ɔ', 0\.42, 0\.30, 0\.90\)", "('ɔ', 0.42, 0.30, 0.00)")
RE_V = (r"\n    \('ɪ', 0\.225, 0\.56, -0\.20\), \('ʏ', 0\.225, 0\.56, 0\.90\),\n"
        r"    \('ə', 0\.35, 0\.46, 0\.50\),", "")

CASES = [
    ('as committed', False, False),
    ('ɔ only reverted', True, False),
    ('ə ɪ ʏ only reverted', False, True),
    ('both reverted', True, True),
]


def variant(src, revert_o, revert_v):
    t = src
    if revert_o:
        t = re.sub(*RE_O, t)
    if revert_v:
        t = re.sub(*RE_V, t)
    return t


def run_fit():
    r = subprocess.run([sys.executable, FIT], cwd=ROOT, capture_output=True,
                       text=True)
    m = re.search(r'F3\s+n=\s*(\d+)\s+R2 = ([\d.]+)\s+RMSE =\s*([\d.]+) Hz',
                  r.stdout)
    if not m:
        return None, (r.stdout[-400:] + r.stderr[-400:])
    return (int(m.group(1)), float(m.group(2)), float(m.group(3))), ''


def main():
    original = io.open(MODEL, encoding='utf-8').read()
    results = {}
    try:
        print('%-26s %5s %8s %10s' % ('variant', 'n', 'R2', 'RMSE Hz'))
        print('-' * 54)
        for label, ro, rv in CASES:
            text = variant(original, ro, rv)
            if not ro and not rv and text != original:
                print('%-26s  FAILED: patterns did not match the committed '
                      'source' % label)
                return 1
            io.open(MODEL, 'w', encoding='utf-8').write(text)
            row, err = run_fit()
            if row is None:
                print('%-26s  FAILED: %s' % (label, err.strip()[:70]))
                continue
            results[label] = row
            print('%-26s %5d %8.3f %10.1f' % ((label,) + row))
    finally:
        io.open(MODEL, 'w', encoding='utf-8').write(original)

    if io.open(MODEL, encoding='utf-8').read() != original:
        print('\nFAIL: the generator was not restored')
        return 1

    doc = io.open(os.path.join(ROOT, 'docs', 'TONGUE-MODEL.md'),
                  encoding='utf-8').read()
    m = re.search(r'\*\*F3\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*([\d.]+)\*\*\s*\|'
                  r'\s*\*\*([\d.]+) Hz\*\*', doc)
    if m:
        print('\ndocument claims: n=%s R2=%s RMSE=%s Hz'
              % (m.group(1), m.group(2), m.group(3)))
    out = os.path.join(ROOT, 'tools', 'data', 'f3_regression.json')
    io.open(out, 'w', encoding='utf-8').write(json.dumps(results, indent=1))
    print('wrote %s  (generator restored)' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())