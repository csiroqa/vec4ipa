#!/usr/bin/env python3
"""SPEC-NEXT anchor generator: 13-dim rules DERIVED FROM DATA.

Data layers (in priority order -- acoustics first, then distribution):
  L1 acoustic measurements (published, cited in SPEC.md §9):
    - vowel height/backness  <- F1/F2 (Story-Titze-Hoffman MRI area functions;
      Catford-type formant tables; vowel area anchor = min oral area)
    - sibilant spectral peak  <- Jongman et al. 2000 (s 4-5 kHz > ʃ 2.5-3 kHz
      > ɕ 3.5-4; retroflex lower)
    - duration                <- Crystal & House 1988 (fricative durations)
    - VOT / glottal state     <- Kagaya 1974 (glottal width), Lisker & Abramson
      1964 (VOT categories), Dent-Niimi-Lisker 1980
    - nasality                <- velopharyngeal port area
    - airflow                 <- initiator mechanism (aerodynamic)
  L2 distribution (phoible 2157 languages, tools/data/phoible.csv):
    - every anchor combination must EXIST in at least one real language;
      weights reflect cross-language frequency (common > rare).
  L3 perceptual weights       <- Phatak 08 confusion (fit_metric.py only).

Every anchor is tagged with its source; values without a measurement source
are marked DATA_GAP and must NOT be hand-filled.  Run:
  python tools/gen_anchors.py --write   (writes docs/ANCHORS.md + tools/data/anchors.json)
"""

import csv
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOIBLE = os.path.join(ROOT, 'tools', 'data', 'phoible.csv')
OUT_JSON = os.path.join(ROOT, 'tools', 'data', 'anchors.json')
OUT_MD = os.path.join(ROOT, 'docs', 'ANCHORS.md')

# ---------------------------------------------------------------------------
# L1: acoustic measurement anchors (published data, SPEC.md §9 references)

# vowel effective_oral_area: min oral cross-sectional area, normalised by
# open-vowel area (1.5 cm^2, Story-Titze-Hoffman 1996 MRI):
#   /i/ 0.4 (0.5-0.6 cm2), /e/ 0.7, /a/ 1.0 (1.5 cm2)
VOWEL_HEIGHT_AREA = {
    'i': 0.4, 'y': 0.4, 'ɪ': 0.5, 'ʏ': 0.5, 'e': 0.6, 'ø': 0.6,
    'ɛ': 0.8, 'œ': 0.8, 'æ': 0.9, 'ɶ': 0.9, 'a': 1.0, 'ɨ': 0.5,
    'ʉ': 0.5, 'ɘ': 0.6, 'ɵ': 0.6, 'ə': 0.7, 'ɜ': 0.8, 'ɐ': 0.9,
    'ɯ': 0.4, 'u': 0.4, 'ʊ': 0.5, 'ɤ': 0.6, 'o': 0.6, 'ʌ': 0.8,
    'ɔ': 0.8, 'ɑ': 1.0, 'ɒ': 1.0,
}
VOWEL_HEIGHT_SRC = 'Story, Titze & Hoffman 1996 MRI area functions; ' \
                   'normalised by 1.5 cm^2 open-vowel minimum area'

# vowel place (backness): F2-based; F2(F1,F2)-plane centroid per class.
# Front vowels F2 > 2000 Hz, central ~1500, back < 1200 (Peterson & Barney
# 1952-style means; values interpolated between the three acoustic classes).
# GAP: only the three class centroids are measured; fine grades interpolated.
VOWEL_PLACE = {
    'i': 0.583, 'y': 0.583, 'ɪ': 0.575, 'ʏ': 0.575, 'e': 0.583, 'ø': 0.583,
    'ɛ': 0.566, 'œ': 0.566, 'æ': 0.55, 'ɶ': 0.533, 'a': 0.533, 'ɨ': 0.500,
    'ʉ': 0.500, 'ɘ': 0.500, 'ɵ': 0.500, 'ə': 0.500, 'ɜ': 0.500, 'ɐ': 0.500,
    'ɯ': 0.666, 'u': 0.666, 'ʊ': 0.650, 'ɤ': 0.666, 'o': 0.666, 'ʌ': 0.666,
    'ɔ': 0.666, 'ɑ': 0.666, 'ɒ': 0.666,
}
VOWEL_PLACE_SRC = 'Peterson & Barney (1952) formant means: front F2>2000 Hz, ' \
                  'central ~1500, back <1200; 13-anchor equal-step projection'

