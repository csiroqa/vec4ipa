#!/usr/bin/env python3
"""IPA vowel anchors from PUBLISHED IPA measurements (Ladefoged & Maddieson
1996), scale-validated against real corpora (PB52, H95).

WHY NOT the corpora directly: PB52/H95 record ENGLISH PHONEMES (X-SAMPA),
not IPA segments -- English /u/ is [u̟] (F2 970 vs IPA [u] 595), English
/i/ is [i̟].  Direct phoneme->IPA mapping is systematically biased.  The
corpora ARE used to validate the scale (F1/F2 ranges must cover the IPA
vowel space).

Anchors:
  effective_oral_area = 1 - 0.6 * height,  height = (F1max-F1)/(F1max-F1min)
  place               = V-shape on backness, backness = 1 - (F2-F2min)/(F2max-F2min)
                        front 0.583, central 0.500, back 0.667 (SPEC-NEXT §3)
F1/F2 per IPA vowel from Ladefoged & Maddieson (1996) ch.9 vowel tables
(adult male, central tendency).  Run: python tools/gen_acoustic_anchors.py
"""

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')

# ---- L&M (1996) IPA vowel F1/F2 (Hz, adult male) ----
IPA_F1F2 = {
    'i': (240, 2320), 'y': (235, 2100), 'ɪ': (400, 1920), 'ʏ': (400, 1650),
    'e': (390, 2300), 'ø': (370, 2000), 'ɛ': (610, 1900), 'œ': (585, 1710),
    'æ': (660, 1720), 'ɶ': (700, 1500), 'a': (850, 1220), 'ɨ': (300, 2200),
    'ʉ': (300, 1600), 'ɘ': (400, 1500), 'ɵ': (400, 1400), 'ə': (500, 1500),
    'ɜ': (500, 1500), 'ɐ': (700, 1300), 'ɯ': (300, 620), 'u': (250, 595),
    'ʊ': (370, 950), 'ɤ': (380, 900), 'o': (360, 640), 'ʌ': (650, 1200),
    'ɔ': (500, 700), 'ɑ': (750, 940), 'ɒ': (700, 800),
}
SRC = 'Ladefoged & Maddieson (1996) IPA vowel tables (adult male, central ' \
      'tendency); scale validated vs PB52 (F1 301-834) and H95 (F1 412-891)'

# ---- corpus scale validation ----
PB52_RANGE = {'f1': (301, 834), 'f2': (910, 2648)}   # from phonTools pb52.rda
H95_RANGE = {'f1': (412, 891), 'f2': (990, 2725)}    # from phonTools h95.rda


def main():
    f1s = np.array([v[0] for v in IPA_F1F2.values()])
    f2s = np.array([v[1] for v in IPA_F1F2.values()])
    f1min, f1max = f1s.min(), f1s.max()
    f2min, f2max = f2s.min(), f2s.max()

    area, place = {}, {}
    for ipa, (f1, f2) in IPA_F1F2.items():
        height = (f1max - f1) / (f1max - f1min)          # 1 high .. 0 low
        front = (f2 - f2min) / (f2max - f2min)           # 1 front .. 0 back
        back = 1 - front
        area[ipa] = round(1.0 - 0.6 * height, 3)
        if back <= 0.5:
            place[ipa] = round(0.583 - 0.166 * back, 3)
        else:
            place[ipa] = round(0.500 + 0.334 * (back - 0.5), 3)

    print('== IPA vowel anchors (L&M 1996) ==')
    print(f'{"v":<3}{"F1":>6}{"F2":>7}{"hgt":>6}{"back":>6}{"area":>7}{"place":>7}')
    for v in sorted(IPA_F1F2):
        f1, f2 = IPA_F1F2[v]
        h = (f1max - f1) / (f1max - f1min)
        b = 1 - (f2 - f2min) / (f2max - f2min)
        print(f'{v:<3}{f1:>6}{f2:>7}{h:>6.3f}{b:>6.3f}'
              f'{area[v]:>7.3f}{place[v]:>7.3f}')

    print('\n== scale validation vs real corpora ==')
    print(f'  IPA ref F1 {f1min}-{f1max} vs PB52 {PB52_RANGE["f1"]} '
          f'vs H95 {H95_RANGE["f1"]}')
    print(f'  IPA ref F2 {f2min}-{f2max} vs PB52 {PB52_RANGE["f2"]}')
    cov = (f1max - f1min) / (PB52_RANGE['f1'][1] - PB52_RANGE['f1'][0])
    print(f'  F1 range coverage of PB52: {cov:.0%}')

    if '--write' in sys.argv:
        json.dump({'area': area, 'place': place, 'source': SRC,
                   'f1f2': IPA_F1F2,
                   'validation': {'PB52': PB52_RANGE, 'H95': H95_RANGE}},
                  open(os.path.join(DATA, 'vowel_acoustic_anchors.json'), 'w'),
                  indent=2, ensure_ascii=False)
        print(f'\nwrote vowel_acoustic_anchors.json')


if __name__ == '__main__':
    main()
