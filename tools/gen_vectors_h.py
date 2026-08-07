#!/usr/bin/env python3
"""Generate vectors.h (C static table) from IPA_VECTORS.md and metric.json.

Output: a C header defining
  typedef struct { const char *ipa; double v[16]; } SegEntry;
  static const SegEntry SEG_TABLE[] = { ... };
  static const double METRIC_W[16];  and  METRIC_LAMBDA;
  static const char *AIRSTREAM_LABELS[4] / AIRSTREAM_VAL[4];
"""

import json, re, sys

SRC_MD = r"D:\2-OGP\IPA2Vector\IPA_VECTORS.md"
SRC_JSON = r"D:\2-OGP\IPA2Vector\metric.json"
SRC_NAMES = r"D:\2-OGP\IPA2Vector\src\names.tsv"
OUT_H = r"D:\2-OGP\IPA2Vector\src\vectors.h"

# airstream from section headers
AIRSTREAM = {"pulmonic", "glottalic egressive", "glottalic ingressive", "lingual"}

entries = []          # (ipa_str, [16 floats], airstream)
cur_air = "pulmonic"
for line in open(SRC_MD, encoding="utf-8"):
    t = line.strip()
    m = re.search(r"\((pulmonic|glottalic egressive|glottalic ingressive|lingual)", t)
    if t.startswith("## ") or t.startswith("### "):
        if m:
            cur_air = m.group(1)
        continue
    # `...`: `(...)` — an optional parenthesised annotation may sit
    # between the closing backtick and the colon (e.g. `/lˠ/` (dark))
    mm = re.match(r'^`/([^/`]*)/`(?: \([^)]*\))?: `\((.*)\)`$', t)
    if mm:
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
        names[parts[0]] = parts[1] if len(parts) > 2 else parts[1]

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

def fmt_vec(v):
    return "{" + ", ".join(f"{x:.4f}" for x in v) + "}"

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
lines.append("static const double METRIC_W[NDIM] = " + fmt_vec(w) + ";")
lines.append("static const double METRIC_LAMBDA = %.4f;" % lam)
lines.append("")
lines.append("static const char *DIM_NAMES[NDIM] = {")
for d in dims:
    lines.append(f'    "{d}",')
lines.append("};")
lines.append("")
lines.append("static const SegEntry SEG_TABLE[NSEG] = {")
for ipa, fvals, air in sorted(entries, key=lambda e: e[0]):
    idx = ["pulmonic", "glottalic egressive", "glottalic ingressive", "lingual"].index(air)
    lines.append(f'    {{ "{cstr(ipa)}", {fmt_vec(fvals)}, {idx} }},')
lines.append("};")
lines.append("")
lines.append("/* latin transliteration of each base segment (same order as SEG_TABLE) */")
lines.append("static const char *NAME_TABLE[NSEG] = {")
for ipa, fvals, air in sorted(entries, key=lambda e: e[0]):
    lat = names.get(ipa, "<U+XXXX>")
    lines.append(f'    "{cstr(lat)}",')
lines.append("};")
lines.append("")
lines.append("#endif /* IPA2VEC_VECTORS_H */")
lines.append("")

import os
os.makedirs(os.path.dirname(OUT_H), exist_ok=True)
with open(OUT_H, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"wrote {OUT_H}: {len(entries)} segments")
