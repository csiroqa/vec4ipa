# IPA Continuous Vector Representation Specification

This document defines a **16‑dimensional** continuous vector space for IPA segments. All dimensions are physically motivated and take real values. Distance between vectors is the **Mahalanobis distance** (a weighted Riemannian metric), optionally combined with an airstream metadata penalty. Inactive articulators are assigned well‑defined resting values; all 16 dimensions participate in distance calculation, guaranteeing correct articulatory place distances. Vowels and consonants share one articulatory scale: **vowel height and consonantal constriction degree are the same dimension** (`effective_oral_area`), so the space is fully unified.

Default per‑dimension weights and the learnable metric matrix live in **`metric.json`** (documented in **`METRIC.md`**); weights are fitted to perceptual confusion data (Phatak et al. 2008; origin Miller & Nicely 1955), not hand‑picked.

---

## 1. Design Principles

1. **Articulatory independence** – each active organ has its own dimension; coarticulation activates several at once.
2. **Unified vowel‑consonant space** – tongue body, lips, etc. are shared; glides sit naturally between their homorganic vowels and consonant manners.
3. **Continuous values only** – no binary features.
4. **Affricates** encoded by *effective oral area* (frication phase) and *duration*, not a separate release dimension.
5. **Laryngeal state is four independent axes** – `voiced` (source), `constricted_glottis` (glottal constriction), `spread_glottis` (glottal spread), `laryngeal_tension`. Voicing and aspiration are deliberately *not* on one axis: `/p/`, `/pʰ/`, `/b/`, `/bʱ/` are all distinct, non‑overlapping points.
6. **Sibilance** expressed as *jet focusing efficiency*, not groove depth.
7. **Laterality** expressed as *lateral airflow ratio* (0 central, 1 fully lateral); velarised (dark) /l/ is encoded by tongue body position, not by a reduced lateral value.
8. **Tongue root** position covers ATR, pharyngealisation.
9. **Effective oral area** is a single constriction scale covering consonantal occlusion/friction and vowel height (high vowel ≈ 0.4, low vowel = 1.0).
10. **Global distance** – all 16 dimensions are used; resting values provide the physiological background.
11. **Distance metric** is the Mahalanobis distance; the metric matrix is initialised from perceptual weights (`metric.json`) and can be learned from data.
12. **Airstream** is metadata (pulmonic / glottalic egressive / glottalic ingressive / lingual); airflow direction is additionally a real dimension (`airflow_direction`: +1 egressive, −1 ingressive) so e.g. clicks are never confusable with pulmonic stops, and a fixed penalty λ is added when the airstream labels differ.
13. **Tip gestures are location × height** – `tongue_tip_pos` (front–back) and `tongue_tip_height` (vertical, Maeda 1990 APEX parameter) are separate; only *active* tip gestures are encoded. A passive tip rides with the tongue body (gestural principle, Browman & Goldstein 1992) and is assigned the resting value.
14. **Bipolar axes have a true neutral** – `lips_rounded`, `tongue_tip_pos`, `tongue_body_pos`, `laryngeal_tension` are −1…+1 with 0 = neutral; positive = front/advanced, negative = back/retracted (no zero‑at‑boundary artifacts).

---

## 2. Vector Dimensions (16‑D)

