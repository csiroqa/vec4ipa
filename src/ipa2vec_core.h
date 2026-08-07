/*
 * ipa2vec_core.h — shared core for the ipa2vec tool suite.
 *
 * Included by:
 *   ipa2vec  (IPA -> vectors)   src/ipa2vec_main.c
 *   vec2ipa  (vectors -> IPA)   src/vec2ipa_main.c
 *   vec4ipa  (full inventory)   src/vec4ipa_main.c
 *
 * All definitions are static: each translation unit gets its own copy.
 * Base vectors: generated src/vectors.h from IPA_VECTORS.md + metric.json.
 */

#ifndef IPA2VEC_CORE_H
#define IPA2VEC_CORE_H

/* tool-suite version (single source of truth) */
#define IPA2VEC_VERSION "1.0.0"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>

#ifdef _WIN32
#include <windows.h>
#include <io.h>
#else
#include <unistd.h>
#endif

/* some core helpers are only used by one of the three tools; silence
 * unused-function warnings for static functions in a header */
#if defined(__GNUC__) || defined(__clang__)
#define IPA2VEC_MAYBE_UNUSED __attribute__((unused))
#else
#define IPA2VEC_MAYBE_UNUSED
#endif

#include "vectors.h"

/*
 * ipa2vec — IPA/extIPA ⇄ 16-D articulatory vector converter.
 *
 * Two-layer intermediate representation (IR):
 *
 *   Layer 1 (character-composition order): tokens in the order they appear
 *     in the input string (base segment, then each modifier as written,
 *     precomposed chars expanded to base + combining marks).
 *
 *   Layer 2 (natural-language order): the same tokens sorted by feature
 *     tier, so features are applied to the vector in a canonical order:
 *       AIRSTREAM → LARYNGEAL → PLACE → MANNER → NASAL → TIMING
 *
 * Every token carries a latin transliteration (see src/names.tsv),
 * which is also the key used for the reverse direction (vector → IPA).
 *
 * Usage:
 *   ipa2vec "tʰeɪk"           parse -> vectors
 *   ipa2vec -j "pʰaːk"        JSON output
 *   ipa2vec -i "tʰeɪk"        inverse: show IR layers then rebuild IPA
 *   ipa2vec -d "p" "b"        weighted distance
 *   ipa2vec -n "v0,...,v15"   nearest base segment to a vector
 *   ipa2vec -t                list base table (ipa, latin, vector)
 *   ipa2vec -v                version
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>

#ifdef _WIN32
#include <windows.h>
#include <io.h>
#else
#include <unistd.h>
#endif

#include "vectors.h"

/* ------------------------------------------------------------------ */
/* Wide-argument helpers (Windows argv is not UTF-8)                   */
/* ------------------------------------------------------------------ */

#ifdef _WIN32
static char **g_argv_utf8;
static int g_argc_utf8;

static char *wide_to_utf8(const wchar_t *w)
{
    if (!w) return NULL;
    int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
    if (n <= 0) return NULL;
    char *s = (char *)malloc((size_t)n);
    if (s) WideCharToMultiByte(CP_UTF8, 0, w, -1, s, n, NULL, NULL);
    return s;
}
#endif

/* ------------------------------------------------------------------ */
/* UTF-8                                                               */
/* ------------------------------------------------------------------ */

static IPA2VEC_MAYBE_UNUSED int utf8_decode (const unsigned char *s, unsigned long *cp)
{
    if (s[0] < 0x80) { *cp = s[0]; return 1; }
    if ((s[0] & 0xE0) == 0xC0 && (s[1] & 0xC0) == 0x80) {
        *cp = ((s[0] & 0x1F) << 6) | (s[1] & 0x3F);
        if (*cp < 0x80) return 0;
        return 2;
    }
    if ((s[0] & 0xF0) == 0xE0 && (s[1] & 0xC0) == 0x80 && (s[2] & 0xC0) == 0x80) {
        *cp = ((s[0] & 0x0F) << 12) | ((s[1] & 0x3F) << 6) | (s[2] & 0x3F);
        if (*cp < 0x800) return 0;
        return 3;
    }
    if ((s[0] & 0xF8) == 0xF0 && (s[1] & 0xC0) == 0x80 &&
        (s[2] & 0xC0) == 0x80 && (s[3] & 0xC0) == 0x80) {
        *cp = ((s[0] & 0x07) << 18) | ((s[1] & 0x3F) << 12) |
              ((s[2] & 0x3F) << 6) | (s[3] & 0x3F);
        if (*cp < 0x10000) return 0;
        return 4;
    }
    return 0;
}

