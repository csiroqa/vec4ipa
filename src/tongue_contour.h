/* Tongue-contour geometry, ported from tools/gen_tongue_model.py.
 *
 * NOTHING HERE IS CALLED YET. This header is additive: it exists so the C
 * runtime can eventually evaluate modifier displacement on a tongue contour
 * instead of flipping signs on the old shared axes, and so the port can be
 * checked against the Python model before any call site is rewired.
 *
 * The reason this is a separate port rather than a data swap: the deployed
 * scheme carries no axis that means "how far the dorsum moved", so
 * mod_palatalised's "body += 0.24" has nothing to land on. The contour gives
 * it somewhere to land.
 *
 * roof() is a byte-for-byte transcription of gen_tongue_model.py's roof(),
 * including the clamp at both ends and the knot walk. Any divergence between
 * the two would mean the C runtime and the audit gates score different
 * geometry, which is worse than either being wrong alone -- so the parity test
 * in tools/test_tongue_contour.py checks 1001 points and must stay at zero
 * max abs difference.
 */
#include <string.h>

#ifndef IPA2VEC_TONGUE_CONTOUR_H
#define IPA2VEC_TONGUE_CONTOUR_H

/* x runs from 0 (behind the upper incisors) to 1 (pharyngeal wall);
 * y is absolute height. Copied from PALATE_KNOTS in gen_tongue_model.py --
 * the notch at x=0.62 (the velic opening) and the low point at x=0.10 (the
 * alveolar ridge) are what make the palate non-uniform, which is why the
 * anchor spacing is deliberately not equal. Do not smooth them out. */
#define TONGUE_KNOT_N 10
static const double TONGUE_KNOTS[TONGUE_KNOT_N][2] = {
    { 0.00, 0.95 }, { 0.10, 0.62 }, { 0.18, 0.85 }, { 0.32, 1.00 },
    { 0.45, 0.86 }, { 0.55, 0.60 }, { 0.62, 0.15 }, { 0.70, 0.62 },
    { 0.80, 0.78 }, { 0.90, 0.45 },
};

#define TONGUE_NPART 4
enum { TONGUE_TIP = 0, TONGUE_BLADE, TONGUE_DORSUM, TONGUE_ROOT };

typedef struct {
    double pt[TONGUE_NPART][2];   /* x, y per control point */
    double lip_open;              /* 0 closed .. 1 open */
    double lip_round;             /* -0.5 spread .. 1.0 rounded */
    /* Non-displacement state. The scalar modifiers write these rather than
     * moving the tongue, so they travel with the contour. larynx is 0 for an
     * ordinary segment, +1 for an ejective, -1 for an implosive: it says
     * whether a glottal gesture exists at all. source_tilt carries how much,
     * which is where the old scheme's split between glottal_aperture and
     * glottal_tension lands. */
    double velum;
    double lateral;
    double periodic;
    double larynx;
    double source_tilt;
    double duration;
} TongueContour;

/* Which field a scalar rule writes. Kept explicit rather than string-keyed
 * because the C side has no schema to validate a name against, and a typo in
 * a name would silently become "field not found". */
enum { SC_VELUM = 0, SC_LATERAL, SC_PERIODIC, SC_LARYNX, SC_TILT,
       SC_DURATION, SC_LIP_OPEN, SC_LIP_ROUND };

static double *sc_field (TongueContour *c, int which)
{
    switch (which) {
    case SC_VELUM:      return &c->velum;
    case SC_LATERAL:    return &c->lateral;
    case SC_PERIODIC:   return &c->periodic;
    case SC_LARYNX:     return &c->larynx;
    case SC_TILT:       return &c->source_tilt;
    case SC_DURATION:   return &c->duration;
    case SC_LIP_OPEN:   return &c->lip_open;
    default:            return &c->lip_round;
    }
}

/* Operation codes shared by the scalar and displacement rules. */
enum { OP_SET = 0, OP_ADD, OP_SUB, OP_SCALE };
#define DISP_NONE (-1)

/* One displacement rule: which part it moves, an op, and up to two operands.
 * Transcribed from DISPLACE in gen_tongue_modifiers.py. `k` is the scale
 * factor for OP_SCALE and is ignored otherwise; `z` is unused and kept only so
 * the tuple reads the same as the Python source. */
typedef struct {
    int part;        /* TONGUE_TIP..TONGUE_ROOT, or DISP_NONE */
    int lip_round;   /* 1 when this row writes lip_round instead */
    int op;
    double a, b, k;
} DispRule;

#define ALL_X_NONE 0.0

