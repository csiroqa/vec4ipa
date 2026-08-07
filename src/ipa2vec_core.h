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
    /* tone annotations — three extra vectors:
     *   tone[0] 5-level letters / single tone  (¹²³⁴⁵, ˩˨˧˦˥)
     *   tone[1] tone sandhi (꜖꜕꜔꜓꜒)
     *   tone[2] 3-D vector (default (0,0,0)):
     *       dim 0: upstep/downstep (ꜛꜜ)
     *       dim 1: global rise/fall (↗↘)
     *       dim 2: Chinese tone class (꜀꜁꜂꜃꜄꜅꜆꜇)
     * NAN means "not set"; tone[0][0]==NAN means group empty. */
    double tone[3][3];
    int tkind[3];          /* 0 none, 1 contour, 2 = 3-D vector */
} SegVec;

/* ------------------------------------------------------------------ */
/* Runtime metric — compiled-in defaults (METRIC_W / METRIC_LAMBDA     */
/* from vectors.h) unless overridden per-invocation by --metric FILE.  */
/* The defaults are used automatically, so the binaries never need an  */
/* external JSON at runtime.                                           */
/* ------------------------------------------------------------------ */

static double g_metric_w[NDIM];
static double g_metric_M[NDIM][NDIM];
static double g_metric_lambda;
static int    g_metric_full = 0;   /* 1: use the full 16x16 matrix form */
static int    g_metric_ready = 0;  /* 0: seg_dist must sync defaults */

static IPA2VEC_MAYBE_UNUSED void metric_sync_defaults (void)
{
    for (int i = 0; i < NDIM; i++) {
        g_metric_w[i] = METRIC_W[i];
        for (int j = 0; j < NDIM; j++)
            g_metric_M[i][j] = (i == j) ? METRIC_W[i] : 0.0;
    }
    g_metric_lambda = METRIC_LAMBDA;
    g_metric_full = 0;
    g_metric_ready = 1;
}

static IPA2VEC_MAYBE_UNUSED void metric_ensure (void)
{
    if (!g_metric_ready) metric_sync_defaults();
}

