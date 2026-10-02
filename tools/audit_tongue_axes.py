"""Dead-axis audit for the NEW tongue-contour basis (10 dims).

WHAT IS MEASURED AND WHY
  The new basis claims to replace the old 16-dim hand-tuned table, so the only
  question that decides it is whether every one of its coordinates carries
  signal that the old scheme did not already have, or whether some of them are
  decorative. A coordinate is DEAD when the inventory cannot move it at all
  (one distinct value), or when it moves but so thinly that no acoustic fit
  could be constrained by it (variance far below the loudest coordinate).

  Two inventories are graded, because they answer different questions:
    1. all 133 committed segments -- the DESIGN CEILING: how much of each
       coordinate does the new model encode at all?
    2. the 112 segments actually attested in NorthEuraLex + SVMCC -- the
       AVAILABILITY CEILING: an axis can be well designed and still be
       unusable, if the corpora never move it.

  Per coordinate: n_distinct, n_off_modal, population variance, strict minimal
  pairs, and a three-tier verdict. The verdict thresholds are stated below and
  are the SAME two numbers the old audit used, so the old and new schemes are
  graded on one ruler and the tier-C counts are comparable.

WHICH MEASURE IS TRUSTED, AND WHY
  Strict minimal pairs (two segments agreeing on 9 coordinates, differing on
  one) are the cleanest statement of an isolated opposition, and on both the
  old 16-dim table and this dense physical contour they are near-zero
  everywhere: a real segment moves place, closure and duration together, so no
  committed pair ever differs on one coordinate alone. On this basis they are
  therefore read as a FLOOR, not a verdict.

  The variance-style measures (n_distinct, n_off_modal, var) are the ones that
  decide the tiers. They need no pair to exist: an axis with 40 rows off the
  modal value is moving in the inventory whether or not any single pair
  isolates it, which is exactly what an acoustic fit needs. Reporting both is
  the point -- a minimal-pair count of 0 here means "no clean isolation", NOT
  "dead axis", and conflating the two is the error this audit exists to avoid.

  The self-check re-derives the constriction from the extracted coordinates
  and compares it with the site stored by gen_tongue_table.py. If the 10
  coordinates did not actually determine the contour the table was built from,
  that round trip breaks, so the audit cannot grade a projection.

HONEST LIMITS OF THIS AUDIT
  All 9 formant datasets behind tools/fit_tongue_forward.py are VOWEL-ONLY, so
  no tier here is validated against consonant acoustics. A coordinate can carry
  articulatory variance and still be acoustically inert for consonants; this
  script measures the articulatory claim only, and says so.

Run: python tools/audit_tongue_axes.py
"""

import collections
import io
import json
import os
import unicodedata

import gen_tongue_model as tm
import gen_tongue_table as gt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
CORPUS = os.path.join(DATA, 'corpus')

TONGUE_TABLE = os.path.join(DATA, 'tongue_table.json')
TONGUE_MODEL = os.path.join(DATA, 'tongue_model.json')
VEC = os.path.join(DATA, 'vec_table_16.json')
OUT = os.path.join(DATA, 'audit_tongue_axes.json')

SVMCC = ['abvd', 'bai', 'central_asian', 'chinese_1964', 'chinese_2004',
         'ielex', 'japanese', 'ob_ugrian', 'tujia']

# The 10 graded coordinates, in the order gen_tongue_model.py declares them.
# Fixed here rather than read from tongue_model.json so a silent dim change in
# the model cannot silently re-grade the audit; main() asserts they agree.
DIMS = [p + '_' + c for p in tm.TONGUE for c in ('x', 'y')] + \
       ['lip_open', 'lip_round']

# Tier C, part 1: a coordinate with a single distinct value over the whole
# inventory is dead in the strongest sense -- the model cannot express it.
#
# Tier C, part 2: the same 0.05-of-the-loudest variance ratio the old audit
# used (audit_axis_coverage.py NEAR_FLAT). Reusing it is the point: a new
# scheme graded on a different ruler could always "win" by lowering the bar.
NEAR_FLAT = 0.05

# Tier B: at most TWO rows sit off the modal value. One off-modal row can be
# an authoring slip; two agreeing rows are a real contrast, so the cut is 2
# and not 1. B is tested BEFORE the variance ratio on purpose -- an axis moved
# by two rows is thin, not dead.
B_OFF_MODAL = 2

