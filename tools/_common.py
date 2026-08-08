#!/usr/bin/env python3
"""Shared helpers for the tools/ test & generator scripts.

Imported by test_suite.py, test_standard_chinese.py, test_metric_space.py
and fuzz_metric_space.py; run from the repo root as `python tools/foo.py`
so that `import _common` resolves to this file.

Scripts using `check()` must assign their primary binary to
`_common.EXE` first (check() runs argv against that exe); the shared
`run(exe, args)` wrapper handles the rest.
"""

import re
import subprocess

MD_LINE_RE = re.compile(r'^`/([^/`]*)/`(?: \([^)]*\))?: `\((.*)\)`$')

EXE = None          # primary binary for check(); set by the importing script
total = 0
fails = 0


def run(exe, args):
    return subprocess.run([exe] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def parse_rebuilt(out):
    """Vector spelled by vec2ipa after '->  /' (trailing slash/linefeeds off)."""
    return out.split("->  /")[-1].rstrip("/\n")


def parse_vector(s):
    """The 16 values of a vector line, between the first ( and )."""
    return s.split("(")[1].split(")")[0]


def check(name, argv, expect_rc=0, expect_segs=None, expect_tone=None,
          expect_note=None, expect_warn=None):
    global total, fails
    total += 1
    r = run(EXE, argv)
    ok = (r.returncode == expect_rc)
    if ok and expect_segs is not None:
        n = len([l for l in r.stdout.splitlines() if l.strip().startswith("[")])
        ok = (n == expect_segs)
    if ok and expect_tone is not None:
        ok = expect_tone in r.stdout
    if ok and expect_note is not None:
        ok = expect_note in r.stderr
    if ok and expect_warn is not None:
        ok = expect_warn in r.stderr
    if not ok:
        fails += 1
        print(f"FAIL: {name}")
        print(f"  rc={r.returncode} (want {expect_rc})")
        if expect_segs is not None:
            print(f"  segs={len([l for l in r.stdout.splitlines() if l.strip().startswith('[')])} (want {expect_segs})")
        print(f"  stdout: {r.stdout.strip()[:120]!r}")
        print(f"  stderr: {r.stderr.strip()[:120]!r}")
    return ok
