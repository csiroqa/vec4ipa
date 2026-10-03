"""Committed artifacts must match what the generators produce right now.

The basis, its table and its modifiers are all generated. When a generator
changes and its output is not committed, the repository silently holds two
different truths: the code says one thing, the data says another, and every
number measured from the data is one revision behind. That already happened
once this round -- tongue_forward.json was regenerated while writing §5.1.1 and
never committed, so the committed file no longer matched its generator.

This regenerates the deterministic outputs into a scratch copy and compares
them with what is committed. Nothing in the working tree is touched, so it is
safe to run, and it fails loudly rather than leaving a stale artifact behind.

The chain is run in dependency order, because each step reads the previous
one's output:

    gen_tongue_model -> gen_tongue_table -> gen_tongue_modifiers
                     -> gen_merged_basis  -> export_tongue_scheme

fit_tongue_forward and the gates are excluded: they read .rda corpora and take
minutes, and gate_retrieval embeds a timestamp-free but environment-dependent
result. Those two are checked by tools/check_doc_numbers.py instead, which
compares the figures the document cites against the committed artifacts.

Run: python tools/check_generated_current.py
"""

import filecmp
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
DATA = os.path.join(TOOLS, 'data')

# (script, outputs it writes) in dependency order.
CHAIN = [
    ('gen_tongue_table.py', ['tongue_table.json']),
    ('gen_tongue_modifiers.py', ['tongue_modifiers.json']),
    ('gen_merged_basis.py', ['merged_basis.json',
                             'summary_basis.json', 'summary_root.json',
                             'summary_height.json', 'summary_uheight.json',
                             'summary_vgap.json', 'summary_vheight.json',
                             'summary_both_glottal.json']),
    ('export_tongue_scheme.py', ['tongue.scheme']),
]


def run(script):
    r = subprocess.run([sys.executable, script], cwd=TOOLS,
                       capture_output=True, text=True,
                       env=dict(os.environ,
                                PYTHONPATH=TOOLS + os.pathsep +
                                os.environ.get('PYTHONPATH', '')))
    if r.returncode != 0:
        raise SystemExit('%s failed:\n%s' % (script, r.stderr[-800:]))


def main():
    stale = []
    # Back up only what this chain writes. tools/data also holds directories
    # and read-only corpora that shutil cannot copy.
    wanted = set()
    for _, outs in CHAIN:
        wanted.update(outs)
    with tempfile.TemporaryDirectory() as td:
        for name in wanted:
            src = os.path.join(DATA, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(td, name))

        for script, outs in CHAIN:
            run(script)
            for name in outs:
                a = os.path.join(DATA, name)
                b = os.path.join(td, name)
                if not os.path.exists(a):
                    stale.append('%s: committed file is missing' % name)
                elif not os.path.exists(b):
                    stale.append('%s: generator did not write it' % name)
                elif not filecmp.cmp(a, b, shallow=False):
                    stale.append(name)

    if stale:
        print('committed artifacts no longer match their generators:')
        for f in stale:
            print('  - %s' % f)
        print('\nRun the chain above and commit the result. A stale artifact '
              'means every number measured from it\nis one revision behind '
              'the code.')
        return 1
    print('all %d generated artifacts match their generators'
          % sum(len(o) for _, o in CHAIN))
    return 0


if __name__ == '__main__':
    sys.exit(main())
