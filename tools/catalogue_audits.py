"""Classify every script under tools/ as a gate or a report, mechanically.

Sixteen audit_*.py scripts exist and none of them is run by `make test`. A
reader reasonably assumes a file called `audit_` guards something; none of
these do, and two of them (audit_modifier_collisions, and the collision
variant) were tried as gates and could not be shown to fail.

Rather than force a threshold onto an exploratory report, this records what
each script actually does, so "is this a check?" has an answer that is derived
from the code rather than from its filename:

  GATE    exits non-zero on a bad result AND is wired into `make test`
  CLAIMED exits non-zero on a bad result but is NOT wired, because the
          threshold could not be shown to fire
  REPORT  always exits zero; prints numbers for a human to read

The classification is generated, not hand-maintained: it reads sys.exit /
return from each script and the Makefile. If someone wires a script up, this
stops saying it is a report.

Run: python tools/catalogue_audits.py
"""

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
DATA = os.path.join(TOOLS, 'data')
OUT = os.path.join(DATA, 'audit_catalogue.json')


def exits_nonzero(path):
    """True when the script can return non-zero from its __main__ path."""
    src = io.open(path, encoding='utf-8').read()
    if re.search(r'sys\.exit\(', src):
        return True
    if re.search(r'if __name__ == .__main__.:\s*\n\s*sys\.exit', src):
        return True
    tail = src.split("if __name__ ==")[-1] if "if __name__ ==" in src else src
    return bool(re.search(r'return\s+[1-9]', tail))


def wired(path):
    mk = io.open(os.path.join(ROOT, 'Makefile'), encoding='utf-8').read()
    return ('tools/' + os.path.basename(path)) in mk


def main():
    scripts = sorted(f for f in os.listdir(TOOLS)
                     if re.match(r'(audit|check|test|verify)_.*\.py$', f))
    rows = []
    for name in scripts:
        path = os.path.join(TOOLS, name)
        can_fail = exits_nonzero(path)
        in_make = wired(path)
        if in_make and can_fail:
            kind = 'GATE'
        elif can_fail and not in_make:
            kind = 'CLAIMED'
        else:
            kind = 'REPORT'
        rows.append({'script': name, 'kind': kind,
                     'in_make_test': in_make, 'can_fail': can_fail})

    counts = {}
    for r in rows:
        counts[r['kind']] = counts.get(r['kind'], 0) + 1
    print('%-44s %-8s %s' % ('script', 'kind', 'in make test'))
    for r in rows:
        print('%-44s %-8s %s' % (r['script'], r['kind'], r['in_make_test']))
    print('\n%s' % ', '.join('%s %d' % (k, counts[k]) for k in sorted(counts)))

    io.open(OUT, 'w', encoding='utf-8').write(
        json.dumps({'rows': rows, 'counts': counts}, indent=1))
    print('wrote %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())