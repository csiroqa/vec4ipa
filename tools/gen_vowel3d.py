#!/usr/bin/env python3
"""Vowel 3-D anchors from MULTI-LANGUAGE acoustic measurements.

Data: phonTools rda sets (all in tools/data/):
  pb52 (English), h95 (English), t07 (English), f73 (Swedish),
  p73 (Dutch), b95 (Spanish), f99 (Greek), a96 (Hebrew), y96 (Korean)

KEY RULE (per user): a rounding pair shares the SAME position on the
height and front/back axes -- i~y, e~ø, ɛ~œ, ɯ~u, ɤ~o, ʌ~ɔ, ɨ~ʉ, ɘ~ɵ,
ɜ~ɞ, æ~ɶ, ɑ~ɒ are the same IPA-chart cell differing ONLY in rounding.
Therefore:
  1. position anchors (height, backness) are derived from UNROUNDED
     vowels only (their F1/F2 measurements);
  2. rounded vowels INHERIT their partner's area/place values;
  3. the rounding axis is derived from the F2 difference of the pair
     (ΔF2 = F2_unrounded - F2_rounded), normalised per language then
     averaged -- nothing hand-picked.

Derivation:
  height   = 1 - (F1-F1min_lang)/(F1max_lang-F1min_lang)   [per language]
  front    = (F2-F2min_lang)/(F2max_lang-F2min_lang)       [per language]
  area     = 1 - 0.6*height            (0.4 .. 1.0)
  place    = V-shape on backness=1-front (front .583, cen .500, back .667)
  rounding = ΔF2 / max(ΔF2)            (0 unrounded .. 1 rounded)

Run: python tools/gen_vowel3d.py --write
"""

import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
OUT = os.path.join(DATA, 'vowel_3d_anchors.json')

# X-SAMPA mapping (phonTools convention) -> IPA
XS = {
    'i': 'i', 'I': 'ɪ', 'e': 'e', 'E': 'ɛ', '{': 'æ', 'a': 'a', 'V': 'ʌ',
    'A': 'ɑ', 'O': 'ɔ', 'o': 'o', 'U': 'ʊ', 'u': 'u', 'y': 'y', '9': 'œ',
    '2': 'ø', '}': 'ʉ', '1': 'ɨ', "3'": 'ɝ', 'Y': 'ʏ',
}
# rounded IPA vowels; their UNROUNDED partner defines the shared position
# (IPA chart geometry: same cell, differing only in rounding)
ROUND_PARTNERS = {'y': 'i', 'ʏ': 'ɪ', 'ø': 'e', 'œ': 'ɛ', 'ɶ': 'æ',
                  'ʉ': 'ɨ', 'ɵ': 'ɘ', 'ɞ': 'ɜ', 'u': 'ɯ', 'o': 'ɤ',
                  'ɔ': 'ʌ', 'ɒ': 'ɑ', 'ʊ': 'ʊpos'}
ROUNDED = set(ROUND_PARTNERS)

DATASETS = ['pb52', 'h95', 't07', 'f73', 'p73', 'b95', 'f99', 'a96', 'y96']


def load_all():
    import pyreadr
    rows = []   # (lang, ipa, f1, f2)
    for ds in DATASETS:
        try:
            df = pyreadr.read_r(os.path.join(DATA, ds + '.rda'))[ds]
        except Exception:
            continue
        for _, r in df.iterrows():
            v = XS.get(str(r['vowel']))
            if v is None:
                continue
            f1, f2 = float(r['f1']), float(r['f2'])
            rows.append((ds, v, f1, f2))
    return rows


