"""CHITRA web demo: browse registration runs and register a new uploaded pair.

uv run uvicorn app.main:app --port 8000     (then open http://localhost:8000)
"""
import json
import re
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from chitra import pipeline
from chitra.prep import normalize

RUNS = Path("runs")
STATIC = Path(__file__).parent / "static"
UPLOAD_EXT = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD = 300 * 2**20  # bytes per file

PREVIEWS = {"overlay_matches", "checkerboard", "overlay_residuals", "render"}
PREVIEW_PX = 1600

RUNS.mkdir(exist_ok=True)
app = FastAPI(title="CHITRA", description="Chandrayaan-2 image registration (SIH 2026 PS 26166)")


def _run_summary(d):
    cfg = json.loads((d / "config.json").read_text()) if (d / "config.json").exists() else {}
    return {"id": d.name, "metrics": json.loads((d / "metrics.json").read_text()),
            "config": {k: cfg.get(k) for k in ("src", "ref", "dem", "sun_used", "src_gsd", "ref_gsd", "matcher",
                                               "model", "benchmark_case", "src_shape", "ref_shape")},
            "files": sorted(f.name for f in d.iterdir() if f.is_file())}


@app.get("/api/runs")
def list_runs():
    return [_run_summary(d) for d in sorted(RUNS.iterdir(), reverse=True) if (d / "metrics.json").exists()]


@app.get("/api/benchmark")
def benchmark():
    f = RUNS / "benchmark.json"
    if not f.exists():
        raise HTTPException(404, "no benchmark yet: run `uv run chitra benchmark`")
    return json.loads(f.read_text())


async def _save(upload: UploadFile, folder: Path, stem: str) -> Path:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in UPLOAD_EXT:
        raise HTTPException(400, f"{stem}: use one of {sorted(UPLOAD_EXT)} (PDS products: cut with scripts/prep_ch2.py)")
    path = folder / f"{stem}{ext}"
    size = 0
    with open(path, "wb") as fh:
        while chunk := await upload.read(2**20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, f"{stem}: larger than {MAX_UPLOAD // 2**20} MB")
            fh.write(chunk)
    return path


@app.post("/api/register")
async def register(
    src: Annotated[UploadFile, File()],
    ref: Annotated[UploadFile, File()],
    dem: Annotated[UploadFile | None, File()] = None,
    sun_az: Annotated[float | None, Form(ge=0, le=360)] = None,
    sun_el: Annotated[float | None, Form(ge=-5, le=90)] = None,
    src_gsd: Annotated[float | None, Form(gt=0)] = None,
    ref_gsd: Annotated[float | None, Form(gt=0)] = None,
    matcher: Annotated[str, Form(pattern="^(auto|roma|sift)$")] = "auto",
    model: Annotated[str, Form(pattern="^(affine|homography)$")] = "affine",
    name: Annotated[str, Form(max_length=40)] = "upload",
):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        s, r = await _save(src, tmp, "src"), await _save(ref, tmp, "ref")
        d = await _save(dem, tmp, "dem") if dem is not None and dem.filename else None
        sun = (sun_az, sun_el) if sun_az is not None and sun_el is not None else None
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", name) or "upload"
        try:
            # ponytail: one registration at a time per worker; add a job queue if several users run at once
            _, run_dir = await run_in_threadpool(pipeline.register_files, s, r, d, sun, src_gsd, ref_gsd,
                                                 matcher=matcher, model=model, out=RUNS, name=safe,
                                                 extra_config={"uploaded": True})
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:  # unreadable raster etc.
            raise HTTPException(422, f"registration failed: {type(e).__name__}: {e}")
    return _run_summary(Path(run_dir))


def make_preview(png: Path) -> Path:
    """<name>.preview.jpg next to <name>.png: longest side <= PREVIEW_PX (full PNGs reach 60+ MB for OHRC)."""
    import cv2
    out = png.with_suffix(".preview.jpg")
    if not out.exists() or out.stat().st_mtime < png.stat().st_mtime:
        img = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
        img = img if img.dtype == "uint8" else normalize(img)
        f = min(1.0, PREVIEW_PX / max(img.shape[:2]))
        small = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out), small, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out


@app.get("/runs/{run_id}/{name}.preview.jpg")
def preview(run_id: str, name: str):
    png = RUNS / run_id / f"{name}.png"
    if not re.fullmatch(r"[\w-]+", run_id) or name not in PREVIEWS or not png.exists():
        raise HTTPException(404)
    return FileResponse(make_preview(png), media_type="image/jpeg")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/runs", StaticFiles(directory=RUNS), name="runs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