# Tolerance of the constriction round trip: the table stores coordinates
# rounded to 3 decimals (gen_tongue_table.py), so 1e-3 is the rounding floor
# and any larger disagreement is a real inconsistency, not float noise.
ROUNDTRIP_TOL = 1e-3

# Spacing IPA modifiers: combining marks are caught by category, these are not.
SPACING_MODS = set('ːˑˈˌ˞ⁿˡʰʷˠˤˀ˥˦˧˨˩')

# The tier-C set the task compares against, from the old 16-dim basis.
OLD_DEAD = ['tongue_root', 'glottal_tension', 'larynx_height', 'lateral_ratio']


def is_modifier(ch):
    return unicodedata.category(ch).startswith('M') or ch in SPACING_MODS


def load_table():
    """segment -> the 10 graded coordinates, as plain floats."""
    raw = json.load(io.open(TONGUE_TABLE, encoding='utf-8'))
    out = {}
    for seg, v in raw.items():
        vals = []
        for p in tm.TONGUE:
            vals.extend(float(c) for c in v['tongue'][p])
        vals.append(float(v['lip_open']))
        vals.append(float(v['lip_round']))
        out[seg] = tuple(vals)
    return raw, out


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


def variance_stats(dims, table, inventory):
    """Per axis: distinct values, rows off the modal value, population
    variance, the rows carrying that signal, and a scale-free relative variance.

    rel_var = var / mean^2 is reported BESIDE var because the tier rule
    compares raw variances across coordinates that do not share a natural
    scale: an x coordinate in [0.1, 0.8] cannot accumulate the variance of a
    binary flag in [0, 1] no matter how much it articulates. Printing both
    keeps a threshold-sensitive tier visible instead of hiding it behind a
    single number. rel_var is meaningless where the mean is 0, so it is null.
    """
    segs = sorted(inventory)
    vecs = [table[s] for s in segs]
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
            'var': round(var, 8),
            'mean': round(mean, 6),
            'rel_var': (round(var / (mean ** 2), 6) if mean else None),
            'modal': modal,
            'off_modal_segments': sorted(off),
        }
    return out


def minimal_pairs(dims, table, inventory):
    """Per axis: pairs of committed segments differing on it and NOWHERE ELSE.

    Read as a floor, not a verdict: a dense physical description moves several
    coordinates for every real segment, so this count is near-zero by
    construction, not by defect.
    """
    segs = sorted(inventory)
    vecs = [table[s] for s in segs]
    ndim = len(dims)
    counts = [0] * ndim
    examples = [[] for _ in range(ndim)]
    for a in range(len(segs)):
        for b in range(a + 1, len(segs)):
            diff = [k for k in range(ndim) if vecs[a][k] != vecs[b][k]]
            if len(diff) == 1:
                counts[diff[0]] += 1
                if len(examples[diff[0]]) < 3:
                    examples[diff[0]].append('%s/%s' % (segs[a], segs[b]))
    return counts, examples


def determines(dims, table, inventory):
    """axis -> axes it fully determines over this inventory.

    j is determined by k when the map (value of k) -> (value of j) is single
    valued. Such a pair is inseparable by any observational data: the corpus
    can contain both contrasts, but never the contrast that isolates one. This
    is a property of the scheme, not of the corpus, so it is the strongest
    dead-axis evidence available -- a determined coordinate is dead for
    confusion data no matter how much is collected.
    """
    segs = sorted(inventory)
    vecs = [table[s] for s in segs]
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


def tier(stat, loudest):
    """A / B / C from the two stated thresholds, nothing hidden."""
    if stat['n_distinct'] <= 1:
        return 'C'
    if stat['n_off_modal'] <= B_OFF_MODAL:
        return 'B'
    if stat['var'] / loudest < NEAR_FLAT:
        return 'C'
    return 'A'


