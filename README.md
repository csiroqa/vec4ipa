# IPA Continuous Vector Representation Specification

This document defines a **13‑dimensional** continuous vector space for IPA segments. All dimensions are physically motivated and take real values. Distance between vectors is the **Mahalanobis distance** (a weighted Riemannian metric), optionally combined with an airstream metadata penalty. Inactive articulators are assigned well‑defined resting values; all 13 dimensions participate in distance calculation, guaranteeing correct articulatory place distances. Vowels and consonants share one articulatory scale: **vowel height and consonantal constriction degree are the same dimension** (`effective_oral_area`), so the space is fully unified.

---

## 1. Design Principles

1. **Articulatory independence** – each active organ has its own dimension; coarticulation activates several at once.
2. **Unified vowel‑consonant space** – tongue body, lips, etc. are shared; glides sit naturally between their homorganic vowels and consonant manners.
3. **Continuous values only** – no binary features.
4. **Affricates** encoded by *effective oral area* (frication phase) and *duration*, not a separate release dimension.
5. **Laryngeal state** split into *glottal aperture* and *laryngeal tension*.
6. **Sibilance** expressed as *jet focusing efficiency*, not groove depth.
7. **Laterality** expressed as *lateral airflow ratio* (0 central, 1 fully lateral); velarised (dark) /l/ is encoded by tongue root/tongue body, not by a reduced lateral value.
8. **Tongue root** position covers ATR, pharyngealisation.
9. **Effective oral area** is a single constriction scale covering consonantal occlusion/friction and vowel height (high vowel ≈ 0.4, low vowel = 1.0).
10. **Global distance** – all 13 dimensions are used; resting values provide the physiological background.
11. **Distance metric** is the Mahalanobis distance; the metric matrix can be learned from data.
12. **Airstream** is metadata; a fixed penalty is added when labels differ.

---

## 2. Vector Dimensions (13‑D)

| Index | Name                  | Description                                                | Range                                                                                            |
| ----- | --------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 0     | `lips_closed`         | Lip closure degree                                         | 0.0 = open, 1.0 = fully closed                                                                   |
| 1     | `lips_rounded`        | Lip rounding/spreading                                     | -1.0 = spread (/i/), 0.0 = neutral, +1.0 = rounded (/u/); consonants may be labialised (e.g. /ʃ/ ≈ +0.25) |
| 2     | `tt_pos`              | Tongue tip/blade anterior–posterior position               | 0.0 = interdental, 0.15 = dental, 0.4 = alveolar, 0.7 = post‑alv., 1.0 = retroflex               |
| 3     | `tb_pos`              | Tongue body anterior–posterior position                    | 0.0 = palatal/front, 0.5 = central, 1.0 = velar/back, 1.3 = uvular, 1.6 = pharyngeal              |
| 4     | `tongue_root`         | Tongue root position (ATR ↔ RTR)                           | -1.0 = advanced, 0.0 = neutral, +1.0 = retracted/pharyngealised                                  |
| 5     | `vel_open`            | Velopharyngeal opening (nasality)                          | 0.0 = oral, 0.8 = nasalised vowel, 1.0 = full nasal                                              |
| 6     | `lateral_ratio`       | Lateral airflow fraction                                   | 0.0 = central, 1.0 = fully lateral                                                               |
| 7     | `voiced`              | Vocal fold vibration                                       | 0.0 = voiceless, 1.0 = voiced (all vowels and sonorants set 1.0)                                 |
| 8     | `glottal_aperture`    | Glottal opening (≈ open quotient)                          | 0.0 = closed (glottal stop/ejective), 0.3 = narrow (creaky, OQ≈0.3), 0.5 = modal (OQ≈0.5), 0.65 = breathy (OQ≈0.6–0.7), 0.75 = open (voiceless), 0.95 = wide (aspirated), 1.0 = maximally open (/h/) |
| 9     | `laryngeal_tension`   | Laryngeal muscle tension                                   | -1.0 = slack (breathy), 0.0 = modal, +1.0 = stiff (creaky/ejective; ejectives also close the glottis, aperture ≈ 0.0) |
| 10    | `duration`            | Inherent relative duration (short V = 1.0)                 | 0.0 = plosive transient, 0.3 = tap/flap, 0.4–1.0 = fricative (anterior→posterior; voiceless 0.5–1.0, voiced ≈ −0.1, sibilants 0.7–0.95), 1.0 = nasal/approximant/short V, 1.2–1.5 = affricate (= 0.5 closure + homorganic fricative phase), 2.0 = long V, geminate = ×2 |
| 11    | `jet_focus`           | Sibilant jet focusing efficiency (spectral peak height)    | 0.0 = non‑sibilant (flat spectrum), 0.8–1.0 = sibilant (sharp peak, +10–15 dB); /s/ ≈ 0.95 > /ɕ/ ≈ 0.90 > /ʃ/ ≈ 0.85 > /ʂ/ ≈ 0.80; voiced ≈ −0.05 |
| 12    | `effective_oral_area` | Normalised minimum cross‑sectional area in the oral cavity (÷ ≈1.5 cm²) | 0.0 = complete occlusion; 0.01–0.15 = fricative (constriction ≤ ~0.2 cm²); 0.3–0.6 = approximant (≈0.5–1.0 cm²); 0.4–0.9 = vowel height (high ≈ 0.4 ≈ 0.5 cm² → low = 1.0 ≈ 1.5 cm²); 1.0 = fully open |

