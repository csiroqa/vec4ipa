/*
 * vec2ipa — 16-D articulatory vector → IPA/extIPA.
 *
 * Usage:
 *   vec2ipa [OPTIONS] [V0,...,V15]
 *
 *   -r, --reverse <VEC>   nearest segment + modifier fit -> IPA (default)
 *   -n, --nearest <VEC>   nearest base segment only
 *   -d, --distance <A> <B>  weighted distance (Mahalanobis + airstream)
 *   -o, --output FILE     write output to FILE
 *   -h, --help            this help
 *   -v, --version         version
 *
 * With no vector, input is read from stdin.
 * Sibling tools: ipa2vec (IPA -> vectors), vec4ipa (inventory).
 */

#include "ipa2vec_core.h"

static int parse_vector_arg(const char *s, double out[NDIM])
{
    char buf[512];
    snprintf(buf, sizeof(buf), "%s", s);
    char *tok = strtok(buf, ", \t");
    int i = 0;
    while (tok && i < NDIM) {
        char *endp = NULL;
        double x = strtod(tok, &endp);
        if (endp == tok) return -1;
        out[i++] = x;
        tok = strtok(NULL, ", \t");
    }
    return (i == NDIM) ? 0 : -1;
}

static void usage(void)
{
    printf("vec2ipa — 16-D articulatory vectors → IPA/extIPA\n\n");
    printf("usage:\n");
    printf("  vec2ipa [OPTIONS] [V0,...,V15]\n");
    printf("\noptions:\n");
    printf("  -r, --reverse <VEC>    nearest segment + modifier fit -> IPA (default)\n");
    printf("  -n, --nearest <VEC>    nearest base segment only\n");
    printf("  -d, --distance <A> <B> weighted distance\n");
    printf("  -o, --output FILE      write output to FILE\n");
    printf("  -h, --help             this help\n");
    printf("  -v, --version          version\n");
    printf("\nwith no vector, input is read from stdin\n");
}

#ifdef _WIN32
int wmain(int argc, wchar_t **wargv)
{
    g_argc_utf8 = argc;
    g_argv_utf8 = (char **)calloc((size_t)argc, sizeof(char *));
    for (int i = 0; i < argc; i++)
        g_argv_utf8[i] = wide_to_utf8(wargv[i]);
    char **argv = g_argv_utf8;
#else
int main(int argc, char **argv)
{
#endif
    const char *vecstr = NULL;
    const char *seg_a = NULL, *seg_b = NULL;
    const char *outfile = NULL;
    int nearest_only = 0;
    int dist_mode = 0;
    int no_more_opts = 0;

    for (int i = 1; i < argc; i++) {
        const char *val = NULL;
        if (!no_more_opts && strcmp(argv[i], "--") == 0) { no_more_opts = 1; continue; }
        if (opt_match(argv[i], "-h", "--help")) { usage(); return 0; }
        if (opt_school(argv[i])) continue;
        if (opt_match(argv[i], "-v", "--version")) {
            printf("vec2ipa %s (16-D vectors, %d base segments, lambda=%.2f)\n",
                   IPA2VEC_VERSION, NSEG, METRIC_LAMBDA);
            return 0;
        }
        if (opt_match(argv[i], "-n", "--nearest")) { nearest_only = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec2ipa: -n/--nearest needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-r", "--reverse")) { if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec2ipa: -r/--reverse needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-d", "--distance")) { dist_mode = 1; if (i + 2 < argc) { seg_a = argv[++i]; seg_b = argv[++i]; } else { fprintf(stderr, "vec2ipa: -d/--distance needs two segments\n"); return 1; } continue; }
        int r = opt_match_val(argv[i], "-o", "--output", &val, argc, argv, &i);
        if (r == 1) { outfile = val; continue; }
        if (r == -1) { fprintf(stderr, "vec2ipa: %s needs a file\n", argv[i]); return 1; }
        if ((no_more_opts || argv[i][0] != '-') && !vecstr && !dist_mode) { vecstr = argv[i]; continue; }
        if (strcmp(argv[i], "-") == 0 && !vecstr) { vecstr = "-"; continue; }
        fprintf(stderr, "vec2ipa: unknown option: %s\n", argv[i]);
        return 1;
    }

    if (outfile && redirect_output(outfile) != 0)
        return 1;

    if (dist_mode) {
        if (!seg_a || !seg_b) { usage(); return 1; }
        ParseOut a, b;
        char err[256];
        if (lex(seg_a, a.layer1, &a.n1, err, sizeof(err)) ||
            lex(seg_b, b.layer1, &b.n1, err, sizeof(err))) {
            fprintf(stderr, "parse error: %s\n", err);
            return 1;
        }
        canonicalise(a.layer1, a.n1, a.layer2, &a.n2);
        canonicalise(b.layer1, b.n1, b.layer2, &b.n2);
        apply_layer2(a.layer2, a.n2, a.segs, &a.nsegs);
        apply_layer2(b.layer2, b.n2, b.segs, &b.nsegs);
        if (a.nsegs != 1 || b.nsegs != 1) {
            fprintf(stderr, "need exactly one segment per argument\n");
            return 1;
        }
        printf("%.4f\n", seg_dist_full(&a.segs[0], &b.segs[0]));
        return 0;
    }

    if (!vecstr || strcmp(vecstr, "-") == 0) {
        char *in = read_stdin();
        if (!in) { usage(); return 1; }
        vecstr = in;
    }

    double v[NDIM];
    if (parse_vector_arg(vecstr, v) != 0) {
        fprintf(stderr, "bad vector: need %d comma-separated values\n", NDIM);
        return 1;
    }

    const SegEntry *b; double d;
    nearest_base(v, &b, &d);

    if (nearest_only) {
        printf("/%s/  %s  d=%.4f  (%s)\n", b->ipa, base_name(b),
               d, AIRSTREAM_LABELS[b->airstream]);
        return 0;
    }

    const ModRec *mods[IPA2VEC_FIT_MAX_MODS] = {0};
    int nm = fit_modifiers(v, b, mods);
    char ipa[128];
    build_ipa(b, mods, nm, ipa, sizeof(ipa));
    printf("/%s/  (%s", b->ipa, base_name(b));
    for (int j = 0; j < nm; j++) printf(" +%s", mods[j]->latin);
    printf(")  d=%.4f  ->  /%s/\n", d, ipa);
    return 0;
}
