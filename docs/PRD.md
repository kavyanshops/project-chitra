# CHITRA — Product Requirements Document

**Chandrayaan High-precision Image Transformation & Registration Algorithm**
SIH 2026 · PS 26166 · Theme: Space Technology · Category: Software · Team Death Eaters

| | |
|---|---|
| Version | 0.1 (prototype) |
| Status | Prototype for SIH final-round selection |
| Owner | Team Death Eaters |
| Source research | `SIH-26166_Deep_Research_Report.pdf`, `sih_final.pdf` (idea deck) |

---

## 1. Problem

Registration aligns a **source (moving)** image to a **reference (fixed)** image in a common lunar coordinate frame. For Chandrayaan-2, three effects happen at once:

| Challenge | Why it is hard on the Moon |
|---|---|
| **Illumination variation** | No atmosphere, so Sun azimuth and elevation reshape crater appearance (bright rim → dark rim → invisible). SIFT collapses beyond ~60° Sun-azimuth difference. |
| **Scale variation** | OHRC 0.25 m/px · TMC-2 5 m/px · IIRS ~80 m/px against LRO NAC 0.5 m · Kaguya TC ~10 m · LRO WAC ~100 m. Ratios reach 320:1 (OHRC↔IIRS) and ~400:1 (OHRC↔WAC). SIFT's scale space covers about 8×. |
| **Viewpoint variation** | Off-nadir and pushbroom geometry over 3D terrain cause parallax that a single homography cannot represent. |
| **Cross-modality** (hidden) | IIRS is a 256-band 0.8–5 µm hyperspectral cube, while OHRC and TMC-2 are panchromatic. |
| **Weak texture** (hidden) | Mare plains and polar shadow leave few stable features. |

**Expected solution (from PS 26166):** generic software that finds correspondences between Chandrayaan-2 optical images and lunar reference images with **sub-pixel accuracy (of the source image)** and a **uniform spatial distribution** of matches. It outputs a **registered product with match points** and **evaluation metrics** (RMSE, inlier count, inlier ratio, …).

## 2. Core idea — Render-and-Match

Every existing lunar registration pipeline treats registration as a 2D image-to-image problem. But the Moon's reference is **3D (a DEM) and photometrically modellable (Hapke)**. CHITRA therefore **renders the reference at the source's own Sun geometry** and then matches source against render. The illumination difference is removed by construction, and scale becomes a rendering-resolution parameter instead of a scale-space limit.

## 3. Users & stakeholders

| User | Need |
|---|---|
| ISRO SAC / ISSDC (PRADAN) | Automated seleno-referenced Ch-2 products without manual GCPs |
| Lunar scientists | Ch-2 data that can be compared across missions with LRO/SELENE archives |
| Landing / TRN teams | Registered maps **with a confidence value**, never a silent failure |

## 4. Prototype scope (this submission)

### In scope — must work end to end
- **F1 Ingest.** GeoTIFF / PNG / PDS `.img+.xml` (via GDAL) for source and reference. Read Sun azimuth and elevation from metadata or CLI flags.
- **F2 Preprocess.** Robust percentile normalisation, CLAHE, shadow/saturation mask. For IIRS: band-quality screening and a PCA-1 registration proxy.
- **F3 Physics render.** Hapke-family shading (Lommel-Seeliger + Hapke phase term) of a DEM at the source Sun geometry, with a cast-shadow mask.
- **F4 Dense matching.** RoMa v2 (DINOv3 backbone), with dense warp + certainty. **Baseline:** SIFT + Lowe ratio + RANSAC, for comparison.
- **F5 Robust geometry.** Certainty threshold → grid-balanced sampling (uniform distribution) → MAGSAC++ (OpenCV USAC) → affine or homography.
- **F6 Metrics.** RMSE, median/P90 residual, inlier count, inlier ratio, grid coverage entropy. RMSE against **ground truth** when it is known.
- **F7 Verdict.** PASS / FLAG / REJECT, each with a machine-readable reason. A wrong registration must never be silently accepted.
- **F8 Outputs.** Registered GeoTIFF, GCP/match CSV with per-point certainty, `metrics.json`, and overlay PNGs (matches, residual arrows, checkerboard).
- **F9 Synthetic benchmark.** Real DEM rendered at two Sun geometries + a known warp/scale gives measured RMSE against the truth.
- **F10 Web demo.** Pick or upload a pair, run it, and view results. A Colab notebook covers GPU runs.

### Out of scope today (roadmap — see `ROADMAP.md`)
Crater-topology fallback (CNSFM, needs a YOLOv9 crater detector) · LoRA fine-tuning on synthetic renders · physics-biased attention inside the matcher · Mitsuba 3 differentiable pose optimisation · ISIS/ASP CSM camera models and SPICE pose · Expected Calibration Error on real lunar ground truth · LunarMatch benchmark release.

## 5. Success criteria (prototype)

| # | Criterion | How it is measured |
|---|---|---|
| S1 | Runs end to end on a real pair and writes every F8 output | CLI exit 0; files present |
| S2 | **Sub-pixel RMSE on synthetic cross-illumination pairs** with known truth | `metrics.json → gt_rmse_px < 1.0` |
| S3 | CHITRA beats the SIFT baseline under a large Sun-azimuth difference | Inlier count and GT RMSE, side-by-side table |
| S4 | Uniform distribution | Coverage entropy ≥ 0.8 on PASS results |
| S5 | Honest refusal | Non-overlapping pair → REJECT with a reason, not a matrix |

**Claims policy.** Report only measured numbers. "Sub-pixel on OHRC↔NAC" is the target stated in the deck; the prototype reports what it achieves on each pair. Literature figures (≈73 m IIRS→WAC SIFT, 72.3 % CNSFM polar) are cited as *reported baselines*, not as our results.

## 6. Constraints
- Development on an Apple M4 with 16 GB (PyTorch MPS / CPU); heavy runs on a Colab/Kaggle GPU.
- Chandrayaan-2 data comes from ISSDC PRADAN (login required); references come from public LROC / PDS / JAXA archives.
- Everything open-source. RoMa v2 is MIT; DINOv3 weights ship under Meta's DINOv3 licence.
