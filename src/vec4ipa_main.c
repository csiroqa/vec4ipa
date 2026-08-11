/*
 * vec4ipa — the complete IPA vector inventory (both directions + query).
 *
 * Usage:
 *   vec4ipa [OPTIONS]
 *
 *   -i, --information      repository, license, feature overview
 *   -R, --readme          full README.md (embedded)
 *   -t, --table            full base table (main + extIPA bases)
 *   -m, --modules          regional modules and their symbols
 *   -q, --query <SYM>      query a symbol (or a base + modifier string)
 *   -s, --stats            statistics
 *   -w, --weights          metric weights / lambda
 *   -r, --reverse <VEC>    vectors -> IPA (nearest + modifier fit)
 *   -n, --nearest <VEC>    nearest base segment only
 *   -d, --distance <A> <B> weighted distance
 *   -j, --json <STRING>    forward IPA -> vectors, JSON output
 *   -e, --ir <STRING>      forward IPA -> vectors, two-layer IR
 *   -o, --output FILE      write output to FILE
 *   -x/-X, --layers-out BASE export layers to BASE.layer1/.layer2 (alias --ir-out)
 *   -v, --version          version
 *
 * With no input string, forward direction reads from stdin.
 * Sibling tools: ipa2vec (IPA -> vectors), vec2ipa (vectors -> IPA).
 */

#include "ipa2vec_core.h"
#include "readme_embed.h"

