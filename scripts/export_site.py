"""Export the demo as a static site (for GitHub Pages / any static host): the same index.html, reading
runs.json + benchmark.json instead of the live API. Only the newest run of each name is exported, with JPEG
previews and the small result files; registered GeoTIFFs stay local (tens of MB each).

uv run python scripts/export_site.py [--out site]
"""
import argparse
import json
import re
import shutil
from pathlib import Path

from app.main import PREVIEWS, RUNS, STATIC, _run_summary, make_preview

SMALL = ("metrics.json", "config.json", "matches.csv")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="site")
    p.add_argument("--skip", nargs="*", default=["api_test", "upload"], help="run names to leave out")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    for f in out.iterdir():  # keep .vercel (the Vercel project link, so redeploys keep the same URL)
        if f.name != ".vercel":
            shutil.rmtree(f) if f.is_dir() else f.unlink()
    (out / "runs").mkdir()

    newest = {}
    for d in sorted(RUNS.iterdir(), reverse=True):
        name = re.sub(r"^\d{8}-\d{6}_", "", d.name)
        if (d / "metrics.json").exists() and name not in newest and name not in a.skip:
            newest[name] = d

    summaries = []
    for d in newest.values():
        dst = out / "runs" / d.name
        dst.mkdir()
        for f in SMALL:
            if (d / f).exists():
                shutil.copy(d / f, dst / f)
        for k in PREVIEWS:
            if (d / f"{k}.png").exists():
                shutil.copy(make_preview(d / f"{k}.png"), dst / f"{k}.preview.jpg")
        s = _run_summary(dst)
        summaries.append(s)
    (out / "runs.json").write_text(json.dumps(summaries, indent=1))
    if (RUNS / "benchmark.json").exists():
        shutil.copy(RUNS / "benchmark.json", out / "benchmark.json")
    shutil.copy(STATIC / "index.html", out / "index.html")
    (out / ".nojekyll").write_text("")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"{len(summaries)} runs -> {out}/ ({size / 2**20:.1f} MB)")


if __name__ == "__main__":
    main()
