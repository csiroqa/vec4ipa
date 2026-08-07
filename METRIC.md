# Metric Specification

Machine‑readable weights and metric live in **`metric.json`**; this document explains the derivation, the schema, and how to learn/tune the metric.

> **v6 (vowel-consonant anchors):** the v5 refit collapsed `effective_oral_area` (0.57) — the confusion data (16 consonants) gives no signal for the vowel space, so a nasalised long vowel mapped to a nasal consonant (ãː → /ɲ/). The refit now adds vowel-consonant separation anchors (`tools/fit_metric.py`, `--anchor`): for every vowel-like base and its nasalised/long extensions, the nearest vowel must stay closer than the nearest consonant, so the vowel-consonant contrast is carried by the dimensions that genuinely differ (oral area, duration, nasality). `effective_oral_area` = 7.45; LOCO held-out NLL: **fitted 21,954 < v5 22,048 < MN55 tiers 28,190**. The four no-signal dimensions (tongue_root, lateral_ratio, laryngeal_tension, airflow_direction) are pinned at tier defaults during the fit.

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
- **Identifiability caveat**: the model has one free global scale (w → c·w, a → a/√c leaves all distances unchanged), so only the *relative* weight pattern is identified, not the absolute values. The absolute scale printed here is the log‑space‑regularised solution (toward the 8/2/1 initialisation); the reported ratios (e.g. lips_rounded ≈ 6× tt_pos, voiced ≈ 1/6 × tt_pos) are stable across initialisations and regularisation schemes.
- The fit collapses the MN55 voicing tier: voicing confusions in Phatak 08 are massive and asymmetric (e.g., θ→ð 22%), so `voiced` and its glottal proxies are fitted low (≈ 0.36–0.89 raw) instead of 8.0. The `voiced`/`cg`/`sg` triplet is perfectly collinear within the 16-consonant set, so only their combined voicing distance is identifiable.
- **Aggregation fix**: the raw pooled fit made the stop voicing distance (p vs b = 0.72) *smaller* than the stop place distance (p vs t = 0.87) — contradicting the data, where stop voicing confusions are tiny (p→b 2% at 0 dB) and stop place confusions are large (p→t 9%). The raw voicing weight is dragged down by fricatives (θ→ð 22%), whose voicing cues genuinely are weaker. Because `voiced`/`cg`/`sg` are perfectly collinear in the 16-consonant set, their *relative* values are unidentifiable and only the combined voicing distance matters — so the triplet was rescaled by factor 1.46 so that the voicing distance equals the place distance (p–b = p–t = 1.295). Cost: +0.5% held-out NLL (23,435 vs 23,240). This keeps the order voicing ≥ place for stops, matching both MN55 and the 0 dB confusion data, while fricative voicing (f–v ≈ 1.30) still prices the genuinely weaker fricative voicing cue realistically.
- `lips_rounded` fitted at ≈ 21 (only /ʃ/ differs on it within the 16 consonants); capped at 8.0 to avoid overfitting noise (costs only 0.3% NLL).
- `tongue_root`, `lateral_ratio`, `laryngeal_tension` carry no signal in this 16-consonant set (constant 0.0) and were kept at their MN55-tier values (1.0 / 2.0 / 8.0); `duration` is well identified (8 distinct values across the set) and was fitted (1.405).

Final fitted weights (dimension order as in `metric.json`, v6 — the v5 weights are shown for reference):

| Dimension | Feature (MN55) | Weight (v6) | v5 | Fit basis |
| --------- | -------------- | ----------- | --- | --------- |
| `lips_closed`      | place (labial closure) | 1.279 | 1.558 | fitted (f/v/p̪/ɱ/ⱱ are 1.0) |
| `lips_rounded`     | place (rounding) | 8.0 (capped; raw ≈ 31) | 8.0 | fitted, capped |
| `tt_pos`           | place (tip position) | 0.968 | 1.148 | fitted |
| `tt_height`        | place (tip closure) | 1.432 | 1.738 | fitted |
| `tb_pos`           | place (body position) | 2.310 | 2.798 | fitted |
| `tongue_root`      | place (ATR; not in MN55/Phatak sets) | 1.0 | 1.0 | tier default (pinned) |
| `vel_open`         | nasality | 3.128 | 3.819 | fitted |
| `lateral_ratio`    | manner (laterality) | 2.0 | 2.0 | tier default (pinned) |
| `voiced`           | voicing | 0.485 | 0.927 | fitted, then rescaled (aggregation fix) |
| `cg`               | voicing (glottal constriction) | 6.916 | 5.806 | fitted, then rescaled (collinear with `voiced`/`sg`) |
| `sg`               | voicing (glottal spread) | 3.554 | 2.858 | fitted, then rescaled (collinear with `voiced`/`cg`) |
| `laryngeal_tension`| voicing (laryngeal) | 8.0 | 8.0 | tier default (pinned) |
| `duration`         | duration | 2.353 | 3.129 | fitted |
| `jet_focus`        | frication | 2.342 | 2.801 | fitted |
| `effective_oral_area` | affrication (manner) / vowel height | 7.450 | 0.565 | fitted + vowel-consonant anchors |
| `airflow_direction` | airstream direction | 4.0 | 4.0 | qualitative (pinned) |