static double tongue_roof (double x)
{
    if (x <= TONGUE_KNOTS[0][0])
        return TONGUE_KNOTS[0][1];
    for (int i = 0; i + 1 < TONGUE_KNOT_N; i++) {
        double x0 = TONGUE_KNOTS[i][0], y0 = TONGUE_KNOTS[i][1];
        double x1 = TONGUE_KNOTS[i + 1][0], y1 = TONGUE_KNOTS[i + 1][1];
        if (x <= x1) {
            double t = (x - x0) / (x1 - x0);
            return y0 + t * (y1 - y0);
        }
    }
    return TONGUE_KNOTS[TONGUE_KNOT_N - 1][1];
}

/* Where the tract is most closed, and by how much.
 *
 * Lips win outright when they are shut: a bilabial closure is the tightest
 * event in the tract and it is not a tongue gesture at all. Below LIP_CLOSED
 * the tongue scan is skipped entirely rather than compared, matching
 * derived_constriction() in gen_tongue_model.py.
 *
 * out_part is written with the winning tongue part, or -1 when the lips won.
 * The caller needs to know which: an ATR modifier must move TONGUE_ROOT and
 * must NOT move the lips. */
#define TONGUE_LIP_CLOSED 0.05

static void tongue_constriction (const TongueContour *c,
        double *out_x, double *out_gap, int *out_part)
{
    int best = TONGUE_TIP;
    double bgap = tongue_roof(c->pt[0][0]) - c->pt[0][1];
    for (int i = 1; i < TONGUE_NPART; i++) {
        double g = tongue_roof(c->pt[i][0]) - c->pt[i][1];
        if (g < bgap) { bgap = g; best = i; }
    }
    /* Lips win only when the tongue is NOT already closed. The generator has
     * this guard and so must the port: overriding unconditionally would make
     * e.g. a retracted-vocalic closure report lips, which is not what the
     * Python side reports. */
    if (c->lip_open <= TONGUE_LIP_CLOSED && 0.0 < bgap) {
        *out_x = 0.0;
        *out_gap = 0.0;
        *out_part = -1;
        return;
    }
    *out_x = c->pt[best][0];
    *out_gap = bgap;
    *out_part = best;
}

/* Keep the contour physical: no part above the roof, nothing off the tract.
 * Transcribed from clamp_cfg(). x is clamped to [0.02, 0.90] and then y to
 * [0, roof(x)] -- in that order, because the roof bound depends on the clamped
 * x. Clamping y against the UNclamped x would let a point sit above the roof
 * at its new position. */
#define TONGUE_X_LO 0.02
#define TONGUE_X_HI 0.90

static void tongue_clamp (TongueContour *c)
{
    for (int p = 0; p < TONGUE_NPART; p++) {
        double x = c->pt[p][0], y = c->pt[p][1];
        if (x < TONGUE_X_LO) x = TONGUE_X_LO;
        if (x > TONGUE_X_HI) x = TONGUE_X_HI;
        if (y < 0.0) y = 0.0;
        double top = tongue_roof(x);
        if (y > top) y = top;
        c->pt[p][0] = x;
        c->pt[p][1] = y;
    }
    if (c->lip_open < 0.0) c->lip_open = 0.0;
    if (c->lip_open > 1.0) c->lip_open = 1.0;
    if (c->lip_round < -0.5) c->lip_round = -0.5;
    if (c->lip_round > 1.0) c->lip_round = 1.0;
}

/* Apply one displacement rule in place. `all_x` shifts every control point's
 * x uniformly, which is what "advanced" and "retracted" mean: a whole-tongue
 * translation, not a movement of any one part. */
static void tongue_displace (TongueContour *c, const DispRule *rules,
        int nrule, double all_x)
{
    if (all_x != ALL_X_NONE)
        for (int p = 0; p < TONGUE_NPART; p++)
            c->pt[p][0] += all_x;
    for (int r = 0; r < nrule; r++) {
        const DispRule *d = &rules[r];
        if (d->lip_round) {
            c->lip_round += d->a;
            continue;
        }
        if (d->part < 0) continue;
        double x = c->pt[d->part][0], y = c->pt[d->part][1];
        switch (d->op) {
        case OP_SET:   x = d->a; y = (d->b < 0.0) ? y : d->b; break;
        case OP_SCALE: x = d->a + (x - d->a) * d->k; break;
        default:       x += d->a; y += d->b; break;
        }
        c->pt[d->part][0] = x;
        c->pt[d->part][1] = y;
    }
}

/* Apply one scalar rule in place. */
static void tongue_scalar (TongueContour *c, const int *field,
        const int *op, const double *val, int n)
{
    for (int i = 0; i < n; i++) {
        double *p = sc_field(c, field[i]);
        if (op[i] == OP_SET) *p = val[i];
        else if (op[i] == OP_ADD) *p += val[i];
        else *p -= val[i];
    }
}

