"""The document's own structure: sequential numbering and live cross-references.

check_doc_numbers.py guards the figures. This guards the shape, which decays
silently and is invisible to every other check:

  * subsections numbered out of order -- 0.9 ran ...11, 13, 14, 15, 12 because
    each defect investigation appended a section where it found one
  * a cross-reference to a section that no longer exists, or that was folded
    into a neighbour -- 3 of those survived the renumbering because the §
    regex in the renumbering script was written as a literal S instead of §
  * a gap in the sequence (0.11.4 never existed at all)

A stale cross-reference is worse than a stale number: it sends the reader to
the wrong section with no error anywhere.

Run: python tools/check_doc_structure.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'TONGUE-MODEL.md')


def main():
    src = io.open(DOC, encoding='utf-8').read()

    heads = [(m.group(1), m.group(2)) for m in
             re.finditer(r'^(#{1,4}) (\S+ .*)$', src, re.M)]
    numbers = [t.split()[0] for _, t in heads]
    bad = []

    # 1. Sequential numbering within each dotted family (0.9.1, 0.9.2, ...).
    fam = {}
    for lvl, t in heads:
        num = t.split()[0]
        m = re.match(r'^(\d+(?:\.\d+)*)$', num)
        if m and '.' in num:
            fam.setdefault(num.rsplit('.', 1)[0], []).append((num, lvl))
    for prefix, items in fam.items():
        seen = [n for n, _ in items]
        # Only judge families whose last component is a small integer; larger
        # values are enumerations, not sequence labels.
        try:
            ints = [int(n.rsplit('.', 1)[1]) for n in seen]
        except ValueError:
            continue
        if max(ints) > 40:
            continue
        want = list(range(1, len(ints) + 1))
        if ints != want:
            bad.append('%s numbering is %s, expected %s'
                       % (prefix, ints, want))
        # A subsection may not jump a heading level relative to its siblings.
        lv = {l for _, l in items}
        if len(lv) > 1:
            bad.append('%s mixes heading levels %s' % (prefix, sorted(lv)))

    # 2. Every §-reference must resolve to a heading that exists.
    known = set(numbers)
    refs = set(re.findall(r'§(\d+(?:\.\d+)+)', src))
    for r in sorted(refs):
        if r not in known:
            bad.append('dangling cross-reference: §%s' % r)

    # 3. Duplicate section numbers would make a reference ambiguous.
    dupes = sorted({n for n in numbers if numbers.count(n) > 1})
    if dupes:
        bad.append('duplicate section numbers: %s' % ', '.join(dupes))

    if bad:
        print('TONGUE-MODEL.md structure is off:')
        for b in bad:
            print('  - %s' % b)
        print('\nThese are invisible to the figure check: a document can quote '
              'correct numbers\nand still send the reader to a section that '
              'does not exist.')
        return 1
    print('structure ok: %d headings, %d cross-references, all resolve'
          % (len(heads), len(refs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())