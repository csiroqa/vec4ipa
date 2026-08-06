# Metric Specification

Machine‑readable weights and metric live in **`metric.json`**; this document explains the derivation, the schema, and how to learn/tune the metric.

## 1. Distance

For two 15‑dimensional vectors **x**, **y**:

$$
D(x, y) = \sqrt{(x-y)^\top M\,(x-y)} \;+\; \lambda \cdot [\text{airstream}(x) \neq \text{airstream}(y)]
$$

- Default: $M = \mathrm{diag}(w)$ with the weights below.
- Learnable: $M = L^\top L$ (positive semi‑definite); train with LMNN, NCA, or triplet loss on perceptual confusion / phonological alternation data (cf. Lakretz et al. 2018).
- Airstream labels: `pulmonic`, `glottalic egressive`, `glottalic ingressive`, `lingual`. The penalty is applied only when the labels differ.

## 2. Default Weights: Derived from Perceptual Data (Miller & Nicely 1955)

Miller & Nicely (1955) measured how robustly each phonetic feature survives masking noise, by testing discrimination of 16 English consonants (CV syllables) at SNRs from −18 to +12 dB. Qualitative threshold data (their Figs. 1–2):

| Feature group | SNR below which discrimination collapses | Empirical anchor |
| ------------- | ----------------------------------------- | ---------------- |
| voicing       | ≈ −12 dB (still discriminable at −12 dB)  | robust |
| nasality      | ≈ −12 dB (same curve as voicing)          | robust |
| affrication (manner) | ≈ 0 dB                             | intermediate |
| duration      | ≈ 0 dB (affrication and duration share a single function) | intermediate |
| place         | < +6 dB is hard to distinguish            | fragile (≈18 dB worse than voicing/nasality) |

**Derivation formula** (place as reference, doubling of weight per 6 dB of threshold advantage):

$$
w_i = 2^{(t_{\text{place}} - t_i)/6}, \qquad t_{\text{place}} = +6\ \text{dB}
$$

This yields three tiers: **8.0** (voicing/nasality), **2.0** (manner/duration), **1.0** (place).

Mapping onto the 15 dimensions:

> **Placement note — `tt_height`:** `tt_height` is in the *place* tier (1.0), not the manner tier, because the tip‑closure contrast it codes is a place contrast: Phatak & Allen (2007) and Miller & Nicely (1955) show /pa,ta/ is the *hardest* stop‑place pair (81% correct at 10 dB SNR vs ≥92% for all other CV pairs), so tip‑activation must not be priced higher than body position. Manner contrasts (e.g., /t/ vs /s/) are already carried by `duration`, `jet_focus` and `effective_oral_area`; `tt_height` contributes only ~5% of that distance.

| Dimension | Feature (MN55) | Weight | Tier |
| --------- | -------------- | ------ | ---- |
| `voiced`      | voicing | 8.0 | laryngeal |
| `cg`          | voicing (glottal constriction) | 8.0 | laryngeal |
| `sg`          | voicing (glottal spread) | 8.0 | laryngeal |
| `laryngeal_tension` | voicing (laryngeal) | 8.0 | laryngeal |
| `vel_open`    | nasality | 8.0 | laryngeal/nasal |
| `effective_oral_area` | affrication (manner) | 2.0 | manner |
| `lateral_ratio` | manner | 2.0 | manner |
| `duration`    | duration | 2.0 | manner |
| `jet_focus`   | duration/frication | 2.0 | manner |
| `lips_closed` | place | 1.0 | place |
| `lips_rounded` | place | 1.0 | place |
| `tt_pos`      | place | 1.0 | place |
| `tt_height`   | place | 1.0 | place |
| `tb_pos`      | place | 1.0 | place |
| `tongue_root` | place (ATR; not covered by MN55 — provisional) | 1.0 | place |

## 3. Airstream Penalty λ

Default **λ = 4.0**. Rationale: cross‑airstream confusions are essentially absent perceptually (an ejective is never heard as a pulmonic stop under any tested condition), so the penalty should be of the same order as the largest within‑category laryngeal difference (e.g., /p/ vs /pʼ/ differs by cg 0→1 and tns 0→0.6: √(1²·8 + 0.6²·8) ≈ 3.3). λ = 4.0 therefore dominates typical within‑category distances while remaining comparable in scale. **Provisional**: to be calibrated when cross‑airstream confusion data become available; treat as an order‑of‑magnitude default.

## 4. Caveats and Tuning

1. **Scope**: MN55 covers 16 English consonants — no vowels, no non‑pulmonics. Vowel‑relevant weights (`tongue_root`, `tb_pos` backness) and `tt_height` are assigned by analogy (manner/place tiers) and are provisional.
2. **Replication**: Lovitt & Allen (2006) repeated MN55 and found voicing *less* robust and place *more* robust than the original. Hence the weights are **initialisation**, not gospel: prefer learning M on task‑specific data when available.
3. **Calibration targets**: (a) fit M to large confusion matrices (e.g., Miller & Nicely 1955; Phatak & Allen 2007; language‑specific CM studies) via metric learning; (b) validate against production‑error data and lexical neighborhood measures.
4. **Per‑language adaptation**: for a target language, restrict the inventory and re‑learn the diagonal; the full matrix M captures correlated cues (e.g., place × rounding for /ʃ/).

## 5. metric.json Schema

```json
{
  "version": 2,
  "dimensions": [ "<name>", ... 15 entries in vector order ],
  "weights":    [ 1.0, ... 15 entries, diagonal of default M ],
  "metric":     null,            // full 15×15 M (row-major); null = diag(weights)
  "lambda":     4.0,             // airstream penalty
  "airstream":  [ "pulmonic", "glottalic egressive", "glottalic ingressive", "lingual" ]
}
```

- `weights` order matches the vector tuple order in README §5 / IPA_VECTORS.md.
- Setting `metric` to a full matrix overrides `weights`.
- When learning: store the learned $L$ (or $M$) back into `metric`; keep `weights` as the documented initialisation.

## 6. References

- Miller, G. A. & Nicely, P. E. (1955). An analysis of perceptual confusions among some English consonants. *JASA* 27:338–352.
- Lovitt, A. & Allen, J. B. (2006). 50 years late: Repeating Miller–Nicely 1955. *INTERSPEECH* 2006:2154–2157.
- Phatak, S. A. & Allen, J. B. (2007). Consonant and vowel confusions in speech‑weighted noise. *JASA* 121:2312–2326.
- Lakretz, Y., Chechik, G., Rubin, S. & Tishby, N. (2018). Interpreting a deep learning model for speech recognition: A perceptual learning perspective. *Interspeech* 2018.
- Weinberger, K. Q. & Saul, L. K. (2009). Distance metric learning for large margin nearest neighbor classification. *JMLR* 10:207–244.
- Goldberger, J., Roweis, S., Hinton, G. & Salakhutdinov, R. (2005). Neighbourhood components analysis. *NIPS* 17.
