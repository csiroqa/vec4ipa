#!/usr/bin/env python3
import sys
"""Verify modifier (diacritic) variants in the 16-dim space.

Applies SPEC-NEXT §5 modifier rules on top of base vectors and checks:
  1. variant vs base distance is sane (not 0, not huge)
  2. different modifiers on the same base are mutually distinguishable
  3. coarticulation modifiers hit the new axes (body for ʲ/ˠ, tension
     for fortis/lenis, larynx_height for ejective)
  4. cross-check: variants do not collide with the base table

NOTE: this validates the DESIGN MODEL (its own Python re-implementation
of the modifier rules over tools/data/vec_table_16.json), not the C
binaries.  The compiled modifier semantics live in MODS in
src/ipa2vec_core.h; binary-level variant behaviour is covered by
tools/test_suite.py / tools/test_metric_space.py.

Run: python tools/verify_modifiers.py
"""

import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC = os.path.join(ROOT, 'tools', 'data', 'vec_table_16.json')

DIMS = ['place', 'body', 'lips_closed', 'lips_rounded', 'tip_shape',
        'tongue_root', 'vel_open', 'lateral_ratio', 'voiced',
        'glottal_aperture', 'glottal_tension', 'larynx_height', 'duration',
        'jet_focus', 'effective_oral_area', 'airflow_direction']
I = {d: k for k, d in enumerate(DIMS)}

# SPEC-NEXT §5 modifier rules (16-dim targets)
MODS = {
    'nasal':       lambda v: setv(v, vel_open=0.6),
    'long':        lambda v: setv(v, duration=2.0),
    'half':        lambda v: setv(v, duration=1.5),
    'extra_short': lambda v: setv(v, duration=min(v[I['duration']], 0.5)),
    'asp':         lambda v: setv(v, glottal_aperture=0.9),
    'weak_asp':    lambda v: setv(v, glottal_aperture=0.6),
    'breathy_asp': lambda v: setv(v, glottal_aperture=0.7, voiced=1.0),
    'creaky':      lambda v: setv(v, glottal_aperture=-0.7, glottal_tension=0.7),
    'breathy':     lambda v: setv(v, glottal_aperture=0.55, glottal_tension=-0.6),
    'voiceless':   lambda v: setv(v, voiced=0.0, glottal_aperture=0.4),
    'voiced':      lambda v: setv(v, voiced=1.0, glottal_aperture=0.0),
    'fortis':      lambda v: setv(v, glottal_tension=1.0),
    'lenis':       lambda v: setv(v, glottal_tension=-0.5),
    'dental':      lambda v: setv(v, place=0.220),
    'linguolabial':lambda v: setv(v, place=0.115),
    'laminal':     lambda v: setv(v, tip_shape=0.6),
    'apical':      lambda v: setv(v, tip_shape=0.8),
    'advanced':    lambda v: setv(v, place=max(v[I['place']] - 0.04, 0.02)),
    'retracted':   lambda v: setv(v, place=min(v[I['place']] + 0.04, 0.98)),
    'centralized': lambda v: setv(v, place=0.500),
    'midcent':     lambda v: setv(v, place=0.500,
                                  effective_oral_area=v[I['effective_oral_area']] + 0.1),
    'raised':      lambda v: setv(v, effective_oral_area=v[I['effective_oral_area']] - 0.1),
    'lowered':     lambda v: setv(v, effective_oral_area=v[I['effective_oral_area']] + 0.1),
    'rnd_more':    lambda v: setv(v, lips_rounded=v[I['lips_rounded']] + 0.3),
    'rnd_less':    lambda v: setv(v, lips_rounded=v[I['lips_rounded']] - 0.3),
    'labialized':  lambda v: setv(v, lips_rounded=max(v[I['lips_rounded']], 0.5)),
    'palatalized': lambda v: setv(v, body=v[I['body']] + 0.4),
    'velarized':   lambda v: setv(v, body=v[I['body']] - 0.3),
    'pharyngeal':  lambda v: setv(v, tongue_root=0.7),
    'atr':         lambda v: setv(v, tongue_root=-0.5),
    'rtr':         lambda v: setv(v, tongue_root=0.5),
    'rhot':        lambda v: setv(v, tip_shape=max(v[I['tip_shape']], 0.7),
                                  duration=v[I['duration']] + 0.3),
    'syllabic':    lambda v: setv(v, duration=v[I['duration']] + 0.5),
    'unrel':       lambda v: setv(v, duration=0.1),
    'nasal_rel':   lambda v: setv(v, vel_open=1.0, duration=v[I['duration']] + 0.3),
    'lat_release': lambda v: setv(v, lateral_ratio=1.0,
                                  duration=v[I['duration']] + 0.3),
    'ejective':    lambda v: setv(v, glottal_aperture=-1.0, glottal_tension=0.6,
                                  larynx_height=1.0),
    'implosive':   lambda v: setv(v, glottal_aperture=-0.55, voiced=1.0,
                                  larynx_height=-1.0),
    # ---- v8 full modifier set (16-dim ports) ----
    'glottal_onset': lambda v: setv(v, glottal_aperture=-1.0),
    'nasal_click': lambda v: setv(v, vel_open=1.0, voiced=1.0,
                                  glottal_aperture=0.0),
    'schwa_rel':  lambda v: setv(v, effective_oral_area=0.7),
    'fric_release': lambda v: setv(v, effective_oral_area=0.08,
                                   duration=v[I['duration']] + 0.2),
    'offglide_lab': lambda v: setv(v, lips_rounded=max(v[I['lips_rounded']], 0.5),
                                   body=v[I['body']] - 0.3),
    'sup_front':  lambda v: setv(v, place=0.575),   # offglide to /i/ (v8: body 1.0)
    'sup_back':   lambda v: setv(v, place=0.640),
    'sup_mid':    lambda v: setv(v, place=0.525,
                                 effective_oral_area=0.7),
    'sup_open':   lambda v: setv(v, effective_oral_area=1.0),
    'sup_stop':   lambda v: setv(v, effective_oral_area=0.0, duration=0.1),
    'centralized':lambda v: setv(v, place=0.500),
    'whistled':   lambda v: setv(v, jet_focus=v[I['jet_focus']] + 0.3,
                                 lips_rounded=max(v[I['lips_rounded']], 0.6)),
    'alveolar_mark': lambda v: setv(v, place=0.290, tip_shape=0.6),
    'lbd_mark':   lambda v: setv(v, place=0.150),
    'part_voiceless': lambda v: setv(v, voiced=0.4, glottal_aperture=0.2),
    'part_voiced':    lambda v: setv(v, voiced=0.6, glottal_aperture=0.2),
    'sliding':    lambda v: setv(v, duration=v[I['duration']] + 0.3),
    'retroflex':  lambda v: setv(v, tip_shape=max(v[I['tip_shape']], 0.8),
                                 place=0.500),   # retroflex anchor (v8: mod_retracted -> ʈ-class)
    'pal_hook':   lambda v: setv(v, body=v[I['body']] + 0.4),
    'lab_subw':   lambda v: setv(v, lips_rounded=max(v[I['lips_rounded']], 0.5)),
}