static IPA2VEC_MAYBE_UNUSED int cp_to_utf8 (unsigned long cp, char out[5])
{
    if (cp < 0x80) { out[0] = (char)cp; return 1; }
    if (cp < 0x800) {
        out[0] = (char)(0xC0 | (cp >> 6));
        out[1] = (char)(0x80 | (cp & 0x3F));
        return 2;
    }
    if (cp < 0x10000) {
        out[0] = (char)(0xE0 | (cp >> 12));
        out[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (char)(0x80 | (cp & 0x3F));
        return 3;
    }
    out[0] = (char)(0xF0 | (cp >> 18));
    out[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
    out[2] = (char)(0x80 | ((cp >> 6) & 0x3F));
    out[3] = (char)(0x80 | (cp & 0x3F));
    return 4;
}

/* ------------------------------------------------------------------ */
/* Vector machinery                                                    */
/* ------------------------------------------------------------------ */

typedef struct {
    double v[NDIM];
    int airstream;
    char note[96];
    /* tone annotations: 5 groups, each up to 3 degrees;
     * tone[g][0]==NAN means group empty. */
    double tone[5][3];
    int tkind[5];          /* 0 none, 1 contour, 2 class, 3 step, 4 global */
} SegVec;

static IPA2VEC_MAYBE_UNUSED double seg_dist (const double a[NDIM], const double b[NDIM])
{
    double s = 0.0;
    for (int i = 0; i < NDIM; i++) {
        double d = a[i] - b[i];
        s += METRIC_W[i] * d * d;
    }
    return sqrt(s);
}

static IPA2VEC_MAYBE_UNUSED double seg_dist_full (const SegVec *a, const SegVec *b)
{
    double d = seg_dist(a->v, b->v);
    if (a->airstream != b->airstream)
        d += METRIC_LAMBDA;
    return d;
}

/* ------------------------------------------------------------------ */
/* Modifier table — every modifier has: code point, latin name, tier,  */
/* and an apply() that modifies the vector IN PLACE (sequential).      */
/* ------------------------------------------------------------------ */

typedef enum {
    TIER_AIRSTREAM = 0,
    TIER_LARYNGEAL,
    TIER_PLACE,
    TIER_MANNER,
    TIER_NASAL,
    TIER_TIMING,
    TIER_COUNT
} Tier;

static const char *TIER_NAMES[TIER_COUNT] = {
    "airstream", "laryngeal", "place", "manner", "nasal", "timing"
};

typedef struct {
    unsigned long cp;
    const char *ipa;      /* the combining mark as printed */
    const char *latin;    /* transliteration / identifier */
    Tier tier;
    int air;              /* if >= 0: force airstream index (e.g. ejective) */
    void (*apply)(double v[NDIM], const void *unused);
    /* tone semantics: 0 = none; 1 = 5-level tone letter (val in val[0]);
     * 2 = Chinese tone class (index 0..7 in val[0]);
     * 3 = upstep/downstep (dir in val[0]); 4 = global rise/fall. */
    int tone_kind;
    double val[2];
    const char *infer;    /* non-NULL: applying this modifier is an inference
                           * (symbol reinterpretation); report to stderr */
    int reverse;          /* 1 = usable in reverse fitting (vec2ipa);
                           * 0 = input-tolerance only (ASCII ', quotes,
                           * prime …) — never emitted when going vec -> IPA */
} ModRec;

/* --- apply functions (sequential, order matters) --- */
static IPA2VEC_MAYBE_UNUSED void mod_nasal (double v[NDIM], const void *m) { (void)m; v[6]  = 0.8; }
static IPA2VEC_MAYBE_UNUSED void mod_long (double v[NDIM], const void *m) { (void)m; v[12] = 2.0; }
static IPA2VEC_MAYBE_UNUSED void mod_half (double v[NDIM], const void *m) { (void)m; v[12] = 1.5; }
static IPA2VEC_MAYBE_UNUSED void mod_asp (double v[NDIM], const void *m) { (void)m; v[10] = 0.9; v[9] = 0.0; }
static IPA2VEC_MAYBE_UNUSED void mod_creaky (double v[NDIM], const void *m) { (void)m; v[9] = 0.7; v[10] = 0.0; v[11] = 0.7; }
static IPA2VEC_MAYBE_UNUSED void mod_breathy (double v[NDIM], const void *m) { (void)m; v[10] = 0.55; v[9] = 0.2; v[11] = -0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_phar (double v[NDIM], const void *m) { (void)m; v[5] = 0.7; v[4] = -0.2; }
static IPA2VEC_MAYBE_UNUSED void mod_velar (double v[NDIM], const void *m) { (void)m; v[4] = -0.3; v[5] = 0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_pal (double v[NDIM], const void *m) { (void)m; v[4] = 0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_lab (double v[NDIM], const void *m) { (void)m; if (v[1] < 0.5) v[1] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_syl (double v[NDIM], const void *m) { (void)m; v[12] += 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_nosyl (double v[NDIM], const void *m) { (void)m; v[12] -= 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_unrel (double v[NDIM], const void *m) { (void)m; v[12] = 0.1; }
static IPA2VEC_MAYBE_UNUSED void mod_voiceless (double v[NDIM], const void *m) { (void)m; v[8] = 0.0; v[9] = 0.0; v[10] = 0.4; }
static IPA2VEC_MAYBE_UNUSED void mod_voiced (double v[NDIM], const void *m) { (void)m; v[8] = 1.0; v[9] = 0.2; v[10] = 0.0; }
static IPA2VEC_MAYBE_UNUSED void mod_nasal_click (double v[NDIM], const void *m){ (void)m; v[6] = 1.0; v[8] = 1.0; v[9] = 0.2; v[10] = 0.0; v[12] = 1.0; }
static IPA2VEC_MAYBE_UNUSED void mod_dental (double v[NDIM], const void *m) { (void)m; v[2] = 1.0; if (v[3] < 0.5) v[3] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_raised (double v[NDIM], const void *m) { (void)m; v[3] += 0.15; }
static IPA2VEC_MAYBE_UNUSED void mod_lowered (double v[NDIM], const void *m) { (void)m; v[3] -= 0.15; }
static IPA2VEC_MAYBE_UNUSED void mod_advanced (double v[NDIM], const void *m) { (void)m; v[2] += 0.15; }
static IPA2VEC_MAYBE_UNUSED void mod_retracted (double v[NDIM], const void *m) { (void)m; v[2] -= 0.15; }
static IPA2VEC_MAYBE_UNUSED void mod_more_round (double v[NDIM], const void *m) { (void)m; if (v[1] < 0.7) v[1] += 0.25; }
static IPA2VEC_MAYBE_UNUSED void mod_less_round (double v[NDIM], const void *m) { (void)m; if (v[1] > -0.7) v[1] -= 0.25; }
static IPA2VEC_MAYBE_UNUSED void mod_laminal (double v[NDIM], const void *m) { (void)m; if (v[3] < 0.6) v[3] = 0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_apical (double v[NDIM], const void *m) { (void)m; if (v[3] < 0.65) v[3] = 0.65; }
static IPA2VEC_MAYBE_UNUSED void mod_midcent (double v[NDIM], const void *m) { (void)m; v[3] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_rhot (double v[NDIM], const void *m) { (void)m; v[11] += 0.5; v[3] += 0.1; }
static IPA2VEC_MAYBE_UNUSED void mod_extra_short (double v[NDIM], const void *m){ (void)m; v[12] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_ejective (double v[NDIM], const void *m) { (void)m; v[9] = 1.0; v[10] = 0.0; v[11] = 0.6; v[8] = 0.0; }
static IPA2VEC_MAYBE_UNUSED void mod_glottal_onset (double v[NDIM], const void *m){ (void)m; v[9] = 1.0; v[10] = 0.0; }
static IPA2VEC_MAYBE_UNUSED void mod_breathy_asp (double v[NDIM], const void *m){ (void)m; v[10] = 0.7; v[9] = 0.2; v[8] = 1.0; }
static IPA2VEC_MAYBE_UNUSED void mod_lat_release (double v[NDIM], const void *m){ (void)m; v[7] = 1.0; }
static IPA2VEC_MAYBE_UNUSED void mod_nasal_rel (double v[NDIM], const void *m){ (void)m; v[6] = 0.8; v[12] += 0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_schwa_rel (double v[NDIM], const void *m){ (void)m; v[14] = 0.7; }
static IPA2VEC_MAYBE_UNUSED void mod_fric_release (double v[NDIM], const void *m){ (void)m; v[14] = 0.08; v[12] += 0.2; }
static IPA2VEC_MAYBE_UNUSED void mod_offglide_lab (double v[NDIM], const void *m){ (void)m; if (v[1] < 0.5) v[1] = 0.5; v[4] = -0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_offglide_pal (double v[NDIM], const void *m){ (void)m; v[4] = 0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_centralized (double v[NDIM], const void *m){ (void)m; v[4] *= 0.5; }
/* superscript-letter modifiers (IPA letters used as diacritics) */
static IPA2VEC_MAYBE_UNUSED void mod_sup_rhot1 (double v[NDIM], const void *m){ (void)m; v[11] += 0.5; v[3] += 0.1; }
static IPA2VEC_MAYBE_UNUSED void mod_sup_front (double v[NDIM], const void *m){ (void)m; v[4] = 1.0; }
static IPA2VEC_MAYBE_UNUSED void mod_sup_back (double v[NDIM], const void *m){ (void)m; v[4] = -0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_sup_mid (double v[NDIM], const void *m){ (void)m; v[4] *= 0.5; v[14] = 0.7; }
static IPA2VEC_MAYBE_UNUSED void mod_sup_open (double v[NDIM], const void *m){ (void)m; v[14] = 1.0; }
static IPA2VEC_MAYBE_UNUSED void mod_sup_stop (double v[NDIM], const void *m){ (void)m; v[14] = 0.0; v[12] = 0.1; }
static IPA2VEC_MAYBE_UNUSED void mod_linguolabial (double v[NDIM], const void *m){ (void)m; v[2] = 1.0; v[3] = 0.6; v[0] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_atr (double v[NDIM], const void *m){ (void)m; v[5] -= 0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_rtr (double v[NDIM], const void *m){ (void)m; v[5] += 0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_weak_asp (double v[NDIM], const void *m){ (void)m; v[10] = 0.6; v[9] = 0.1; }
static IPA2VEC_MAYBE_UNUSED void mod_pal_hook (double v[NDIM], const void *m){ (void)m; v[4] = 0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_lab_subw (double v[NDIM], const void *m){ (void)m; if (v[1] < 0.5) v[1] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_fortis (double v[NDIM], const void *m){ (void)m; v[11] += 0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_lenis (double v[NDIM], const void *m){ (void)m; v[11] -= 0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_alveolar_mark (double v[NDIM], const void *m){ (void)m; v[2] = 0.55; v[3] = 0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_whistled (double v[NDIM], const void *m){ (void)m; v[13] += 0.3; v[1] = 0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_lbd_mark (double v[NDIM], const void *m){ (void)m; v[0] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_sliding (double v[NDIM], const void *m){ (void)m; v[12] += 0.3; }

static const ModRec MODS[] = {
    /* --- postposed combining marks --- */
    { 0x0303, "◌̃",  "nas",       TIER_NASAL,     -1, mod_nasal,        0, {0,0} , NULL, 1  },
    { 0x0304, "◌̄",  "macron_tone", TIER_COUNT,    -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x0324, "◌̤",  "breathy",   TIER_LARYNGEAL, -1, mod_breathy,      0, {0,0} , NULL, 1  },
    { 0x0306, "◌̆",  "short",     TIER_TIMING,    -1, mod_extra_short,  0, {0,0} , NULL, 1  },
    { 0x0308, "◌̈",  "centralized", TIER_MANNER,  -1, mod_centralized,  0, {0,0} , NULL, 1  },
    { 0x030A, "◌̊",  "vl",        TIER_LARYNGEAL, -1, mod_voiceless,    0, {0,0} , NULL, 1  },
    { 0x030B, "◌̋",  "extra_high_tone", TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x031A, "◌̚",  "unrel",     TIER_TIMING,    -1, mod_unrel,        0, {0,0} , NULL, 1  },
    { 0x031C, "◌̜",  "rnd_less",  TIER_PLACE,     -1, mod_less_round,   0, {0,0} , NULL, 1  },
    { 0x031D, "◌̝",  "raised",    TIER_MANNER,    -1, mod_raised,       0, {0,0} , NULL, 1  },
    { 0x031E, "◌̞",  "lowered",   TIER_MANNER,    -1, mod_lowered,      0, {0,0} , NULL, 1  },
    { 0x031F, "◌̟",  "adv",       TIER_PLACE,     -1, mod_advanced,     0, {0,0} , NULL, 1  },
    { 0x0320, "◌̠",  "retr",      TIER_PLACE,     -1, mod_retracted,    0, {0,0} , NULL, 1  },
    { 0x0318, "◌̘",  "atr",       TIER_PLACE,     -1, mod_atr,          0, {0,0} , NULL, 1  },
    { 0x0319, "◌̙",  "rtr",       TIER_PLACE,     -1, mod_rtr,          0, {0,0} , NULL, 1  },
    { 0x0322, "◌̢",  "retroflex", TIER_PLACE,     -1, mod_retracted,    0, {0,0} , NULL, 1  },
    { 0x0321, "◌̡",  "pal_hook",  TIER_PLACE,     -1, mod_pal_hook,     0, {0,0} , NULL, 1  },
    { 0x032B, "◌̫",  "lab_subw",  TIER_PLACE,     -1, mod_lab_subw,     0, {0,0} , NULL, 1  },
    { 0x0316, "◌̖",  "tone_lowfall", TIER_COUNT,  -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x0317, "◌̗",  "tone_lowrise", TIER_COUNT,  -1, NULL, 0, {0,0} , NULL, 1  },
    /* IPA 2018: fortis / lenis */
    { 0x0348, "◌͈",  "fortis",    TIER_LARYNGEAL, -1, mod_fortis,      0, {0,0} , NULL, 1  },
    { 0x0349, "◌͉",  "lenis",     TIER_LARYNGEAL, -1, mod_lenis,       0, {0,0} , NULL, 1  },
    /* extIPA diacritics */
    { 0x0347, "◌͇",  "alveolar",  TIER_PLACE,     -1, mod_alveolar_mark, 0, {0,0} , NULL, 1  },
    { 0x034E, "◌͎",  "whistled",  TIER_MANNER,    -1, mod_whistled,    0, {0,0} , NULL, 1  },
    { 0x1DB9, "◌ᶹ",  "labiodental", TIER_PLACE,   -1, mod_lbd_mark,    0, {0,0} , NULL, 1  },
    { 0x0362, "◌͢",  "sliding",   TIER_TIMING,    -1, mod_sliding,     0, {0,0} , NULL, 1  },
    { 0x0323, "◌̣",  "lowered",   TIER_MANNER,    -1, mod_lowered,      0, {0,0} , NULL, 1  },
    { 0x0325, "◌̥",  "vl",        TIER_LARYNGEAL, -1, mod_voiceless,    0, {0,0} , NULL, 1  },
    { 0x0329, "◌̩",  "syl",       TIER_TIMING,    -1, mod_syl,          0, {0,0} , NULL, 1  },
    { 0x032A, "◌̪",  "dental",    TIER_PLACE,     -1, mod_dental,       0, {0,0} , NULL, 1  },
    { 0x032C, "◌̬",  "vd",        TIER_LARYNGEAL, -1, mod_voiced,       0, {0,0} , NULL, 1  },
    { 0x032F, "◌̯",  "nsyl",      TIER_TIMING,    -1, mod_nosyl,        0, {0,0} , NULL, 1  },
    { 0x0330, "◌̰",  "creaky",    TIER_LARYNGEAL, -1, mod_creaky,       0, {0,0} , NULL, 1  },
    { 0x0334, "◌̴",  "phar",      TIER_PLACE,     -1, mod_phar,         0, {0,0} , NULL, 1  },
    { 0x0339, "◌̹",  "rnd_more",  TIER_PLACE,     -1, mod_more_round,   0, {0,0} , NULL, 1  },
    { 0x033A, "◌̺",  "apical",    TIER_MANNER,    -1, mod_apical,       0, {0,0} , NULL, 1  },
    { 0x033B, "◌̻",  "laminal",   TIER_MANNER,    -1, mod_laminal,      0, {0,0} , NULL, 1  },
    { 0x033C, "◌̼",  "linguolabial", TIER_PLACE,  -1, mod_linguolabial, 0, {0,0} , NULL, 1  },
    { 0x033D, "◌̽",  "midcent",   TIER_MANNER,    -1, mod_midcent,      0, {0,0} , NULL, 1  },
    { 0x0346, "◌͆",  "lam",       TIER_MANNER,    -1, mod_laminal,      0, {0,0} , NULL, 1  },
    /* pitch/tone diacritics — no articulatory effect */
    { 0x0300, "◌̀",  "tone_low",      TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x0301, "◌́",  "tone_high",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x0302, "◌̂",  "tone_fall",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x030C, "◌̌",  "tone_rise",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x030F, "◌̏",  "tone_extralow",TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x030D, "◌̍",  "tone_highv",   TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x030E, "◌̎",  "tone_lowv",    TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    /* --- ligature ties (no apply; handled by parser) --- */
    { 0x035C, "◌͜",  "tie",       TIER_COUNT,     -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x0360, "◌͠",  "tie",       TIER_COUNT,     -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x0361, "◌͡",  "tie",       TIER_COUNT,     -1, NULL, 0, {0,0} , NULL, 1  },
    /* --- postposed spacing modifier letters --- */
    { 0x02B0, "ʰ",   "asp",       TIER_LARYNGEAL, -1, mod_asp,          0, {0,0} , NULL, 1  },
    { 0x02B2, "ʲ",   "pal",       TIER_PLACE,     -1, mod_pal,         0, {0,0} , NULL, 1  },
    { 0x02B7, "ʷ",   "lab",       TIER_PLACE,     -1, mod_lab,         0, {0,0} , NULL, 1  },
    { 0x02BC, "ʼ",   "ej",        TIER_AIRSTREAM, 1,  mod_ejective,    0, {0,0} , NULL, 1  },
    { 0x02BD, "ʽ",   "weak_asp",  TIER_LARYNGEAL, -1, mod_weak_asp,    0, {0,0} , "quote ʽ reinterpreted as weak aspiration", 0  },
    { 0x2018, "‘",   "weak_asp",  TIER_LARYNGEAL, -1, mod_weak_asp,    0, {0,0} , "quote ‘ reinterpreted as weak aspiration", 0  },
    { 0x201B, "‛",   "weak_asp",  TIER_LARYNGEAL, -1, mod_weak_asp,    0, {0,0} , "quote ‛ reinterpreted as weak aspiration", 0  },
    { 0x2032, "′",   "pal_prime", TIER_PLACE,     -1, mod_pal,         0, {0,0} , "prime ′ reinterpreted as palatalization (Irish tradition)", 0  },
    { 0x0027, "'",   "unrel",     TIER_TIMING,    -1, mod_unrel,       0, {0,0} , "ASCII apostrophe ' reinterpreted as unreleased release", 0  },
    { 0x02C0, "ˀ",   "glottal_onset", TIER_AIRSTREAM, -1, mod_glottal_onset, 0, {0,0} , NULL, 1  },
    { 0x02C8, "ˈ",   "stress_1",  TIER_COUNT,     -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x02CC, "ˌ",   "stress_2",  TIER_COUNT,     -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x02D0, "ː",   "long",      TIER_TIMING,    -1, mod_long,        0, {0,0} , NULL, 1  },
    { 0x02D1, "ˑ",   "half",      TIER_TIMING,    -1, mod_half,        0, {0,0} , NULL, 1  },
    { 0x02D4, "˔",   "raised",    TIER_MANNER,    -1, mod_raised,      0, {0,0} , NULL, 1  },
    { 0x02D5, "˕",   "lowered",   TIER_MANNER,    -1, mod_lowered,     0, {0,0} , NULL, 1  },
    { 0x02DE, "˞",   "rhot",      TIER_MANNER,    -1, mod_rhot,        0, {0,0} , NULL, 1  },
    { 0x02E0, "ˠ",   "vel",       TIER_PLACE,     -1, mod_velar,       0, {0,0} , NULL, 1  },
    { 0x02E1, "ˡ",   "lat_release", TIER_MANNER,  -1, mod_lat_release, 0, {0,0} , NULL, 1  },
    { 0x02E2, "ˢ",   "fric_release", TIER_MANNER, -1, mod_fric_release,0, {0,0} , NULL, 1  },
    { 0x02E4, "ˤ",   "phar",      TIER_PLACE,     -1, mod_phar,        0, {0,0} , NULL, 1  },
    /* superscript letters as diacritics (IPA letters used as modifiers) */
    { 0x02B3, "ʳ",   "sup_rhot_r",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 1  },
    { 0x02B4, "ʴ",   "sup_rhot_ʁ",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 1  },
    { 0x02B5, "ʵ",   "sup_rhot_ʕ",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 1  },
    { 0x02B6, "ʶ",   "sup_rhot_ʢ",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 1  },
    { 0x1D49, "ᵉ",   "sup_e",        TIER_PLACE,  -1, mod_sup_front,   0, {0,0} , NULL, 1  },
    { 0x1D4C, "ᵌ",   "sup_ɛ",        TIER_MANNER, -1, mod_sup_mid,     0, {0,0} , NULL, 1  },
    { 0x1D64, "ᵤ",   "sup_u",        TIER_PLACE,  -1, mod_sup_back,    0, {0,0} , NULL, 1  },
    { 0x1D62, "ᵢ",   "sub_i",        TIER_PLACE,  -1, mod_sup_front,   0, {0,0} , NULL, 1  },
    { 0x1D63, "ᵣ",   "sub_r",        TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 1  },
    { 0x1D30, "ᴰ",   "sup_h",        TIER_LARYNGEAL, -1, mod_asp,       0, {0,0} , NULL, 1  },
    { 0x1D3B, "ᴻ",   "sup_N",        TIER_NASAL,  -1, mod_nasal_rel,   0, {0,0} , NULL, 1  },
    { 0x1D2C, "ᴬ",   "sup_A",        TIER_NASAL,  -1, mod_sup_open,    0, {0,0} , NULL, 1  },
    { 0x1D2E, "ᴮ",   "sup_B",        TIER_MANNER, -1, mod_sup_stop,    0, {0,0} , NULL, 1  },
    { 0x1D3C, "ᴼ",   "sup_O",        TIER_PLACE,  -1, mod_sup_back,    0, {0,0} , NULL, 1  },
    { 0x1D3E, "ᴾ",   "sup_P",        TIER_MANNER, -1, mod_sup_stop,    0, {0,0} , NULL, 1  },
    { 0x1D41, "ᵁ",   "sup_U",        TIER_PLACE,  -1, mod_sup_back,    0, {0,0} , NULL, 1  },
    { 0x1D42, "ᵂ",   "sup_W",        TIER_PLACE,  -1, mod_lab,         0, {0,0} , NULL, 1  },
    { 0x02D2, "˒",   "light",        TIER_TIMING, -1, mod_sliding,     0, {0,0} , NULL, 1  },
    { 0x02D3, "˓",   "dark",         TIER_TIMING, -1, mod_sliding,     0, {0,0} , NULL, 1  },
    { 0x02D9, "˙",   "lengthened",   TIER_TIMING, -1, mod_long,        0, {0,0} , NULL, 1  },
    /* --- preposed modifiers --- */
    { 0x1D51, "ᵑ",   "nas_click", TIER_AIRSTREAM, -1, mod_nasal_click, 0, {0,0} , NULL, 1  },
    { 0x1D4B, "ᵋ",   "nas_rel",   TIER_AIRSTREAM, -1, mod_nasal,       0, {0,0} , NULL, 1  },
    { 0x1D4A, "ᵊ",   "schwa_rel", TIER_MANNER,    -1, mod_schwa_rel,   0, {0,0} , NULL, 1  },
    { 0x207F, "ⁿ",   "nasal_rel", TIER_NASAL,     -1, mod_nasal_rel,   0, {0,0} , NULL, 1  },
    { 0x02B1, "ʱ",   "breathy_asp", TIER_LARYNGEAL, -1, mod_breathy_asp, 0, {0,0} , "ʱ = voiced/breathy release (reinterpreted from aspiration)", 1  },
    { 0x02B8, "ʸ",   "offglide_pal", TIER_PLACE,  -1, mod_offglide_pal,0, {0,0} , NULL, 1  },
    { 0x1DB7, "ᶷ",   "offglide_lab", TIER_PLACE,  -1, mod_offglide_lab,0, {0,0} , NULL, 1  },
    { 0x1DA3, "ᶣ",   "offglide_labpal", TIER_PLACE, -1, mod_offglide_pal, 0, {0,0} , NULL, 1  },
    /* --- 5-level tone letters (high->low) --- */
    { 0x02E5, "˥", "tone_5",  TIER_COUNT, -1, NULL, 1, {5,0}, NULL, 1  },
    { 0x02E6, "˦", "tone_4",  TIER_COUNT, -1, NULL, 1, {4,0}, NULL, 1  },
    { 0x02E7, "˧", "tone_3",  TIER_COUNT, -1, NULL, 1, {3,0}, NULL, 1  },
    { 0x02E8, "˨", "tone_2",  TIER_COUNT, -1, NULL, 1, {2,0}, NULL, 1  },
    { 0x02E9, "˩", "tone_1",  TIER_COUNT, -1, NULL, 1, {1,0}, NULL, 1  },
    { 0xA712, "꜒", "tone_5",  TIER_COUNT, -1, NULL, 1, {5,0}, NULL, 1  },
    { 0xA713, "꜓", "tone_4",  TIER_COUNT, -1, NULL, 1, {4,0}, NULL, 1  },
    { 0xA714, "꜔", "tone_3",  TIER_COUNT, -1, NULL, 1, {3,0}, NULL, 1  },
    { 0xA715, "꜕", "tone_2",  TIER_COUNT, -1, NULL, 1, {2,0}, NULL, 1  },
    { 0xA716, "꜖", "tone_1",  TIER_COUNT, -1, NULL, 1, {1,0}, NULL, 1  },
    /* --- Chinese tone classes 1..8 -> 1,-1,2,-2,3,-3,4,-4 --- */
    { 0xA700, "꜀", "class1",  TIER_COUNT, -1, NULL, 2, {1, 0}, NULL, 1  },
    { 0xA701, "꜁", "class2",  TIER_COUNT, -1, NULL, 2, {-1,0}, NULL, 1  },
    { 0xA702, "꜂", "class3",  TIER_COUNT, -1, NULL, 2, {2, 0}, NULL, 1  },
    { 0xA703, "꜃", "class4",  TIER_COUNT, -1, NULL, 2, {-2,0}, NULL, 1  },
    { 0xA704, "꜄", "class5",  TIER_COUNT, -1, NULL, 2, {3, 0}, NULL, 1  },
    { 0xA705, "꜅", "class6",  TIER_COUNT, -1, NULL, 2, {-3,0}, NULL, 1  },
    { 0xA706, "꜆", "class7",  TIER_COUNT, -1, NULL, 2, {4, 0}, NULL, 1  },
    { 0xA707, "꜇", "class8",  TIER_COUNT, -1, NULL, 2, {-4,0}, NULL, 1  },
    /* --- upstep / downstep / global rise / global fall --- */
    { 0xA71B, "ꜛ", "upstep",   TIER_COUNT, -1, NULL, 3, {-1, NAN}, NULL, 1  },
    { 0xA71C, "ꜜ", "downstep", TIER_COUNT, -1, NULL, 3, {1,  NAN}, NULL, 1  },
    { 0x2197, "↗", "global_up",   TIER_COUNT, -1, NULL, 4, {NAN, 1}, NULL, 1  },
    { 0x2198, "↘", "global_down", TIER_COUNT, -1, NULL, 4, {NAN, -1}, NULL, 1  },
    /* --- pitch contour marks (diacritics) — no articulatory effect --- */
    { 0x1DC4, "◌᷄", "pitch_midrise",  TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x1DC5, "◌᷅", "pitch_midfall",  TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x1DC6, "◌᷆", "pitch_highfall", TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x1DC7, "◌᷇", "pitch_highrise", TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x1DC8, "◌᷈", "pitch_risefall", TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x1DC9, "◌᷉", "pitch_fallrise", TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    /* --- undertie (linking) — ignored --- */
    { 0x203F, "‿",   "link",     TIER_COUNT,     -1, NULL, 0, {0,0} , NULL, 1  },
    /* --- superscript digits (pitch levels, e.g. ⁵²); ignored --- */
    { 0x2070, "⁰", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x00B9, "¹", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x00B2, "²", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x00B3, "³", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x2074, "⁴", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x2075, "⁵", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x2076, "⁶", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x2077, "⁷", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x2078, "⁸", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
    { 0x2079, "⁹", "pitch",     TIER_COUNT, -1, NULL, 0, {0,0} , NULL, 1  },
};
#define NMODS ((int)(sizeof(MODS) / sizeof(MODS[0])))

static const ModRec *find_mod(unsigned long cp)
{
    for (int i = 0; i < NMODS; i++)
        if (MODS[i].cp == cp)
            return &MODS[i];
    return NULL;
}

static IPA2VEC_MAYBE_UNUSED int is_ligature_cp (unsigned long cp)
{
    return cp == 0x035C || cp == 0x0360 || cp == 0x0361;
}

/* ------------------------------------------------------------------ */
/* Precomposed characters (canonical decomposition)                    */
/* ------------------------------------------------------------------ */

typedef struct {
    unsigned long pre;
    unsigned long base;
    unsigned long mods[4];
    int nmods;
} PrecompEntry;

static const PrecompEntry PRECOMPOSED[] = {
    { 0x00E3, 0x0061, { 0x0303 }, 1 },   /* ã = a + ◌̃ */
    { 0x1EBD, 0x0065, { 0x0303 }, 1 },   /* ẽ */
    { 0x0129, 0x0069, { 0x0303 }, 1 },   /* ĩ */
    { 0x00F5, 0x006F, { 0x0303 }, 1 },   /* õ */
    { 0x0169, 0x0075, { 0x0303 }, 1 },   /* ũ */
    { 0x1EF9, 0x0079, { 0x0303 }, 1 },   /* ỹ */
    { 0x1EA1, 0x0061, { 0x0323 }, 1 },   /* ạ = a + ◌̣ */
    { 0x1EB9, 0x0065, { 0x0323 }, 1 },   /* ẹ */
    { 0x1ECD, 0x006F, { 0x0323 }, 1 },   /* ọ */
    { 0x1EE9, 0x0075, { 0x0323 }, 1 },   /* ụ */
    /* precomposed vowels with pitch/tone diacritics -> base + tone mark */
    { 0x00E9, 0x0065, { 0x0301 }, 1 },   /* é = e + ◌́ (high tone) */
    { 0x00E8, 0x0065, { 0x0300 }, 1 },   /* è = e + ◌̀ (low tone) */
    { 0x00EA, 0x0065, { 0x0302 }, 1 },   /* ê = e + ◌̂ (falling tone) */
    { 0x011B, 0x0065, { 0x030C }, 1 },   /* ě = e + ◌̌ (rising tone) */
    { 0x0205, 0x0065, { 0x030F }, 1 },   /* ȅ = e + ◌̏ (extra-low tone) */
    { 0x0113, 0x0065, { 0x0304 }, 1 },   /* ē = e + ◌̄ (macron = level tone) */
    { 0x0101, 0x0061, { 0x0304 }, 1 },   /* ā = a + ◌̄ */
    { 0x014D, 0x006F, { 0x0304 }, 1 },   /* ō = o + ◌̄ */
    { 0x012B, 0x0069, { 0x0304 }, 1 },   /* ī = i + ◌̄ */
    { 0x016B, 0x0075, { 0x0304 }, 1 },   /* ū = u + ◌̄ */
    { 0x0101, 0x0061, { 0 }, 0 },        /* ā = a + macron */
    { 0x014D, 0x006F, { 0 }, 0 },        /* ō = o + macron */
};
#define NPRECOMP ((int)(sizeof(PRECOMPOSED) / sizeof(PRECOMPOSED[0])))

static const PrecompEntry *lookup_precomposed(unsigned long cp)
{
    for (int i = 0; i < NPRECOMP; i++)
        if (PRECOMPOSED[i].pre == cp)
            return &PRECOMPOSED[i];
    return NULL;
}

/* ------------------------------------------------------------------ */
/* IR tokens (two layers)                                              */
/* ------------------------------------------------------------------ */

typedef enum { TK_BASE, TK_MOD, TK_LIG } TokKind;

typedef struct {
    TokKind kind;
    const char *ipa;      /* printed form (base spelling or combining mark) */
    const char *latin;    /* transliteration */
    Tier tier;            /* TK_MOD only */
    const ModRec *mod;    /* TK_MOD only */
    const SegEntry *seg;  /* TK_BASE only */
    int consumed;         /* bytes consumed from input (TK_BASE) */
    /* tone data collected for the segment (filled on the TK_BASE token) */
    int tkind[5];         /* per-group kind: 0 none, 1 contour, 2 class, 3 step, 4 global */
    double tone[5][3];    /* group values; NAN = unknown placeholder */
    int preposed;         /* TK_MOD only: modifier appeared BEFORE the base */
} IrTok;

#define MAX_TOKS 256
#define MAX_SEGS 128

typedef struct {
    IrTok layer1[MAX_TOKS];   /* character-composition order */
    int n1;
    IrTok layer2[MAX_TOKS];   /* natural-language (feature tier) order */
    int n2;
    SegVec segs[MAX_SEGS];    /* one final vector per segment, in order */
    int nsegs;
} ParseOut;

/* ------------------------------------------------------------------ */
/* Deprecated / non-standard symbols (Unicode) -> modern IPA string.   */
/* Applied at the start of a segment (before base matching).           */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/* Deprecated / non-standard / regional symbols, organised into        */
/* modules by tradition (Americanist, Slavicist, Sinologist,           */
/* Indologist, Koreanologist, Japanologist, Africanist, OED, generic). */
/* Each module is an Alias array; lookup_alias scans all modules.      */
/* ------------------------------------------------------------------ */

typedef struct { const char *sym; const char *repl; const char *note; int need_mods; int warn; } Alias;
/* need_mods: 0 = always, 1 = only when followed by combining marks/modifiers,
 * -1 = only when NOT followed by combining marks.
 * warn: 1 = deprecated/ambiguous usage; print a warning when used. */

/* --- module: generic (any tradition) --- */
static const Alias ALIAS_GENERIC[] = {
    { "?",   "\xCA\x94", "glottal stop", 0, 0   },
    { "\xD1\x8F", "\xCA\xA2", "vd epiglottal trill (Cyrillic ya)", 0, 0   },       /* я -> ʢ */
    { "\xE2\x88\x85", "", "null initial (no sound)", 0, 0   },                     /* ∅ */
    { "\xC3\x98", "", "null initial (no sound)", 0, 0   },                         /* Ø */
    { "\xC8\xB7", "j", "dotless j", 0, 0  },                                       /* ȷ */
    { "\xC9\xAB", "l\xCB\xA0", "velarised l (dark l)", 0, 0   },                   /* ɫ -> lˠ */
    { "\xC4\xB1", "i",  "dotless i (dot-free form of i)", 1, 0  },
    { "\xC4\xB1", "\xC9\xAA", "dotless i (obsolete: near-close)", -1, 1  },
    /* small-capital letter bases (historical/alternative glyphs, U+1D00 block) */
    { "\xE1\xB4\x81", "\xC3\xA6", "small cap AE -> æ", 0, 0   },
    { "\xE1\xB4\x8A", "j", "small cap J -> j", 0, 0   },
    { "\xE1\xB4\x8B", "k", "small cap K -> k", 0, 0   },
    { "\xE1\xB4\x8D", "m", "small cap M -> m", 0, 0   },
    { "\xE1\xB4\x8F", "o", "small cap O -> o", 0, 0   },
    { "\xE1\xB4\x90", "\xC9\x94", "small cap open O -> ɔ", 0, 0   },
    { "\xE1\xB4\x98", "p", "small cap P -> p", 0, 0   },
    { "\xE1\xB4\x9B", "t", "small cap T -> t", 0, 0   },
    { "\xE1\xB4\x9C", "u", "small cap U -> u", 0, 0   },
    { "\xE1\xB4\xA0", "v", "small cap V -> v", 0, 0   },
    { "\xE1\xB4\xA1", "w", "small cap W -> w", 0, 0   },
    { "\xE1\xB4\xA2", "z", "small cap Z -> z", 0, 0   },
    { "\xE1\xB4\xA4", "\xCA\x95", "voiced laryngeal spirant -> ʕ", 0, 0   },
    { "\xE1\xB4\xA5", "\xCA\x95", "ain -> ʕ", 0, 0   },
    { "\xE1\xB4\xA6", "\xC9\xA3", "small cap gamma -> ɣ", 0, 0   },
};

/* --- module: withdrawn / obsolete IPA symbols --- */
static const Alias ALIAS_WITHDRAWN[] = {
    { "\xC6\x8D", "z\xCA\xB7", "labialized vd alveolo-dental fricative", 0, 0   },  /* ƍ -> zʷ */
    { "\xC3\xB3", "s\xCA\xB7", "labialized vl alveolo-dental fricative", 0, 0   },  /* σ -> sʷ */
    { "\xC6\xBA", "ʒ\xCA\xB7", "labialized vd postalveolar fricative", 0, 0   },    /* ƺ -> ʒʷ */
    { "\xC6\xAA", "ʃ\xCA\xB7", "labialized vl postalveolar fricative", 0, 0   },    /* ƪ -> ʃʷ */
    { "\xC6\xBB", "d\xCD\xA1z", "vd alveolar affricate (withdrawn 1976)", 0, 0   }, /* ƻ -> d͡z */
    { "\xC6\xBE", "t\xCD\xA1s", "vl alveolar affricate (withdrawn 1976)", 0, 0   }, /* ƾ -> t͡s */
    { "\xCA\xA6", "t\xCD\xA1s", "vl alveolar affricate (ligature)", 0, 0   },       /* ʦ */
    { "\xCA\xA3", "d\xCD\xA1z", "vd alveolar affricate (ligature)", 0, 0   },       /* ʣ */
    { "\xCA\xA7", "t\xCD\xA1ʃ", "vl postalveolar affricate (ligature)", 0, 0   },   /* ʧ */
    { "\xCA\xA4", "d\xCD\xA1ʒ", "vd postalveolar affricate (ligature)", 0, 0   },   /* ʤ */
    { "\xCA\xA8", "t\xCD\xA1ɕ", "vl alveolo-palatal affricate (ligature)", 0, 0   },/* ʨ */
    { "\xCA\xA5", "d\xCD\xA1ʑ", "vd alveolo-palatal affricate (ligature)", 0, 0   },/* ʥ */
    { "\xCA\x87", "\xC7\x80", "dental click (superseded 1989)", 0, 0   },           /* ʇ -> ǀ */
    { "\xCA\x97", "\xC7\x83", "alveolar click (superseded 1989)", 0, 0   },         /* ʗ -> ǃ */
    { "\xCA\x96", "\xC7\x81", "alveolar lateral click (superseded 1989)", 0, 0   }, /* ʖ -> ǁ */
    { "\xCA\x9E", "\xC7\x83", "velar click (withdrawn)", 0, 1   },                  /* ʞ -> ǃ */
    { "\xC6\xA5", "\xC9\x93\xCC\xA5", "vl bilabial implosive (withdrawn 1993)", 0, 0   },  /* ƥ -> ɓ̥ */
    { "\xC6\xAD", "\xC9\x97\xCC\xA5", "vl dental/alveolar implosive (withdrawn 1993)", 0, 0 }, /* ƭ -> ɗ̥ */
    { "\xC6\x88", "\xC9\x84\xCC\x8A", "vl palatal implosive (withdrawn 1993)", 0, 0   },    /* ƈ -> ʄ̊ */
    { "\xC6\x99", "\xC9\xA0\xCC\xA5", "vl velar implosive (withdrawn 1993)", 0, 0   },      /* ƙ -> ɠ̥ */
    { "\xCA\xA0", "\xC9\x9B\xCC\xA5", "vl uvular implosive (withdrawn 1993)", 0, 0   },     /* ʠ -> ʛ̥ */
    { "\xC6\x9E", "n\xCC\xA9", "syllabic n (withdrawn 1976)", 0, 0   },              /* ƞ -> n̩ */
    { "\xC6\xAB", "t\xCA\xB2", "palatalized t (withdrawn 1989)", 0, 0   },           /* ƫ -> tʲ */
    { "\xCA\x93", "\xCA\x91", "vd alveolo-palatal fricative (withdrawn 1989)", 0, 0   }, /* ʓ -> ʑ */
    { "\xCA\x86", "\xC9\x95", "vl alveolo-palatal fricative (withdrawn 1989)", 0, 0   },  /* ʆ -> ɕ */
    { "\xC9\xBC", "r\xCC\x9D", "vd strident apico-alveolar trill (withdrawn 1989)", 0, 0   }, /* ɼ -> r̝ */
    { "\xC9\xA9", "\xC9\xAA", "near-close near-front unrounded vowel (rejected)", 0, 0   }, /* ɩ -> ɪ */
    { "\xCA\x9A", "\xC9\x9E", "open-mid central rounded vowel (misprint)", 0, 0   }, /* ʚ -> ɞ */
    { "\xC9\xB7", "\xCA\x8A", "near-close near-back rounded vowel (rejected)", 0, 0   },   /* ɷ -> ʊ */
    { "\xCF\x89", "\xCA\x8A\xCC\x9C", "near-close near-back unrounded vowel", 0, 0   },    /* ω -> ʊ̜ */
    { "\xC8\xA3", "\xC9\xA4", "close-mid back unrounded vowel (mistake)", 0, 0   },  /* ȣ -> ɤ */
};

/* --- module: Americanist / Slavicist --- */
static const Alias ALIAS_AMERICANIST[] = {
    { "\xC5\xA1", "\xCA\x83", "postalveolar", 0, 0   },                              /* š -> ʃ */
    { "\xC4\x8D", "t\xCD\xA1\xCA\x83", "postalveolar affricate", 0, 0   },           /* č -> t͡ʃ */
    { "\xC5\xBE", "\xCA\x92", "postalveolar", 0, 0   },                              /* ž -> ʒ */
    { "\xC7\xB0", "d\xCD\xA1\xCA\x92", "vd postalveolar affricate", 0, 0   },        /* ǰ -> d͡ʒ */
    { "\xC7\xA7", "d\xCD\xA1\xCA\x92", "vd postalveolar affricate", 0, 0   },        /* ǧ -> d͡ʒ */
    { "\xC7\xAF", "d\xCD\xA1\xCA\x92", "vd postalveolar affricate", 0, 0   },        /* ǯ -> d͡ʒ */
    { "\xE1\xBA\x8B", "\xCF\x87", "vl uvular fricative", 0, 0   },                   /* ẋ -> χ */
    { "\xC6\x9B", "t\xCD\xA1\xC9\xAC", "vl alveolar lateral affricate", 0, 0   },    /* ƛ -> t͡ɬ */
    { "\xC5\x82", "\xC9\xAC", "vl alveolar lateral fricative", 0, 0   },             /* ł -> ɬ */
    { "\xCE\xBB", "d\xCD\xA1\xC9\xAE", "vd alveolar lateral affricate", 0, 0   },    /* λ -> d͡ɮ */
};

/* --- module: Sinologist (Chinese linguistics) --- */
static const Alias ALIAS_SINOLOGIST[] = {
    { "\xC9\xBF", "z\xCC\xA9", "apical dental unrounded vowel", 0, 0   },            /* ɿ -> z̩ */
    { "\xCA\x85", "\xCA\x90\xCC\xA9", "apical retroflex unrounded vowel", 0, 0   },  /* ʅ -> ʐ̩ */
    { "\xCA\xAE", "z\xCC\xA9\xCA\xB7", "apical dental rounded vowel", 0, 0   },      /* ʮ -> z̩ʷ */
    { "\xCA\xAF", "\xCA\x90\xCC\xA9\xCA\xB7", "apical retroflex rounded vowel", 0, 0   }, /* ʯ -> ʐ̩ʷ */
    { "\xE1\xB4\x80", "a\xCC\x88", "open central vowel", 0, 0   },                   /* ᴀ -> ä */
    { "\xC8\xA1", "\xC9\x9F", "vd alveolo-palatal stop", 0, 0   },                   /* ȡ -> ɟ */
    { "\xC8\xB6", "c", "vl alveolo-palatal stop", 0, 0   },                          /* ȶ -> c */
    { "\xC8\xB5", "\xC9\xB2", "vd alveolo-palatal nasal", 0, 0   },                  /* ȵ -> ɲ */
    { "\xC8\xB4", "\xCA\x8E", "vd alveolo-palatal lateral", 0, 0   },                /* ȴ -> ʎ */
};

/* --- module: Indologist / Semiticist (dotted letters) --- */
static const Alias ALIAS_INDOLOGIST[] = {
    { "\xE1\xB8\x8D", "\xC9\x96", "retroflex stop (d-dot-below)", 0, 0   },                /* ḍ -> ɖ */
    { "\xE1\xB9\xAD", "\xCA\x88", "retroflex stop (t-dot-below)", 0, 0   },                /* ṭ -> ʈ */
    { "\xE1\xB9\x87", "\xC9\xB3", "retroflex nasal (n-dot-below)", 0, 0   },               /* ṇ -> ɳ */
    { "\xE1\xB9\x9B", "\xC9\xBD", "retroflex tap (r-dot-below)", 0, 0   },                 /* ṛ -> ɽ */
    { "\xE1\xB8\xB7", "\xC9\xAD", "retroflex lateral (l-dot-below)", 0, 0   },             /* ḷ -> ɭ */
    { "\xE1\xB9\xA3", "\xCA\x82", "retroflex fricative (s-dot-below)", 0, 0   },           /* ṣ -> ʂ */
    { "\xC5\x9B", "\xC9\x95", "alveolo-palatal fricative (s-acute)", 0, 0   },         /* ś -> ɕ */
    { "\xE1\xB9\x83", "m\xCC\xA9", "syllabic nasal (m-dot-below)", 0, 0   },               /* ṃ -> m̩ */
    { "\xE1\xB9\x85", "\xC5\x8B", "velar nasal (n-dot-above)", 0, 0   },                   /* ṅ -> ŋ */
    { "\xC3\xB1", "\xC9\xB2", "palatal nasal (ñ)", 0, 0   },                           /* ñ -> ɲ */
    { "\xE1\xB8\xA5", "h", "voiceless glottal fricative (h-dot-below)", 0, 0   },          /* ḥ -> h */
    { "\xE1\xB8\xAB", "x", "voiceless velar fricative (h-breve-below)", 0, 0   },          /* ḫ -> x */
    { "\xE1\xBA\x93", "\xCA\x90", "retroflex fricative (z-dot-below)", 0, 0   },           /* ẓ -> ʐ */
    { "\xE1\xBA\x96", "\xC4\xA7", "voiceless pharyngeal fricative (h-line-below)", 0, 0   }, /* ẖ -> ħ */
    /* Semiticist line-below letters */
    { "\xE1\xB8\x8F", "\xC3\xB0", "voiced dental fricative (d-line-below)", 0, 0   },     /* ḏ -> ð */
    { "\xE1\xB9\xAF", "\xC3\xB8", "voiceless dental fricative (t-line-below)", 0, 0   },  /* ṯ -> θ */
    { "\xC4\xA1", "\xC9\xA3", "voiced velar fricative (g-dot-above)", 0, 0   },        /* ġ -> ɣ */
    { "\xE1\xB8\xA1", "\xC9\xA3", "voiced velar fricative (g-macron)", 0, 0   },           /* ḡ -> ɣ */
    /* Dravidian */
    { "\xE1\xB8\xBB", "\xC9\xAD", "retroflex lateral (l-dot-below-macron)", 0, 0   },     /* ḻ -> ɭ */
    { "\xE1\xB9\x9F", "r", "alveolar trill (r-dot-above)", 0, 0   },                       /* ṟ -> r */
    { "\xE1\xB9\x81", "m\xCC\x83", "anusvara (m-dot-above) -> nasalised m", 0, 0   },      /* ṁ -> m̃ */
};

/* --- module: Polish / Czech (acute letters) --- */
static const Alias ALIAS_POLISH[] = {
    { "\xC5\xBA", "\xCA\x91", "alveolo-palatal fricative (z-acute)", 0, 0   },         /* ź -> ʑ */
    { "\xC4\x87", "t\xCD\xA1\xC9\x95", "alveolo-palatal affricate (c-acute)", 0, 0   }, /* ć -> t͡ɕ */
    { "\xC5\xBC", "\xCA\x90", "retroflex fricative (z-dot-above)", 0, 0   },           /* ż -> ʐ */
};

/* --- module: Teuthonista / UPA (German dialectology, Uralic) --- */
static const Alias ALIAS_TEUTHONISTA[] = {
    { "\xC6\x80", "\xCE\xB2", "voiced bilabial fricative (b-stroke)", 0, 0   },        /* ƀ -> β */
    { "\xC4\x91", "\xC3\xB0", "voiced dental fricative (d-stroke)", 0, 0   },          /* đ -> ð */
    { "\xC7\xA5", "\xC9\xA3", "voiced velar fricative (g-stroke)", 0, 0   },           /* ǥ -> ɣ */
    { "\xC7\xA9", "c", "palatal plosive (k-caron, UPA)", 0, 0   },                     /* ǩ -> c */
    { "\xC8\x9F", "x", "voiceless velar fricative (h-caron, UPA)", 0, 0   },           /* ȟ -> x */
    { "\xC7\xB5", "\xC9\x9F", "palatal plosive (g-acute, UPA)", 0, 0   },              /* ǵ -> ɟ */
};

/* --- module: Koreanologist --- */
static const Alias ALIAS_KOREANOLOGIST[] = {
    { "\xC6\x8E", "\xC9\xA4", "close-mid near-back unrounded vowel", 0, 0   },       /* Ǝ -> ɤ */
    { "K", "k", "fortis k", 0, 1   },
    { "P", "p", "fortis p", 0, 1   },
    { "T", "t", "fortis t", 0, 1   },
};

/* --- module: Japanologist --- */
static const Alias ALIAS_JAPANOLOGIST[] = {
    { "Q", "\xCB\x90", "gemination (sokuon)", 0, 1   },                             /* Q -> ː */
    { "N", "n\xCC\xA9", "syllabic nasal (Japanese hatsuon)", 0, 0   },              /* N -> n̩ */
};

/* --- module: uppercase letters with an explicitly listed value.
 * No shape-based extrapolation — only symbols listed in the reference
 * table are mapped. --- */
static const Alias ALIAS_UPPERCASE[] = {
    { "G",   "\xC9\xA2", "uppercase for voiced uvular plosive", 0, 0   },            /* G -> ɢ */
    { "R",   "\xCA\x80", "uppercase for voiced uvular trill", 0, 0   },               /* R -> ʀ */
    { "\xC5\x92", "\xC9\xB6", "uppercase for open front rounded vowel", 0, 0   },    /* Œ -> ɶ */
};

/* --- module: Africanist --- */
static const Alias ALIAS_AFRICANIST[] = {
    { "\xC8\xB9", "p\xCC\xAA", "vl labiodental plosive", 0, 0   },                   /* ȹ -> p̪ */
    { "\xC8\xB8", "p\xCC\xAA\xCC\xAC", "vd labiodental plosive", 0, 0   },           /* ȸ -> p̪+◌̬ */
};

/* --- module: OED / dictionary conventions --- */
static const Alias ALIAS_OED[] = {
    { "\xE1\xB5\xBB", "\xC9\xA8\xCC\x9E", "near-close central unrounded vowel", 0, 0   }, /* ᵻ -> ɨ̞ */
    { "\xE1\xB5\xBF", "\xCA\x89\xCC\x9E", "near-close central rounded vowel", 0, 0   },   /* ᵿ -> ʉ̞ */
};

/* module registry */
typedef struct { const Alias *tab; int n; const char *name; } AliasModule;

static const AliasModule ALIAS_MODULES[] = {
    { ALIAS_GENERIC,     (int)(sizeof(ALIAS_GENERIC)     / sizeof(Alias)), "generic" },
    { ALIAS_WITHDRAWN,   (int)(sizeof(ALIAS_WITHDRAWN)   / sizeof(Alias)), "withdrawn" },
    { ALIAS_AMERICANIST, (int)(sizeof(ALIAS_AMERICANIST) / sizeof(Alias)), "americanist" },
    { ALIAS_SINOLOGIST,  (int)(sizeof(ALIAS_SINOLOGIST)  / sizeof(Alias)), "sinologist" },
    { ALIAS_INDOLOGIST,  (int)(sizeof(ALIAS_INDOLOGIST)  / sizeof(Alias)), "indologist" },
    { ALIAS_POLISH,      (int)(sizeof(ALIAS_POLISH)      / sizeof(Alias)), "polish" },
    { ALIAS_TEUTHONISTA, (int)(sizeof(ALIAS_TEUTHONISTA) / sizeof(Alias)), "teuthonista" },
    { ALIAS_KOREANOLOGIST,(int)(sizeof(ALIAS_KOREANOLOGIST)/sizeof(Alias)), "koreanologist" },
    { ALIAS_JAPANOLOGIST,(int)(sizeof(ALIAS_JAPANOLOGIST)/sizeof(Alias)), "japanologist" },
    { ALIAS_AFRICANIST,  (int)(sizeof(ALIAS_AFRICANIST)  / sizeof(Alias)), "africanist" },
    { ALIAS_OED,         (int)(sizeof(ALIAS_OED)         / sizeof(Alias)), "oed" },
    { ALIAS_UPPERCASE,   (int)(sizeof(ALIAS_UPPERCASE)   / sizeof(Alias)), "uppercase" },
};
#define N_ALIAS_MODULES ((int)(sizeof(ALIAS_MODULES) / sizeof(ALIAS_MODULES[0])))

/* ------------------------------------------------------------------ */
/* Implicit (no-tie) affricates: two adjacent letters that form an     */
/* affricate by convention (IPA table "affricates" row).               */
/* tied != NULL: the tie-spelled form exists in the base table;        */
/* tied == NULL: synthesize via closure + release (ligature rule).     */
/* ------------------------------------------------------------------ */

typedef struct { const char *a; const char *b; const char *tied; } Nolig;

static const Nolig NOLIG[] = {
    { "p\u032A", "f", NULL },         /* p̪f  */
    { "t", "s", "\x74\xCD\xA1s" },    /* ts -> t͡s */
    { "d", "z", "\x64\xCD\xA1z" },    /* dz -> d͡z */
    { "t", "\u0283", "\x74\xCD\xA1\xCA\x83" }, /* tʃ -> t͡ʃ */
    { "d", "\u0292", "\x64\xCD\xA1\xCA\x92" }, /* dʒ -> d͡ʒ */
    { "t", "\u0255", "\x74\xCD\xA1\xCA\x95" }, /* tɕ -> t͡ɕ */
    { "d", "\u0291", "\x64\xCD\xA1\xCA\x91" }, /* dʑ -> d͡ʑ */
    { "\u0288", "\u0282", "\xCA\x88\xCD\xA1\xCA\x82" }, /* ʈʂ -> ʈ͡ʂ */
    { "\u0256", "\u0290", "\xC9\x96\xCD\xA1\xCA\x90" }, /* ɖʐ -> ɖ͡ʐ */
    { "t", "\u026C", NULL },          /* tɬ (synthesize) */
    { "d", "\u026E", NULL },          /* dɮ (synthesize) */
    { "c", "\u00E7", NULL },          /* cç (synthesize) */
    { "\u025F", "\u029D", NULL },     /* ɟʝ (synthesize) */
};
#define NNOLIG ((int)(sizeof(NOLIG) / sizeof(NOLIG[0])))

static const Alias *lookup_alias(const char *s, int has_mods)
{
    for (int m = 0; m < N_ALIAS_MODULES; m++) {
        for (int i = 0; i < ALIAS_MODULES[m].n; i++) {
            const Alias *a = &ALIAS_MODULES[m].tab[i];
            if (a->repl == NULL) continue;
            size_t L = strlen(a->sym);
            if (strncmp(s, a->sym, L) == 0) {
                if (a->need_mods == 1 && !has_mods) continue;
                if (a->need_mods == -1 && has_mods) continue;
                return a;
            }
        }
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* ExtIPA base segments not covered by IPA_VECTORS.md                  */
/* (clinical phonetics additions; vectors derived from the closest     */
/*  articulatory description)                                          */
/* ------------------------------------------------------------------ */

static const SegEntry EXTRA_BASE[] = {
    /* ᴇ U+1D07: unrounded mid central vowel (extIPA) ≈ ɘ */
    { "\xe1\xb4\x87", { 0.0, 0.0, 0.55, 0.25, 0.0, -0.1, 0.0, 0.0,
                         1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.7, 1.0 }, 0 },
    /* ɚ U+025A: rhotacised schwa */
    { "\xc9\x9a", { 0.0, 0.0, 0.55, 0.45, 0.0, 0.0, 0.0, 0.0,
                    1.0, 0.2, 0.0, 0.3, 1.0, 0.0, 0.65, 1.0 }, 0 },
    /* ɞ U+025E: open-mid central rounded vowel */
    { "\xc9\x9e", { 0.0, 1.0, 0.55, 0.25, 0.0, 0.1, 0.0, 0.0,
                    1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.85, 1.0 }, 0 },
    /* ɝ U+025D: rhotacised open-mid central vowel (extIPA) */
    { "\xc9\x9d", { 0.0, 0.0, 0.55, 0.35, 0.0, 0.1, 0.0, 0.0,
                    1.0, 0.2, 0.0, 0.5, 1.0, 0.0, 0.85, 1.0 }, 0 },
    /* ʬ U+02AC: bilabial percussive (extIPA) */
    { "\xca\xac", { 1.0, 0.0, 0.55, 0.25, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.4, 0.0, 0.1, 0.0, 0.0, 1.0 }, 0 },
    /* ʭ U+02AD: bidental percussive (extIPA) */
    { "\xca\xad", { 0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.4, 0.0, 0.1, 0.0, 0.0, 1.0 }, 0 },
    /* ʩ U+02A9: velopharyngeal fricative (extIPA) */
    { "\xca\xa9", { 0.0, 0.0, 0.55, 0.25, -0.5, 0.0, 0.5, 0.0,
                    0.0, 0.0, 0.4, 0.0, 0.6, 0.0, 0.09, 1.0 }, 0 },
    /* ʪ U+02AA: voiceless velar lateral fricative (extIPA) */
    { "\xca\xaa", { 0.0, 0.0, 0.55, 0.25, -0.5, 0.0, 0.0, 1.0,
                    0.0, 0.0, 0.4, 0.0, 0.9, 0.5, 0.08, 1.0 }, 0 },
    /* ʫ U+02AB: voiced velar lateral fricative (extIPA) */
    { "\xca\xab", { 0.0, 0.0, 0.55, 0.25, -0.5, 0.0, 0.0, 1.0,
                    1.0, 0.2, 0.0, 0.0, 0.8, 0.45, 0.08, 1.0 }, 0 },
    /* ꞎ U+A7AE: voiceless retroflex lateral fricative (IPA 2018) */
    { "\xea\x9e\xae", { 0.0, 0.0, 0.1, 0.8, 0.0, 0.0, 0.0, 1.0,
                        0.0, 0.0, 0.4, 0.0, 0.9, 0.5, 0.08, 1.0 }, 0 },
    /* ᶑ U+1D91: retroflex implosive (IPA 2018) */
    { "\xe1\xb6\x91", { 0.0, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0,
                        1.0, 0.55, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0 }, 2 },
};
#define N_EXTRA ((int)(sizeof(EXTRA_BASE) / sizeof(EXTRA_BASE[0])))

/* latin feature names for EXTRA_BASE (parallel array) */
static const char *EXTRA_NAMES[N_EXTRA] = {
    "cent.mid.unr.vwl",   /* ᴇ ≈ ɘ */
    "cent.mid.rnd.vwl",   /* ɚ rhotacised schwa */
    "cent.omid.rnd.vwl",  /* ɞ */
    "cent.omid.rhot.vwl", /* ɝ */
    "bil.percussive",     /* ʬ */
    "bidental.percussive",/* ʭ */
    "velophar.frc",       /* ʩ */
    "vel.lat.frc",        /* ʪ */
    "vel.lat.frc.vd",     /* ʫ */
    "rfl.lat.frc",        /* ꞎ */
    "rfl.imp",            /* ᶑ */
};

/* longest-prefix base lookup against the 132-entry table */
static const SegEntry *match_base(const char *s, int *consumed)
{
    int best = -1;
    const SegEntry *be = NULL;
    for (int i = 0; i < NSEG; i++) {
        size_t L = strlen(SEG_TABLE[i].ipa);
        if (strncmp(s, SEG_TABLE[i].ipa, L) == 0) {
            if ((int)L > best) { best = (int)L; be = &SEG_TABLE[i]; }
        }
    }
    if (consumed) *consumed = best;
    return be;
}

/* extended base lookup: SEG_TABLE first, then EXTRA_BASE */
static const SegEntry *match_base_ex(const char *s, int *consumed)
{
    const SegEntry *be = match_base(s, consumed);
    if (be) return be;
    for (int i = 0; i < N_EXTRA; i++) {
        size_t L = strlen(EXTRA_BASE[i].ipa);
        if (strncmp(s, EXTRA_BASE[i].ipa, L) == 0) {
            if (consumed) *consumed = (int)L;
            return &EXTRA_BASE[i];
        }
    }
    return NULL;
}

static IPA2VEC_MAYBE_UNUSED int lex_inner (const char *input, IrTok out[MAX_TOKS], int *nout, char *err, size_t errsz);

static IPA2VEC_MAYBE_UNUSED int lex (const char *input, IrTok out[MAX_TOKS], int *nout, char *err, size_t errsz)
{
    static int depth = 0;
    if (++depth > 8) { depth--; snprintf(err, errsz, "alias expansion too deep"); return -1; }
    int rc = lex_inner(input, out, nout, err, errsz);
    depth--;
    return rc;
}

static IPA2VEC_MAYBE_UNUSED int lex_inner (const char *input, IrTok out[MAX_TOKS], int *nout, char *err, size_t errsz)
{
    const unsigned char *p = (const unsigned char *)input;
    const unsigned char *end = p + strlen(input);
    int n = 0;

    while (p < end) {
        /* whitespace, syllable break '.', minor break '|', major break '‖',
         * and the undertie '‿' are all non-segmental separators */
        if (isspace(*p) || *p == '.' || *p == '|' ||
            (p + 2 < end && p[0] == 0xE2 && p[1] == 0x80 && p[2] == 0x96)) {
            p += (*p == 0xE2) ? 3 : 1;   /* ‖ is 3 bytes */
            continue;
        }

        /* preposed modifiers (airstream) and tone marks */
        int pre_idx[4], npre = 0;
        int pre_tone[4];     /* tone values collected preposed (5-level) */
        int npre_tone = 0;
        int pre_class_val = 0; int pre_class_set = 0;
        int pre_consumed = 0;   /* bytes consumed by preposed marks */
        while (p < end && pre_consumed < 16) {
            unsigned long cp;
            int k = utf8_decode(p, &cp);
            if (!k) break;
            const ModRec *m = find_mod(cp);
            if (!m) break;
            if (m->tone_kind != 0) {
                if (m->tone_kind == 1) {
                    if (npre_tone < 4) { pre_tone[npre_tone++] = (int)m->val[0]; p += k; pre_consumed += k; continue; }
                } else if (m->tone_kind == 2) {
                    pre_class_val = (int)m->val[0]; pre_class_set = 1; p += k; pre_consumed += k; continue;
                } else if (m->tone_kind == 3) {
                    p += k; pre_consumed += k; continue;  /* upstep/downstep preposed: skip (no base yet) */
                }
                break;
            }
            if (!is_ligature_cp(cp) && m->tier == TIER_AIRSTREAM) {
                pre_idx[npre] = (int)(m - MODS);
                npre++;
                p += k;
                pre_consumed += k;
            } else break;
        }

        /* base (or precomposed char expanded to base + combining marks) */
        int cons = 0;
        const SegEntry *base = match_base_ex((const char *)p, &cons);
        /* ASCII alias: Latin 'g' == IPA ɡ (U+0261) */
        if (!base && p[0] == 'g') {
            base = match_base_ex("\xc9\xa1", &cons);   /* ɡ in UTF-8 */
            if (base) {
                cons = 1;   /* consumed only the ASCII 'g' */
                fprintf(stderr, "ipa2vec: note: ASCII 'g' interpreted as IPA ɡ\n");
            }
        }
        unsigned long precomp_mods[4];
        int n_precomp = 0;
        if (!base) {
            unsigned long cp;
            int k = utf8_decode(p, &cp);
            if (k) {
                const PrecompEntry *pe = lookup_precomposed(cp);
                if (pe) {
                    char buf[8];
                    int nb = cp_to_utf8(pe->base, buf);
                    buf[nb] = 0;
                    base = match_base_ex(buf, &cons);
                    if (base) {
                        for (int i = 0; i < pe->nmods && i < 4; i++)
                            precomp_mods[n_precomp++] = pe->mods[i];
                        cons = k;   /* consume the whole precomposed char */
                    }
                }
            }
        }
        if (!base) {
            /* deprecated / non-standard symbol: parse its modern-IPA
             * replacement together with any following combining marks */
             size_t probe_len = 0;
            {
                const Alias *probe = NULL;
                for (int m = 0; m < N_ALIAS_MODULES && !probe; m++) {
                    for (int i = 0; i < ALIAS_MODULES[m].n; i++) {
                        const Alias *a = &ALIAS_MODULES[m].tab[i];
                        size_t L = strlen(a->sym);
                        if (a->repl && strncmp((const char*)p, a->sym, L) == 0) {
                            probe = a; probe_len = L; break;
                        }
                    }
                }
                (void)probe;
            }
            int has_mods = 0;
            {
                unsigned long cp;
                const unsigned char *q = p + probe_len;
                if (utf8_decode(q, &cp)) {
                    const ModRec *m = find_mod(cp);
                    has_mods = (m != NULL);
                }
            }
            const Alias *al = lookup_alias((const char *)p, has_mods);
            if (al) {
                size_t alen = strlen(al->sym);
                char buf[256];
                snprintf(buf, sizeof(buf), "%s", al->repl);
                size_t blen = strlen(buf);
                /* append following combining marks / modifier letters so
                 * e.g. "ı̤̃ˤ" is parsed as one segment with its mods */
                const unsigned char *q = p + alen;
                while (q < end && blen + 8 < sizeof(buf)) {
                    unsigned long cp;
                    int k = utf8_decode(q, &cp);
                    if (!k) break;
                    const ModRec *m = find_mod(cp);
                    if (m && m->tone_kind == 0 && !is_ligature_cp(cp)) {
                        memcpy(buf + blen, q, (size_t)k);
                        blen += (size_t)k;
                        buf[blen] = 0;
                        q += k;
                    } else break;
                }
                IrTok tmp[MAX_TOKS];
                int tn = 0;
                char terr[256];
                if (lex(buf, tmp, &tn, terr, sizeof(terr)) == 0) {
                    fprintf(stderr, "ipa2vec: %s: '%s' -> %s (%s)\n",
                            al->warn ? "warning" : "note",
                            al->sym, al->repl, al->note);
                    if (n + tn >= MAX_TOKS) goto full;
                    for (int j = 0; j < tn; j++)
                        out[n++] = tmp[j];
                    p = q;   /* consume alias + appended combining marks */
                    continue;
                }
            }
            /* alias replacement failed to lex (e.g. it is a bare modifier);
             * report clearly */
            {
                const Alias *fal = lookup_alias((const char *)p, 0);
                if (fal) {
                    snprintf(err, errsz,
                             "'%s' (%s) needs a base segment to attach to",
                             fal->sym, fal->note);
                    return -1;
                }
            }
            unsigned long cp = 0;
            utf8_decode(p, &cp);
            if (pre_consumed > 0) {
                /* consumed only modifiers/tone marks with no base following */
                p -= pre_consumed;
                utf8_decode(p, &cp);
                snprintf(err, errsz,
                         "modifier-only at offset %d (U+%04lX): a base segment is required first",
                         (int)(p - (const unsigned char*)input), cp);
                return -1;
            }
            const ModRec *m0 = find_mod(cp);
            if (m0 && m0->apply == NULL) {
                snprintf(err, errsz,
                         "modifier-only at offset %d (U+%04lX): a base segment is required first",
                         (int)(p - (const unsigned char*)input), cp);
                return -1;
            }
            snprintf(err, errsz, "unknown segment at offset %d: U+%04lX",
                     (int)(p - (const unsigned char*)input), cp);
            return -1;
        }
        /* implicit (no-tie) affricate: base + following letter.
         * If tied form exists in table, swap base; else remember to emit
         * tie + release right after the closure base token. */
        int synth_rel = 0;
        int synth_rel_len = 0;
        {
            const Nolig *nl = NULL;
            for (int i = 0; i < NNOLIG; i++) {
                if (strcmp(base->ipa, NOLIG[i].a) == 0 &&
                    strncmp((const char *)p + cons, NOLIG[i].b, strlen(NOLIG[i].b)) == 0) {
                    nl = &NOLIG[i];
                    break;
                }
            }
            if (nl) {
                if (nl->tied) {
                    int c2 = 0;
                    const SegEntry *t = match_base_ex(nl->tied, &c2);
                    if (t) {
                        fprintf(stderr, "ipa2vec: note: inferred tie: '%s%s' -> '%s'\n",
                                nl->a, nl->b, nl->tied);
                        base = t;
                        cons = (int)strlen(nl->a) + (int)strlen(nl->b);
                    }
                } else {
                    synth_rel = 1;
                    synth_rel_len = (int)strlen(nl->b);
                }
            }
        }
        /* record the base token with its preposed modifiers in order */
        for (int i = 0; i < npre; i++) {
            if (n >= MAX_TOKS) goto full;
            IrTok t;
            t.kind = TK_MOD;
            t.preposed = 0;
            t.ipa = MODS[pre_idx[i]].ipa;
            t.latin = MODS[pre_idx[i]].latin;
            t.tier = MODS[pre_idx[i]].tier;
            t.mod = &MODS[pre_idx[i]];
            t.seg = NULL;
            t.consumed = 0;
            t.preposed = 1;
            out[n++] = t;
        }
        if (n >= MAX_TOKS) goto full;
        IrTok t;
        t.kind = TK_BASE;
        t.preposed = 0;
        t.ipa = base->ipa;
        t.latin = (base >= SEG_TABLE && base < SEG_TABLE + NSEG)
                  ? NAME_TABLE[base - SEG_TABLE]
                  : EXTRA_NAMES[base - EXTRA_BASE];
        t.tier = TIER_COUNT;
        t.mod = NULL;
        t.seg = base;
        t.consumed = cons;
        for (int g = 0; g < 5; g++) { t.tkind[g] = 0; t.tone[g][0] = t.tone[g][1] = t.tone[g][2] = NAN; }
        out[n++] = t;
        p += cons;

        /* synthesized implicit affricate: emit tie + release base */
        if (synth_rel) {
            const SegEntry *rel = match_base_ex((const char *)p, &synth_rel_len);
            if (rel) {
                fprintf(stderr, "ipa2vec: note: inferred affricate with synthesized tie (closure + release)\n");
                if (n >= MAX_TOKS) goto full;
                IrTok lt;
                lt.kind = TK_LIG;
                lt.preposed = 0;
                lt.ipa = "◌͡";
                lt.latin = "tie";
                lt.tier = TIER_COUNT;
                lt.mod = NULL;
                lt.seg = NULL;
                lt.consumed = 0;
                out[n++] = lt;
                if (n >= MAX_TOKS) goto full;
                IrTok rt;
                rt.kind = TK_BASE;
                rt.preposed = 0;
                rt.ipa = rel->ipa;
                rt.latin = (rel >= SEG_TABLE && rel < SEG_TABLE + NSEG)
                           ? NAME_TABLE[rel - SEG_TABLE]
                           : EXTRA_NAMES[rel - EXTRA_BASE];
                rt.tier = TIER_COUNT;
                rt.mod = NULL;
                rt.seg = rel;
                rt.consumed = synth_rel_len;
                for (int g = 0; g < 5; g++) { rt.tkind[g] = 0; rt.tone[g][0] = rt.tone[g][1] = rt.tone[g][2] = NAN; }
                out[n++] = rt;
                p += synth_rel_len;
            }
        }

        /* tone bookkeeping for this segment: 5-level letters collected here,
         * then grouped on segment end. */
        int tonebuf[8], ntone = 0;
        for (int i = 0; i < npre_tone; i++) tonebuf[ntone++] = pre_tone[i];
        if (pre_class_set) {
            /* Chinese tone class preposed -> group 5 */
            out[n-1].tkind[4] = 2;
            out[n-1].tone[4][0] = pre_class_val;
            out[n-1].tone[4][1] = NAN;
        }

        /* precomposed combining marks: emit as postposed modifier tokens
         * (character-composition layer keeps the decomposed order) */
        for (int i = 0; i < n_precomp; i++) {
            const ModRec *m = find_mod(precomp_mods[i]);
            if (!m) continue;
            if (n >= MAX_TOKS) goto full;
            IrTok t;
            t.kind = TK_MOD;
            t.preposed = 0;
            t.ipa = m->ipa;
            t.latin = m->latin;
            t.tier = m->tier;
            t.mod = m;
            t.seg = NULL;
            t.consumed = 0;
            out[n++] = t;
        }

        /* postposed modifiers & ligatures */
        while (p < end) {
            unsigned long cp;
            int k = utf8_decode(p, &cp);
            if (!k) break;
            const ModRec *m = find_mod(cp);
            if (!m) break;
            /* airstream-prefix modifiers (ˀ glottal onset, ᵑ nasal click
             * release) are preposed by convention: if they appear after a
             * base, stop and let the next segment collect them.  Ejective
             * ʼ (air >= 0) stays postposed. */
            if (m->tier == TIER_AIRSTREAM && m->air < 0 && !is_ligature_cp(cp))
                break;
            if (m->tone_kind != 0) {
                /* tone mark: store into segment tone state */
                if (m->tone_kind == 1) {           /* 5-level letter */
                    if (ntone < 8) tonebuf[ntone++] = (int)m->val[0];
                } else if (m->tone_kind == 2) {    /* Chinese tone class -> group 5 */
                    out[n-1].tkind[4] = 2;
                    out[n-1].tone[4][0] = m->val[0];
                    out[n-1].tone[4][1] = NAN;
                } else if (m->tone_kind == 3) {    /* upstep/downstep -> group 4 */
                    out[n-1].tkind[3] = 3;
                    out[n-1].tone[3][0] = m->val[0];
                    out[n-1].tone[3][1] = NAN;
                } else {                            /* global rise/fall -> group 4 */
                    out[n-1].tkind[3] = 4;
                    out[n-1].tone[3][0] = NAN;
                    out[n-1].tone[3][1] = m->val[1];
                }
                p += k;
                continue;
            }
            if (is_ligature_cp(cp)) {
                /* tie: next must be a base */
                p += k;
                int c2 = 0;
                const SegEntry *b2 = match_base_ex((const char *)p, &c2);
                if (!b2) {
                    snprintf(err, errsz, "ligature tie without second segment at offset %d",
                             (int)(p - (const unsigned char*)input));
                    return -1;
                }
                IrTok l;
                l.kind = TK_LIG;
                l.ipa = "◌͡";
                l.latin = "tie";
                l.tier = TIER_COUNT;
                l.mod = m;
                l.seg = NULL;
                l.consumed = 0;
                out[n++] = l;      /* Layer1 keeps the tie for round-trip */
                IrTok r;
                r.kind = TK_BASE;
                r.preposed = 0;
                r.ipa = b2->ipa;
                r.latin = (b2 >= SEG_TABLE && b2 < SEG_TABLE + NSEG)
                          ? NAME_TABLE[b2 - SEG_TABLE]
                          : EXTRA_NAMES[b2 - EXTRA_BASE];
                r.tier = TIER_COUNT;
                r.mod = NULL;
                r.seg = b2;
                r.consumed = c2;
                out[n++] = r;
                p += c2;
                continue;
            }
            if (n >= MAX_TOKS) goto full;
            IrTok t;
            t.kind = TK_MOD;
            t.preposed = 0;
            t.ipa = m->ipa;
            t.latin = m->latin;
            t.tier = m->tier;
            t.mod = m;
            t.seg = NULL;
            t.consumed = 0;
            out[n++] = t;
            p += k;
        }

        /* flush 5-level tone letters into groups (single tone / tone sandhi):
         *   1 letter  -> (a)              level tone
         *   2 letters -> (a,b)            single tone
         *   3 letters -> (a,b,c)          single tone, 3-degree
         *   4 letters -> (a,b) + (c,d)    single + sandhi
         *   5 letters -> (a,b,c) + (d,e)
         *   6 letters -> (a,b,c) + (d,e,f) */
        if (ntone >= 1 && out[n-1].kind == TK_BASE) {
            if (ntone == 1) {
                out[n-1].tkind[1] = 1;
                out[n-1].tone[1][0] = tonebuf[0];
                out[n-1].tone[1][1] = tonebuf[0];
            } else if (ntone == 2) {
                out[n-1].tkind[1] = 1;
                out[n-1].tone[1][0] = tonebuf[0]; out[n-1].tone[1][1] = tonebuf[1];
            } else if (ntone == 3) {
                out[n-1].tkind[1] = 1;
                out[n-1].tone[1][0] = tonebuf[0]; out[n-1].tone[1][1] = tonebuf[1];
                out[n-1].tone[1][2] = tonebuf[2];
            } else if (ntone == 4) {
                out[n-1].tkind[1] = 1;
                out[n-1].tone[1][0] = tonebuf[0]; out[n-1].tone[1][1] = tonebuf[1];
                out[n-1].tkind[2] = 1;
                out[n-1].tone[2][0] = tonebuf[2]; out[n-1].tone[2][1] = tonebuf[3];
            } else if (ntone == 5) {
                out[n-1].tkind[1] = 1;
                out[n-1].tone[1][0] = tonebuf[0]; out[n-1].tone[1][1] = tonebuf[1];
                out[n-1].tone[1][2] = tonebuf[2];
                out[n-1].tkind[2] = 1;
                out[n-1].tone[2][0] = tonebuf[3]; out[n-1].tone[2][1] = tonebuf[4];
            } else { /* >= 6 */
                out[n-1].tkind[1] = 1;
                out[n-1].tone[1][0] = tonebuf[0]; out[n-1].tone[1][1] = tonebuf[1];
                out[n-1].tone[1][2] = tonebuf[2];
                out[n-1].tkind[2] = 1;
                out[n-1].tone[2][0] = tonebuf[3]; out[n-1].tone[2][1] = tonebuf[4];
                out[n-1].tone[2][2] = tonebuf[5];
            }
        }
    }
    *nout = n;
    return 0;
full:
    snprintf(err, errsz, "too many tokens");
    return -1;
}

/* ------------------------------------------------------------------ */
/* Canonicalise: Layer1 -> Layer2 (feature-tier order)                 */
/* Each segment's tokens are re-grouped: the base stays first, then     */
/* modifiers sorted by tier (stable).  A ligature pair keeps its order  */
/* (closure, tie, release are a single unit).                           */
/* ------------------------------------------------------------------ */

static IPA2VEC_MAYBE_UNUSED void canonicalise (IrTok *l1, int n1, IrTok *l2, int *n2)
{
    int m = 0;
    int i = 0;
    while (i < n1) {
        if (l1[i].kind == TK_BASE) {
            /* collect preposed mods (TK_MOD with preposed flag, contiguous
             * immediately before this base) + postposed mods (contiguous
             * after), then emit base first, mods sorted by tier. */
            int seg_start = i;
            while (seg_start > 0 && l1[seg_start - 1].kind == TK_MOD &&
                   l1[seg_start - 1].preposed)
                seg_start--;
            int seg_end = i + 1;
            while (seg_end < n1 && l1[seg_end].kind == TK_MOD &&
                   !l1[seg_end].preposed)
                seg_end++;
            l2[m++] = l1[i];
            for (Tier t = TIER_AIRSTREAM; t < TIER_COUNT; t = (Tier)(t + 1)) {
                for (int j = seg_start; j < seg_end; j++)
                    if (j != i && l1[j].kind == TK_MOD && l1[j].tier == t)
                        l2[m++] = l1[j];
            }
            i = seg_end;
        } else if (l1[i].kind == TK_LIG) {
            /* keep tie + release base + its mods as a unit */
            l2[m++] = l1[i];
            i++;
            if (i < n1 && l1[i].kind == TK_BASE) {
                l2[m++] = l1[i];
                int start = ++i;
                while (i < n1 && l1[i].kind != TK_BASE && l1[i].kind != TK_LIG)
                    i++;
                for (Tier t = TIER_AIRSTREAM; t < TIER_COUNT; t = (Tier)(t + 1))
                    for (int j = start; j < i; j++)
                        if (l1[j].kind == TK_MOD && l1[j].tier == t)
                            l2[m++] = l1[j];
            }
        } else {
            /* preposed modifiers are collected by the following base's
             * seg_start scan; any other stray token is dropped */
            i++;
        }
    }
    *n2 = m;
}

/* ------------------------------------------------------------------ */
/* Apply: Layer2 in order -> per-segment vectors                       */
/* A segment starts at every TK_BASE (or at the release base of a      */
/* ligature pair); modifiers are applied sequentially.                 */
/* ------------------------------------------------------------------ */

static IPA2VEC_MAYBE_UNUSED void apply_layer2 (IrTok *l2, int n2, SegVec *segs, int *nsegs)
{
    *nsegs = 0;
    int i = 0;
    while (i < n2) {
        /* expect a base or a ligature pair at segment start */
        if (l2[i].kind == TK_BASE) {
            SegVec out;
            const SegEntry *base = l2[i].seg;
            memcpy(out.v, base->v, sizeof(out.v));
            out.airstream = base->airstream;
            out.note[0] = 0;
            for (int g = 0; g < 5; g++) {
                out.tone[g][0] = NAN;
                out.tone[g][1] = NAN;
                out.tone[g][2] = NAN;
                out.tkind[g] = 0;
                if (l2[i].tkind[g]) {
                    out.tkind[g] = l2[i].tkind[g];
                    for (int k = 0; k < 3; k++)
                        out.tone[g][k] = l2[i].tone[g][k];
                }
            }
            i++;
            /* apply following modifiers until next segment start */
            while (i < n2 && (l2[i].kind == TK_MOD || l2[i].kind == TK_LIG)) {
                if (l2[i].kind == TK_MOD) {
                    if (l2[i].mod && l2[i].mod->apply) {
                        l2[i].mod->apply(out.v, NULL);
                        if (l2[i].mod->air >= 0)
                            out.airstream = l2[i].mod->air;
                        if (l2[i].mod->infer)
                            fprintf(stderr, "ipa2vec: note: %s\n", l2[i].mod->infer);
                        if (out.note[0]) strcat(out.note, ",");
                        strcat(out.note, l2[i].latin);
                    } else {
                        /* no-op modifiers (tone/pitch letters): note only */
                        if (out.note[0]) strcat(out.note, ",");
                        strcat(out.note, l2[i].latin);
                    }
                    i++;
                } else { /* ligature pair: release base + its modifiers */
                    int j = i + 1;
                    if (j < n2 && l2[j].kind == TK_BASE) {
                        const SegEntry *rel = l2[j].seg;
                        out.v[12] = rel->v[12] + 0.5;
                        out.v[13] = rel->v[13];
                        out.v[14] = rel->v[14];
                        if (rel->airstream != base->airstream) {
                            out.airstream = rel->airstream;
                            out.v[15] = rel->v[15];
                            out.v[9]  = rel->v[9];
                            out.v[10] = rel->v[10];
                            out.v[11] = rel->v[11];
                        }
                        if (out.note[0]) strcat(out.note, ",");
                        strcat(out.note, "tie");
                        j++;
                        while (j < n2 && l2[j].kind == TK_MOD) {
                            if (l2[j].mod && l2[j].mod->apply) {
                                l2[j].mod->apply(out.v, NULL);
                                if (l2[j].mod->air >= 0)
                                    out.airstream = l2[j].mod->air;
                            }
                            j++;
                        }
                        i = j;
                    } else {
                        i++;
                    }
                }
            }
            if (*nsegs < MAX_SEGS)
                segs[(*nsegs)++] = out;
        } else {
            i++;   /* stray modifier or tie without base: skip */
        }
    }
}

/* ------------------------------------------------------------------ */
/* Reverse: vector -> IR (canonical order) -> IPA string               */
/* Greedy: start from nearest base; repeatedly add the modifier that   */
/* most reduces weighted distance, until no improvement.               */
/* ------------------------------------------------------------------ */

static IPA2VEC_MAYBE_UNUSED void nearest_base (const double v[NDIM], const SegEntry **out, double *outd)
{
    int best = -1;
    double bestd = 1e300;
    for (int i = 0; i < NSEG; i++) {
        double d = seg_dist(v, SEG_TABLE[i].v);
        if (d < bestd) { bestd = d; best = i; }
    }
    *out = &SEG_TABLE[best];
    *outd = bestd;
}

/* greedy modifier fit; returns number of modifiers chosen (<= 3).
 * A modifier is never chosen twice — nor an equivalent one with the same
 * apply() function under a different glyph (e.g. raised ◌̝ vs ˔).
 * Each added modifier must improve the distance by at least 8% (relative),
 * otherwise it is judged noise and dropped — this keeps intermediate
 * centroids (e.g. the average of two different segments) from stacking
 * four diacritics onto a single letter. */
#define IPA2VEC_FIT_MAX_MODS   3
#define IPA2VEC_FIT_MIN_GAIN   0.08

static IPA2VEC_MAYBE_UNUSED int fit_modifiers (const double target[NDIM], const SegEntry *base,
                         const ModRec *mods[IPA2VEC_FIT_MAX_MODS])
{
    double cur[NDIM];
    memcpy(cur, base->v, sizeof(cur));
    int n = 0;
    for (int round = 0; round < IPA2VEC_FIT_MAX_MODS; round++) {
        int besti = -1;
        double bestd = seg_dist(target, cur);
        for (int i = 0; i < NMODS; i++) {
            if (!MODS[i].apply || is_ligature_cp(MODS[i].cp)) continue;
            if (!MODS[i].reverse) continue;   /* input-tolerance only */
            /* skip modifiers already chosen, or with the same effect */
            int used = 0;
            for (int k = 0; k < n; k++)
                if (mods[k]->apply == MODS[i].apply) { used = 1; break; }
            if (used) continue;
            double trial[NDIM];
            memcpy(trial, cur, sizeof(trial));
            MODS[i].apply(trial, NULL);
            double d = seg_dist(target, trial);
            if (d < bestd - 1e-9) { bestd = d; besti = i; }
        }
        if (besti < 0) break;
        /* significance gate: require at least MIN_GAIN relative improvement
         * over the previous distance (before this round) */
        double prev = seg_dist(target, cur);
        if (prev > 1e-12 && (prev - bestd) / prev < IPA2VEC_FIT_MIN_GAIN)
            break;
        mods[n++] = &MODS[besti];
        MODS[besti].apply(cur, NULL);
    }
    return n;
}

/* rebuild an IPA string from (base, modifier cps): base then combining
 * marks in canonical-feature order; the result is a valid *composed* form */
/* does the base letter have a descender (below-line stroke)?  On such
 * letters IPA convention places below-marks above the letter instead
 * (e.g. ŋ̥ -> ŋ̊). */
static IPA2VEC_MAYBE_UNUSED int has_descender(const char *s)
{
    /* descender letters: g ɡ ɢ ɠ ɣ ŋ ɳ ɲ ɴ ɟ ʝ ɧ ʡ ʢ ɮ ɬ? (ɬ no),
     * j ȷ ç? (ç no), and any letter containing the combining cases below */
    static const char *desc[] = {
        "g", "\xc9\xa1", "\xc9\xa2", "\xc9\xa0", "\xc9\xa3",
        "\xc5\x8b", "\xc9\xb3", "\xc9\xb2", "\xc9\xb4",
        "\xc9\x9f", "\xca\x9d", "\xc9\xa7", "\xca\xa1", "\xca\xa2",
        "\xc9\xae", "j", "\xc8\xb7", "q", "\xc9\xb5", "\xc9\xa6",
        NULL };
    for (int i = 0; desc[i]; i++)
        if (strcmp(s, desc[i]) == 0)
            return 1;
    return 0;
}

/* combining-mark equivalents for spacing modifier letters: prefer the
 * combining form when emitting (standard IPA uses ◌̝ not ˔, ◌̞ not ˕ …).
 * Superscript letters (ʰ ʲ ʷ ˠ ˤ ʼ) are themselves standard IPA and are
 * kept as-is. */
static IPA2VEC_MAYBE_UNUSED const char *combining_form(const ModRec *m)
{
    switch (m->cp) {
    case 0x02D4: return "\xcc\x9d";   /* ˔ raised  -> ◌̝ */
    case 0x02D5: return "\xcc\x9e";   /* ˕ lowered -> ◌̞ */
    default: return NULL;
    }
}

/* IPA diacritic order (near -> far from the base letter), per the
 * Handbook of the IPA and conventional practice:
 *   1 phonation/voicing (̥ ̬ ̤ ̰ ʱ)
 *   2 place micro-adjustment (̟ ̠ ̪ ̺ ̻ ̼ ̢)
 *   3 manner (̝ ̞ ˔ ˕ ̽)
 *   4 tongue root (̘ ̙)
 *   5 secondary articulation (ʲ ʷ ˠ ˤ ̴)
 *   6 nasality (̃)
 *   7 release (ʰ ʼ ˡ ⁿ ᵊ ˢ ̚)
 *   8 timing (ː ˑ ̆ ̩ ̯)
 *   9 tone / everything else
 * Lower number = closer to the letter. */
static IPA2VEC_MAYBE_UNUSED int mod_priority(const ModRec *m)
{
    switch (m->cp) {
    case 0x0325: case 0x030A: case 0x0308: case 0x032C:      /* voicing */
    case 0x0304: case 0x0330: case 0x02B1:                    /* phonation */
        return 1;
    case 0x031F: case 0x0320: case 0x032A: case 0x033A:       /* place micro */
    case 0x033B: case 0x033C: case 0x0322: case 0x0347:
        return 2;
    case 0x031D: case 0x031E: case 0x02D4: case 0x02D5:       /* manner */
    case 0x033D:
        return 3;
    case 0x0318: case 0x0319:                                  /* tongue root */
        return 4;
    case 0x02B2: case 0x02B7: case 0x02E0: case 0x02E4:       /* secondary */
    case 0x0334: case 0x02B8:
        return 5;
    case 0x0303: case 0x1D51: case 0x1D4B:                    /* nasality */
        return 6;
    case 0x02B0: case 0x02BC: case 0x02E1: case 0x207F:       /* release */
    case 0x1D4A: case 0x02E2: case 0x031A: case 0x1D30:
        return 7;
    case 0x02D0: case 0x02D1: case 0x0306: case 0x0329:       /* timing */
    case 0x032F:
        return 8;
    default:
        return 9;
    }
}

/* order modifiers by IPA diacritic order (stable) */
static IPA2VEC_MAYBE_UNUSED void order_mods(const ModRec **mods, int nmods)
{
    for (int i = 1; i < nmods; i++) {
        const ModRec *key = mods[i];
        int j = i - 1;
        while (j >= 0 && mod_priority(mods[j]) > mod_priority(key)) {
            mods[j + 1] = mods[j];
            j--;
        }
        mods[j + 1] = key;
    }
}

/* build the IPA spelling: base letter + modifiers in feature-tier order.
 * Standard symbols only: spacing modifier letters are replaced by their
 * combining forms where one exists; below-marks on descender letters are
 * moved above (voiceless ◌̥ -> ◌̊). */
static IPA2VEC_MAYBE_UNUSED void build_ipa (const SegEntry *base, const ModRec **mods, int nmods,
                       char *out, size_t outsz)
{
    snprintf(out, outsz, "%s", base->ipa);
    size_t used = strlen(out);

    /* copy to a local array so we can reorder without touching caller data */
    const ModRec *ordered[8];
    int n = nmods < 8 ? nmods : 8;
    for (int i = 0; i < n; i++) ordered[i] = mods[i];
    order_mods(ordered, n);

    int desc = has_descender(base->ipa);

    for (int i = 0; i < n; i++) {
        const char *glyph = ordered[i]->ipa;
        /* prefer the combining form of spacing modifier letters */
        const char *comb = combining_form(ordered[i]);
        if (comb) glyph = comb;
        /* voiceless below-mark on a descender letter -> above ring */
        if (desc && (ordered[i]->cp == 0x0325 || ordered[i]->cp == 0x030A ||
                     ordered[i]->cp == 0x0308)) {
            glyph = "\xcc\x8a";   /* ◌̊ voiceless ring (above) */
        }
        /* strip the U+25CC dotted-circle placeholder from display glyphs
         * (MODS entries are written "◌̝" for readability; the emitted IPA
         * spelling carries only the combining mark itself) */
        const unsigned char *g = (const unsigned char *)glyph;
        while (*g) {
            unsigned long cp;
            int k = utf8_decode(g, &cp);
            if (!k) break;
            if (cp != 0x25CC) {
                if (used + (size_t)k + 1 < outsz) {
                    memcpy(out + used, g, (size_t)k);
                    used += (size_t)k;
                    out[used] = 0;
                }
            }
            g += k;
        }
    }
}

/* ------------------------------------------------------------------ */
/* Output helpers                                                      */
/* ------------------------------------------------------------------ */

/* print the 5-group tone annotation, e.g.  ()?(1,2)?(4,5)  */
static IPA2VEC_MAYBE_UNUSED void print_tone (const SegVec *sv)
{
    int last = -1;
    for (int g = 0; g < 5; g++)
        if (sv->tkind[g] != 0)
            last = g;
    if (last < 0) return;
    printf("  tone=");
    for (int g = 0; g <= last; g++) {
        if (sv->tkind[g] == 0) { printf("%s()", g ? "?" : ""); continue; }
        /* group 4 (step/global) and group 5 (class): (a,?) / (?,b) forms */
        int nvals = 3;
        if (sv->tkind[g] == 2) nvals = 1;      /* class: single value */
        else if (sv->tkind[g] == 3) nvals = 2; /* step: (a,?) */
        else if (sv->tkind[g] == 4) nvals = 2; /* global: (?,b) */
        else {
            /* contour: 2 or 3 values */
            nvals = !isnan(sv->tone[g][2]) ? 3 : 2;
        }
        printf("%s(", g ? "?" : "");
        for (int k = 0; k < nvals; k++) {
            if (k) printf(",");
            if (isnan(sv->tone[g][k])) printf("?");
            else printf("%g", sv->tone[g][k]);
        }
        printf(")");
    }
}

static IPA2VEC_MAYBE_UNUSED void print_seg_text (const SegVec *sv, const char *label)
{
    printf("%-6s (", label);
    for (int i = 0; i < NDIM; i++)
        printf("%s%.4f", i ? ", " : "", sv->v[i]);
    printf(")  %s%s%s", AIRSTREAM_LABELS[sv->airstream],
           sv->note[0] ? "  [" : "", sv->note);
    print_tone(sv);
    printf("\n");
}

static IPA2VEC_MAYBE_UNUSED void print_layer (IrTok *toks, int n, const char *title)
{
    printf("  %s: ", title);
    for (int i = 0; i < n; i++) {
        if (i) printf(" → ");
        switch (toks[i].kind) {
        case TK_BASE: printf("[%s:%s]", toks[i].ipa, toks[i].latin); break;
        case TK_MOD:  printf("[%s:%s", toks[i].ipa, toks[i].latin);
            if (toks[i].tier < TIER_COUNT)
                printf("/%s", TIER_NAMES[toks[i].tier]);
            printf("]");
            break;
        case TK_LIG:  printf("[tie]"); break;
        }
    }
    printf("\n");
}

/* ------------------------------------------------------------------ */
/* Unified option parsing (every tool: short name + long name)         */
/* ------------------------------------------------------------------ */

/* matches an argument against (short, long); both forms accepted */
static IPA2VEC_MAYBE_UNUSED int opt_match(const char *arg,
                                          const char *short_opt,
                                          const char *long_opt)
{
    if (short_opt && strcmp(arg, short_opt) == 0) return 1;
    if (long_opt && strcmp(arg, long_opt) == 0) return 1;
    return 0;
}

/* option with a value: "-o FILE", "--output FILE" or "--output=FILE".
 * Returns 1 if matched (val set), 0 if not, -1 if value missing. */
static IPA2VEC_MAYBE_UNUSED int opt_match_val(const char *arg,
                                              const char *short_opt,
                                              const char *long_opt,
                                              const char **val,
                                              int argc, char **argv, int *i)
{
    if (short_opt && strcmp(arg, short_opt) == 0) {
        if (*i + 1 >= argc) return -1;
        *val = argv[++*i];
        return 1;
    }
    if (long_opt) {
        size_t L = strlen(long_opt);
        if (strcmp(arg, long_opt) == 0) {
            if (*i + 1 >= argc) return -1;
            *val = argv[++*i];
            return 1;
        }
        if (strncmp(arg, long_opt, L) == 0 && arg[L] == '=') {
            *val = arg + L + 1;
            return 1;
        }
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* I/O helpers shared by all three tools                               */
/* ------------------------------------------------------------------ */

#define STDIN_MAX 65536

/* read all of stdin (used when no positional argument is given) */
static IPA2VEC_MAYBE_UNUSED char *read_stdin(void)
{
    char *buf = (char *)malloc(STDIN_MAX);
    if (!buf) return NULL;
    size_t n = 0;
    int c;
    while (n + 1 < STDIN_MAX && (c = getchar()) != EOF)
        buf[n++] = (char)c;
    buf[n] = 0;
    if (n == 0) { free(buf); return NULL; }
    /* trim trailing whitespace/newline */
    while (n > 0 && (buf[n-1] == '\n' || buf[n-1] == '\r' || buf[n-1] == ' ' ||
                     buf[n-1] == '\t'))
        buf[--n] = 0;
    return buf;
}

/* redirect stdout to a file if -o FILE was given; returns 0 on success */
static IPA2VEC_MAYBE_UNUSED int redirect_output(const char *file)
{
    FILE *f = fopen(file, "w");
    if (!f) { fprintf(stderr, "ipa2vec: cannot open %s for writing\n", file); return -1; }
#ifdef _WIN32
    if (_dup2(_fileno(f), _fileno(stdout)) != 0)
#else
    if (dup2(fileno(f), fileno(stdout)) != 0)
#endif
    {
        fprintf(stderr, "ipa2vec: cannot redirect to %s\n", file);
        fclose(f);
        return -1;
    }
    fclose(f);
    return 0;
}

/* write the two-layer IR of a parse to <base>.layer1 and <base>.layer2 */
static IPA2VEC_MAYBE_UNUSED int export_ir(const IrTok *l1, int n1,
                                          const IrTok *l2, int n2,
                                          const char *base)
{
    char path[512];
    FILE *f;

    snprintf(path, sizeof(path), "%s.layer1", base);
    f = fopen(path, "w");
    if (!f) { fprintf(stderr, "ipa2vec: cannot open %s\n", path); return -1; }
    for (int i = 0; i < n1; i++) {
        const IrTok *t = &l1[i];
        switch (t->kind) {
        case TK_BASE:
            fprintf(f, "BASE\t%s\t%s\n", t->ipa, t->latin);
            break;
        case TK_MOD:
            fprintf(f, "MOD\t%s\t%s\t%s\n", t->ipa, t->latin,
                    t->tier < TIER_COUNT ? TIER_NAMES[t->tier] : "-");
            break;
        case TK_LIG:
            fprintf(f, "TIE\t-\t-\t-\n");
            break;
        }
    }
    fclose(f);

    snprintf(path, sizeof(path), "%s.layer2", base);
    f = fopen(path, "w");
    if (!f) { fprintf(stderr, "ipa2vec: cannot open %s\n", path); return -1; }
    for (int i = 0; i < n2; i++) {
        const IrTok *t = &l2[i];
        switch (t->kind) {
        case TK_BASE:
            fprintf(f, "BASE\t%s\t%s\n", t->ipa, t->latin);
            break;
        case TK_MOD:
            fprintf(f, "MOD\t%s\t%s\t%s\n", t->ipa, t->latin,
                    t->tier < TIER_COUNT ? TIER_NAMES[t->tier] : "-");
            break;
        case TK_LIG:
            fprintf(f, "TIE\t-\t-\t-\n");
            break;
        }
    }
    fclose(f);
    return 0;
}

#endif /* IPA2VEC_CORE_H */