**Note:** Former separate dimensions *tt_close*, *tb_close*, *constriction_area* are merged into `effective_oral_area`, which now also encodes vowel height.

---

## 3. Resting Values for Inactive Articulators

When an articulator is not actively recruited for a segment, it is set to a **physiologically neutral resting value**. This ensures that all 13 dimensions always contain meaningful numbers and that place distances are correctly captured.

| Dimension             | Resting value                     |
| --------------------- | --------------------------------- |
| `lips_closed`         | 0.0                               |
| `lips_rounded`        | 0.0                               |
| `tt_pos`              | 0.5                               |
| `tb_pos`              | 0.5                               |
| `tongue_root`         | 0.0                               |
| `vel_open`            | 0.0                               |
| `lateral_ratio`       | 0.0                               |
| `voiced`              | 0.0 (vowels and all sonorants set this to 1.0) |
| `glottal_aperture`    | 0.5                               |
| `laryngeal_tension`   | 0.0                               |
| `duration`            | 1.0                               |
| `jet_focus`           | 0.0                               |
| `effective_oral_area` | 1.0                               |

**Example:** `/p/` uses `lips_closed=1.0`, `effective_oral_area=0.0`, while its tongue dimensions remain at rest (`tt_pos=0.5`, `tb_pos=0.5`). `/t/` sets `tt_pos=0.4`, `effective_oral_area=0.0`, and `lips_closed=0.0` (rest). The global distance between them naturally reflects the large difference in `lips_closed` and the small difference in `tt_pos`. Glottal consonants `/h/` and `/ʔ/` keep every oral articulator at rest; their identity lives entirely in the laryngeal dimensions (`glottal_aperture`, `voiced`, `laryngeal_tension`) and `duration`.

---

## 4. Distance Metric: Mahalanobis Distance

The distance between two vectors **x** and **y** (both in ℝ¹³) is defined as:

$$
      D(x, y) = d_M(x, y) + λ · [airstream(x) ≠ airstream(y)]
$$

This keeps the vector space purely continuous while still penalising different initiatory mechanisms.

---

## 5. Example Vectors

Format: 13‑tuple `(lips_closed, lips_rounded, tt_pos, tb_pos, tongue_root, vel_open, lateral_ratio, voiced, glottal_aperture, laryngeal_tension, duration, jet_focus, effective_oral_area)`, followed by airstream label.

### `/p/` (pulmonic)
`(1.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0, 0.0, 0.0, 0.0)`

### `/t/` (pulmonic)
`(0.0, 0.0, 0.4, 0.5, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0, 0.0, 0.0, 0.0)`

