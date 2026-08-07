/*
 * vec4ipa — the complete IPA vector inventory (both directions + query).
 *
 * Usage:
 *   vec4ipa [OPTIONS]
 *
 *   -i, --information      the full documentation (embedded README)
 *   -h, --help             this help
 *   -t, --table            full base table (main + extIPA bases)
 *   -m, --modules          regional modules and their symbols
 *   -q, --query <SYM>      query one symbol
 *   -s, --stats            statistics
 *   -w, --weights          metric weights / lambda
 *   -r, --reverse <VEC>    vectors -> IPA (nearest + modifier fit)
 *   -n, --nearest <VEC>    nearest base segment only
 *   -d, --distance <A> <B> weighted distance
 *   -j, --json <STRING>    forward IPA -> vectors, JSON output
 *   -e, --ir <STRING>      forward IPA -> vectors, two-layer IR
 *   -o, --output FILE      write output to FILE
 *   -x, --ir-out BASE      export IR to BASE.layer1/.layer2
 *   -v, --version          version
 *
 * With no input string, forward direction reads from stdin.
 * Sibling tools: ipa2vec (IPA -> vectors), vec2ipa (vectors -> IPA).
 */

#include "ipa2vec_core.h"
#include "readme_embed.h"

static void print_table(void)
{
    printf("# ipa\tlatin\tlips_closed lips_rounded tt_pos tt_height tb_pos "
           "tongue_root vel_open lateral_ratio voiced cg sg laryngeal_tension "
           "duration jet_focus effective_oral_area airflow_direction\tairstream\n");
    for (int i = 0; i < NSEG; i++) {
        printf("%s\t%s\t", SEG_TABLE[i].ipa, NAME_TABLE[i]);
        for (int j = 0; j < NDIM; j++)
            printf("%s%.4f", j ? " " : "", SEG_TABLE[i].v[j]);
        printf("\t%s\n", AIRSTREAM_LABELS[SEG_TABLE[i].airstream]);
    }
    printf("# extIPA bases (EXTRA_BASE):\n");
    for (int i = 0; i < N_EXTRA; i++) {
        printf("%s\t%s\t", EXTRA_BASE[i].ipa, EXTRA_NAMES[i]);
        for (int j = 0; j < NDIM; j++)
            printf("%s%.4f", j ? " " : "", EXTRA_BASE[i].v[j]);
        printf("\t%s\n", AIRSTREAM_LABELS[EXTRA_BASE[i].airstream]);
    }
}

static void print_modules(void)
{
    printf("# regional / tradition modules (all active)\n");
    for (int m = 0; m < N_ALIAS_MODULES; m++) {
        printf("[%s] %d symbols\n", ALIAS_MODULES[m].name, ALIAS_MODULES[m].n);
        for (int i = 0; i < ALIAS_MODULES[m].n; i++) {
            const Alias *a = &ALIAS_MODULES[m].tab[i];
            printf("    %-8s -> %-12s %s%s\n", a->sym, a->repl,
                   a->note ? a->note : "",
                   a->warn ? "  [deprecated]" : "");
        }
    }
    printf("\n# modifier code points: %d\n", NMODS);
}

static void query_symbol(const char *sym)
{
    for (int i = 0; i < NSEG; i++) {
        if (strcmp(SEG_TABLE[i].ipa, sym) == 0) {
            printf("base: /%s/  %s  (%s)\n  (", SEG_TABLE[i].ipa,
                   NAME_TABLE[i], AIRSTREAM_LABELS[SEG_TABLE[i].airstream]);
            for (int j = 0; j < NDIM; j++)
                printf("%s%.4f", j ? ", " : "", SEG_TABLE[i].v[j]);
            printf(")\n");
            return;
        }
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (strcmp(EXTRA_BASE[i].ipa, sym) == 0) {
            printf("extIPA base: /%s/  %s  (%s)\n  (", EXTRA_BASE[i].ipa,
                   EXTRA_NAMES[i], AIRSTREAM_LABELS[EXTRA_BASE[i].airstream]);
            for (int j = 0; j < NDIM; j++)
                printf("%s%.4f", j ? ", " : "", EXTRA_BASE[i].v[j]);
            printf(")\n");
            return;
        }
    }
    const unsigned char *u = (const unsigned char *)sym;
    unsigned long cp = 0;
    if (utf8_decode(u, &cp)) {
        const ModRec *m = find_mod(cp);
        if (m) {
            printf("modifier: %s  %s  tier=%d%s%s\n", m->ipa, m->latin,
                   (int)m->tier,
                   m->air >= 0 ? "  [sets airstream]" : "",
                   m->infer ? "  [inference]" : "");
            return;
        }
    }
    const Alias *a = lookup_alias(sym, 0);
    if (a) {
        printf("alias: '%s' -> %s (%s)%s\n", a->sym, a->repl, a->note,
               a->warn ? "  [deprecated]" : "");
        return;
    }
    printf("not found: %s\n", sym);
}

