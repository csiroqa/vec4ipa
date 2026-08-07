/*
 * ipa2vec_core.dll — C export layer over src/ipa2vec_core.h for the
 * WinUI 3 front-end (ui/winui/). Compiled with MinGW:
 *
 *   gcc -O2 -std=c11 -I../src -shared -o ipa2vec_core.dll core_wrap.c \
 *       -Wl,--out-implib,libipa2vec_core.a -lwinmm
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
    static const int maxmods[5] = { 2, 3, 4, 6, 10 };
    static const double mingain[5] = { 0.25, 0.10, 0.04, 0.015, 0.001 };
    if (level < 0) level = 0;
    if (level > 4) level = 4;
    g_fit_max_mods = maxmods[level];
    g_fit_min_gain = mingain[level];
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
    apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs);
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

    const SegEntry *b; double d;
    nearest_base(vv, &b, &d);
    if (b < SEG_TABLE || b >= SEG_TABLE + NSEG + N_EXTRA) {
        snprintf(out, outsz, "no nearest base segment found");
        return -1;
    }
    const ModRec *mods[IPA2VEC_FIT_MAX_MODS] = {0};
    int nm = fit_modifiers(vv, b, mods);
    char ipa[128];
    build_ipa(b, mods, nm, ipa, sizeof(ipa));

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
    static const char extra[] = "\u203f\n \n";  /* ‿ and space */
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

/* Apply CLI-style settings (school modules, --width) for the GUI.
 * Unknown options are skipped. Returns 0. */
EXPORT int ipa2v_set_args(int n, const char **argv)
{
    int i = 0;
    while (i < n) {
        const char *a = argv[i];
        if (opt_school(a)) { i++; continue; }
        if (strncmp(a, "--width", 7) == 0) {
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

/* -w equivalent: metric weights */
EXPORT int ipa2v_weights(char *out, size_t outsz)
{
    size_t L = 0;
    int n = snprintf(out + L, outsz - L,
                     "# dimension weights (metric v4)\n");
    if (n > 0 && (size_t)n < outsz - L) L += n;
    for (int i = 0; i < NDIM; i++) {
        n = snprintf(out + L, outsz - L, "%2d  %-22s %8.4f\n", i,
                     DIM_NAMES[i], METRIC_W[i]);
        if (n < 0 || (size_t)n >= outsz - L) break; L += n;
    }
    n = snprintf(out + L, outsz - L, "lambda (airstream penalty):  %.2f\n",
                 METRIC_LAMBDA);
    if (n > 0 && (size_t)n < outsz - L) L += n;
    return (int)L;
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
    apply_layer2(pa.layer2, pa.n2, pa.segs, &pa.nsegs);
    apply_layer2(pb.layer2, pb.n2, pb.segs, &pb.nsegs);
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
    apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs);

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
        const SegEntry *b; double d;
        nearest_base(po.segs[s].v, &b, &d);
        const ModRec *mods[IPA2VEC_FIT_MAX_MODS] = {0};
        int nm = fit_modifiers(po.segs[s].v, b, mods);
        char rebuilt[128];
        build_ipa(b, mods, nm, rebuilt, sizeof(rebuilt));
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
    apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs);

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
    apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs);
    return export_ir(po.layer1, po.n1, po.layer2, po.n2, base);
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
    for (int i = 0; i < NSEG; i++) {
        const char *nm = NAME_TABLE[i];
        if (!nm || !strstr(nm, ".vwl")) continue;
        double tt = SEG_TABLE[i].v[2];
        double th = SEG_TABLE[i].v[3];
        int col = 0;
        for (int c = 0; c < 8; c++)
            if (tt >= pos_steps[c]) col = c;
        int row = (int)((1.0 - th) * 4.0 + 0.5);
        if (row < 0) row = 0;
        if (row > 4) row = 4;
        int n = snprintf(out + L, outsz - L, "%s\t%d\t%d\n",
                         SEG_TABLE[i].ipa, row, col);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

/* consonant place: one "sym\ttt_pos\n" line per consonant (incl. EXTRA),
 * tt_pos runs front (0, lips) to back (1, glottis) */
EXPORT int ipa2v_kb_cons_pos(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NSEG; i++) {
        if (is_vowel_name(NAME_TABLE[i])) continue;
        int n = snprintf(out + L, outsz - L, "%s\t%.4f\n",
                         SEG_TABLE[i].ipa, SEG_TABLE[i].v[2]);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (is_vowel_name(EXTRA_NAMES[i])) continue;
        int n = snprintf(out + L, outsz - L, "%s\t%.4f\n",
                         EXTRA_BASE[i].ipa, EXTRA_BASE[i].v[2]);
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