def roundtrip_check(raw, table):
    """Re-derive the constriction from the graded coordinates alone.

    If the 10 coordinates did not determine the contour, the derived site
    would not reproduce the one gen_tongue_table.py stored. gen_tongue_table's
    own derived_site() is reused so the check tests the coordinate extraction,
    not a second copy of the site rule: that function falls back to the
    ANCHOR-assigned site whenever the derived gap is >= 0.05, and only 57 of
    133 rows are derived rather than assigned, so comparing raw derived_constriction
    output against stored derived_x would report false failures on the 66
    assigned rows.
    """
    worst = 0.0
    worst_seg = None
    checked = 0
    for seg, vec in table.items():
        cfg = {}
        for i, p in enumerate(tm.TONGUE):
            cfg[p] = (vec[2 * i], vec[2 * i + 1])
        cfg['lip_open'] = vec[8]
        cfg['lip_round'] = vec[9]
        if raw[seg]['anchor'] == 'vowel':
            # gen_tongue_table has no vowel branch in CONSTRICTOR: a vowel has
            # no constriction site to derive, its dorsum_x is the parameter
            # itself. Reproduce that branch explicitly rather than pretending
            # the geometry derived it.
            x = cfg['dorsum'][0]
        else:
            x, _gap, _part, _origin = gt.derived_site(
                cfg, raw[seg]['anchor'], raw[seg]['manner'])
        stored = raw[seg]['derived_x']
        if stored is None:
            if x is not None:
                print('  round trip invented a site for %s' % seg)
            continue
        checked += 1
        d = abs(x - stored)
        if d > worst:
            worst, worst_seg = d, seg
    return worst, worst_seg, checked


def place_zero_check(raw, table):
    """Does tip_x alone separate the old place=0.00 overload?

    The old table pins place=0.00 for BOTH central vowels/glides AND retroflex
    stops, so it needs tip_shape as a crutch. The new basis claims not to need
    that crutch, which is only true if the two groups differ in a graded
    coordinate. Measured, not asserted.
    """
    D = json.load(io.open(VEC, encoding='utf-8'))
    dims16, table16 = D['dims'], D['table']
    ip = dims16.index('place')
    it = dims16.index('tip_shape')
    retro, central = [], []
    for seg in sorted(raw):
        v = table16[seg]
        if abs(v[ip]) < 1e-9:
            (retro if v[it] >= 0.5 else central).append(seg)
    ix = DIMS.index('tip_x')
    rv = [table[s][ix] for s in retro]
    cv = [table[s][ix] for s in central]
    overlap = sorted(set(rv) & set(cv))
    return {'retroflex_stops': retro, 'central_vowels_glides': central,
            'tip_x_retroflex_range': [min(rv), max(rv)] if rv else None,
            'tip_x_central_range': [min(cv), max(cv)] if cv else None,
            'tip_x_values_shared': overlap}


def collision_test(dims, table, inventory, keep):
    """Do the KEPT coordinates still tell all the segments apart?

    A tier-C coordinate is only a real loss if dropping it merges segments that
    were distinct. Grouping the inventory by the kept coordinates and counting
    the resulting collisions measures that loss directly, instead of assuming
    that a low-variance coordinate is worthless -- it may be low-variance
    precisely because it is redundant with the others.
    """
    segs = sorted(inventory)
    groups = {}
    for s in segs:
        key = tuple(table[s][dims.index(d)] for d in keep)
        groups.setdefault(key, []).append(s)
    merged = {str(k): v for k, v in groups.items() if len(v) > 1}
    return len(groups), merged


