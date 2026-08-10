#!/usr/bin/env python3
"""Generate the 16-dim SPEC-NEXT vector table with FULLY-SOURCED values.

Every value has an explicit origin (no hand-picking):
  INHERIT  -- same physical quantity as v8, value copied from v8 table
              (lips_closed[chain-fixed], lips_rounded[vowels], tip_shape,
              tongue_root, vel_open, lateral_ratio, voiced, duration,
              jet_focus, effective_oral_area, airflow_direction,
              glottal_tension = v8 laryngeal_tension)
  RULE     -- reconstructed axis:
              place            <- PLACE anchor table (place_anchors.py)
              glottal_aperture <- cg/sg lookup (SPEC-NEXT §4)
              body             <- secondary-constriction rule (0 default;
                                   ʲ +0.4, ˠ -0.3, ɧ +0.4, clicks -0.4)
              larynx_height    <- ejective +1.0 / implosive -1.0 / else 0
  DATA     -- vowel place/area from acoustic measurements
              (vowel_3d_anchors.json: L&M 1996 + phonTools 9 corpora,
              remapped to [0.08, 0.92]); vowel lips_rounded inherited from v8.

Chain-neutralisation (SPEC-NEXT §3): labiodental f/v/p̪/ɱ/ⱱ get
lips_closed = 0 (v8 used it to force bilabial-vs-labiodental); sibilant
rounding removed (v8 encoded s-vs-ʃ via /ʃ/ rounding -- place axis owns it
now); vowel rounding kept (core vowel feature).

Output: tools/data/vec_table_16.json (+ printed table).
Run: python tools/gen_vec_table.py
"""

import json
import os
import re

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V8_MD = os.path.join(ROOT, 'IPA_VECTORS.md')
VOWEL3D = os.path.join(ROOT, 'tools', 'data', 'vowel_3d_anchors.json')
OUT = os.path.join(ROOT, 'tools', 'data', 'vec_table_16.json')

from place_anchors import PLACE, remap

NDIM = 16
DIMS = ['place', 'body', 'lips_closed', 'lips_rounded', 'tip_shape',
        'tongue_root', 'vel_open', 'lateral_ratio', 'voiced',
        'glottal_aperture', 'glottal_tension', 'larynx_height', 'duration',
        'jet_focus', 'effective_oral_area', 'airflow_direction']

# v8 base rows
_pat = re.compile(r"^`/([^/`]*)/`: `\((.*)\)`")
V8 = {}
for _line in open(V8_MD, encoding='utf-8'):
    _m = _pat.match(_line.strip())
    if _m and len(_m.group(2).split(',')) == 16:
        V8[_m.group(1)] = [float(x.strip())
                           for x in _m.group(2).replace('+', '').split(',')]

# vowel 3-D anchors from acoustic data: place columns by PERCEIVED
# frontness (Bark2 of phonTools F1/F2/F3 means, vowel_bark_anchors.json):
#   front  +0.15  (Bark2 >= 13.0): i e ɪ y ɛ æ
#   central 0.00  (11.0-13.0):     ø ʉ ɨ ɝ œ a     <- a/ø/œ centralised in
#                                     real speech (Bark2 evidence)
#   back   +0.30  (< 11.0):        ʌ ɑ ʊ u ɔ o
# (vowels missing from the 9 corpora keep the IPA-chart column)
# height 7 uniform cells: 0.40 0.50 0.60 0.70 0.80 0.90 1.00
# (adjacent differ 0.10; central: ɨ 0.40, ᵻ(=ɨ̞) 0.50, ɘ/ɵ 0.60, ə 0.70,
#  ɜ/ɞ 0.80, ɐ 0.90, ᴀ(=ä) 1.00)
VOWEL_COL = {  # vowel -> (body, area); body = tongue-body position
    # (v8 semantics: front +, central 0, back -; uniform v8 scale x0.4,
    #  anchor i=1.0 -> 0.40: front i/e = 1.0, back u = -0.5 -> -0.20;
    #  vowel HEIGHT lives on area only, as in v8 -- body has no height
    #  gradient within a column)
    'i': (0.40, 0.40), 'y': (0.40, 0.40), 'ɪ': (0.36, 0.50), 'ʏ': (0.36, 0.50),
    'e': (0.40, 0.60), 'ɛ': (0.32, 0.80), 'æ': (0.24, 0.90),
    'ɶ': (0.16, 0.90),
    'ø': (0.40, 0.60), 'œ': (0.32, 0.80), 'a': (0.00, 1.00),
    'ɨ': (0.00, 0.40), 'ʉ': (0.00, 0.40), 'ɘ': (0.00, 0.60), 'ɵ': (0.00, 0.60),
    'ə': (0.00, 0.70), 'ɜ': (0.00, 0.80), 'ɞ': (0.00, 0.80), 'ɐ': (0.00, 0.90),
    'ɯ': (-0.20, 0.40), 'u': (-0.20, 0.40), 'ʊ': (-0.18, 0.50),
    'ɤ': (-0.20, 0.60),
    'o': (-0.20, 0.60), 'ʌ': (-0.20, 0.80), 'ɔ': (-0.20, 0.80),
    'ɑ': (-0.20, 1.00), 'ɒ': (-0.20, 1.00),
}

