/*
 * ipa2vec_core.dll — C export layer over src/ipa2vec_core.h for the
 * WinUI 3 front-end (ui/winui/). Compiled with MinGW (build.bat):
 *
 *   gcc -O2 -std=c11 -Wno-unused-function -Wno-unused-variable ^
 *       -I..\..\src -shared -o ..\ipa2vec_core.dll core_wrap.c
 *
 * The DLL is a thin adapter: all tables and algorithms live in the
 * header (ipa2vec_core.h), identical to the CLI tools.
 */

#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#include "../src/ipa2vec_core.h"
#include "../src/readme_embed.h"

#define EXPORT __declspec(dllexport)

/* same mapping as opt_width() in ipa2vec_core.h */
static void set_width_global(int level)
{
    width_apply(level);
}

/* forward: IPA string -> N segments. Returns segment count or -1 on
 * parse error (err filled). Buffer sizes are fixed (MAX_TOKS etc.). */
EXPORT int ipa2v_forward(const char *str, char *err, size_t errsz,
                         double *out /* NDIM * MAX_TOKS */,
                         int *airstream /* MAX_TOKS */,
                         char *names /* MAX_TOKS * 48 */)
{
    ParseOut po;
    if (lex(str, po.layer1, &po.n1, err, errsz))
        return -1;
    canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
    if (apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs, "core")) {
        snprintf(err, errsz, "too many segments");
        return -1;
    }
    for (int s = 0; s < po.nsegs && s < MAX_TOKS; s++) {
        for (int i = 0; i < NDIM; i++)
            out[s * NDIM + i] = po.segs[s].v[i];
        airstream[s] = po.segs[s].airstream;
        if (names) {
            char *d = names + s * 48;
            snprintf(d, 48, "%s", po.segs[s].note);
        }
    }
    return po.nsegs;
}

/* forward + tone extra vectors: tone[3][3] per segment (NAN = unset),
 * tkind[3] per segment (0 none, 1 contour, 2 = 3-D vector) */
EXPORT int ipa2v_forward_tone(const char *str, char *err, size_t errsz,
                              double *out /* NDIM * MAX_TOKS */,
                              double *tone /* 9 * MAX_TOKS */,
                              int *tkind /* 3 * MAX_TOKS */)
{
    ParseOut po;
    if (lex(str, po.layer1, &po.n1, err, errsz))
        return -1;
    canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
    if (apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs, "core")) {
        snprintf(err, errsz, "too many segments");
        return -1;
    }
    for (int s = 0; s < po.nsegs && s < MAX_TOKS; s++) {
        for (int i = 0; i < NDIM; i++)
            out[s * NDIM + i] = po.segs[s].v[i];
        for (int g = 0; g < 3; g++) {
            tkind[s * 3 + g] = po.segs[s].tkind[g];
            for (int k = 0; k < 3; k++)
                tone[s * 9 + g * 3 + k] = po.segs[s].tone[g][k];
        }
    }
    return po.nsegs;
}