/* --- the 27 rules -------------------------------------------------------
 * Transcribed one-for-one from DISPLACE and SCALAR in
 * gen_tongue_modifiers.py. tools/test_tongue_contour.py replays all of them
 * against the Python definitions over every segment, so a transcription slip
 * shows up as a parity failure rather than as a plausible-looking vector.
 *
 * b = -1.0 on an OP_SET row is the "keep y" sentinel: the Python tuples write
 * None there, meaning the rule names a position in x and says nothing about
 * height. All real y values are >= 0 after clamping, so the sentinel cannot
 * collide with data. */

#define MOD_PALATALIZED 0
#define MOD_VELARIZED   1
#define MOD_LABIALIZED  2
#define MOD_PHARYNGEAL  3
#define MOD_ATR         4
#define MOD_RTR         5
#define MOD_ADVANCED    6
#define MOD_RETRACTED   7
#define MOD_DENTAL      8
#define MOD_LAMINAL     9
#define MOD_APICAL      10
#define MOD_CENTRALIZED 11
#define MOD_MIDCENT     12
#define MOD_NDISPLACE   13

/* { part, lip_round, op, a, b, k } */
static const DispRule DISP_RULES[MOD_NDISPLACE][3] = {
    /* palatalized */ {{TONGUE_BLADE,0,OP_ADD, 0.08, 0.35, 0},
                       {TONGUE_DORSUM,0,OP_ADD,-0.05, 0.05, 0},{-1,0,0,0,0,0}},
    /* velarized   */ {{TONGUE_DORSUM,0,OP_ADD,-0.18, 0.05, 0},
                       {TONGUE_ROOT,  0,OP_ADD, 0.02, 0.08, 0},{-1,0,0,0,0,0}},
    /* labialized  */ {{TONGUE_DORSUM,0,OP_ADD,-0.10, 0.08, 0},
                       {TONGUE_TIP,   0,OP_ADD,-0.02, 0.05, 0},
                       {DISP_NONE,1,OP_ADD, 0.30, 0.00, 0}},
    /* pharyngeal  */ {{TONGUE_ROOT,  0,OP_ADD, 0.14, 0.30, 0},
                       {TONGUE_DORSUM,0,OP_ADD, 0.00,-0.08, 0},{-1,0,0,0,0,0}},
    /* atr         */ {{TONGUE_ROOT,  0,OP_ADD,-0.10,-0.08, 0},{-1,0,0,0,0,0},{-1,0,0,0,0,0}},
    /* rtr         */ {{TONGUE_ROOT,  0,OP_ADD, 0.10, 0.08, 0},{-1,0,0,0,0,0},{-1,0,0,0,0,0}},
    /* advanced    */ {{-1,0,0,0,0,0},{-1,0,0,0,0,0},{-1,0,0,0,0,0}},
    /* retracted   */ {{-1,0,0,0,0,0},{-1,0,0,0,0,0},{-1,0,0,0,0,0}},
    /* dental      */ {{TONGUE_BLADE,0,OP_SET, 0.10,-1.0, 0},
                       {TONGUE_TIP,   0,OP_SET, 0.10,-1.0, 0},{-1,0,0,0,0,0}},
    /* laminal     */ {{TONGUE_BLADE,0,OP_SET, 0.20,-1.0, 0},
                       {TONGUE_TIP,   0,OP_SET, 0.16,-1.0, 0},{-1,0,0,0,0,0}},
    /* apical      */ {{TONGUE_TIP,   0,OP_SET, 0.24,-1.0, 0},
                       {TONGUE_BLADE,0,OP_SET, 0.22,-1.0, 0},{-1,0,0,0,0,0}},
    /* centralized */ {{TONGUE_DORSUM,0,OP_SCALE,0.33,0.0, 0.5},{-1,0,0,0,0,0},{-1,0,0,0,0,0}},
    /* midcent     */ {{TONGUE_TIP,   0,OP_SET, 0.16,-1.0, 0},{-1,0,0,0,0,0},{-1,0,0,0,0,0}},
};

/* How many rules each displacement actually uses, so the unused slots do not
 * get applied as zeroes. */
static const int DISP_NRULE[MOD_NDISPLACE] = {
    2, 2, 3, 2, 1, 1, 0, 0, 2, 2, 2, 1, 1,
};

/* Uniform whole-tongue x shift, or ALL_X_NONE. advanced is -0.06 and
 * retracted is +0.06 in the Python table. */
static const double DISP_ALL_X[MOD_NDISPLACE] = {
    ALL_X_NONE, ALL_X_NONE, ALL_X_NONE, ALL_X_NONE,
    ALL_X_NONE, ALL_X_NONE, -0.06, +0.06,
    ALL_X_NONE, ALL_X_NONE, ALL_X_NONE, ALL_X_NONE, ALL_X_NONE,
};

#define MOD_NSCALAR 13
enum { S_NASAL = 0, S_NASAL_REL, S_LAT_RELEASE, S_NASAL_CLICK, S_RAISED,
       S_LOWERED, S_RND_MORE, S_RND_LESS, S_LONG, S_HALF, S_EXTRA_SHORT,
       S_SYLLABIC, S_UNREL };

