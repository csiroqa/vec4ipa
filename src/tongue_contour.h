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
} TongueContour;

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

#endif /* IPA2VEC_TONGUE_CONTOUR_H */
