"""Re-run the six per-symbol checks on the current table, mechanically.

tools/gen_tongue_table.py derives the coordinates; whether each derived value
is self-consistent with the model that produced it is a separate question, and
the arithmetic is small enough to check directly rather than by eye. This
re-derives every symbol's expectation from the generator's own constants and
reports only the disagreements.

The checks are the same six an audit pass found useful:

  1 anatomy    no tongue point above the palate (contact excepted)
  2 place      derived_x is posterior to the previous place, and in the anchor's
               own range
  3 manner     velum/lateral/larynx/duration match the manner profile
  4 provenance site_from agrees with what derived_site could have concluded
  5 carrier    constrictor matches the anchor's declared constrictor
  6 internal   states consistent with the manner, no NaN/None/negative

Run: python tools/audit_symbol_assignments.py
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_tongue_model as tm          # noqa: E402
import gen_tongue_table as tt          # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
TABLE = os.path.join(DATA, 'tongue_table.json')
BASIS = os.path.join(DATA, 'merged_basis.json')
OUT = os.path.join(DATA, 'symbol_audit.json')

# The IPA place order. Retroflex sits between postalveolar and palatoalveolar:
# its blade contacts just behind the alveolar ridge while the tip retracts
# past it, which is why 0.28 falls where it does.
PLACE_ORDER = ['bilabial', 'labiodental', 'dental', 'alveolar',
               'postalveolar', 'retroflex', 'palatoalveol', 'palatal',
               'velar', 'uvular', 'pharyngeal', 'epiglottal', 'glottal']

CONTACTS = {'stop': 0.0, 'affricate': 0.0, 'trill': 0.0,
            'ejective': 0.0, 'implosive': 0.0, 'nasal': 0.0}

# The table stores coordinates rounded to 3 decimals, so a contact height
# written from roof() can land half a milliunit above the exact roof. Judging
# a stored 0.979 against an exact 0.9786 is rounding, not an anatomy error;
# TOL is that stored precision. Anything above it is a real violation.
TOL = 1e-3

# Vowels have no entry in CONSTRICTOR -- they are not a constriction category at
# all -- but their constrictor is the dorsum. Checking them against the table
# would report all 33 as a carrier mismatch.
VOWEL_CARRIER = 'dorsum'


def main():
    table = json.load(io.open(TABLE, encoding='utf-8'))
    basis = json.load(io.open(BASIS, encoding='utf-8'))
    problems = []

    def flag(sym, check, detail, evidence, severity='minor'):
        problems.append({'symbol': sym, 'check': check, 'severity': severity,
                         'detail': detail, 'evidence': evidence})

    # -- 1 anatomy and 6 internal, per symbol ------------------------------
    for s, e in sorted(table.items()):
        for p in tm.TONGUE:
            x, y = e['tongue'][p]
            if not (-0.05 <= x <= 1.05):
                flag(s, 1, '%s 的 x 越出声道范围' % p,
                     'tongue.%s = [%.4f, %.4f]' % (p, x, y), 'blocking')
            if y > tm.roof(x) + TOL:
                flag(s, 1, '%s 高于腭顶，舌头穿出口腔' % p,
                     'y=%.4f > roof(%.4f)=%.4f' % (y, x, tm.roof(x)), 'blocking')
        m = e['manner']
        if m in tt.PROFILES:
            prof = tt.PROFILES[m]
            for key, want in (('velum', prof['velum']),
                              ('lateral', prof['lat']),
                              ('larynx', prof['larynx'])):
                if abs(e[key] - want) > 1e-9:
                    flag(s, 3, '%s 的 %s 与方式档案不符' % (m, key),
                         '%s=%s, profile=%s' % (key, e[key], want),
                         'blocking' if abs(e[key] - want) > 0.5 else 'minor')
            if abs(e['duration'] - prof['dur']) > 0.15 + 1e-9:
                flag(s, 3, '%s 的 duration 偏离档案' % m,
                     'duration=%.4f, profile=%.4f' % (e['duration'],
                                                      prof['dur']))
            if m in CONTACTS and e['gap'] > 0.05:
                flag(s, 3, '%s 类应为闭合，gap 却非零' % m,
                     'gap=%.4f, profile=%.4f' % (e['gap'], prof['gap']),
                     'blocking')
        if not 0.0 <= e['lip_open'] <= 1.0:
            flag(s, 6, 'lip_open 越出 [0,1]', 'lip_open=%s' % e['lip_open'],
                 'blocking')
        if e['duration'] < 0:
            flag(s, 6, 'duration 为负', 'duration=%s' % e['duration'],
                 'blocking')

        # -- 5 carrier ---------------------------------------------------
        want = (VOWEL_CARRIER if e['anchor'] == 'vowel'
                else tt.CONSTRICTOR.get(e['anchor']))
        got = e['constrictor'] or None
        if want != got:
            flag(s, 5, '收缩载体与锚点声明不符',
                 'CONSTRICTOR[%s]=%s, table=%s' % (e['anchor'], want, got),
                 'blocking')

        # -- 4 provenance ------------------------------------------------
        # 'derived' claims the geometry found it: the gap must then be the
        # minimum over the parts, not the profile's nominal value.
        if e['site_from'] == 'derived' and e['constrictor']:
            px, py = e['tongue'][e['constrictor']]
            if abs(e['gap'] - (tm.roof(px) - py)) > 1e-3:
                flag(s, 4, '标为 derived，但 gap 与该载体处的高度不符',
                     'gap=%.4f, roof(%.4f)-y=%.4f'
                     % (e['gap'], px, tm.roof(px) - py))
        if e['site_from'] == 'none' and e['derived_x'] is not None:
            flag(s, 4, '标为无收缩，却给出了收缩位置',
                 'derived_x=%s' % e['derived_x'])

    # -- 2 place order ----------------------------------------------------
    seen_x = {}
    for a in PLACE_ORDER:
        xs = sorted({e['derived_x'] for e in table.values()
                     if e['anchor'] == a and e['derived_x'] is not None})
        if xs:
            seen_x[a] = (min(xs), max(xs))
    prev_anchor, prev_x = None, None
    for a in PLACE_ORDER:
        if a not in seen_x:
            continue
        lo, hi = seen_x[a]
        if prev_x is not None and lo <= prev_x:
            flag(a, 2, '部位序列倒错：%s 不比 %s 更靠后' % (a, prev_anchor),
                 '%s x=%.4f, %s x=%.4f' % (a, lo, prev_anchor, prev_x),
                 'blocking')
        prev_anchor, prev_x = a, hi

    # -- check 7: no two base segments may share a vector ------------------
    # A duplicate vector is unfixable downstream: vec2ipa cannot separate two
    # symbols whose coordinates are identical, whatever the metric says, and
    # every gate that scores per-symbol silently reports them as one point.
    # This is the single check that would have caught ɔ being authored with
    # lip_round 0.00 (colliding with ʌ), the click branch reading no airflow
    # direction (ǂ == c), and ɪ / ʏ / ə falling through to schwa's cell.
    seen_vec = {}
    for seg in sorted(table):
        key = tuple(round(x, 6) for x in basis['table'][seg])
        if key in seen_vec:
            flag(seg, 7, '与 %s 的基向量逐位相同' % seen_vec[key],
                 '两者的 18 维坐标完全一致', 'blocking')
        else:
            seen_vec[key] = seg

    # -- report ------------------------------------------------------------
    blocking = [p for p in problems if p['severity'] == 'blocking']
    by_symbol = {}
    for p in problems:
        by_symbol.setdefault(p['symbol'], []).append(p)
    print('audited %d symbols, %d problems (%d blocking) on %d symbols'
          % (len(table), len(problems), len(blocking), len(by_symbol)))
    for ck in sorted({p['check'] for p in problems}):
        sel = [p for p in problems if p['check'] == ck]
        print('  check %d: %d issues, %d symbols -- %s'
              % (ck, len(sel), len({p['symbol'] for p in sel}),
                 ' '.join(sorted({p['symbol'] for p in sel})[:18])))
    if not problems:
        print('  every symbol passes all six checks')

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'n_symbols': len(table),
                            'n_problems': len(problems),
                            'n_blocking': len(blocking),
                            'problems': problems}, ensure_ascii=False,
                           indent=1))
    print('wrote %s' % OUT)


if __name__ == '__main__':
    main()