/* Up to three fields per scalar rule; nasal_click is the only one that writes
 * three. Single-field rules repeat their own field in the spare slots and
 * SC_N says how many are real, so the repeat is never applied. */
static const int   SC_FIELD[MOD_NSCALAR][3] = {
    {SC_VELUM,     SC_VELUM,     SC_VELUM    },   /* nasal        */
    {SC_VELUM,     SC_DURATION,  SC_VELUM    },   /* nasal_rel    */
    {SC_LATERAL,   SC_DURATION,  SC_LATERAL  },   /* lat_release  */
    {SC_VELUM,     SC_PERIODIC,  SC_DURATION },   /* nasal_click  */
    {SC_LIP_OPEN,  SC_LIP_OPEN,  SC_LIP_OPEN },   /* raised       */
    {SC_LIP_OPEN,  SC_LIP_OPEN,  SC_LIP_OPEN },   /* lowered      */
    {SC_LIP_ROUND, SC_LIP_ROUND, SC_LIP_ROUND },   /* rnd_more     */
    {SC_LIP_ROUND, SC_LIP_ROUND, SC_LIP_ROUND },   /* rnd_less     */
    {SC_DURATION,  SC_DURATION,  SC_DURATION },   /* long         */
    {SC_DURATION,  SC_DURATION,  SC_DURATION },   /* half         */
    {SC_DURATION,  SC_DURATION,  SC_DURATION },   /* extra_short  */
    {SC_DURATION,  SC_DURATION,  SC_DURATION },   /* syllabic     */
    {SC_DURATION,  SC_DURATION,  SC_DURATION },   /* unrel        */
};
static const int   SC_OP[MOD_NSCALAR][3] = {
    {OP_SET, OP_SET, OP_SET},        {OP_SET, OP_ADD, OP_SET},
    {OP_SET, OP_ADD, OP_SET},        {OP_SET, OP_SET, OP_SET},
    {OP_SUB, OP_SUB, OP_SUB},        {OP_ADD, OP_ADD, OP_ADD},
    {OP_ADD, OP_ADD, OP_ADD},        {OP_SUB, OP_SUB, OP_SUB},
    {OP_SET, OP_SET, OP_SET},        {OP_SET, OP_SET, OP_SET},
    {OP_SET, OP_SET, OP_SET},        {OP_ADD, OP_ADD, OP_ADD},
    {OP_SET, OP_SET, OP_SET},
};
static const double SC_VAL[MOD_NSCALAR][3] = {
    {0.6,0.0,0.0}, {0.8,0.3,0.0}, {1.0,0.3,0.0}, {1.0,1.0,1.0},
    {0.10,0.0,0.0},{0.10,0.0,0.0},{0.25,0.0,0.0},{0.25,0.0,0.0},
    {2.0,0.0,0.0}, {1.5,0.0,0.0}, {0.5,0.0,0.0}, {0.5,0.0,0.0},
    {0.1,0.0,0.0},
};
static const int SC_N[MOD_NSCALAR] = { 1, 2, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1 };

static const char *DISP_NAME[MOD_NDISPLACE] = {
    "palatalized", "velarized", "labialized", "pharyngeal", "atr", "rtr",
    "advanced", "retracted", "dental", "laminal", "apical", "centralized",
    "midcent",
};
static const char *SCALAR_NAME[MOD_NSCALAR] = {
    "nasal", "nasal_rel", "lat_release", "nasal_click", "raised", "lowered",
    "rnd_more", "rnd_less", "long", "half", "extra_short", "syllabic",
    "unrel",
};

/* Apply a modifier by name, matching apply_mod() in gen_tongue_modifiers.py:
 * scalars return early without touching the tongue, displacements clamp
 * afterwards. Returns 0 if the name is not a modifier -- callers must handle
 * that rather than assume success, since an unknown diacritic silently doing
 * nothing is how the old scheme's sign flips went unnoticed. */
static int tongue_apply_mod (TongueContour *c, const char *name)
{
    for (int i = 0; i < MOD_NSCALAR; i++) {
        if (strcmp(name, SCALAR_NAME[i]) != 0) continue;
        tongue_scalar(c, SC_FIELD[i], SC_OP[i], SC_VAL[i], SC_N[i]);
        tongue_clamp(c);
        return 1;
    }
    for (int i = 0; i < MOD_NDISPLACE; i++) {
        if (strcmp(name, DISP_NAME[i]) != 0) continue;
        tongue_displace(c, DISP_RULES[i], DISP_NRULE[i], DISP_ALL_X[i]);
        tongue_clamp(c);
        return 1;
    }
    return 0;
}



#endif /* IPA2VEC_TONGUE_CONTOUR_H */
