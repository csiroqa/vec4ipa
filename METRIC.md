# Metric Specification

Machine‑readable weights and metric live in **`metric.json`**; this document explains the derivation, the schema, and how to learn/tune the metric.

> **v9 (published = fitted):** `metric.json` was re-written from the current
> fit (`fit_metric.py --write`), updating the published weights to the fitted
> values (aggregation fix by name lookup, vowel-consonant anchors, nasalised
> `vel_open` 0.6 all included). LOCO held-out NLL: fitted = published
> **22,355** (vs v8 22,316; MN55 tiers 28,190). λ unchanged at 5.5.

> **v8 (aggregation-fix correction):** the post-processing rescale that equalises the stop voicing and place distances compared the **wrong rows** — `CONS_ORDER` assumed the confusion-matrix rows were ordered `[p, t, b, g, v, ð, z, ʒ]`, but `phatak08_cm.json` is ordered `[p, t, k, f, θ, s, ʃ, b, d, g, v, ð, z, ʒ, m, n]`, so the rescale equalised **d(p–k) = d(p–t)** instead of d(p–b) = d(p–t), and the published triplet (voiced 0.477, cg 7.538, sg 4.188) still priced stop voicing (p–b = 1.204) *below* stop place (p–t = 1.508) — exactly the anomaly the fix was meant to remove. `fit_metric.py` now looks rows up by name, the triplet is rescaled by s² = 1.758 (voiced 0.426→**0.749**, cg 6.730→**11.833**, sg 3.739→**6.575**), and **p–b = p–t = 1.508** (aggregation fix verified in `tools/test_metric_space.py`-style checks). Cost: LOCO +1.5% (fitted **22,316** vs published v7 21,992; MN55 tiers 28,190). λ raised 5.0→**5.5** so it again exceeds the largest within-airstream distance (now 5.156, /ʍ/–/ʔ/, up from 4.717 in v6/v7 — the heavier cg weight stretched glottal-constriction pairs).

> **v7 (nasalised-value fix):** nasalised vowels were encoded at `vel_open` 0.8 — only 0.2 below full nasals — so nasalised high/back vowels anchored to nasal consonants (ɯ̃ → /ŋ/). The nasalised-vowel anchor is now **0.6** (clearly weaker than 1.0; SPEC §2/§10, `mod_nasal`), and the extIPA velopharyngeal fricative ʩ moved from a half-nasal 0.5 to full-nasal 1.0 (friction at the port requires full nasal airflow; 0.5 made it the accidental nearest neighbour of every nasalised voiceless fricative). LOCO held-out NLL: **fitted 21,992 < v6 21,954-vs… (≈ +0.2%) < MN55 tiers 28,190**. All 36 vowel-like bases × {̃, ː, ̃ː} now anchor to vowels (regression-tested in `tools/test_metric_space.py`).

## 1. Distance

For two 16‑dimensional vectors **x**, **y**:

$$
D(x, y) = \sqrt{(x-y)^\top M\,(x-y)} \;+\; \lambda \cdot [\text{airstream}(x) \neq \text{airstream}(y)]
$$

- Default: $M = \mathrm{diag}(w)$ with the weights below.
- Learnable: $M = L^\top L$ (positive semi‑definite); train with LMNN, NCA, or triplet loss on perceptual confusion / phonological alternation data (cf. Lakretz et al. 2018).
- Airstream labels: `pulmonic`, `glottalic egressive`, `glottalic ingressive`, `lingual`. The penalty is applied only when the labels differ.

## 2. Default Weights: Fitted to Perceptual Confusion Data (Phatak et al. 2008)

**Origin (Miller & Nicely 1955, qualitative tiers).** MN55 measured how robustly each phonetic feature survives masking noise, testing 16 English consonants (CV syllables) at SNRs from −18 to +12 dB. Their qualitative thresholds (Figs. 1–2) define three tiers:

| Feature group | SNR below which discrimination collapses | Tier weight |
| ------------- | ----------------------------------------- | ----------- |
| voicing       | ≈ −12 dB (still discriminable at −12 dB)  | 8.0 |
| nasality      | ≈ −12 dB (same curve as voicing)          | 8.0 |
| affrication (manner) / duration | ≈ 0 dB                            | 2.0 |
| place         | < +6 dB is hard to distinguish            | 1.0 |

via $w_i = 2^{(t_{\text{place}} - t_i)/6}$ with $t_{\text{place}} = +6\ \text{dB}$.