def setv(v, **kw):
    x = np.array(v, dtype=float)
    for k, val in kw.items():
        x[I[k]] = val
    return x


def main():
    d = json.load(open(VEC, encoding='utf-8'))
    tbl = d['table']
    names = list(tbl)

    print(f'== modifier verification on {len(names)} base segments ==\n')
    fails = 0

    # 1. variants of a few representative bases
    bases = ['t', 'p', 'b', 'k', 'a', 'n', 'l', 'u']
    checks = [
        ('t', ['asp', 'palatalized', 'velarized', 'labialized', 'dental',
               'unrel', 'voiced', 'breathy', 'creaky', 'ejective',
               'nasal_rel', 'lat_release']),
        ('p', ['asp', 'ejective', 'unrel', 'voiceless', 'fortis', 'lenis']),
        ('a', ['nasal', 'long', 'creaky', 'breathy', 'rhot', 'centralized',
               'raised', 'lowered']),
        ('n', ['syllabic', 'voiceless', 'nasal_rel', 'palatalized']),
        ('l', ['velarized', 'voiceless', 'syllabic']),
        ('k', ['asp', 'ejective', 'labialized', 'palatalized', 'velarized',
               'pharyngeal', 'fortis', 'lenis']),
        ('b', ['breathy_asp', 'asp', 'creaky', 'palatalized', 'labialized']),
        ('u', ['nasal', 'long', 'half', 'centralized', 'breathy', 'creaky']),
    ]
    print('== 1. variant vs base distance ==')
    idempotent = {('p', 'voiceless'), ('b', 'voiced'), ('n', 'nasal'),
                  ('a', 'centralized'), ('a', 'lowered')}  # lowered /a/ saturates at area 1.0
    for base, mods in checks:
        bv = np.array(tbl[base])
        for m in mods:
            v = MODS[m](bv)
            dd = np.sqrt(np.sum((v - bv) ** 2))
            if dd < 0.05 and (base, m) not in idempotent:
                fails += 1
                print(f'  FAIL {base}+{m}: d={dd:.3f} (too close)')
        # show a few
        for m in mods[:3]:
            v = MODS[m](bv)
            dd = np.sqrt(np.sum((v - bv) ** 2))
            print(f'  {base}+{m}: d={dd:.3f}')

    # 2. same base, different modifiers mutually distinguishable
    # (unit weights; cross-axis pairs like dental[place] vs unrel[duration]
    # separate further under the fitted weights -- see §7)
    print('\n== 2. variants of t mutually distinguishable ==')
    t = np.array(tbl['t'])
    variants = {}
    for m in ['asp', 'palatalized', 'dental', 'unrel', 'voiced', 'creaky',
              'ejective', 'fortis', 'lenis', 'labialized']:
        variants[m] = MODS[m](t)
    for a in variants:
        for b in variants:
            if a < b:
                dd = np.sqrt(np.sum((variants[a] - variants[b]) ** 2))
                if dd < 0.05:
                    fails += 1
                    print(f'  FAIL t+{a} vs t+{b}: d={dd:.3f}')

    # 3. hit the new axes
    print('\n== 3. new-axis hits ==')
    t = np.array(tbl['t'])
    v = MODS['palatalized'](t)
    print(f'  t+palatalized: body={v[I["body"]]:.2f} (expect ~0.4)')
    v = MODS['fortis'](t)
    print(f'  t+fortis: tension={v[I["glottal_tension"]]:.2f} (expect 1.0)')
    v = MODS['ejective'](t)
    print(f'  t+ejective: aperture={v[I["glottal_aperture"]]:.2f} '
          f'tension={v[I["glottal_tension"]]:.2f} '
          f'larynx={v[I["larynx_height"]]:.2f}')
    v = MODS['implosive'](t)
    print(f'  t+implosive: aperture={v[I["glottal_aperture"]]:.2f} '
          f'larynx={v[I["larynx_height"]]:.2f}')

    # 4. variants vs base table collisions
    # NOTE: ejective/implosive variants EQUAL the base-table ejective/
    # implosive entries (t+ejective == tʼ) -- that is consistency, not a
    # collision.  Excluded from the collision check.
    print('\n== 4. variants not colliding with base table ==')
    X = np.array([tbl[n] for n in names])
    skip = {'ejective', 'implosive'}
    for base in ['t', 'a', 'n']:
        bv = np.array(tbl[base])
        for m in ['asp', 'palatalized', 'nasal', 'long', 'creaky']:
            v = MODS[m](bv)
            dd = np.sqrt(np.sum((X - v) ** 2, axis=1))
            j = np.argmin(dd)
            if dd[j] < 0.2:
                fails += 1
                print(f'  FAIL {base}+{m} collides with {names[j]}: '
                      f'd={dd[j]:.3f}')
    # consistency: t+ejective should EXACTLY equal tʼ (base entry)
    t = np.array(tbl['t'])
    v = MODS['ejective'](t)
    dd = np.sqrt(np.sum((np.array(tbl["tʼ"]) - v) ** 2))
    print(f'  t+ejective vs base tʼ: d={dd:.3f} '
          f'({"consistency OK" if dd < 1e-9 else "MISMATCH"})')
    if dd >= 1e-9:
        fails += 1

    # 5. full v8 modifier set: every modifier moves the vector sanely
    print('\n== 5. full v8 modifier set (16-dim ports) ==')
    extra_mods = ['glottal_onset', 'nasal_click', 'schwa_rel', 'fric_release',
                  'offglide_lab', 'sup_front', 'sup_back', 'sup_mid',
                  'sup_open', 'sup_stop', 'centralized', 'whistled',
                  'alveolar_mark', 'lbd_mark', 'part_voiceless',
                  'part_voiced', 'sliding', 'retroflex', 'pal_hook',
                  'lab_subw']
    for base in ['t', 'a', 'ǀ', 'w']:
        if base not in tbl:
            continue
        bv = np.array(tbl[base])
        for m in extra_mods:
            v = MODS[m](bv)
            dd = np.sqrt(np.sum((v - bv) ** 2))
            # idempotent cases: modifier target already equals base state
            idem = {('t', 'alveolar_mark'), ('a', 'sup_open'), ('a', 'sup_mid'),
                    ('ǀ', 'nasal_click'), ('a', 'centralized'),
                    ('w', 'sup_back'), ('w', 'lab_subw')}
            if dd < 0.05 and (base, m) not in idem:
                fails += 1
                print(f'  FAIL {base}+{m}: d={dd:.3f} (no effect)')
            elif (base, m) in idem:
                print(f'  {base}+{m}: d={dd:.3f} (idempotent, OK)')
        # spot-show the meaningful ones
        for m in ['glottal_onset', 'retroflex', 'pal_hook', 'lab_subw',
                  'fric_release', 'whistled', 'schwa_rel']:
            v = MODS[m](bv)
            dd = np.sqrt(np.sum((v - bv) ** 2))
            print(f'  {base}+{m}: d={dd:.3f}')
        print()

    print(f'\n== result: {"ALL PASS" if fails == 0 else f"{fails} FAILURES"} ==')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    main()
