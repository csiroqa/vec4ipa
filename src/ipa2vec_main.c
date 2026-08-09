/*
 * ipa2vec — IPA/extIPA string → 16-D articulatory vectors.
 *
 * Usage:
 *   ipa2vec [OPTIONS] [STRING]
 *
 *   -L, --layers <STRING> two-layer tier decomposition + rebuild demo
 *   -j, --json <STRING>  JSON output
 *   -o, --output FILE    write output to FILE
 *   -x/-X, --layers-out BASE export layer1/layer2 to BASE.layer1 / BASE.layer2
 *   -i, --information    repository, license, feature overview
 *   -R, --readme         full README.md (embedded)
 *   -h, --help           this help
 *   -v, --version        version
 *
 * With no STRING, input is read from stdin.
 * Sibling tools: vec2ipa (vectors -> IPA), vec4ipa (inventory).
 */

#include "ipa2vec_core.h"
#include "readme_embed.h"

static void usage(void)
{
    printf("ipa2vec — IPA/extIPA → 16-D articulatory vectors\n\n");
    printf("usage:\n");
    printf("  ipa2vec [OPTIONS] [STRING]\n");
    printf("\noptions:\n");
    printf("  -L, --layers <STRING> two-layer tier decomposition + rebuild demo (alias --ir)\n");
    printf("  -j, --json <STRING>   JSON output\n");
    printf("  -A, --align <IPA1> <IPA2> sequence (syllable/word) alignment distance\n");
    printf("  -o, --output FILE     write output to FILE\n");
    printf("  -x/-X, --layers-out BASE export layers to BASE.layer1/.layer2 (alias --ir-out)\n");
    printf("  -i, --information     repository, license, feature overview\n");
    printf("  -R, --readme          full README.md (embedded)\n");
    printf("  -h, --help            this help\n");
    printf("  -N, --narrowness=LEVEL transcription narrowness: broadest|broad|medium|narrow (default)|narrowest (or 0-4; alias --width; --layers only)\n");
    printf("  -M, --metric FILE     load metric.json weights/lambda at runtime\n");
    printf("  -D, --scheme FILE     load custom dimension scheme (ndim/dim/weight/lambda)\n");
    printf("  -S, --symbols=CLASS   reverse output symbols: standard|extipa|sinologist|all (aliases std, ext, school, sino; alias --charset; repeatable; --layers only)\n");
    printf("  -P, --spacing=NAME    modifier spacing: binary (default)|ternary|2:1:2|1:x:1|X (alias --mode)\n");
    printf("  -v, --version         version\n");
    printf("\nwith no STRING, input is read from stdin\n");
    printf("layer 1 = character order; layer 2 = feature-tier order:\n");
    printf("airstream → laryngeal → place → manner → nasal → timing\n");
}

#ifdef _WIN32
int wmain(int argc, wchar_t **wargv)
{
    char **argv = argv_utf8_from_wide(argc, wargv);
    if (!argv) { fprintf(stderr, "ipa2vec: out of memory\n"); return 1; }
#else
int main(int argc, char **argv)
{
#endif
    int json = 0, ir = 0, align_mode = 0;
    const char *str = NULL;
    const char *seg_a = NULL, *seg_b = NULL;
    const char *outfile = NULL;
    const char *irbase = NULL;
    int no_more_opts = 0;

    for (int i = 1; i < argc; i++) {
        const char *val = NULL;
        if (!no_more_opts && strcmp(argv[i], "--") == 0) { no_more_opts = 1; continue; }
        if (opt_match(argv[i], "-h", "--help")) { usage(); return 0; }
        if (opt_match(argv[i], "-i", "--information")) { print_info("ipa2vec"); return 0; }
        if (opt_match(argv[i], "-R", "--readme")) { printf("%s", EMBEDDED_README); return 0; }
        if (opt_school(argv[i])) continue;
        int w = opt_width(argv[i], argc, argv, &i);
        if (w == 1) continue;
        if (w == -1) { fprintf(stderr, "ipa2vec: --narrowness needs broadest|broad|medium|narrow|narrowest|0-4\n"); return 1; }
        int m = opt_metric(argv[i], argc, argv, &i);
        if (m == 1) continue;
        if (m == -1) { fprintf(stderr, "ipa2vec: --metric needs a file\n"); return 1; }
        if (m == -2) return 1;
        int sc = opt_scheme(argv[i], argc, argv, &i);
        if (sc == 1) continue;
        if (sc == -1) { fprintf(stderr, "ipa2vec: --scheme needs a file\n"); return 1; }
        if (sc == -2) return 1;
        int cs = opt_charset(argv[i], argc, argv, &i);
        if (cs == 1) continue;
        if (cs == -1) { fprintf(stderr, "ipa2vec: --symbols needs standard|extipa|sinologist|all\n"); return 1; }
        int ms = opt_mod_spacing(argv[i], argc, argv, &i);
        if (ms == 1) continue;
        if (ms == -1) { fprintf(stderr, "ipa2vec: --spacing needs binary|ternary|2:1:2|1:x:1|0-10\n"); return 1; }
        if (opt_match(argv[i], "-v", "--version")) {
            printf("ipa2vec %s (16-D vectors, %d base segments, lambda=%.2f)\n",
                   IPA2VEC_VERSION, NSEG, METRIC_LAMBDA);
            return 0;
        }
        if (opt_match(argv[i], "-L", "--layers") || opt_match(argv[i], "-e", "--ir")) { ir = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "ipa2vec: -L/--layers needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-j", "--json")) { json = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "ipa2vec: -j/--json needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-A", "--align")) { align_mode = 1; if (i + 2 < argc) { seg_a = argv[++i]; seg_b = argv[++i]; } else { fprintf(stderr, "ipa2vec: -A/--align needs two IPA strings\n"); return 1; } continue; }
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

    if (ir && json) {
        fprintf(stderr, "ipa2vec: -L/--layers and -j/--json are mutually exclusive\n");
        return 1;
    }
    if (align_mode && (ir || json)) {
        fprintf(stderr, "ipa2vec: -A/--align conflicts with -L/--layers or -j/--json\n");
        return 1;
    }
    if (outfile && redirect_output(outfile, "ipa2vec") != 0)
        return 1;
    if (align_mode) {
        if (!seg_a || !seg_b) { usage(); return 1; }
        return run_align(seg_a, seg_b, "ipa2vec");
    }
    if (!str || strcmp(str, "-") == 0) {
        char *in = read_stdin("ipa2vec");
        if (!in) { usage(); return 1; }
        str = in;
    }
    return run_forward(str, ir, json, irbase, "ipa2vec");
}