static void print_table(void)
{
    printf("# ipa\tlatin\t");
    for (int j = 0; j < NDIM; j++)
        printf("%s%s", j ? " " : "", DIM_NAMES[j]);
    printf("\tairstream\n");
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

/* latin modifier tag -> English word, for the near-natural-language
 * reading of a parsed segment (unknown tags pass through as-is) */
static const char *mod_word(const char *tag)
{
    static const struct { const char *tag; const char *word; } W[] = {
        { "vl", "voiceless" }, { "vd", "voiced" },
        { "asp", "aspirated" }, { "weak_asp", "weakly aspirated" },
        { "breathy", "breathy" }, { "breathy_asp", "breathy aspirated" },
        { "creaky", "creaky" }, { "fortis", "fortis" }, { "lenis", "lenis" },
        { "nas", "nasalised" }, { "nas_rel", "nasal release" },
        { "nasal_rel", "nasalised" }, { "nas_click", "nasalised click" },
        { "unrel", "no audible release" },
        { "syl", "syllabic" }, { "nsyl", "non-syllabic" },
        { "raised", "raised" }, { "lowered", "lowered" },
        { "adv", "advanced" }, { "retr", "retracted" },
        { "atr", "advanced tongue root" }, { "rtr", "retracted tongue root" },
        { "rnd_more", "more rounded" }, { "rnd_less", "less rounded" },
        { "centralized", "centralised" }, { "midcent", "mid-centralised" },
        { "dental", "dentalised" }, { "alveolar", "alveolarised" },
        { "apical", "apical" }, { "laminal", "laminal" }, { "lam", "laminal" },
        { "linguolabial", "linguolabial" }, { "labiodental", "labiodental" },
        { "pal", "palatalised" }, { "pal_hook", "palatalised" },
        { "pal_prime", "palatalised" }, { "vel", "velarised" },
        { "phar", "pharyngealised" }, { "lab", "labialised" },
        { "lab_subw", "labialised" }, { "retroflex", "retroflex" },
        { "dark", "velarised" }, { "light", "palatalised" },
        { "whistled", "whistled" },
        { "lat_release", "lateral release" },
        { "fric_release", "fricative release" },
        { "schwa_rel", "schwa-coloured" }, { "rhot", "rhotacised" },
        { "ej", "ejective" }, { "glottal_onset", "glottal onset" },
        { "long", "long" }, { "half", "half-long" }, { "short", "extra-short" },
        { "gemination", "geminated" }, { "lengthened", "lengthened" },
        { "sliding", "sliding" }, { "tie", "tied" },
        { "offglide_pal", "palatal offglide" },
        { "offglide_lab", "labial offglide" },
        { "offglide_labpal", "labial-palatal offglide" },
        { "sup_rhot_r", "r-coloured release" },
        { "sup_rhot_\xC9\xA2", "r-coloured release" },
        { "sup_rhot_\xC9\x95", "r-coloured release" },
        { "sup_rhot_\xC9\x81", "r-coloured release" },
        { "sup_\xC9\x9B", "superscript \xC9\x9B" },
        { "sup_e", "superscript e" }, { "sup_u", "superscript u" },
        { "sup_d", "superscript d" }, { "sup_N", "superscript n" },
        { "sup_A", "superscript a" }, { "sup_B", "superscript b" },
        { "sup_O", "superscript o" }, { "sup_P", "superscript p" },
        { "sup_U", "superscript u" }, { "sup_W", "superscript w" },
        { "sub_i", "subscript i" }, { "sub_r", "subscript r" },
        { "tone_5", "top tone" }, { "tone_4", "high tone" },
        { "tone_3", "mid tone" }, { "tone_2", "low tone" },
        { "tone_1", "lowest tone" },
    };
    for (size_t i = 0; i < sizeof(W) / sizeof(W[0]); i++)
        if (strcmp(W[i].tag, tag) == 0)
            return W[i].word;
    return tag;
}

/* describe one parsed segment in near-natural language */
static void print_seg_query(int s, const ParseOut *po, const char *const *bases,
                            const char *const *names, int nb,
                            const char *spelled)
{
    const SegVec *sv = &po->segs[s];
    printf("[%d] /%s/ = ", s, spelled);
    for (int j = 0; j < nb; j++) {
        if (j) printf(" + ");
        if (bases[j])
            printf("/%s/ (%s)", bases[j], names[j]);
        else
            printf("(%s)", names[j]);
    }
    char words[192] = "";
    const char *n = sv->note;
    while (*n) {
        const char *e = strchr(n, ',');
        size_t L = e ? (size_t)(e - n) : strlen(n);
        char tag[40];
        if (L >= sizeof(tag)) L = sizeof(tag) - 1;
        memcpy(tag, n, L);
        tag[L] = 0;
        if (words[0]) strncat(words, ", ", sizeof(words) - strlen(words) - 1);
        strncat(words, mod_word(tag), sizeof(words) - strlen(words) - 1);
        n = e ? e + 1 : n + L;
    }
    if (words[0])
        printf(" + [%s]", words);
    printf("  (%s)\n", AIRSTREAM_LABELS[sv->airstream]);
    printf("    vector: (");
    for (int j = 0; j < NDIM; j++)
        printf("%s%.4f", j ? ", " : "", sv->v[j]);
    printf(")");
    print_tone(sv);
    printf("\n");
}

/* describe a parsed multi-symbol string in near-natural language:
 * group the layer1 tokens into segments (a TK_LIG continues the
 * segment, everything else starts a new one) */
static void describe_segments(const ParseOut *po)
{
    const char *bases[8];
    const char *names[8];
    char spelled[128];
    char pending[32];   /* preposed tokens (airstream marks) of the next segment */
    int nb = 0, s = 0;
    size_t sl = 0, pl = 0;
    spelled[0] = 0;
    pending[0] = 0;

    for (int i = 0; i < po->n1 && s < po->nsegs; i++) {
        const IrTok *t = &po->layer1[i];
        if (t->kind == TK_BASE) {
            int cont = (i > 0 && po->layer1[i - 1].kind == TK_LIG);
            if (!cont && nb > 0) {
                print_seg_query(s++, po, bases, names, nb, spelled);
                nb = 0;
                sl = 0;
                spelled[0] = 0;
            }
            if (pl) {
                memcpy(spelled + sl, pending, pl);
                sl += pl;
                spelled[sl] = 0;
                pl = 0;
            }
            if (nb < 8) {
                bases[nb] = t->seg ? t->seg->ipa : NULL;
                names[nb] = t->seg ? base_name(t->seg) : t->latin;
                nb++;
            }
            size_t L = strlen(t->ipa);
            if (sl + L < sizeof(spelled) - 1) {
                memcpy(spelled + sl, t->ipa, L);
                sl += L;
                spelled[sl] = 0;
            }
        } else if (t->kind == TK_MOD) {
            const char *p0 = t->ipa;
            if (strncmp(p0, "\xE2\x97\x8C", 3) == 0)
                p0 += 3;   /* strip the dotted-circle placeholder */
            size_t L = strlen(p0);
            if (nb == 0) {
                if (pl + L < sizeof(pending) - 1) {
                    memcpy(pending + pl, p0, L);
                    pl += L;
                    pending[pl] = 0;
                }
            } else if (sl + L < sizeof(spelled) - 1) {
                memcpy(spelled + sl, p0, L);
                sl += L;
                spelled[sl] = 0;
            }
        } else if (t->kind == TK_LIG) {
            const char *p0 = t->ipa;
            if (strncmp(p0, "\xE2\x97\x8C", 3) == 0)
                p0 += 3;   /* strip the dotted-circle placeholder */
            size_t L = strlen(p0);
            if (sl + L < sizeof(spelled) - 1) {
                memcpy(spelled + sl, p0, L);
                sl += L;
                spelled[sl] = 0;
            }
        }
    }
    if (nb > 0 && s < po->nsegs)
        print_seg_query(s, po, bases, names, nb, spelled);
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
    int uk = utf8_decode(u, &cp);
    if (uk && !u[uk]) {   /* exactly one code point */
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
    if (a && strcmp(a->sym, sym) == 0) {
        printf("alias: '%s' -> %s (%s)%s\n", a->sym, a->repl, a->note,
               a->warn ? "  [deprecated]" : "");
        return;
    }
    /* composite string (base + modifiers): run the full parse pipeline
     * and describe every segment in near-natural language */
    ParseOut po;
    char err[256];
    if (lex(sym, po.layer1, &po.n1, err, sizeof(err)) == 0) {
        canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
        if (apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs, "vec4ipa") == 0 &&
            po.nsegs > 0)
        {
            describe_segments(&po);
            return;
        }
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
    printf("# dimension weights (compiled-in defaults from spec_next.scheme)\n");
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
    printf("  -i, --information     repository, license, feature overview\n");
    printf("  -R, --readme          full README.md (embedded)\n");
    printf("  -N, --narrowness=LEVEL transcription narrowness: broadest|broad|medium|narrow (default)|narrowest (or 0-4; alias --width)\n");
    printf("  -M, --metric FILE     load metric.json weights/lambda at runtime\n");
    printf("  -D, --scheme FILE     load custom dimension scheme (ndim/dim/weight/lambda)\n");
    printf("  -S, --symbols=CLASS   reverse output symbols: standard|extipa|sinologist|all (aliases std, ext, school, sino; alias --charset; repeatable)\n");
    printf("  -P, --spacing=NAME    modifier spacing: binary (default)|ternary|2:1:2|1:x:1|X (alias --mode)\n");
    printf("  -t, --table            full base table\n");
    printf("  -m, --modules          regional modules\n");
    printf("  -q, --query SYM        query a symbol, or parse a base + modifier string\n");
    printf("  -s, --stats            statistics\n");
    printf("  -w, --weights          metric weights / lambda\n");
    printf("  -r, --reverse VEC      vectors -> IPA (nearest + modifier fit)\n");
    printf("  -n, --nearest VEC      nearest base segment only\n");
    printf("  -d, --distance A B     weighted distance\n");
    printf("  -A, --align IPA1 IPA2  sequence (syllable/word) alignment distance\n");
    printf("  -j, --json STRING      forward IPA -> vectors, JSON\n");
    printf("  -e/-L, --layers STRING forward IPA -> vectors, two-layer tier decomposition (alias --ir)\n");
    printf("  -o, --output FILE      write output to FILE\n");
    printf("  -x/-X, --layers-out BASE export layers to BASE.layer1/.layer2 (alias --ir-out)\n");
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
    int align_mode = 0;
    int no_more_opts = 0;

    for (int i = 1; i < argc; i++) {
        const char *val = NULL;
        if (!no_more_opts && strcmp(argv[i], "--") == 0) { no_more_opts = 1; continue; }
        if (opt_match(argv[i], "-h", "--help")) { usage(); return 0; }
        if (opt_school(argv[i])) continue;
        int w = opt_width(argv[i], argc, argv, &i);
        if (w == 1) continue;
        if (w == -1) { fprintf(stderr, "vec4ipa: --narrowness needs broadest|broad|medium|narrow|narrowest|0-4\n"); return 1; }
        int m = opt_metric(argv[i], argc, argv, &i);
        if (m == 1) continue;
        if (m == -1) { fprintf(stderr, "vec4ipa: --metric needs a file\n"); return 1; }
        if (m == -2) return 1;
        int sc = opt_scheme(argv[i], argc, argv, &i);
        if (sc == 1) continue;
        if (sc == -1) { fprintf(stderr, "vec4ipa: --scheme needs a file\n"); return 1; }
        if (sc == -2) return 1;
        int cs = opt_charset(argv[i], argc, argv, &i);
        if (cs == 1) continue;
        if (cs == -1) { fprintf(stderr, "vec4ipa: --symbols needs standard|extipa|sinologist|all\n"); return 1; }
        int ms = opt_mod_spacing(argv[i], argc, argv, &i);
        if (ms == 1) continue;
        if (ms == -1) { fprintf(stderr, "vec4ipa: --spacing needs binary|ternary|2:1:2|1:x:1|0-10\n"); return 1; }
        if (opt_match(argv[i], "-i", "--information")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); print_info("vec4ipa"); return 0; }
        if (opt_match(argv[i], "-R", "--readme")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); printf("%s", EMBEDDED_README); return 0; }
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
        if (opt_match(argv[i], "-e", "--ir") || opt_match(argv[i], "-L", "--layers")) { ir = 1; if (i + 1 < argc) str = argv[++i]; else { fprintf(stderr, "vec4ipa: -e/--layers needs a string\n"); return 1; } continue; }
        if (opt_match(argv[i], "-n", "--nearest")) { nearest_only = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec4ipa: -n/--nearest needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-r", "--reverse")) { reverse_given = 1; if (i + 1 < argc) vecstr = argv[++i]; else { fprintf(stderr, "vec4ipa: -r/--reverse needs a vector\n"); return 1; } continue; }
        if (opt_match(argv[i], "-d", "--distance")) { dist_mode = 1; if (i + 2 < argc) { seg_a = argv[++i]; seg_b = argv[++i]; } else { fprintf(stderr, "vec4ipa: -d/--distance needs two segments\n"); return 1; } continue; }
        if (opt_match(argv[i], "-A", "--align")) { align_mode = 1; if (i + 2 < argc) { seg_a = argv[++i]; seg_b = argv[++i]; } else { fprintf(stderr, "vec4ipa: -A/--align needs two IPA strings\n"); return 1; } continue; }
        if (opt_match(argv[i], "-q", "--query")) { note_ignored_inputs(argv[i], dist_mode, vecstr, json, ir, query); if (i + 1 < argc) query = argv[++i]; else { fprintf(stderr, "vec4ipa: -q/--query needs a symbol\n"); return 1; } continue; }
        int r = opt_match_val(argv[i], "-o", "--output", &val, argc, argv, &i);
        if (r == 1) { outfile = val; continue; }
        if (r == -1) { fprintf(stderr, "vec4ipa: %s needs a file\n", argv[i]); return 1; }
        r = opt_match_val(argv[i], "-x", "--ir-out", &val, argc, argv, &i);
        if (r == 1) { irbase = val; continue; }
        if (r == -1) { fprintf(stderr, "vec4ipa: %s needs a base name\n", argv[i]); return 1; }
        r = opt_match_val(argv[i], "-X", "--layers-out", &val, argc, argv, &i);
        if (r == 1) { irbase = val; continue; }
        if (r == -1) { fprintf(stderr, "vec4ipa: %s needs a base name\n", argv[i]); return 1; }
        if ((no_more_opts || argv[i][0] != '-' ||
             (argv[i][1] && (argv[i][1] == '.' ||
              (argv[i][1] >= '0' && argv[i][1] <= '9')))) &&
            !str && !vecstr) { str = argv[i]; continue; }
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
    if (align_mode && (dist_mode || vecstr || json || ir)) {
        fprintf(stderr, "vec4ipa: -A/--align conflicts with -d/--distance, -r/--reverse, -n/--nearest, -j/--json or -e/--ir\n");
        return 1;
    }
    if (outfile && redirect_output(outfile, "vec4ipa") != 0)
        return 1;

    if (align_mode) {
        if (!seg_a || !seg_b) { usage(); return 1; }
        return run_align(seg_a, seg_b, "vec4ipa");
    }

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