| Index | Name                  | Description                                                | Range                                                                                            |
| ----- | --------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 0     | `lips_closed`         | Lip closure degree                                         | 0.0 = open, 1.0 = fully closed                                                                   |
| 1     | `lips_rounded`        | Lip rounding/spreading                                     | -1.0 = spread (/i/), 0.0 = neutral, +1.0 = rounded (/u/); consonants may be labialised (e.g. /ʃ/ ≈ +0.25) |
| 2     | `tongue_tip_pos`              | Tongue tip position (front–back)                           | +1.0 = interdental/dental, +0.55 = alveolar, +0.25 = post‑alv., +0.1 = retroflex, 0.0 = palatal, −1.0 = velar |
| 3     | `tongue_tip_height`           | Tongue tip height (Maeda APEX)                             | 0.25 = rest/low, 0.5 = raised (dental fricatives), 0.6 = laminal sibilants, 0.8–0.9 = apical/retroflex/taps, 1.0 = full tip closure (t/d/n) |
| 4     | `tongue_body_pos`              | Tongue body position (front–back)                          | +1.0 = palatal/front, 0.0 = central, −0.5 = velar, −0.72 = uvular, −0.89 = pharyngeal, −1.0 = epiglottal |
| 5     | `tongue_root`         | Tongue root position (ATR ↔ RTR)                           | -1.0 = advanced, 0.0 = neutral, +1.0 = retracted/pharyngealised                                  |
| 6     | `vel_open`            | Velopharyngeal opening (nasality)                          | 0.0 = oral, 0.6 = nasalised vowel, 1.0 = full nasal                                              |
| 7     | `lateral_ratio`       | Lateral airflow fraction                                   | 0.0 = central, 1.0 = fully lateral                                                               |
| 8     | `voiced`              | Vocal fold vibration                                       | 0.0 = voiceless, 1.0 = voiced (all vowels and sonorants set 1.0)                                 |
| 9     | `constricted_glottis`                  | Glottal constriction (≈ 1 − OQ)                            | 0.0 = open, 0.2 = modal voiced, 0.55 = implosive constriction, 0.7 = creaky (OQ≈0.3), 1.0 = fully closed (/ʔ/, ejective hold) |
| 10    | `spread_glottis`                  | Glottal spread (abduction)                                 | 0.0 = adducted, 0.4 = voiceless unaspirated, 0.55 = breathy /ɦ/, 0.7 = voiced aspiration (/bʱ/), 0.9 = voiceless aspiration (/pʰ/), 1.0 = maximally open (/h/) |
| 11    | `laryngeal_tension`   | Laryngeal muscle tension                                   | -1.0 = slack (breathy), 0.0 = modal, +1.0 = stiff (creaky/ejective)                              |
| 12    | `duration`            | Inherent relative duration (short V = 1.0, ratio scale)    | 0.0 = plosive transient, 0.3 = tap/flap, 0.4–1.0 = fricative (anterior→posterior; voiceless 0.5–1.0, voiced ≈ −0.1, sibilants 0.7–0.95), 1.0 = nasal/approximant/short V, 1.2–1.5 = affricate (= 0.5 closure + homorganic fricative phase), 2.0 = long V, geminate = ×2 |
| 13    | `jet_focus`           | Sibilant jet focusing efficiency (spectral peak height)    | 0.0 = non‑sibilant (flat spectrum), 0.8–1.0 = sibilant (sharp peak, +10–15 dB); /s/ ≈ 0.95 > /ɕ/ ≈ 0.90 > /ʃ/ ≈ 0.85 > /ʂ/ ≈ 0.80; voiced ≈ −0.05 |
| 14    | `effective_oral_area` | Normalised minimum cross‑sectional area in the oral cavity (÷ ≈1.5 cm²) | 0.0 = complete occlusion; 0.01–0.15 = fricative (constriction ≤ ~0.2 cm²); 0.3–0.6 = approximant (≈0.5–1.0 cm²); 0.4–0.9 = vowel height (high ≈ 0.4 ≈ 0.5 cm² → low = 1.0 ≈ 1.5 cm²); 1.0 = fully open |
| 15    | `airflow_direction`   | Airflow direction (continuous physical quantity)           | +1.0 = egressive (pulmonic, glottalic egressive), −1.0 = ingressive (glottalic ingressive, lingual); endpoints only — no intermediate mechanism exists |

**Former single axis `glottal_aperture` (which conflated voicing with aspiration) is split into `constricted_glottis` + `spread_glottis`.** Former `tongue_tip_pos` (0…1, zero at the teeth) and `tongue_body_pos` (0…1.8) are re‑anchored as bipolar axes with physiological neutral at 0; `tongue_tip_height` is new (Maeda APEX).

---

## 3. Resting Values for Inactive Articulators