### `/t͡s/` (pulmonic)
`(0.0, 0.0, 0.4, 0.5, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0, 1.3, 0.95, 0.10)`

### `/s/` (pulmonic)
`(0.0, 0.0, 0.4, 0.5, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0, 0.8, 0.95, 0.08)`

### `/ʃ/` (pulmonic)
`(0.0, 0.25, 0.7, 0.5, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0, 0.9, 0.85, 0.12)`

### `/i/` (pulmonic)
`(0.0, -0.3, 0.5, 0.0, -0.4, 0.0, 0.0, 1.0, 0.5, 0.0, 1.0, 0.0, 0.4)`

### `/a/` (pulmonic)
`(0.0, 0.0, 0.5, 0.3, 0.0, 0.0, 0.0, 1.0, 0.5, 0.0, 1.0, 0.0, 1.0)`

### `/u/` (pulmonic)
`(0.0, 1.0, 0.5, 1.0, 0.0, 0.0, 0.0, 1.0, 0.5, 0.0, 1.0, 0.0, 0.4)`

### `/o/` (pulmonic)
`(0.0, 0.95, 0.5, 1.0, 0.0, 0.0, 0.0, 1.0, 0.5, 0.0, 1.0, 0.0, 0.7)`

### `/w/` (pulmonic)
`(0.0, 1.0, 0.5, 1.0, 0.0, 0.0, 0.0, 1.0, 0.5, 0.0, 1.0, 0.0, 0.3)`

### `/a̰/` (creaky voice, pulmonic)
`(0.0, 0.0, 0.5, 0.3, 0.0, 0.0, 0.0, 1.0, 0.3, 0.7, 1.0, 0.0, 1.0)`

### `/ɓ/` (glottalic ingressive)
`(1.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 1.0, 0.3, 0.0, 0.0, 0.0, 0.0)`

### `/h/` (pulmonic)
`(0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.7, 0.0, 1.0)`

### `/ʔ/` (glottalic egressive)
`(0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 1.0)`

### Unification notes

- **Vowel height is consonantal constriction degree** on one scale: `/i/` (0.4) → `/e/` (0.7) → `/a/` (1.0) differ only in `effective_oral_area`; `/u/` (0.4) → `/o/` (0.7) → `/ɔ/` (0.85) likewise. The same dimension covers plosive occlusion (0.0), frication (0.01–0.15) and approximants (0.3–0.6).
- **Glides are non‑syllabic vowels**: `/w/` (0.3) sits just below `/u/` (0.4), `/j/` (0.35) just below `/i/` (0.4), so glide–vowel distances are small, as they should be.
- **Vowel place**: `tb_pos` = backness (front 0.0 / central 0.5 / back 1.0), `lips_rounded` = rounding, `tongue_root` = ATR, `effective_oral_area` = height, `duration` = length (1.0 short / 2.0 long).
- **Sibilance lives in `jet_focus` + `effective_oral_area`**, not in `duration`: fricative duration is place- and voicing-graded (anterior 0.5 → posterior 1.0, voiceless > voiced), so `/s/` (0.8) and `/ʃ/` (0.9) are separated by place, rounding, jet focus and area, not by an artificial length gap.

The complete vector table for the IPA inventory (vowels, pulmonic consonants, co‑articulated consonants, ejectives, implosives, clicks, and diacritic modifier rules) is provided in [IPA_VECTORS.md](IPA_VECTORS.md).

---

## 6. Learning the Metric Matrix M

The metric matrix M can be initialised as the identity matrix (default equal‑weight Euclidean) or with hand‑tuned diagonal entries. To tailor distances for a specific language or task, M can be learned from data:

- **Training data:** pairs of segments with target distances or similarity labels (from perceptual confusion matrices, phonological alternations, acoustic distances).
- **Algorithms:**  
  - **Diagonal weighting:** learn per‑dimension weights via contrastive or triplet loss.  
  - **Full matrix:** use Large Margin Nearest Neighbour (LMNN), Neighbourhood Components Analysis (NCA), or end‑to‑end metric learning with a triplet loss, where M = LᵀL.
