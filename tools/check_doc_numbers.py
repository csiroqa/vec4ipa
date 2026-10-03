"""Fail when a number in TONGUE-MODEL.md no longer matches what was measured.

The prose in that document is the only place the project's conclusions live,
and every generator change moves the numbers under it. It drifted more than
once this round: the LOCO figure was three revisions out of date and the
reconstruction table two, because nothing compared the document against the
JSON it claims to report.

This does that comparison for the handful of figures the conclusions actually
rest on. Each entry names the artifact the number comes from and the pattern to
find in the document. A number that is absent is an error too -- if the section
is rewritten and the line drops out, the claim needs re-saying rather than
silently disappearing.

Deliberately not a general linter: it checks the anchors, not the prose, and a
reviewer still has to judge the wording.

Run: python tools/check_doc_numbers.py
"""

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
DOC = os.path.join(ROOT, 'docs', 'TONGUE-MODEL.md')


def main():
    doc = io.open(DOC, encoding='utf-8').read()
    gate = json.load(io.open(os.path.join(DATA, 'retrieval_gate.json'),
                            encoding='utf-8'))
    basis = json.load(io.open(os.path.join(DATA, 'merged_basis.json'),
                              encoding='utf-8'))
    clean = json.load(io.open(os.path.join(DATA, 'j6_new_clean.json'),
                              encoding='utf-8'))
    audit = json.load(io.open(os.path.join(DATA, 'symbol_audit.json'),
                              encoding='utf-8'))

    loco = gate['gate3_loco']['summary']['new/strict/act_prec'][
        'mean_excl_thin_folds']
    loco_clean = clean['loco']['mean_excl_thin_folds']
    ceiling = len({tuple(basis['table'][s]) for s in basis['table']})

    checks = [
        ('LOCO, new basis',
         loco,
         r'new\s+0\.\d{4}\s+\(mean_excl_thin\)'),
        ('LOCO, new basis cleaned',
         loco_clean,
         r'\u65b0\u57fa\u7ebf %d \u6839 0\.\d{4}' % len(clean['kept_dims'])),
        ('distinct base vectors',
         ceiling,
         r'\u4e0a\u9650 %d' % ceiling),
        ('symbol audit problems',
         audit['n_problems'],
         r'133 \u7b26\u53f7 %d \u95ee\u9898' % audit['n_problems']),
    ]

    bad = []
    for name, value, pat in checks:
        m = re.search(pat, doc)
        if not m:
            bad.append('%s: no line in the doc matches %s' % (name, pat))
            continue
        got = re.findall(r'0\.\d{4}|%d' % value, m.group(0))
        if str(round(value, 4)) not in got:
            bad.append('%s: doc says %r, measured %.4f'
                       % (name, m.group(0)[:60], value))

    if bad:
        print('TONGUE-MODEL.md is out of date with the measurements:')
        for b in bad:
            print('  - %s' % b)
        print('\nEither rerun the measurement or update the section; a stale '
              'number here is how a conclusion outlives its evidence.')
        return 1
    print('all %d headline figures in TONGUE-MODEL.md match the artifacts'
          % len(checks))
    return 0


if __name__ == '__main__':
    sys.exit(main())