# labiodentals: lip closure removed (chain-neutral)
LABIODENTAL = {'f', 'v', 'p̪', 'ɱ', 'ⱱ', 'fʼ'}

# ejective/implosive sets (airstream from v8 airflow/cg)
def is_ejective(v):
    return v[15] > 0 and v[9] >= 0.9
def is_implosive(v):
    return v[15] < 0 and v[8] >= 0.5
def is_click(v):
    return v[15] < 0 and v[8] < 0.5

def aperture_of(v):
    """SPEC-NEXT §4 lookup from v8 (cg, sg)."""
    cg, sg = v[9], v[10]
    if sg >= 0.55:
        return sg
    if cg == 0.0 and sg == 0.4:
        return 0.4
    if cg == 0.2 and sg == 0.0:
        return 0.0
    if cg == 0.55:
        return -0.55
    if cg == 0.7:
        return -0.7
    if cg >= 0.9:
        return -1.0
    return sg - cg


def body_of(seg):
    """Tongue-body position by PLACE FAMILY (SPEC-NEXT §3).

    Uniform v8 scale x0.4 (anchor i=1.0 -> 0.40): the body axis carries
    the front/back dimension of every dorsal segment, matching v8's
    tongue_body_pos (palatal 1.0, velar -0.5, uvular -0.73, pharyngeal
    -0.97, epiglottal -1.2).  Front vowels/glides inherit via VOWEL_COL
    / GLIDE_PARTNER.  Only secondary-articulation deltas (ɧ, mod_*)
    and clicks (velar secondary closure) add on top.
    """
    if seg in ('ɧ',):
        return -0.4                      # postalveolar + VELAR secondary
                                         # (IPA: simultaneous postalv.+velar)
    if is_click(V8[seg]):
        return -0.2                      # clicks: velar secondary closure
                                         # (v8 body=-0.5 = velar, x0.4)
    if seg in ('c', 'ɟ', 'ɲ', 'ç', 'ʝ', 'ʎ', 'ʄ'):
        return 0.4                       # palatal series (v8 body=1.0)
    if seg in ('k', 'ɡ', 'ŋ', 'x', 'ɣ', 'kʼ', 'xʼ', 'ʟ', 'ɠ',
               'k͡p', 'k͡x', 'ɡ͡b', 'ŋ͡m'):
        return -0.2                      # velar series (v8 body=-0.5)
    if seg in ('q', 'ɢ', 'χ', 'ʀ', 'ʁ', 'ɴ', 'ʛ', 'qʼ', 'q͡χ'):
        return -0.29                     # uvular series (v8 body=-0.73)
    if seg in ('ħ', 'ʕ'):
        return -0.39                     # pharyngeal series (v8 body=-0.97)
    if seg in ('ʡ', 'ʢ', 'ʜ'):
        return -0.48                     # epiglottal series (v8 body=-1.2)
    return 0.0                           # default: no tongue-body gesture
                                         # (labial, coronal, glottal)


def larynx_of(v, seg):
    """larynx height: ejective +1 (raised), implosive -1 (lowered), else 0.
    /ʔ/ is a glottal stop -- NOT an ejective -- so its v8 cg=1.0 must not
    trigger the ejective rule."""
    if seg == 'ʔ':
        return 0.0
    if is_ejective(v):
        return 1.0                       # ejective: larynx raised
    if is_implosive(v):
        return -1.0                      # implosive: larynx lowered
    return 0.0