- **Integration with airstream penalty:** the learning objective can incorporate the airstream penalty or treat it as post‑processing.

Because M is constant, the resulting space is a Euclidean space after linear transformation by L (where M = LᵀL), preserving computational efficiency.

---

## 7. Notes on Masking (Optional)

Although the distance computation uses all 13 dimensions, a **binary mask vector** can still be stored alongside the feature vector to indicate which dimensions are actively controlled by the segment. This mask is not used in the default distance formula, but it may serve as auxiliary information for:
- Selective weighting (e.g., emphasising dimensions where both segments are active).
- Visualisation or debugging.

To use a mask, one can define an effective metric matrix **M' = M ⊙ (mmᵀ)** where m is the joint mask (logical AND). However, the recommended baseline is to use the full M without masking, relying on the resting values to produce correct place distances.

---

## 8. Summary of Degrees of Freedom

- **Lip actions:** lips_closed, lips_rounded
- **Tongue tip/blade:** tt_pos (interdental → retroflex)
- **Tongue body:** tb_pos (palatal → pharyngeal)
- **Tongue root:** tongue_root
- **Nasal port:** vel_open
- **Lateral airflow:** lateral_ratio
- **Laryngeal state:** voiced, glottal_aperture, laryngeal_tension
- **Timing:** duration
- **Sibilant jet:** jet_focus
- **Aerodynamic area / vowel height:** effective_oral_area
- **Airstream** (metadata, not a dimension): 4 categories

This set captures the articulatory, aerodynamic, and laryngeal essence of all IPA segments while maintaining a clean, continuous, and learnable distance metric.

---

## 9. Empirical Grounding of Values

All anchor values are **normalised ratios of empirical quantities**; intermediate values are interpolated between anchors. Global normalisation: `duration` by short vowel ≈ 120 ms (short V = 1.0); `effective_oral_area` by ≈ 1.5 cm² (minimum oral area of an open vowel); `glottal_aperture` by open quotient (OQ) / glottal width. Reported values are speaker- and context-dependent; anchors use central tendencies.

