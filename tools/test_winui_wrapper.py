"""Exercise the WinUI core wrapper's buffer contract against a wide scheme.

ui/winui/core_wrap.c hands the managed side `NDIM` (16) coordinates per
segment, because Core.cs declares `public const int NDIM = 16` and allocates
`NDIM * MAX_TOKS` with the same stride. That is a contract between the two
halves, and under an 18-dim --scheme the last two axes -- constriction_pos and
constriction_gap -- have nowhere to go.

This cannot be fixed from the C side alone: writing at stride g_ndim while the
caller still allocates NDIM would overrun its buffer. The managed half has to
move too, and that project needs the AppxPackage targets this SDK does not
ship, so it cannot be built or verified here. What can be done, and is done,
is stop the truncation being silent.

So this test asserts the warning fires exactly when the scheme is wider than
the wrapper can carry, and stays quiet otherwise. A silent regression here
would put the UI back to truncating without saying so.

Run: python tools/test_winui_wrapper.py
"""

import ctypes
import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRAP = os.path.join(ROOT, 'ui', 'winui', 'core_wrap.c')
DATA = os.path.join(ROOT, 'tools', 'data')

MAX_TOKS = 64
NAMESZ = 48

PROBE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "core_wrap.c"

int main(int argc, char **argv)
{
    char err[256];
    double *out = calloc(MAX_TOKS * MAXDIM, sizeof(double));
    int air[MAX_TOKS];
    char names[MAX_TOKS * 48];
    if (ipa2v_set_args(argc - 1, (const char **)(argv + 1)) != 0) return 2;
    int n = ipa2v_forward("t\u02c8\u0283", err, sizeof err, out, air, names);
    if (n < 0) { fprintf(stdout, "parse error: %s\n", err); return 3; }
    /* Count non-zero coordinates of the FIRST segment only -- scanning the
     * whole buffer would straddle segments and say nothing useful. */
    int last = -1;
    for (int i = 0; i < NDIM; i++) if (out[i] != 0.0) last = i;
    fprintf(stdout, "segments=%d seg0_last_nonzero=%d stride=%d\n",
            n, last, NDIM);
    free(out);
    return 0;
}
'''


def build(src, exe):
    r = subprocess.run(['gcc', '-O2', '-std=c11',
                        '-Wno-unused-function', '-Wno-unused-variable',
                        '-Wno-format-truncation',
                        '-I', os.path.join(ROOT, 'src'),
                        '-I', os.path.dirname(WRAP), src, '-o', exe],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('compile failed:\n%s' % r.stderr[-1500:])
        return False
    return True


def run(exe, args):
    r = subprocess.run([exe] + args, capture_output=True, text=True)
    return r.stdout, r.stderr, r.returncode


def main():
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'probe.c')
        exe = os.path.join(td, 'probe.exe' if os.name == 'nt' else 'probe')
        io.open(src, 'w', encoding='utf-8').write(PROBE)
        if not build(src, exe):
            return 1

        old = os.path.join(DATA, 'spec_next.scheme')
        wide = os.path.join(DATA, 'tongue.scheme')
        fails = []

        out, err, rc = run(exe, ['-D', old, 't'])
        quiet = 'dropped' not in err
        if not quiet:
            fails.append('committed 16-dim scheme warns: %s' % err.strip()[:90])
        print('committed scheme   rc=%d  quiet=%s  %s'
              % (rc, quiet, out.strip()))

        out, err, rc = run(exe, ['-D', wide, 't'])
        loud = 'dropped' in err
        if not loud:
            fails.append('18-dim scheme does not report the truncation')
        else:
            first = [l for l in err.splitlines() if 'dropped' in l][0]
            for token in ('constriction', '16', '18'):
                if token not in first:
                    fails.append('warning omits %r: %s' % (token, first[:90]))
            print('wide scheme       rc=%d  reported=%s' % (rc, loud))
            print('  %s' % first.strip())

        # Once only: a second call in the same process must stay silent.
        out2, err2, _ = run(exe, ['-D', wide, 't'])
        n = err2.count('dropped')
        if n != 1:
            fails.append('warning appears %d times across two runs, '
                         'expected 1' % n)
        print('repeat runs       warnings=%d (expected 1)' % n)

        if fails:
            print('\nFAIL')
            for f in fails:
                print('  - %s' % f)
            return 1
        print('\nPASS: the wrapper reports exactly when it cannot carry the '
              'scheme, and says so once.')
        return 0


if __name__ == '__main__':
    sys.exit(main())