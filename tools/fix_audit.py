#!/usr/bin/env python3
"""Fix audit findings on vec_table_16.json (subagent-verified list).

SUPERSEDED: never applied.  The committed scheme
(tools/data/spec_next.scheme -> src/vectors.h) keeps the hand-tuned
values — vowels sit at place 0.0 with the front/central/back split on
`body`, which this script's positive place values (A) contradict; the
tip_shape unification (B) is already present.  Run only if the vowel
place-by-chart-class design is adopted as canonical; then re-export the
scheme (tools/export_scheme.py) and re-run the test suites.

Findings fixed (all cross-checked against IPA definitions by 4 auditors):
  A. Vowel place anchors: acoustic F2 drifted ɨ/ʉ/ɛ/œ/ɤ/ʌ/ɔ away from the
     IPA chart classes.  Fix: place by IPA CHART CLASS (front/central/back
     columns + height gradient), area keeps acoustic height.
  B. tip_shape: retroflex set unified to 0.8 (ʈ ɖ ɳ ɽ ɻ ʈ͡ʂ ɖ͡ʐ).
  C. Glottal: ʔ tension 0.5->0, larynx 1.0->0 (glottal stop has no
     ejective larynx raise); ɦ tension -0.3->-0.6 (breathy).
  D. ɶ area -> 1.0 (open front vowel, = a's rounding partner);
     ʐ/ɖ͡ʐ jet_focus 0.75 -> 0.8 (sibilant floor).
  E. ǀ place 0.290 -> 0.220 (dental click).
Run: python tools/fix_audit.py  (writes vec_table_16.json in place)
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'data', 'vec_table_16.json')

# --- A. vowel place by IPA chart class (front/central/back, height order)
# front column: high i y -> mid e ø -> open-mid ɛ œ -> near-open æ -> open a
FRONT = {'i': 0.570, 'y': 0.570, 'ɪ': 0.555, 'ʏ': 0.555, 'e': 0.550,
         'ø': 0.550, 'ɛ': 0.535, 'œ': 0.535, 'æ': 0.525, 'ɶ': 0.525,
         'a': 0.520}
# central column: high ɨ ʉ -> mid ɘ ɵ ə ɜ ɞ -> near-open ɐ
CENTRAL = {'ɨ': 0.500, 'ʉ': 0.500, 'ɘ': 0.500, 'ɵ': 0.500, 'ə': 0.500,
           'ɜ': 0.500, 'ɞ': 0.500, 'ɐ': 0.500}
# back column: high ɯ u -> near-high ʊ -> mid ɤ o -> open-mid ʌ ɔ -> open ɑ ɒ
BACK = {'ɯ': 0.640, 'u': 0.640, 'ʊ': 0.625, 'ɤ': 0.620, 'o': 0.615,
        'ʌ': 0.610, 'ɔ': 0.610, 'ɑ': 0.640, 'ɒ': 0.640}

VPLACE = dict(FRONT); VPLACE.update(CENTRAL); VPLACE.update(BACK)

# ɶ: open front ROUNDED vowel -- area must equal /a/ (open), and it is
# æ's rounding partner (same position) per the chart, but NOT æ's area:
# area follows HEIGHT (open), so 1.0 like a/ɑ/ɒ.
AREA_FIX = {'ɶ': 1.0}

# --- B. retroflex tip_shape -> 0.8
TIP_FIX = {'ʈ': 0.8, 'ɖ': 0.8, 'ɳ': 0.8, 'ɽ': 0.8, 'ɻ': 0.8,
           'ʈ͡ʂ': 0.8, 'ɖ͡ʐ': 0.8}

# --- C. glottal fixes
# ʔ: glottal stop -- aperture -1.0 (closed), tension 0 (not creaky/ejective),
#    larynx 0 (no raise)
GLOTTAL_FIX = {'ʔ': {'glottal_tension': 0.0, 'larynx_height': 0.0},
               'ɦ': {'glottal_tension': -0.6}}

# --- D. sibilant floor
JET_FIX = {'ʐ': 0.8, 'ɖ͡ʐ': 0.8}

# --- E. dental click
PLACE_FIX = {'ǀ': 0.220}

DIMS = ['place', 'body', 'lips_closed', 'lips_rounded', 'tip_shape',
        'tongue_root', 'vel_open', 'lateral_ratio', 'voiced',
        'glottal_aperture', 'glottal_tension', 'larynx_height', 'duration',
        'jet_focus', 'effective_oral_area', 'airflow_direction']


def main():
    d = json.load(open(OUT, encoding='utf-8'))
    tbl = d['table']
    fixes = 0
    for seg in tbl:
        row = tbl[seg]
        changed = False
        if seg in VPLACE:
            row[0] = VPLACE[seg]
            changed = True
        if seg in AREA_FIX:
            row[14] = AREA_FIX[seg]
            changed = True
        if seg in TIP_FIX:
            row[4] = TIP_FIX[seg]
            changed = True
        if seg in GLOTTAL_FIX:
            for dim, val in GLOTTAL_FIX[seg].items():
                row[DIMS.index(dim)] = val
            changed = True
        if seg in JET_FIX:
            row[13] = JET_FIX[seg]
            changed = True
        if seg in PLACE_FIX:
            row[0] = PLACE_FIX[seg]
            changed = True
        if changed:
            fixes += 1
    json.dump(d, open(OUT, 'w', encoding='utf-8'), indent=1,
              ensure_ascii=False)
    print(f'fixed {fixes} segments (audit findings A-E)')

    # re-verify the audited items
    def val(seg, dim):
        return tbl[seg][DIMS.index(dim)]
    print('\n== re-verify ==')
    print(f'  ɨ place = {val("ɨ","place")} (expect 0.500)')
    print(f'  ɛ place = {val("ɛ","place")} (expect 0.535)')
    print(f'  ɤ place = {val("ɤ","place")} (expect 0.620)')
    print(f'  ɶ place = {val("ɶ","place")} area = {val("ɶ","effective_oral_area")}')
    print(f'  ʈ tip_shape = {val("ʈ","tip_shape")} (expect 0.8)')
    print(f'  ʔ tension = {val("ʔ","glottal_tension")} larynx = {val("ʔ","larynx_height")}')
    print(f'  ɦ tension = {val("ɦ","glottal_tension")} (expect -0.6)')
    print(f'  ʐ jet_focus = {val("ʐ","jet_focus")} (expect 0.8)')
    print(f'  ǀ place = {val("ǀ","place")} (expect 0.220)')


if __name__ == '__main__':
    main()