static void print_stats(void)
{
    int nmod = 0;
    for (int m = 0; m < N_ALIAS_MODULES; m++)
        nmod += ALIAS_MODULES[m].n;
    printf("base segments (SEG_TABLE):   %d\n", NSEG);
    printf("extIPA bases (EXTRA_BASE):   %d\n", N_EXTRA);
    printf("modifiers (MODS):            %d\n", NMODS);
    printf("precomposed chars:           %d\n", NPRECOMP);
    printf("alias modules:               %d (%d symbols)\n", N_ALIAS_MODULES, nmod);
    printf("implicit affricates:         %d\n", NNOLIG);
    printf("dimensions:                  %d\n", NDIM);
    metric_ensure();
    printf("lambda:                      %.2f\n", g_metric_lambda);
    printf("airstreams:                  %s | %s | %s | %s | %s\n",
           AIRSTREAM_LABELS[0], AIRSTREAM_LABELS[1],
           AIRSTREAM_LABELS[2], AIRSTREAM_LABELS[3], AIRSTREAM_LABELS[4]);
}

static void print_weights(void)
{
    metric_ensure();
    printf("# dimension weights (metric.json v4, refit to Phatak 2008 + MN55)\n");
    printf("# --metric FILE overrides these at runtime\n");
    for (int i = 0; i < NDIM; i++)
        printf("%2d  %-22s %8.4f\n", i, DIM_NAMES[i],
               g_metric_full ? g_metric_M[i][i] : g_metric_w[i]);
    if (g_metric_full)
        printf("# full 16x16 metric matrix in effect (off-diagonal terms active)\n");
    printf("lambda (airstream penalty):  %.2f\n", g_metric_lambda);
}

static void usage(void)
{
    printf("vec4ipa — complete IPA vector inventory (both directions)\n\n");
    printf("usage:\n");
    printf("  vec4ipa [OPTIONS]\n");
    printf("\noptions:\n");
    printf("  -i, --information      full documentation (embedded README)\n");
    printf("  -h, --help             this help\n");
    printf("  --width <0-4>          transcription narrowness (default 3)\n");
    printf("  --metric FILE          load metric.json weights/lambda at runtime\n");
    printf("  -t, --table            full base table\n");
    printf("  -m, --modules          regional modules\n");
    printf("  -q, --query SYM        query a symbol\n");
    printf("  -s, --stats            statistics\n");
    printf("  -w, --weights          metric weights / lambda\n");
    printf("  -r, --reverse VEC      vectors -> IPA (nearest + modifier fit)\n");
    printf("  -n, --nearest VEC      nearest base segment only\n");
    printf("  -d, --distance A B     weighted distance\n");
    printf("  -j, --json STRING      forward IPA -> vectors, JSON\n");
    printf("  -e, --ir STRING        forward IPA -> vectors, two-layer IR\n");
    printf("  -o, --output FILE      write output to FILE\n");
    printf("  -x, --ir-out BASE      export IR to BASE.layer1/.layer2\n");
    printf("  -v, --version          version\n");
    printf("\nwith no input string, forward direction reads from stdin\n");
}