**Revision: weights fitted to Phatak et al. (2008) confusion matrices.** Lovitt & Allen (2006) replicated MN55 and found voicing *less* robust and place *more* robust than the original. Phatak, Lovitt & Allen (2008, JASA 124:1743–1752) provide complete digitized confusion matrices for the same 16 consonants (p t k f θ s ʃ b d g v ð z c m n) at 8 SNRs (+12 to −18 dB). We fitted $P(j|i) = \mathrm{softmax}_j(-a_c \cdot d_{ij})$ (Shepard kernel, per-condition $a_c$) to the 4 mid-SNR matrices (12, 6, 0, −6 dB; "other" response column excluded), L-BFGS-B with $\ell_2$ regularization toward 1.0, leaving-one-condition-out cross-validation:

- Fitted weights beat the original 8/2/1 tiers at **every** held-out SNR (total held-out NLL 23,240 vs 29,553; per-SNR 2,192/3,712/6,382/10,953 vs 3,716/5,636/8,097/12,104). Symmetric and asymmetric variants of the data agree on the fitted values. The conclusion is robust to the identifiability treatment: re-fitting with L²‑normalised weights (absorbing the global scale into the per‑condition $a_c$) reproduces the same LOCO ranking (23,446 vs 29,553). The published weights (with the aggregation fix of §2) score 23,435 held-out — within 1% of the raw optimum.
- **Identifiability caveat**: the model has one free global scale (w → c·w, a → a/√c leaves all distances unchanged), so only the *relative* weight pattern is identified, not the absolute values. The absolute scale printed here is the log‑space‑regularised solution (toward the 8/2/1 initialisation); the reported ratios (e.g. lips_rounded ≈ 6× tongue_tip_pos, voiced ≈ 1/6 × tongue_tip_pos) are stable across initialisations and regularisation schemes.
- The fit collapses the MN55 voicing tier: voicing confusions in Phatak 08 are massive and asymmetric (e.g., θ→ð 22%), so `voiced` and its glottal proxies are fitted low (≈ 0.36–0.89 raw) instead of 8.0. The `voiced`/`constricted_glottis`/`spread_glottis` triplet is perfectly collinear within the 16-consonant set, so only their combined voicing distance is identifiable.
- **Aggregation fix**: the raw pooled fit made the stop voicing distance (p vs b = 0.72) *smaller* than the stop place distance (p vs t = 0.87) — contradicting the data, where stop voicing confusions are tiny (p→b 2% at 0 dB) and stop place confusions are large (p→t 9%). The raw voicing weight is dragged down by fricatives (θ→ð 22%), whose voicing cues genuinely are weaker. Because `voiced`/`constricted_glottis`/`spread_glottis` are perfectly collinear in the 16-consonant set, their *relative* values are unidentifiable and only the combined voicing distance matters — so the triplet is rescaled (s² = 1.758 in v8) so that the voicing distance equals the place distance (**p–b = p–t = 1.508**). Cost: +1.5% LOCO held-out NLL (v8 22,316 vs v7 21,992). This keeps the order voicing ≥ place for stops, matching both MN55 and the 0 dB confusion data, while fricative voicing (f–v ≈ 1.30) still prices the genuinely weaker fricative voicing cue realistically. *(v4–v7 shipped a defective implementation of this fix: the row lookup assumed `[p, t, b, …]` data ordering while the matrix is ordered `[p, t, k, f, …]`, so the rescale actually equalised d(p–k) with d(p–t) and the published triplet still priced stop voicing below stop place — corrected in v8, see the version note.)*
- `lips_rounded` fitted at ≈ 21 (only /ʃ/ differs on it within the 16 consonants); capped at 8.0 to avoid overfitting noise (costs only 0.3% NLL).
- `tongue_root`, `lateral_ratio`, `laryngeal_tension` carry no signal in this 16-consonant set (constant 0.0) and were kept at their MN55-tier values (1.0 / 2.0 / 8.0); `duration` is well identified (8 distinct values across the set) and was fitted (1.405).

Final fitted weights (dimension order as in `metric.json`, v8 — the v7 weights are shown for reference):

