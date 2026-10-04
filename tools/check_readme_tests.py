"""The README's test list must match what `make test` actually runs.

The README grew a hand-maintained list of the checks, and it went stale within
the same round it was written: three checks added that day never made it in,
while two scripts that are deliberately NOT in `make test` sat in the list
looking identical to the ones that are.

A list that looks right but names the wrong set is worse than no list, because
a reader uses it to decide what is verified.

Manual-run scripts are declared in a trailing sentence rather than by name in
the block, so this check can require the two lists to agree exactly.

Run: python tools/check_readme_tests.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    mk = io.open(os.path.join(ROOT, 'Makefile'), encoding='utf-8').read()
    # Only the `test:` target's commands. Matching every tools/*.py in the
    # Only the `test:` target's commands. Matching every tools/*.py in the
    # Makefile also catches build rules (gen_vectors_h.py, gen_readme_embed.py
    # are dependencies of targets, not checks). The target ends at the next
    # unindented line -- a blank line can sit inside it, because the recipe
    # carries indented comments.
    tstart = mk.index('\ntest:')
    tend = len(mk)
    for line in mk[tstart + 1:].split('\n'):
        if line.strip() and not line.startswith(('\t', ' ')):
            break
        tend += len(line) + 1
    body = mk[tstart:tend]
    in_make = set(re.findall(r'tools/([a-z0-9_]+\.py)', body))
    rd = io.open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()

    # Scripts the README names as hand-run, outside the fenced block.
    tail = rd.split('Not part of `make test`')[-1] if \
        'Not part of `make test`' in rd else ''
    manual = set(re.findall(r'`([a-z0-9_]+\.py)`', tail))
    block = rd.split('Not part of `make test`')[0]
    in_readme = set(re.findall(r'tools/([a-z0-9_]+\.py)', block)) | manual

    missing = sorted(in_make - in_readme)
    extra = sorted(in_readme - in_make - manual)

    if missing or extra:
        print('README.md test list disagrees with the Makefile:')
        for m in missing:
            print('  - %s runs in make test but is not listed' % m)
        for e in extra:
            print('  - %s is listed but does not run in make test' % e)
        return 1
    print('README lists all %d checks make test runs (%d declared hand-run)'
          % (len(in_make), len(manual)))
    return 0


if __name__ == '__main__':
    sys.exit(main())