When an articulator is not actively recruited for a segment, it is set to a **physiologically neutral resting value**. This ensures that all 16 dimensions always contain meaningful numbers and that place distances are correctly captured.

| Dimension             | Resting value                     |
| --------------------- | --------------------------------- |
| `lips_closed`         | 0.0                               |
| `lips_rounded`        | 0.0                               |
| `tongue_tip_pos`              | +0.55 (relaxed tip projects to the alveolar region; Maeda 1990 neutral config) |
| `tongue_tip_height`           | 0.25 (tip low; Maeda 1990 neutral apex) |
| `tongue_body_pos`              | 0.0 (central)                     |
| `tongue_root`         | 0.0                               |
| `vel_open`            | 0.0                               |
| `lateral_ratio`       | 0.0                               |
| `voiced`              | 0.0 (vowels and all sonorants set this to 1.0) |
| `constricted_glottis`                  | 0.2 (modal adduction)             |
| `spread_glottis`                  | 0.0                               |
| `laryngeal_tension`   | 0.0                               |
| `duration`            | 1.0                               |
| `jet_focus`           | 0.0                               |
| `effective_oral_area` | 1.0                               |
| `airflow_direction`   | (no neutral value: +1.0 egressive / −1.0 ingressive; every segment takes one endpoint) |

**Example:** `/p/` uses `lips_closed=1.0`, `effective_oral_area=0.0`, while its tongue dimensions remain at rest (`tongue_tip_pos=+0.55`, `tongue_tip_height=0.25`, `tongue_body_pos=0.0`). `/t/` sets `tongue_tip_pos=+0.55`, `tongue_tip_height=1.0` (tip raised to closure), `effective_oral_area=0.0`, and `lips_closed=0.0` (rest). The global distance between them reflects the large difference in `lips_closed` and `tongue_tip_height`. Glottal consonants `/h/` and `/ʔ/` keep every oral articulator at rest; their identity lives entirely in the laryngeal dimensions (`constricted_glottis`, `spread_glottis`, `voiced`, `laryngeal_tension`) and `duration`.

**Passive tip rule:** segments whose constriction is made by another organ (labials, velars, uvulars, pharyngeals, epiglottals, glottals, and vowels) carry the resting tip values; the tip is *carried* by the tongue body and its true position emerges from the body gesture (Browman & Goldstein 1992). Only active tip gestures are encoded in `tongue_tip_pos`/`tongue_tip_height`.

---

## 4. Distance Metric: Mahalanobis Distance

The distance between two vectors **x** and **y** (both in ℝ¹⁶) is defined as:

$$
      D(x, y) = d_M(x, y) + λ · [airstream(x) ≠ airstream(y)]
$$

with $d_M(x,y) = \sqrt{(x-y)^\top M (x-y)}$. The default metric is $M = \mathrm{diag}(w)$ with weights from **`metric.json`** (see **`METRIC.md`** for the fitting to Phatak et al. 2008 confusion matrices, origin Miller & Nicely 1955 thresholds). $M$ can be replaced by a full learned matrix $M = L^\top L$.

This keeps the vector space purely continuous while still penalising different initiatory mechanisms.

---

## 5. Example Vectors

Format: 16‑tuple `(lips_closed, lips_rounded, tongue_tip_pos, tongue_tip_height, tongue_body_pos, tongue_root, vel_open, lateral_ratio, voiced, constricted_glottis, spread_glottis, laryngeal_tension, duration, jet_focus, effective_oral_area, airflow_direction)`, followed by airstream label. All examples below are pulmonic egressive unless labelled otherwise (`airflow_direction = +1.0`).

### `/p/` (pulmonic)
`(1.0, 0.0, 0.55, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, +1.0)`

### `/t/` (pulmonic)
`(0.0, 0.0, 0.55, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, +1.0)`

### `/t͡s/` (pulmonic)
`(0.0, 0.0, 0.55, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 1.3, 0.95, 0.10, +1.0)`