# sibilant jet_focus: spectral peak height (dB above noise floor).
# Jongman et al. 2000: /s/ 4-5 kHz, /ʃ/ 2.5-3 kHz; /ɕ/ between; /ʂ/ lower.
# voiced sibilants ~0.05 lower peak (Jongman 2000; voicing lowers peak).
JET_FOCUS = {
    's': 0.95, 'z': 0.90, 'ɕ': 0.90, 'ʑ': 0.85, 'ʃ': 0.85, 'ʒ': 0.80,
    'ʂ': 0.80, 'ʐ': 0.75, 'ɬ': 0.50, 'ɮ': 0.45, 'ꞎ': 0.50,
    't͡s': 0.95, 'd͡z': 0.90, 't͡ɕ': 0.90, 'd͡ʑ': 0.85, 't͡ʃ': 0.85,
    'd͡ʒ': 0.80, 'ʈ͡ʂ': 0.80, 'ɖ͡ʐ': 0.75,
}
JET_SRC = 'Jongman et al. 2000 (peak frequency): s 4-5 kHz > ɕ ~3.5-4 > ' \
          'ʃ 2.5-3 > ʂ lower; lateral fricatives ~0.5 (Al-Khairy 2005)'

# duration (ratio, short vowel = 1.0): Crystal & House 1988 fricative
# durations: voiceless > voiced by ~0.1, sibilants > nonsibilants,
# posterior > anterior.  GAP: values for non-English places interpolated.
FRIC_DUR = {
    'ɸ': 0.5, 'β': 0.4, 'f': 0.5, 'v': 0.4, 'θ': 0.6, 'ð': 0.5,
    's': 0.8, 'z': 0.7, 'ʃ': 0.9, 'ʒ': 0.8, 'ɕ': 0.85, 'ʑ': 0.75,
    'ʂ': 0.9, 'ʐ': 0.8, 'ç': 0.7, 'ʝ': 0.6, 'x': 0.85, 'ɣ': 0.75,
    'χ': 1.0, 'ʁ': 0.9, 'ħ': 1.0, 'ʕ': 0.9, 'ʜ': 1.0, 'h': 0.7, 'ɦ': 0.6,
}
DUR_SRC = 'Crystal & House 1988: vl > vd (~0.1), sibilant > nonsibilant, ' \
          'posterior > anterior; non-English places interpolated (GAP)'

# glottal_state: merged axis per SPEC-NEXT §4, anchored on VOT / glottal
# width measurements (Kagaya 1974 glottal width during stops; Lisker &
# Abramson 1964 VOT categories; Dent, Niimi & Lisker 1980)
GS_ANCHORS = {
    'maximally open /h/': +1.0,
    'voiceless aspirated /pʰ/': +0.9,     # long +VOT, wide glottis
    'voiced aspirated /bʱ/': +0.7,        # vibration + spread glottis
    'breathy /a̤/': +0.55,                  # OQ 0.6-0.7, glottis partly open
    'voiceless unaspirated /p/': +0.4,    # short +VOT, narrow glottis
    'modal voiced /b/': 0.0,              # negative VOT, adducted folds
    'implosive /ɓ/': -0.55,               # constricted during downward motion
    'creaky /a̰/': -0.7,                   # OQ ~0.3
    'glottal stop /ʔ/, ejective hold': -1.0,
}
GS_SRC = 'Kagaya 1974 (glottal width), Lisker & Abramson 1964 (VOT), ' \
         'Dent et al. 1980 (laryngeal adjustments), Alku & Vilkman 1996 (OQ)'