/* reverse: 16-D vector -> IPA fit. Returns 0 on success. */
EXPORT int ipa2v_reverse(const double *v, int width,
                         char *out /* 512 */, size_t outsz)
{
    double vv[NDIM];
    for (int i = 0; i < NDIM; i++) vv[i] = v[i];

    /* guard: NaN/Inf would make nearest_base index out of bounds */
    for (int i = 0; i < NDIM; i++) {
        if (!(vv[i] == vv[i]) || vv[i] > 1e300 || vv[i] < -1e300) {
            snprintf(out, outsz, "vector must contain finite values");
            return -1;
        }
    }

    set_width_global(width);

    const SegEntry *b = NULL;
    double d = 0.0;
    const ModRec *mods[IPA2VEC_FIT_MAX_MODS] = {0};
    int nm = 0;
    fit_best(vv, &b, mods, &nm, &d);
    /* membership via integer addresses: relational pointer compares
     * across SEG_TABLE/EXTRA_BASE are UB and reject EXTRA bases
     * (ɚ/ʩ/ᴇ/… never reverse) when EXTRA_BASE sits past the window */
    if (b) {
        int ok = seg_in_table(b);
        if (!ok) {
            uintptr_t x = (uintptr_t)(const void *)b;
            ok = x >= (uintptr_t)(const void *)EXTRA_BASE &&
                 x < (uintptr_t)(const void *)EXTRA_BASE +
                     sizeof(SegEntry) * (uintptr_t)N_EXTRA;
        }
        if (!ok) b = NULL;
    }
    if (!b) {
        snprintf(out, outsz, "no nearest base segment found");
        return -1;
    }

    /* affricate decode competes when it beats the single-base fit
     * (mirrors run_reverse in the CLI); on an exact fit it cannot win
     * (afd < 0 is impossible) and it dominates the reverse cost */
    const SegEntry *afc = NULL, *afr = NULL;
    const ModRec *afrm[4];
    int afnm = 0;
    double afd = 0.0;
    if (d > 1e-6 && affricate_decode(vv, &afc, &afr, afrm, &afnm, &afd) == 0) {
        const ModRec *cur[IPA2VEC_FIT_MAX_MODS + 4];
        int nc = 0;
        for (int k = 0; k < nm; k++) cur[nc++] = mods[k];
        double trial[NDIM];
        apply_mod_set(trial, b, cur, nc);
        double d_fit = seg_dist(vv, trial);
        if (afd + 1e-9 < d_fit * 0.85) {
            char rel[128];
            build_ipa(afr, afrm, afnm, 0, rel, sizeof(rel));
            char afipa[128];
            snprintf(afipa, sizeof(afipa), "%s\xCD\xA1%s", afc->ipa, rel);
            snprintf(out, outsz, "/%s/  (affricate %s+%s)  d=%.4f  ->  /%s/",
                     afc->ipa, afc->ipa, rel, afd, afipa);
            return 0;
        }
    }

    char ipa[128];
    build_ipa(b, mods, nm, 0, ipa, sizeof(ipa));

    char buf[256];
    snprintf(buf, sizeof(buf), "/%s/  (%s", b->ipa, base_name(b));
    for (int j = 0; j < nm; j++) {
        size_t L = strlen(buf);
        snprintf(buf + L, sizeof(buf) - L, " +%s", mods[j]->latin);
    }
    snprintf(out, outsz, "%s)  d=%.4f  ->  /%s/", buf, d, ipa);
    return 0;
}

/* query a single symbol (base / extIPA / modifier / alias) */
EXPORT int ipa2v_query(const char *sym, char *out /* 512 */, size_t outsz)
{
    for (int i = 0; i < NSEG; i++) {
        if (strcmp(SEG_TABLE[i].ipa, sym) == 0) {
            snprintf(out, outsz, "base: /%s/  %s  (%s)\n  (",
                     SEG_TABLE[i].ipa, NAME_TABLE[i],
                     AIRSTREAM_LABELS[SEG_TABLE[i].airstream]);
            size_t L = strlen(out);
            for (int j = 0; j < NDIM; j++) {
                snprintf(out + L, outsz - L, "%s%.4f", j ? ", " : "",
                         SEG_TABLE[i].v[j]);
                L = strlen(out);
            }
            snprintf(out + L, outsz - L, ")");
            return 0;
        }
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (strcmp(EXTRA_BASE[i].ipa, sym) == 0) {
            snprintf(out, outsz, "extIPA base: /%s/  %s  (%s)",
                     EXTRA_BASE[i].ipa, EXTRA_NAMES[i],
                     AIRSTREAM_LABELS[EXTRA_BASE[i].airstream]);
            return 0;
        }
    }
    const unsigned char *u = (const unsigned char *)sym;
    unsigned long cp = 0;
    if (utf8_decode(u, &cp)) {
        const ModRec *m = find_mod(cp);
        if (m) {
            snprintf(out, outsz, "modifier: %s  %s  tier=%d%s%s",
                     m->ipa, m->latin, (int)m->tier,
                     m->air >= 0 ? "  [sets airstream]" : "",
                     m->infer ? "  [inference]" : "");
            return 0;
        }
    }
    const Alias *a = lookup_alias(sym, 0);
    if (a) {
        snprintf(out, outsz, "alias: %s -> %s%s%s", a->sym, a->repl,
                 a->note ? "  " : "", a->note ? a->note : "");
        return 0;
    }
    snprintf(out, outsz, "no entry for: %s", sym);
    return 0;
}

