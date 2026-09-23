# CHITRA — Metrics & Evaluation Protocol

All residuals are measured in **source-image pixels**, with metres reported alongside.

## 1. Metrics

| Metric | Definition |
|---|---|
| **RMSE (fit)** | √(mean ‖T(p_src) − p_ref‖²) over inliers. Measures self-consistency of the fitted transform. |
| **GT RMSE** | √(mean ‖T_est(q) − T_true(q)‖²) over a dense 32×32 grid q covering the source. **Only available when truth is known** (synthetic pairs, co-registered LROC orthos). This is the honest accuracy number. |
| Median / P90 residual | Robust centre and tail of the inlier residuals. |
| **Inlier count** | Matches consistent with the model under MAGSAC++. |
| **Inlier ratio** | inliers / candidate matches passed to the estimator. |
| **Coverage entropy** | Split the source into an 8×8 grid, with p_i = share of inliers in cell i. H = −Σ p_i log p_i / log 64 ∈ [0, 1]. A value of 1 means perfectly uniform. |
| Shadow fraction | Share of source pixels under the shadow threshold. |
| Mean certainty | Mean RoMa certainty of the inliers. |

> ECE (Expected Calibration Error) needs a lunar validation set with real ground truth. It is planned, not reported by the prototype.

## 2. Verdict policy

Checked in order. The first failing rule sets the reason.

| Verdict | Rule |
|---|---|
| **REJECT** | inliers < 20 → `too_few_inliers` · inlier ratio < 0.15 → `matcher_collapse` · coverage entropy < 0.5 → `matches_clustered` · shadow fraction > 0.6 → `shadow_dominated` · degenerate or non-invertible transform → `inconsistent_geometry` |
| **FLAG** | RMSE ≥ 1.0 px → `rmse_above_subpixel` · coverage entropy < 0.8 → `uneven_distribution` · inlier ratio < 0.3 → `low_inlier_ratio` |
| **PASS** | none of the above |

The thresholds live in one place in code (`chitra/metrics.py`) and are copied into `config.json` for every run.

## 3. Evaluation sets (prototype)

| Set | Construction | Truth | What it proves |
|---|---|---|---|
| **SYN-ILLUM** | Apollo 11 NAC DTM (2 m/px) rendered at Sun (az₁, el₁) and (az₂, el₂), Δaz ∈ {30°, 90°, 150°}, plus a known similarity warp | exact | Sun-angle invariance |
| **SYN-SCALE** | As above, source downsampled 2×–8× | exact | Scale invariance |
| **REAL-NAC** | LROC orthophotos M150361817 ↔ M150368601 (same site, different orbits, co-registered by LROC) with a known synthetic warp applied | exact up to LROC ortho accuracy | Real-image cross-illumination |
| **REAL-CH2** | TMC-2 / OHRC (PRADAN) ↔ NAC ortho / Kaguya TC over Apollo 11 | none (fit metrics + visual) | Real multi-sensor operation |
| **NEG** | Two non-overlapping tiles | must REJECT | Honest refusal |

## 4. Ablation table (reported in README)

| Variant | Purpose |
|---|---|
| SIFT + RANSAC on raw images | Classical baseline |
| RoMa v2 on raw images | Foundation-matcher contribution |
| RoMa v2 on the Sun-matched render (full CHITRA) | Value of Render-and-Match |
| Full CHITRA without grid balancing | Value of the uniform-distribution step |

## 5. Literature baselines (cited, not ours)
- SIFT IIRS→WAC: mean ≈ 73 m RMS; fails past ±55° latitude (Preprints 2025, not peer reviewed).
- CNSFM crater topology: 72.3 % success at the South Pole vs SIFT 17.3 % (Xie 2025).
- Georgakis 2024 fine-tuned LoFTR: 41.8 % at 180° azimuth difference, where SIFT scores ≈ 0 %.
