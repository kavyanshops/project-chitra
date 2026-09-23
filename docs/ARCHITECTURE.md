# CHITRA — Architecture

## 1. Pipeline

```
 ┌───────────── inputs ─────────────┐
 │ source image (OHRC/TMC-2/IIRS)   │   Sun az/el, GSD ← PDS4 XML or CLI
 │ reference image (NAC/TC/WAC)     │
 │ DEM (NAC DTM / SLDEM / LOLA)     │   optional; enables Render-and-Match
 └───────────────┬──────────────────┘
                 ▼
 A. PREPARE       read → resample to common GSD → percentile normalise → CLAHE
                  shadow/saturation mask   (IIRS: bad-band screen → PCA-1 proxy)
                 ▼
 B. RENDER        DEM → surface normals → Hapke shading at SOURCE Sun geometry
                  + cast-shadow mask (ray-march along Sun azimuth)
                  → reference domain now "lit like" the source
                 ▼
 C. MATCH         SIFT + Lowe ratio on source ↔ render and source ↔ reference (auto)
                  [GPU option: RoMa v2 dense warp + certainty]
                 ▼
 D. GEOMETRY      certainty ≥ τ  →  grid-balanced sampling (k per cell)
                  → MAGSAC++ (cv2.USAC_MAGSAC) → affine | homography
                 ▼
 E. VERIFY        residuals, RMSE, inlier ratio, coverage entropy, shadow fraction
                  → PASS / FLAG / REJECT + reason
                 ▼
 F. OUTPUT        registered GeoTIFF · matches.csv · metrics.json · overlays/*.png
```

The design follows the report's rule: **geometry and physics first, learning second, verification always.**

## 2. Components

| Module | Responsibility | Key libraries |
|---|---|---|
| `chitra/io.py` | Read GeoTIFF/PNG/PDS via GDAL; parse Sun geometry from PDS4 XML; write GeoTIFF with the reference CRS/transform | rasterio, lxml |
| `chitra/prep.py` | Normalisation, CLAHE, masks, IIRS PCA proxy, resampling to a common GSD | numpy, OpenCV |
| `chitra/render.py` | Hapke / Lommel-Seeliger shading, cast shadows, synthetic pair generator with known warp | numpy |
| `chitra/match.py` | RoMa v2 wrapper (device: cuda → mps → cpu) and SIFT baseline | torch, romav2, OpenCV |
| `chitra/geometry.py` | Grid-balanced sampling, MAGSAC++ fit, residuals, warping | OpenCV |
| `chitra/metrics.py` | RMSE / median / P90, inliers, coverage entropy, GT RMSE, verdict | numpy |
| `chitra/pipeline.py` + `cli.py` | Orchestration, run folder, config snapshot | stdlib |
| `app/` | FastAPI API + single-page UI | FastAPI, uvicorn |
| `notebooks/chitra_colab.ipynb` | GPU run on Colab | — |

## 3. Key technical decisions

| Decision | Choice | Why |
|---|---|---|
| Matcher | **SIFT on the Sun-matched render** (local default); **RoMa v2** optional on GPU | Once the render removes the illumination difference, a classical matcher reaches sub-pixel accuracy on a laptop CPU. RoMa v2 (DINOv3, dense, SOTA on extreme photometric change, arXiv 2511.15706) is too heavy for the 16 GB dev laptop, so it is an optional `[roma]` extra for Colab. |
| Match domain | `auto`: try the real reference **and** the render, keep the better verdict | The render wins under large Sun changes; the real reference wins when the Sun already agrees, because the DTM render has no albedo texture. The chosen domain is recorded in `metrics.json`. |
| Illumination handling | **Render the reference at the source's Sun** | Removes the Sun-angle difference by construction (Grumpe 2014; NASA LuNaMaps), instead of learning invariance to it. |
| Reflectance model | Lommel-Seeliger disk function × Hapke single-term Henyey-Greenstein phase function | Physically grounded for regolith, cheap, and has no unconstrained parameters. The full Hapke model (roughness θ̄, opposition surge) is on the roadmap. |
| Robust estimator | **MAGSAC++** | Threshold-free marginalisation. It is more accurate than vanilla RANSAC and already built into OpenCV ≥ 4.5. |
| Uniform distribution | Grid-balanced sampling *before* fitting, coverage entropy *after* | The PS explicitly requires even spread, and clustered inliers give a misleading RMSE. |
| Transform model | Affine (default) / homography, on DEM-orthorectified or map-projected tiles | The report warns against one global homography over long strips. The prototype registers **local tiles**; strip-wise adjustment is on the roadmap. |
| Scale bridging | Resample both images to a common working GSD before matching; residuals are reported in **source pixels** | This turns scale into a resampling/rendering parameter, and the PS asks for accuracy in *source-image* pixels. |
| Safety | Verdict + reason on every run | "Do not report success merely because RANSAC returned a matrix" (report §7.2). |

## 4. Coordinate conventions
- Reference products stay in their own CRS (for LROC ortho/DTM: Moon 2015 equirectangular or polar stereographic, metres). The registered source is written onto the **reference grid**.
- Residuals and RMSE are in **source-image pixels**, with metres reported alongside (`px × source GSD`).
- Sun azimuth is measured clockwise from north (PDS convention); elevation = 90° − incidence.

## 5. Run artefacts

```
runs/<timestamp>_<name>/
  config.json        exact inputs + parameters (reproducible)
  metrics.json       all metrics + verdict + reasons
  matches.csv        x_src,y_src,x_ref,y_ref,certainty,inlier,residual_px
  registered.tif     source warped onto the reference grid (GeoTIFF when the ref is georeferenced)
  overlay_matches.png, overlay_residuals.png, checkerboard.png, render.png
```

## 6. Deployment
- **Local:** `uv run chitra register …` and `uv run uvicorn app.main:app`.
- **GPU:** Colab notebook clones the repo and runs the same CLI on CUDA.
- **Public link for the PPT:** the GitHub repo + Colab badge + a hosted results page.