/* keyboard symbol lists (UTF-8, one per line):
 *   cons:   SEG_TABLE/EXTRA_BASE entries that are not vowels
 *   vowels: entries whose name ends in .vwl
 *   mods:   MODS entries that are not tone marks (tone_kind == 0)
 *   tones:  MODS entries with tone semantics, plus ‿ and space
 * Returns number of bytes written. */
static int is_vowel_name(const char *name)
{
    return name && strstr(name, ".vwl") != NULL;
}

EXPORT int ipa2v_kb_cons(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NSEG; i++) {
        if (is_vowel_name(NAME_TABLE[i])) continue;
        if (SEG_TABLE[i].airstream != 0) continue;   /* pulmonic only */
        int n = snprintf(out + L, outsz - L, "%s\n", SEG_TABLE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (is_vowel_name(EXTRA_NAMES[i])) continue;
        if (EXTRA_BASE[i].airstream != 0) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", EXTRA_BASE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

/* non-pulmonic consonants: ejectives, implosives, clicks, percussives */
EXPORT int ipa2v_kb_cons_np(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NSEG; i++) {
        if (is_vowel_name(NAME_TABLE[i])) continue;
        if (SEG_TABLE[i].airstream == 0) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", SEG_TABLE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (is_vowel_name(EXTRA_NAMES[i])) continue;
        if (EXTRA_BASE[i].airstream == 0) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", EXTRA_BASE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

EXPORT int ipa2v_kb_vowels(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NSEG; i++) {
        if (!is_vowel_name(NAME_TABLE[i])) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", SEG_TABLE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (!is_vowel_name(EXTRA_NAMES[i])) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", EXTRA_BASE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

EXPORT int ipa2v_kb_mods(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NMODS; i++) {
        if (MODS[i].tone_kind != 0) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", MODS[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

EXPORT int ipa2v_kb_tones(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NMODS; i++) {
        if (MODS[i].tone_kind == 0) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", MODS[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    static const char extra[] = "\u203f\n\xe2\x97\x8c\n";  /* ‿ and ◌ placeholder */
    if (L + sizeof(extra) <= outsz)
        memcpy(out + L, extra, sizeof(extra));
    return (int)strlen(out);
}

EXPORT const char *ipa2v_version(void)
{
    return IPA2VEC_VERSION;
}

EXPORT const char *ipa2v_docs(void)
{
    return EMBEDDED_README;
}

/* Apply CLI-style settings (school modules, --narrowness) for the GUI.
 * Unknown options are skipped. Returns 0. */
EXPORT int ipa2v_set_args(int n, const char **argv)
{
    int i = 0;
    while (i < n) {
        const char *a = argv[i];
        if (opt_school(a)) { i++; continue; }
        if (strncmp(a, "--narrowness", 12) == 0 || strncmp(a, "--width", 7) == 0) {
            int lev = 3;
            if (i + 1 < n && argv[i + 1][0] >= '0' && argv[i + 1][0] <= '4')
                lev = argv[i + 1][0] - '0', i++;
            set_width_global(lev);
        }
        i++;
    }
    return 0;
}

/* school module names, one per line (for the GUI menu) */
EXPORT int ipa2v_modules(char *out, size_t outsz)
{
    size_t L = 0;
    for (int m = 0; m < N_ALIAS_MODULES; m++) {
        if (!ALIAS_MODULES[m].school) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", ALIAS_MODULES[m].name);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

/* -t equivalent: the full base table */
EXPORT int ipa2v_table(char *out, size_t outsz)
{
    size_t L = 0;
    int n;
    n = snprintf(out + L, outsz - L,
                 "# ipa\tlatin\tairstream\t(16-D vector)\n");
    if (n > 0 && (size_t)n < outsz - L) L += n;
    for (int i = 0; i < NSEG; i++) {
        n = snprintf(out + L, outsz - L, "%s\t%s\t%s\t(",
                     SEG_TABLE[i].ipa, NAME_TABLE[i],
                     AIRSTREAM_LABELS[SEG_TABLE[i].airstream]);
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
        for (int j = 0; j < NDIM; j++) {
            n = snprintf(out + L, outsz - L, "%s%.4f", j ? ", " : "",
                         SEG_TABLE[i].v[j]);
            if (n < 0 || (size_t)n >= outsz - L) break; L += n;
        }
        n = snprintf(out + L, outsz - L, ")\n");
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    for (int i = 0; i < N_EXTRA; i++) {
        n = snprintf(out + L, outsz - L, "%s\t%s\t%s\t(\n",
                     EXTRA_BASE[i].ipa, EXTRA_NAMES[i],
                     AIRSTREAM_LABELS[EXTRA_BASE[i].airstream]);
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    return (int)L;
}

/* -s equivalent: inventory statistics */
EXPORT int ipa2v_stats(char *out, size_t outsz)
{
    int nmod = 0;
    for (int m = 0; m < N_ALIAS_MODULES; m++)
        nmod += ALIAS_MODULES[m].n;
    snprintf(out, outsz,
             "base segments (SEG_TABLE):   %d\n"
             "extIPA bases (EXTRA_BASE):   %d\n"
             "modifiers (MODS):            %d\n"
             "precomposed chars:           %d\n"
             "alias modules:               %d (%d symbols)\n"
             "implicit affricates:         %d\n"
             "dimensions:                  %d\n"
             "lambda:                      %.2f\n"
             "airstreams:                  %s | %s | %s | %s | %s\n",
             NSEG, N_EXTRA, NMODS, NPRECOMP, N_ALIAS_MODULES, nmod,
             NNOLIG, NDIM, METRIC_LAMBDA,
             AIRSTREAM_LABELS[0], AIRSTREAM_LABELS[1], AIRSTREAM_LABELS[2],
             AIRSTREAM_LABELS[3], AIRSTREAM_LABELS[4]);
    return 0;
}

/* --metric FILE: load metric.json weights/lambda at runtime */
EXPORT int ipa2v_load_metric(const char *path)
{
    return load_metric_json(path);
}

/* effective weights after --metric (for the GUI table view) */
EXPORT int ipa2v_weights_effective(char *out, size_t outsz)
{
    metric_ensure();
    size_t L = 0;
    int n = snprintf(out + L, outsz - L,
                     "# effective dimension weights\n");
    if (n > 0 && (size_t)n < outsz - L) L += n;
    for (int i = 0; i < NDIM; i++) {
        n = snprintf(out + L, outsz - L, "%2d  %-22s %8.4f\n", i,
                     DIM_NAMES[i], g_metric_w[i]);
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    n = snprintf(out + L, outsz - L, "lambda (airstream penalty):  %.2f\n",
                 g_metric_lambda);
    if (n > 0 && (size_t)n < outsz - L) L += n;
    return (int)L;
}

/* -m equivalent: every alias module with its symbol -> replacement map */
EXPORT int ipa2v_modules_full(char *out, size_t outsz)
{
    size_t L = 0;
    int n;
    for (int m = 0; m < N_ALIAS_MODULES; m++) {
        n = snprintf(out + L, outsz - L, "[%s]  %d symbols%s%s\n",
                     ALIAS_MODULES[m].name, ALIAS_MODULES[m].n,
                     ALIAS_MODULES[m].school ? "  (school)" : "",
                     ALIAS_MODULES[m].school ? "" : "  (always on)");
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
        for (int i = 0; i < ALIAS_MODULES[m].n && L < outsz - 64; i++) {
            const Alias *a = &ALIAS_MODULES[m].tab[i];
            n = snprintf(out + L, outsz - L, "    %-8s -> %s%s\n", a->sym,
                         a->repl, a->warn ? "  [deprecated]" : "");
            if (n < 0 || (size_t)n >= outsz - L) break; L += n;
        }
    }
    return (int)L;
}

/* -d equivalent: weighted distance between two symbols */
EXPORT int ipa2v_distance(const char *a, const char *b, double *out)
{
    ParseOut pa, pb;
    char err[256];
    if (lex(a, pa.layer1, &pa.n1, err, sizeof(err)) ||
        lex(b, pb.layer1, &pb.n1, err, sizeof(err)))
        return -1;
    canonicalise(pa.layer1, pa.n1, pa.layer2, &pa.n2);
    canonicalise(pb.layer1, pb.n1, pb.layer2, &pb.n2);
    if (apply_layer2(pa.layer2, pa.n2, pa.segs, &pa.nsegs, "core") ||
        apply_layer2(pb.layer2, pb.n2, pb.segs, &pb.nsegs, "core"))
        return -1;
    if (pa.nsegs != 1 || pb.nsegs != 1) return -2;
    *out = seg_dist_full(&pa.segs[0], &pb.segs[0]);
    return 0;
}

/* -e/--ir equivalent: two-layer IR + rebuilt IPA for a string */
EXPORT int ipa2v_ir(const char *str, char *out, size_t outsz)
{
    ParseOut po;
    char err[256];
    if (lex(str, po.layer1, &po.n1, err, sizeof(err))) {
        snprintf(out, outsz, "parse error: %s", err);
        return -1;
    }
    canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
    if (apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs, "core")) {
        snprintf(out, outsz, "too many segments");
        return -1;
    }

    size_t L = 0;
    int n;
    n = snprintf(out + L, outsz - L, "input: /%s/\n", str);
    if (n > 0 && (size_t)n < outsz - L) L += n;

    n = snprintf(out + L, outsz - L, "  layer1 (char order): ");
    if (n > 0 && (size_t)n < outsz - L) L += n;
    for (int i = 0; i < po.n1 && L < outsz - 96; i++) {
        const IrTok *t = &po.layer1[i];
        if (i) { n = snprintf(out + L, outsz - L, " \xe2\x86\x92 "); if (n>0 && (size_t)n<outsz-L) L += n; }
        switch (t->kind) {
        case TK_BASE:
            n = snprintf(out + L, outsz - L, "[%s:%s]", t->ipa, t->latin); break;
        case TK_MOD:
            n = snprintf(out + L, outsz - L, "[%s:%s", t->ipa, t->latin);
            if (n > 0 && (size_t)n < outsz - L) L += n;
            if (t->tier < TIER_COUNT) {
                n = snprintf(out + L, outsz - L, "/%s", TIER_NAMES[t->tier]);
                if (n > 0 && (size_t)n < outsz - L) L += n;
            }
            n = snprintf(out + L, outsz - L, "]"); break;
        case TK_LIG:
            n = snprintf(out + L, outsz - L, "[tie]"); break;
        }
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    n = snprintf(out + L, outsz - L, "\n  layer2 (feature order): ");
    if (n > 0 && (size_t)n < outsz - L) L += n;
    for (int i = 0; i < po.n2 && L < outsz - 96; i++) {
        const IrTok *t = &po.layer2[i];
        if (i) { n = snprintf(out + L, outsz - L, " \xe2\x86\x92 "); if (n>0 && (size_t)n<outsz-L) L += n; }
        switch (t->kind) {
        case TK_BASE:
            n = snprintf(out + L, outsz - L, "[%s:%s]", t->ipa, t->latin); break;
        case TK_MOD:
            n = snprintf(out + L, outsz - L, "[%s:%s", t->ipa, t->latin);
            if (n > 0 && (size_t)n < outsz - L) L += n;
            if (t->tier < TIER_COUNT) {
                n = snprintf(out + L, outsz - L, "/%s", TIER_NAMES[t->tier]);
                if (n > 0 && (size_t)n < outsz - L) L += n;
            }
            n = snprintf(out + L, outsz - L, "]"); break;
        case TK_LIG:
            n = snprintf(out + L, outsz - L, "[tie]"); break;
        }
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    n = snprintf(out + L, outsz - L, "\n");
    if (n > 0 && (size_t)n < outsz - L) L += n;

    for (int s = 0; s < po.nsegs && L < outsz - 160; s++) {
        n = snprintf(out + L, outsz - L, "vector[%d]: (", s);
        if (n > 0 && (size_t)n < outsz - L) L += n;
        for (int i = 0; i < NDIM; i++) {
            n = snprintf(out + L, outsz - L, "%s%.4f", i ? ", " : "",
                         po.segs[s].v[i]);
            if (n < 0 || (size_t)n >= outsz - L) break; L += n;
        }
        n = snprintf(out + L, outsz - L, ")  %s%s%s\n",
                     AIRSTREAM_LABELS[po.segs[s].airstream],
                     po.segs[s].note[0] ? "  [" : "", po.segs[s].note);
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
        const SegEntry *b = NULL; double d = 0.0;
        const ModRec *mods[IPA2VEC_FIT_MAX_MODS] = {0};
        int nm = 0;
        fit_best(po.segs[s].v, &b, mods, &nm, &d);
        if (!b) continue;
        char rebuilt[128];
        build_ipa(b, mods, nm, po.segs[s].dotless, rebuilt, sizeof(rebuilt));
        n = snprintf(out + L, outsz - L, "rebuilt[%d]: /%s/\n", s, rebuilt);
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    return 0;
}

/* -j equivalent: JSON output */
EXPORT int ipa2v_json(const char *str, char *out, size_t outsz)
{
    ParseOut po;
    char err[256];
    if (lex(str, po.layer1, &po.n1, err, sizeof(err))) {
        snprintf(out, outsz, "parse error: %s", err);
        return -1;
    }
    canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
    if (apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs, "core")) {
        snprintf(out, outsz, "{\"error\": \"too many segments\"}\n");
        return -1;
    }

    size_t L = 0;
    int n = snprintf(out + L, outsz - L, "{\"input\": \"%s\", \"segments\": [\n",
                     str);
    if (n > 0 && (size_t)n < outsz - L) L += n;
    for (int s = 0; s < po.nsegs && L < outsz - 512; s++) {
        n = snprintf(out + L, outsz - L, "%s    {\"values\": {",
                     s ? ",\n" : "");
        if (n > 0 && (size_t)n < outsz - L) L += n;
        for (int i = 0; i < NDIM; i++) {
            n = snprintf(out + L, outsz - L, "%s\"%s\": %.4f",
                         i ? ", " : "", DIM_NAMES[i], po.segs[s].v[i]);
            if (n < 0 || (size_t)n >= outsz - L) break; L += n;
        }
        n = snprintf(out + L, outsz - L, "}, \"airstream\": \"%s\"}",
                     AIRSTREAM_LABELS[po.segs[s].airstream]);
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    n = snprintf(out + L, outsz - L, "\n]}\n");
    if (n > 0 && (size_t)n < outsz - L) L += n;
    return 0;
}

/* -x equivalent: write <base>.layer1 / <base>.layer2 for the parse */
EXPORT int ipa2v_ir_export(const char *str, const char *base,
                           char *err, size_t errsz)
{
    ParseOut po;
    if (lex(str, po.layer1, &po.n1, err, errsz))
        return -1;
    canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
    if (apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs, "core")) {
        snprintf(err, errsz, "too many segments");
        return -1;
    }
    return export_ir(po.layer1, po.n1, po.layer2, po.n2, base, "core");
}

/* dimension names, one per line (for feature-name output view) */
EXPORT int ipa2v_dim_names(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NDIM; i++) {
        int n = snprintf(out + L, outsz - L, "%s\n", DIM_NAMES[i]);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

/* vowel keyboard positions: one "sym\trow\tcol\n" line per vowel
 * (row = height close..open 0..4, col = position front..back 0..7) */
EXPORT int ipa2v_vowel_positions(char *out, size_t outsz)
{
    static const double pos_steps[8] = {0.0, 0.14, 0.28, 0.42,
                                        0.56, 0.70, 0.84, 1.0};
    size_t L = 0;
    /* resolve dims by name: the compiled scheme is SPEC-NEXT order
     * (v[2]=lips_closed, v[3]=lips_rounded), not v8 order */
    int body = dim_of_ok("body", DIM_TONGUE_BODY_POS);
    int area = dim_of_ok("effective_oral_area", DIM_EFFECTIVE_ORAL_AREA);
    for (int i = 0; i < NSEG; i++) {
        const char *nm = NAME_TABLE[i];
        if (!nm || !strstr(nm, ".vwl")) continue;
        /* frontness lives on body (front +0.4 .. back -0.4),
         * height on effective_oral_area (close 0.4 .. open 1.0) */
        double tt = (SEG_TABLE[i].v[body] + 0.4) / 0.8;
        double th = (SEG_TABLE[i].v[area] - 0.4) / 0.6;
        if (tt < 0.0) tt = 0.0;
        if (tt > 1.0) tt = 1.0;
        if (th < 0.0) th = 0.0;
        if (th > 1.0) th = 1.0;
        int col = 0;
        for (int c = 0; c < 8; c++)
            if (tt >= pos_steps[c]) col = c;
        /* close (small oral area) is row 0 at the top of the trapezium */
        int row = (int)(th * 4.0 + 0.5);
        if (row < 0) row = 0;
        if (row > 4) row = 4;
        int n = snprintf(out + L, outsz - L, "%s\t%d\t%d\n",
                         SEG_TABLE[i].ipa, row, col);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

/* consonant place: one "sym\tplace\n" line per consonant (incl. EXTRA),
 * place runs front (0, lips) to back (1, glottis) */
EXPORT int ipa2v_kb_cons_pos(char *out, size_t outsz)
{
    size_t L = 0;
    int place = dim_of_ok("place", DIM_TONGUE_TIP_POS);
    double norm(const double v[MAXDIM])
    {
        double p = (v[place] + 0.9) / 1.8;   /* lips -0.9 .. glottis +0.9 -> 0..1 */
        return p < 0.0 ? 0.0 : (p > 1.0 ? 1.0 : p);
    }
    for (int i = 0; i < NSEG; i++) {
        if (is_vowel_name(NAME_TABLE[i])) continue;
        int n = snprintf(out + L, outsz - L, "%s\t%.4f\n",
                         SEG_TABLE[i].ipa, norm(SEG_TABLE[i].v));
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (is_vowel_name(EXTRA_NAMES[i])) continue;
        int n = snprintf(out + L, outsz - L, "%s\t%.4f\n",
                         EXTRA_BASE[i].ipa, norm(EXTRA_BASE[i].v));
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

/* modifier tiers: one "sym\ttier\n" line per MODS entry */
EXPORT int ipa2v_kb_mod_tiers(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NMODS; i++) {
        int n = snprintf(out + L, outsz - L, "%s\t%d\n",
                         MODS[i].ipa, (int)MODS[i].tier);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}
