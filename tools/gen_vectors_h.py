#!/usr/bin/env python3
"""Generate vectors.h (C static table) from IPA_VECTORS.md + metric.json.

Output: a C header defining
  typedef struct { const char *ipa; double v[16]; } SegEntry;
  static const SegEntry SEG_TABLE[] = { ... };
  static const double METRIC_W[16];  and  METRIC_LAMBDA;
  static const char *AIRSTREAM_LABELS[5];

With --scheme FILE, the table is generated from a custom scheme file
(ndim/dim/weight/lambda/seg lines, tools/data/spec_next.scheme format)
instead of IPA_VECTORS.md + metric.json.  This is how a custom dimension
scheme AND its ipa->vec table are imported into the C binaries.

Usage:
  python tools/gen_vectors_h.py            # v8 (default)
  python tools/gen_vectors_h.py --scheme tools/data/spec_next.scheme
"""

import json, os, re, sys
from pathlib import Path

from _common import MD_LINE_RE, fmt_vec_c

ROOT = Path(__file__).resolve().parents[1]
SRC_MD = ROOT / "IPA_VECTORS.md"
SRC_JSON = ROOT / "metric.json"
SRC_NAMES = ROOT / "src" / "names.tsv"
OUT_H = ROOT / "src" / "vectors.h"

AIRSTREAM_INDEX = {"pulmonic": 0, "glottalic egressive": 1,
                   "glottalic ingressive": 2, "lingual": 3,
                   "pulmonic2": 0, "glottalic-egressive": 1,
                   "glottalic-ingressive": 2}

def load_scheme(path):
    """Parse a custom scheme file -> (ndim, dims, weights, lambda, entries)."""
    ndim = None
    dims = []
    weights = None
    lam = None
    entries = []   # (ipa, [ndim floats], airstream_idx)
    for ln in open(path, encoding="utf-8"):
        t = ln.strip()
        if not t or t.startswith("#"):
            continue
        parts = t.split()
        if parts[0] == "ndim":
            ndim = int(parts[1])
        elif parts[0] == "dim":
            dims.append(parts[1])
        elif parts[0] == "weight":
            weights = [float(x) for x in parts[1:]]
        elif parts[0] == "lambda":
            lam = float(parts[1])
        elif parts[0] == "seg":
            ipa = parts[1]
            vals = [float(x) for x in parts[2:2 + ndim]]
            air = parts[2 + ndim] if len(parts) > 2 + ndim else "pulmonic"
            idx = AIRSTREAM_INDEX.get(air)
            if idx is None:
                print(f"WARN {ipa}: unknown airstream {air!r}", file=sys.stderr)
                idx = 0
            entries.append((ipa, vals, idx))
    if ndim is None or weights is None:
        sys.exit("gen_vectors_h: bad scheme file (need ndim + weight)")
    return ndim, dims, weights, lam, entries

def main():
    global entries, dims, w, lam, names
    scheme_path = None
    if "--scheme" in sys.argv:
        i = sys.argv.index("--scheme")
        scheme_path = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if not scheme_path:
            sys.exit("gen_vectors_h: --scheme needs a file")
    if scheme_path:
        ndim, dims, w, lam, entries = load_scheme(scheme_path)
    else:
        parse_md()
        metric = json.load(open(SRC_JSON, encoding="utf-8"))
        w = metric["weights"]
        lam = metric["lambda"]
        dims = metric["dimensions"]
    load_names()
    emit(ndim if scheme_path else 16)