### `/s/` (pulmonic)
`(0.0, 0.0, 0.55, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.8, 0.95, 0.08, +1.0)`

### `/ʃ/` (pulmonic)
`(0.0, 0.25, 0.25, 0.65, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.9, 0.85, 0.12, +1.0)`

### `/i/` (pulmonic)
`(0.0, -0.3, 0.55, 0.25, 1.0, -0.4, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.4, +1.0)`

### `/a/` (pulmonic)
`(0.0, 0.0, 0.55, 0.25, 0.4, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 1.0, +1.0)`

### `/u/` (pulmonic)
`(0.0, 1.0, 0.55, 0.25, -0.5, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.4, +1.0)`

### `/o/` (pulmonic)
`(0.0, 0.95, 0.55, 0.25, -0.5, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.7, +1.0)`

### `/w/` (pulmonic)
`(0.0, 1.0, 0.55, 0.25, -0.5, 0.0, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 1.0, 0.0, 0.3, +1.0)`

### `/a̰/` (creaky voice, pulmonic)
`(0.0, 0.0, 0.55, 0.25, 0.4, 0.0, 0.0, 0.0, 1.0, 0.7, 0.0, 0.7, 1.0, 0.0, 1.0, +1.0)`

### `/ɓ/` (glottalic ingressive)
`(1.0, 0.0, 0.55, 0.25, 0.0, 0.0, 0.0, 0.0, 1.0, 0.55, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)`

### `/h/` (pulmonic)
`(0.0, 0.0, 0.55, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.7, 0.0, 1.0, +1.0)`

### `/ʔ/` (glottalic egressive)
`(0.0, 0.0, 0.55, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.5, 0.0, 0.0, 1.0, +1.0)`

### Unification notes

- **Vowel height is consonantal constriction degree** on one scale: `/i/` (0.4) → `/e/` (0.7) → `/a/` (1.0) differ only in `effective_oral_area`; `/u/` (0.4) → `/o/` (0.7) → `/ɔ/` (0.85) likewise. The same dimension covers plosive occlusion (0.0), frication (0.01–0.15) and approximants (0.3–0.6).
- **Glides are non‑syllabic vowels**: `/w/` (0.3) sits just below `/u/` (0.4), `/j/` (0.35) just below `/i/` (0.4), so glide–vowel distances are small, as they should be.
- **Vowel place**: `tongue_body_pos` = backness (front +1.0 / central 0 / back −0.5), `lips_rounded` = rounding, `tongue_root` = ATR, `effective_oral_area` = height, `duration` = length (1.0 short / 2.0 long).
- **Voicing and aspiration are independent**: `/b/` = (voiced 1.0, constricted_glottis 0.2, spread_glottis 0.0) vs `/bʱ/` = (voiced 1.0, constricted_glottis 0.2, spread_glottis 0.7) vs `/p/` = (voiced 0.0, constricted_glottis 0.0, spread_glottis 0.4) vs `/pʰ/` = (voiced 0.0, constricted_glottis 0.0, spread_glottis 0.9) — four distinct, non‑conflated points.
- **Sibilance lives in `jet_focus` + `effective_oral_area`**, not in `duration`: fricative duration is place- and voicing-graded (anterior 0.5 → posterior 1.0, voiceless > voiced), so `/s/` (0.8) and `/ʃ/` (0.9) are separated by place, rounding, jet focus and area, not by an artificial length gap.

The complete vector table for the IPA inventory (vowels, pulmonic consonants, co‑articulated consonants, ejectives, implosives, clicks, and diacritic modifier rules) is provided in [IPA_VECTORS.md](IPA_VECTORS.md).

---

## 6. Learning the Metric Matrix M

The metric matrix M is initialised as $\mathrm{diag}(w)$ with the default weights in `metric.json` (documented in `METRIC.md`). To tailor distances for a specific language or task, M can be learned from data:

