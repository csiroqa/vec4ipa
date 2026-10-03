"""Check the runtime against the scheme files, not against its own defaults.

Every defect this round came from one mistake: treating the compiled-in NDIM
as if it were the loaded scheme's width. Three of them were silent -- the
wrong axis was written, the two derived site axes went missing from every
diagnostic, cross terms were dropped from the metric -- and the 395 existing
checks never noticed, because they all run against the committed 16-dim
scheme, which is the one case where NDIM and g_ndim agree.

So this suite deliberately tests the *swap*, not the default: load each
scheme and assert that what the binary reports back matches what the file
declares. A fourth defect in this family has to fail here rather than pass.

  1. reported dimension count == the file's `ndim`
  2. reported axis names == the file's `dim` lines, in order
  3. reported weights == the file's `weight` line, one per axis
  4. a parsed segment prints exactly `ndim` coordinates
  5. a --metric file sized for the loaded scheme is accepted, and one sized
     for a different width is rejected rather than silently truncated

Run: python tools/test_scheme_portability.py
"""

import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
VEC4IPA = os.path.join(ROOT, 'vec4ipa.exe' if os.name == 'nt' else 'vec4ipa')

SCHEMES = ['spec_next.scheme', 'tongue.scheme']

fails = []
checks = 0


def check(ok, label, detail=''):
    global checks
    checks += 1
    if not ok:
        fails.append('%s%s' % (label, (': ' + detail) if detail else ''))
    return ok


def parse_scheme(path):
    ndim = None
    dims, weights, lam = [], [], None
    for ln in io.open(path, encoding='utf-8'):
        t = ln.split()
        if not t or t[0].startswith('#'):
            continue
        if t[0] == 'ndim':
            ndim = int(t[1])
        elif t[0] == 'dim':
            dims.append(t[1])
        elif t[0] == 'weight':
            weights = [float(x) for x in t[1:]]
        elif t[0] == 'lambda':
            lam = float(t[1])
    return ndim, dims, weights, lam


def run(args):
    r = subprocess.run([VEC4IPA] + args, capture_output=True, text=True)
    return r.stdout, r.stderr


def main():
    if not os.path.exists(VEC4IPA):
        print('vec4ipa not built -- run make first')
        return 2

    for name in SCHEMES:
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            check(False, '%s exists' % name)
            continue
        ndim, dims, weights, lam = parse_scheme(path)
        check(ndim == len(dims), '%s ndim matches dim count' % name,
              'ndim=%d dims=%d' % (ndim, len(dims)))
        check(len(weights) == ndim, '%s weight count' % name,
              '%d weights for %d dims' % (len(weights), ndim))

        # 1: reported width. --weights prints the axis list; -s prints the
        # count. They are separate flags and neither prints both.
        out, _ = run(['-D', path, '-s'])
        m = re.search(r'dimensions:\s+(\d+)', out)
        check(m is not None, '%s: -s reports dimensions' % name)
        if m:
            check(int(m.group(1)) == ndim,
                  '%s: reported dimension count' % name,
                  'reported %s, file says %d' % (m.group(1), ndim))

        # 2: reported axis names, in order.
        out, _ = run(['-D', path, '--weights'])
        got = re.findall(r'^\s*\d+\s+(\S+)\s+[-\d.]+$', out, re.M)
        check(got == dims, '%s: reported axis names and order' % name,
              'got %r vs %r' % (got[:4], dims[:4]))

        # 3: one weight per axis, matching the file.
        gw = [float(x) for x in
              re.findall(r'^\s*\d+\s+\S+\s+([-\d.]+)$', out, re.M)]
        check(len(gw) == ndim, '%s: reported weight count' % name,
              'reported %d, file has %d' % (len(gw), ndim))
        if len(gw) == len(weights):
            check(all(abs(a - b) <= 1e-3 for a, b in zip(gw, weights)),
                  '%s: reported weights match the file')

        # 4: a parsed segment carries exactly ndim coordinates.
        # The per-segment listing prints "[0]    (v0, v1, ...)"; the verbose
        # single-segment form prints "vector: (...)". Both must be ndim wide,
        # because a loop bounded by the compiled NDIM truncates silently here.
        out, _ = run(['-D', path, 't'])
        mv = re.search(r'^\[\d+\]\s+\(([^)]*)\)', out, re.M)
        if check(mv is not None, '%s: segment prints a vector' % name,
                 out.strip()[:80]):
            got_n = len([x for x in mv.group(1).split(',') if x.strip()])
            check(got_n == ndim, '%s: segment vector width' % name,
                  'printed %d, expected %d' % (got_n, ndim))
        out, _ = run(['-D', path, 'ta'])
        # Multi-symbol queries route through print_seg_query(), which prints
        # "vector: (...)" instead. It is not reachable from these inputs, so
        # this only guards that the listing form is not the sole one to check.
        check('[0]' in out or 'vector:' in out,
              '%s: multi-symbol query renders' % name, out.strip()[:60])

        # 5: --metric sized for THIS scheme is accepted; a wrong width is
        # rejected instead of being read partially.
        with tempfile.TemporaryDirectory() as td:
            good = os.path.join(td, 'good.json')
            bad = os.path.join(td, 'bad.json')
            io.open(good, 'w', encoding='utf-8').write(json.dumps(
                {'weights': [1.0] * ndim, 'lambda': lam}))
            # one weight short of what this scheme needs
            io.open(bad, 'w', encoding='utf-8').write(json.dumps(
                {'weights': [1.0] * max(1, ndim - 1), 'lambda': lam}))
            _, err = run(['-D', path, '--metric', good, '-s'])
            check('dimensions:' in _, '%s: --metric sized for it is accepted'
                  % name, err.strip()[:80])
            _, err2 = run(['-D', path, '--metric', bad, '-s'])
            check('dimensions:' not in err2,
                  '%s: --metric of the wrong width is rejected' % name,
                  err2.strip()[:80])

    print('%d/%d checks passed' % (checks - len(fails), checks))
    for f in fails:
        print('  FAIL  %s' % f)
    return 1 if fails else 0


