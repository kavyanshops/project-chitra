# CHITRA

**Chandrayaan High-precision Image Transformation & Registration Algorithm** — SIH 2026 · PS 26166 · Team Death Eaters

Multi-modal, Sun-angle- and scale-invariant registration of Chandrayaan-2 **OHRC / TMC-2 / IIRS** imagery to lunar references (**LRO NAC / WAC, SELENE TC**). The Render-and-Match approach renders the reference DEM under the **source's own Sun geometry** with a Hapke reflectance model, matches densely with **RoMa v2 (DINOv3)**, fits with **MAGSAC++** on grid-balanced matches, and outputs a registered GeoTIFF with match points, RMSE / inlier / coverage metrics and a **PASS / FLAG / REJECT verdict**.

| Doc | Contents |
|---|---|
| [PRD](docs/PRD.md) | Problem, scope, success criteria, claims policy |
| [Architecture](docs/ARCHITECTURE.md) | Pipeline, modules, design decisions |
| [Metrics](docs/METRICS.md) | Metric definitions, verdict policy, evaluation sets, ablations |
| [Data](docs/DATA.md) | Reference + Chandrayaan-2 data acquisition |
| [Roadmap](docs/ROADMAP.md) | Post-prototype research plan, known limitations |

> Status: Phase 0 (docs). The engine and demo land in Phases 1–2.
