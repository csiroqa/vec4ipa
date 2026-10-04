"""Every file path a reader is told to open must exist.

This round put a lot of runnable detail into README.md and
docs/TONGUE-MODEL.md: the scheme file to pass to `-D`, the tools to run, the
JSON each script writes. A path that no longer exists is the same defect as a
stale literal -- the document says one thing and the repository is another --
and unlike prose drift it breaks the reader's first command.

Paths are read out of backticked spans rather than maintained as a list, so
this cannot itself go stale.

Run: python tools/check_doc_paths.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ['README.md', 'docs/TONGUE-MODEL.md']

# Spans that look like paths but are not: globs, regex fragments, flags.
SKIP = re.compile(r'^(\{|\*|\[|<|[-/]|/|\\)')

# A real repository path starts at a repository directory. Without this the
# scan matched notation like `i/j` ("i or j", a pair of IPA symbols) and
# `root_x/root_y` (two axis names) and reported them as missing files.
REPO_DIRS = ('tools/', 'src/', 'ui/', 'docs/')


def main():
    missing = []
    seen = 0
    for doc in DOCS:
        path = os.path.join(ROOT, doc)
        if not os.path.exists(path):
            missing.append('%s: the document itself is gone' % doc)
            continue
        src = io.open(path, encoding='utf-8').read()
        for m in re.finditer(r'`([^`\n]+)`', src):
            span = m.group(1).strip()
            if not re.match(r'^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)+$', span):
                continue
            if SKIP.match(span) or not span.startswith(REPO_DIRS):
                continue
            seen += 1
            full = os.path.join(ROOT, span.replace('/', os.sep))
            if not os.path.exists(full):
                line = src[:m.start()].count('\n') + 1
                missing.append('%s:%d  %s' % (doc, line, span))

    if missing:
        print('documents reference paths that do not exist:')
        for m in sorted(set(missing)):
            print('  - %s' % m)
        print('\nEach of these is something a reader is told to open or pass to '
              'a command;\nthe first one they try will fail.')
        return 1
    print('all %d repository paths named in the documents exist' % seen)
    return 0


if __name__ == '__main__':
    sys.exit(main())