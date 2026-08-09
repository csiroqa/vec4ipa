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
    printf("  --width <0-4>          transcription narrowness (default 3)\n");
    printf("  --metric FILE          load metric.json weights/lambda at runtime\n");
    printf("  --charset CLASS        enable reverse charset class (std|extipa|sinologist|all; default std; aliases ext, school, sino)\n");
    printf("  -h, --help             this help\n");
    printf("  -v, --version          version\n");
    printf("\nwith no vector, input is read from stdin\n");
}

#ifdef _WIN32
int wmain(int argc, wchar_t **wargv)
{
    char **argv = argv_utf8_from_wide(argc, wargv);
    if (!argv) { fprintf(stderr, "vec2ipa: out of memory\n"); return 1; }
#else
int main(int argc, char **argv)
{
#endif
    const char *vecstr = NULL;
    const char *seg_a = NULL, *seg_b = NULL;
    const char *outfile = NULL;
    int nearest_only = 0;
    int dist_mode = 0;
    int reverse_given = 0;
    int no_more_opts = 0;

    for (int i = 1; i < argc; i++) {
        const char *val = NULL;
        if (!no_more_opts && strcmp(argv[i], "--") == 0) { no_more_opts = 1; continue; }
        if (opt_match(argv[i], "-h", "--help")) { usage(); return 0; }
        if (opt_school(argv[i])) continue;
        int w = opt_width(argv[i], argc, argv, &i);
        if (w == 1) continue;
        if (w == -1) { fprintf(stderr, "vec2ipa: --width needs 0-4\n"); return 1; }
        int m = opt_metric(argv[i], argc, argv, &i);
        if (m == 1) continue;
        if (m == -1) { fprintf(stderr, "vec2ipa: --metric needs a file\n"); return 1; }
        if (m == -2) return 1;
        int sc = opt_scheme(argv[i], argc, argv, &i);
        if (sc == 1) continue;
        if (sc == -1) { fprintf(stderr, "vec2ipa: --scheme needs a file\n"); return 1; }
        if (sc == -2) return 1;
        int cs = opt_charset(argv[i], argc, argv, &i);
        if (cs == 1) continue;
        if (cs == -1) { fprintf(stderr, "vec2ipa: --charset needs std|extipa|sinologist|all\n"); return 1; }
        if (opt_match(argv[i], "-v", "--version")) {
            printf("vec2ipa %s (16-D vectors, %d base segments, lambda=%.2f)\n",
                   IPA2VEC_VERSION, NSEG, METRIC_LAMBDA);
            return 0;
        }
        if (opt_match(argv[i], "-n", "--nearest")) { nearest_only = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec2ipa: -n/--nearest needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-r", "--reverse")) { reverse_given = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec2ipa: -r/--reverse needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-d", "--distance")) { dist_mode = 1; if (i + 2 < argc) { seg_a = argv[++i]; seg_b = argv[++i]; } else { fprintf(stderr, "vec2ipa: -d/--distance needs two segments\n"); return 1; } continue; }
        int r = opt_match_val(argv[i], "-o", "--output", &val, argc, argv, &i);
        if (r == 1) { outfile = val; continue; }
        if (r == -1) { fprintf(stderr, "vec2ipa: %s needs a file\n", argv[i]); return 1; }
        if ((no_more_opts || argv[i][0] != '-') && !vecstr && !dist_mode) { vecstr = argv[i]; continue; }
        if (strcmp(argv[i], "-") == 0 && !vecstr) { vecstr = "-"; continue; }
        fprintf(stderr, "vec2ipa: unknown option: %s\n", argv[i]);
        return 1;
    }

    if (nearest_only && reverse_given) {
        fprintf(stderr, "vec2ipa: -r/--reverse and -n/--nearest are mutually exclusive\n");
        return 1;
    }
    if (dist_mode && vecstr) {
        fprintf(stderr, "vec2ipa: -d/--distance conflicts with -r/--reverse or -n/--nearest\n");
        return 1;
    }
    if (outfile && redirect_output(outfile, "vec2ipa") != 0)
        return 1;

    if (dist_mode) {
        if (!seg_a || !seg_b) { usage(); return 1; }
        return run_distance(seg_a, seg_b, "vec2ipa");
    }

    if (!vecstr || strcmp(vecstr, "-") == 0) {
        char *in = read_stdin("vec2ipa");
        if (!in) { usage(); return 1; }
        vecstr = in;
    }
    return run_reverse(vecstr, nearest_only);
}