- **Training data:** pairs of segments with target distances or similarity labels (from perceptual confusion matrices, phonological alternations, acoustic distances).
- **Algorithms:**  
  - **Diagonal weighting:** refine per‑dimension weights via contrastive or triplet loss.  
  - **Full matrix:** use Large Margin Nearest Neighbour (LMNN), Neighbourhood Components Analysis (NCA), or end‑to‑end metric learning with a triplet loss, where M = LᵀL.
- **Integration with airstream penalty:** the learning objective can incorporate the airstream penalty or treat it as post‑processing.

Because M is constant, the resulting space is a Euclidean space after linear transformation by L (where M = LᵀL), preserving computational efficiency.

---

## 7. Notes on Masking (Optional)

Although the distance computation uses all 16 dimensions, a **binary mask vector** can still be stored alongside the feature vector to indicate which dimensions are actively controlled by the segment. This mask is not used in the default distance formula, but it may serve as auxiliary information for:
- Selective weighting (e.g., emphasising dimensions where both segments are active).
- Visualisation or debugging.

To use a mask, one can define an effective metric matrix **M' = M ⊙ (mmᵀ)** where m is the joint mask (logical AND). However, the recommended baseline is to use the full M without masking, relying on the resting values to produce correct place distances.

---

## 8. Summary of Degrees of Freedom

- **Lip actions:** lips_closed, lips_rounded
- **Tongue tip/blade:** tongue_tip_pos (dental → velar), tongue_tip_height (Maeda APEX: rest → full closure)
- **Tongue body:** tongue_body_pos (palatal +1 → epiglottal −1)
- **Tongue root:** tongue_root
- **Nasal port:** vel_open
- **Lateral airflow:** lateral_ratio
- **Laryngeal state:** voiced, constricted_glottis, spread_glottis, laryngeal_tension
- **Timing:** duration
- **Sibilant jet:** jet_focus
- **Aerodynamic area / vowel height:** effective_oral_area
- **Airflow direction:** airflow_direction (+1 egressive / −1 ingressive)
- **Airstream** (metadata, not a dimension): 4 categories (pulmonic / glottalic egressive / glottalic ingressive / lingual)

This set captures the articulatory, aerodynamic, and laryngeal essence of all IPA segments while maintaining a clean, continuous, and learnable distance metric.

---

## 9. Empirical Grounding of Values

All anchor values are **normalised ratios of empirical quantities**; intermediate values are interpolated between anchors and are labelled `(interpolated)` where no direct measurement exists. Global normalisation: `duration` by short vowel ≈ 120 ms (short V = 1.0); `effective_oral_area` by ≈ 1.5 cm² (minimum oral area of an open vowel); `constricted_glottis` ≈ 1 − open quotient (OQ); `spread_glottis` by glottal width (Kagaya 1974). Reported values are speaker- and context-dependent; anchors use central tendencies.

