"""Audit: which of the 16 SPEC-NEXT axes carry real, attested signal?

Three inventories are compared, so design intent and data availability stay
separable:

  1. the committed 16-dim table (tools/data/vec_table_16.json) -- the design
     ceiling: how much of each axis the table encodes at all?
  2. the Phatak 2008 consonant set that fits weights -- the self-check. It must
     report ZERO variance on exactly the axes that tools/fit_metric16.py pins in
     FIXED, otherwise this audit is measuring the wrong thing.
  3. the IPA segments that actually occur in the NorthEuraLex + SVMCC corpora
     under tools/data/corpus/ -- the availability ceiling.

Three measures are reported per axis, because they answer different questions.

Variance-style (`n_distinct`, `n_off_modal`, `var`): does the axis carry any
signal at all in this inventory? This is the measure that exposes the Phatak
problem, which is zero variance on the pinned axes -- not a missing minimal
pair. `n_off_modal` counts segments not sitting at the most common value, so no
invented neutral value is needed.

Strict minimal pairs (two segments agreeing on 15 axes, differing on one): the
cleanest statement of an isolated opposition, but read them as a floor. They are
near-zero everywhere, because a dense physical table moves p/b on voiced,
glottal_aperture and duration at once, so no pair ever differs on one axis alone.

`determines` reports the limit that variance cannot: axis j is determined by
axis k when every inventory segment sharing a k value also shares a j value. No
confusion data can separate such a pair no matter how much is collected. This is
a property of the scheme, not of the corpus.

Modifier coverage is reported separately (modifier codepoint frequency in the
corpora) because SPEC-NEXT encodes modifiers as rules on top of base rows, not
as rows; attributing their axis effects needs the C core's MODS table, which
this audit deliberately does not reimplement.

Run: python tools/audit_axis_coverage.py
"""

import collections
import io
import json
import os
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
CORPUS = os.path.join(DATA, 'corpus')

VEC = os.path.join(DATA, 'vec_table_16.json')
OUT = os.path.join(DATA, 'audit_axis_coverage.json')
SVMCC = ['abvd', 'bai', 'central_asian', 'chinese_1964', 'chinese_2004',
         'ielex', 'japanese', 'ob_ugrian', 'tujia']

# fit_metric16.py CONS, verbatim -- the inventory that fits the metric.
PHATAK = ['p', 't', 'k', 'f', 'θ', 's', 'ʃ', 'b', 'd', 'ɡ', 'v', 'ð', 'z',
          'ʒ', 'm', 'n']

# fit_metric16.py FIXED = [1, 5, 10, 11, 15] -> these axes are hand-pinned.
# The self-check asserts they carry no usable variance on PHATAK. "Usable" is a
# ratio, not zero: ʃ/ʒ do carry body=+0.40, so body is flat in practice but not
# literally constant, and fit_metric16's "no signal" comment is the loose one.
DEAD_AXES = ['body', 'tongue_root', 'glottal_tension', 'larynx_height',
             'airflow_direction']
NEAR_FLAT = 0.05   # var below this fraction of the loudest axis counts as flat

# Spacing IPA modifiers: combining marks are caught by category, these are not.
SPACING_MODS = set('ːˑˈˌ˞ⁿˡʰʷˠˤˀ˥˦˧˨˩')


def is_modifier(ch):
    return unicodedata.category(ch).startswith('M') or ch in SPACING_MODS


def load_table():
    d = json.load(io.open(VEC, encoding='utf-8'))
    return d['dims'], d['table']