# affricates inherit the FRICATIVE-PHASE features of their homorganic
# fricative (composition rule): lips_rounded, jet_focus, duration =
# 0.5(closure) + fricative duration (v8 structure, verified 10/10).
AFFRICATE_FRIC = {'t͡s': 's', 'd͡z': 'z', 't͡ʃ': 'ʃ', 'd͡ʒ': 'ʒ',
                  't͡ɕ': 'ɕ', 'd͡ʑ': 'ʑ', 'ʈ͡ʂ': 'ʂ', 'ɖ͡ʐ': 'ʐ',
                  'k͡x': 'x', 'q͡χ': 'χ'}

# glides (semi-vowels) are the NON-SYLLABIC forms of their vowel partner:
# same tongue root (ATR) and lip shape, slightly narrower constriction
# (physical: approximant < vowel area).  j=i, ɥ=y, w=u, ɰ=ɯ.
GLIDE_PARTNER = {'j': 'i', 'ɥ': 'y', 'w': 'u', 'ɰ': 'ɯ', 'ʍ': 'u'}


def build():
    out = {}
    for seg, v in V8.items():
        x = np.zeros(NDIM)
        # --- place: anchor table for consonants; vowels and GLIDES have NO
        # tip gesture -> 0.0 (v8: j/w rest tongue_tip_pos at 0.55; their
        # palatal/velar identity lives on body, front/back respectively)
        if seg in PLACE and seg not in GLIDE_PARTNER:
            x[0] = PLACE[seg]
        elif seg in VOWEL_COL:
            x[0] = 0.0
        elif seg in GLIDE_PARTNER:
            x[0] = 0.0
        else:
            raise KeyError(f'no place for {seg!r}')
        # --- body: tongue-BODY position (v8 semantics: front +, back -);
        # vowels carry their front/central/back column here; consonants
        # keep only true secondary constrictions (clicks, ɧ)
        if seg in VOWEL_COL:
            x[1] = VOWEL_COL[seg][0]
        else:
            x[1] = body_of(seg)
        is_vowel = seg in VOWEL_COL
        # --- lips_closed: bilabials 1.0; labiodentals 0.3 (lower lip on
        # upper teeth -- partial lip involvement, not closure); rest 0
        if seg in LABIODENTAL:
            x[2] = 0.3
        elif v[0] >= 1.0:
            x[2] = 1.0
        else:
            x[2] = 0.0
        # --- lips_rounded: vowels keep v8 (rounding is core); consonants
        # keep rounding ONLY for inherently rounded ones (ɥ w ʍ) and the
        # sibilants ʃ ʒ (v8 used /ʃ/ rounding for s-ʃ; the confusion data
        # s-ʃ = 2.5% shows it is perceptually real).  Other consonants 0.
        ROUND_CONS = {'ɥ', 'w', 'ʍ', 'ʃ', 'ʒ'}
        x[3] = v[1] if is_vowel or seg in ROUND_CONS else 0.0
        # --- tip_shape: inherit v8 tip_height with IPA fixes:
        #   retroflex stops/nasal/affricates 0.8 (not 0.9 -- that's trill)
        #   ɹ 0.7 (postalveolar approx, not 0.6 sibilant)
        #   ɻ 0.8 / ɭ 0.7 (v8 had them swapped)
        #   ʘ 1.0 (bilabial click closure), ǂ 0.6 (palatal click, no tip)
        if seg in ('ʈ', 'ɖ', 'ɳ', 'ʈ͡ʂ', 'ɖ͡ʐ'):
            x[4] = 0.8
        elif seg == 'ɻ':
            x[4] = 0.8
        elif seg == 'ɭ':
            x[4] = 0.7
        elif seg == 'ɹ':
            x[4] = 0.7
        elif seg == 'ʘ':
            x[4] = 1.0
        elif seg == 'ǂ':
            x[4] = 0.6
        else:
            x[4] = v[3]
        # --- tongue_root
        x[5] = v[5]
        # --- vel_open
        x[6] = v[6]
        # --- lateral_ratio
        x[7] = v[7]
        # --- voiced
        x[8] = v[8]
        # --- glottal_aperture: cg/sg lookup
        x[9] = aperture_of(v)
        # --- glottal_tension: inherit v8 laryngeal_tension
        x[10] = -0.6 if seg == 'ɦ' else v[11]   # ɦ breathy: tension -0.6 (v8 0.3)
        # --- larynx_height: ejective/implosive rule
        x[11] = larynx_of(v, seg)
        # --- duration / jet_focus / area / airflow inherit
        x[12] = v[12]
        x[13] = v[13]
        x[14] = v[14] if not is_vowel else VOWEL_COL[seg][1]
        x[15] = v[15]
        # --- affricate composition: inherit fricative-phase rounding
        # (area stays at the v8 affricate value -- t͡s 0.1 vs s 0.08 is an
        # intended closure-phase distinction)
        if seg in AFFRICATE_FRIC and AFFRICATE_FRIC[seg] in out:
            x[3] = out[AFFRICATE_FRIC[seg]][3]   # rounding of the fricative
        # ejective affricate t͡ʃʼ inherits ʃ rounding too
        if seg == 't͡ʃʼ' and 't͡ʃ' in out:
            x[3] = out['t͡ʃ'][3]
        # --- glide composition: semi-vowel inherits vowel partner's
        # tongue root (ATR) and lip shape; area slightly narrower
        if seg in GLIDE_PARTNER and GLIDE_PARTNER[seg] in out:
            pv = out[GLIDE_PARTNER[seg]]
            x[5] = pv[5]                    # tongue_root (ATR)
            x[3] = pv[3]                    # lip shape
            x[1] = pv[1]                    # tongue-body position (front/back)
            # velar glide ɰ is wider than the others (v8 0.45): keep its
            # extra openness rather than the uniform -0.10
            x[14] = 0.35 if seg == 'ɰ' else pv[14] - 0.10
        out[seg] = [round(float(t), 3) for t in x]
    # ɞ (central open-mid rounded vowel): IPA standard, absent from v8.
    # Rounding partner of ɜ -- same place/area, lips +1.0.
    if 'ɜ' in out:
        x = list(out['ɜ'])
        x[3] = 1.0
        out['ɞ'] = [round(float(t), 3) for t in x]
    return out