| Dimension | Anchor | Empirical basis |
| --------- | ------ | --------------- |
| `lips_closed` | 0 / 1 | Complete bilabial contact for /p b m/ (x-ray/MRI occlusion) |
| `lips_rounded` | −1 (spread /i/) … +1 (rounded /u/) | Lip protrusion/width measurements for rounding contrasts |
| `tongue_tip_pos` | +1 interdental/dental, +0.55 alveolar, +0.25 postalv., +0.1 retroflex, 0 palatal, −1 velar | Tongue‑tip contact sites ordered from teeth to palate (palatography, MRI); rest +0.55 = relaxed apex projects to alveolar region (Maeda 1990 neutral configuration); habitual rest posture places the tip at the incisive papilla ≈ 5 mm behind the upper incisors (≈ +0.75; resting‑posture cephalometry, BMC Oral Health 2025) — documented, but muscle‑neutral rest is used for inactive articulators |
| `tongue_tip_height` | rest 0.25, vowels 0.25, dental fricatives 0.5, laminal sibilants 0.6, apical/retroflex 0.8–0.9, tip closures 1.0 | Maeda (1990) APEX parameter (tongue‑tip height; affects F2); anchors ordered by tip‑raising scale `(interpolated between APEX settings)` |
| `tongue_body_pos` | +1 palatal → 0 central → −0.5 velar → −0.72 uvular → −0.89 pharyngeal → −1 epiglottal | Dorsal place along hard palate → velum → posterior pharynx (MRI area functions, Story, Titze & Hoffman 1996); −0.72/−0.89/−1.0 pinned to uvular/pharyngeal/epiglottal MRI sites; −0.5 velar is the central‑to‑uvular midpoint `(interpolated)` |
| `tongue_root` | −1 ATR … +1 RTR | Pharyngeal width differences for ATR pairs (MRI: advanced root widens pharynx) |
| `vel_open` | oral 0, nasalised V 0.6, nasal 1.0 | Velopharyngeal port area: nasal consonants require maximal port opening; nasal vowels partial opening |
| `lateral_ratio` | 0 central … 1 fully lateral | Lateral airflow fraction measured aerodynamically for /l/ |
| `voiced` | 0 / 1 | Vocal fold vibration (EGG, laryngoscopy) |
| `constricted_glottis` | 0 open, 0.2 modal, 0.55 implosive, 0.7 creaky, 1.0 closed (/ʔ/, ejective hold) | Open quotient: pressed/creaky OQ ≈ 0.3, modal ≈ 0.5, breathy 0.6–0.7 (Alku & Vilkman 1996; Henrich et al. 2005); constricted_glottis ≈ 1 − OQ for phonatory states; full closure for glottal stop and ejective hold (Dent, Niimi & Lisker 1980); implosives 0.55 = constricted during downward glottal movement `(interpolated)` |
| `spread_glottis` | 0 adducted, 0.4 voiceless unaspirated, 0.55 breathy, 0.7 voiced aspirated, 0.9 aspirated, 1.0 /h/ | Glottal width during stops: unaspirated < aspirated (Kagaya 1974); /h/ maximal abduction; voiced aspiration keeps folds vibrating with spread glottis (breathy source, Alku & Vilkman 1996) |
| `laryngeal_tension` | −1 slack … +1 stiff | Intrinsic laryngeal EMG: ejectives show lateralis+vocalis peak; Korean fortis vs lax muscle activity (Dent et al. 1980; Kagaya 1974; Hirose et al. 1974) |
| `duration` | fricatives 0.5–1.0, anterior → posterior, voiceless > voiced, sibilants > nonsibilants; affricates = 0.5 (closure) + fricative phase | English fricative durations: voiceless > voiced; nonsibilants (/f v θ ð/) shorter than sibilants (/s z ʃ ʒ/); within sibilants /ʃ/ > /s/ (Baum & Blumstein 1987; Crystal & House 1988; Maniwa, Jongman & Wade 2009). Non‑English places (χ ħ x) interpolated |
| `jet_focus` | non‑sibilant 0.0 (flat spectrum); /s/ 0.95 > /ɕ/ 0.90 > /ʃ/ 0.85 > /ʂ/ 0.80, voiced ≈ −0.05 | Spectral peak location decreases as place moves backward (Al‑Khairy 2005); /s z/ peak ≈ 4–5 kHz vs /ʃ ʒ/ ≈ 2.5–3 kHz (Jongman et al. 2000); sibilants 10–15 dB louder than nonsibilants with sharp peaks (Strevens 1960; Behrens & Blumstein 1988); voicing lowers the spectral peak (Jongman et al. 2000) |
| `effective_oral_area` | 0.0 occlusion; 0.01–0.15 fricative; 0.3–0.6 approximant; vowel high 0.4 → low 1.0 | Turbulence requires narrow constriction (≈ ≤0.2 cm², Stevens 1998); MRI area functions: close vowels have minimum areas ≈ 0.4–0.5 cm², open /ɑ/ ≈ 1.5 cm² (Story, Titze & Hoffman 1996); approximants intermediate |
| `airflow_direction` | +1 egressive / −1 ingressive | Airflow direction during the segment's initiator (pulmonic and glottalic egressive push air out; glottalic ingressive and lingual pull it in); endpoints only — no intermediate mechanism exists `(no direct perceptual data for non‑pulmonic pairs; qualitative)` |
| **weights** | Fitted to Phatak et al. (2008) confusion matrices (12/6/0/−6 dB SNR, LOCO-validated): laryngeal `voiced`/`constricted_glottis`/`spread_glottis` ≈ 0.7–11.8 (v8; rescaled so stop voicing = place), nasality `vel_open` 3.6, manner/duration/`jet_focus`/`lateral_ratio` ≈ 1.4–3.8, place `tongue_tip_*`/`tongue_body_*` ≈ 2.5–3.6; `lips_rounded` 8.0 (capped), `tongue_root`/`laryngeal_tension` at MN55 tiers | Origin: MN55 qualitative tiers (voicing ≈ nasality −12 dB, affrication/duration ≈ 0 dB, place < +6 dB; w = 2^((t_place − t_feature)/6)) give 8/2/1; refitted on the complete digitized Phatak, Lovitt & Allen (2008) white-noise matrices — fitted weights beat the tiers at every held-out SNR (total NLL 23,240 vs 29,553; published weights 23,435). See METRIC.md |