def load_corpus_tokens():
    """Return (token -> count) over NorthEuraLex + SVMCC.

    Tokens are corpus-supplied, so unknown ones are counted, never dropped.
    """
    counts = collections.Counter()
    with io.open(os.path.join(CORPUS, 'northeuralex_ipa.txt'),
                 encoding='utf-8') as f:
        for line in f:
            for tok in line.split():
                counts[tok] += 1

    for name in SVMCC:
        path = os.path.join(CORPUS, 'svmcc_%s.tsv' % name)
        with io.open(path, encoding='utf-8') as f:
            header = f.readline().rstrip('\n').split('\t')
            col = header.index('tokens')
            for line in f:
                cells = line.rstrip('\n').split('\t')
                if len(cells) > col:
                    for tok in cells[col].split():
                        counts[tok] += 1
    return counts


def key_of(vec):
    return tuple(round(v, 6) for v in vec)


def variance_stats(dims, table, inventory):
    """Per axis: distinct values, segments off the modal value, population
    variance, and the segments carrying that signal."""
    segs = sorted(inventory)
    vecs = [key_of(table[s]) for s in segs]
    ndim = len(dims)
    n = len(segs)
    out = {}

    for k in range(ndim):
        vals = [v[k] for v in vecs]
        counts = collections.Counter(vals)
        modal = counts.most_common(1)[0][0]
        off = [segs[i] for i in range(n) if vals[i] != modal]
        mean = sum(vals) / n
        var = sum((x - mean) ** 2 for x in vals) / n
        out[dims[k]] = {
            'n_distinct': len(counts),
            'n_off_modal': len(off),
            'var': round(var, 6),
            'off_modal_segments': sorted(off),
        }
    return out


def minimal_pairs(dims, table, inventory):
    """Per axis: pairs differing there and nowhere else."""
    segs = sorted(inventory)
    vecs = [key_of(table[s]) for s in segs]
    ndim = len(dims)
    counts = [0] * ndim
    examples = [[] for _ in range(ndim)]
    for a in range(len(segs)):
        for b in range(a + 1, len(segs)):
            diff = [k for k in range(ndim)
                    if vecs[a][k] != vecs[b][k]]
            if len(diff) == 1:
                counts[diff[0]] += 1
                if len(examples[diff[0]]) < 3:
                    examples[diff[0]].append('%s/%s' % (segs[a], segs[b]))
    return counts, examples


def determines(dims, table, inventory):
    """axis -> axes it fully determines over this inventory.

    j is determined by k when the map (value of k) -> (value of j) is single
    valued. Such a pair is inseparable by any observational data: the corpus
    can contain both contrasts, but never the contrast that isolates one.
    """
    segs = sorted(inventory)
    vecs = [key_of(table[s]) for s in segs]
    result = {}
    for k, dk in enumerate(dims):
        fwd = {}
        for v in vecs:
            fwd.setdefault(v[k], set()).add(v)
        tied = sorted(dims[j] for j in range(len(dims))
                      if j != k
                      and all(len({v[j] for v in group}) == 1
                              for group in fwd.values()))
        if tied:
            result[dk] = tied
    return result


def classify_unknown(tokens, table):
    """Why a corpus token has no row: carrying a modifier, modifier-only, a
    longer sequence, or outside the IPA segment space entirely."""
    bases = set(table)
    out = {'carries_modifier': collections.Counter(),
           'modifier_only': collections.Counter(),
           'sequence': collections.Counter(),
           'out_of_space': collections.Counter()}
    for tok, n in tokens.items():
        if tok in bases:
            continue
        stripped = ''.join(ch for ch in tok if not is_modifier(ch))
        if stripped in bases:
            out['carries_modifier'][tok] = n
        elif stripped == '':
            out['modifier_only'][tok] = n
        elif len(stripped) > 1:
            out['sequence'][tok] = n
        else:
            out['out_of_space'][tok] = n
    return out