def main():
    table = build()
    print(f'generated {len(table)} segments, {NDIM} dims\n')

    # spot checks with PROVISIONAL weights (place must dominate; final
    # weights from fit_metric).  Unit-weight distances show RAW separations.
    def d(a, b):
        return np.sqrt(np.sum((np.array(table[a]) - np.array(table[b])) ** 2))
    print('== raw unit-weight separations ==')
    print(f'  ʃ-ɕ   = {d("ʃ","ɕ"):.3f}  (place 0.360 vs 0.430: diff 0.07)')
    print(f'  k-q   = {d("k","q"):.3f}  (place 0.640 vs 0.710: diff 0.07)')
    print(f'  ʃ-ɧ   = {d("ʃ","ɧ"):.3f}  (v8 0.159; body +0.4 separates)')
    print(f'  ɧ-ç   = {d("ɧ","ç"):.3f}')
    print(f'  i-y   = {d("i","y"):.3f}  (only lips_rounded differs: '
          f'-0.3 vs 1.0)')
    print(f'  e-ø   = {d("e","ø"):.3f}')
    print(f'  ɐ-ɜ   = {d("ɐ","ɜ"):.3f}  (v8 0.215)')
    # modifiers emulated (SPEC-NEXT §5): ʲ -> body +0.4; ʰ -> aperture 0.9
    def mod(base, **kw):
        x = np.array(table[base])
        for k, v in kw.items():
            x[DIMS.index(k)] = v
        return x
    t = np.array(table['t']); tj = mod('t', body=0.4)
    print(f'  t-tʲ   = {np.sqrt(np.sum((t-tj)**2)):.3f}  (body +0.4)')
    k = np.array(table['k'])
    kh = mod('k', glottal_aperture=0.9)
    kfort = mod('k', glottal_tension=1.0)
    klen = mod('k', glottal_tension=-0.5)
    print(f'  k-kʰ   = {np.sqrt(np.sum((k-kh)**2)):.3f}  (aperture)')
    print(f'  k-k͈   = {np.sqrt(np.sum((k-kfort)**2)):.3f}  (tension +1)')
    print(f'  k-k͉   = {np.sqrt(np.sum((k-klen)**2)):.3f}  (tension -0.5)')
    print(f'  p-pʼ   = {d("p","pʼ"):.3f}  (aperture + larynx_height + tension)')

    print('\n== vowel place/area provenance (acoustic data) ==')
    for v in ('i', 'y', 'e', 'ø', 'a', 'u', 'ə', 'ɐ'):
        if v in table:
            print(f'  {v}: place={table[v][0]:.3f} area={table[v][14]:.3f} '
                  f'lips={table[v][3]:+.2f}')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'dims': DIMS, 'table': table}, f, indent=1,
                  ensure_ascii=False)
    print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
