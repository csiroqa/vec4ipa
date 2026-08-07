/*
 * ipa2vec — IPA/extIPA string → 16-D articulatory vectors.
 *
 * Usage:
 *   ipa2vec [OPTIONS] [STRING]
 *
 *   -i, --ir <STRING>    show two-layer IR, then rebuild IPA
 *   -j, --json <STRING>  JSON output
 *   -o, --output FILE    write output to FILE
 *   -x, --ir-out BASE   export layer1/layer2 to BASE.layer1 / BASE.layer2
 *   -h, --help           this help
 *   -v, --version        version
 *
 * With no STRING, input is read from stdin.
 * Sibling tools: vec2ipa (vectors -> IPA), vec4ipa (inventory).
 */

#include "ipa2vec_core.h"

static void usage(void)
{
    printf("ipa2vec — IPA/extIPA → 16-D articulatory vectors\n\n");
    printf("usage:\n");
    printf("  ipa2vec [OPTIONS] [STRING]\n");
    printf("\noptions:\n");
    printf("  -i, --ir <STRING>     two-layer IR + rebuild demo\n");
    printf("  -j, --json <STRING>   JSON output\n");
    printf("  -o, --output FILE     write output to FILE\n");
    printf("  -x, --ir-out BASE     export IR to BASE.layer1/.layer2\n");
    printf("  -h, --help            this help\n");
    printf("  -v, --version         version\n");
    printf("\nwith no STRING, input is read from stdin\n");
    printf("layer 1 = character order; layer 2 = feature-tier order:\n");
    printf("airstream → laryngeal → place → manner → nasal → timing\n");
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
    int json = 0, ir = 0;
    const char *str = NULL;
    const char *outfile = NULL;
    const char *irbase = NULL;
    int no_more_opts = 0;

    for (int i = 1; i < argc; i++) {
        const char *val = NULL;
        if (!no_more_opts && strcmp(argv[i], "--") == 0) { no_more_opts = 1; continue; }
        if (opt_match(argv[i], "-h", "--help")) { usage(); return 0; }
        if (opt_school(argv[i])) continue;
        if (opt_match(argv[i], "-v", "--version")) {
            printf("ipa2vec %s (16-D vectors, %d base segments, lambda=%.2f)\n",
                   IPA2VEC_VERSION, NSEG, METRIC_LAMBDA);
            return 0;
        }
        if (opt_match(argv[i], "-i", "--ir")) { ir = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "ipa2vec: -i/--ir needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-j", "--json")) { json = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "ipa2vec: -j/--json needs a string\n"); return 1; } continue; }
        int r = opt_match_val(argv[i], "-o", "--output", &val, argc, argv, &i);
        if (r == 1) { outfile = val; continue; }
        if (r == -1) { fprintf(stderr, "ipa2vec: %s needs a file\n", argv[i]); return 1; }
        r = opt_match_val(argv[i], "-x", "--ir-out", &val, argc, argv, &i);
        if (r == 1) { irbase = val; continue; }
        if (r == -1) { fprintf(stderr, "ipa2vec: %s needs a base name\n", argv[i]); return 1; }
        if ((no_more_opts || argv[i][0] != '-') && !str) { str = argv[i]; continue; }
        if (strcmp(argv[i], "-") == 0 && !str) { str = "-"; continue; }
        fprintf(stderr, "ipa2vec: unknown option: %s\n", argv[i]);
        return 1;
    }

    if (outfile && redirect_output(outfile) != 0)
        return 1;
    if (!str || strcmp(str, "-") == 0) {
        char *in = read_stdin();
        if (!in) { usage(); return 1; }
        str = in;
    }

    ParseOut po;
    char err[256];
    if (lex(str, po.layer1, &po.n1, err, sizeof(err))) {
        fprintf(stderr, "ipa2vec: %s\n", err);
        return 1;
    }
    canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
    apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs);

    if (irbase)
        export_ir(po.layer1, po.n1, po.layer2, po.n2, irbase);

    if (ir) {
        printf("input: /%s/\n", str);
        print_layer(po.layer1, po.n1, "layer1 (char order) ");
        print_layer(po.layer2, po.n2, "layer2 (feature order)");
        for (int s = 0; s < po.nsegs; s++) {
            printf("vector[%d]: (", s);
            for (int i = 0; i < NDIM; i++)
                printf("%s%.4f", i ? ", " : "", po.segs[s].v[i]);
            printf(")  %s%s%s\n", AIRSTREAM_LABELS[po.segs[s].airstream],
                   po.segs[s].note[0] ? "  [" : "", po.segs[s].note);
            const SegEntry *b; double d;
            nearest_base(po.segs[s].v, &b, &d);
            const ModRec *mods[IPA2VEC_FIT_MAX_MODS] = {0};
            int nm = fit_modifiers(po.segs[s].v, b, mods);
            char rebuilt[128];
            build_ipa(b, mods, nm, rebuilt, sizeof(rebuilt));
            printf("rebuilt[%d]: /%s/\n", s, rebuilt);
        }
        return 0;
    }

    if (json) {
        printf("{\"input\": \"%s\", \"segments\": [\n", str);
        int first = 1;
        for (int s = 0; s < po.nsegs; s++) {
            if (!first) printf(",\n");
            first = 0;
            printf("    {\"values\": {");
            for (int i = 0; i < NDIM; i++)
                printf("%s\"%s\": %.4f", i ? ", " : "", DIM_NAMES[i], po.segs[s].v[i]);
            printf("}, \"airstream\": \"%s\"}", AIRSTREAM_LABELS[po.segs[s].airstream]);
        }
        printf("\n]}\n");
        return 0;
    }

    for (int s = 0; s < po.nsegs; s++) {
        char label[16];
        snprintf(label, sizeof(label), "[%d]", s);
        print_seg_text(&po.segs[s], label);
    }
    return 0;
}