| Dimension | Anchor | Empirical basis |
| --------- | ------ | --------------- |
| `lips_closed` | 0 / 1 | Complete bilabial contact for /p b m/ (x-ray/MRI occlusion) |
| `lips_rounded` | −1 (spread /i/) … +1 (rounded /u/) | Lip protrusion/width measurements for rounding contrasts |
| `tt_pos` | interdental 0.0 → dental 0.15 → alveolar 0.4 → postalv. 0.7 → retroflex 1.0 | Tongue-tip/blade contact points ordered from teeth to palate (palatography, MRI) |
| `tb_pos` | palatal 0.0 → central 0.5 → velar 1.0 → uvular 1.3 → pharyngeal 1.6 | Dorsal place along hard palate → velum → posterior pharynx (MRI area functions, Story, Titze & Hoffman 1996) |
| `tongue_root` | −1 ATR … +1 RTR | Pharyngeal width differences for ATR pairs (MRI: advanced root widens pharynx) |
| `vel_open` | oral 0, nasalised V 0.8, nasal 1.0 | Velopharyngeal port area: nasal consonants require maximal port opening; nasal vowels partial opening |
| `lateral_ratio` | 0 central … 1 fully lateral | Lateral airflow fraction measured aerodynamically for /l/ |
| `voiced` | 0 / 1 | Vocal fold vibration (EGG, laryngoscopy) |
| `glottal_aperture` | 0.3 creaky, 0.5 modal, 0.65 breathy, 0.75 voiceless, 0.95 aspirated, 1.0 /h/ | Open quotient: pressed/creaky OQ ≈ 0.3, modal ≈ 0.5, breathy 0.6–0.7 (Alku & Vilkman 1996; Henrich et al. 2005); voiceless stops: glottal width unaspirated < aspirated (Kagaya 1974); ejectives: tight glottal closure (Dent, Niimi & Lisker 1980) |
| `laryngeal_tension` | −1 slack … +1 stiff | Intrinsic laryngeal EMG: ejectives show lateralis+vocalis peak; Korean fortis vs lax muscle activity (Dent et al. 1980; Kagaya 1974; Hirose et al. 1974) |
| `duration` | fricatives 0.5–1.0, anterior → posterior, voiceless > voiced, sibilants > nonsibilants; affricates = 0.5 (closure) + fricative phase | English fricative durations: voiceless > voiced; nonsibilants (/f v θ ð/) shorter than sibilants (/s z ʃ ʒ/); within sibilants /ʃ/ > /s/ (Baum & Blumstein 1987; Crystal & House 1988; Maniwa, Jongman & Wade 2009). Non‑English places (χ ħ x) interpolated |
| `jet_focus` | non‑sibilant 0.0 (flat spectrum); /s/ 0.95 > /ɕ/ 0.90 > /ʃ/ 0.85 > /ʂ/ 0.80, voiced ≈ −0.05 | Spectral peak location decreases as place moves backward (Al‑Khairy 2005); /s z/ peak ≈ 4–5 kHz vs /ʃ ʒ/ ≈ 2.5–3 kHz (Jongman et al. 2000); sibilants 10–15 dB louder than nonsibilants with sharp peaks (Strevens 1960; Behrens & Blumstein 1988); voicing lowers the spectral peak (Jongman et al. 2000) |
| `effective_oral_area` | 0.0 occlusion; 0.01–0.15 fricative; 0.3–0.6 approximant; vowel high 0.4 → low 1.0 | Turbulence requires narrow constriction (≈ ≤0.2 cm², Stevens 1998); MRI area functions: close vowels have minimum areas ≈ 0.4–0.5 cm², open /ɑ/ ≈ 1.5 cm² (Story, Titze & Hoffman 1996); approximants intermediate |

### Key references

- Baum, S. R. & Blumstein, S. E. (1987). Preliminary observations on the use of duration as a cue to syllable‑initial fricative consonant voicing in English. *JASA* 82:1073–1077.
- Crystal, T. H. & House, A. S. (1988). A note on the durations of fricatives in American English. *JASA* 84:1932–1935.
- Jongman, A., Wayland, R. & Wong, S. (2000). Acoustic characteristics of English fricatives. *JASA* 108:1252–1263.
- Maniwa, K., Jongman, A. & Wade, T. (2009). Acoustic characteristics of clearly spoken English fricatives. *JASA* 125:3962–3973.
- Al‑Khairy, M. (2005). *Acoustic characteristics of Arabic fricatives.* University of Florida dissertation.
- Kagaya, R. (1974). A fiberscopic and acoustic study of the Korean stops, affricates, and fricatives. *J. Phonetics* 2:161–180.
- Dent, L., Niimi, S. & Lisker, L. (1980). Laryngeal adjustments in the production of voiceless unaspirated, aspirated, and glottalized stops. *JASA* 68:S101–S102.
- Alku, P. & Vilkman, E. (1996). A comparison of glottal voice source quantification parameters in breathy, normal, and pressed phonation. *Folia Phoniatrica* 48:240–254.
- Henrich, N., d'Alessandro, C., Doval, B. & Castellengo, M. (2005). Glottal open quotient in singing: Measurements and correlation with laryngeal mechanisms, vocal intensity, and fundamental frequency. *JASA* 117:1417–1430.
- Story, B. H., Titze, I. R. & Hoffman, E. A. (1996). Vocal tract area functions from magnetic resonance imaging. *JASA* 100:537–554.
- Stevens, K. N. (1998). *Acoustic Phonetics.* MIT Press.
- Strevens, P. (1960). Spectra of fricative noise in human speech. *Language and Speech* 3:32–49.
- Behrens, S. J. & Blumstein, S. E. (1988). Acoustic characteristics of English voiceless fricatives: A descriptive analysis. *J. Phonetics* 16:295–298.

---

**End of Specification**