static IPA2VEC_MAYBE_UNUSED double seg_dist (const double a[NDIM], const double b[NDIM])
{
    metric_ensure();
    double s = 0.0;
    if (g_metric_full) {
        for (int i = 0; i < NDIM; i++) {
            double di = a[i] - b[i];
            if (di == 0.0) continue;
            for (int j = 0; j < NDIM; j++) {
                double dj = a[j] - b[j];
                if (dj == 0.0) continue;
                s += g_metric_M[i][j] * di * dj;
            }
        }
    } else {
        for (int i = 0; i < NDIM; i++) {
            double d = a[i] - b[i];
            s += g_metric_w[i] * d * d;
        }
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
static const SegEntry EXTRA_BASE[] = {
    /* ᴇ U+1D07: small-cap E = lowered e [e̞] (front mid unrounded) */
    { "\xe1\xb4\x87", { 0.0, 0.0, 0.55, 0.1, 1.0, -0.2, 0.0, 0.0,
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
    /* ʬ U+02AC: bilabial percussive (extIPA) — non-pulmonic (no airflow:
     * airflow_direction 0), airstream = percussive (index 4) */
    { "\xca\xac", { 1.0, 0.0, 0.55, 0.25, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.4, 0.0, 0.1, 0.0, 0.0, 0.0 }, 4 },
    /* ʭ U+02AD: bidental percussive (extIPA) — non-pulmonic */
    { "\xca\xad", { 0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.4, 0.0, 0.1, 0.0, 0.0, 0.0 }, 4 },
    /* ʩ U+02A9: velopharyngeal fricative (extIPA) */
    { "\xca\xa9", { 0.0, 0.0, 0.55, 0.25, -0.5, 0.0, 0.5, 0.0,
                    0.0, 0.0, 0.4, 0.0, 0.6, 0.0, 0.09, 1.0 }, 0 },
    /* ꞎ U+A78E: voiceless retroflex lateral fricative (IPA 2018) */
    { "\xea\x9e\x8e", { 0.0, 0.0, 0.1, 0.8, 0.0, 0.0, 0.0, 1.0,
                        0.0, 0.0, 0.4, 0.0, 0.9, 0.5, 0.08, 1.0 }, 0 },
    /* ᶑ U+1D91: retroflex implosive (IPA 2018) */
    { "\xe1\xb6\x91", { 0.0, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0,
                        1.0, 0.55, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0 }, 2 },
    /* ȶ U+0236: voiceless alveolo-palatal stop (curl notation, Sinologist);
     * alveolo-palatal = tip at 0.25 with tongue body neutral (cf. ɕ ʑ) */
    { "\xc8\xb6", { 0.0, 0.0, 0.25, 1.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, 1.0 }, 0 },
    /* ȡ U+0221: voiced alveolo-palatal stop */
    { "\xc8\xa1", { 0.0, 0.0, 0.25, 1.0, 0.0, 0.0, 0.0, 0.0,
                    1.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0 }, 0 },
    /* ȵ U+0235: voiced alveolo-palatal nasal */
    { "\xc8\xb5", { 0.0, 0.0, 0.25, 1.0, 0.0, 0.0, 1.0, 0.0,
                    1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0 }, 0 },
    /* ȴ U+0234: voiced alveolo-palatal lateral */
    { "\xc8\xb4", { 0.0, 0.0, 0.25, 1.0, 0.0, 0.0, 0.0, 1.0,
                    1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.5, 1.0 }, 0 },
};
#define N_EXTRA ((int)(sizeof(EXTRA_BASE) / sizeof(EXTRA_BASE[0])))

/* latin feature names for EXTRA_BASE (parallel array) */
static const char *EXTRA_NAMES[N_EXTRA] = {
    "fr.mid.unr.vwl",     /* ᴇ = e̞ */
    "cent.mid.rnd.vwl",   /* ɚ rhotacised schwa */
    "cent.omid.rnd.vwl",  /* ɞ */
    "cent.omid.rhot.vwl", /* ɝ */
    "bil.percussive",     /* ʬ */
    "bidental.percussive",/* ʭ */
    "velophar.frc",       /* ʩ */
    "rfl.lat.frc",        /* ꞎ */
    "rfl.imp",            /* ᶑ */
    "alvpal.pls",         /* ȶ */
    "alvpal.pls.vd",      /* ȡ */
    "alvpal.nas",         /* ȵ */
    "alvpal.lat",         /* ȴ */
};

/* school gate for EXTRA_BASE entries: index into ALIAS_MODULES
 * (or -1 = always available).  The Sinologist curl letters ȶ ȡ ȵ ȴ
 * follow the school's place split (cf. ɕ ʑ), so they are gated on
 * --sinologist like the alias symbols. */
static const int EXTRA_SCHOOL[N_EXTRA] = {
    -1, -1, -1, -1, -1, -1, -1, -1, -1,
    4, 4, 4, 4,        /* sinologist (module index 4) */
};

/* longest-prefix base lookup against the 132-entry table */
static IPA2VEC_MAYBE_UNUSED void mod_nasal (double v[NDIM], const void *m) { (void)m; v[6]  = 0.8; }
static IPA2VEC_MAYBE_UNUSED void mod_long (double v[NDIM], const void *m) { (void)m; v[12] = 2.0; }
/* contrast-aware setter: set v[dim] to full_val unless the result would
 * exactly equal a DIFFERENTLY-spelled base segment (e.g. p + ◌̚ would
 * become ʬ, whose only difference from p is duration) — in that case take
 * the midpoint so the spelling stays distinct. */
static IPA2VEC_MAYBE_UNUSED void set_avoid_collision(double v[NDIM], int dim,
                                                     double full_val)
{
    double full[NDIM];
    memcpy(full, v, sizeof(full));
    full[dim] = full_val;
    int collides = 0;
    for (int i = 0; i < NSEG && !collides; i++) {
        int same = 1;
        for (int k = 0; k < NDIM; k++)
            if (SEG_TABLE[i].v[k] != full[k]) { same = 0; break; }
        if (same) collides = 1;
    }
    for (int i = 0; i < N_EXTRA && !collides; i++) {
        int same = 1;
        for (int k = 0; k < NDIM; k++)
            if (EXTRA_BASE[i].v[k] != full[k]) { same = 0; break; }
        if (same) collides = 1;
    }
    if (collides)
        v[dim] = (v[dim] + full_val) / 2.0;
    else
        v[dim] = full_val;
}

/* half-long with contrast awareness (χ + ◌ˑ would become q͡χ) */
static IPA2VEC_MAYBE_UNUSED void mod_half (double v[NDIM], const void *m)
{
    (void)m;
    set_avoid_collision(v, 12, 1.5);
}

/* unreleased with contrast awareness (p + ◌̚ would become ʬ) */
static IPA2VEC_MAYBE_UNUSED void mod_unrel (double v[NDIM], const void *m)
{
    (void)m;
    set_avoid_collision(v, 12, 0.1);
}
static IPA2VEC_MAYBE_UNUSED void mod_asp (double v[NDIM], const void *m) { (void)m; v[10] = 0.9; v[9] = 0.0; }
static IPA2VEC_MAYBE_UNUSED void mod_creaky (double v[NDIM], const void *m) { (void)m; v[9] = 0.7; v[10] = 0.0; v[11] = 0.7; }
static IPA2VEC_MAYBE_UNUSED void mod_breathy (double v[NDIM], const void *m) { (void)m; v[10] = 0.55; v[9] = 0.2; v[11] = -0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_phar (double v[NDIM], const void *m) { (void)m; v[5] = 0.7; v[4] = -0.2; }
static IPA2VEC_MAYBE_UNUSED void mod_velar (double v[NDIM], const void *m) { (void)m; v[4] = -0.3; v[5] = 0.3; }
static IPA2VEC_MAYBE_UNUSED void mod_pal (double v[NDIM], const void *m) { (void)m; v[4] = 0.6; }
static IPA2VEC_MAYBE_UNUSED void mod_lab (double v[NDIM], const void *m) { (void)m; if (v[1] < 0.5) v[1] = 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_syl (double v[NDIM], const void *m) { (void)m; v[12] += 0.5; }
static IPA2VEC_MAYBE_UNUSED void mod_nosyl (double v[NDIM], const void *m) { (void)m; v[12] -= 0.5; }
/* Voicing / devoicing is *contrast-aware*:
 *
 *   ◌̬ / ◌̥ on a segment that HAS a voicing counterpart (t ↔ d, s ↔ z …)
 *     push part-way so t → t̬ → d̥ → d advances in small steps (t̬ ≠ d).
 *   ◌̥ on a segment with NO voiceless counterpart (n, m, ŋ, l, r, w … —
 *     IPA has no voiceless nasal/approximant symbols) means "the voiceless
 *     form" itself, so it goes all the way (n̥ = voiceless n, voiced = 0).
 *   ◌̬ likewise: on ǃ (no voiced click symbol) it means "the voiced form"
 *     (ǃ̬ fully voiced).
 *
 * Absolute values make the modifiers idempotent (t̬̬ = t̬). */
static IPA2VEC_MAYBE_UNUSED void mod_voiceless_part (double v[NDIM], const void *m) { (void)m; v[8] = 0.4; v[9] = 0.1; v[10] = 0.2; }
static IPA2VEC_MAYBE_UNUSED void mod_voiced_part    (double v[NDIM], const void *m) { (void)m; v[8] = 0.6; v[9] = 0.1; v[10] = 0.2; }
static IPA2VEC_MAYBE_UNUSED void mod_voiceless_full (double v[NDIM], const void *m) { (void)m; v[8] = 0.0; v[9] = 0.0; v[10] = 0.4; }
static IPA2VEC_MAYBE_UNUSED void mod_voiced_full    (double v[NDIM], const void *m) { (void)m; v[8] = 1.0; v[9] = 0.2; v[10] = 0.0; }
static IPA2VEC_MAYBE_UNUSED void mod_voiceless (double v[NDIM], const void *m) { mod_voiceless_part(v, m); }
static IPA2VEC_MAYBE_UNUSED void mod_voiced    (double v[NDIM], const void *m) { mod_voiced_part(v, m); }

/* lazy table of which base segments have a voicing counterpart */
static IPA2VEC_MAYBE_UNUSED int g_voice_counter[NSEG];
static IPA2VEC_MAYBE_UNUSED int g_voice_counter_ready = 0;

static IPA2VEC_MAYBE_UNUSED int has_voicing_counterpart(const SegEntry *base)
{
    if (base < SEG_TABLE || base >= SEG_TABLE + NSEG)
        return 0;   /* EXTRA_BASE entries: assume no counterpart */
    if (!g_voice_counter_ready) {
        for (int i = 0; i < NSEG; i++)
            g_voice_counter[i] = 0;
        for (int i = 0; i < NSEG; i++) {
            for (int j = i + 1; j < NSEG; j++) {
                const double *a = SEG_TABLE[i].v, *b = SEG_TABLE[j].v;
                int same = 1, vdiff = 0;
                for (int k = 0; k < NDIM; k++) {
                    if (k == 8 || k == 9 || k == 10) {
                        if (a[k] != b[k]) vdiff = 1;
                    } else if (k == 12 || k == 13) {
                        /* voiced fricatives are systematically slightly
                         * shorter/lower in the table (z vs s: dur 0.7/0.8,
                         * jet 0.85/0.95) — allow that accompanying
                         * difference, it is still the same segment pair */
                        if (fabs(a[k] - b[k]) > 0.15) { same = 0; break; }
                    } else if (a[k] != b[k]) { same = 0; break; }
                }
                if (same && vdiff) {
                    g_voice_counter[i] = 1;
                    g_voice_counter[j] = 1;
                }
            }
        }
        g_voice_counter_ready = 1;
    }
    return g_voice_counter[base - SEG_TABLE];
}

/* apply a voicing modifier, choosing full vs partial by contrast */
static IPA2VEC_MAYBE_UNUSED void apply_voicing_mod(double v[NDIM],
                                                   const ModRec *m,
                                                   const SegEntry *base)
{
    if (m->apply == mod_voiceless)
        has_voicing_counterpart(base) ? mod_voiceless_part(v, NULL)
                                      : mod_voiceless_full(v, NULL);
    else if (m->apply == mod_voiced)
        has_voicing_counterpart(base) ? mod_voiced_part(v, NULL)
                                      : mod_voiced_full(v, NULL);
    else
        m->apply(v, NULL);
}
static IPA2VEC_MAYBE_UNUSED void mod_nasal_click (double v[NDIM], const void *m){ (void)m; v[6] = 1.0; v[8] = 1.0; v[9] = 0.2; v[10] = 0.0; v[12] = 1.0; }
/* dental (U+032A): on labials this is the labiodental plosive/nasal
 * (b̪ = vd labiodental plosive, p̪ = vl, m̪ = labiodental nasal — IPA
 * writes labiodental stops as p̪ b̪); on lingual segments it dentalises
 * the tip (t̪ d̪ n̪ …). */
static IPA2VEC_MAYBE_UNUSED void mod_dental (double v[NDIM], const void *m) {
    (void)m;
    if (v[0] > 0.5)          /* bilabial -> labiodental */
        v[0] = 0.9;
    else { v[2] = 1.0; if (v[3] < 0.5) v[3] = 0.5; }
}
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
    { 0x0362, "◌͢",  "sliding",   TIER_TIMING,    -1, mod_sliding,     0, {0,0} , NULL, 0  },
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
    { 0x0051, "Q",   "gemination",TIER_TIMING,    -1, mod_long,        0, {0,0} , NULL, 1  },
    { 0x02D1, "ˑ",   "half",      TIER_TIMING,    -1, mod_half,        0, {0,0} , NULL, 1  },
    { 0x02D4, "˔",   "raised",    TIER_MANNER,    -1, mod_raised,      0, {0,0} , NULL, 1  },
    { 0x02D5, "˕",   "lowered",   TIER_MANNER,    -1, mod_lowered,     0, {0,0} , NULL, 1  },
    { 0x02DE, "˞",   "rhot",      TIER_MANNER,    -1, mod_rhot,        0, {0,0} , NULL, 1  },
    { 0x02E0, "ˠ",   "vel",       TIER_PLACE,     -1, mod_velar,       0, {0,0} , NULL, 1  },
    { 0x02E1, "ˡ",   "lat_release", TIER_MANNER,  -1, mod_lat_release, 0, {0,0} , NULL, 1  },
    { 0x02E2, "ˢ",   "fric_release", TIER_MANNER,  -1, mod_fric_release,0, {0,0} , NULL, 1  },
    { 0x02E3, "ˣ",   "fric_release", TIER_MANNER,  -1, mod_fric_release,0, {0,0} , NULL, 1  },
    { 0x02E4, "ˤ",   "phar",      TIER_PLACE,     -1, mod_phar,        0, {0,0} , NULL, 1  },
    /* superscript letters as diacritics (IPA letters used as modifiers) */
    { 0x02B3, "ʳ",   "sup_rhot_r",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 0  },
    { 0x02B4, "ʴ",   "sup_rhot_ʁ",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 0  },
    { 0x02B5, "ʵ",   "sup_rhot_ʕ",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 0  },
    { 0x02B6, "ʶ",   "sup_rhot_ʢ",   TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 0  },
    { 0x1D49, "ᵉ",   "sup_e",        TIER_PLACE,  -1, mod_sup_front,   0, {0,0} , NULL, 0  },
    { 0x1D4C, "ᵌ",   "sup_ɛ",        TIER_MANNER, -1, mod_sup_mid,     0, {0,0} , NULL, 0  },
    { 0x1D64, "ᵤ",   "sup_u",        TIER_PLACE,  -1, mod_sup_back,    0, {0,0} , NULL, 0  },
    { 0x1D62, "ᵢ",   "sub_i",        TIER_PLACE,  -1, mod_sup_front,   0, {0,0} , NULL, 0  },
    { 0x1D63, "ᵣ",   "sub_r",        TIER_MANNER, -1, mod_sup_rhot1,   0, {0,0} , NULL, 0  },
    { 0x1D30, "ᴰ",   "sup_d",        TIER_MANNER, -1, mod_sup_stop,    0, {0,0} , NULL, 0  },
    { 0x1D3B, "ᴻ",   "sup_N",        TIER_NASAL,  -1, mod_nasal_rel,   0, {0,0} , NULL, 0  },
    { 0x1D2C, "ᴬ",   "sup_A",        TIER_NASAL,  -1, mod_sup_open,    0, {0,0} , NULL, 0  },
    { 0x1D2E, "ᴮ",   "sup_B",        TIER_MANNER, -1, mod_sup_stop,    0, {0,0} , NULL, 0  },
    { 0x1D3C, "ᴼ",   "sup_O",        TIER_PLACE,  -1, mod_sup_back,    0, {0,0} , NULL, 0  },
    { 0x1D3E, "ᴾ",   "sup_P",        TIER_MANNER, -1, mod_sup_stop,    0, {0,0} , NULL, 0  },
    { 0x1D41, "ᵁ",   "sup_U",        TIER_PLACE,  -1, mod_sup_back,    0, {0,0} , NULL, 0  },
    { 0x1D42, "ᵂ",   "sup_W",        TIER_PLACE,  -1, mod_lab,         0, {0,0} , NULL, 0  },
    { 0x02D2, "˒",   "light",        TIER_TIMING, -1, mod_sliding,     0, {0,0} , NULL, 0  },
    { 0x02D3, "˓",   "dark",         TIER_TIMING, -1, mod_sliding,     0, {0,0} , NULL, 0  },
    { 0x02D9, "˙",   "lengthened",   TIER_TIMING, -1, mod_long,        0, {0,0} , NULL, 0  },
    /* --- preposed modifiers --- */
    { 0x1D51, "ᵑ",   "nas_click", TIER_AIRSTREAM, -1, mod_nasal_click, 0, {0,0} , NULL, 1  },
    { 0x1D4B, "ᵋ",   "nas_rel",   TIER_AIRSTREAM, -1, mod_nasal,       0, {0,0} , NULL, 1  },
    { 0x1D4A, "ᵊ",   "schwa_rel", TIER_MANNER,    -1, mod_schwa_rel,   0, {0,0} , NULL, 1  },
    { 0x207F, "ⁿ",   "nasal_rel", TIER_NASAL,     -1, mod_nasal_rel,   0, {0,0} , NULL, 1  },
    { 0x02B1, "ʱ",   "breathy_asp", TIER_LARYNGEAL, -1, mod_breathy_asp, 0, {0,0} , "ʱ = voiced/breathy release (reinterpreted from aspiration)", 1  },
    { 0x02B8, "ʸ",   "offglide_pal", TIER_PLACE,  -1, mod_offglide_pal,0, {0,0} , NULL, 1  },
    { 0x1DB7, "ᶷ",   "offglide_lab", TIER_PLACE,  -1, mod_offglide_lab,0, {0,0} , NULL, 1  },
    { 0x1DA3, "ᶣ",   "offglide_labpal", TIER_PLACE, -1, mod_offglide_pal, 0, {0,0} , NULL, 1  },
    /* --- 5-level tone letters (high->low) -> extra vector 1 --- */
    { 0x02E5, "˥", "tone_5",  TIER_COUNT, -1, NULL, 1, {5,0}, NULL, 1  },
    { 0x02E6, "˦", "tone_4",  TIER_COUNT, -1, NULL, 1, {4,0}, NULL, 1  },
    { 0x02E7, "˧", "tone_3",  TIER_COUNT, -1, NULL, 1, {3,0}, NULL, 1  },
    { 0x02E8, "˨", "tone_2",  TIER_COUNT, -1, NULL, 1, {2,0}, NULL, 1  },
    { 0x02E9, "˩", "tone_1",  TIER_COUNT, -1, NULL, 1, {1,0}, NULL, 1  },
    /* --- superscript digits (⁰¹²³⁴⁵⁶⁷⁸⁹ = pitch levels 0-9) -> vec 1 --- */
    { 0x2070, "⁰", "pitch_0",  TIER_COUNT, -1, NULL, 1, {0,0}, NULL, 1  },
    { 0x00B9, "¹", "pitch_1",  TIER_COUNT, -1, NULL, 1, {1,0}, NULL, 1  },
    { 0x00B2, "²", "pitch_2",  TIER_COUNT, -1, NULL, 1, {2,0}, NULL, 1  },
    { 0x00B3, "³", "pitch_3",  TIER_COUNT, -1, NULL, 1, {3,0}, NULL, 1  },
    { 0x2074, "⁴", "pitch_4",  TIER_COUNT, -1, NULL, 1, {4,0}, NULL, 1  },
    { 0x2075, "⁵", "pitch_5",  TIER_COUNT, -1, NULL, 1, {5,0}, NULL, 1  },
    { 0x2076, "⁶", "pitch_6",  TIER_COUNT, -1, NULL, 1, {6,0}, NULL, 1  },
    { 0x2077, "⁷", "pitch_7",  TIER_COUNT, -1, NULL, 1, {7,0}, NULL, 1  },
    { 0x2078, "⁸", "pitch_8",  TIER_COUNT, -1, NULL, 1, {8,0}, NULL, 1  },
    { 0x2079, "⁹", "pitch_9",  TIER_COUNT, -1, NULL, 1, {9,0}, NULL, 1  },
    /* --- tone sandhi letters (꜖꜕꜔꜓꜒) -> extra vector 2 --- */
    { 0xA712, "꜒", "sandhi_5", TIER_COUNT, -1, NULL, 5, {5,0}, NULL, 1  },
    { 0xA713, "꜓", "sandhi_4", TIER_COUNT, -1, NULL, 5, {4,0}, NULL, 1  },
    { 0xA714, "꜔", "sandhi_3", TIER_COUNT, -1, NULL, 5, {3,0}, NULL, 1  },
    { 0xA715, "꜕", "sandhi_2", TIER_COUNT, -1, NULL, 5, {2,0}, NULL, 1  },
    { 0xA716, "꜖", "sandhi_1", TIER_COUNT, -1, NULL, 5, {1,0}, NULL, 1  },
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
    /* tone data collected for the segment (filled on the TK_BASE token):
     * 3 extra vectors — see SegVec. */
    int tkind[3];         /* 0 none, 1 contour (tone[0] or tone[1]), 2 = 3-D vector */
    double tone[3][3];    /* vector values; NAN = not set */
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
    { "\xC9\xAB", "l\xCB\xA4", "pharyngealised l (dark l)", 0, 0   },                /* ɫ -> lˤ */
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

/* --- module: equivalent symbols (Wikipedia IPA equivalent-symbols
 * table: superscript/subscript forms, hook letters, velarised/palatalised
 * forms of the base letters). --- */
static const Alias ALIAS_EQUIV[] = {
    { "\xE1\xB5\x83", "a", "superscript a", 0, 0   },
    { "\xE2\x82\x90", "a", "subscript a", 0, 0   },
    { "\xE1\xB5\x85", "\xC9\x91", "superscript alpha (open a)", 0, 0   },
    { "\xE1\xB5\x86", "\xC3\xA6", "superscript small turned ae (open-mid ae)", 0, 0   },
    { "\xE1\xB5\x84", "\xC9\x90", "superscript turned a (near-open central)", 0, 0   },
    { "\xE1\xB4\xB1", "e\xCC\x9E", "superscript capital E (lowered e)", 0, 0   },
    { "\xE1\xB6\x9F", "\xC9\x9C", "superscript reversed open e", 0, 0   },
    { "\xE2\x82\x91", "e", "subscript e", 0, 0   },
    { "\xE1\xB6\xA6", "\xC9\xAA", "superscript small capital I", 0, 0   },
    { "\xE2\x81\xB1", "i", "superscript i", 0, 0   },
    { "\xE1\xB6\xA4", "\xC9\xA8", "superscript barred i", 0, 0   },
    { "\xE1\xB5\x92", "o", "superscript o", 0, 0   },
    { "\xE2\x82\x92", "o", "subscript o", 0, 0   },
    { "\xE1\xB5\x93", "\xC9\x94", "superscript open o", 0, 0   },
    { "\xE1\xB6\x9B", "\xC9\x92", "superscript turned alpha (open back rounded)", 0, 0   },
    { "\xE1\xB6\xB1", "\xC9\xB5", "superscript barred o", 0, 0   },
    { "\xEA\x9F\xB9", "\xC5\x93", "superscript ligature oe", 0, 0   },
    { "\xE1\xB6\xB8", "\xCA\x8A", "superscript small capital U", 0, 0   },
    { "\xE1\xB5\x98", "u", "superscript u", 0, 0   },
    { "\xE1\xB6\xB6", "\xCA\x89", "superscript u bar", 0, 0   },
    { "\xE1\xB5\x9A", "\xC9\xAF", "superscript turned m", 0, 0   },
    { "\xE1\xB6\xBA", "\xCA\x8C", "superscript turned v", 0, 0   },
    { "\xE1\xB6\xA7", "\xC9\xAA\xCC\x88", "superscript small capital barred I", 0, 0   },
    { "\xE1\xB5\xBB", "\xC9\xA8\xCC\x9E", "small capital barred i (near-close central)", 0, 0   },
    { "\xE1\xB5\xBF", "\xCA\x89\xCC\x9E", "small capital barred u (near-close central rounded)", 0, 0   },
    { "\xE1\xB4\xAE", "b", "superscript capital B", 0, 0   },
    { "\xE1\xB5\x87", "b", "superscript b", 0, 0   },
    { "\xE1\xB5\x9D", "\xCE\xB2", "superscript beta", 0, 0   },
    { "\xE1\xB5\xA6", "\xCE\xB2", "subscript beta", 0, 0   },
    { "\xE1\xB6\x9C", "c", "superscript c", 0, 0   },
    { "\xE1\xB6\x9D", "\xC9\x95", "superscript c with curl", 0, 0   },
    { "\xE1\xB5\x88", "d", "superscript d", 0, 0   },
    { "\xE1\xB6\x9E", "\xC3\xB0", "superscript eth", 0, 0   },
    { "\xE1\xB6\xBF", "\xCE\xB8", "superscript theta", 0, 0   },
    { "\xE1\xB6\xA0", "f", "superscript f", 0, 0   },
    { "\xE1\xB6\xA1", "\xC9\x9F", "superscript dotless j with stroke (palatal stop)", 0, 0   },
    { "\xE1\xB4\xB3", "\xC9\xA1", "superscript capital G", 0, 0   },
    { "\xE1\xB5\x8D", "\xC9\xA1", "superscript g", 0, 0   },
    { "\xE1\xB6\xA2", "\xC9\xA1", "superscript g", 0, 0   },
    { "\xE1\xB5\xB8", "\xCA\x9C", "superscript Cyrillic en (epiglottal trill)", 0, 0   },
    { "\xE2\x82\x95", "h", "subscript h", 0, 0   },
    { "\xE1\xB4\xB6", "j", "superscript capital J", 0, 0   },
    { "\xE2\xB1\xBC", "j", "subscript j", 0, 0   },
    { "\xE1\xB6\xA8", "\xCA\x9D", "superscript j with crossed tail (palatal fricative)", 0, 0   },
    { "\xE1\xB4\xB7", "k", "superscript capital K", 0, 0   },
    { "\xE1\xB5\x8F", "k", "superscript k", 0, 0   },
    { "\xE2\x82\x96", "k", "subscript k", 0, 0   },
    { "\xE1\xB4\xB8", "l", "superscript capital L", 0, 0   },
    { "\xE2\x82\x97", "l", "subscript l", 0, 0   },
    { "\xE1\xB6\xA9", "\xC9\xAD", "superscript l with retroflex hook", 0, 0   },
    { "\xE1\xB6\xAA", "l\xCA\xB2", "superscript l with palatal hook", 0, 0   },
    { "\xE1\xB4\xB9", "m", "superscript capital M", 0, 0   },
    { "\xE1\xB5\x90", "m", "superscript m", 0, 0   },
    { "\xE2\x82\x98", "m", "subscript m", 0, 0   },
    { "\xE1\xB6\xAC", "\xC9\xB1", "superscript m with hook", 0, 0   },
    { "\xE1\xB4\xBA", "n", "superscript capital N", 0, 0   },
    { "\xE1\xB6\xAE", "\xC9\xB2", "superscript n with left hook", 0, 0   },
    { "\xE1\xB6\xAF", "\xC9\xB3", "superscript n with retroflex hook", 0, 0   },
    { "\xE1\xB6\xB0", "\xC9\xB4", "superscript small capital N", 0, 0   },
    { "\xE1\xB4\xBB", "\xC9\xB4", "superscript capital reversed N", 0, 0   },
    { "\xE2\x82\x99", "n", "subscript n", 0, 0   },
    { "\xE1\xB5\x96", "p", "superscript p", 0, 0   },
    { "\xE2\x82\x9A", "p", "subscript p", 0, 0   },
    { "\xE1\xB4\xBF", "r", "superscript capital R", 0, 0   },
    { "\xE1\xB5\xA3", "r", "subscript r", 0, 0   },
    { "\xE1\xB5\x9B", "v", "superscript v", 0, 0   },
    { "\xE1\xB5\xA5", "v", "subscript v", 0, 0   },
    { "\xE1\xB6\xB9", "\xCA\x8B", "superscript v with hook", 0, 0   },
    { "\xE2\x82\x9B", "s", "subscript s", 0, 0   },
    { "\xE1\xB6\xB3", "\xCA\x82", "superscript s with hook", 0, 0   },
    { "\xE1\xB5\x80", "t", "superscript capital T", 0, 0   },
    { "\xE1\xB5\x97", "t", "superscript t", 0, 0   },
    { "\xE2\x82\x9C", "t", "subscript t", 0, 0   },
    { "\xE1\xB6\xB5", "t\xCA\xB2", "superscript t with palatal hook", 0, 0   },
    { "\xE2\xB1\xBD", "v", "superscript capital V", 0, 0   },
    { "\xCB\x85", "v", "subscript v (down tack)", 0, 0   },
    { "\xE2\x82\x93", "x", "subscript x", 0, 0   },
    { "\xE1\xB5\xA1", "\xCF\x87", "superscript chi", 0, 0   },
    { "\xE1\xB5\xAA", "\xCF\x87", "subscript chi", 0, 0   },
    { "\xE1\xB6\xAD", "\xC9\xB0", "superscript turned m with long leg", 0, 0   },
    { "\xE1\xB6\xBB", "z", "superscript z", 0, 0   },
    { "\xE1\xB6\xBC", "\xCA\x90", "superscript z with retroflex hook", 0, 0   },
    { "\xE1\xB6\xBD", "\xCA\x91", "superscript z with curl", 0, 0   },
    { "\xE1\xB6\xBE", "\xCA\x92", "superscript ezh", 0, 0   },
    { "\xE1\xB6\xB2", "\xC9\xB8", "superscript phi", 0, 0   },
    { "\xE1\xB6\xA3", "\xC9\xA5", "superscript turned h (palatal approximant)", 0, 0   },
    { "\xE1\xB6\x8F", "a\xCB\x9E", "rhotacised a", 0, 0   },
    { "\xE1\xB6\x90", "\xC9\x91\xCB\x9E", "rhotacised alpha", 0, 0   },
    { "\xE1\xB6\x92", "e\xCB\x9E", "rhotacised e", 0, 0   },
    { "\xE1\xB6\x93", "\xC9\x9B\xCB\x9E", "rhotacised open e", 0, 0   },
    { "\xE1\xB6\x94", "\xC9\x9C\xCB\x9E", "rhotacised reversed open e", 0, 0   },
    { "\xE1\xB6\x95", "\xC9\x99\xCB\x9E", "rhotacised schwa", 0, 0   },
    { "\xE1\xB6\x96", "\xC9\xAA\xCB\x9E", "rhotacised small capital I", 0, 0   },
    { "\xE1\xB6\x97", "\xC9\x94\xCB\x9E", "rhotacised open o", 0, 0   },
    { "\xE1\xB6\x99", "u\xCB\x9E", "rhotacised u", 0, 0   },
    { "\xE1\xB6\x98", "\xCA\x82", "esh with retroflex hook", 0, 0   },
    { "\xE1\xB6\x9A", "\xCA\x90", "ezh with retroflex hook", 0, 0   },
    { "\xE1\xB6\x80", "b\xCA\xB2", "b with palatal hook", 0, 0   },
    { "\xE1\xB6\x81", "d\xCA\xB2", "d with palatal hook", 0, 0   },
    { "\xE1\xB6\x82", "f\xCA\xB2", "f with palatal hook", 0, 0   },
    { "\xE1\xB6\x83", "\xC9\xA1\xCA\xB2", "g with palatal hook", 0, 0   },
    { "\xE1\xB6\x84", "k\xCA\xB2", "k with palatal hook", 0, 0   },
    { "\xE1\xB6\x85", "l\xCA\xB2", "l with palatal hook", 0, 0   },
    { "\xE1\xB6\x86", "m\xCA\xB2", "m with palatal hook", 0, 0   },
    { "\xE1\xB6\x87", "n\xCA\xB2", "n with palatal hook", 0, 0   },
    { "\xE1\xB6\x88", "p\xCA\xB2", "p with palatal hook", 0, 0   },
    { "\xE1\xB6\x89", "r\xCA\xB2", "r with palatal hook", 0, 0   },
    { "\xE1\xB6\x8A", "s\xCA\xB2", "s with palatal hook", 0, 0   },
    { "\xE1\xB6\x8B", "\xCA\x83\xCA\xB2", "esh with palatal hook", 0, 0   },
    { "\xE1\xB6\x8C", "v\xCA\xB2", "v with palatal hook", 0, 0   },
    { "\xE1\xB6\x8D", "x\xCA\xB2", "x with palatal hook", 0, 0   },
    { "\xE1\xB6\x8E", "z\xCA\xB2", "z with palatal hook", 0, 0   },
    { "\xE1\xB5\xAC", "b\xCB\xA0", "b with middle tilde", 0, 0   },
    { "\xE1\xB5\xAD", "d\xCB\xA0", "d with middle tilde", 0, 0   },
    { "\xE1\xB5\xAE", "f\xCB\xA0", "f with middle tilde", 0, 0   },
    { "\xE1\xB5\xAF", "m\xCB\xA0", "m with middle tilde", 0, 0   },
    { "\xE1\xB5\xB0", "n\xCB\xA0", "n with middle tilde", 0, 0   },
    { "\xE1\xB5\xB1", "p\xCB\xA0", "p with middle tilde", 0, 0   },
    { "\xE1\xB5\xB2", "r\xCB\xA0", "r with middle tilde", 0, 0   },
    { "\xE1\xB5\xB3", "\xC9\xBB\xCB\xA0", "r with fishhook and middle tilde", 0, 0   },
    { "\xE1\xB5\xB4", "s\xCB\xA0", "s with middle tilde", 0, 0   },
    { "\xE1\xB5\xB5", "t\xCB\xA0", "t with middle tilde", 0, 0   },
    { "\xE1\xB5\xB6", "z\xCB\xA0", "z with middle tilde", 0, 0   },
    { "\xE2\xB1\xBB", "\xC9\x9C", "small capital turned E (open-mid central unrounded)", 0, 0   },
    { "\xE1\xB4\xB2", "\xC9\x9C", "capital reversed E (open-mid central unrounded)", 0, 0   },
    { "\xE1\xB4\x81", "\xC3\xA6", "small capital AE", 0, 0   },
    { "\xE1\xB4\xAD", "\xC3\xA6", "capital AE modifier", 0, 0   },
    { "\xE1\xB4\x8C", "\xC9\xAC", "small capital L with stroke (voiceless lateral fricative)", 0, 0   },
    { "\xC9\x89", "\xC9\x9F", "j with stroke (palatal stop)", 0, 0   },
    { "\xE1\xB4\x9D", "\xC9\xAF", "sideways u (close back unrounded)", 0, 0   },
    { "\xE1\xB5\x99", "\xC9\xAF", "modifier sideways u", 0, 0   },
    { "\xE1\xB5\x8E", "j", "modifier small turned i (palatal approximant)", 0, 0   },
    { "\xE1\xB4\x83", "\xC9\x93", "small capital barred B (bilabial implosive)", 0, 0   },
    { "\xE1\xB4\xAF", "\xC9\x93", "capital barred B (bilabial implosive)", 0, 0   },
    { "\xC2\xA1", "\xC7\x83", "inverted exclamation (alveolar click)", 0, 0   },
    { "\xE1\x94\xBF", "\xCA\x8D", "Canadian syllabics Y (labial-velar approximant)", 0, 0   },
    { "\xEA\xAD\xA5", "\xC9\x94\xCC\x9D", "small capital omega (raised open o)", 0, 0   },
    { "\xE1\xB5\xB7", "\xC9\xA1", "turned g (voiced velar plosive)", 0, 0   },
    { "\xE1\xB4\x82", "\xC3\xA6", "small capital AE (open-mid front unrounded)", 0, 0   },
    { "\xE1\xB4\x84", "c", "small capital C (voiceless palatal stop)", 0, 0   },
    { "\xE1\xB4\x85", "d", "small capital D (voiced alveolar stop)", 0, 0   },
    { "\xE1\xB4\x8E", "\xC9\xB4", "small capital reversed N (uvular nasal)", 0, 0   },
    { "\xE1\xB4\xB5", "i", "modifier capital I", 0, 0   },
    { "\xE1\xB6\xB4", "\xCA\x83", "modifier esh (voiceless postalveolar fricative)", 0, 0   },
    { "\xCB\x81", "\xCA\x95", "reversed glottal stop (voiced pharyngeal fricative)", 0, 0   },
    { "\xEA\x9C\x9D", "\xC7\x83", "modifier exclamation (alveolar click)", 0, 0   },
    { "\xEA\xAD\x9C", "\xC9\xA7", "modifier heng (voiceless palatal-velar fricative)", 0, 0   },
    { "\xEA\xAD\x9E", "l\xCB\xA4", "modifier l with middle tilde (pharyngealised l)", 0, 0   },
    { "\xE2\x81\xBD", "", "superscript left parenthesis (optional)", 0, 0   },
    { "\xE2\x81\xBE", "", "superscript right parenthesis (optional)", 0, 0   },
    { "\xE2\x82\x8D", "", "subscript left parenthesis (optional)", 0, 0   },
    { "\xE2\x82\x8E", "", "subscript right parenthesis (optional)", 0, 0   },
    { "\xE2\x97\x8C", "", "dotted circle (placeholder)", 0, 0   },
    /* MODS modifiers that also stand alone as superscript letters */
    { "\xE1\xB5\x89", "e", "superscript e", 0, 0   },
    { "\xE1\xB5\x8A", "\xC9\x99", "superscript schwa", 0, 0   },
    { "\xE1\xB5\xA4", "u", "subscript u", 0, 0   },
    { "\xE1\xB5\xA2", "i", "subscript i", 0, 0   },
    { "\xE1\xB4\xB0", "d", "superscript capital D", 0, 0   },
    { "\xE1\xB4\xAC", "a", "superscript capital A", 0, 0   },
    { "\xE1\xB4\xBC", "o", "superscript capital O", 0, 0   },
    { "\xE1\xB4\xBE", "p", "superscript capital P", 0, 0   },
    { "\xE1\xB5\x81", "u", "superscript capital U", 0, 0   },
    { "\xE1\xB5\x82", "w", "superscript capital W", 0, 0   },
    { "\xE1\xB5\x93", "\xC9\x94", "superscript open o", 0, 0   },
    { "\xE1\xB5\x8B", "\xC9\x9B", "superscript open e (nasal release)", 0, 0   },
    { "\xE1\xB5\x91", "\xC5\x8B", "superscript eng (nasal release)", 0, 0   },
    /* standard IPA superscript letters, standalone forms */
    { "\xCA\xB0", "h", "superscript h", 0, 0   },
    { "\xCA\xB1", "\xC9\xA6", "superscript h with hook (breathy)", 0, 0   },
    { "\xCA\xB2", "j", "superscript j (palatalised)", 0, 0   },
    { "\xCA\xB3", "r", "superscript r", 0, 0   },
    { "\xCA\xB4", "\xC9\xB9", "superscript turned r (alveolar approximant)", 0, 0   },
    { "\xCA\xB5", "\xC9\xBB", "superscript turned r with hook (retroflex)", 0, 0   },
    { "\xCA\xB6", "\xCA\x80", "superscript small capital inverted R (uvular)", 0, 0   },
    { "\xCA\xB7", "w", "superscript w (labialised)", 0, 0   },
    { "\xCA\xB8", "j", "superscript y (palatal)", 0, 0   },
    { "\xCB\xA0", "\xC9\xA3", "superscript gamma (velarised)", 0, 0   },
    { "\xCB\xA1", "l", "superscript l (lateral release)", 0, 0   },
    { "\xCB\xA2", "s", "superscript s (fricative release)", 0, 0   },
    { "\xCB\xA3", "x", "superscript x (fricative release)", 0, 0   },
    { "\xCB\xA4", "\xCA\x95", "superscript reversed glottal stop (pharyngealised)", 0, 0   },
    { "\xE2\x81\xBF", "n", "superscript n (nasal release)", 0, 0   },
    { "\xE1\xB5\x8C", "\xC9\x9C", "superscript reversed open e", 0, 0   },
    { "\xE1\xB6\xB7", "\xCA\x8A", "superscript upsilon (near-close back)", 0, 0   },
};

/* --- module: withdrawn / obsolete IPA symbols --- */
static const Alias ALIAS_WITHDRAWN[] = {
    { "\xC6\x8D", "z\xCA\xB7", "labialized vd alveolo-dental fricative", 0, 0   },  /* ƍ -> zʷ */
    { "\xCF\x83", "s\xCA\xB7", "labialized vl alveolo-dental fricative", 0, 0   },  /* σ -> sʷ */
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
    { "\xCA\xAA", "\xC9\xAC\xCD\xA1s", "vl alveolar lateral affricate (LS digraph)", 0, 0   }, /* ʪ -> ɬ͡s */
    { "\xCA\xAB", "\xC9\xAE\xCD\xA1z", "vd alveolar lateral affricate (LZ digraph)", 0, 0   }, /* ʫ -> ɮ͡z */
    { "\xCA\x87", "\xC7\x80", "dental click (superseded 1989)", 0, 0   },           /* ʇ -> ǀ */
    { "\xCA\x97", "\xC7\x83", "alveolar click (superseded 1989)", 0, 0   },         /* ʗ -> ǃ */
    { "\xCA\x96", "\xC7\x81", "alveolar lateral click (superseded 1989)", 0, 0   }, /* ʖ -> ǁ */
    { "\xCA\x9E", "\xC7\x83", "velar click (withdrawn)", 0, 1   },                  /* ʞ -> ǃ */
    { "\xC6\xA5", "\xC9\x93\xCC\xA5", "vl bilabial implosive (withdrawn 1993)", 0, 0   },  /* ƥ -> ɓ̥ */
    { "\xC6\xAD", "\xC9\x97\xCC\xA5", "vl dental/alveolar implosive (withdrawn 1993)", 0, 0 }, /* ƭ -> ɗ̥ */
    { "\xC6\x88", "\xCA\x84\xCC\x8A", "vl palatal implosive (withdrawn 1993)", 0, 0   },    /* ƈ -> ʄ̊ */
    { "\xC6\x99", "\xC9\xA0\xCC\xA5", "vl velar implosive (withdrawn 1993)", 0, 0   },      /* ƙ -> ɠ̥ */
    { "\xCA\xA0", "\xCA\x9B\xCC\xA5", "vl uvular implosive (withdrawn 1993)", 0, 0   },     /* ʠ -> ʛ̥ */
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
    { "\xC9\xBF", "\xC9\xB9\xCC\xAA", "apical dental unrounded vowel", 0, 0   },     /* ɿ -> ɹ̪ */
    { "\xCA\x85", "\xC9\xBB", "apical retroflex unrounded vowel", 0, 0   },           /* ʅ -> ɻ */
    { "\xCA\xAE", "\xC9\xB9\xCC\xAA\xCA\xB7", "apical dental rounded vowel", 0, 0   }, /* ʮ -> ɹ̪ʷ */
    { "\xCA\xAF", "\xC9\xBB\xCA\xB7", "apical retroflex rounded vowel", 0, 0   },     /* ʯ -> ɻʷ */
    { "\xE1\xB4\x80", "a\xCC\x88", "open central vowel", 0, 0   },                   /* ᴀ -> ä */
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
    /* Polish orthography (conflicts with Americanist values; enable
     * --polish to prefer the Polish readings) */
    { "\xC4\x8D", "t\xCD\xA1\xCA\x82", "voiceless retroflex affricate (c-caron, Polish)", 0, 0   }, /* č -> ʈ͡ʂ */
    { "\xC5\xA1", "\xCA\x82", "voiceless retroflex fricative (s-caron, Polish)", 0, 0   },         /* š -> ʂ */
    { "\xC5\xBE", "\xCA\x90", "voiced retroflex fricative (z-caron, Polish)", 0, 0   },            /* ž -> ʐ */
    { "\xC5\x82", "w", "labial-velar approximant (l-stroke, Polish)", 0, 0   },                   /* ł -> w */
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
    { "\xC8\xB8", "b\xCC\xAA", "vd labiodental plosive", 0, 0   },                   /* ȸ -> b̪ */
};

/* --- module: OED / dictionary conventions --- */
static const Alias ALIAS_OED[] = {
    { "\xE1\xB5\xBB", "\xC9\xA8\xCC\x9E", "near-close central unrounded vowel", 0, 0   }, /* ᵻ -> ɨ̞ */
    { "\xE1\xB5\xBF", "\xCA\x89\xCC\x9E", "near-close central rounded vowel", 0, 0   },   /* ᵿ -> ʉ̞ */
};

/* module registry */
typedef struct { const Alias *tab; int n; const char *name; int school; } AliasModule;
/* school: 1 = school-of-linguistics symbols (Americanist, Sinologist, …):
 * resolved by default with a warning; pass --<name> to enable without
 * warning. 0 = generic/withdrawn/equiv/uppercase (always on). */

static const AliasModule ALIAS_MODULES[] = {
    { ALIAS_GENERIC,     (int)(sizeof(ALIAS_GENERIC)     / sizeof(Alias)), "generic",     0 },
    { ALIAS_EQUIV,       (int)(sizeof(ALIAS_EQUIV)       / sizeof(Alias)), "equiv",       0 },
    { ALIAS_WITHDRAWN,   (int)(sizeof(ALIAS_WITHDRAWN)   / sizeof(Alias)), "withdrawn",   0 },
    { ALIAS_AMERICANIST, (int)(sizeof(ALIAS_AMERICANIST) / sizeof(Alias)), "americanist", 1 },
    { ALIAS_SINOLOGIST,  (int)(sizeof(ALIAS_SINOLOGIST)  / sizeof(Alias)), "sinologist",  1 },
    { ALIAS_INDOLOGIST,  (int)(sizeof(ALIAS_INDOLOGIST)  / sizeof(Alias)), "indologist",  1 },
    { ALIAS_POLISH,      (int)(sizeof(ALIAS_POLISH)      / sizeof(Alias)), "polish",      1 },
    { ALIAS_TEUTHONISTA, (int)(sizeof(ALIAS_TEUTHONISTA) / sizeof(Alias)), "teuthonista", 1 },
    { ALIAS_KOREANOLOGIST,(int)(sizeof(ALIAS_KOREANOLOGIST)/sizeof(Alias)), "koreanologist", 1 },
    { ALIAS_JAPANOLOGIST,(int)(sizeof(ALIAS_JAPANOLOGIST)/sizeof(Alias)), "japanologist", 1 },
    { ALIAS_AFRICANIST,  (int)(sizeof(ALIAS_AFRICANIST)  / sizeof(Alias)), "africanist",  1 },
    { ALIAS_OED,         (int)(sizeof(ALIAS_OED)         / sizeof(Alias)), "oed",         1 },
    { ALIAS_UPPERCASE,   (int)(sizeof(ALIAS_UPPERCASE)   / sizeof(Alias)), "uppercase",   0 },
};
#define N_ALIAS_MODULES ((int)(sizeof(ALIAS_MODULES) / sizeof(ALIAS_MODULES[0])))

/* per-module enable flags: 0 = off (school symbols warn), >0 = enable
 * order (earlier --<name> wins when a symbol appears in several) */
static int g_alias_on[N_ALIAS_MODULES];
static int g_alias_pri_max = 0;
/* warned-once bookkeeping: warn per symbol, not per occurrence */
static const char *g_alias_warned[256];
static int g_alias_n_warned = 0;

static IPA2VEC_MAYBE_UNUSED void enable_alias_module(const char *name)
{
    for (int m = 0; m < N_ALIAS_MODULES; m++)
        if (strcmp(ALIAS_MODULES[m].name, name) == 0 && g_alias_on[m] == 0)
            g_alias_on[m] = ++g_alias_pri_max;
}

/* match one module's entries; returns the alias or NULL */
static IPA2VEC_MAYBE_UNUSED const Alias *match_module_alias(int m,
                                                            const char *s,
                                                            int has_mods)
{
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
    return NULL;
}

/* one-line warning listing every disabled school that contains the
 * symbol, e.g. "using symbol 'ł' from americanist, polish — enable
 * with --americanist --polish". Warned once per symbol. */
static IPA2VEC_MAYBE_UNUSED void warn_school_symbol(const char *sym)
{
    for (int w = 0; w < g_alias_n_warned; w++)
        if (g_alias_warned[w] == sym) return;
    if (g_alias_n_warned >= 256) return;
    char mods[256] = "";
    char flags[256] = "";
    int first = 1, n = 0;
    for (int m = 0; m < N_ALIAS_MODULES; m++) {
        if (!ALIAS_MODULES[m].school || g_alias_on[m] != 0) continue;
        const Alias *a = match_module_alias(m, sym, 0);
        if (!a || strcmp(a->sym, sym) != 0) continue;
        if (!first) { strncat(mods, ", ", sizeof(mods) - strlen(mods) - 1); }
        strncat(mods, ALIAS_MODULES[m].name, sizeof(mods) - strlen(mods) - 1);
        strncat(flags, " --", sizeof(flags) - strlen(flags) - 1);
        strncat(flags, ALIAS_MODULES[m].name, sizeof(flags) - strlen(flags) - 1);
        first = 0; n++;
    }
    if (n == 0) return;
    g_alias_warned[g_alias_n_warned++] = sym;
    fprintf(stderr,
            "ipa2vec: warning: using symbol '%s' from %s — enable with%s\n",
            sym, mods, flags);
}

static const Alias *lookup_alias(const char *s, int has_mods)
{
    /* pass 1: enabled modules, in enable order */
    for (int pri = 1; pri <= g_alias_pri_max; pri++)
        for (int m = 0; m < N_ALIAS_MODULES; m++)
            if (g_alias_on[m] == pri) {
                const Alias *a = match_module_alias(m, s, has_mods);
                if (a) return a;
            }
    /* pass 2: disabled modules, table order (school ones warn) */
    for (int m = 0; m < N_ALIAS_MODULES; m++) {
        if (g_alias_on[m] != 0) continue;
        const Alias *a = match_module_alias(m, s, has_mods);
        if (a) {
            if (ALIAS_MODULES[m].school)
                warn_school_symbol(a->sym);
            return a;
        }
    }
    return NULL;
}

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
    { "t", "\u0255", "\x74\xCD\xA1\xC9\x95" }, /* tɕ -> t͡ɕ */
    { "d", "\u0291", "\x64\xCD\xA1\xCA\x91" }, /* dʑ -> d͡ʑ */
    { "\u0236", "\u0255", "\x74\xCD\xA1\xC9\x95" }, /* ȶɕ -> t͡ɕ (curl notation) */
    { "\u0221", "\u0291", "\x64\xCD\xA1\xCA\x91" }, /* ȡʑ -> d͡ʑ */
    { "\u0288", "\u0282", "\xCA\x88\xCD\xA1\xCA\x82" }, /* ʈʂ -> ʈ͡ʂ */
    { "\u0256", "\u0290", "\xC9\x96\xCD\xA1\xCA\x90" }, /* ɖʐ -> ɖ͡ʐ */
    { "t", "\u0282", "\xCA\x88\xCD\xA1\xCA\x82" },      /* tʂ -> ʈ͡ʂ (t-notation for retroflex affricate) */
    { "d", "\u0290", "\xC9\x96\xCD\xA1\xCA\x90" },      /* dʐ -> ɖ͡ʐ */
    { "t", "\u026C", NULL },          /* tɬ (synthesize) */
    { "d", "\u026E", NULL },          /* dɮ (synthesize) */
    { "c", "\u00E7", NULL },          /* cç (synthesize) */
    { "\u025F", "\u029D", NULL },     /* ɟʝ (synthesize) */
    { "k", "x", "\x6B\xCD\xA1x" },    /* kx -> k͡x */
    { "q", "\u03C7", "\x71\xCD\xA1\xCF\x87" }, /* qχ -> q͡χ */
    { "t", "\u03B8", NULL },          /* tθ (synthesize) */
    { "t", "f", NULL },               /* tf (synthesize) */
};
#define NNOLIG ((int)(sizeof(NOLIG) / sizeof(NOLIG[0])))

/* ------------------------------------------------------------------ */
/* ExtIPA base segments not covered by IPA_VECTORS.md                  */
/* (clinical phonetics additions; vectors derived from the closest     */
/*  articulatory description)                                          */
/* ------------------------------------------------------------------ */

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
            if (EXTRA_SCHOOL[i] >= 0 &&
                !g_alias_on[EXTRA_SCHOOL[i]]) {
                /* school-gated base (e.g. Sinologist ȶ ȡ ȵ ȴ):
                 * resolve but warn like school alias symbols */
                const char *nm = ALIAS_MODULES[EXTRA_SCHOOL[i]].name;
                int seen = 0;
                for (int w = 0; w < g_alias_n_warned; w++)
                    if (g_alias_warned[w] == EXTRA_BASE[i].ipa) { seen = 1; break; }
                if (!seen && g_alias_n_warned < 256) {
                    g_alias_warned[g_alias_n_warned++] = EXTRA_BASE[i].ipa;
                    fprintf(stderr,
                            "ipa2vec: warning: using %s symbol '%s' — enable with --%s\n",
                            nm, EXTRA_BASE[i].ipa, nm);
                }
            }
            return &EXTRA_BASE[i];
        }
    }
    return NULL;
}

/* feature name of any base (SEG_TABLE or EXTRA_BASE) */
static IPA2VEC_MAYBE_UNUSED const char *base_name(const SegEntry *b)
{
    if (b >= SEG_TABLE && b < SEG_TABLE + NSEG)
        return NAME_TABLE[b - SEG_TABLE];
    return EXTRA_NAMES[b - EXTRA_BASE];
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
        int pre_tone[4];     /* tone values collected preposed (5-level, vec 1) */
        int npre_tone = 0;
        int pre_tone_digit = 0;   /* superscript-digit pitch seen (pitch_*) */
        int pre_tone_letter = 0;  /* 5-level letter seen (tone_*) */
        int pre_sandhi[4];   /* sandhi letters (vec 2) */
        int npre_sandhi = 0;
        /* 3-D vector (vec 3): dim0 step, dim1 global, dim2 class */
        double pre_vec3[3] = { 0, 0, 0 };
        int pre_vec3_set = 0;
        int pre_consumed = 0;   /* bytes consumed by preposed marks */
        while (p < end && pre_consumed < 16) {
            unsigned long cp;
            int k = utf8_decode(p, &cp);
            if (!k) break;
            const ModRec *m = find_mod(cp);
            if (!m) break;
            if (m->tone_kind != 0) {
                if (m->tone_kind == 1) {
                    if (npre_tone < 4) {
                        pre_tone[npre_tone++] = (int)m->val[0];
                        if (m->latin && strncmp(m->latin, "pitch_", 6) == 0)
                            pre_tone_digit = 1;
                        else
                            pre_tone_letter = 1;
                        p += k; pre_consumed += k;
                        continue;
                    }
                } else if (m->tone_kind == 5) {
                    if (npre_sandhi < 4) { pre_sandhi[npre_sandhi++] = (int)m->val[0]; p += k; pre_consumed += k; continue; }
                } else {
                    /* 3-D vector component */
                    if (m->tone_kind == 3) pre_vec3[0] = m->val[0];
                    else if (m->tone_kind == 4) pre_vec3[1] = m->val[1];
                    else pre_vec3[2] = m->val[0];
                    pre_vec3_set = 1;
                    p += k; pre_consumed += k;
                    continue;
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
                    /* skip preposed airstream modifiers (ˀ glottal onset,
                     * ᵑ nasal click release): they belong to the NEXT
                     * segment, appending them would break the repl */
                    if (m && m->tone_kind == 0 && !is_ligature_cp(cp) &&
                        !(m->tier == TIER_AIRSTREAM && m->air < 0)) {
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
                /* consumed only modifiers/tone marks with no base following:
                 * some of them double as standalone letters (superscript
                 * forms like ᵋ = ɛ, ᵑ = ŋ); try the alias path first */
                const unsigned char *pre_p = p - pre_consumed;
                size_t probe_len = 0;
                {
                    const Alias *probe = NULL;
                    for (int m = 0; m < N_ALIAS_MODULES && !probe; m++) {
                        for (int i = 0; i < ALIAS_MODULES[m].n; i++) {
                            const Alias *a = &ALIAS_MODULES[m].tab[i];
                            size_t L = strlen(a->sym);
                            if (a->repl && strncmp((const char*)pre_p, a->sym, L) == 0) {
                                probe = a; probe_len = L; break;
                            }
                        }
                    }
                    (void)probe;
                }
                const Alias *fal = lookup_alias((const char *)pre_p, 0);
                if (fal) {
                    char buf[256];
                    snprintf(buf, sizeof(buf), "%s", fal->repl);
                    IrTok tmp[MAX_TOKS];
                    int tn = 0;
                    char terr[256];
                    if (lex(buf, tmp, &tn, terr, sizeof(terr)) == 0) {
                        fprintf(stderr, "ipa2vec: %s: '%s' -> %s (%s)\n",
                                fal->warn ? "warning" : "note",
                                fal->sym, fal->repl, fal->note);
                        if (n + tn >= MAX_TOKS) goto full;
                        for (int j = 0; j < tn; j++)
                            out[n++] = tmp[j];
                        p = pre_p + (probe_len ? probe_len : strlen(fal->sym));
                        continue;
                    }
                }
                /* standalone tone marks (↗ ↘ ꜛ ꜜ, tone classes): no segment
                 * needed — record the 3-D tone vector on a null segment
                 * (silent, v=0) so prosodic marks survive the parse */
                if (pre_vec3_set) {
                    if (n >= MAX_TOKS) goto full;
                    IrTok t;
                    t.kind = TK_BASE;
                    t.preposed = 0;
                    t.ipa = "";
                    t.latin = "tone-only";
                    t.tier = TIER_COUNT;
                    t.mod = NULL;
                    t.seg = NULL;
                    t.consumed = pre_consumed;
                    for (int g = 0; g < 3; g++) { t.tkind[g] = 0; t.tone[g][0] = t.tone[g][1] = t.tone[g][2] = NAN; }
                    t.tkind[2] = 2;
                    for (int d = 0; d < 3; d++)
                        t.tone[2][d] = pre_vec3[d];
                    out[n++] = t;
                    p += pre_consumed;
                    continue;
                }
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
        for (int g = 0; g < 3; g++) { t.tkind[g] = 0; t.tone[g][0] = t.tone[g][1] = t.tone[g][2] = NAN; }
        out[n++] = t;
        int seg_base_idx = n - 1;   /* base token of this segment: tone
                                     * marks bind here even when modifiers
                                     * follow (they occupy later tokens) */
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
                for (int g = 0; g < 3; g++) { rt.tkind[g] = 0; rt.tone[g][0] = rt.tone[g][1] = rt.tone[g][2] = NAN; }
                out[n++] = rt;
                p += synth_rel_len;
            }
        }

        /* tone bookkeeping for this segment: 5-level letters collected here,
         * then grouped on segment end. */
        int tonebuf[8], ntone = 0;
        int sandhibuf[8], nsandhi = 0;
        int tone_digit = pre_tone_digit;   /* superscript-digit pitch seen */
        int tone_letter = pre_tone_letter; /* 5-level letter seen */
        for (int i = 0; i < npre_tone; i++) tonebuf[ntone++] = pre_tone[i];
        for (int i = 0; i < npre_sandhi; i++) sandhibuf[nsandhi++] = pre_sandhi[i];
        if (pre_vec3_set) {
            /* 3-D tone vector preposed */
            out[seg_base_idx].tkind[2] = 2;
            for (int d = 0; d < 3; d++)
                out[seg_base_idx].tone[2][d] = pre_vec3[d];
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
                /* tone mark: store into segment tone state.
                 * Three extra vectors:
                 *   tone[0] 5-level / single tone (kind 1)
                 *   tone[1] sandhi (kind 5)
                 *   tone[2] 3-D (kind 2 class, 3 step, 4 global) */
                if (m->tone_kind == 1) {           /* 5-level letter -> vec 1 */
                    if (ntone < 8) {
                        tonebuf[ntone++] = (int)m->val[0];
                        if (m->latin && strncmp(m->latin, "pitch_", 6) == 0)
                            tone_digit = 1;
                        else
                            tone_letter = 1;
                    }
                } else if (m->tone_kind == 5) {    /* sandhi letter -> vec 2 */
                    if (nsandhi < 8) sandhibuf[nsandhi++] = (int)m->val[0];
                } else {
                    /* 3-D vector (tone[2]), default (0,0,0):
                     *   dim 0: upstep/downstep (kind 3, ±1)
                     *   dim 1: global rise/fall (kind 4, ±1)
                     *   dim 2: Chinese class (kind 2, ±1..±4) */
                    out[seg_base_idx].tkind[2] = 2;
                    if (m->tone_kind == 3) {
                        out[seg_base_idx].tone[2][0] = m->val[0];
                    } else if (m->tone_kind == 4) {
                        out[seg_base_idx].tone[2][1] = m->val[1];
                    } else { /* kind 2: Chinese tone class */
                        out[seg_base_idx].tone[2][2] = m->val[0];
                    }
                }
                p += k;
                continue;
            }
            if (is_ligature_cp(cp)) {
                /* tie: next must be a base.  If the pair is a NOLIG
                 * affricate (e.g. t+ʂ -> ʈ͡ʂ, d+ʐ -> ɖ͡ʐ), use the tied
                 * form's segments so the closure carries the right place
                 * (retroflex ʈ/ɖ, not alveolar t/d). */
                p += k;
                int c2 = 0;
                const SegEntry *b2 = match_base_ex((const char *)p, &c2);
                if (!b2) {
                    snprintf(err, errsz, "ligature tie without second segment at offset %d",
                             (int)(p - (const unsigned char*)input));
                    return -1;
                }
                const SegEntry *closure = out[n-1].seg;
                const SegEntry *release = b2;
                int rel_len = c2;
                for (int nl = 0; nl < NNOLIG; nl++) {
                    const Nolig *g = &NOLIG[nl];
                    if (g->tied &&
                        closure && strcmp(closure->ipa, g->a) == 0 &&
                        strcmp(release->ipa, g->b) == 0) {
                        /* re-parse the tied spelling (e.g. ʈ͡ʂ) */
                        const SegEntry *t2 = NULL;
                        int tc = 0;
                        const unsigned char *tp = (const unsigned char*)g->tied;
                        t2 = match_base_ex((const char*)tp, &tc);
                        /* only rewrite when the tied form is a single base
                         * that differs from the closure (t+ʂ -> ʈ͡ʂ is a
                         * place fix; t+s -> t͡s already exists as t͡s) */
                        if (t2 && strcmp(t2->ipa, closure->ipa) != 0) {
                            /* tied form is a single base: swap the closure
                             * token in place, preserving its tone state */
                            out[n-1].seg = t2;
                            out[n-1].ipa = t2->ipa;
                            out[n-1].latin = (t2 >= SEG_TABLE && t2 < SEG_TABLE + NSEG)
                                      ? NAME_TABLE[t2 - SEG_TABLE]
                                      : EXTRA_NAMES[t2 - EXTRA_BASE];
                            p += rel_len;
                            goto tie_done;
                        }
                        break;
                    }
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
                r.ipa = release->ipa;
                r.latin = (release >= SEG_TABLE && release < SEG_TABLE + NSEG)
                          ? NAME_TABLE[release - SEG_TABLE]
                          : EXTRA_NAMES[release - EXTRA_BASE];
                r.tier = TIER_COUNT;
                r.mod = NULL;
                r.seg = release;
                r.consumed = rel_len;
                out[n++] = r;
                p += rel_len;
                continue;
            tie_done:
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

        /* flush 5-level tone letters into the three extra vectors:
         *   vec 1 (tone[0]) single tone: 1..3 letters
         *   vec 2 (tone[1]) tone sandhi: 4+ letters overflow here (and ꜖꜕꜔꜓꜒)
         *   vec 3 (tone[2]) 3-D: (upstep, global, class), default (0,0,0) */
        if (out[seg_base_idx].kind == TK_BASE) {
            if (ntone >= 1) {
                out[seg_base_idx].tkind[0] = 1;
                int c = ntone < 3 ? ntone : 3;
                for (int k = 0; k < c; k++)
                    out[seg_base_idx].tone[0][k] = tonebuf[k];
                if (ntone == 1)
                    out[seg_base_idx].tone[0][1] = tonebuf[0];   /* level tone */
                if (tone_digit && tone_letter)
                    fprintf(stderr,
                            "ipa2vec: warning: mixing superscript digits (¹²³⁴⁵) and tone letters (˩˨˧˦˥) for the same segment\n");
                /* 4+ letters: remainder becomes tone sandhi (vec 2) */
                if (ntone > 3) {
                    out[seg_base_idx].tkind[1] = 1;
                    int r = ntone - 3;
                    int rc = r < 3 ? r : 3;
                    for (int k = 0; k < rc; k++)
                        out[seg_base_idx].tone[1][k] = tonebuf[3 + k];
                    if (r == 1)
                        out[seg_base_idx].tone[1][1] = tonebuf[3];
                }
            }
            if (nsandhi >= 1) {
                out[seg_base_idx].tkind[1] = 1;
                int c = nsandhi < 3 ? nsandhi : 3;
                for (int k = 0; k < c; k++)
                    out[seg_base_idx].tone[1][k] = sandhibuf[k];
                if (nsandhi == 1)
                    out[seg_base_idx].tone[1][1] = sandhibuf[0];
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
            if (base) {
                memcpy(out.v, base->v, sizeof(out.v));
                out.airstream = base->airstream;
            } else {
                /* tone-only segment (standalone ↗ ↘ ꜛ ꜜ, tone class):
                 * silent, zero vector */
                memset(out.v, 0, sizeof(out.v));
                out.airstream = 0;
            }
            out.note[0] = 0;
            for (int g = 0; g < 3; g++) {
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
                        /* nasality spelling rules (input tolerance):
                         *  - nasalising a nasal consonant (ñ) is redundant
                         *    and lowers its nasality (usually a place
                         *    shift: ñ -> ɲ)
                         *  - vowels take ◌̃, oral consonants take ⁿ */
                        int base_nasal = base && base->v[6] >= 0.5;
                        int base_vowel = base && base->v[14] >= 0.5;
                        if (l2[i].mod->apply == mod_nasal && !out.note[0]) {
                            if (base_nasal) {
                                const char *guess = NULL;
                                if (strcmp(base->ipa, "n") == 0) guess = "\xC9\xB2";     /* ɲ */
                                else if (strcmp(base->ipa, "m") == 0) guess = "\xC9\xB1"; /* ɱ */
                                else if (strcmp(base->ipa, "\xC5\x8B") == 0) guess = "\xC9\xB4"; /* ŋ -> ɴ */
                                if (guess)
                                    fprintf(stderr,
                                            "ipa2vec: warning: nasalising the nasal %s is redundant — did you mean %s?\n",
                                            base->ipa, guess);
                                else
                                    fprintf(stderr,
                                            "ipa2vec: warning: nasalising the nasal %s is redundant\n",
                                            base->ipa);
                            } else if (!base_vowel) {
                                fprintf(stderr,
                                        "ipa2vec: warning: oral consonant %s nasalises with ◌ⁿ, not ◌̃\n",
                                        base->ipa);
                            }
                        } else if (l2[i].mod->apply == mod_nasal_rel && !out.note[0]) {
                            if (base_vowel)
                                fprintf(stderr,
                                        "ipa2vec: warning: vowel %s nasalises with ◌̃, not ◌ⁿ\n",
                                        base->ipa);
                        }
                        apply_voicing_mod(out.v, l2[i].mod, base);
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
                                apply_voicing_mod(out.v, l2[j].mod, rel);
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
    /* EXTRA_BASE entries (extIPA + school-gated bases like the
     * Sinologist curl letters ȶ ȡ ȵ ȴ) are valid reverse targets too;
     * skip school entries whose module is not enabled */
    for (int i = 0; i < N_EXTRA; i++) {
        if (EXTRA_SCHOOL[i] >= 0 && !g_alias_on[EXTRA_SCHOOL[i]])
            continue;
        double d = seg_dist(v, EXTRA_BASE[i].v);
        if (d < bestd) { bestd = d; best = NSEG + i; }
    }
    *out = (best < NSEG) ? &SEG_TABLE[best] : &EXTRA_BASE[best - NSEG];
    *outd = bestd;
}

/* reverse-fit narrowness knobs: max modifiers per segment and the
 * minimum relative distance gain a modifier must achieve to be kept.
 * Adjustable at runtime (--width) so the output can range from broad
 * (few diacritics) to narrow (all that help). */
#define IPA2VEC_FIT_MAX_MODS   10     /* hard cap; array bound below */
#define IPA2VEC_FIT_MIN_GAIN   0.0
static int    g_fit_max_mods = 6;
static double g_fit_min_gain = 0.015;

static IPA2VEC_MAYBE_UNUSED int mod_priority(const ModRec *m);   /* fwd: canonical order (see below) */

static IPA2VEC_MAYBE_UNUSED int fit_modifiers (const double target[NDIM], const SegEntry *base,
                         const ModRec *mods[IPA2VEC_FIT_MAX_MODS])
{
    /* The greedy search picks the best single modifier each round, but the
     * chosen set must be applied in the SAME canonical order (combining
     * marks first, then spacing superscripts, each by feature tier) that
     * the parser will use when the emitted IPA is re-parsed.  Applying
     * them in greedy pick order would give a different vector than the
     * emitted string reproduces (order matters for interacting mods like
     * rnd_more vs whistled on v[1]).  So the chosen list is kept sorted
     * by mod_priority and every evaluation re-applies the whole set. */
    int n = 0;
    /* nasality spelling depends on the base: vowels AND nasal
     * consonants use ◌̃ (mod_nasal); oral consonants use the
     * superscript ⁿ (mod_nasal_rel, nasal release).  During fitting,
     * allow only the matching one so the output never writes ̃ⁿ
     * together and vowels never get a release mark. */
    int base_nasal = (base->v[6] >= 0.5);
    int base_is_vowel = (base->v[14] >= 0.5);
    int maxmods = g_fit_max_mods < IPA2VEC_FIT_MAX_MODS
                  ? g_fit_max_mods : IPA2VEC_FIT_MAX_MODS;
    for (int round = 0; round < maxmods; round++) {
        int besti = -1;
        double trial[NDIM];
        double curd = 1e300;
        /* distance of the current chosen set, applied canonically */
        if (n == 0) {
            curd = seg_dist(target, base->v);
        } else {
            memcpy(trial, base->v, sizeof(trial));
            for (int k = 0; k < n; k++)
                apply_voicing_mod(trial, mods[k], base);
            curd = seg_dist(target, trial);
        }
        double bestd = curd;
        for (int i = 0; i < NMODS; i++) {
            if (!MODS[i].apply || is_ligature_cp(MODS[i].cp)) continue;
            if (!MODS[i].reverse) continue;   /* input-tolerance only */
            /* skip modifiers already chosen, or with the same effect */
            int used = 0;
            for (int k = 0; k < n; k++)
                if (mods[k]->apply == MODS[i].apply) { used = 1; break; }
            if (used) continue;
            /* vowel/nasal -> ◌̃ only; oral consonant -> ⁿ only */
            if (MODS[i].apply == mod_nasal &&
                !(base_is_vowel || base_nasal)) continue;
            if (MODS[i].apply == mod_nasal_rel &&
                (base_is_vowel || base_nasal)) continue;
            /* evaluate: base + mods[0..n-1] + candidate, applied in
             * canonical order (the order the emitted IPA re-parses in) */
            const ModRec *ins[IPA2VEC_FIT_MAX_MODS + 1];
            int ni = 0, placed = 0;
            for (int k = 0; k < n; k++) {
                if (!placed && mod_priority(&MODS[i]) < mod_priority(mods[k]))
                    { ins[ni++] = &MODS[i]; placed = 1; }
                ins[ni++] = mods[k];
            }
            if (!placed) ins[ni++] = &MODS[i];
            memcpy(trial, base->v, sizeof(trial));
            for (int k = 0; k < ni; k++)
                apply_voicing_mod(trial, ins[k], base);
            double d = seg_dist(target, trial);
            if (d < bestd - 1e-9) { bestd = d; besti = i; }
        }
        if (besti < 0) break;
        /* significance gate: require at least g_fit_min_gain relative
         * improvement over the previous distance (before this round) */
        if (curd > 1e-12 && (curd - bestd) / curd < g_fit_min_gain)
            break;
        /* insert the winner in canonical position */
        const ModRec *ins[IPA2VEC_FIT_MAX_MODS + 1];
        int ni = 0, placed = 0;
        for (int k = 0; k < n; k++) {
            if (!placed && mod_priority(&MODS[besti]) < mod_priority(mods[k]))
                { ins[ni++] = &MODS[besti]; placed = 1; }
            ins[ni++] = mods[k];
        }
        if (!placed) ins[ni++] = &MODS[besti];
        for (int k = 0; k < ni; k++) mods[k] = ins[k];
        n = ni;
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
    /* descender letters (below-line stroke): g ɡ ɢ ɠ ɣ ŋ ɳ ɲ ɴ ɟ ʝ ɧ ʡ ʢ
     * ɮ ɻ ɽ ꞎ j ȷ q ɦ — on these, below-marks go above (ŋ̥ -> ŋ̊) */
    static const char *desc[] = {
        "g", "\xc9\xa1", "\xc9\xa2", "\xc9\xa0", "\xc9\xa3",
        "\xc5\x8b", "\xc9\xb3", "\xc9\xb2", "\xc9\xb4",
        "\xc9\x9f", "\xca\x9d", "\xc9\xa7", "\xca\xa1", "\xca\xa2",
        "\xc9\xae", "\xc9\xbb", "\xc9\xbd", "\xea\x9e\xae",
        "j", "\xc8\xb7", "q", "\xc9\xa6",
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
/* A modifier is "spacing" when its emitted glyph is a modifier-letter /
 * superscript character that advances the cursor horizontally (ʼ ʰ ʲ ʷ
 * ˠ ˤ ˡ ˢ ˣ ˞ ː ˑ ʳ …) rather than a zero-width combining mark that
 * overlays the base letter.  Such characters are typographically new
 * characters, not marks on the base, so they are emitted AFTER all
 * combining marks.  (mod_phar emits ˤ U+02E4 — spacing; mod_voiceless
 * emits ◌̥/◌̊ — combining; ˔ ˕ are converted to their combining forms.) */
static IPA2VEC_MAYBE_UNUSED int mod_is_spacing(const ModRec *m)
{
    if (m->apply == mod_phar) return 1;        /* emitted as ˤ U+02E4 */
    if (m->apply == mod_voiceless) return 0;   /* emitted as ◌̥/◌̊ */
    if (combining_form(m)) return 0;           /* ˔ ˕ -> ◌̝ ◌̞ */
    const unsigned char *g = (const unsigned char *)m->ipa;
    unsigned long cp;
    int k = utf8_decode(g, &cp);
    if (!k) return 1;
    return cp != 0x25CC;   /* stored with the ◌ placeholder = combining */
}

/* canonical modifier order: combining marks first, then spacing
 * superscripts, each in the feature-tier order the parser applies
 * (airstream → laryngeal → place → manner → nasal → timing), stable
 * within a group and tier.  Re-parsing re-sorts by tier, so the emitted
 * spelling reproduces the same vector. */
static IPA2VEC_MAYBE_UNUSED int mod_priority(const ModRec *m)
{
    return (mod_is_spacing(m) ? TIER_COUNT : 0) + (int)m->tier;
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

/* does the base spelling end in spacing superscript marks (e.g. qʼ, lˠ)?
 * Return a pointer to the first such trailing mark (0 if none). */
static IPA2VEC_MAYBE_UNUSED const char *base_tail_marks(const char *s)
{
    /* modifier letters / superscripts: U+02B0-02FF, U+1D00-1D7F */
    const unsigned char *p = (const unsigned char *)s;
    const char *tail = NULL;
    while (*p) {
        unsigned long cp;
        int k = utf8_decode(p, &cp);
        if (!k) break;
        if ((cp >= 0x02B0 && cp <= 0x02FF) ||
            (cp >= 0x1D00 && cp <= 0x1D7F)) {
            if (!tail) tail = (const char *)p;   /* start of trailing run */
        } else {
            tail = NULL;   /* run broken by a letter */
        }
        p += k;
    }
    return tail;
}

/* build the IPA spelling: base letter (without its own trailing spacing
 * marks) + combining marks in feature-tier order, then all spacing
 * superscript marks (the base's own + the fitted modifiers) last, in
 * feature-tier order.
 * Standard symbols only: spacing modifier letters are replaced by their
 * combining forms where one exists; below-marks on descender letters are
 * moved above (voiceless ◌̥ -> ◌̊). */
static IPA2VEC_MAYBE_UNUSED void build_ipa (const SegEntry *base, const ModRec **mods, int nmods,
                       char *out, size_t outsz)
{
    /* copy to a local array so we can reorder without touching caller data */
    const ModRec *ordered[8];
    int n = nmods < 8 ? nmods : 8;
    for (int i = 0; i < n; i++) ordered[i] = mods[i];
    order_mods(ordered, n);

    int desc = has_descender(base->ipa);
    const char *tail = base_tail_marks(base->ipa);
    size_t corelen = tail ? (size_t)(tail - base->ipa) : strlen(base->ipa);
    size_t used = 0;
    if (corelen + 1 <= outsz) {
        memcpy(out, base->ipa, corelen);
        used = corelen;
        out[used] = 0;
    }

    /* pass 0: combining marks (attach to the base letter) */
    for (int i = 0; i < n; i++) {
        const ModRec *m = ordered[i];
        if (mod_is_spacing(m)) continue;
        const char *glyph = m->ipa;
        /* prefer the combining form of spacing modifier letters */
        const char *comb = combining_form(m);
        if (comb) glyph = comb;
        /* voiceless: standard form is ◌̥ (below ring); on descender
         * letters the below ring collides with the descender, so the
         * above ring ◌̊ is used instead (ŋ̥ -> ŋ̊, but m̥ stays m̥).
         * The choice depends on the letter, not on which MODS glyph was
         * picked during fitting. */
        if (m->apply == mod_voiceless)
            glyph = desc ? "\xcc\x8a" : "\xcc\xa5";
        /* pharyngealised: emit the unambiguous superscript ˤ (U+02E4)
         * rather than the velarised-or-pharyngealised overlay ◌̴ */
        if (m->apply == mod_phar)
            glyph = "\xcb\xa4";
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

    /* the base's own trailing spacing marks come before any fitted ones */
    if (tail && used + strlen(tail) + 1 <= outsz) {
        memcpy(out + used, tail, strlen(tail));
        used += strlen(tail);
        out[used] = 0;
    }

    /* pass 1: spacing superscripts from the fitted modifiers (typographic
     * new characters — appended last) */
    for (int i = 0; i < n; i++) {
        const ModRec *m = ordered[i];
        if (!mod_is_spacing(m)) continue;
        const char *glyph = m->ipa;
        /* prefer the combining form of spacing modifier letters */
        const char *comb = combining_form(m);
        if (comb) glyph = comb;
        /* voiceless: standard form is ◌̥ (below ring); on descender
         * letters the below ring collides with the descender, so the
         * above ring ◌̊ is used instead (ŋ̥ -> ŋ̊, but m̥ stays m̥).
         * The choice depends on the letter, not on which MODS glyph was
         * picked during fitting. */
        if (m->apply == mod_voiceless)
            glyph = desc ? "\xcc\x8a" : "\xcc\xa5";
        /* pharyngealised: emit the unambiguous superscript ˤ (U+02E4)
         * rather than the velarised-or-pharyngealised overlay ◌̴ */
        if (m->apply == mod_phar)
            glyph = "\xcb\xa4";
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
    /* three extra vectors:
     *   vec 0: single tone (contour, 1-3 levels) / ¹²³⁴⁵ digits
     *   vec 1: tone sandhi (contour, 1-3 levels)
     *   vec 2: 3-D (upstep, global, class); default (0,0,0)
     * Empty vectors print as '?'; trailing consecutive '?' are dropped. */
    int last = -1;
    for (int g = 0; g < 3; g++)
        if (sv->tkind[g] != 0)
            last = g;
    if (last < 0) return;
    printf("  tone=");
    for (int g = 0; g <= last; g++) {
        if (g) printf("?");
        if (sv->tkind[g] == 0) continue;   /* empty vector placeholder */
        if (g == 2) {
            /* 3-D vector: always three values, default (0,0,0) */
            printf("(");
            for (int d = 0; d < 3; d++) {
                if (d) printf(",");
                if (isnan(sv->tone[2][d])) printf("0");
                else printf("%g", sv->tone[2][d]);
            }
            printf(")");
            continue;
        }
        /* contour: 2 or 3 values */
        int nvals = !isnan(sv->tone[g][2]) ? 3 : 2;
        printf("(");
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

/* school-of-linguistics enable flags: --americanist, --sinologist, … */
static IPA2VEC_MAYBE_UNUSED int opt_school(const char *arg)
{
    if (arg[0] != '-' || arg[1] != '-') return 0;
    for (int m = 0; m < N_ALIAS_MODULES; m++) {
        if (!ALIAS_MODULES[m].school) continue;
        if (strcmp(arg + 2, ALIAS_MODULES[m].name) == 0) {
            enable_alias_module(ALIAS_MODULES[m].name);
            return 1;
        }
    }
    return 0;
}

/* transcription narrowness: --width <0-4>
 *   0 broadest: max 2 mods, >=25% gain
 *   1 broad:    max 3 mods, >=10% gain
 *   2 medium:   max 4 mods, >=4% gain
 *   3 narrow:   max 6 mods, >=1.5% gain (default)
 *   4 narrowest: max 10 mods, >=0.1% gain (keep almost everything)
 * Long form only (short -w is taken by vec4ipa's --weights).
 * Returns 1 if matched (level set), -1 if malformed, 0 if not ours. */
static IPA2VEC_MAYBE_UNUSED int opt_width(const char *arg, int argc, char **argv, int *i)
{
    static const int maxmods[5] = { 2, 3, 4, 6, 10 };
    static const double mingain[5] = { 0.25, 0.10, 0.04, 0.015, 0.001 };
    int level = -1;
    if (strcmp(arg, "--width") == 0) {
        if (*i + 1 >= argc) return -1;
        const char *v = argv[++*i];
        if (v[0] >= '0' && v[0] <= '4' && v[1] == 0)
            level = v[0] - '0';
        else return -1;
    } else if (strncmp(arg, "--width=", 8) == 0) {
        const char *v = arg + 8;
        if (v[0] >= '0' && v[0] <= '4' && v[1] == 0)
            level = v[0] - '0';
        else return -1;
    } else {
        return 0;
    }
    g_fit_max_mods = maxmods[level];
    g_fit_min_gain = mingain[level];
    return 1;
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
/* --metric FILE — load a metric.json (weights / lambda / full 16x16  */
/* matrix) at runtime, overriding the compiled-in defaults for this    */
/* invocation only.  Without --metric the compiled-in METRIC_W /       */
/* METRIC_LAMBDA are used, so no external JSON is ever required.       */
/*                                                                     */
/* The JSON schema follows metric.json (METRIC.md §5):                 */
/*   { "weights": [16 numbers], "lambda": number,                      */
/*     "metric": null | [256 numbers], ... }                           */
/* A non-null "metric" matrix overrides "weights".                     */
/* ------------------------------------------------------------------ */

typedef struct { const char *p, *end; int line; } JsonCtx;

static IPA2VEC_MAYBE_UNUSED void json_ws (JsonCtx *c)
{
    while (c->p < c->end) {
        char ch = *c->p;
        if (ch == ' ' || ch == '\t' || ch == '\r') { c->p++; }
        else if (ch == '\n') { c->p++; c->line++; }
        else break;
    }
}

static IPA2VEC_MAYBE_UNUSED int json_skip_value (JsonCtx *c)
{
    json_ws(c);
    if (c->p >= c->end) return -1;
    char ch = *c->p;
    if (ch == '"') {
        c->p++;
        while (c->p < c->end) {
            char s = *c->p++;
            if (s == '\\') { if (c->p < c->end) c->p++; }
            else if (s == '"') return 0;
            else if (s == '\n') c->line++;
        }
        return -1;
    }
    if (ch == '{' || ch == '[') {
        char open = ch, close = (ch == '{') ? '}' : ']';
        c->p++;
        for (;;) {
            if (json_ws(c), c->p >= c->end) return -1;
            char s = *c->p++;
            if (s == close) return 0;
            if (s == '"') {
                while (c->p < c->end) {
                    char t = *c->p++;
                    if (t == '\\') { if (c->p < c->end) c->p++; }
                    else if (t == '"') break;
                    else if (t == '\n') c->line++;
                }
            }
            if (c->p >= c->end) return -1;
        }
    }
    /* bare literal / number: consume to the next structural char */
    while (c->p < c->end) {
        char s = *c->p;
        if (s == ',' || s == '}' || s == ']' || s == ' ' || s == '\t' ||
            s == '\n' || s == '\r')
            break;
        c->p++;
    }
    return 0;
}

/* parse one JSON number; on success *out is set and 0 returned */
static IPA2VEC_MAYBE_UNUSED int json_number (JsonCtx *c, double *out)
{
    json_ws(c);
    if (c->p >= c->end) return -1;
    char *endp = NULL;
    double v = strtod(c->p, &endp);
    if (endp == c->p) return -1;
    c->p = endp;
    *out = v;
    return 0;
}

/* parse a JSON array of numbers into out[0..n-1]; must have exactly n */
static IPA2VEC_MAYBE_UNUSED int json_num_array (JsonCtx *c, double *out, int n)
{
    json_ws(c);
    if (c->p >= c->end || *c->p != '[') return -1;
    c->p++;
    for (int k = 0; k < n; k++) {
        double v;
        if (json_number(c, &v) != 0) return -1;
        out[k] = v;
        json_ws(c);
        if (c->p >= c->end) return -1;
        if (*c->p == ',') { c->p++; continue; }
        if (*c->p == ']') {
            if (k != n - 1) return -1;   /* too few elements */
            c->p++;
            return 0;
        }
        return -1;
    }
    /* exactly n elements read: the array must close now */
    json_ws(c);
    if (c->p < c->end && *c->p == ']') { c->p++; return 0; }
    return -1;
}

/* returns 1 if "key": is at the cursor (and consumes it), else 0 */
static IPA2VEC_MAYBE_UNUSED int json_key (JsonCtx *c, const char *key)
{
    json_ws(c);
    if (c->p >= c->end || *c->p != '"') return 0;
    const char *q = c->p + 1;
    size_t L = strlen(key);
    if ((size_t)(c->end - q) < L || memcmp(q, key, L) != 0) return 0;
    q += L;
    if (q >= c->end || *q != '"') return 0;
    c->p = q + 1;
    json_ws(c);
    if (c->p >= c->end || *c->p != ':') return 0;
    c->p++;
    return 1;
}

/* load metric.json into the runtime metric globals.
 * Returns 0 on success; -1 on any parse/IO error (message printed). */
static IPA2VEC_MAYBE_UNUSED int load_metric_json (const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "--metric: cannot open '%s'\n", path);
        return -1;
    }
    long sz;
    if (fseek(f, 0, SEEK_END) != 0 || (sz = ftell(f)) < 0 ||
        fseek(f, 0, SEEK_SET) != 0 || sz > (1 << 20)) {
        fclose(f);
        fprintf(stderr, "--metric: '%s': unreadable or too large\n", path);
        return -1;
    }
    char *buf = (char *)malloc((size_t)sz + 1);
    if (!buf) { fclose(f); fprintf(stderr, "--metric: out of memory\n"); return -1; }
    size_t got = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    buf[got] = 0;

    JsonCtx c = { buf, buf + got, 1 };
    int have_w = 0, have_m = 0;
    json_ws(&c);
    if (c.p >= c.end || *c.p != '{') {
        fprintf(stderr, "--metric: '%s': not a JSON object\n", path);
        free(buf);
        return -1;
    }
    c.p++;
    for (;;) {
        json_ws(&c);
        if (c.p >= c.end) goto bad;
        if (*c.p == '}') { c.p++; break; }
        if (json_key(&c, "weights")) {
            if (json_num_array(&c, g_metric_w, NDIM) != 0) goto bad;
            have_w = 1;
        } else if (json_key(&c, "lambda")) {
            if (json_number(&c, &g_metric_lambda) != 0) goto bad;
        } else if (json_key(&c, "metric")) {
            json_ws(&c);
            if (c.p < c.end && *c.p == 'n') {   /* null */
                while (c.p < c.end && (isalpha((unsigned char)*c.p))) c.p++;
                g_metric_full = 0;
            } else {
                if (json_num_array(&c, &g_metric_M[0][0], NDIM * NDIM) != 0)
                    goto bad;
                g_metric_full = 1;
                have_m = 1;
            }
        } else {
            /* unknown key: skip the "key": value pair (nested ok) */
            if (json_skip_value(&c) != 0) goto bad;   /* the key string */
            json_ws(&c);
            if (c.p >= c.end || *c.p != ':') goto bad;
            c.p++;
            if (json_skip_value(&c) != 0) goto bad;   /* the value */
        }
        json_ws(&c);
        if (c.p >= c.end) goto bad;
        if (*c.p == ',') { c.p++; continue; }
        if (*c.p == '}') { c.p++; break; }
        goto bad;
    }
    if (!have_w && !have_m) {
        fprintf(stderr, "--metric: '%s': no 'weights' or 'metric' array\n", path);
        free(buf);
        return -1;
    }
    free(buf);
    g_metric_ready = 1;
    return 0;
bad:
    fprintf(stderr, "--metric: '%s': parse error near line %d\n", path, c.line);
    free(buf);
    return -1;
}

/* --metric FILE / --metric=FILE.
 * Returns 1 if matched (metric loaded), -1 if value missing,
 * -2 if the file failed to load (message already printed), 0 if not ours. */
static IPA2VEC_MAYBE_UNUSED int opt_metric(const char *arg, int argc, char **argv, int *i)
{
    const char *path = NULL;
    if (strcmp(arg, "--metric") == 0) {
        if (*i + 1 >= argc) return -1;
        path = argv[++*i];
    } else if (strncmp(arg, "--metric=", 9) == 0) {
        path = arg + 9;
    } else {
        return 0;
    }
    if (load_metric_json(path) != 0) return -2;
    return 1;
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