/* forward: IPA -> vectors */
static int run_forward(const char *str, int ir, int json, const char *irbase)
{
    ParseOut po;
    char err[256];
    if (lex(str, po.layer1, &po.n1, err, sizeof(err))) {
        fprintf(stderr, "vec4ipa: %s\n", err);
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
    const char *outfile = NULL;
    const char *irbase = NULL;
    const char *str = NULL;          /* forward IPA string */
    const char *vecstr = NULL;       /* reverse vector */
    const char *seg_a = NULL, *seg_b = NULL;
    const char *query = NULL;
    int json = 0, ir = 0, nearest_only = 0, dist_mode = 0;
    int no_more_opts = 0;

    for (int i = 1; i < argc; i++) {
        const char *val = NULL;
        if (!no_more_opts && strcmp(argv[i], "--") == 0) { no_more_opts = 1; continue; }
        if (opt_match(argv[i], "-h", "--help")) { usage(); return 0; }
        if (opt_school(argv[i])) continue;
        int w = opt_width(argv[i], argc, argv, &i);
        if (w == 1) continue;
        if (w == -1) { fprintf(stderr, "vec4ipa: --width needs 0-4\n"); return 1; }
        int m = opt_metric(argv[i], argc, argv, &i);
        if (m == 1) continue;
        if (m == -1) { fprintf(stderr, "vec4ipa: --metric needs a file\n"); return 1; }
        if (m == -2) return 1;
        if (opt_match(argv[i], "-i", "--information")) { printf("%s", EMBEDDED_README); return 0; }
        if (opt_match(argv[i], "-v", "--version")) {
            printf("vec4ipa %s (%d base segments + %d extIPA bases, %d modifiers)\n",
                   IPA2VEC_VERSION, NSEG, N_EXTRA, NMODS);
            return 0;
        }
        if (opt_match(argv[i], "-t", "--table")) { print_table(); return 0; }
        if (opt_match(argv[i], "-m", "--modules")) { print_modules(); return 0; }
        if (opt_match(argv[i], "-s", "--stats")) { print_stats(); return 0; }
        if (opt_match(argv[i], "-w", "--weights")) { print_weights(); return 0; }
        if (opt_match(argv[i], "-j", "--json")) { json = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "vec4ipa: -j/--json needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-e", "--ir")) { ir = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "vec4ipa: -e/--ir needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-n", "--nearest")) { nearest_only = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec4ipa: -n/--nearest needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-r", "--reverse")) { if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec4ipa: -r/--reverse needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-d", "--distance")) { dist_mode = 1; if (i + 2 < argc) { seg_a = argv[++i]; seg_b = argv[++i]; } else { fprintf(stderr, "vec4ipa: -d/--distance needs two segments\n"); return 1; } continue; }
        if (opt_match(argv[i], "-q", "--query")) { if (i + 1 < argc) query = argv[++i]; else { fprintf(stderr, "vec4ipa: -q/--query needs a symbol\n"); return 1; } continue; }
        int r = opt_match_val(argv[i], "-o", "--output", &val, argc, argv, &i);
        if (r == 1) { outfile = val; continue; }
        if (r == -1) { fprintf(stderr, "vec4ipa: %s needs a file\n", argv[i]); return 1; }
        r = opt_match_val(argv[i], "-x", "--ir-out", &val, argc, argv, &i);
        if (r == 1) { irbase = val; continue; }
        if (r == -1) { fprintf(stderr, "vec4ipa: %s needs a base name\n", argv[i]); return 1; }
        if ((no_more_opts || argv[i][0] != '-') && !str && !vecstr) { str = argv[i]; continue; }
        if (strcmp(argv[i], "-") == 0 && !str) { str = "-"; continue; }
        fprintf(stderr, "vec4ipa: unknown option: %s\n", argv[i]);
        return 1;
    }

    if (query) { query_symbol(query); return 0; }
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

    if (vecstr) {
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
        order_mods(mods, nm);   /* canonical order — same as the rebuilt IPA */
        char ipa[128];
        build_ipa(b, mods, nm, ipa, sizeof(ipa));
        printf("/%s/  (%s", b->ipa, base_name(b));
        for (int j = 0; j < nm; j++) printf(" +%s", mods[j]->latin);
        printf(")  d=%.4f  ->  /%s/\n", d, ipa);
        return 0;
    }

    if (!str || strcmp(str, "-") == 0) {
        char *in = read_stdin();
        if (!in) { usage(); return 1; }
        str = in;
    }
    return run_forward(str, ir, json, irbase);
}
