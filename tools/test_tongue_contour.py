"""Prove the C tongue_contour port and the Python model are the same function.

A port that is one guard clause different from its source is worse than no port:
the C runtime and the audit gates would score different geometry and nobody
would know which one the numbers belonged to. This compares them directly.

  roof()            1001 points across and past both ends of the scale
  constriction()    every one of the 133 committed segments, comparing x, gap
                    and the winning part (including the lips case)

Any difference is a defect in one of the two, not a tolerance question: both
are double precision doing the same arithmetic on the same constants.

Run: python tools/test_tongue_contour.py
"""

import io
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import gen_tongue_model as tm          # noqa: E402

PART_ID = {'tip': 0, 'blade': 1, 'dorsum': 2, 'root': 3, 'lips': -1}

PROBE = r'''
#include <stdio.h>
#include "tongue_contour.h"
int main(void)
{
    /* 1001 points from -0.2 to 1.2 so both end clamps are exercised.
     * The loop index is printed rather than x: %.10f rounds, and a rounded
     * key would compare roof() at two slightly different arguments. */
    for (int i = 0; i <= 1000; i++) {
        double x = -0.2 + 1.4 * i / 1000.0;
        printf("R %d %.17g\n", i, tongue_roof(x));
    }
    int n;
    if (scanf("%d", &n) != 1) return 2;
    for (int i = 0; i < n; i++) {
        TongueContour c;
        for (int p = 0; p < 4; p++) scanf("%lf %lf", &c.pt[p][0], &c.pt[p][1]);
        scanf("%lf %lf", &c.lip_open, &c.lip_round);
        double x, g; int part;
        tongue_constriction(&c, &x, &g, &part);
        printf("C %.10f %.17g %d\n", x, g, part);
    }
    return 0;
}
'''


def main():
    table = json.load(io.open(os.path.join(ROOT, 'tools', 'data',
                                          'tongue_table.json'), encoding='utf-8'))
    syms = sorted(table)

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'probe.c')
        exe = os.path.join(td, 'probe.exe' if os.name == 'nt' else 'probe')
        io.open(src, 'w', encoding='utf-8').write(PROBE)
        r = subprocess.run(['cc', '-O2', '-std=c11', '-I',
                            os.path.join(ROOT, 'src'), src, '-o', exe],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print('compile failed:\n%s' % r.stderr)
            return 1

        payload = ['%d' % len(syms)]
        for s in syms:
            e = table[s]
            for p in ('tip', 'blade', 'dorsum', 'root'):
                payload.append('%.17g %.17g' % (e['tongue'][p][0],
                                                e['tongue'][p][1]))
            payload.append('%.17g %.17g' % (e['lip_open'], e['lip_round']))
        r = subprocess.run([exe], input='\n'.join(payload) + '\n',
                           capture_output=True, text=True)
        if r.returncode != 0:
            print('probe failed: rc=%d %s' % (r.returncode, r.stderr))
            return 1
        lines = r.stdout.splitlines()

    roof_c = {}
    for ln in lines:
        if ln.startswith('R '):
            _, i, y = ln.split()
            roof_c[int(i)] = float(y)

    bad_roof = 0
    max_d = 0.0
    for i in range(1001):
        x = -0.2 + 1.4 * i / 1000.0
        want, got = tm.roof(x), roof_c[i]
        d = abs(want - got)
        max_d = max(max_d, d)
        if d > 1e-12:
            bad_roof += 1
    print('roof(): %d points, max abs difference %.3g, mismatches %d'
          % (1001, max_d, bad_roof))

    cons_c = [ln.split() for ln in lines if ln.startswith('C ')]
    bad_c, bad_g, bad_p = 0, 0, 0
    first = []
    for s, row in zip(syms, cons_c):
        cx, cg, cpart = float(row[1]), float(row[2]), int(row[3])
        cfg = {p: tuple(table[s]['tongue'][p]) for p in tm.TONGUE}
        cfg['lip_open'] = table[s]['lip_open']
        cfg['lip_round'] = table[s]['lip_round']
        want = tm.derived_constriction(cfg)
        wx, wg, wp = want[0], want[1], want[2]
        if abs(wx - cx) > 1e-12:
            bad_c += 1
        if abs(wg - cg) > 1e-12:
            bad_g += 1
        if PART_ID.get(wp, -99) != cpart:
            bad_p += 1
        if (bad_c or bad_g or bad_p) and len(first) < 6:
            first.append('  %-4s C=(%.10f, %.10f, %d)  PY=(%.10f, %.10f, %s)'
                         % (s, cx, cg, cpart, wx, wg, wp))
    print('constriction(): %d segments, x mismatches %d, gap mismatches %d, '
          'part mismatches %d' % (len(syms), bad_c, bad_g, bad_p))
    for ln in first:
        print(ln)

    ok = bad_roof == 0 and bad_c == 0 and bad_g == 0 and bad_p == 0
    print('\n%s' % ('PASS: the C port and the Python model agree exactly'
                    if ok else 'FAIL: the port has diverged'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
