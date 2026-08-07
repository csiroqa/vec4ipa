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

    set_width_global(width);

    const SegEntry *b; double d;
    nearest_base(vv, &b, &d);
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
 *   cons: all SEG_TABLE entries except vowels, then EXTRA_BASE
 *   vowels: SEG_TABLE entries with airstream==VWL
 *   mods:  all MODS
 * Returns number of symbols written. */
EXPORT int ipa2v_kb_cons(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NSEG; i++) {
        if (SEG_TABLE[i].airstream == 1) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", SEG_TABLE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    for (int i = 0; i < N_EXTRA; i++) {
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
        if (SEG_TABLE[i].airstream != 1) continue;
        int n = snprintf(out + L, outsz - L, "%s\n", SEG_TABLE[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

EXPORT int ipa2v_kb_mods(char *out, size_t outsz)
{
    size_t L = 0;
    for (int i = 0; i < NMODS; i++) {
        int n = snprintf(out + L, outsz - L, "%s\n", MODS[i].ipa);
        if (n < 0 || (size_t)n >= outsz - L) break;
        L += n;
    }
    return (int)L;
}

EXPORT const char *ipa2v_version(void)
{
    return IPA2VEC_VERSION;
}