> **Placement note — `tt_height`:** `tt_height` stays in the *place* tier: the tip‑closure contrast it codes is a place contrast. Phatak & Allen (2007) and MN55 show /pa,ta/ is the *hardest* stop‑place pair (81% correct at 10 dB SNR vs ≥92% for all other CV pairs), so tip‑activation must not be priced higher than body position. Manner contrasts (e.g., /t/ vs /s/) are carried by `duration`, `jet_focus`, `effective_oral_area`.

> **Why voicing lost its 8.0:** the fitted voicing weight reflects the 2008 replication, where fricative voicing confusions are large and asymmetric (θ→ð, f→b). The classic MN55 voicing-is-robust result holds only in the 1955 analog experiment. Caveat: a symmetric Shepard model cannot capture asymmetric confusions, so the voicing weight is a lower bound on voicing discriminability; treat it as fitted-for-Phatak-08, not a universal constant. The published weights use the aggregation fix (§2) so that stop voicing (p–b 1.30) is not priced below stop place (p–t 1.30). See §4 for tuning guidance.
>
> **Aggregation caveat — stop vs fricative voicing.** Stop voicing confusions are tiny (/p/→/b/ 2%, /t/→/d/ 0%, /k/→/g/ 0.3% at 0 dB) while fricative voicing confusions are large and asymmetric (/θ/→/ð/ 22%, /f/→/b/ 15%). A single scalar weight cannot represent both; the pooled fit lands between them. The published weights resolve the direction for stops (voicing ≥ place) at +0.5% NLL cost. A structurally exact solution would need per‑manner weights (beyond a single global diagonal M); refit per manner class if task‑specific data require it.

> **The airstream dimension.** `airflow_direction` encodes airflow direction as a continuous physical quantity: +1.0 egressive (pulmonic, glottalic egressive), −1.0 ingressive (glottalic ingressive, lingual). It is the *only* continuous dimension in the space: no intermediate value exists in speech production (there is no half‑ingressive mechanism), so ±1 endpoints are used and interpolation between them is meaningless but harmless in the metric. Its weight (4.0) is qualitative — no confusion data cover non‑pulmonic pairs. Consequences:
> - `/k͡p/` vs `/ʘ/` (identical on the 15 articulatory dims) now differ by √(4·4) = 4.0 before λ, plus λ = 5.0 → total 9.0, well above e.g. `/p/` vs `/pʼ/` at 7.7, matching the perceptual intuition that the click is far more distinct.
> - Any click vs pulmonic pair is ≥ 9.0 total; any ejective vs pulmonic pair is ≤ 9.9 and can be as close as 6.9 (/ʔ/ vs /fʼ/).

## 3. Airstream Penalty λ

Default **λ = 5.0**. Rationale: cross‑airstream confusions are essentially absent perceptually (an ejective is never heard as a pulmonic stop under any tested condition), so the penalty must exceed every within‑category distance. Calibrated on the full IPA vector table with the fitted weights of §2: the largest within‑category distance is 4.717 (pulmonic /ø/ vs /ʡ/; ejective 2.679, implosive 2.795, lingual 1.918). Setting λ = 5.0 guarantees any two segments of different airstreams are farther apart than any same‑airstream pair. Measured cross‑airstream articulatory distances (before λ): pulmonic↔ejective 1.898–4.943 (min /ʔ,fʼ/; max /ø,qʼ/), pulmonic↔ingressive 4.061–5.972 (min /b,ɓ/), pulmonic↔lingual 4.000–6.088 (min /k͡p,ʘ/). With λ the closest cross‑airstream pair becomes /ʔ/ vs /fʼ/ at 6.9, while click–stop pairs sit at ≥ 9.0 — the click's perceptual distinctness is carried by the `airflow_direction` dimension rather than by a category‑specific penalty.

## 4. Caveats and Tuning

1. **Scope**: the fitted data cover 16 English consonants (Phatak et al. 2008; MN55) — no vowels, no non‑pulmonics. `tongue_root` (constant 0.0 in the set) carries no signal and was kept at its MN55‑tier value; vowel‑specific behaviour of `tb_pos` (backness) and `tt_height` is not covered and remains provisional.
2. **Voicing weight is data‑specific**: raw fitted ≈0.36–0.89, published (rescaled) ≈0.94–5.8 on the 2008 replication, whose voicing confusions are large and asymmetric. MN55 (1955) found voicing the most robust feature. A symmetric Shepard model cannot capture asymmetric confusions; expect the true voicing weight to lie between the MN55 tier (8.0) and the fitted value. Refit on task‑specific data when available.
3. **Calibration targets**: (a) refit M to larger confusion matrices (Miller & Nicely 1955; Phatak & Allen 2007; language‑specific CM studies) via metric learning; (b) validate against production‑error data and lexical neighborhood measures.
4. **Per‑language adaptation**: for a target language, restrict the inventory and re‑learn the diagonal; the full matrix M captures correlated cues (e.g., place × rounding for /ʃ/).
5. **Clicks**: all clicks encode the dual closure (front contact + velar `tb_pos=−0.5`) and `airflow_direction=−1.0`; without the velar component /p/, /t̪/, /t/, /c/ would collide with /ʘ/, /ǀ/, /ǃ/, /ǂ/ respectively, and without the airflow dimension /k͡p/ would equal /ʘ/.

## 5. metric.json Schema

```json
{
  "version": 3,
  "dimensions": [ "<name>", ... 16 entries in vector order ],
  "weights":    [ 1.0, ... 16 entries, diagonal of default M ],
  "metric":     null,            // full 16×16 M (row-major); null = diag(weights)
  "lambda":     5.0,             // airstream penalty
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