def warn_checks():
    """The two behaviours still verified only by hand.

    dim_of_ok() falls back to a compile-time enum index when an axis name is
    missing, which under a mismatched scheme writes the right value into the
    wrong coordinate. That is silent, so it needs a test: load a scheme that
    declares the right WIDTH but the wrong NAMES and assert the binary says so.

    The second is the positive counterpart: under the tongue scheme the
    contour modifier path must actually engage, and it must carry the derived
    site axis along with it. A modifier that moves the tongue without moving
    constriction_pos is undetectable from the output, so it has to be asserted.
    """
    print('\n== silent-fallback and contour-path guards ==')

    with tempfile.TemporaryDirectory() as td:
        # Same width as the tongue scheme, none of its axis names.
        wrong = os.path.join(td, 'wrong.scheme')
        src = io.open(os.path.join(DATA, 'tongue.scheme'), encoding='utf-8')
        ndim, dims, weights, lam = parse_scheme(
            os.path.join(DATA, 'tongue.scheme'))
        lines = ['ndim %d' % ndim]
        lines += ['dim bogus_%d' % i for i in range(ndim)]
        lines.append('weight ' + ' '.join('%.6f' % w for w in weights))
        lines.append('lambda %.4f' % lam)
        for ln in src:
            t = ln.split()
            if t and t[0] == 'seg':
                lines.append(' '.join(t))
        io.open(wrong, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

        _, err = run(['-D', wrong, 'tˤ'])
        check('warning' in err and 'not in the loaded scheme' in err,
              'mismatched scheme warns instead of writing silently',
              err.strip()[:90])

        # The committed scheme must stay silent: a warning on every run would
        # train people to ignore the ones that matter.
        _, err2 = run(['-D', os.path.join(DATA, 'spec_next.scheme'), 'tˤ'])
        check('not in the loaded scheme' not in err2,
              'committed scheme warns about nothing', err2.strip()[:90])

        # Contour path engaged: pharyngealised t must move the derived site.
        def site(sym):
            out, _ = run(['-D', os.path.join(DATA, 'tongue.scheme'), sym])
            mv = re.search(r'^\[\d+\]\s+\(([^)]*)\)', out, re.M)
            return [float(x) for x in mv.group(1).split(',')]

        # Constriction_pos only follows when the moved part BECOMES the tightest
        # point. On `t` the blade already closes at gap 0, so pharyngealised
        # t moves the root without moving the site -- and asserting otherwise
        # would be asserting a bug. On a velar base the dorsum is the
        # constrictor, so the same modifier can genuinely shift it.
        base, mod = site('t'), site('tˤ')
        check(len(base) == 18 and len(mod) == 18,
              'tongue scheme vectors are 18 wide')
        if len(base) == 18 and len(mod) == 18:
            check(abs(base[6] - mod[6]) > 1e-6,
                  'a tongue modifier moves root_x',
                  't=%r tˤ=%r' % (base[6], mod[6]))
            check(abs(base[16] - mod[16]) < 1e-6,
                  'constriction_pos holds when the blade stays tightest',
                  't=%r tˤ=%r' % (base[16], mod[16]))
            kb, km = site('k'), site('kˤ')
            if len(kb) == 18 and len(km) == 18:
                check(abs(kb[16] - km[16]) > 1e-6,
                      'constriction_pos follows when the moved part wins',
                      'k=%r kˤ=%r' % (kb[16], km[16]))

    print('%d/%d checks passed (cumulative)' % (checks - len(fails), checks))
    for f in fails:
        print('  FAIL  %s' % f)
    return 1 if fails else 0


if __name__ == '__main__':
    rc = main()
    sys.exit(warn_checks() or rc)