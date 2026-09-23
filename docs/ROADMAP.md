# CHITRA — Roadmap

## Prototype (this submission)
- [x] Phase 0 — docs + skeleton
- [x] Phase 1 — engine: ingest → Hapke render → SIFT (RoMa v2 optional, GPU) → MAGSAC++ → metrics/verdict → GeoTIFF; synthetic + LROC benchmark
- [ ] Phase 1b — run TMC-2 / OHRC ↔ NAC once PRADAN scenes are in `data/raw/ch2/`; RoMa v2 benchmark on Colab GPU
- [ ] Phase 2 — web demo (FastAPI + UI) + Colab notebook + results in README

## After selection (from report §13)

| Stage | Work | Exit criterion |
|---|---|---|
| I · Baselines (wk 1–2) | SIFT/ORB/RIFT2 baselines; scene catalogue (lat, Sun, GSD, DEM availability); ISIS `spiceinit` + ALE/CSM camera models | Reproducible baseline table |
| II · Physics matching (wk 3–4) | Full Hapke (θ̄, opposition surge; Sato 2014 parameter maps); SPICE-initialised footprint; IIRS–WAC and TMC-2 benchmark | Beats ≈73 m IIRS→WAC baseline on comparable scenes |
| III · Synthetic adaptation (wk 5–8) | 100k DEM-rendered pairs; LoRA on the last 3 transformer layers; physics bias B_phys = g(R_h) added to attention logits | ≥15 % RMSE reduction over zero-shot, or stop |
| IV · Topology + uncertainty (wk 9–12) | YOLOv9 crater detector + CNSFM neighbourhood matcher as polar fallback; covariance-weighted fitting; ECE calibration | Polar success rate reported; ECE on held-out scenes |
| V · Benchmark | "LunarMatch" (200 pairs, ICP-to-LOLA truth), Mitsuba 3 differentiable pose refinement, staged OHRC→TMC-2→Kaguya→WAC pyramid | Public release + paper (ISPRS JPRS / IEEE TGRS) |

## Known limitations of the prototype
- Local-tile affine/homography only, with no strip-wise or DEM-forward-projection model yet.
- Single-term Hapke without roughness or opposition effect.
- No SPICE-based initial pose: tiles are assumed to overlap. The verdict rejects them when they don't.
- RoMa certainty is not calibrated on lunar data, so it is used for ranking and filtering, not as a probability.
- The local matcher is SIFT. On a real image against a 2 m DTM render it finds few matches, because the render has no albedo or sub-DTM texture. `auto` mode then falls back to the real reference. A cross-modal matcher (RoMa v2 on GPU) is the planned fix.
- The LROC Apollo 11 labels carry no Sun angles, so the Sun geometry for the real pair is estimated by fitting DTM renders.