def parse_md():
    global entries
    entries = []
    cur_air = "pulmonic"
    unset_sec = None
    for line in open(SRC_MD, encoding="utf-8"):
        t = line.strip()
        m = re.search(r"\((pulmonic|glottalic egressive|glottalic ingressive|lingual)", t)
        if t.startswith("## ") or t.startswith("### "):
            if m:
                cur_air = m.group(1)
                unset_sec = None
            elif t.startswith("## ") and unset_sec is None:
                unset_sec = t[:60]
            continue
        mm = MD_LINE_RE.match(t)
        if mm:
            if unset_sec is not None:
                print(f"WARN: no airstream in section header {unset_sec!r}, "
                      f"keeping {cur_air!r}", file=sys.stderr)
                unset_sec = None
            ipa = mm.group(1).strip()
            vals = [x.strip() for x in mm.group(2).split(",")]
            if len(vals) != 16:
                print(f"WARN skip {ipa}: {len(vals)} values", file=sys.stderr)
                continue
            try:
                fvals = [float(x) for x in vals]
            except ValueError:
                print(f"WARN skip {ipa}: bad number", file=sys.stderr)
                continue
            entries.append((ipa, fvals, cur_air))


def load_names():
    global names
    names = {}
    for ln in open(SRC_NAMES, encoding="utf-8"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split("\t")
        if len(parts) >= 2:
            names[parts[0]] = parts[1]

# escape for C string (UTF-8 bytes preserved; only quote/backslash escaped)

def cstr(s: str) -> str:
    out = []
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        else:
            out.append(ch)
    return ''.join(out)


def emit(ndim):
    lines = []
    lines.append("/* Auto-generated from IPA_VECTORS.md + metric.json — do not edit. */")
    lines.append("#ifndef IPA2VEC_VECTORS_H")
    lines.append("#define IPA2VEC_VECTORS_H")
    lines.append("")
    lines.append("#define NDIM %d" % ndim)
    lines.append("#define MAXDIM 32")
    lines.append("#define NSEG %d" % len(entries))
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    const char *ipa;      /* UTF-8 IPA spelling (base segment, no diacritics) */")
    lines.append("    double v[MAXDIM];     /* articulatory vector (NDIM active) */")
    lines.append("    int   airstream;      /* index into AIRSTREAM_LABELS */")
    lines.append("} SegEntry;")
    lines.append("")
    lines.append("static const char *AIRSTREAM_LABELS[5] = {")
    lines.append('    "pulmonic", "glottalic egressive", "glottalic ingressive", "lingual", "percussive"')
    lines.append("};")
    lines.append("")
    lines.append("static const double METRIC_W[NDIM] = " + fmt_vec_c(w) + ";")
    lines.append("static const double METRIC_LAMBDA = %.4f;" % lam)
    lines.append("")
    lines.append("static const char *DIM_NAMES[NDIM] = {")
    for d in dims:
        lines.append(f'    "{d}",')
    lines.append("};")
    lines.append("")
    lines.append("static const SegEntry SEG_TABLE[NSEG] = {")
    sorted_entries = sorted(entries, key=lambda e: e[0])
    for ipa, fvals, air in sorted_entries:
        idx = AIRSTREAM_INDEX.get(air)
        if idx is None:
            print(f"WARN {ipa}: unknown airstream {air!r}, defaulting to pulmonic",
                  file=sys.stderr)
            idx = 0
        lines.append(f'    {{ "{cstr(ipa)}", {fmt_vec_c(fvals)}, {idx} }},')
    lines.append("};")
    lines.append("")
    lines.append("/* latin transliteration of each base segment (same order as SEG_TABLE) */")
    lines.append("static const char *NAME_TABLE[NSEG] = {")
    for ipa, fvals, air in sorted_entries:
        lat = names.get(ipa)
        if lat is None:
            print(f"WARN {ipa}: no latin name in names.tsv", file=sys.stderr)
            lat = "<U+XXXX>"
        lines.append(f'    "{cstr(lat)}",')
    lines.append("};")
    lines.append("")
    lines.append("#endif /* IPA2VEC_VECTORS_H */")
    lines.append("")
    os.makedirs(OUT_H.parent, exist_ok=True)
    with open(OUT_H, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {OUT_H}: {len(entries)} segments")


if __name__ == "__main__":
    main()