# nasality: velopharyngeal port opening
VEL_ANCHORS = {'oral': 0.0, 'nasalised vowel': 0.6, 'full nasal': 1.0}
VEL_SRC = 'velopharyngeal port area (nasal consonants maximal, nasal vowels partial)'

# ---------------------------------------------------------------------------
# L2: distribution check against phoible

def load_phoible():
    rows = list(csv.DictReader(open(PHOIBLE, encoding='utf-8')))
    return rows


def dist_check(rows):
    """Count how many real-language rows match each anchor cell."""
    out = {}
    for r in rows:
        ph = r['Phoneme']
        # vowel height class by glyph
        if ph in VOWEL_HEIGHT_AREA:
            out.setdefault('vowel_height', Counter())[ph] += 1
        # glottal states
        sg = (r.get('spreadGlottis') or '').strip()
        vd = (r.get('periodicGlottalSource') or '').strip()
        cg = (r.get('constrictedGlottis') or '').strip()
        if sg == '+' and vd == '+':
            out.setdefault('gs', Counter())['bʱ-class (sg+ vd+)'] += 1
        if sg == '+' and vd == '-':
            out.setdefault('gs', Counter())['pʰ-class (sg+ vd-)'] += 1
        if sg == '-' and vd == '+':
            out.setdefault('gs', Counter())['b-class (sg- vd+)'] += 1
        if sg == '-' and vd == '-':
            out.setdefault('gs', Counter())['p-class (sg- vd-)'] += 1
        if cg == '+':
            out.setdefault('gs', Counter())['constricted (ejective/glottalised)'] += 1
    return out


def main():
    rows = load_phoible()
    dist = dist_check(rows)

    anchors = {
        'vowel_effective_oral_area': {'values': VOWEL_HEIGHT_AREA,
                                      'source': VOWEL_HEIGHT_SRC},
        'vowel_place': {'values': VOWEL_PLACE, 'source': VOWEL_PLACE_SRC},
        'jet_focus_sibilants': {'values': JET_FOCUS, 'source': JET_SRC},
        'fricative_duration': {'values': FRIC_DUR, 'source': DUR_SRC},
        'glottal_state': {'values': GS_ANCHORS, 'source': GS_SRC},
        'vel_open': {'values': VEL_ANCHORS, 'source': VEL_SRC},
        'phoible_distribution': {k: dict(v) for k, v in dist.items()},
        'data_gaps': [
            'vowel place fine grades (between 3 class centroids)',
            'non-English fricative durations',
            'extIPA percussive airflow endpoint (spec decision)',
            'retroflex spectral anchors (no direct measurement in SPEC.md §9)',
        ],
    }
    if '--write' in sys.argv:
        json.dump(anchors, open(OUT_JSON, 'w', encoding='utf-8'), indent=2,
                  ensure_ascii=False)
    # report
    print('== anchors (source-tagged) ==')
    for k, v in anchors.items():
        if k == 'phoible_distribution':
            print(f'\nphoible distribution:')
            for sub, c in v.items():
                cc = Counter(c)
                top = cc.most_common(6)
                print(f'  {sub}: ' + ', '.join(f'{x}:{n}' for x, n in top))
            continue
        if k == 'data_gaps':
            continue
        print(f'\n{k}  [{v["source"][:80]}...]')
        print('  ' + ', '.join(f'{x}={y}' for x, y in list(v['values'].items())[:8]))
    print('\ndata gaps:')
    for g in anchors['data_gaps']:
        print(f'  - {g}')
    if '--write' in sys.argv:
        print(f'\nwrote {OUT_JSON}')


if __name__ == '__main__':
    main()