def main():
    dims, table = load_table()
    tokens = load_corpus_tokens()
    all_ours = set(table)
    in_corpus = all_ours & set(tokens)

    print('== 1. inventory sizes ==')
    print('  committed table rows        : %d' % len(all_ours))
    print('  distinct corpus tokens      : %d' % len(tokens))
    print('  table rows present in corpus: %d' % len(in_corpus))
    print('  table rows never attested   : %d  %s'
          % (len(all_ours - in_corpus), sorted(all_ours - in_corpus)))

    v_ph = variance_stats(dims, table, set(PHATAK))
    v_cor = variance_stats(dims, table, in_corpus)
    v_all = variance_stats(dims, table, all_ours)
    m_cor, ex_cor = minimal_pairs(dims, table, in_corpus)

    print('\n== 2. self-check: Phatak-16 must be flat on the FIXED axes ==')
    loudest = max(v_ph[d]['var'] for d in dims)
    ok = True
    for dim in DEAD_AXES:
        ratio = v_ph[dim]['var'] / loudest
        flag = 'flat' if ratio < NEAR_FLAT else 'FAIL'
        if ratio >= NEAR_FLAT:
            ok = False
        print('  %-22s off-modal = %-3d var = %-8.4f (%.1f%% of max) [%s]'
              % (dim, v_ph[dim]['n_off_modal'], v_ph[dim]['var'],
                 100 * ratio, flag))
    print('  self-check %s' % ('PASS' if ok else 'FAIL'))

    flat_free = [d for d in dims
                 if d not in DEAD_AXES
                 and v_ph[d]['var'] / loudest < NEAR_FLAT]
    print('  FITTED BUT FLAT (weight unconstrained by the fitting data):')
    print('        %s' % (', '.join(flat_free) or '(none)'))

    print('\n== 3. per-axis signal, table rows vs corpus rows ==')
    print('  %-22s %8s %8s | %8s %8s | %8s %8s'
          % ('axis', 'off/all', 'off/cor', 'var/all', 'var/cor',
             'dist/cor', 'min/cor'))
    for d in dims:
        print('  %-22s %8d %8d | %8.4f %8.4f | %8d %8d'
              % (d, v_all[d]['n_off_modal'], v_cor[d]['n_off_modal'],
                 v_all[d]['var'], v_cor[d]['var'],
                 v_cor[d]['n_distinct'], m_cor[dims.index(d)]))

    print('\n== 4. which corpus phonemes carry each formerly dead axis ==')
    for dim in DEAD_AXES:
        print('  %-22s %s' % (dim, ' '.join(v_cor[dim]['off_modal_segments'])))

    det_cor = determines(dims, table, in_corpus)
    det_all = determines(dims, table, all_ours)
    print('\n== 5. axes determined by another axis (inseparable by any data) ==')
    for label, det in (('all rows', det_all), ('corpus rows', det_cor)):
        print('  -- %s --' % label)
        for k, tied in det.items():
            print('     %-22s -> %s' % (k, ', '.join(tied)))
    if not det_all:
        print('     (none)')

    print('\n== 6. corpus tokens with no table row ==')
    unk = classify_unknown(tokens, table)
    for label in ['carries_modifier', 'modifier_only', 'sequence', 'out_of_space']:
        items = unk[label].most_common(10)
        print('  %-16s %6d occurrences, %4d distinct  %s'
              % (label, sum(unk[label].values()), len(unk[label]), items[:6]))

    report = {
        'dims': dims,
        'inventory': {
            'table_rows': len(all_ours),
            'corpus_tokens': len(tokens),
            'rows_in_corpus': len(in_corpus),
            'rows_never_attested': sorted(all_ours - in_corpus),
        },
        'phatak16_variance': v_ph,
        'table_rows_variance': v_all,
        'corpus_rows_variance': v_cor,
        'corpus_minimal_pairs': dict(zip(dims, m_cor)),
        'corpus_minimal_pair_examples': {dims[k]: ex_cor[k]
                                         for k in range(len(dims))},
        'determined_by': {'all_rows': det_all, 'corpus_rows': det_cor},
        'unknown_tokens': {k: dict(v.most_common(80)) for k, v in unk.items()},
    }
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()