### Key references

- Baum, S. R. & Blumstein, S. E. (1987). Preliminary observations on the use of duration as a cue to syllable‑initial fricative consonant voicing in English. *JASA* 82:1073–1077.
- Behrens, S. J. & Blumstein, S. E. (1988). Acoustic characteristics of English voiceless fricatives: A descriptive analysis. *J. Phonetics* 16:295–298.
- Browman, C. P. & Goldstein, L. (1992). Articulatory phonology: An overview. *Phonetica* 49:155–180.
- Crystal, T. H. & House, A. S. (1988). A note on the durations of fricatives in American English. *JASA* 84:1932–1935.
- Dent, L., Niimi, S. & Lisker, L. (1980). Laryngeal adjustments in the production of voiceless unaspirated, aspirated, and glottalized stops. *JASA* 68:S101–S102.
- Henrich, N., d'Alessandro, C., Doval, B. & Castellengo, M. (2005). Glottal open quotient in singing: Measurements and correlation with laryngeal mechanisms, vocal intensity, and fundamental frequency. *JASA* 117:1417–1430.
- Alku, P. & Vilkman, E. (1996). A comparison of glottal voice source quantification parameters in breathy, normal, and pressed phonation. *Folia Phoniatrica* 48:240–254.
- Jongman, A., Wayland, R. & Wong, S. (2000). Acoustic characteristics of English fricatives. *JASA* 108:1252–1263.
- Kagaya, R. (1974). A fiberscopic and acoustic study of the Korean stops, affricates, and fricatives. *J. Phonetics* 2:161–180.
- Lovitt, A. & Allen, J. B. (2006). 50 years late: Repeating Miller–Nicely 1955. *INTERSPEECH* 2006:2154–2157.
- Maeda, S. (1990). Compensatory articulation during speech: Evidence from the analysis and synthesis of vocal‑tract shapes using an articulatory model. In *Speech Production and Speech Modelling*, 131–149.
- Maniwa, K., Jongman, A. & Wade, T. (2009). Acoustic characteristics of clearly spoken English fricatives. *JASA* 125:3962–3973.
- Miller, G. A. & Nicely, P. E. (1955). An analysis of perceptual confusions among some English consonants. *JASA* 27:338–352.
- Al‑Khairy, M. (2005). *Acoustic characteristics of Arabic fricatives.* University of Florida dissertation.
- Resting tongue posture: tip rests ≈ 5 mm behind the upper incisors at the incisive papilla ("N" point). *BMC Oral Health* (2025), 25, article 682 (cephalometric tongue‑position study).
- Story, B. H., Titze, I. R. & Hoffman, E. A. (1996). Vocal tract area functions from magnetic resonance imaging. *JASA* 100:537–554.
- Stevens, K. N. (1998). *Acoustic Phonetics.* MIT Press.
- Strevens, P. (1960). Spectra of fricative noise in human speech. *Language and Speech* 3:32–49.

---

**End of Specification**
