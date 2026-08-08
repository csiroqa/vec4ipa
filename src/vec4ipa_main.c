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
    printf("# ipa\tlatin\tlips_closed lips_rounded tongue_tip_pos tongue_tip_height tongue_body_pos "
           "tongue_root vel_open lateral_ratio voiced constricted_glottis spread_glottis laryngeal_tension "
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
    printf("# regional / tradition modules (always on: generic, equiv, withdrawn,\n");
    printf("# uppercase; school modules are off unless enabled with --<name>)\n");
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
    printf("  --charset CLASS        enable reverse charset class (std|extipa|sinologist|all; default std; aliases ext, school, sino)\n");
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

/* -i/-t/-m/-s/-w/-q return immediately, silently dropping any input
 * options parsed before them; say so on stderr when that happens */
static void note_ignored_inputs(const char *opt, int dist_mode,
                                const char *vecstr, int json, int ir,
                                const char *query)
{
    if (dist_mode || vecstr || json || ir || query)
        fprintf(stderr, "vec4ipa: note: %s ignores the input options given before it\n", opt);
}

#ifdef _WIN32
int wmain(int argc, wchar_t **wargv)
{
    char **argv = argv_utf8_from_wide(argc, wargv);
    if (!argv) { fprintf(stderr, "vec4ipa: out of memory\n"); return 1; }
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
    int json = 0, ir = 0, nearest_only = 0, dist_mode = 0, reverse_given = 0;
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
        int cs = opt_charset(argv[i], argc, argv, &i);
        if (cs == 1) continue;
        if (cs == -1) { fprintf(stderr, "vec4ipa: --charset needs std|extipa|sinologist|all\n"); return 1; }
        if (opt_match(argv[i], "-i", "--information")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); printf("%s", EMBEDDED_README); return 0; }
        if (opt_match(argv[i], "-v", "--version")) {
            printf("vec4ipa %s (%d base segments + %d extIPA bases, %d modifiers)\n",
                   IPA2VEC_VERSION, NSEG, N_EXTRA, NMODS);
            return 0;
        }
        if (opt_match(argv[i], "-t", "--table")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); print_table(); return 0; }
        if (opt_match(argv[i], "-m", "--modules")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); print_modules(); return 0; }
        if (opt_match(argv[i], "-s", "--stats")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); print_stats(); return 0; }
        if (opt_match(argv[i], "-w", "--weights")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); print_weights(); return 0; }
        if (opt_match(argv[i], "-j", "--json")) { json = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "vec4ipa: -j/--json needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-e", "--ir")) { ir = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "vec4ipa: -e/--ir needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-n", "--nearest")) { nearest_only = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec4ipa: -n/--nearest needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-r", "--reverse")) { reverse_given = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec4ipa: -r/--reverse needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-d", "--distance")) { dist_mode = 1; if (i + 2 < argc) { seg_a = argv[++i]; seg_b = argv[++i]; } else { fprintf(stderr, "vec4ipa: -d/--distance needs two segments\n"); return 1; } continue; }
        if (opt_match(argv[i], "-q", "--query")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); if (i + 1 < argc) query = argv[++i]; else { fprintf(stderr, "vec4ipa: -q/--query needs a symbol\n"); return 1; } continue; }
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
    if (json && ir) {
        fprintf(stderr, "vec4ipa: -j/--json and -e/--ir are mutually exclusive\n");
        return 1;
    }
    if (vecstr && (json || ir)) {
        fprintf(stderr, "vec4ipa: -r/--reverse conflicts with -j/--json or -e/--ir\n");
        return 1;
    }
    if (nearest_only && reverse_given) {
        fprintf(stderr, "vec4ipa: -r/--reverse and -n/--nearest are mutually exclusive\n");
        return 1;
    }
    if (dist_mode && (vecstr || json || ir)) {
        fprintf(stderr, "vec4ipa: -d/--distance conflicts with -r/--reverse, -n/--nearest, -j/--json or -e/--ir\n");
        return 1;
    }
    if (outfile && redirect_output(outfile, "vec4ipa") != 0)
        return 1;

    if (dist_mode) {
        if (!seg_a || !seg_b) { usage(); return 1; }
        return run_distance(seg_a, seg_b, "vec4ipa");
    }

    if (vecstr)
        return run_reverse(vecstr, nearest_only);

    if (!str || strcmp(str, "-") == 0) {
        char *in = read_stdin("vec4ipa");
        if (!in) { usage(); return 1; }
        str = in;
    }
    return run_forward(str, ir, json, irbase, "vec4ipa");
}