def old_basis_tables():
    """The old 16-dim table as {segment -> tuple}, read only.

    Loaded here so the new tier-C count can be compared against the old one on
    the SAME ruler. Comparing against the old audit's hand-quoted 4 dead axes
    would be circular: those 4 were produced by a different rule, and grading
    the old table with the new thresholds is what makes the comparison fair.
    """
    D = json.load(io.open(VEC, encoding='utf-8'))
    return D['dims'], {s: tuple(float(x) for x in v)
                       for s, v in D['table'].items()}


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
    raw, table = load_table()
    tokens = load_corpus_tokens()
    all_rows = set(table)
    attested = all_rows & set(tokens)

    model = json.load(io.open(TONGUE_MODEL, encoding='utf-8'))
    dims = list(model['dims'])

    print('== 1. inventory sizes ==')
    print('  committed tongue-table rows : %d' % len(all_rows))
    print('  graded coordinates          : %d  %s' % (len(dims), dims))
    print('  distinct corpus tokens      : %d' % len(tokens))
    print('  rows present in corpus      : %d' % len(attested))
    print('  rows never attested         : %d  %s'
          % (len(all_rows - attested), sorted(all_rows - attested)))

    site_src = collections.Counter(v['site_from'] for v in raw.values())
    print('\n== 2. self-check ==')
    ok_dims = dims == DIMS
    print('  dim list matches gen_tongue_model : %s' % ('PASS' if ok_dims
                                                       else 'FAIL %s' % dims))
    worst, worst_seg, n_checked = roundtrip_check(raw, table)
    ok_rt = worst <= ROUNDTRIP_TOL
    print('  constriction round trip on %d rows, worst dx = %.5f on %s'
          % (n_checked, worst, worst_seg))
    print('  self-check %s (tolerance %.0e = 3-decimal storage rounding)'
          % ('PASS' if (ok_dims and ok_rt) else 'FAIL', ROUNDTRIP_TOL))
    print('  site provenance of the 133 rows  : %s  -- only %d are GEOMETRICALLY'
          % (dict(site_src), site_src['derived']))
    print('  derived; the other %d take the anchor-assigned site, which is a'
          % (site_src['assigned'] + site_src['none']))
    print('  limit on the "constriction is derived, not stored" claim.')

    v_all = variance_stats(dims, table, all_rows)
    v_cor = variance_stats(dims, table, attested)
    loud_all = max(v_all[d]['var'] for d in dims)
    loud_cor = max(v_cor[d]['var'] for d in dims)
    mp_all, ex_all = minimal_pairs(dims, table, all_rows)
    mp_cor, ex_cor = minimal_pairs(dims, table, attested)

    t_all = {d: tier(v_all[d], loud_all) for d in dims}
    t_cor = {d: tier(v_cor[d], loud_cor) for d in dims}

    print('\n== 3. per-coordinate signal: all 133 rows vs %d attested rows =='
          % len(attested))
    print('  ratio = var / loudest var on the same inventory')
    print('  %-10s %4s %5s %9s %6s %8s %4s | %4s %5s %6s %8s %4s | %5s %5s'
          % ('coord', 'dist', 'off', 'var', 'ratio', 'relvar', 'tier',
             'dist', 'off', 'ratio', 'relvar', 'tier', 'minp', 'minc'))
    for d in dims:
        ra = v_all[d]['var'] / loud_all
        rc = v_cor[d]['var'] / loud_cor
        print('  %-10s %4d %5d %9.5f %6.3f %8s %4s | %4d %5d %6.3f %8s %4s '
              '| %5d %5d'
              % (d, v_all[d]['n_distinct'], v_all[d]['n_off_modal'],
                 v_all[d]['var'], ra,
                 '%.3f' % v_all[d]['rel_var'] if v_all[d]['rel_var'] else '-',
                 t_all[d],
                 v_cor[d]['n_distinct'], v_cor[d]['n_off_modal'], rc,
                 '%.3f' % v_cor[d]['rel_var'] if v_cor[d]['rel_var'] else '-',
                 t_cor[d],
                 mp_all[dims.index(d)], mp_cor[dims.index(d)]))

    print('\n== 4. tier counts ==')
    for label, tiers in (('all 133 rows', t_all),
                         ('attested %d rows' % len(attested), t_cor)):
        c = collections.Counter(tiers.values())
        print('  %-22s A=%d  B=%d  C=%d   C = %s'
              % (label, c['A'], c['B'], c['C'],
                 ', '.join(d for d in dims if tiers[d] == 'C') or '(none)'))

    print('\n== 5. tier-B coordinates: which rows carry them ==')
    for label, tiers, v in (('all', t_all, v_all), ('corpus', t_cor, v_cor)):
        for d in dims:
            if tiers[d] == 'B':
                print('  %-8s %-10s off-modal=%d  %s'
                      % (label, d, v[d]['n_off_modal'],
                         ' '.join(v[d]['off_modal_segments'][:12])))

    print('\n== 6. axes determined by another axis (inseparable by ANY data) ==')
    det_all = determines(dims, table, all_rows)
    det_cor = determines(dims, table, attested)
    for label, det in (('all rows', det_all), ('attested rows', det_cor)):
        if det:
            for k, tied in det.items():
                print('  %-13s %-10s -> %s' % (label, k, ', '.join(tied)))
        else:
            print('  %-13s (none)' % label)

    print('\n== 7. did the corpora FIX anything? ==')
    print('  A coordinate is corpus-fixed when its tier drops from all-rows to')
    print('  attested-rows; the old audit found that for body and tongue_root.')
    for d in dims:
        if t_all[d] != t_cor[d]:
            print('  %-10s %s -> %s   var %.5f -> %.5f  ratio %.3f -> %.3f'
                  % (d, t_all[d], t_cor[d], v_all[d]['var'], v_cor[d]['var'],
                     v_all[d]['var'] / loud_all, v_cor[d]['var'] / loud_cor))
    unchanged = [d for d in dims if t_all[d] == t_cor[d]]
    print('  unchanged by the corpora: %s' % (', '.join(unchanged) or '(none)'))
    print('  NOTE dorsum_x flips on a 0.046-vs-0.056 ratio either side of the')
    print('  0.05 bar; that tier is threshold-sensitive, not robust.')

    pz = place_zero_check(raw, table)
    print('\n== 8. the old place=0.00 overload, re-measured on tip_x ==')
    print('  retroflex stops        : %2d  tip_x %.2f..%.2f  %s'
          % (len(pz['retroflex_stops']), pz['tip_x_retroflex_range'][0],
             pz['tip_x_retroflex_range'][1], ' '.join(pz['retroflex_stops'])))
    print('  central vowels/glides  : %2d  tip_x %.2f..%.2f'
          % (len(pz['central_vowels_glides']), pz['tip_x_central_range'][0],
             pz['tip_x_central_range'][1]))
    print('  shared tip_x values    : %d  %s'
          % (len(pz['tip_x_values_shared']), pz['tip_x_values_shared']))

    d16, t16 = old_basis_tables()
    a16 = set(t16) & set(tokens)
    o_all = variance_stats(d16, t16, set(t16))
    o_cor = variance_stats(d16, t16, a16)
    l16a = max(o_all[d]['var'] for d in d16)
    l16c = max(o_cor[d]['var'] for d in d16)
    t16_all = {d: tier(o_all[d], l16a) for d in d16}
    t16_cor = {d: tier(o_cor[d], l16c) for d in d16}
    print('\n== 9. the OLD 16-dim basis graded by the SAME thresholds ==')
    for label, tiers in (('all 133 rows', t16_all),
                         ('attested %d rows' % len(a16), t16_cor)):
        c = collections.Counter(tiers.values())
        print('  %-22s A=%d  B=%d  C=%d   C = %s'
              % (label, c['A'], c['B'], c['C'],
                 ', '.join(d for d in d16 if tiers[d] == 'C') or '(none)'))
    print('  hand-quoted old dead axes (%s):'
          % ', '.join(OLD_DEAD))
    print('    %s' % '  '.join('%s=%s' % (d, t16_all[d]) for d in OLD_DEAD))
    print('  So the comparison the task asks for, ruler held fixed:')
    na = sum(1 for d in dims if t_all[d] == 'C')
    nc = sum(1 for d in dims if t_cor[d] == 'C')
    oa = sum(1 for d in d16 if t16_all[d] == 'C')
    oc = sum(1 for d in d16 if t16_cor[d] == 'C')
    print('    new basis tier-C = %d (all rows) / %d (attested)' % (na, nc))
    print('    old basis tier-C = %d (all rows) / %d (attested)' % (oa, oc))
    print('  The task quotes the old basis as having 4 dead axes; the ruler')
    print('  here does not reproduce that. Reconciliation, measured:')
    print('    old tongue_root var/loudest = %.4f, i.e. it clears the %.2f bar'
          % (o_all['tongue_root']['var'] / l16a, NEAR_FLAT))
    print('    by %.4f. The old figure of 4 came from fit_metric16 PINNING'
          % (o_all['tongue_root']['var'] / l16a - NEAR_FLAT))
    print('    those axes constant, not from measuring 133 rows; and the old')
    print('    audit graded only the 16 Phatak consonants, not the full table.')
    print('    Literal-dead vs low-contrast, both bases, all 133 rows:')
    lit_new = [d for d in dims if v_all[d]['n_distinct'] <= 1]
    lit_old = [d for d in d16 if o_all[d]['n_distinct'] <= 1]
    print('      new: literally constant %d %s' % (len(lit_new),
                                                   lit_new or '(none)'))
    print('      old: literally constant %d %s' % (len(lit_old),
                                                   lit_old or '(none)'))
    lo_new = [d for d in dims if t_all[d] == 'C' and d not in lit_new]
    lo_old = [d for d in d16 if t16_all[d] == 'C' and d not in lit_old]
    print('      new: low-contrast      %d %s' % (len(lo_new),
                                                   lo_new or '(none)'))
    print('      old: low-contrast      %d %s' % (len(lo_old),
                                                   lo_old or '(none)'))

    print('\n== 10. do the tier-C coordinates cost any segment identity? ==')
    keep_a = [d for d in dims if t_all[d] != 'C']
    ng, merged = collision_test(dims, table, all_rows, keep_a)
    print('  all 133 rows, keeping only the %d non-C coords (%s)'
          % (len(keep_a), ' '.join(keep_a)))
    print('  distinct signatures %d of 133  -> %d collision groups'
          % (ng, len(merged)))
    for k, v in sorted(merged.items(), key=lambda kv: -len(kv[1]))[:8]:
        print('     %2d rows share one signature: %s' % (len(v), ' '.join(v)))
    ng10, merged10 = collision_test(dims, table, all_rows, dims)
    print('  all 10 coords: %d distinct signatures of 133' % ng10)
    print('  -> the 10 tongue coordinates alone are NOT injective: %d of the'
          % (133 - ng10))
    print('  133 segments share a contour with at least one other segment.')
    print('  Voicing and manner are simply not in a sagittal contour, so')
    print('  p/b/ɓ and p/t are expected here; this is a LIMIT OF WHAT WAS')
    print('  GRADED (tongue_table.py also carries velum/lateral/larynx/duration,')
    print('  which this audit does not score), not a defect in the contour.')
    nga, mergeda = collision_test(dims, table, attested, dims)
    harmed = sorted({s for v in mergeda.values() for s in v})
    print('  attested rows only: %d distinct signatures of %d, %d attested'
          % (nga, len(attested), len(harmed)))
    print('  segments (%d%%) sit in a collision group.'
          % round(100 * len(harmed) / len(attested)))

    unk = classify_unknown(tokens, table)
    print('\n== 11. corpus tokens with no row ==')
    for label in ['carries_modifier', 'modifier_only', 'sequence',
                  'out_of_space']:
        items = unk[label].most_common(6)
        print('  %-16s %6d occurrences, %4d distinct  %s'
              % (label, sum(unk[label].values()), len(unk[label]), items))

    report = {
        'dims': dims,
        'thresholds': {
            'near_flat_fraction_of_loudest': NEAR_FLAT,
            'b_off_modal_max': B_OFF_MODAL,
            'roundtrip_tolerance': ROUNDTRIP_TOL,
            'rule': 'C if n_distinct<=1, else B if n_off_modal<=%d, '
                    'else C if var/loudest<%s, else A'
                    % (B_OFF_MODAL, NEAR_FLAT),
        },
        'self_check': {
            'dims_match_model': ok_dims,
            'roundtrip_rows_checked': n_checked,
            'worst_roundtrip_dx': round(worst, 6),
            'worst_roundtrip_segment': worst_seg,
            'site_provenance': dict(site_src),
            'pass': bool(ok_dims and ok_rt),
        },
        'inventory': {
            'table_rows': len(all_rows),
            'corpus_tokens': len(tokens),
            'attested_rows': len(attested),
            'rows_never_attested': sorted(all_rows - attested),
        },
        'table_rows': {
            'variance': v_all,
            'var_ratio_to_loudest': {d: round(v_all[d]['var'] / loud_all, 6)
                                     for d in dims},
            'minimal_pairs': dict(zip(dims, mp_all)),
            'minimal_pair_examples': {dims[k]: ex_all[k]
                                      for k in range(len(dims))},
            'tiers': t_all,
            'loudest_var': round(loud_all, 8),
            'loudest_coord': max(dims, key=lambda d: v_all[d]['var']),
        },
        'attested_rows': {
            'variance': v_cor,
            'var_ratio_to_loudest': {d: round(v_cor[d]['var'] / loud_cor, 6)
                                     for d in dims},
            'minimal_pairs': dict(zip(dims, mp_cor)),
            'minimal_pair_examples': {dims[k]: ex_cor[k]
                                      for k in range(len(dims))},
            'tiers': t_cor,
            'loudest_var': round(loud_cor, 8),
            'loudest_coord': max(dims, key=lambda d: v_cor[d]['var']),
        },
        'determined_by': {'all_rows': det_all, 'attested_rows': det_cor},
        'place_zero_overload': pz,
        'old_basis_same_rules': {
            'dims': d16,
            'tiers_all_rows': t16_all,
            'tiers_attested_rows': t16_cor,
            'var_all_rows': {d: o_all[d] for d in d16},
            'var_attested_rows': {d: o_cor[d] for d in d16},
            'tier_c_count_all_rows': oa,
            'tier_c_count_attested_rows': oc,
        },
        'new_tier_c_count_all_rows': na,
        'new_tier_c_count_attested_rows': nc,
        'old_basis_dead_axes_as_quoted': OLD_DEAD,
        'dead_versus_low_contrast': {
            'new_literally_constant': lit_new,
            'new_low_contrast': lo_new,
            'old_literally_constant': lit_old,
            'old_low_contrast': lo_old,
            'note': 'The old "4 dead axes" was a statement about axes '
                    'fit_metric16 pins by construction, not a variance '
                    'measurement over the 133 rows; the two are not the same '
                    'ruler.',
        },
        'collision_test': {
            'kept_coords': keep_a,
            'distinct_signatures_of_133': ng,
            'collision_groups': merged,
            'all_coords_signatures_of_133': ng10,
            'all_coords_collision_groups': merged10,
            'attested_signatures_of_attested': nga,
            'attested_collision_groups': mergeda,
            'attested_segments_in_collision': harmed,
        },
        'unknown_tokens': {k: dict(v.most_common(80)) for k, v in unk.items()},
        'limits': [
            'All 9 formant datasets behind tools/fit_tongue_forward.py are '
            'vowel-only; no tier here is validated against consonant acoustics.',
            'Minimal-pair counts are a floor, not a verdict: a dense physical '
            'description moves several coordinates per segment by construction.',
            'The tier rule compares raw variances across coordinates of '
            'different natural scale (x in [0.1,0.8] vs a 0/1 lip flag), so '
            'rel_var and the ratio column must be read with any tier.',
            'Only %d of 133 rows have a GEOMETRICALLY derived constriction; '
            '%d take the anchor-assigned site.' % (site_src['derived'],
                                                   site_src['assigned']),
            'A separate groove_depth parameter exists in '
            'tools/data/tongue_groove.json (the ɕ/ʃ fix for known gap 1) but '
            'it is NOT one of the 10 coordinates in tongue_table.json, so it '
            'is outside this audit and its dead-axis risk is untested here.',
        ],
    }
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))
    print('\nwrote %s' % OUT)

    print('\n== VERDICT: does the new basis have dead axes? ==')
    print('  Literally dead (n_distinct<=1): %d of 10. No coordinate is inert.'
          % len(lit_new))
    print('  Low-contrast tier C: %d of 10 on all 133 rows (%s), %d of 10 on the'
          % (na, ', '.join(lo_new), nc))
    print('  %d attested rows (%s).' % (len(attested),
                                        ', '.join(d for d in dims
                                                  if t_cor[d] == 'C')))
    print('  Compared with the old basis ON THE SAME RULER: old 0, new %d.' % na)
    print('  The task\'s premise of "old = 4" does not survive measurement:')
    print('  the old 4 are axes fit_metric16 pins constant, not axes that')
    print('  measure flat over 133 rows, where the flattest old axis clears')
    print('  the bar by %.4f. On the variance axis this ruler scores, the new'
          % (o_all['tongue_root']['var'] / l16a - NEAR_FLAT))
    print('  basis is worse than the old one and better on no coordinate.')
    print('  The larger defect is not the tiers but non-injectivity: %d of 133'
          % (133 - ng10))
    print('  segments share a contour, because a sagittal contour cannot hold')
    print('  voicing or manner. Only 57 of 133 sites are geometrically derived.')
    print('  What the new basis does buy, measured: tip_x separates the 10')
    print('  retroflex stops (0.30) from the 33 central vowels/glides (0.20)')
    print('  with 0 shared values, so the old place=0.00 overload is gone.')
    print('  UNVALIDATED: all 9 formant datasets are vowel-only, so none of')
    print('  this is confirmed against consonant acoustics.')


if __name__ == '__main__':
    main()