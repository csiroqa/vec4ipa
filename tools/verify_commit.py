"""Build and test what is COMMITTED, not what happens to be in the tree.

This exists because of a defect this repo actually shipped. A commit added the
caller in ipa2vec_core.h without adding tongue_axes_resolve() in
tongue_contour.h, so every revision from there on failed to compile -- while
`make test` passed throughout, because make test builds and runs the WORKING
TREE. Green tests said nothing about whether the commit was sound. It took
`git archive HEAD | tar -x` into a scratch directory to see it.

So: extract the commit, build there, and run the fast suites there. A commit
that cannot build is not a commit.

Run: python tools/verify_commit.py            (checks HEAD)
     python tools/verify_commit.py --rev v1.2 (checks a tag)
"""

import argparse
import io
import os
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The suites that need a built binary and finish in seconds. test_metric_space
# is left out because it dominates the runtime and does not depend on the
# compile; it runs in `make test` for that reason.
FAST_SUITES = ['tools/test_spec_next.py', 'tools/test_suite.py',
               'tools/test_scheme_portability.py',
               'tools/audit_symbol_assignments.py']


def extract(rev, dest):
    ar = subprocess.run(['git', 'archive', rev], cwd=ROOT,
                        capture_output=True)
    if ar.returncode != 0:
        raise SystemExit('git archive %s failed: %s'
                         % (rev, ar.stderr.decode('utf-8', 'replace')))
    with tarfile.open(fileobj=io.BytesIO(ar.stdout)) as t:
        t.extractall(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rev', default='HEAD')
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        extract(args.rev, td)
        # The Makefile prefers python3 on POSIX; on Windows it falls back to
        # whatever `python` resolves to, which is what we want here.
        mk = os.path.join(td, 'Makefile')
        src = io.open(mk, encoding='utf-8').read()
        io.open(mk, 'w', encoding='utf-8').write(src)

        b = subprocess.run(['make'], cwd=td, capture_output=True, text=True,
                           shell=True)
        if b.returncode != 0:
            print('BUILD FAILED for %s' % args.rev)
            print(b.stdout[-3000:])
            print(b.stderr[-2000:])
            return 1
        print('build ok (%s)' % args.rev)

        bad = []
        for suite in FAST_SUITES:
            r = subprocess.run([sys.executable, os.path.join(td, suite)],
                               cwd=td, capture_output=True, text=True)
            last = [l for l in r.stdout.splitlines() if l.strip()][-1:] or ['']
            ok = r.returncode == 0
            print('  %-38s %s  %s' % (suite, 'ok ' if ok else 'FAIL',
                                      last[0][:48]))
            if not ok:
                bad.append(suite)
                print(r.stdout[-1500:])
                print(r.stderr[-800:])

        if bad:
            print('\n%s does not pass: %s' % (args.rev, ', '.join(bad)))
            return 1
        print('\n%s builds and passes.' % args.rev)
        return 0


if __name__ == '__main__':
    sys.exit(main())