| Dimension | Feature (MN55) | Weight (v8) | v7 | Fit basis |
| --------- | -------------- | ----------- | --- | --------- |
| `lips_closed`      | place (labial closure) | 1.397 | 1.397 | fitted (f/v/p̪/ɱ/ⱱ are 1.0) |
| `lips_rounded`     | place (rounding) | 8.0 (capped; raw ≈ 34) | 8.0 | fitted, capped |
| `tongue_tip_pos`           | place (tip position) | 1.069 | 1.069 | fitted |
| `tongue_tip_height`        | place (tip closure) | 1.559 | 1.559 | fitted |
| `tongue_body_pos`           | place (body position) | 2.533 | 2.533 | fitted |
| `tongue_root`      | place (ATR; not in MN55/Phatak sets) | 1.0 | 1.0 | tier default (pinned) |
| `vel_open`         | nasality | 3.442 | 3.442 | fitted |
| `lateral_ratio`    | manner (laterality) | 2.0 | 2.0 | tier default (pinned) |
| `voiced`           | voicing | 0.749 | 0.477 | fitted, then rescaled (aggregation fix, v8 correction) |
| `constricted_glottis`               | voicing (glottal constriction) | 11.833 | 7.537 | fitted, then rescaled (collinear with `voiced`/`spread_glottis`) |
| `spread_glottis`               | voicing (glottal spread) | 6.575 | 4.188 | fitted, then rescaled (collinear with `voiced`/`constricted_glottis`) |
| `laryngeal_tension`| voicing (laryngeal) | 8.0 | 8.0 | tier default (pinned) |
| `duration`         | duration | 2.671 | 2.671 | fitted |
| `jet_focus`        | frication | 2.531 | 2.531 | fitted |
| `effective_oral_area` | affrication (manner) / vowel height | 4.421 | 4.421 | fitted + vowel-consonant anchors |
| `airflow_direction` | airstream direction | 4.0 | 4.0 | qualitative (pinned) |

> **Placement note — `tongue_tip_height`:** `tongue_tip_height` stays in the *place* tier: the tip‑closure contrast it codes is a place contrast. Phatak & Allen (2007) and MN55 show /pa,ta/ is the *hardest* stop‑place pair (81% correct at 10 dB SNR vs ≥92% for all other CV pairs), so tip‑activation must not be priced higher than body position. Manner contrasts (e.g., /t/ vs /s/) are carried by `duration`, `jet_focus`, `effective_oral_area`.

> **Why voicing lost its 8.0:** the fitted voicing weight reflects the 2008 replication, where fricative voicing confusions are large and asymmetric (θ→ð, f→b). The classic MN55 voicing-is-robust result holds only in the 1955 analog experiment. Caveat: a symmetric Shepard model cannot capture asymmetric confusions, so the voicing weight is a lower bound on voicing discriminability; treat it as fitted-for-Phatak-08, not a universal constant. The published weights use the aggregation fix (§2) so that stop voicing (p–b 1.51) is not priced below stop place (p–t 1.51). See §4 for tuning guidance.
>
> **Aggregation caveat — stop vs fricative voicing.** Stop voicing confusions are tiny (/p/→/b/ 2%, /t/→/d/ 0%, /k/→/g/ 0.3% at 0 dB) while fricative voicing confusions are large and asymmetric (/θ/→/ð/ 22%, /f/→/b/ 15%). A single scalar weight cannot represent both; the pooled fit lands between them. The published weights resolve the direction for stops (voicing ≥ place) at +1.5% LOCO cost (v8). A structurally exact solution would need per‑manner weights (beyond a single global diagonal M); refit per manner class if task‑specific data require it.

> **The airstream dimension.** `airflow_direction` encodes airflow direction as a continuous physical quantity: +1.0 egressive (pulmonic, glottalic egressive), −1.0 ingressive (glottalic ingressive, lingual). It is the *only* continuous dimension in the space: no intermediate value exists in speech production (there is no half‑ingressive mechanism), so ±1 endpoints are used and interpolation between them is meaningless but harmless in the metric. Its weight (4.0) is qualitative — no confusion data cover non‑pulmonic pairs. Consequences:
> - `/k͡p/` vs `/ʘ/` (identical on the 15 articulatory dims) now differ by √(4·4) = 4.0 before λ, plus λ = 5.5 → total 9.5, well above e.g. `/p/` vs `/pʼ/`, matching the perceptual intuition that the click is far more distinct.
> - Any click vs pulmonic pair is ≥ 9.5 total; any ejective vs pulmonic pair is ≤ 11.5 (v8) and can be as close as 6.3 (/kʼ/ vs /ʔ/).

## 3. Airstream Penalty λ

