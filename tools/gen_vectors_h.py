#!/usr/bin/env python3
"""Generate vectors.h (C static table) from IPA_VECTORS.md and metric.json.

Output: a C header defining
  typedef struct { const char *ipa; double v[16]; } SegEntry;
  static const SegEntry SEG_TABLE[] = { ... };
  static const double METRIC_W[16];  and  METRIC_LAMBDA;
  static const char *AIRSTREAM_LABELS[5];
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
                   "glottalic ingressive": 2, "lingual": 3}

entries = []          # (ipa_str, [16 floats], airstream)
cur_air = "pulmonic"
unset_sec = None      # a `## ` header with no airstream: warn only if it holds entries
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
    # `...`: `(...)` — an optional parenthesised annotation may sit
    # between the closing backtick and the colon (e.g. `/lˠ/` (dark))
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

metric = json.load(open(SRC_JSON, encoding="utf-8"))
w = metric["weights"]
lam = metric["lambda"]
dims = metric["dimensions"]

# latin transliteration table: ipa -> (latin, comment)
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

lines = []
lines.append("/* Auto-generated from IPA_VECTORS.md + metric.json — do not edit. */")
lines.append("#ifndef IPA2VEC_VECTORS_H")
lines.append("#define IPA2VEC_VECTORS_H")
lines.append("")
lines.append("#define NDIM 16")
lines.append("#define NSEG %d" % len(entries))
lines.append("")
lines.append("typedef struct {")
lines.append("    const char *ipa;      /* UTF-8 IPA spelling (base segment, no diacritics) */")
lines.append("    double v[NDIM];       /* articulatory vector */")
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