def main():
    rows = load_all()
    lang_vowels = {}
    for ds, v, f1, f2 in rows:
        lang_vowels.setdefault(ds, set()).add(v)
    print('== vowel inventories per language ==')
    for ds in DATASETS:
        if ds in lang_vowels:
            print(f'  {ds:<6} {sorted(lang_vowels[ds])}')

    # --- per-language normalisation (avoids cross-language flattening):
    # scale each language's F1/F2 by ITS OWN range, then average.
    lang_f1 = {}
    lang_f2 = {}
    for ds in DATASETS:
        f1l = [r[2] for r in rows if r[0] == ds]
        f2l = [r[3] for r in rows if r[0] == ds and r[1] not in ROUNDED]
        if f1l and len(f1l) > 2:
            lang_f1[ds] = (min(f1l), max(f1l))
        if f2l and len(f2l) > 2:
            lang_f2[ds] = (min(f2l), max(f2l))

    # aggregate per-vowel per-language means first
    agg = {}   # (ds, vowel) -> [f1, f2]
    for ds, v, f1, f2 in rows:
        if (ds, v) not in agg:
            agg[(ds, v)] = [f1, f2]
    f1m = {}   # vowel -> list of language-normalised height (ALL vowels;
                # rounded vowels inherit only when partner measured)
    f2m = {}   # vowel -> list of language-normalised frontness
    for (ds, v), (f1, f2) in agg.items():
        if ds in lang_f1:
            lo, hi = lang_f1[ds]
            f1m.setdefault(v, []).append((hi - f1) / max(hi - lo, 1e-9))
        if ds in lang_f2:
            lo, hi = lang_f2[ds]
            f2m.setdefault(v, []).append((f2 - lo) / max(hi - lo, 1e-9))
    height = {v: float(np.mean(x)) for v, x in f1m.items()}
    front = {v: float(np.mean(x)) for v, x in f2m.items()}
    back = {v: 1.0 - f for v, f in front.items()}

    # position anchors from own measurement for every vowel; then rounded
    # vowels with a MEASURED unrounded partner INHERIT the partner's
    # position (same IPA cell, differs only in rounding)
    area = {v: round(1.0 - 0.6 * h, 3) for v, h in height.items()}
    place = {}
    for v, b in back.items():
        if b <= 0.5:
            place[v] = round(0.583 - 0.166 * b, 3)
        else:
            place[v] = round(0.500 + 0.334 * (b - 0.5), 3)
    inherited = set()
    for rv, uv in ROUND_PARTNERS.items():
        if uv in area and uv in place and uv != 'ʊpos':
            if rv not in area or area[rv] != area[uv] or place[rv] != place[uv]:
                inherited.add(rv)
                area[rv] = area[uv]
                place[rv] = place[uv]

    # rounding via unrounded-partner F2 difference (per language, mean)
    f2lang = {}   # (ds, vowel) -> f2
    for ds, v, f1, f2 in rows:
        f2lang[(ds, v)] = f2
    round_delta = {}
    for rv, uv in ROUND_PARTNERS.items():
        ds_deltas = []
        for ds in DATASETS:
            if (ds, rv) in f2lang and (ds, uv) in f2lang:
                ds_deltas.append(f2lang[(ds, uv)] - f2lang[(ds, rv)])
        if ds_deltas:
            round_delta[rv] = float(np.mean(ds_deltas))
    round_max = max(round_delta.values()) if round_delta else 1.0
    rounding = {rv: d / round_max for rv, d in round_delta.items()}
    # rounding for unmeasured rounded vowels: nearest measured rounded vowel
    # in the same family (e.g. ʏ <- y, ɶ <- œ); marked 'derived'
    for rv, uv in ROUND_PARTNERS.items():
        if rv not in rounding and rv in area:
            fam = {'ʏ': 'y', 'ɶ': 'œ', 'ɵ': 'ø', 'ɞ': 'œ'}
            if rv in fam and fam[rv] in rounding:
                rounding[rv] = rounding[fam[rv]]

    print('\n== 3-D vowel anchors (per-language-normalised; pair = same pos) ==')
    print(f'{"v":<3}{"area":>7}{"place":>7}{"round":>7}  n_lang  src')
    for v in sorted(set(r[1] for r in rows)):
        nl = len({r[0] for r in rows if r[1] == v})
        rnd = rounding.get(v, 0.0)
        src = 'inherit' if v in inherited else 'measured'
        print(f'{v:<3}{area[v]:>7.3f}{place[v]:>7.3f}{rnd:>7.3f}  {nl:<2}  {src}')
    for v in sorted(set(area) - set(r[1] for r in rows)):
        print(f'{v:<3}{area[v]:>7.3f}{place[v]:>7.3f}{rounding.get(v,0):>7.3f}'
              f'  {-1:<2}  position-only')

    print('\n== rounding pairs (mean ΔF2 across languages) ==')
    for rv in sorted(round_delta):
        print(f'  {rv} (ΔF2={round_delta[rv]:+.0f}Hz, round={rounding[rv]:.2f})')

    if '--write' in sys.argv:
        json.dump({'area': area, 'place': place, 'rounding': rounding,
                   'sources': DATASETS,
                   'partner_delta_f2': {k: float(v)
                                        for k, v in round_delta.items()},
                   'gaps': ['ʊ partner (ʊpos/ɯ̞) not in these languages; '
                            'ɵ/ɞ/ʉ partners ɘ/ɜ/ɨ sparse'],
                   },
                  open(OUT, 'w'), indent=2, ensure_ascii=False)
        print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