Default **λ = 5.5** (v8; was 5.0 in v4–v7). Rationale: cross‑airstream confusions are essentially absent perceptually (an ejective is never heard as a pulmonic stop under any tested condition), so the penalty must exceed every within‑category distance. Calibrated on the full IPA vector table with the fitted weights of §2: the largest within‑category distance is 5.156 (pulmonic /ʍ/ vs /ʔ/; ejective 3.162, implosive 2.737, lingual 2.067). Setting λ = 5.5 guarantees any two segments of different airstreams are farther apart than any same‑airstream pair (measured minimum cross‑airstream total 6.344, /kʼ/ vs /ʔ/). Measured cross‑airstream distances (with λ): pulmonic↔ejective 6.344–11.049, pulmonic↔ingressive 9.677–11.684, pulmonic↔lingual 9.500–11.741, ejective↔ingressive 10.193–11.258, ejective↔lingual 11.192–12.011, ingressive↔lingual 7.952–9.236. Click–stop pairs sit at ≥ 9.5 — the click's perceptual distinctness is carried by the `airflow_direction` dimension rather than by a category‑specific penalty.

## 4. Caveats and Tuning

1. **Scope**: the fitted data cover 16 English consonants (Phatak et al. 2008; MN55) — no vowels, no non‑pulmonics. `tongue_root` (constant 0.0 in the set) carries no signal and was kept at its MN55‑tier value; vowel‑specific behaviour of `tongue_body_pos` (backness) and `tongue_tip_height` is not covered and remains provisional.
2. **Voicing weight is data‑specific**: raw fitted ≈0.36–0.89, published (rescaled, v8) `voiced` 0.749 / `constricted_glottis` 11.833 / `spread_glottis` 6.575 on the 2008 replication, whose voicing confusions are large and asymmetric. MN55 (1955) found voicing the most robust feature. A symmetric Shepard model cannot capture asymmetric confusions; expect the true voicing weight to lie between the MN55 tier (8.0) and the fitted value. Refit on task‑specific data when available.
3. **Calibration targets**: (a) refit M to larger confusion matrices (Miller & Nicely 1955; Phatak & Allen 2007; language‑specific CM studies) via metric learning; (b) validate against production‑error data and lexical neighborhood measures.
4. **Per‑language adaptation**: for a target language, restrict the inventory and re‑learn the diagonal; the full matrix M captures correlated cues (e.g., place × rounding for /ʃ/).
5. **Clicks**: all clicks encode the dual closure (front contact + velar `tongue_body_pos=−0.5`) and `airflow_direction=−1.0`; without the velar component /p/, /t̪/, /t/, /c/ would collide with /ʘ/, /ǀ/, /ǃ/, /ǂ/ respectively, and without the airflow dimension /k͡p/ would equal /ʘ/.

## 5. metric.json Schema

```json
{
  "version": 9,
  "dimensions": [ "<name>", ... 16 entries in vector order ],
  "weights":    [ 1.0, ... 16 entries, diagonal of default M ],
  "metric":     null,            // full 16×16 M (row-major); null = diag(weights)
  "lambda":     5.5,             // airstream penalty
  "airstream":  [ "pulmonic", "glottalic egressive", "glottalic ingressive", "lingual" ]
}
```

- `weights` order matches the vector tuple order in README §5 / IPA_VECTORS.md.
- Setting `metric` to a full matrix overrides `weights`.
- When learning: store the learned $L$ (or $M$) back into `metric`; keep `weights` as the documented initialisation.

## 6. References

- Miller, G. A. & Nicely, P. E. (1955). An analysis of perceptual confusions among some English consonants. *JASA* 27:338–352.
- Lovitt, A. & Allen, J. B. (2006). 50 years late: Repeating Miller–Nicely 1955. *INTERSPEECH* 2006:2154–2157.
- Phatak, S. A., Lovitt, A. & Allen, J. B. (2008). Consonant confusions in white noise. *JASA* 124:1743–1752.
- Phatak, S. A. & Allen, J. B. (2007). Consonant and vowel confusions in speech‑weighted noise. *JASA* 121:2312–2326.
- Lakretz, Y., Chechik, G., Rubin, S. & Tishby, N. (2018). Interpreting a deep learning model for speech recognition: A perceptual learning perspective. *Interspeech* 2018.
- Weinberger, K. Q. & Saul, L. K. (2009). Distance metric learning for large margin nearest neighbor classification. *JMLR* 10:207–244.
- Goldberger, J., Roweis, S., Hinton, G. & Salakhutdinov, R. (2005). Neighbourhood components analysis. *NIPS* 17.
